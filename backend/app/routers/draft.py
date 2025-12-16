"""
Draft Router - Content drafting agent
"""
import structlog
from fastapi import APIRouter, HTTPException

from app.models.schemas import DraftRequest, DraftResponse
from app.services.gemini import GeminiService


router = APIRouter()
logger = structlog.get_logger()


@router.post("/draft", response_model=DraftResponse)
async def run_draft(request: DraftRequest):
    """
    Run the drafter agent to create initial content.
    
    Generates either a Markdown blog post or JSON slides
    based on the output type.
    """
    try:
        logger.info(
            "Draft request",
            output_type=request.outputType.value,
            research_length=len(request.researchData.content)
        )
        
        service = GeminiService()
        draft = await service.run_drafter_agent(
            research_data=request.researchData,
            output_type=request.outputType
        )
        
        logger.info(
            "Draft completed",
            output_type=request.outputType.value,
            draft_length=len(draft)
        )
        
        return DraftResponse(draft=draft)
        
    except Exception as e:
        logger.error("Draft failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Drafting failed: {str(e)}")
