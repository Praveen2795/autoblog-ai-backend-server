"""
AutoBlog AI - FastAPI Main Application
Enterprise-grade backend for AI-powered content generation.
"""
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.config import settings
from app.routers import research, draft, review, refine, visualize, config_chat, health, pipeline, email_pipeline


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting AutoBlog AI API", version=settings.APP_VERSION)
    
    # Validate critical settings
    if not settings.GEMINI_API_KEY or settings.GEMINI_API_KEY == "":
        logger.warning("GEMINI_API_KEY not set - API calls will fail")
    
    if settings.JWT_SECRET_KEY == "change-me-in-production-use-openssl-rand-hex-32":
        logger.warning("Using default JWT secret - CHANGE THIS IN PRODUCTION")
    
    # Check email configuration
    if settings.EMAIL_ADDRESS and settings.EMAIL_PASSWORD:
        logger.info("Email pipeline configured", email=settings.EMAIL_ADDRESS)
        
        # Auto-start email pipeline if configured
        if settings.EMAIL_AUTO_START:
            from app.services.email_pipeline import get_email_orchestrator
            orchestrator = get_email_orchestrator()
            await orchestrator.start()
            logger.info("Email pipeline auto-started")
    else:
        logger.info("Email pipeline not configured - set EMAIL_ADDRESS and EMAIL_PASSWORD to enable")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AutoBlog AI API")
    
    # Stop email pipeline if running
    if settings.EMAIL_ADDRESS and settings.EMAIL_PASSWORD:
        from app.services.email_pipeline import get_email_orchestrator
        orchestrator = get_email_orchestrator()
        if orchestrator.is_running:
            await orchestrator.stop()
            logger.info("Email pipeline stopped")


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise AI-powered content generation with multi-agent workflow",
    docs_url="/docs" if settings.DEBUG else None,  # Disable docs in production
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    logger.error(
        "Unhandled exception",
        error=str(exc),
        path=request.url.path,
        method=request.method
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": "server_error"}
    )


# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(config_chat.router, prefix="/api", tags=["Configuration"])
app.include_router(research.router, prefix="/api", tags=["Research"])
app.include_router(draft.router, prefix="/api", tags=["Draft"])
app.include_router(review.router, prefix="/api", tags=["Review"])
app.include_router(refine.router, prefix="/api", tags=["Refine"])
app.include_router(visualize.router, prefix="/api", tags=["Visualize"])
app.include_router(pipeline.router, prefix="/api", tags=["Pipeline"])
app.include_router(email_pipeline.router, prefix="/api", tags=["Email Pipeline"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational"
    }
