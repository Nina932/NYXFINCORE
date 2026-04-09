"""
FinAI Modern Email Service
==========================
Sends beautifully formatted HTML emails with modern Excel report attachments.
Features modern email templates with professional styling and branding.
"""

import logging
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import smtplib

from app.config import settings

logger = logging.getLogger(__name__)


class ModernEmailService:
    """Modern email service for sending professional reports."""

    def __init__(self):
        self.smtp_enabled = (
            getattr(settings, "SMTP_ENABLED", False)
            or os.getenv("SMTP_ENABLED", "false").lower() == "true"
        )
        self.smtp_host = getattr(settings, "SMTP_HOST", None) or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(getattr(settings, "SMTP_PORT", None) or os.getenv("SMTP_PORT", "587"))
        self.smtp_user = getattr(settings, "SMTP_USER", None) or os.getenv("SMTP_USER", "")
        self.smtp_password = getattr(settings, "SMTP_PASSWORD", None) or os.getenv("SMTP_PASSWORD", "")
        self.smtp_from = getattr(settings, "SMTP_FROM", None) or os.getenv("SMTP_FROM", "FinAI Reports <reports@finai.ai>")

    def send_report_email(
        self,
        recipients: List[str],
        subject: str,
        report_type: str,
        company_name: str,
        period: str,
        excel_attachment: bytes,
        filename: str,
        custom_message: Optional[str] = None,
        summary_data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Send a modern HTML email with Excel report attachment.

        Args:
            recipients: List of email addresses
            subject: Email subject line
            report_type: Type of report (e.g., "Cash Runway Analysis", "P&L Comparison")
            company_name: Company name for the report
            period: Reporting period
            excel_attachment: Excel file bytes
            filename: Name for the Excel attachment
            custom_message: Optional custom message from user

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.smtp_enabled:
            logger.warning("SMTP not enabled - email not sent")
            return False

        if not recipients:
            logger.warning("No recipients specified")
            return False

        # Generate modern HTML email body
        html_body = self._generate_modern_html(
            report_type=report_type,
            company_name=company_name,
            period=period,
            custom_message=custom_message,
            summary_data=summary_data,
        )

        try:
            # Create message
            msg = MIMEMultipart("mixed")
            msg["From"] = self.smtp_from
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = subject

            # HTML body
            html_part = MIMEText(html_body, "html", "utf-8")
            msg.attach(html_part)

            # Excel attachment
            excel_part = MIMEBase("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            excel_part.set_payload(excel_attachment)
            encoders.encode_base64(excel_part)
            excel_part.add_header("Content-Disposition", f"attachment; filename={filename}")
            msg.attach(excel_part)

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                # Extract bare email for envelope sender
                from_addr = self.smtp_user or self.smtp_from
                server.sendmail(from_addr, recipients, msg.as_string())

            logger.info(f"Modern report email sent successfully - {report_type} for {company_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to send modern report email: {e}")
            return False

    def _generate_modern_html(
        self,
        report_type: str,
        company_name: str,
        period: str,
        custom_message: Optional[str] = None,
        summary_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate modern HTML email template matching the FinAI brand."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
        report_label = report_type.replace('_', ' ').title()

        def _fmt(n):
            if n is None: return "-"
            try:
                n = float(n)
            except (ValueError, TypeError):
                return str(n)
            sign = "" if n >= 0 else "-"
            abs_n = abs(n)
            if abs_n >= 1e9: return f"{sign}{abs_n/1e9:,.1f}B GEL"
            if abs_n >= 1e6: return f"{sign}{abs_n/1e6:,.1f}M GEL"
            if abs_n >= 1e3: return f"{sign}{abs_n/1e3:,.0f}K GEL"
            return f"{sign}{abs_n:,.0f} GEL"

        # Build KPI cards HTML if summary_data provided
        kpi_html = ""
        if summary_data:
            kpi_items = []
            for key in ["revenue", "gross_profit", "ebitda", "net_profit"]:
                val = summary_data.get(key)
                if val is not None:
                    label = key.replace("_", " ").title()
                    color = "#ef4444" if isinstance(val, (int, float)) and val < 0 else "#ffffff"
                    kpi_items.append(f"""
                    <td style="padding:12px 8px;text-align:center;width:25%;">
                        <div style="font-size:11px;color:rgba(255,255,255,.7);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;">{label}</div>
                        <div style="font-size:18px;font-weight:700;color:{color};">{_fmt(val)}</div>
                    </td>""")
            if kpi_items:
                kpi_html = f"""
                <table style="width:100%;border-collapse:collapse;margin-top:16px;">
                    <tr>{"".join(kpi_items)}</tr>
                </table>"""

        # Build the full HTML
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>[FinAI] {report_label} — {period}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:Calibri,Arial,Helvetica,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:24px 0;">
<tr><td align="center">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.08);">

<!-- HEADER -->
<tr><td style="background:linear-gradient(135deg,#1B3A5C 0%,#2563EB 100%);padding:32px 28px 20px;text-align:center;">
    <div style="font-size:24px;font-weight:700;color:#ffffff;letter-spacing:-0.5px;">{company_name} &mdash; FinAI Report</div>
    <div style="font-size:13px;color:rgba(255,255,255,.8);margin-top:6px;">Financial Report &middot; Period: {period} &middot; Generated: {now}</div>
    {kpi_html}
</td></tr>

<!-- REPORT TYPE BADGE -->
<tr><td style="padding:24px 28px 0;">
    <table role="presentation" cellpadding="0" cellspacing="0"><tr>
        <td style="background:#2563EB;color:#ffffff;padding:6px 16px;border-radius:20px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px;">
            {report_label}
        </td>
    </tr></table>
</td></tr>

<!-- COMPANY & PERIOD -->
<tr><td style="padding:20px 28px 0;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border-radius:8px;border-left:4px solid #2563EB;">
    <tr><td style="padding:16px 20px;">
        <div style="font-size:16px;font-weight:600;color:#1B3A5C;">{company_name}</div>
        <div style="font-size:13px;color:#64748b;margin-top:4px;"><strong>Reporting Period:</strong> {period}</div>
    </td></tr>
    </table>
</td></tr>

<!-- ATTACHMENT NOTICE -->
<tr><td style="padding:20px 28px 0;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#059669 0%,#10b981 100%);border-radius:8px;">
    <tr><td style="padding:18px 20px;text-align:center;color:#ffffff;">
        <div style="font-size:15px;font-weight:600;">Professional Excel Report Attached</div>
        <div style="font-size:13px;opacity:.9;margin-top:6px;">Your {report_label.lower()} has been generated with modern formatting and comprehensive analysis.</div>
    </td></tr>
    </table>
</td></tr>"""

        if custom_message:
            html += f"""
<!-- CUSTOM MESSAGE -->
<tr><td style="padding:20px 28px 0;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border-radius:8px;border-left:4px solid #f59e0b;">
    <tr><td style="padding:16px 20px;">
        <div style="font-size:13px;font-weight:600;color:#1e293b;margin-bottom:8px;">Message</div>
        <div style="font-size:13px;color:#475569;line-height:1.6;">{custom_message}</div>
    </td></tr>
    </table>
</td></tr>"""

        html += f"""
<!-- BODY TEXT -->
<tr><td style="padding:20px 28px;">
    <div style="font-size:13px;color:#64748b;line-height:1.6;">
        This report was generated using FinAI's advanced financial intelligence engine.
        The attached Excel file contains detailed breakdowns and professional formatting suitable for executive presentations.
    </div>
</td></tr>

<!-- FOOTER -->
<tr><td style="background:#f8fafc;padding:24px 28px;text-align:center;border-top:1px solid #e2e8f0;">
    <div style="font-size:13px;font-weight:600;color:#1e293b;">FinAI &mdash; Advanced Financial Intelligence Platform</div>
    <div style="font-size:11px;color:#94a3b8;margin-top:6px;">Empowering financial decision-making with AI-driven insights</div>
    <div style="margin-top:12px;">
        <span style="display:inline-block;background:#1B3A5C;color:#ffffff;padding:4px 12px;border-radius:12px;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:1px;">AI-Powered Analytics</span>
    </div>
    <div style="font-size:10px;color:#cbd5e1;margin-top:12px;">&copy; {datetime.now().year} {settings.COMPANY_NAME} &mdash; Confidential</div>
</td></tr>

</table>
</td></tr></table>
</body>
</html>"""

        return html


# Global instance
modern_email_service = ModernEmailService()