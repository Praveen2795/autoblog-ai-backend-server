"""
Content Guardrail Service

Uses Gemini Flash to check if a topic is safe to process.
Blocks political, sexual, illegal, violent, or harmful content.
"""
import structlog
from typing import Tuple
from google import genai
from google.genai import types

from app.config import settings


logger = structlog.get_logger()


# Categories of content to block
BLOCKED_CATEGORIES = [
    "political",
    "sexual", 
    "illegal",
    "violent",
    "hateful",
    "discriminatory",
    "dangerous",
    "self-harm",
    "terrorism",
    "weapons",
    "drugs",
    "gambling",
]


GUARDRAIL_PROMPT = """You are a content moderation system. Determine if a blog topic is SAFE or UNSAFE.

UNSAFE topics include:
- Political (elections, candidates, parties, controversial policies)
- Sexual or adult content
- Illegal activities (hacking, fraud, theft)
- Violence or harm
- Hate speech or discrimination
- Terrorism, weapons, drugs
- Gambling

SAFE topics include:
- Technology, programming, science
- Business, health, lifestyle, hobbies
- Educational and informational content

TOPIC: "{topic}"

Respond with ONLY valid JSON (no markdown):
{{"safe": true, "reason": "brief reason"}} or {{"safe": false, "reason": "brief reason"}}"""


class GuardrailService:
    """
    Content moderation guardrail using Gemini Flash.
    
    Fast, cheap check before running the expensive pipeline.
    """
    
    def __init__(self):
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Gemini client."""
        if settings.GEMINI_API_KEY:
            self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    async def check_topic(self, topic: str) -> Tuple[bool, str]:
        """
        Check if a topic is safe to process.
        
        Args:
            topic: The blog topic to check
            
        Returns:
            Tuple of (is_safe, reason)
        """
        if not self.client:
            logger.warning("Guardrail skipped - no API key configured")
            return True, "Guardrail skipped - no API key"
        
        # ============================================================
        # LAYER 1: Input validation (regex-based, no API call)
        # ============================================================
        is_valid, reason = self._validate_input(topic)
        if not is_valid:
            logger.warning("Topic rejected by input validation", topic=topic[:50], reason=reason)
            return False, reason
        
        # ============================================================
        # LAYER 2: Keyword filter (no API call)
        # ============================================================
        is_safe, reason = self._quick_keyword_check(topic)
        if not is_safe:
            logger.warning("Topic blocked by keyword filter", topic=topic[:50], reason=reason)
            return False, reason
        
        # ============================================================
        # LAYER 3: AI moderation (API call - only for valid inputs)
        # ============================================================
        # Use Gemini Flash for nuanced check
        try:
            prompt = GUARDRAIL_PROMPT.format(topic=topic)
            
            response = self.client.models.generate_content(
                model=settings.GEMINI_FLASH_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,  # Low temperature for consistent moderation
                    max_output_tokens=256,  # Increased for full response
                )
            )
            
            result_text = response.text.strip()
            
            # Parse the JSON response
            import json
            import re
            
            # Clean up potential markdown formatting
            if "```" in result_text:
                # Extract content between code blocks
                match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', result_text)
                if match:
                    result_text = match.group(1).strip()
            
            # Strategy 1: Try direct JSON parse first (most reliable if valid)
            is_safe = None
            reason = "Unknown"
            
            try:
                result = json.loads(result_text)
                is_safe = result.get("safe", False)
                reason = result.get("reason", "Unknown")
                logger.info("Parsed via direct JSON", is_safe=is_safe, reason=reason)
            except json.JSONDecodeError:
                # Strategy 2: Try regex for {"safe": true/false, "reason": "..."}
                # Handle escaped quotes and complex strings
                json_match = re.search(r'\{\s*"safe"\s*:\s*(true|false)', result_text, re.IGNORECASE)
                if json_match:
                    is_safe = json_match.group(1).lower() == "true"
                    # Try to extract reason separately
                    reason_match = re.search(r'"reason"\s*:\s*"((?:[^"\\]|\\.)*)"\s*\}', result_text)
                    if reason_match:
                        reason = reason_match.group(1).replace('\\"', '"')
                    else:
                        reason = "Safe topic" if is_safe else "Unsafe topic"
                    logger.info("Parsed via regex", is_safe=is_safe, reason=reason)
                else:
                    # Strategy 3: Look for keywords as last resort
                    text_lower = result_text.lower()
                    if '"safe": true' in text_lower or '"safe":true' in text_lower:
                        is_safe = True
                        reason = "Parsed from response text"
                    elif '"safe": false' in text_lower or '"safe":false' in text_lower:
                        is_safe = False
                        reason = "Parsed from response text"
                    else:
                        # Default to safe if we can't parse (fail-open)
                        is_safe = True
                        reason = f"Could not parse response: {result_text[:50]}"
                    logger.warning("Parsed via keyword fallback", is_safe=is_safe, text=result_text[:100])
            
            logger.info(
                "Guardrail check completed",
                topic=topic[:50],
                is_safe=is_safe,
                reason=reason
            )
            
            return is_safe, reason
            
        except Exception as e:
            logger.error("Guardrail check failed", error=str(e), topic=topic[:50])
            # On error, allow through but log it (fail-open for availability)
            # Change to return False if you want fail-closed behavior
            return True, f"Guardrail error: {str(e)}"
    
    def _validate_input(self, topic: str) -> Tuple[bool, str]:
        """
        Validate input before processing.
        Uses regex to catch garbage/invalid inputs without API call.
        
        Returns:
            Tuple of (is_valid, reason)
        """
        import re
        
        # Strip whitespace
        topic = topic.strip()
        
        # Check 1: Empty or whitespace only
        if not topic:
            return False, "Topic is empty"
        
        # Check 2: Too short (less than 3 characters)
        if len(topic) < 3:
            return False, "Topic is too short (minimum 3 characters)"
        
        # Check 3: Too long (more than 500 characters)
        if len(topic) > 500:
            return False, "Topic is too long (maximum 500 characters)"
        
        # Check 4: Only symbols/punctuation (no letters)
        if not re.search(r'[a-zA-Z]', topic):
            return False, "Topic must contain letters, not just symbols"
        
        # Check 5: Excessive symbols (more than 50% non-alphanumeric)
        alpha_count = len(re.findall(r'[a-zA-Z0-9\s]', topic))
        if alpha_count < len(topic) * 0.5:
            return False, "Topic contains too many symbols"
        
        # Check 6: Repetitive characters (e.g., "aaaaaaa" or "!!!!!!")
        if re.search(r'(.)\1{5,}', topic):
            return False, "Topic contains repetitive characters"
        
        # Check 7: Random gibberish detection (no vowels in long words)
        words = topic.split()
        for word in words:
            # Skip short words and numbers
            if len(word) > 4 and word.isalpha():
                if not re.search(r'[aeiouAEIOU]', word):
                    return False, f"Topic contains gibberish: '{word}'"
        
        # Check 8: Only numbers
        if topic.replace(' ', '').isdigit():
            return False, "Topic cannot be only numbers"
        
        # Check 9: Looks like code/script injection
        code_patterns = [
            r'<script',
            r'javascript:',
            r'onclick=',
            r'onerror=',
            r'\{\{.*\}\}',  # Template injection
            r'\$\{.*\}',    # Variable injection
            r'SELECT.*FROM',  # SQL injection
            r'DROP\s+TABLE',
            r'--\s*$',      # SQL comment
            r';\s*DELETE',
        ]
        topic_check = topic.lower()
        for pattern in code_patterns:
            if re.search(pattern, topic_check, re.IGNORECASE):
                return False, "Topic looks like code injection attempt"
        
        # Check 10: Excessive whitespace
        if re.search(r'\s{5,}', topic):
            return False, "Topic contains excessive whitespace"
        
        # Check 11: Only special characters mixed with few letters
        special_count = len(re.findall(r'[!@#$%^&*()_+=\[\]{}|\\:";\'<>?,./~`]', topic))
        if special_count > 10:
            return False, "Topic contains too many special characters"
        
        # Check 12: URL-only topics (just a link, not a real topic)
        if re.match(r'^https?://\S+$', topic.strip()):
            return False, "Topic cannot be just a URL"
        
        return True, "Input validation passed"
    
    def _quick_keyword_check(self, topic: str) -> Tuple[bool, str]:
        """
        Fast keyword-based pre-filter.
        Catches obvious violations without API call.
        """
        topic_lower = topic.lower()
        
        # Explicit blocked keywords
        blocked_keywords = [
            # Violence
            'kill', 'murder', 'assassinate', 'bomb', 'terrorist', 'terrorism',
            'mass shooting', 'genocide', 'torture',
            
            # Sexual
            'porn', 'xxx', 'nude', 'naked', 'sex video', 'onlyfans hack',
            
            # Illegal
            'hack into', 'crack password', 'steal credit card', 'identity theft',
            'counterfeit', 'money laundering', 'tax evasion', 'drug dealing',
            
            # Weapons
            'make a bomb', 'build explosive', 'gun silencer', '3d print gun',
            
            # Hate
            'white supremacy', 'nazi', 'racial slur',
            
            # Self-harm
            'how to suicide', 'kill myself', 'self harm methods',
            
            # Drugs
            'cook meth', 'make cocaine', 'grow marijuana illegally',
        ]
        
        for keyword in blocked_keywords:
            if keyword in topic_lower:
                return False, f"Blocked keyword detected: '{keyword}'"
        
        return True, "Passed keyword check"


# Singleton instance
_guardrail_service = None


def get_guardrail_service() -> GuardrailService:
    """Get or create the guardrail service singleton."""
    global _guardrail_service
    if _guardrail_service is None:
        _guardrail_service = GuardrailService()
    return _guardrail_service
