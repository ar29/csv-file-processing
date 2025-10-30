# Monitoring Configuration

This directory contains all monitoring and observability configuration for the CSV File Processing Service.

## Directory Structure

```
monitoring/
├── README.md                           # This file
├── prometheus.yml                      # Prometheus configuration
└── grafana/                            # Grafana configuration
    └── provisioning/                   # Auto-provisioning configs
        ├── datasources/                # Data source configs
        │   └── prometheus.yml          # Prometheus datasource
        └── dashboards/                 # Dashboard configs
            ├── dashboard.yml           # Dashboard provider config
            └── csv-processor-overview.json  # Main dashboard
```

## Prometheus Configuration

The `prometheus.yml` file configures:

- **Scrape interval**: 15 seconds (adjustable based on your needs)
- **Scrape targets**: API service metrics endpoint
- **Retention**: Default 15 days (configurable in docker-compose.yml)

### Metrics Collected

The service exposes the following Prometheus metrics:

| Metric Name | Type | Description |
|-------------|------|-------------|
| `csv_processing_total` | Counter | Total files processed (by status) |
| `csv_processing_errors_total` | Counter | Total processing errors (by type) |
| `csv_validation_failures_total` | Counter | Validation failures (by type) |
| `csv_rows_processed_total` | Counter | Total rows processed |
| `csv_rows_valid_total` | Counter | Total valid rows |
| `csv_processing_duration_seconds` | Histogram | Processing time distribution |
| `csv_file_size_bytes` | Histogram | File size distribution |
| `rabbitmq_queue_depth` | Gauge | Current queue depth |
| `active_workers` | Gauge | Active worker count |

### Accessing Prometheus

- **URL**: http://localhost:9090
- **No authentication** required in development
- **PromQL**: Use for querying metrics

Example queries:
```promql
# Average processing time over last 5 minutes
rate(csv_processing_duration_seconds_sum[5m]) / rate(csv_processing_duration_seconds_count[5m])

# Error rate
rate(csv_processing_errors_total[5m])

# Success rate
rate(csv_processing_total{status="completed"}[5m]) / rate(csv_processing_total[5m]) * 100
```

## Grafana Configuration

Grafana is pre-configured with:

1. **Datasource**: Prometheus (auto-configured)
2. **Dashboard**: CSV Processor Overview (auto-imported)

### Accessing Grafana

- **URL**: http://localhost:3000
- **Username**: admin
- **Password**: admin (change on first login)

### Pre-configured Dashboard

The **CSV Processor Overview** dashboard includes:

#### Key Metrics (Top Row)
- Total Files Processed
- Valid Rows Processed
- Processing Errors
- Average Processing Time (95th percentile)

#### Charts
1. **Processing Rate**: Files processed per second (completed vs failed)
2. **Processing Duration Percentiles**: 50th, 95th, 99th percentiles
3. **Validation Failures Rate**: Breakdown by validation type
4. **RabbitMQ Queue Depth**: Current backlog

### Customising Dashboards

1. **Edit existing dashboard**:
   - Go to dashboard → Click "Dashboard settings" (gear icon)
   - Make changes
   - Save

2. **Create new dashboard**:
   - Click "+" → "Dashboard"
   - Add panels with PromQL queries
   - Save dashboard

3. **Export dashboard**:
   ```bash
   # Save to file
   curl http://admin:admin@localhost:3000/api/dashboards/uid/csv-processor-overview | \
     jq .dashboard > my-dashboard.json
   ```

4. **Import dashboard**:
   - Copy JSON to `grafana/provisioning/dashboards/`
   - Restart Grafana: `docker-compose restart grafana`

## Alert Configuration

To add alerting:

1. **Create alert rules** in `prometheus-alerts.yml`:

```yaml
groups:
  - name: csv_processor_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: rate(csv_processing_errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors/second"
      
      - alert: LargeQueueBacklog
        expr: rabbitmq_queue_depth > 1000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Large queue backlog"
          description: "Queue has {{ $value }} messages"
      
      - alert: SlowProcessing
        expr: histogram_quantile(0.95, rate(csv_processing_duration_seconds_bucket[5m])) > 300
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Slow processing detected"
          description: "95th percentile is {{ $value }}s"
```

2. **Update prometheus.yml**:

```yaml
rule_files:
  - "prometheus-alerts.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']
```

3. **Configure Alertmanager** (optional):

Add to `docker-compose.yml`:
```yaml
alertmanager:
  image: prom/alertmanager:latest
  ports:
    - "9093:9093"
  volumes:
    - ./monitoring/alertmanager.yml:/etc/alertmanager/alertmanager.yml
```

## Retention Policies

### Prometheus
- Default: 15 days
- Configure in docker-compose.yml:
  ```yaml
  command:
    - '--storage.tsdb.retention.time=30d'
  ```

### Grafana
- Dashboards: Stored in database (persistent volume)
- Backups: Export dashboards as JSON regularly

## Production Considerations

### Security
1. **Enable authentication** on Prometheus:
   ```yaml
   basic_auth_users:
     admin: $2y$10$...  # bcrypt hash
   ```

2. **Use HTTPS** with reverse proxy (nginx/traefik)

3. **Restrict access** with firewall rules

### Scaling
1. **Prometheus federation** for multiple instances
2. **Thanos** for long-term storage
3. **Grafana HA** with load balancer

### Storage
1. **Prometheus**: Use persistent volume
   ```yaml
   volumes:
     - prometheus_data:/prometheus
   ```

2. **Grafana**: Use persistent volume
   ```yaml
   volumes:
     - grafana_data:/var/lib/grafana
   ```

## Troubleshooting

### Prometheus not scraping metrics

1. Check target status:
   - Go to http://localhost:9090/targets
   - Verify API service is UP

2. Test metrics endpoint:
   ```bash
   curl http://localhost:8000/metrics
   ```

3. Check Prometheus logs:
   ```bash
   docker-compose logs prometheus
   ```

### Grafana dashboard not showing data

1. **Check datasource**:
   - Settings → Data Sources → Prometheus
   - Click "Test" button

2. **Verify query**:
   - Edit panel → View query inspector
   - Run query in Prometheus UI

3. **Check time range**:
   - Ensure time range includes data

### Missing metrics

1. **Verify metric exists**:
   ```bash
   curl http://localhost:8000/metrics | grep metric_name
   ```

2. **Check scrape interval**:
   - Metrics appear after first scrape (15s default)

3. **Restart services**:
   ```bash
   docker-compose restart api prometheus
   ```

## Best Practises

1. **Set appropriate scrape intervals**:
   - High-frequency: 5-10s (development/testing)
   - Production: 15-30s (balance between accuracy and load)

2. **Use labels wisely**:
   - Keep cardinality low (avoid unbounded labels like user IDs)
   - Use consistent naming conventions

3. **Create meaningful dashboards**:
   - Group related metrics
   - Use appropriate visualisations
   - Add descriptions to panels

4. **Set up alerts for critical issues**:
   - High error rates
   - Service unavailability
   - Resource exhaustion
   - Queue backlogs

5. **Regular maintenance**:
   - Export important dashboards
   - Review and update alert thresholds
   - Clean up old metrics

## Additional Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Tutorial](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Dashboards](https://grafana.com/grafana/dashboards/)

## Support

For monitoring-related issues:
- Check service logs: `docker-compose logs prometheus grafana`
- Verify configurations in this directory
- Review Prometheus targets: http://localhost:9090/targets