"""使用DeepSeek API分析观点和生成反驳论点"""

import logging
import time
from typing import List, Optional, Dict, Any
import re

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("openai library not installed. Please install with: pip install openai")


class LLMAnalyzer:
    """使用DeepSeek API分析观点和生成反驳"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
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

        self.logger.info(f"LLMAnalyzer initialized with base_url: {self.base_url}")

    def _call_api_with_retry(self, messages: List[Dict[str, str]], **kwargs) -> Optional[str]:
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model, messages=messages, **kwargs
                )
                if response.choices and response.choices[0].message.content:
                    content = response.choices[0].message.content.strip()
                    self.logger.debug(f"API call successful (attempt {attempt + 1})")
                    return content
                self.logger.warning(f"Empty response from API (attempt {attempt + 1})")

            except openai.APIConnectionError as e:
                self.logger.warning(f"API connection error (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise
            except openai.APIError as e:
                self.logger.error(f"API error (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise
            except Exception as e:
                self.logger.error(f"Unexpected error (attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise

        return None

    def analyze_majority_opinion(self, post_samples: List[str], topic_label: Optional[str] = None) -> str:
        """分析帖子样本，总结多数观点"""
        if not post_samples:
            raise ValueError("post_samples cannot be empty")

        valid_samples = [s for s in post_samples if s and s.strip()]
        if not valid_samples:
            raise ValueError("No valid text samples found in post_samples")

        self.logger.info(f"Analyzing majority opinion from {len(valid_samples)} samples")

        samples_text = "\n".join([f"- {s}" for s in valid_samples[:10]])

        if topic_label:
            clean_label = self._clean_topic_label(topic_label)
            prompt = f"""你是一名社交媒体分析师。请分析以下关于#{clean_label}的Twitter帖子样本，总结出大多数用户持有的核心观点和论据。

帖子样本：
{samples_text}

请用1-2句话总结多数观点，专注于核心主张而非细节。"""
        else:
            prompt = f"""你是一名社交媒体分析师。请分析以下Twitter帖子样本，总结出大多数用户持有的核心观点和论据。

帖子样本：
{samples_text}

请用1-2句话总结多数观点，专注于核心主张而非细节。"""

        messages = [
            {"role": "system", "content": "你是一名专业的社交媒体分析师，擅长从大量用户帖子中识别主流观点。"},
            {"role": "user", "content": prompt}
        ]

        try:
            result = self._call_api_with_retry(messages, temperature=0.3, max_tokens=200)
            if result:
                self.logger.info("Successfully analyzed majority opinion")
                return result
            raise RuntimeError("Failed to analyze majority opinion: API returned empty response")
        except Exception as e:
            self.logger.error(f"Failed to analyze majority opinion: {e}")
            raise RuntimeError(f"Failed to analyze majority opinion: {e}")

    def generate_counterargument(self, majority_opinion: str, topic_label: str) -> str:
        """生成针对多数观点的反驳论点"""
        if not majority_opinion or not majority_opinion.strip():
            raise ValueError("majority_opinion cannot be empty")
        if not topic_label or not topic_label.strip():
            raise ValueError("topic_label cannot be empty")

        self.logger.info(f"Generating counterargument for topic: {topic_label}")
        clean_label = self._clean_topic_label(topic_label)

        prompt = f"""你是一名普通中国网民。针对以下关于#{clean_label}的多数观点，请生成一个反驳论点，并且口语化自然地像网友聊天一样，生成适合作为Twitter推文发布。

多数观点：
{majority_opinion}

要求：
1. 论点清晰有力，针对多数观点的核心假设
2. 适合Twitter平台，长度不超过280字符
3. 包含话题标签 #{clean_label}
4. 语气：理性、有说服力，不人身攻击
5. 可考虑提供替代视角或未被考虑的因素

请直接输出反驳论点，不要添加任何解释或前缀。"""

        messages = [
            {"role": "system", "content": "你是一名善于辩论的思想家，擅长从不同角度分析问题并提出有力的反驳论点。"},
            {"role": "user", "content": prompt}
        ]

        try:
            result = self._call_api_with_retry(messages, temperature=0.7, max_tokens=150)
            if result:
                if f"#{clean_label}" not in result:
                    result = f"{result} #{clean_label}"
                result = self._clean_and_truncate_tweet(result, 280)
                self.logger.info(f"Successfully generated counterargument ({len(result)} chars)")
                return result
            raise RuntimeError("Failed to generate counterargument: API returned empty response")
        except Exception as e:
            self.logger.error(f"Failed to generate counterargument: {e}")
            raise RuntimeError(f"Failed to generate counterargument: {e}")

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
                {"role": "user", "content": "Say 'Hello' if you can hear me."}
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
            self.logger.error(f"API connection test failed: {e}")
            return False


if __name__ == "__main__":
    import os
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if api_key:
        analyzer = LLMAnalyzer(api_key=api_key)
        analyzer.test_api_connection()
