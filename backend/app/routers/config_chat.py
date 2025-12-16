"""
Configuration Chat Router - Natural language source configuration
"""
import structlog
from fastapi import APIRouter, HTTPException

from app.models.schemas import ConfigChatRequest, ConfigChatResponse, SearchConstraints
from app.services.gemini import GeminiService


router = APIRouter()
logger = structlog.get_logger()


@router.post("/config-chat", response_model=ConfigChatResponse)
async def run_config_chat(request: ConfigChatRequest):
    """
    Process natural language input to configure research sources.
    
    This endpoint allows users to configure search constraints using
    natural language, e.g., "Only use academic papers" or "Exclude Wikipedia".
    """
    try:
        logger.info(
            "Config chat request",
            user_input=request.userInput[:100],
            history_length=len(request.history)
        )
        
        service = GeminiService()
        result = await service.run_source_config_chat(
            history=request.history,
            user_input=request.userInput,
            current_constraints=request.currentConstraints
        )
        
        return ConfigChatResponse(
            response=result["response"],
            updatedConstraints=result["updated_constraints"]
        )
        
    except Exception as e:
        logger.error("Config chat failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Configuration failed: {str(e)}")
