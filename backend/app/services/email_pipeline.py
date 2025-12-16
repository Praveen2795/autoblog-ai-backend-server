"""
Email Pipeline Orchestrator

This module handles the background task that:
1. Monitors the inbox for new blog requests
2. Processes each request through the AI pipeline
3. Sends the generated blog back via email
"""
import asyncio
import structlog
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.config import settings
from app.services.email_service import EmailService, EmailJob, get_email_service
from app.services.gemini import GeminiService
from app.services.guardrail import get_guardrail_service
from app.models.schemas import (
    SearchConstraints,
    SourceType,
    OutputType,
)


logger = structlog.get_logger()


class EmailPipelineOrchestrator:
    """
    Orchestrates the email-to-blog pipeline.
    
    Runs as a background task that:
    1. Periodically checks inbox for new requests
    2. Processes requests through the AI pipeline
    3. Sends results back via email
    """
    
    def __init__(self):
        self.email_service = get_email_service()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._processing_jobs: Dict[str, asyncio.Task] = {}
    
    @property
    def is_running(self) -> bool:
        return self._running
    
    @property
    def status(self) -> Dict[str, Any]:
        """Get current status of the orchestrator."""
        return {
            "is_running": self._running,
            "last_check": self.email_service.state.last_check.isoformat() if self.email_service.state.last_check else None,
            "jobs_processed": self.email_service.state.jobs_processed,
            "active_jobs": len(self.email_service.state.active_jobs),
            "completed_jobs": len(self.email_service.state.completed_jobs),
            "check_interval_seconds": settings.EMAIL_CHECK_INTERVAL,
        }
    
    async def start(self) -> bool:
        """Start the email monitoring background task."""
        if self._running:
            logger.warning("Email pipeline already running")
            return False
        
        # Validate configuration
        if not self._validate_config():
            logger.error("Email configuration incomplete")
            return False
        
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        
        logger.info("Email pipeline started", 
                   check_interval=settings.EMAIL_CHECK_INTERVAL)
        return True
    
    async def stop(self) -> bool:
        """Stop the email monitoring background task."""
        if not self._running:
            logger.warning("Email pipeline not running")
            return False
        
        self._running = False
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        
        # Cancel any processing jobs
        for job_id, task in self._processing_jobs.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._processing_jobs.clear()
        
        logger.info("Email pipeline stopped")
        return True
    
    def _validate_config(self) -> bool:
        """Validate that email configuration is complete."""
        required = [
            settings.EMAIL_ADDRESS,
            settings.EMAIL_PASSWORD,
            settings.EMAIL_IMAP_SERVER,
            settings.EMAIL_SMTP_SERVER,
        ]
        return all(required)
    
    async def _monitor_loop(self):
        """Main monitoring loop - runs in background."""
        logger.info("Starting email monitor loop")
        
        while self._running:
            try:
                # Check for new emails
                new_jobs = await self.email_service.check_inbox()
                
                # Process each new job
                for job in new_jobs:
                    # Start processing in background
                    task = asyncio.create_task(self._process_job(job))
                    self._processing_jobs[job.job_id] = task
                
                # Clean up completed processing tasks
                completed_job_ids = []
                for job_id, task in self._processing_jobs.items():
                    if task.done():
                        completed_job_ids.append(job_id)
                
                for job_id in completed_job_ids:
                    del self._processing_jobs[job_id]
                
            except Exception as e:
                logger.error("Error in monitor loop", error=str(e))
            
            # Wait before next check
            await asyncio.sleep(settings.EMAIL_CHECK_INTERVAL)
    
    async def _process_job(self, job: EmailJob):
        """
        Process a single blog generation job.
        
        Runs the full AI pipeline and sends results via email.
        """
        logger.info("Processing job", job_id=job.job_id, topic=job.topic)
        
        job.status = "processing"
        
        try:
            # ============================================================
            # GUARDRAIL CHECK - Block harmful content
            # ============================================================
            guardrail = get_guardrail_service()
            is_safe, reason = await guardrail.check_topic(job.topic)
            
            if not is_safe:
                logger.warning(
                    "Topic blocked by guardrail",
                    job_id=job.job_id,
                    topic=job.topic[:50],
                    reason=reason
                )
                job.status = "blocked"
                job.error = f"Content blocked: {reason}"
                
                # Send rejection email to user
                await self._send_rejection_email(job, reason)
                
                # Move to completed (as rejected)
                if job.job_id in self.email_service.state.active_jobs:
                    del self.email_service.state.active_jobs[job.job_id]
                job.completed_at = datetime.utcnow()
                self.email_service.state.completed_jobs.append(job)
                return
            
            logger.info("Topic passed guardrail", job_id=job.job_id, reason=reason)
            
            # Initialize Gemini service
            service = GeminiService()
            
            # Default constraints
            constraints = SearchConstraints(
                preferredDomains=[],
                excludedDomains=[],
                focusDescription="",
                allowedSourceTypes=[SourceType.YOUTUBE, SourceType.ARTICLE, SourceType.PAPER]
            )
            
            # ============================================================
            # PHASE 1: RESEARCH
            # ============================================================
            logger.info("Starting research", job_id=job.job_id)
            
            research_data = await service.run_research_agent(
                topic=job.topic,
                keywords=job.keywords,
                constraints=constraints
            )
            
            logger.info("Research complete", 
                       job_id=job.job_id, 
                       sources=len(research_data.sources))
            
            # ============================================================
            # PHASE 2: DRAFTING
            # ============================================================
            logger.info("Starting draft", job_id=job.job_id)
            
            current_draft = await service.run_drafter_agent(
                research_data=research_data,
                output_type=job.output_type
            )
            
            logger.info("Draft complete", job_id=job.job_id)
            
            # ============================================================
            # PHASE 3: REVIEW/REFINE LOOP
            # ============================================================
            max_iterations = settings.MAX_REFINEMENT_ITERATIONS
            iteration = 0
            is_approved = False
            previous_scores = []
            last_critique = None
            
            while iteration < max_iterations and not is_approved:
                iteration += 1
                
                logger.info(f"Review iteration {iteration}", job_id=job.job_id)
                
                # Review
                feedback = await service.run_reviewer_agent(
                    draft=current_draft,
                    iteration=iteration,
                    output_type=job.output_type,
                    previous_scores=previous_scores if previous_scores else None,
                    previous_critique=last_critique
                )
                
                previous_scores.append(feedback.score)
                last_critique = feedback.critique
                
                logger.info(f"Review score: {feedback.score}", 
                           job_id=job.job_id,
                           approved=feedback.approved)
                
                if feedback.approved:
                    is_approved = True
                    break
                
                # Refine
                logger.info("Refining draft", job_id=job.job_id)
                
                current_draft = await service.run_refiner_agent(
                    draft=current_draft,
                    feedback=feedback.critique,
                    output_type=job.output_type
                )
            
            # ============================================================
            # PHASE 4: SEND RESULT
            # ============================================================
            logger.info("Sending blog via email", job_id=job.job_id)
            
            sources = [
                {"title": s.title, "uri": s.uri, "type": s.type.value}
                for s in research_data.sources
            ]
            
            await self.email_service.send_blog_result(
                job=job,
                blog_content=current_draft,
                sources=sources
            )
            
            # Update job status
            job.status = "completed"
            job.result = current_draft
            job.completed_at = datetime.utcnow()
            
            # Move to completed
            if job.job_id in self.email_service.state.active_jobs:
                del self.email_service.state.active_jobs[job.job_id]
            self.email_service.state.completed_jobs.append(job)
            self.email_service.state.jobs_processed += 1
            
            logger.info("Job completed successfully", job_id=job.job_id)
            
        except Exception as e:
            logger.error("Job failed", job_id=job.job_id, error=str(e))
            
            job.status = "failed"
            job.error = str(e)
            job.completed_at = datetime.utcnow()
            
            # Try to send error notification
            await self.email_service.send_error_notification(job, str(e))
            
            # Move to completed (with error status)
            if job.job_id in self.email_service.state.active_jobs:
                del self.email_service.state.active_jobs[job.job_id]
            self.email_service.state.completed_jobs.append(job)
    
    async def _send_rejection_email(self, job: EmailJob, reason: str):
        """Send email notifying user their topic was blocked."""
        try:
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            import smtplib
            
            msg = MIMEMultipart('alternative')
            msg['From'] = settings.EMAIL_ADDRESS
            msg['To'] = job.sender_email
            msg['Subject'] = f"❌ Blog Request Declined: {job.topic[:50]}"
            
            text_content = f"""
Your Blog Request Could Not Be Processed
========================================

Topic: {job.topic}
Reason: {reason}

Our content guidelines don't allow us to generate content on this topic.

We block topics that are:
• Politically charged or biased
• Sexual or adult in nature
• Related to illegal activities
• Violent or promoting harm
• Hateful or discriminatory

Please try a different topic that is educational, informational, or professionally appropriate.

---
AutoBlog AI
"""
            
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #ef4444, #dc2626); color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
        .content {{ background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 20px; }}
        .reason {{ background: white; padding: 15px; border-radius: 6px; margin: 15px 0; border-left: 4px solid #ef4444; }}
        ul {{ color: #666; }}
    </style>
</head>
<body>
    <div class="header">
        <h1 style="color: white; margin: 0;">❌ Request Declined</h1>
    </div>
    
    <div class="content">
        <p><strong>Topic:</strong> {job.topic}</p>
        
        <div class="reason">
            <strong>Reason:</strong> {reason}
        </div>
        
        <p>Our content guidelines don't allow us to generate content on this topic.</p>
        
        <p><strong>We block topics that are:</strong></p>
        <ul>
            <li>Politically charged or biased</li>
            <li>Sexual or adult in nature</li>
            <li>Related to illegal activities</li>
            <li>Violent or promoting harm</li>
            <li>Hateful or discriminatory</li>
        </ul>
        
        <p>Please try a different topic that is educational, informational, or professionally appropriate.</p>
    </div>
    
    <p style="color: #666; font-size: 0.9em; margin-top: 20px;">— AutoBlog AI</p>
</body>
</html>
"""
            
            msg.attach(MIMEText(text_content, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            server = smtplib.SMTP_SSL(settings.EMAIL_SMTP_SERVER, settings.EMAIL_SMTP_PORT)
            server.login(settings.EMAIL_ADDRESS, settings.EMAIL_PASSWORD)
            server.sendmail(settings.EMAIL_ADDRESS, job.sender_email, msg.as_string())
            server.quit()
            
            logger.info("Rejection email sent", job_id=job.job_id, recipient=job.sender_email)
            
        except Exception as e:
            logger.error("Failed to send rejection email", job_id=job.job_id, error=str(e))

    async def process_single_topic(
        self,
        topic: str,
        recipient_email: str,
        keywords: str = "",
        output_type: OutputType = OutputType.BLOG_POST
    ) -> EmailJob:
        """
        Process a single topic directly (for API testing).
        
        Creates a job and processes it without waiting for email.
        """
        job = EmailJob(
            job_id=self.email_service._generate_job_id(),
            sender_email=recipient_email,
            subject=f"BLOG: {topic}",
            topic=topic,
            keywords=keywords,
            output_type=output_type,
            received_at=datetime.utcnow()
        )
        
        self.email_service.state.active_jobs[job.job_id] = job
        
        # Process in background
        task = asyncio.create_task(self._process_job(job))
        self._processing_jobs[job.job_id] = task
        
        return job
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific job."""
        # Check active jobs
        if job_id in self.email_service.state.active_jobs:
            job = self.email_service.state.active_jobs[job_id]
            return {
                "job_id": job.job_id,
                "status": job.status,
                "topic": job.topic,
                "sender": job.sender_email,
                "received_at": job.received_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "error": job.error,
            }
        
        # Check completed jobs
        for job in self.email_service.state.completed_jobs:
            if job.job_id == job_id:
                return {
                    "job_id": job.job_id,
                    "status": job.status,
                    "topic": job.topic,
                    "sender": job.sender_email,
                    "received_at": job.received_at.isoformat(),
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    "error": job.error,
                }
        
        return None
    
    def list_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent jobs."""
        jobs = []
        
        # Add active jobs
        for job in self.email_service.state.active_jobs.values():
            jobs.append({
                "job_id": job.job_id,
                "status": job.status,
                "topic": job.topic,
                "sender": job.sender_email,
                "received_at": job.received_at.isoformat(),
            })
        
        # Add completed jobs (most recent first)
        for job in reversed(self.email_service.state.completed_jobs[-limit:]):
            jobs.append({
                "job_id": job.job_id,
                "status": job.status,
                "topic": job.topic,
                "sender": job.sender_email,
                "received_at": job.received_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            })
        
        return jobs[:limit]


# Singleton instance
_orchestrator: Optional[EmailPipelineOrchestrator] = None


def get_email_orchestrator() -> EmailPipelineOrchestrator:
    """Get or create orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = EmailPipelineOrchestrator()
    return _orchestrator
