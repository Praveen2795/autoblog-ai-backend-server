"""
Pydantic Schemas for Request/Response validation.
These models ensure type safety and automatic documentation.
"""
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


# ============================================================
# ENUMS
# ============================================================

class SourceType(str, Enum):
    """Types of research sources."""
    YOUTUBE = "YOUTUBE"
    ARTICLE = "ARTICLE"
    PAPER = "PAPER"


class OutputType(str, Enum):
    """Types of content output."""
    BLOG_POST = "BLOG_POST"
    LINKEDIN_CAROUSEL = "LINKEDIN_CAROUSEL"
    INSTAGRAM_CARDS = "INSTAGRAM_CARDS"


# ============================================================
# CORE MODELS
# ============================================================

class Source(BaseModel):
    """A research source reference."""
    title: str = Field(..., description="Title of the source")
    uri: str = Field(..., description="URL of the source")
    type: SourceType = Field(..., description="Type of source")


class ResearchData(BaseModel):
    """Research results from the Researcher agent."""
    content: str = Field(..., description="Combined research content")
    sources: List[Source] = Field(default_factory=list, description="List of sources used")


class VisualSlide(BaseModel):
    """A single slide for carousel/card outputs."""
    slideNumber: int = Field(..., ge=1, description="Slide number (1-indexed)")
    title: str = Field(..., description="Slide title")
    content: str = Field(..., description="Slide content (bullet points or text)")
    imagePrompt: str = Field(..., description="Prompt for image generation")
    imageUrl: Optional[str] = Field(None, description="Generated image URL (base64 data URI)")


class IssueType(str, Enum):
    """Types of issues the reviewer can identify."""
    MISSING_CONTENT = "MISSING_CONTENT"       # Section/paragraph needs to be added
    INCOMPLETE_CONTENT = "INCOMPLETE_CONTENT" # Existing content is cut off or unfinished
    INACCURATE_DATA = "INACCURATE_DATA"       # Facts, numbers, or claims are wrong
    WEAK_ARGUMENT = "WEAK_ARGUMENT"           # Reasoning or analysis is shallow
    POOR_STRUCTURE = "POOR_STRUCTURE"         # Organization or flow issues
    STYLE_ISSUE = "STYLE_ISSUE"               # Tone, voice, or writing quality
    FORMATTING_ERROR = "FORMATTING_ERROR"     # Markdown, JSON, or layout problems


class ReviewIssue(BaseModel):
    """A specific, actionable issue identified by the reviewer."""
    type: IssueType = Field(..., description="Category of the issue")
    location: str = Field(..., description="Where in the draft (section name, paragraph, or 'end of article')")
    description: str = Field(..., description="Clear description of what's wrong")
    action: str = Field(..., description="Specific action to fix it (ADD, REPLACE, REWRITE, REMOVE)")
    priority: int = Field(..., ge=1, le=3, description="1=Critical, 2=Important, 3=Minor")


class ReviewFeedback(BaseModel):
    """Feedback from the Reviewer agent."""
    score: int = Field(..., ge=0, le=100, description="Quality score (0-100)")
    approved: bool = Field(..., description="True if score > 90 and content is approved")
    summary: str = Field(..., description="One-line summary of overall quality")
    issues: List[ReviewIssue] = Field(default_factory=list, description="List of specific issues to fix")
    # Keep critique for backward compatibility and logging
    critique: str = Field("", description="Full critique text (auto-generated from issues)")


class SearchConstraints(BaseModel):
    """Configuration constraints for research."""
    preferredDomains: List[str] = Field(default_factory=list, description="Preferred domains to search")
    excludedDomains: List[str] = Field(default_factory=list, description="Domains to exclude")
    focusDescription: str = Field("", description="Focus description for research")
    allowedSourceTypes: List[SourceType] = Field(
        default=[SourceType.YOUTUBE, SourceType.ARTICLE, SourceType.PAPER],
        description="Which source types to search"
    )


class ChatMessage(BaseModel):
    """A message in the configuration chat."""
    role: str = Field(..., pattern="^(user|model)$", description="Message role")
    text: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================
# REQUEST MODELS
# ============================================================

class ConfigChatRequest(BaseModel):
    """Request for source configuration chat."""
    history: List[ChatMessage] = Field(default_factory=list, description="Chat history")
    userInput: str = Field(..., min_length=1, description="User's input message")
    currentConstraints: SearchConstraints = Field(
        default_factory=SearchConstraints,
        description="Current search constraints"
    )


class ResearchRequest(BaseModel):
    """Request for research agent."""
    topic: str = Field(..., min_length=1, max_length=500, description="Topic to research")
    keywords: str = Field("", description="Additional keywords to prioritize")
    constraints: Optional[SearchConstraints] = Field(None, description="Search constraints")


class DraftRequest(BaseModel):
    """Request for draft agent."""
    researchData: ResearchData = Field(..., description="Research data to use")
    outputType: OutputType = Field(..., description="Type of output to generate")


class ReviewRequest(BaseModel):
    """Request for review agent."""
    draft: str = Field(..., min_length=1, description="Draft content to review")
    iteration: int = Field(..., ge=1, description="Current iteration number")
    outputType: OutputType = Field(..., description="Type of content being reviewed")


class RefineRequest(BaseModel):
    """Request for refine agent."""
    draft: str = Field(..., min_length=1, description="Draft content to refine")
    feedback: str = Field(..., description="Feedback to address")
    outputType: OutputType = Field(..., description="Type of content being refined")


class VisualizeRequest(BaseModel):
    """Request for visualize agent."""
    draftJson: str = Field(..., description="JSON string of slides to visualize")


# ============================================================
# RESPONSE MODELS
# ============================================================

class ConfigChatResponse(BaseModel):
    """Response from configuration chat."""
    response: str = Field(..., description="Agent's response message")
    updatedConstraints: SearchConstraints = Field(..., description="Updated search constraints")


class ResearchResponse(BaseModel):
    """Response from research agent."""
    data: ResearchData = Field(..., description="Research results")


class DraftResponse(BaseModel):
    """Response from draft agent."""
    draft: str = Field(..., description="Generated draft content")


class ReviewResponse(BaseModel):
    """Response from review agent."""
    feedback: ReviewFeedback = Field(..., description="Review feedback")


class RefineResponse(BaseModel):
    """Response from refine agent."""
    refinedDraft: str = Field(..., description="Refined draft content")


class VisualizeResponse(BaseModel):
    """Response from visualize agent."""
    slides: List[VisualSlide] = Field(..., description="Slides with generated images")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    gemini_configured: bool = Field(..., description="Whether Gemini API is configured")
