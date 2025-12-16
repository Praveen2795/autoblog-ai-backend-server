"""
Gemini AI Service - Core AI logic (PROTECTED IP)

This module contains all the proprietary prompts and AI logic.
It is server-side only and never exposed to the client.
"""
import json
import asyncio
import structlog
from typing import List, Dict, Any, Optional

from google import genai
from google.genai import types

from app.config import settings
from app.models.schemas import (
    SearchConstraints,
    ChatMessage,
    ResearchData,
    Source,
    SourceType,
    OutputType,
    ReviewFeedback,
    ReviewIssue,
    IssueType,
    VisualSlide,
)
from app.prompts import (
    CONFIG_CHAT_PROMPT,
    RESEARCH_PROMPT,
    BLOG_DRAFTER_PROMPT,
    VISUAL_DRAFTER_PROMPT,
    REVIEWER_PROMPT,
    REFINER_PROMPT,
)


logger = structlog.get_logger()


class GeminiService:
    """
    Gemini AI Service for content generation.
    
    All prompts and AI logic are encapsulated here,
    protected from client-side exposure.
    """
    
    def __init__(self):
        """Initialize the Gemini client."""
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not configured")
        
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.flash_model = settings.GEMINI_FLASH_MODEL
        self.pro_model = settings.GEMINI_PRO_MODEL
        self.image_model = settings.GEMINI_IMAGE_MODEL
    
    # ================================================================
    # CONFIGURATION CHAT AGENT
    # ================================================================
    
    async def run_source_config_chat(
        self,
        history: List[ChatMessage],
        user_input: str,
        current_constraints: SearchConstraints
    ) -> Dict[str, Any]:
        """
        Process natural language input to configure research sources.
        """
        # Flatten history for context
        conversation = "\n".join(
            f"{m.role.upper()}: {m.text}" for m in history
        )
        
        prompt = CONFIG_CHAT_PROMPT.format(
            preferred_domains=json.dumps(current_constraints.preferredDomains),
            excluded_domains=json.dumps(current_constraints.excludedDomains),
            allowed_source_types=json.dumps([st.value for st in current_constraints.allowedSourceTypes]),
            focus_description=current_constraints.focusDescription,
            user_input=user_input,
            conversation_history=conversation
        )
        
        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.flash_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    system_instruction="You are a strict, secure configuration agent. You only discuss data sources."
                )
            )
            
            data = json.loads(response.text or "{}")
            new_constraints = data.get("constraints", {})
            
            # Ensure defaults
            if not new_constraints.get("allowedSourceTypes"):
                new_constraints["allowedSourceTypes"] = ["YOUTUBE", "ARTICLE", "PAPER"]
            
            return {
                "response": data.get("response", "I didn't understand that."),
                "updated_constraints": SearchConstraints(
                    preferredDomains=new_constraints.get("preferredDomains", []),
                    excludedDomains=new_constraints.get("excludedDomains", []),
                    focusDescription=new_constraints.get("focusDescription", ""),
                    allowedSourceTypes=[
                        SourceType(st) for st in new_constraints.get("allowedSourceTypes", [])
                    ]
                )
            }
            
        except Exception as e:
            logger.error("Config chat error", error=str(e))
            return {
                "response": "System Error: Could not parse configuration.",
                "updated_constraints": current_constraints
            }
    
    # ================================================================
    # RESEARCH AGENT
    # ================================================================
    
    async def _validate_content_quality(self, content: str, topic: str) -> bool:
        """Validate research content quality."""
        prompt = f"""Analyze the following research notes about "{topic}".
        Determine if they are high-quality, relevant, and provide enough technical depth to write a blog post.
        Return JSON: {{ "isGood": boolean }}
        
        NOTES:
        {content[:5000]}"""
        
        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.pro_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            result = json.loads(response.text or "{}")
            return result.get("isGood", False)
            
        except Exception as e:
            logger.error("Validation error", error=str(e))
            return False
    
    async def _run_research_stream(
        self,
        topic: str,
        keywords: str,
        source_type: SourceType,
        constraints: Optional[SearchConstraints]
    ) -> Dict[str, Any]:
        """Run a single research stream."""
        type_prompts = {
            SourceType.YOUTUBE: "Search for YouTube video transcripts, technical talks, and video summaries.",
            SourceType.PAPER: "Search for published research papers, arXiv preprints, and academic abstracts.",
            SourceType.ARTICLE: "Search for high-authority tech news, official documentation, and expert blogs."
        }
        
        type_prompt = type_prompts.get(source_type, type_prompts[SourceType.ARTICLE])
        
        # Build query modifiers
        query_modifiers = ""
        if constraints:
            if constraints.preferredDomains:
                site_ops = " OR ".join(f"site:{d}" for d in constraints.preferredDomains)
                query_modifiers += f" ({site_ops})"
            if constraints.excludedDomains:
                exclude_ops = " ".join(f"-site:{d}" for d in constraints.excludedDomains)
                query_modifiers += f" {exclude_ops}"
        
        best_content = ""
        collected_sources: List[Source] = []
        
        for attempt in range(1, settings.MAX_RESEARCH_RETRIES + 1):
            logger.info(f"[{source_type.value}] Attempt {attempt} for topic: {topic}")
            
            try:
                prompt = RESEARCH_PROMPT.format(
                    attempt=attempt,
                    type_prompt=type_prompt,
                    topic=topic,
                    keywords=keywords,
                    focus_description=constraints.focusDescription if constraints else "General Technical",
                    query_modifiers=query_modifiers
                )
                
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.pro_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(google_search=types.GoogleSearch())]
                    )
                )
                
                if response.text:
                    # Extract sources from grounding metadata
                    current_sources: List[Source] = []
                    if response.candidates and response.candidates[0].grounding_metadata:
                        chunks = response.candidates[0].grounding_metadata.grounding_chunks or []
                        for chunk in chunks:
                            if chunk.web and chunk.web.uri and chunk.web.title:
                                current_sources.append(Source(
                                    title=chunk.web.title,
                                    uri=chunk.web.uri,
                                    type=source_type
                                ))
                    
                    best_content = response.text
                    collected_sources = current_sources
                    
                    # Validate quality
                    is_valid = await self._validate_content_quality(response.text, topic)
                    if is_valid:
                        break
                        
            except Exception as e:
                logger.error(f"[{source_type.value}] Error on attempt {attempt}", error=str(e))
        
        return {"text": best_content, "sources": collected_sources}
    
    async def run_research_agent(
        self,
        topic: str,
        keywords: str = "",
        constraints: Optional[SearchConstraints] = None
    ) -> ResearchData:
        """Run the research agent across multiple source types."""
        # Determine which streams to run
        types_to_run = (
            constraints.allowedSourceTypes
            if constraints and constraints.allowedSourceTypes
            else [SourceType.YOUTUBE, SourceType.ARTICLE, SourceType.PAPER]
        )
        
        # Run streams in parallel
        tasks = [
            self._run_research_stream(topic, keywords, st, constraints)
            for st in types_to_run
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Combine results
        combined_content = ""
        all_sources: List[Source] = []
        
        for result, source_type in zip(results, types_to_run):
            combined_content += f"\n# SECTION: {source_type.value} ANALYSIS\n{result['text']}\n\n"
            all_sources.extend(result["sources"])
        
        if not combined_content.strip():
            combined_content = "No research data found based on the provided constraints."
        
        # Deduplicate sources
        unique_sources = list({s.uri: s for s in all_sources}.values())
        
        return ResearchData(content=combined_content, sources=unique_sources)
    
    # ================================================================
    # DRAFTER AGENT
    # ================================================================
    
    async def run_drafter_agent(
        self,
        research_data: ResearchData,
        output_type: OutputType
    ) -> str:
        """Run the drafter agent to create initial content."""
        print(f"\n🖊️ DRAFTER: Starting draft generation for {output_type.value}...")
        
        if output_type == OutputType.BLOG_POST:
            prompt = BLOG_DRAFTER_PROMPT.format(
                research_content=research_data.content[:15000]  # Limit research content
            )
            
            print(f"   Prompt length: {len(prompt)} chars")
            print(f"   Calling Gemini API (this may take 30-60 seconds)...")
            
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.pro_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            max_output_tokens=16000,  # Request longer output
                        )
                    ),
                    timeout=180.0  # 3 minute timeout
                )
                
                result = response.text or "Drafting failed."
                print(f"   ✅ Draft generated: {len(result)} chars")
                
                # Check for truncation
                last_char = result.strip()[-1] if result.strip() else ''
                if last_char not in '.!?")\']':
                    print(f"   ⚠️ WARNING: Draft may be truncated (ends with: ...{result[-100:]})")
                
                return result
            except asyncio.TimeoutError:
                print(f"   ❌ TIMEOUT: Drafter took too long (>180s)")
                raise Exception("Drafter timeout - Gemini API took too long to respond")
        
        else:
            # Visual carousel/cards flow
            is_linkedin = output_type == OutputType.LINKEDIN_CAROUSEL
            card_count = 8 if is_linkedin else 5
            context = (
                "LinkedIn Carousel (Professional, Insightful)"
                if is_linkedin
                else "Instagram Post (Visual, punchy, high energy)"
            )
            
            prompt = VISUAL_DRAFTER_PROMPT.format(
                context=context,
                card_count=card_count,
                research_content=research_data.content[:15000]
            )
            
            print(f"   Visual draft prompt length: {len(prompt)} chars")
            
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.pro_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            max_output_tokens=16000,
                        )
                    ),
                    timeout=180.0
                )
                print(f"   ✅ Visual draft generated: {len(response.text or '')} chars")
                return response.text or "[]"
            except asyncio.TimeoutError:
                print(f"   ❌ TIMEOUT: Visual drafter took too long (>180s)")
                raise Exception("Drafter timeout - Gemini API took too long to respond")
    
    # ================================================================
    # REVIEWER AGENT
    # ================================================================
    
    async def run_reviewer_agent(
        self,
        draft: str,
        iteration: int,
        output_type: OutputType,
        previous_scores: list = None,
        previous_critique: str = None
    ) -> ReviewFeedback:
        """Run the reviewer agent to critique content with structured feedback."""
        
        # Build previous feedback context
        if previous_scores and len(previous_scores) > 0:
            prev_feedback = f"""PREVIOUS REVIEW HISTORY:
- Previous iteration score(s): {previous_scores}
- Last issues that should have been addressed: {previous_critique[:1000] if previous_critique else 'N/A'}

You MUST check if the above issues were fixed and adjust your score accordingly!"""
        else:
            prev_feedback = "This is the FIRST review. Evaluate the content fresh."
        
        # IMPORTANT: Don't truncate too aggressively - Gemini 2.5 Pro can handle large context
        # Truncating before the conclusion causes the reviewer to think content is incomplete!
        draft_for_review = draft[:40000] if len(draft) > 40000 else draft
        
        # Log if we're truncating so we know
        if len(draft) > 40000:
            print(f"   ⚠️ REVIEWER: Truncating draft from {len(draft)} to 40000 chars")
        else:
            print(f"   📖 REVIEWER: Reviewing full draft ({len(draft)} chars)")
        
        if output_type == OutputType.BLOG_POST:
            content_prompt = f"Review the following blog post draft:\n{draft_for_review}"
        else:
            content_prompt = f"""Review the following JSON content for a Social Media Carousel:
{draft_for_review}

Check for punchiness, clarity, and image prompt relevance. Ensure there is NO markdown in the JSON strings."""
        
        prompt = REVIEWER_PROMPT.format(
            iteration=iteration,
            content_prompt=content_prompt,
            previous_feedback=prev_feedback
        )
        
        # Retry logic for JSON parsing issues
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.pro_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
                
                if not response.text:
                    raise ValueError("Reviewer returned empty response")
                
                # Try to parse JSON, handle potential issues
                text = response.text.strip()
                
                # Sometimes the model wraps JSON in markdown code blocks
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                    text = text.strip()
                
                data = json.loads(text)
                score = int(data.get("score", 75))
                summary = data.get("summary", "")
                
                # Parse structured issues
                raw_issues = data.get("issues", [])
                issues = []
                for issue_data in raw_issues:
                    try:
                        # Map string type to enum
                        issue_type_str = issue_data.get("type", "STYLE_ISSUE")
                        issue_type = IssueType(issue_type_str) if issue_type_str in [e.value for e in IssueType] else IssueType.STYLE_ISSUE
                        
                        issues.append(ReviewIssue(
                            type=issue_type,
                            location=issue_data.get("location", "unknown"),
                            description=issue_data.get("description", ""),
                            action=issue_data.get("action", ""),
                            priority=int(issue_data.get("priority", 3))
                        ))
                    except Exception as e:
                        logger.warning(f"Failed to parse issue: {issue_data}, error: {e}")
                        continue
                
                # IMPORTANT: Force approved logic - don't rely on Gemini
                # Approve if:
                # 1. Score > 90 (excellent quality)
                # 2. Score >= 85 AND iteration >= 3 AND no priority 1 issues
                has_critical_issues = any(i.priority == 1 for i in issues)
                approved = (score > 90 and not has_critical_issues) or (score >= 85 and iteration >= 3 and not has_critical_issues)
                
                # Generate formatted critique from issues for logging and backward compatibility
                formatted_issues = []
                for i, issue in enumerate(sorted(issues, key=lambda x: x.priority), 1):
                    formatted_issues.append(
                        f"[P{issue.priority}] {issue.type.value} @ {issue.location}\n"
                        f"    Problem: {issue.description}\n"
                        f"    Action: {issue.action}"
                    )
                critique = "\n\n".join(formatted_issues) if formatted_issues else summary
                
                # Print to console for visibility
                print(f"\n{'='*60}")
                print(f"📝 REVIEWER RESULT - Iteration {iteration}")
                print(f"{'='*60}")
                print(f"   Score: {score}/100")
                print(f"   Summary: {summary}")
                print(f"   Approved: {approved} (Gemini said: {data.get('approved')})")
                print(f"   Issues found: {len(issues)}")
                print(f"\n   📋 STRUCTURED ISSUES:")
                print(f"   {'-'*50}")
                for issue in sorted(issues, key=lambda x: x.priority):
                    print(f"   [P{issue.priority}] {issue.type.value}")
                    print(f"       Location: {issue.location}")
                    print(f"       Problem: {issue.description}")
                    print(f"       Action: {issue.action}")
                    print(f"   {'-'*50}")
                print(f"{'='*60}\n")
                
                return ReviewFeedback(
                    score=score,
                    approved=approved,
                    summary=summary,
                    issues=issues,
                    critique=critique  # For backward compat and refiner
                )
                
            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")
                continue
            except Exception as e:
                last_error = e
                logger.warning(f"Review error on attempt {attempt + 1}: {e}")
                continue
        
        # If all retries failed, return a default response to continue the pipeline
        logger.error(f"All review attempts failed: {last_error}")
        return ReviewFeedback(
            score=70,
            approved=False,
            summary="Review encountered parsing issues.",
            issues=[],
            critique="Review encountered parsing issues. Please refine for clarity."
        )
    
    # ================================================================
    # REFINER AGENT
    # ================================================================
    
    async def run_refiner_agent(
        self,
        draft: str,
        feedback: str,
        output_type: OutputType
    ) -> str:
        """Run the refiner agent to improve content with accountability."""
        
        # Don't truncate the draft too aggressively - Gemini 2.5 Pro can handle large context
        # Only truncate if extremely large (>50k chars)
        draft_to_refine = draft[:50000] if len(draft) > 50000 else draft
        
        print(f"\n✏️ REFINER: Processing draft with accountability checklist...")
        print(f"   Original draft length: {len(draft)} chars")
        print(f"   Draft sent to refiner: {len(draft_to_refine)} chars")
        print(f"\n   📋 STRUCTURED FEEDBACK BEING SENT TO REFINER:")
        print(f"   {'-'*50}")
        print(f"   {feedback}")
        print(f"   {'-'*50}")
        
        prompt = REFINER_PROMPT.format(
            draft=draft_to_refine,
            feedback=feedback  # Send FULL structured feedback
        )
        
        print(f"   Total prompt length: {len(prompt)} chars")
        
        # Configure for longer output - Gemini 2.5 Pro supports 65k output tokens
        config = types.GenerateContentConfig(
            max_output_tokens=32000,  # ~100k chars should be plenty
        )
        
        if output_type != OutputType.BLOG_POST:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=32000,
            )
        
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.pro_model,
                    contents=prompt,
                    config=config
                ),
                timeout=180.0  # 3 minute timeout for refining
            )
            
            result = response.text or draft
            
            # Extract the revised draft from the accountability format
            # The refiner now outputs: ## FIX PLAN: ... ---REVISED_DRAFT_START--- ... ---REVISED_DRAFT_END---
            if "---REVISED_DRAFT_START---" in result and "---REVISED_DRAFT_END---" in result:
                # Log the fix plan for visibility
                start_marker = "---REVISED_DRAFT_START---"
                end_marker = "---REVISED_DRAFT_END---"
                
                fix_plan = result[:result.index(start_marker)]
                print(f"\n   📝 REFINER'S FIX PLAN:")
                for line in fix_plan.split("\n")[:15]:  # Show first 15 lines of fix plan
                    print(f"   {line}")
                if fix_plan.count("\n") > 15:
                    print(f"   ... ({fix_plan.count(chr(10)) - 15} more lines)")
                
                # Extract just the draft part
                start_idx = result.index(start_marker) + len(start_marker)
                end_idx = result.index(end_marker)
                result = result[start_idx:end_idx].strip()
            elif "## FIX PLAN:" in result:
                # Fallback: Try to extract after the fix plan section
                # Log the fix plan
                fix_plan_match = result.split("## FIX PLAN:")[1] if "## FIX PLAN:" in result else ""
                print(f"\n   📝 REFINER'S FIX PLAN:")
                for line in fix_plan_match.split("\n")[:10]:
                    print(f"   {line}")
                
                # Look for the start of actual content (usually markdown heading)
                lines = result.split("\n")
                content_start = 0
                in_fix_plan = False
                for i, line in enumerate(lines):
                    if "## FIX PLAN" in line:
                        in_fix_plan = True
                        continue
                    if in_fix_plan and line.strip().startswith("#") and "FIX" not in line.upper():
                        content_start = i
                        break
                    if in_fix_plan and line.strip().startswith("---") and "DRAFT" not in line.upper() and "FIX" not in line.upper():
                        content_start = i + 1
                        break
                if content_start > 0:
                    result = "\n".join(lines[content_start:]).strip()
            
            # Clean up potential markdown code blocks
            if result.strip().startswith("```"):
                lines = result.strip().split("\n")
                # Remove first line (```markdown or ```) and last line (```)
                if len(lines) > 2:
                    result = "\n".join(lines[1:-1])
            
            print(f"   ✅ Refined draft: {len(result)} chars")
            
            # Check if the response might have been truncated
            # Signs of truncation: ends mid-word, ends with incomplete sentence
            last_char = result.strip()[-1] if result.strip() else ''
            if last_char not in '.!?")\']':
                print(f"   ⚠️ WARNING: Response may be truncated (ends with '{result[-50:]}')")
            
            # Verify the refiner actually produced something meaningful
            if len(result) < 500:
                print(f"   ⚠️ WARNING: Refiner returned suspiciously short content, keeping original")
                return draft
            
            return result
            
        except asyncio.TimeoutError:
            print(f"   ❌ TIMEOUT: Refiner took too long (>180s)")
            return draft
        except Exception as e:
            logger.error(f"Refiner error: {e}")
            print(f"   ❌ ERROR: {e}")
            return draft  # Return original draft if refining fails
    
    # ================================================================
    # VISUALIZER AGENT
    # ================================================================
    
    async def run_visualizer_agent(self, draft_json: str) -> List[VisualSlide]:
        """Run the visualizer agent to generate images for slides."""
        try:
            slides_data = json.loads(draft_json)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse draft JSON for visualizer", error=str(e))
            return []
        
        async def generate_image(slide_data: dict) -> VisualSlide:
            """Generate image for a single slide."""
            slide = VisualSlide(**slide_data)
            
            try:
                image_prompt = f"{slide.imagePrompt} high quality, photorealistic, 4k, no text in image"
                
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.image_model,
                    contents=image_prompt
                )
                
                # Extract image from response
                if response.candidates and response.candidates[0].content:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            slide.imageUrl = (
                                f"data:{part.inline_data.mime_type};"
                                f"base64,{part.inline_data.data}"
                            )
                            break
                
            except Exception as e:
                logger.error(
                    f"Failed to generate image for slide {slide.slideNumber}",
                    error=str(e)
                )
            
            return slide
        
        # Generate images in parallel
        tasks = [generate_image(s) for s in slides_data]
        slides = await asyncio.gather(*tasks)
        
        return list(slides)
