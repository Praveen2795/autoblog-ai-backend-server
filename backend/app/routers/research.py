"""
Research Router - Multi-stream research agent
"""
import structlog
from fastapi import APIRouter, HTTPException

from app.models.schemas import ResearchRequest, ResearchResponse
from app.services.gemini import GeminiService


router = APIRouter()
logger = structlog.get_logger()


@router.post("/research", response_model=ResearchResponse)
async def run_research(request: ResearchRequest):
    """
    Run the research agent to gather information on a topic.
    
    Searches across multiple source types (YouTube, Articles, Papers)
    based on the configured constraints.
    """
    try:
        logger.info(
            "Research request",
            topic=request.topic,
            keywords=request.keywords,
            constraints=request.constraints.model_dump() if request.constraints else None
        )
        
        service = GeminiService()
        result = await service.run_research_agent(
            topic=request.topic,
            keywords=request.keywords,
            constraints=request.constraints
        )
        
        logger.info(
            "Research completed",
            topic=request.topic,
            sources_count=len(result.sources)
        )
        
        return ResearchResponse(data=result)
        
    except Exception as e:
        logger.error("Research failed", error=str(e), topic=request.topic)
        raise HTTPException(status_code=500, detail=f"Research failed: {str(e)}")
