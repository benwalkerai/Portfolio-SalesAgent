"""
Email sending functionality using SendGrid.

Author : Ben Walker (BenRWalker@icloud.com)
"""

# Modules
import asyncio
import os
from typing import Dict, Optional, Any

import sendgrid
from dotenv import load_dotenv
from sendgrid.helpers.mail import Content, Email, Mail, To

from agents import function_tool
from logger_config import setup_logger

logger = setup_logger(__name__)

load_dotenv()

from_email: Optional[str] = os.environ.get('FROM_EMAIL')
to_email: Optional[str] = os.environ.get('TO_EMAIL')

logger.info(f"Email service configured - From: {from_email}, To: {to_email}")

async def send_html_email(subject: str, html_body: str, recipient_email: Optional[str] = None) -> Dict[str, Any]:
    logger.info(f"Attempting to send email with subject: {subject}")
    logger.debug(f"Email body length: {len(html_body)} characters")
    
    sendgrid_api_key = os.environ.get('SENDGRID') or os.environ.get('SENDGRID_API_KEY')
    if not sendgrid_api_key:
        logger.error("SENDGRID / SENDGRID_API_KEY not found in environment variables")
        return {"status": "error", "message": "SENDGRID / SENDGRID_API_KEY not configured"}
    
    if not from_email:
        logger.error("FROM_EMAIL not configured", extra={"from_email": from_email})
        return {"status": "error", "message": "FROM_EMAIL not configured"}

    target_recipient = recipient_email or to_email
    if not target_recipient:
        logger.error(
            "No recipient email specified",
            extra={"recipient_email": recipient_email, "default_to_email": to_email}
        )
        return {"status": "error", "message": "Recipient email not provided"}
    
    def _send_email_request() -> Dict[str, Any]:
        sg = sendgrid.SendGridAPIClient(api_key=sendgrid_api_key)
        from_email_obj = Email(from_email)
        to_email_obj = To(target_recipient)
        content = Content("text/html", html_body)
        mail = Mail(from_email_obj, to_email_obj, subject, content)
        response = sg.client.mail.send.post(request_body=mail.get())
        return {
            "status_code": response.status_code,
            "headers": getattr(response, "headers", {}) or {}
        }
    
    try:
        send_result = await asyncio.to_thread(_send_email_request)
        status_code = send_result.get("status_code")
        headers = send_result.get("headers", {})
        message_id = headers.get("X-Message-Id") or headers.get("x-message-id")
        logger.info(
            "Email sent successfully",
            extra={
                'subject': subject,
                'status_code': status_code,
                'to': target_recipient,
                'message_id': message_id
            }
        )
        return {
            "status": "success",
            "status_code": status_code,
            "to": target_recipient,
            "from": from_email,
            "subject": subject,
            "message_id": message_id,
            "body_length": len(html_body)
        }
    except Exception as e:
        logger.error(
            f"Failed to send email: {e}",
            exc_info=True,
            extra={
                'subject': subject,
                'to': to_email
            }
        )
        return {
            "status": "error",
            "message": str(e)
        }

send_html_email_tool = function_tool(send_html_email)
