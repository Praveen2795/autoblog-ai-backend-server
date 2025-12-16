"""
Email Service - Email monitoring and sending for blog pipeline

This service monitors an IMAP inbox for blog generation requests,
parses topics from email subjects/body, triggers the pipeline,
and sends the generated blog back to the sender.
"""
import asyncio
import email
import imaplib
import smtplib
import re
import structlog
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field

from app.config import settings
from app.models.schemas import (
    SearchConstraints,
    OutputType,
    SourceType,
)


logger = structlog.get_logger()


@dataclass
class EmailJob:
    """Represents a blog generation job from an email."""
    job_id: str
    sender_email: str
    subject: str
    topic: str
    keywords: str
    output_type: OutputType
    received_at: datetime
    status: str = "pending"  # pending, processing, completed, failed
    result: Optional[str] = None
    error: Optional[str] = None
    completed_at: Optional[datetime] = None


@dataclass
class EmailMonitorState:
    """State of the email monitoring service."""
    is_running: bool = False
    last_check: Optional[datetime] = None
    jobs_processed: int = 0
    active_jobs: Dict[str, EmailJob] = field(default_factory=dict)
    completed_jobs: List[EmailJob] = field(default_factory=list)


class EmailService:
    """
    Email service for monitoring inbox and sending blog results.
    
    Workflow:
    1. Monitor inbox for emails with subject containing "BLOG:" prefix
    2. Parse topic and optional keywords from email
    3. Trigger the AI pipeline
    4. Send the generated blog back to the sender
    """
    
    def __init__(self):
        self.state = EmailMonitorState()
        self._monitor_task: Optional[asyncio.Task] = None
        self._on_new_job: Optional[Callable[[EmailJob], None]] = None
    
    def _connect_imap(self) -> imaplib.IMAP4_SSL:
        """Connect to IMAP server."""
        if not settings.EMAIL_IMAP_SERVER:
            raise ValueError("EMAIL_IMAP_SERVER not configured")
        
        mail = imaplib.IMAP4_SSL(
            settings.EMAIL_IMAP_SERVER,
            settings.EMAIL_IMAP_PORT
        )
        mail.login(settings.EMAIL_ADDRESS, settings.EMAIL_PASSWORD)
        return mail
    
    def _connect_smtp(self) -> smtplib.SMTP_SSL:
        """Connect to SMTP server."""
        if not settings.EMAIL_SMTP_SERVER:
            raise ValueError("EMAIL_SMTP_SERVER not configured")
        
        server = smtplib.SMTP_SSL(
            settings.EMAIL_SMTP_SERVER,
            settings.EMAIL_SMTP_PORT
        )
        server.login(settings.EMAIL_ADDRESS, settings.EMAIL_PASSWORD)
        return server
    
    def _decode_email_header(self, header: str) -> str:
        """Decode email header handling different encodings."""
        if not header:
            return ""
        
        decoded_parts = decode_header(header)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(encoding or 'utf-8', errors='ignore'))
            else:
                result.append(part)
        return "".join(result)
    
    def _parse_email_body(self, msg: email.message.Message) -> str:
        """Extract text body from email message."""
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, errors='ignore')
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                body = payload.decode(charset, errors='ignore')
        
        return body.strip()
    
    def _parse_blog_request(self, subject: str, body: str, sender_email: str = "") -> Optional[Dict[str, Any]]:
        """
        Parse blog generation request from email.
        
        SIMPLE FORMAT: The email subject IS the topic. That's it!
        - Subject: "AI in Healthcare" → generates blog about AI in Healthcare
        - Subject: "Best practices for Python testing" → generates blog about that
        
        No special prefix needed. Just send an email with your topic as the subject.
        Body is ignored (can be empty).
        
        SECURITY: Uses whitelist mode if EMAIL_ALLOWED_SENDERS is configured.
        
        Returns dict with topic, keywords, output_type
        """
        # ============================================================
        # STEP 1: WHITELIST CHECK (most secure - recommended!)
        # ============================================================
        if settings.EMAIL_ALLOWED_SENDERS:
            allowed = [s.strip().lower() for s in settings.EMAIL_ALLOWED_SENDERS.split(',') if s.strip()]
            if sender_email.lower() not in allowed:
                logger.info(f"Sender not in whitelist, ignoring: {sender_email}")
                return None
        
        # ============================================================
        # STEP 2: BASIC VALIDATION
        # ============================================================
        topic = subject.strip()
        if not topic:
            return None
        
        # Too short to be a real topic
        if len(topic) < 5:
            logger.info(f"Subject too short, ignoring: {topic}")
            return None
        
        topic_lower = topic.lower()
        
        # ============================================================
        # STEP 3: SKIP AUTO-GENERATED SYSTEM EMAILS
        # ============================================================
        system_patterns = [
            'out of office',
            'automatic reply',
            'auto-reply',
            'autoreply',
            'delivery status',
            'delivery failure',
            'undeliverable',
            'read receipt',
            'read:',
            'meeting invitation',
            'meeting request',
            'meeting accepted',
            'meeting declined',
            'calendar:',
            'invitation:',
            'accepted:',
            'declined:',
            'tentative:',
            'cancelled:',
            'updated invitation',
            're:',  # Skip replies
            'fwd:',  # Skip forwards
            'fw:',
            'aw:',  # German reply
            'sv:',  # Swedish reply
            'antw:',  # Dutch reply
        ]
        if any(topic_lower.startswith(p) or p in topic_lower for p in system_patterns):
            logger.info(f"Skipping system email: {topic[:50]}")
            return None
        
        # ============================================================
        # STEP 4: SKIP PROMOTIONAL / SPAM PATTERNS
        # ============================================================
        spam_patterns = [
            # Sales/Marketing
            'unsubscribe',
            'subscription',
            'newsletter',
            'weekly digest',
            'daily digest',
            'promotional',
            'special offer',
            'limited time',
            'act now',
            'don\'t miss',
            'exclusive deal',
            'free trial',
            'sign up now',
            '% off',
            'discount',
            'coupon',
            'promo code',
            'black friday',
            'cyber monday',
            'flash sale',
            'clearance',
            
            # Account/Service notifications
            'your order',
            'order confirmation',
            'shipping confirmation',
            'tracking number',
            'password reset',
            'verify your',
            'confirm your',
            'account security',
            'account update',
            'billing statement',
            'invoice',
            'payment received',
            'payment due',
            'receipt for',
            'your receipt',
            
            # Social media notifications
            'new follower',
            'new connection',
            'liked your',
            'commented on',
            'mentioned you',
            'tagged you',
            'shared your',
            'new message from',
            'sent you a message',
            
            # Alerts/Notifications
            'security alert',
            'login attempt',
            'new sign-in',
            'unusual activity',
            'action required',
            'action needed',
            'reminder:',
            'alert:',
            'notification:',
            'update:',
            
            # Job/Recruiting spam
            'job opportunity',
            'job alert',
            'we\'re hiring',
            'career opportunity',
            'your application',
            
            # Common spam phrases
            'congratulations',
            'you\'ve won',
            'claim your',
            'urgent',
            'important notice',
            'final notice',
            'immediate action',
        ]
        if any(p in topic_lower for p in spam_patterns):
            logger.info(f"Skipping promotional/spam email: {topic[:50]}")
            return None
        
        # ============================================================
        # STEP 5: SKIP KNOWN SPAM SENDER DOMAINS
        # ============================================================
        spam_domains = [
            'noreply',
            'no-reply',
            'donotreply',
            'mailer-daemon',
            'postmaster',
            'notifications',
            'alerts',
            'news@',
            'newsletter@',
            'marketing@',
            'promo@',
            'sales@',
            'support@',
            'info@',
            'hello@',
            'team@',
        ]
        sender_lower = sender_email.lower()
        if any(d in sender_lower for d in spam_domains):
            logger.info(f"Skipping email from automated sender: {sender_email}")
            return None
        
        # ============================================================
        # PASSED ALL CHECKS - This looks like a real blog request!
        # ============================================================
        logger.info(f"Valid blog request from {sender_email}: {topic[:50]}")
        
        return {
            "topic": topic,
            "keywords": "",  # Let the AI figure out relevant keywords
            "output_type": OutputType.BLOG_POST
        }
    
    def _generate_job_id(self) -> str:
        """Generate unique job ID."""
        import uuid
        return f"blog-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    
    async def check_inbox(self) -> List[EmailJob]:
        """
        Check inbox for new blog requests.
        Returns list of new EmailJob objects.
        """
        new_jobs = []
        
        try:
            mail = await asyncio.to_thread(self._connect_imap)
            
            # Select inbox
            await asyncio.to_thread(mail.select, "INBOX")
            
            # Search for unread emails
            _, message_numbers = await asyncio.to_thread(
                mail.search, None, "(UNSEEN)"
            )
            
            for num in message_numbers[0].split():
                try:
                    _, msg_data = await asyncio.to_thread(
                        mail.fetch, num, "(RFC822)"
                    )
                    
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    # Decode headers
                    subject = self._decode_email_header(msg.get("Subject", ""))
                    sender = self._decode_email_header(msg.get("From", ""))
                    
                    # Extract email address from sender
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+', sender)
                    sender_email = email_match.group(0) if email_match else sender
                    
                    # Parse body
                    body = self._parse_email_body(msg)
                    
                    # Check if this is a blog request (with spam filtering)
                    request = self._parse_blog_request(subject, body, sender_email)
                    
                    if request:
                        job = EmailJob(
                            job_id=self._generate_job_id(),
                            sender_email=sender_email,
                            subject=subject,
                            topic=request["topic"],
                            keywords=request["keywords"],
                            output_type=request["output_type"],
                            received_at=datetime.utcnow()
                        )
                        new_jobs.append(job)
                        self.state.active_jobs[job.job_id] = job
                        
                        logger.info(
                            "New blog request received",
                            job_id=job.job_id,
                            topic=job.topic,
                            sender=sender_email
                        )
                        
                        # Mark as read (by fetching, it's marked as seen)
                        # Or explicitly mark as seen
                        await asyncio.to_thread(
                            mail.store, num, '+FLAGS', '\\Seen'
                        )
                    
                except Exception as e:
                    logger.error("Error processing email", error=str(e))
                    continue
            
            await asyncio.to_thread(mail.logout)
            self.state.last_check = datetime.utcnow()
            
        except Exception as e:
            logger.error("Error checking inbox", error=str(e))
            raise
        
        return new_jobs
    
    async def send_blog_result(
        self,
        job: EmailJob,
        blog_content: str,
        sources: Optional[List[Dict]] = None
    ) -> bool:
        """
        Send generated blog back to the requester.
        """
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = settings.EMAIL_ADDRESS
            msg['To'] = job.sender_email
            msg['Subject'] = f"✅ Your Blog is Ready: {job.topic}"
            
            # Plain text version
            text_content = f"""
Your AI-Generated Blog is Ready!
================================

Topic: {job.topic}
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}

{blog_content}

---
Sources Used:
{self._format_sources(sources) if sources else 'N/A'}

---
Generated by AutoBlog AI
Want another blog? Just send an email with your topic as the subject!
"""
            
            # HTML version (with markdown converted to HTML)
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #1a1a2e; border-bottom: 2px solid #4f46e5; padding-bottom: 10px; }}
        h2 {{ color: #2d2d44; margin-top: 30px; }}
        h3 {{ color: #4a4a6a; }}
        pre {{ background: #f4f4f5; padding: 15px; border-radius: 8px; overflow-x: auto; }}
        code {{ background: #f4f4f5; padding: 2px 6px; border-radius: 4px; }}
        blockquote {{ border-left: 4px solid #4f46e5; margin: 20px 0; padding-left: 20px; color: #666; }}
        .header {{ background: linear-gradient(135deg, #4f46e5, #7c3aed); color: white; padding: 20px; border-radius: 10px; margin-bottom: 30px; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 0.9em; }}
        .sources {{ background: #f8fafc; padding: 15px; border-radius: 8px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1 style="color: white; border: none; margin: 0;">✨ Your Blog is Ready!</h1>
        <p style="margin: 10px 0 0 0; opacity: 0.9;">Topic: {job.topic}</p>
    </div>
    
    <div class="content">
        {self._markdown_to_html(blog_content)}
    </div>
    
    <div class="sources">
        <strong>📚 Sources Used:</strong>
        {self._format_sources_html(sources) if sources else '<p>N/A</p>'}
    </div>
    
    <div class="footer">
        <p>Generated by <strong>AutoBlog AI</strong> on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
        <p>💡 Want another blog? Just send an email with your topic as the subject!</p>
    </div>
</body>
</html>
"""
            
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            server = await asyncio.to_thread(self._connect_smtp)
            await asyncio.to_thread(
                server.sendmail,
                settings.EMAIL_ADDRESS,
                job.sender_email,
                msg.as_string()
            )
            await asyncio.to_thread(server.quit)
            
            logger.info(
                "Blog sent to requester",
                job_id=job.job_id,
                recipient=job.sender_email
            )
            
            return True
            
        except Exception as e:
            logger.error("Failed to send blog", error=str(e), job_id=job.job_id)
            return False
    
    async def send_error_notification(self, job: EmailJob, error_message: str) -> bool:
        """Send error notification when blog generation fails."""
        try:
            msg = MIMEText(f"""
Unfortunately, we couldn't generate your blog.

Topic: {job.topic}
Error: {error_message}

Please try again or modify your request.

---
To request a blog, send an email with:
Subject: BLOG: Your Topic Here
Body: (optional) keywords: key1, key2, key3

Generated by AutoBlog AI
""")
            msg['From'] = settings.EMAIL_ADDRESS
            msg['To'] = job.sender_email
            msg['Subject'] = f"❌ Blog Generation Failed: {job.topic}"
            
            server = await asyncio.to_thread(self._connect_smtp)
            await asyncio.to_thread(
                server.sendmail,
                settings.EMAIL_ADDRESS,
                job.sender_email,
                msg.as_string()
            )
            await asyncio.to_thread(server.quit)
            
            return True
            
        except Exception as e:
            logger.error("Failed to send error notification", error=str(e))
            return False
    
    def _format_sources(self, sources: Optional[List[Dict]]) -> str:
        """Format sources for plain text email."""
        if not sources:
            return ""
        
        lines = []
        for s in sources:
            lines.append(f"- {s.get('title', 'Unknown')}: {s.get('uri', 'N/A')}")
        return "\n".join(lines)
    
    def _format_sources_html(self, sources: Optional[List[Dict]]) -> str:
        """Format sources for HTML email."""
        if not sources:
            return ""
        
        items = []
        for s in sources:
            title = s.get('title', 'Unknown')
            uri = s.get('uri', '#')
            items.append(f'<li><a href="{uri}">{title}</a></li>')
        return f"<ul>{''.join(items)}</ul>"
    
    def _markdown_to_html(self, markdown_text: str) -> str:
        """
        Simple markdown to HTML conversion.
        For production, consider using a proper markdown library.
        """
        import html
        text = html.escape(markdown_text)
        
        # Headers
        text = re.sub(r'^### (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)
        text = re.sub(r'^# (.+)$', r'<h1>\1</h1>', text, flags=re.MULTILINE)
        
        # Bold and italic
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        
        # Inline code
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        
        # Code blocks (simple version)
        text = re.sub(r'```[\w]*\n(.*?)```', r'<pre><code>\1</code></pre>', text, flags=re.DOTALL)
        
        # Blockquotes
        text = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', text, flags=re.MULTILINE)
        
        # Lists
        text = re.sub(r'^- (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
        text = re.sub(r'(<li>.*</li>\n?)+', r'<ul>\g<0></ul>', text)
        
        # Paragraphs (simple: double newlines)
        paragraphs = text.split('\n\n')
        processed = []
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith('<'):
                p = f'<p>{p}</p>'
            processed.append(p)
        text = '\n'.join(processed)
        
        return text


# Singleton instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get or create email service singleton."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
