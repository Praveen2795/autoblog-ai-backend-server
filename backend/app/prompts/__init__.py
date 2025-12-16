"""
Prompt Templates Module

All proprietary prompts are stored here, server-side only.
These are NEVER exposed to the client.
"""
from app.prompts.templates import (
    CONFIG_CHAT_PROMPT,
    RESEARCH_PROMPT,
    BLOG_DRAFTER_PROMPT,
    VISUAL_DRAFTER_PROMPT,
    REVIEWER_PROMPT,
    REFINER_PROMPT,
)

__all__ = [
    "CONFIG_CHAT_PROMPT",
    "RESEARCH_PROMPT",
    "BLOG_DRAFTER_PROMPT",
    "VISUAL_DRAFTER_PROMPT",
    "REVIEWER_PROMPT",
    "REFINER_PROMPT",
]
