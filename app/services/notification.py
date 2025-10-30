"""
Notification service for sending emails and webhooks.
Handles user notifications about processing completion.
"""
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import httpx
from typing import Optional, Dict
from app.config import get_settings
from app.utils.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class NotificationService:
    """Handles sending notifications via email and webhooks"""
    
    async def send_email(self, to_email: str, subject: str, body: str) -> bool:
        """
        Sends email notification.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body (HTML supported)
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not settings.smtp_user or not settings.smtp_password:
            logger.warning("SMTP credentials not configured, skipping email")
            return False
        
        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = subject
            message['From'] = settings.smtp_from
            message['To'] = to_email
            
            # Add HTML body
            html_part = MIMEText(body, 'html')
            message.attach(html_part)
            
            # Send email
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user,
                password=settings.smtp_password,
                start_tls=True
            )
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    async def send_webhook(self, webhook_url: str, payload: Dict) -> bool:
        """
        Sends webhook notification.
        
        Args:
            webhook_url: Webhook URL
            payload: JSON payload to send
        
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    timeout=30.0
                )
                
                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(f"Webhook sent successfully to {webhook_url}")
                    return True
                else:
                    logger.warning(f"Webhook failed with status {response.status_code}: {webhook_url}")
                    return False
        
        except Exception as e:
            logger.error(f"Failed to send webhook to {webhook_url}: {e}")
            return False
    
    async def notify_processing_complete(
        self,
        job_id: str,
        filename: str,
        status: str,
        total_rows: int,
        valid_rows: int,
        invalid_rows: int,
        processing_time: float,
        errors: Optional[list] = None,
        email: Optional[str] = None,
        webhook_url: Optional[str] = None
    ):
        """
        Sends notification about processing completion.
        
        Args:
            job_id: Unique job identifier
            filename: Name of processed file
            status: Processing status (completed/failed)
            total_rows: Total number of rows
            valid_rows: Number of valid rows
            invalid_rows: Number of invalid rows
            processing_time: Processing duration in seconds
            errors: List of error messages
            email: Optional email address for notification
            webhook_url: Optional webhook URL for notification
        """
        # Prepare notification data
        notification_data = {
            'job_id': str(job_id),
            'filename': filename,
            'status': status,
            'total_rows': total_rows,
            'valid_rows': valid_rows,
            'invalid_rows': invalid_rows,
            'processing_time_seconds': round(processing_time, 2),
            'errors': errors[:10] if errors else []  # limit errors in notification
        }
        
        # Send email if provided
        if email:
            subject = f"CSV Processing {status.title()}: {filename}"
            body = self._generate_email_body(notification_data)
            await self.send_email(email, subject, body)
        
        # Send webhook if provided
        if webhook_url:
            await self.send_webhook(webhook_url, notification_data)
    
    def _generate_email_body(self, data: Dict) -> str:
        """
        Generates HTML email body from notification data.
        
        Args:
            data: Notification data dictionary
        
        Returns:
            HTML string
        """
        status_color = '#28a745' if data['status'] == 'completed' else '#dc3545'
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: {status_color}; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; border: 1px solid #ddd; }}
                .stat {{ margin: 10px 0; }}
                .label {{ font-weight: bold; }}
                .errors {{ background-color: #fff3cd; padding: 10px; margin-top: 15px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>CSV Processing {data['status'].title()}</h2>
                </div>
                <div class="content">
                    <div class="stat">
                        <span class="label">Job ID:</span> {data['job_id']}
                    </div>
                    <div class="stat">
                        <span class="label">Filename:</span> {data['filename']}
                    </div>
                    <div class="stat">
                        <span class="label">Status:</span> {data['status'].upper()}
                    </div>
                    <div class="stat">
                        <span class="label">Total Rows:</span> {data['total_rows']}
                    </div>
                    <div class="stat">
                        <span class="label">Valid Rows:</span> {data['valid_rows']}
                    </div>
                    <div class="stat">
                        <span class="label">Invalid Rows:</span> {data['invalid_rows']}
                    </div>
                    <div class="stat">
                        <span class="label">Processing Time:</span> {data['processing_time_seconds']} seconds
                    </div>
        """
        
        if data.get('errors'):
            html += """
                    <div class="errors">
                        <strong>Errors (first 10):</strong>
                        <ul>
            """
            for error in data['errors']:
                html += f"<li>{error}</li>"
            html += """
                        </ul>
                    </div>
            """
        
        html += """
                </div>
            </div>
        </body>
        </html>
        """
        
        return html


# Singleton instance
notification_service = NotificationService()