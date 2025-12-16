"""
Email Pipeline Router

API endpoints to manage the email-triggered blog generation pipeline.
"""
import structlog
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List

from app.config import settings
from app.services.email_pipeline import get_email_orchestrator
from app.models.schemas import OutputType


router = APIRouter()
logger = structlog.get_logger()


# ============================================================
# REQUEST/RESPONSE MODELS
# ============================================================

class EmailPipelineStatusResponse(BaseModel):
    """Status of the email pipeline."""
    is_running: bool
    last_check: Optional[str]
    jobs_processed: int
    active_jobs: int
    completed_jobs: int
    check_interval_seconds: int
    email_configured: bool


class StartPipelineRequest(BaseModel):
    """Request to start email pipeline (optional config overrides)."""
    pass  # Future: allow runtime config overrides


class TriggerJobRequest(BaseModel):
    """Manually trigger a blog generation job."""
    topic: str = Field(..., min_length=1, max_length=500, description="Blog topic")
    recipient_email: EmailStr = Field(..., description="Email to send the result to")
    keywords: str = Field("", description="Optional keywords to prioritize")
    output_type: OutputType = Field(default=OutputType.BLOG_POST)


class TriggerJobResponse(BaseModel):
    """Response after triggering a job."""
    job_id: str
    topic: str
    recipient_email: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Status of a specific job."""
    job_id: str
    status: str
    topic: str
    sender: str
    received_at: str
    completed_at: Optional[str]
    error: Optional[str]


class JobListResponse(BaseModel):
    """List of jobs."""
    jobs: List[dict]
    total: int


class ConfigStatusResponse(BaseModel):
    """Email configuration status."""
    email_address_configured: bool
    imap_configured: bool
    smtp_configured: bool
    check_interval: int
    is_fully_configured: bool


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/email-pipeline/status", response_model=EmailPipelineStatusResponse)
async def get_pipeline_status():
    """
    Get the current status of the email pipeline.
    
    Returns whether the pipeline is running, how many jobs have been
    processed, and configuration status.
    """
    orchestrator = get_email_orchestrator()
    status = orchestrator.status
    
    email_configured = all([
        settings.EMAIL_ADDRESS,
        settings.EMAIL_PASSWORD,
        settings.EMAIL_IMAP_SERVER,
        settings.EMAIL_SMTP_SERVER,
    ])
    
    return EmailPipelineStatusResponse(
        is_running=status["is_running"],
        last_check=status["last_check"],
        jobs_processed=status["jobs_processed"],
        active_jobs=status["active_jobs"],
        completed_jobs=status["completed_jobs"],
        check_interval_seconds=status["check_interval_seconds"],
        email_configured=email_configured,
    )


@router.post("/email-pipeline/start")
async def start_pipeline(request: StartPipelineRequest = None):
    """
    Start the email monitoring pipeline.
    
    The pipeline will periodically check the configured email inbox
    for new blog requests and process them automatically.
    """
    # Check configuration
    if not settings.EMAIL_ADDRESS or not settings.EMAIL_PASSWORD:
        raise HTTPException(
            status_code=400,
            detail="Email credentials not configured. Set EMAIL_ADDRESS and EMAIL_PASSWORD in .env"
        )
    
    if not settings.EMAIL_IMAP_SERVER or not settings.EMAIL_SMTP_SERVER:
        raise HTTPException(
            status_code=400,
            detail="Email servers not configured. Set EMAIL_IMAP_SERVER and EMAIL_SMTP_SERVER in .env"
        )
    
    orchestrator = get_email_orchestrator()
    
    if orchestrator.is_running:
        return {"message": "Pipeline already running", "status": "running"}
    
    success = await orchestrator.start()
    
    if success:
        logger.info("Email pipeline started via API")
        return {"message": "Pipeline started successfully", "status": "running"}
    else:
        raise HTTPException(status_code=500, detail="Failed to start pipeline")


@router.post("/email-pipeline/stop")
async def stop_pipeline():
    """
    Stop the email monitoring pipeline.
    
    Active jobs will be cancelled.
    """
    orchestrator = get_email_orchestrator()
    
    if not orchestrator.is_running:
        return {"message": "Pipeline not running", "status": "stopped"}
    
    success = await orchestrator.stop()
    
    if success:
        logger.info("Email pipeline stopped via API")
        return {"message": "Pipeline stopped successfully", "status": "stopped"}
    else:
        raise HTTPException(status_code=500, detail="Failed to stop pipeline")


@router.post("/email-pipeline/trigger", response_model=TriggerJobResponse)
async def trigger_job(request: TriggerJobRequest):
    """
    Manually trigger a blog generation job.
    
    This bypasses email monitoring and directly creates a job.
    The generated blog will be sent to the specified email address.
    
    Useful for testing or API-based integrations.
    """
    # Check Gemini API key
    if not settings.GEMINI_API_KEY:
        raise HTTPException(
            status_code=400,
            detail="GEMINI_API_KEY not configured"
        )
    
    # Check email sending capability
    if not settings.EMAIL_ADDRESS or not settings.EMAIL_SMTP_SERVER:
        raise HTTPException(
            status_code=400,
            detail="Email sending not configured. Set EMAIL_ADDRESS and EMAIL_SMTP_SERVER"
        )
    
    orchestrator = get_email_orchestrator()
    
    try:
        job = await orchestrator.process_single_topic(
            topic=request.topic,
            recipient_email=request.recipient_email,
            keywords=request.keywords,
            output_type=request.output_type
        )
        
        logger.info(
            "Job triggered via API",
            job_id=job.job_id,
            topic=job.topic,
            recipient=request.recipient_email
        )
        
        return TriggerJobResponse(
            job_id=job.job_id,
            topic=job.topic,
            recipient_email=request.recipient_email,
            status="processing",
            message="Blog generation started. You will receive an email when complete."
        )
        
    except Exception as e:
        logger.error("Failed to trigger job", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start job: {str(e)}")


@router.get("/email-pipeline/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get the status of a specific job.
    """
    orchestrator = get_email_orchestrator()
    status = orchestrator.get_job_status(job_id)
    
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(**status)


@router.get("/email-pipeline/jobs", response_model=JobListResponse)
async def list_jobs(limit: int = 20):
    """
    List recent jobs (active and completed).
    """
    orchestrator = get_email_orchestrator()
    jobs = orchestrator.list_jobs(limit=limit)
    
    return JobListResponse(jobs=jobs, total=len(jobs))


@router.get("/email-pipeline/config", response_model=ConfigStatusResponse)
async def get_config_status():
    """
    Get email configuration status.
    
    Shows which parts of email configuration are set up.
    Does NOT expose actual credentials.
    """
    email_configured = bool(settings.EMAIL_ADDRESS)
    imap_configured = bool(settings.EMAIL_IMAP_SERVER)
    smtp_configured = bool(settings.EMAIL_SMTP_SERVER)
    
    return ConfigStatusResponse(
        email_address_configured=email_configured,
        imap_configured=imap_configured,
        smtp_configured=smtp_configured,
        check_interval=settings.EMAIL_CHECK_INTERVAL,
        is_fully_configured=all([email_configured, imap_configured, smtp_configured, settings.EMAIL_PASSWORD])
    )


@router.post("/email-pipeline/test-email")
async def test_email_connection():
    """
    Test email connection (IMAP and SMTP).
    
    Attempts to connect to both servers to verify configuration.
    """
    from app.services.email_service import get_email_service
    
    email_service = get_email_service()
    results = {
        "imap": {"success": False, "error": None},
        "smtp": {"success": False, "error": None},
    }
    
    # Test IMAP
    try:
        mail = email_service._connect_imap()
        mail.logout()
        results["imap"]["success"] = True
    except Exception as e:
        results["imap"]["error"] = str(e)
    
    # Test SMTP
    try:
        server = email_service._connect_smtp()
        server.quit()
        results["smtp"]["success"] = True
    except Exception as e:
        results["smtp"]["error"] = str(e)
    
    all_success = results["imap"]["success"] and results["smtp"]["success"]
    
    return {
        "success": all_success,
        "results": results,
        "message": "All connections successful!" if all_success else "Some connections failed"
    }


# ============================================================
# GUARDRAIL ENDPOINT
# ============================================================

class GuardrailCheckRequest(BaseModel):
    """Request to check if a topic is safe."""
    topic: str = Field(..., min_length=1, max_length=500, description="Topic to check")


class GuardrailCheckResponse(BaseModel):
    """Response from guardrail check."""
    topic: str
    is_safe: bool
    reason: str


@router.post("/email-pipeline/check-topic", response_model=GuardrailCheckResponse)
async def check_topic_safety(request: GuardrailCheckRequest):
    """
    Check if a topic is safe to generate a blog about.
    
    Uses AI-powered content moderation to detect:
    - Political content
    - Sexual/adult content
    - Illegal activities
    - Violence or harm
    - Hate speech
    
    Returns whether the topic would be processed or blocked.
    """
    from app.services.guardrail import get_guardrail_service
    
    guardrail = get_guardrail_service()
    is_safe, reason = await guardrail.check_topic(request.topic)
    
    return GuardrailCheckResponse(
        topic=request.topic,
        is_safe=is_safe,
        reason=reason
    )
