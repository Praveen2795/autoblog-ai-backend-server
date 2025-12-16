"""
Pipeline Router - Complete AI pipeline orchestration

This endpoint handles the entire content generation pipeline:
Research → Draft → Review/Refine Loop → Visualize

The frontend makes ONE call and receives progress updates.
"""
import json
import asyncio
from typing import AsyncGenerator
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List

from app.models.schemas import (
    SearchConstraints,
    OutputType,
    SourceType,
)
from app.services.gemini import GeminiService


router = APIRouter()

MAX_ITERATIONS = 5


class PipelineRequest(BaseModel):
    """Request for the complete pipeline."""
    topic: str = Field(..., min_length=1, max_length=500)
    keywords: str = Field("")
    outputType: OutputType = Field(default=OutputType.BLOG_POST)
    constraints: Optional[SearchConstraints] = None


class PipelineEvent(BaseModel):
    """A single event in the pipeline stream."""
    event: str  # 'progress', 'research', 'draft', 'review', 'refine', 'visualize', 'complete', 'error'
    agent: str  # Which agent is active
    message: str
    data: Optional[dict] = None


async def run_pipeline(request: PipelineRequest) -> AsyncGenerator[str, None]:
    """
    Run the complete pipeline and yield Server-Sent Events.
    """
    service = GeminiService()
    
    def send_event(event: str, agent: str, message: str, data: dict = None) -> str:
        """Format an SSE event."""
        payload = PipelineEvent(event=event, agent=agent, message=message, data=data)
        return f"data: {payload.model_dump_json()}\n\n"
    
    try:
        # ============================================================
        # PHASE 1: RESEARCH
        # ============================================================
        yield send_event("progress", "RESEARCHER", "Starting research phase...")
        
        constraints = request.constraints or SearchConstraints(
            preferredDomains=[],
            excludedDomains=[],
            focusDescription="",
            allowedSourceTypes=[SourceType.YOUTUBE, SourceType.ARTICLE, SourceType.PAPER]
        )
        
        yield send_event("progress", "RESEARCHER", "Scanning sources for data...")
        
        research_data = await service.run_research_agent(
            topic=request.topic,
            keywords=request.keywords,
            constraints=constraints
        )
        
        yield send_event("research", "RESEARCHER", "Research completed", {
            "sourceCount": len(research_data.sources),
            "contentLength": len(research_data.content)
        })
        
        # ============================================================
        # PHASE 2: DRAFTING
        # ============================================================
        yield send_event("progress", "DRAFTER", "Creating initial draft...")
        
        current_draft = await service.run_drafter_agent(
            research_data=research_data,
            output_type=request.outputType
        )
        
        yield send_event("draft", "DRAFTER", "Draft v1 created", {
            "draftLength": len(current_draft)
        })
        
        # ============================================================
        # PHASE 3: REVIEW/REFINE LOOP (ALL IN PYTHON NOW!)
        # ============================================================
        iteration = 0
        is_approved = False
        feedback_history = []
        previous_scores = []
        last_critique = None
        
        while iteration < MAX_ITERATIONS and not is_approved:
            iteration += 1
            
            yield send_event("progress", "REVIEWER", f"Review cycle {iteration}/{MAX_ITERATIONS}...")
            
            # --- REVIEWER (now with history context!) ---
            feedback = await service.run_reviewer_agent(
                draft=current_draft,
                iteration=iteration,
                output_type=request.outputType,
                previous_scores=previous_scores if previous_scores else None,
                previous_critique=last_critique
            )
            
            # Track scores for next iteration
            previous_scores.append(feedback.score)
            last_critique = feedback.critique
            
            feedback_history.append({
                "iteration": iteration,
                "score": feedback.score,
                "approved": feedback.approved,
                "critique": feedback.critique
            })
            
            yield send_event("review", "REVIEWER", f"Score: {feedback.score}/100", {
                "iteration": iteration,
                "score": feedback.score,
                "approved": feedback.approved,
                "critique": feedback.critique
            })
            
            if feedback.approved:
                is_approved = True
                yield send_event("progress", "REVIEWER", f"✅ Content approved at iteration {iteration}!")
                break
            
            # --- REFINER ---
            yield send_event("progress", "REFINER", f"Refining draft based on feedback...")
            
            # Store draft content before refinement for comparison
            draft_before = current_draft
            draft_before_len = len(current_draft)
            
            current_draft = await service.run_refiner_agent(
                draft=current_draft,
                feedback=feedback.critique,
                output_type=request.outputType
            )
            
            # Debug: Check if draft actually changed
            draft_after_len = len(current_draft)
            
            # Compare more of the content, not just the beginning
            content_identical = (draft_before == current_draft)
            beginning_same = (draft_before[:500] == current_draft[:500])
            ending_same = (draft_before[-500:] == current_draft[-500:]) if len(draft_before) > 500 and len(current_draft) > 500 else True
            
            print(f"\n🔄 REFINER DEBUG - Iteration {iteration}")
            print(f"   Draft length: {draft_before_len} → {draft_after_len} chars ({draft_after_len - draft_before_len:+d})")
            print(f"   Content identical: {content_identical}")
            print(f"   Beginning (first 500) same: {beginning_same}")
            print(f"   Ending (last 500) same: {ending_same}")
            if not content_identical:
                print(f"   Last 200 chars of NEW draft: ...{current_draft[-200:]}")
            print()
            
            yield send_event("refine", "REFINER", f"Draft v{iteration + 1} ready", {
                "iteration": iteration + 1,
                "draftLength": len(current_draft)
            })
        
        if not is_approved:
            yield send_event("progress", "SYSTEM", f"Max iterations ({MAX_ITERATIONS}) reached, proceeding with best draft")
        
        # ============================================================
        # PHASE 4: VISUALIZATION (for carousels/cards)
        # ============================================================
        final_slides = None
        
        if request.outputType != OutputType.BLOG_POST:
            yield send_event("progress", "VISUALIZER", "Generating visual assets...")
            
            final_slides = await service.run_visualizer_agent(current_draft)
            
            yield send_event("visualize", "VISUALIZER", f"Generated {len(final_slides)} visual assets", {
                "slideCount": len(final_slides)
            })
        
        # ============================================================
        # COMPLETE
        # ============================================================
        yield send_event("complete", "SYSTEM", "Pipeline completed successfully!", {
            "finalDraft": current_draft,
            "finalSlides": [s.model_dump() for s in final_slides] if final_slides else None,
            "totalIterations": iteration,
            "feedbackHistory": feedback_history,
            "researchSources": [{"title": s.title, "uri": s.uri, "type": s.type.value} for s in research_data.sources]
        })
        
    except Exception as e:
        yield send_event("error", "SYSTEM", f"Pipeline failed: {str(e)}", {
            "error": str(e)
        })


@router.post("/pipeline")
async def run_full_pipeline(request: PipelineRequest):
    """
    Run the complete content generation pipeline.
    
    Returns a Server-Sent Events stream with progress updates.
    The frontend can listen to these events and update the UI in real-time.
    """
    return StreamingResponse(
        run_pipeline(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
