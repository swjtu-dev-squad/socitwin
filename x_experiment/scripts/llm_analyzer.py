"""使用DeepSeek API分析观点和生成多角度观点"""

import logging
import re
import time
import warnings
from typing import Any, Dict, List, Optional, Union

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("openai library not installed. Please install with: pip install openai")

from prompt_loader import PromptContext, PromptLoader


class LLMAnalyzer:
    """使用DeepSeek API分析观点和生成多角度观点"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com",
                 prompt_loader: Optional[PromptLoader] = None):
        if not OPENAI_AVAILABLE:
            raise ImportError("openai library is required. Install with: pip install openai")
        if not api_key or not isinstance(api_key, str):
            raise ValueError("API key must be a non-empty string")

        self.api_key = api_key
        self.base_url = base_url
        self.logger = logging.getLogger(__name__)
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model = "deepseek-chat"
        self.max_retries = 3
        self.retry_delay = 2
        self.prompt_loader = prompt_loader or PromptLoader()

        self.logger.info("LLMAnalyzer initialized with base_url: %s", self.base_url)

    def _call_api_with_retry(
        self,
        messages_or_context: Union[List[Dict[str, str]], PromptContext],
        **kwargs: Any,
    ) -> Optional[str]:
        """调用 API 并重试，接受 raw messages 或 PromptContext"""
        if isinstance(messages_or_context, PromptContext):
            ctx = messages_or_context
            messages = ctx.messages
            kwargs = {**ctx.model_params, **kwargs}
        else:
            messages = messages_or_context

        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model, messages=messages, **kwargs
                )
                if response.choices and response.choices[0].message.content:
                    content = response.choices[0].message.content.strip()
                    self.logger.debug("API call successful (attempt %d)", attempt + 1)
                    return content
                self.logger.warning("Empty response from API (attempt %d)", attempt + 1)

            except openai.APIConnectionError as e:
                self.logger.warning("API connection error (attempt %d): %s", attempt + 1, e)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise
            except openai.APIError as e:
                self.logger.error("API error (attempt %d): %s", attempt + 1, e)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise
            except Exception as e:
                self.logger.error("Unexpected error (attempt %d): %s", attempt + 1, e)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise

        return None

    def analyze_majority_opinion(self, post_samples: List[str],
                                 topic_label: Optional[str] = None) -> str:
        """分析帖子样本，总结多数观点"""
        if not post_samples:
            raise ValueError("post_samples cannot be empty")

        valid_samples = [s for s in post_samples if s and s.strip()]
        if not valid_samples:
            raise ValueError("No valid text samples found in post_samples")

        self.logger.info("Analyzing majority opinion from %d samples", len(valid_samples))

        samples_text = "\n".join([f"- {s}" for s in valid_samples[:10]])
        topic_label = topic_label or "trending"

        try:
            ctx = self.prompt_loader.render(
                "analyze_majority",
                topic_label=topic_label,
                samples_text=samples_text,
            )
            result = self._call_api_with_retry(ctx)
            if result:
                self.logger.info("Successfully analyzed majority opinion")
                return result
            raise RuntimeError("Failed to analyze majority opinion: API returned empty response")
        except Exception as e:
            self.logger.error("Failed to analyze majority opinion: %s", e)
            raise RuntimeError(f"Failed to analyze majority opinion: {e}")

    def generate_perspective(self, majority_opinion: str, topic_label: str,
                             perspective: str = "counterargument") -> str:
        """针对多数观点，以指定角度生成观点内容

        Args:
            majority_opinion: 多数观点文本
            topic_label: 话题标签
            perspective: 角度 key，可选值见 prompt_loader.list_perspectives()

        Returns:
            生成的观点文本（已截断至 280 字符以内）
        """
        if not majority_opinion or not majority_opinion.strip():
            raise ValueError("majority_opinion cannot be empty")
        if not topic_label or not topic_label.strip():
            raise ValueError("topic_label cannot be empty")

        self.logger.info("Generating '%s' perspective for topic: %s", perspective, topic_label)
        clean_label = self._clean_topic_label(topic_label)

        try:
            ctx = self.prompt_loader.render(
                "generate_perspective",
                perspective=perspective,
                topic_label=clean_label,
                majority_opinion=majority_opinion,
            )
            result = self._call_api_with_retry(ctx)
            if result:
                result = self._clean_and_truncate_tweet(result, 280)
                self.logger.info("Successfully generated '%s' perspective (%d chars)",
                                 perspective, len(result))
                return result
            raise RuntimeError("Failed to generate perspective: API returned empty response")
        except Exception as e:
            self.logger.error("Failed to generate perspective '%s': %s", perspective, e)
            raise RuntimeError(f"Failed to generate perspective '{perspective}': {e}")

    def generate_counterargument(self, majority_opinion: str, topic_label: str) -> str:
        """[已废弃] 生成反驳论点。请使用 generate_perspective(..., perspective='counterargument')"""
        warnings.warn(
            "generate_counterargument() is deprecated. "
            "Use generate_perspective(majority_opinion, topic_label, "
            "perspective='counterargument') instead.",
            DeprecationWarning, stacklevel=2,
        )
        return self.generate_perspective(
            majority_opinion, topic_label, perspective="counterargument"
        )

    def _clean_topic_label(self, topic_label: str) -> str:
        """清理话题标签，使其适合作为Twitter话题标签"""
        cleaned = re.sub(r'[^\w\s#]', '', topic_label)
        words = cleaned.strip().split()
        cleaned = ''.join(word.title() for word in words) if len(words) > 1 else cleaned.strip()
        if cleaned and not cleaned[0].isalpha():
            cleaned = "Topic" + cleaned
        return cleaned

    def _clean_and_truncate_tweet(self, text: str, max_length: int = 280) -> str:
        """清理推文文本并确保不超过最大长度"""
        cleaned = re.sub(r'\s+', ' ', text.strip())
        if len(cleaned) > max_length:
            sentences = re.split(r'[.!?]', cleaned)
            truncated = ""
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                potential = f"{truncated} {sentence}.".strip()
                if len(potential) <= max_length:
                    truncated = potential
                else:
                    break
            if not truncated:
                words = cleaned.split()
                truncated = ""
                for word in words:
                    potential = f"{truncated} {word}".strip()
                    if len(potential) <= max_length - 3:
                        truncated = potential
                    else:
                        break
                if truncated and len(truncated) < len(cleaned):
                    truncated += "..."
            cleaned = truncated
        return cleaned[:max_length]

    def test_api_connection(self) -> bool:
        """测试API连接"""
        try:
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'Hello' if you can hear me."},
            ]
            response = self.client.chat.completions.create(
                model=self.model, messages=messages, max_tokens=10
            )
            if response.choices and response.choices[0].message.content:
                self.logger.info("API connection test successful")
                return True
            self.logger.warning("API connection test returned empty response")
            return False
        except Exception as e:
            self.logger.error("API connection test failed: %s", e)
            return False


if __name__ == "__main__":
    import os
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if api_key:
        analyzer = LLMAnalyzer(api_key=api_key)
        analyzer.test_api_connection()
