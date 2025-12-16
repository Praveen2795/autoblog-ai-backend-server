"""
Visualize Router - Image generation agent
"""
import structlog
from fastapi import APIRouter, HTTPException

from app.models.schemas import VisualizeRequest, VisualizeResponse
from app.services.gemini import GeminiService


router = APIRouter()
logger = structlog.get_logger()


@router.post("/visualize", response_model=VisualizeResponse)
async def run_visualize(request: VisualizeRequest):
    """
    Run the visualizer agent to generate images for slides.
    
    Takes JSON slides and generates images based on
    the image prompts in each slide.
    """
    try:
        logger.info(
            "Visualize request",
            draft_length=len(request.draftJson)
        )
        
        service = GeminiService()
        slides = await service.run_visualizer_agent(
            draft_json=request.draftJson
        )
        
        logger.info(
            "Visualize completed",
            slides_count=len(slides),
            images_generated=sum(1 for s in slides if s.imageUrl)
        )
        
        return VisualizeResponse(slides=slides)
        
    except Exception as e:
        logger.error("Visualize failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Visualization failed: {str(e)}")
