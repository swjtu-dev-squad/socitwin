"""
LLM Evaluator - LLM-based evaluation utilities for OASIS metrics

This module provides LLM evaluation capabilities for analyzing agent behavior,
particularly for calculating group polarization by comparing initial and current opinions.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMEvaluator:
    """
    LLM-based evaluation utilities

    Uses DeepSeek API to evaluate opinion shifts and polarization in agent behavior.
    """

    def __init__(self):
        """Initialize LLM evaluator with configured API"""
        settings = get_settings()

        # Use configured OpenAI API settings (for lab proxy or other providers)
        # Fall back to DeepSeek specific settings if OpenAI settings not configured
        api_key = settings.OPENAI_API_KEY or settings.DEEPSEEK_API_KEY
        base_url = settings.OPENAI_BASE_URL or "https://api.deepseek.com"

        if not api_key:
            logger.warning("No API key configured (OPENAI_API_KEY or DEEPSEEK_API_KEY). LLM evaluation will fail.")

        # Initialize async client with configured settings
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )

        # Smart fallback: POLARIZATION_LLM_MODEL → OASIS_MODEL_TYPE → error
        self.model = (
            settings.POLARIZATION_LLM_MODEL or
            settings.OASIS_MODEL_TYPE or
            "deepseek-chat"  # Last resort fallback
        )
        self.temperature = getattr(settings, 'POLARIZATION_LLM_TEMPERATURE', 0.3)
        self.timeout = 30  # seconds

        logger.info(f"LLM Evaluator initialized with model: {self.model}, base_url: {base_url}")

    async def evaluate_polarization(
        self,
        initial_opinion: str,
        current_opinion: str,
        context: str = "social media discussion"
    ) -> Dict[str, Any]:
        """
        Evaluate polarization shift using LLM

        Compares initial and current opinions to determine direction and magnitude of change.

        Args:
            initial_opinion: Agent's opinion at the beginning
            current_opinion: Agent's current opinion
            context: Discussion context for the LLM

        Returns:
            Dictionary with keys:
                - direction: PolarizationDirection enum value
                - magnitude: float between 0.0 and 1.0
                - reasoning: str with LLM explanation

        Raises:
            LLMAPIError: If LLM API call fails after retries
        """
        prompt = self._build_polarization_prompt(
            initial_opinion,
            current_opinion,
            context
        )

        try:
            # Call LLM with timeout
            response = await asyncio.wait_for(
                self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a neutral political analyst evaluating opinion shifts. You must respond with valid JSON only."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=self.temperature,
                    max_tokens=200,
                    response_format={"type": "json_object"}
                ),
                timeout=self.timeout
            )

            content = (response.choices[0].message.content or "").strip()
            logger.debug(f"LLM response: {content}")

            # Parse JSON response
            result = self._parse_llm_response(content)

            # Validate and normalize
            result['magnitude'] = max(0.0, min(1.0, result['magnitude']))
            result['direction'] = self._normalize_direction(result['direction'])

            logger.info(f"Polarization evaluation completed: direction={result['direction']}, magnitude={result['magnitude']}")

            return result

        except asyncio.TimeoutError as e:
            logger.error(f"LLM evaluation timeout after {self.timeout}s: {e}")
            raise LLMAPIError(f"LLM evaluation timeout: {str(e)}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            raise LLMAPIError(f"Invalid JSON response: {str(e)}")

        except Exception as e:
            logger.error(f"LLM evaluation failed: {e}")
            raise LLMAPIError(f"LLM API call failed: {str(e)}")

    def _build_polarization_prompt(
        self,
        initial_opinion: str,
        current_opinion: str,
        context: str
    ) -> str:
        """Build polarization evaluation prompt"""
        # Truncate opinions if too long
        initial = initial_opinion[:500] if initial_opinion else "No opinion"
        current = current_opinion[:500] if current_opinion else "No opinion"

        prompt = f"""
You are analyzing opinion shifts in social media discussions.

Initial Opinion: {initial}

Current Opinion: {current}

Context: {context}

Evaluate the polarization:
1. Direction: Choose one of these exact values:
   - EXTREME_CONSERVATIVE (became much more conservative)
   - MODERATE_CONSERVATIVE (became somewhat more conservative)
   - NEUTRAL (no clear direction or balanced)
   - MODERATE_PROGRESSIVE (became somewhat more progressive)
   - EXTREME_PROGRESSIVE (became much more progressive)

2. Magnitude: Score from 0.0 (no shift) to 1.0 (extreme shift)

3. Reasoning: Brief explanation (max 100 words)

Return ONLY valid JSON in this exact format:
{{
    "direction": "NEUTRAL",
    "magnitude": 0.3,
    "reasoning": "Brief explanation here"
}}
"""
        return prompt

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """Parse and validate LLM JSON response"""
        try:
            # Try to extract JSON from response (in case of extra text)
            if "```json" in content:
                # Extract JSON from code block
                start = content.find("{")
                end = content.rfind("}") + 1
                json_str = content[start:end]
            else:
                json_str = content

            result = json.loads(json_str)

            # Validate required fields
            if 'direction' not in result or 'magnitude' not in result:
                raise ValueError("Missing required fields in LLM response")

            return result

        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
            # Return default neutral response
            return {
                'direction': 'NEUTRAL',
                'magnitude': 0.0,
                'reasoning': f'Parse error: {str(e)}'
            }

    def _normalize_direction(self, direction: str) -> str:
        """Normalize direction string to valid enum value"""
        direction_map = {
            'extreme_conservative': 'EXTREME_CONSERVATIVE',
            'moderate_conservative': 'MODERATE_CONSERVATIVE',
            'neutral': 'NEUTRAL',
            'moderate_progressive': 'MODERATE_PROGRESSIVE',
            'extreme_progressive': 'EXTREME_PROGRESSIVE',
        }

        normalized = direction_map.get(direction.lower().strip())
        if not normalized:
            logger.warning(f"Unknown direction '{direction}', defaulting to NEUTRAL")
            return 'NEUTRAL'

        return normalized


class LLMAPIError(Exception):
    """LLM API call failed"""
    pass


# ============================================================================
# Singleton Instance
# ============================================================================

_llm_evaluator: Optional[LLMEvaluator] = None


def get_llm_evaluator() -> LLMEvaluator:
    """
    Get LLM evaluator singleton instance

    Returns:
        LLMEvaluator instance
    """
    global _llm_evaluator

    if _llm_evaluator is None:
        _llm_evaluator = LLMEvaluator()
        logger.info("LLM Evaluator singleton created")

    return _llm_evaluator


def reset_llm_evaluator():
    """Reset LLM evaluator singleton (mainly for testing)"""
    global _llm_evaluator
    _llm_evaluator = None
    logger.info("LLM Evaluator singleton reset")
