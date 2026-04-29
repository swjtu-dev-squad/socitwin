"""使用Tweepy发布推文到X平台，支持dry-run模式"""

import logging
import time
from typing import Dict, Optional, Any
from datetime import datetime

import tweepy
from tweepy.errors import TweepyException


class XPublisher:
    """使用Tweepy发布推文到X平台"""

    MAX_TWEET_LENGTH = 280

    def __init__(self, api_key: str, api_key_secret: str,
                 access_token: str, access_token_secret: str,
                 **kwargs):
        self.dry_run = kwargs.get('dry_run', False)
        self.max_retries = kwargs.get('max_retries', 3)
        self.retry_delay = kwargs.get('retry_delay', 1.0)
        self.logger = logging.getLogger(__name__)

        if not all([api_key, api_key_secret, access_token, access_token_secret]):
            raise ValueError("所有认证参数都必须提供")

        try:
            self.client = tweepy.Client(
                consumer_key=api_key,
                consumer_secret=api_key_secret,
                access_token=access_token,
                access_token_secret=access_token_secret
            )
            self.logger.info("XPublisher初始化成功 (dry_run=%s)", self.dry_run)
        except Exception as e:
            self.logger.error("Tweepy客户端初始化失败: %s", str(e))
            raise TweepyException(f"Tweepy客户端初始化失败: {str(e)}")

    def _validate_tweet_text(self, text: str) -> str:
        """验证并截断推文文本"""
        if not text or not isinstance(text, str):
            raise ValueError("推文文本必须是非空字符串")
        text = text.strip()
        if not text:
            raise ValueError("推文文本不能为空或仅包含空白字符")

        if len(text) > self.MAX_TWEET_LENGTH:
            self.logger.warning("推文长度超过限制 (%d > %d)，将被截断", len(text), self.MAX_TWEET_LENGTH)
            if len(text) > self.MAX_TWEET_LENGTH:
                truncated = text[:self.MAX_TWEET_LENGTH - 3]
                last_boundary = max(
                    truncated.rfind('。'), truncated.rfind('.'),
                    truncated.rfind('！'), truncated.rfind('!'),
                    truncated.rfind('？'), truncated.rfind('?'),
                    truncated.rfind('，'), truncated.rfind(','),
                    truncated.rfind(' '), truncated.rfind('\n')
                )
                if last_boundary > self.MAX_TWEET_LENGTH * 0.7:
                    text = truncated[:last_boundary + 1] + "..."
                else:
                    text = truncated + "..."
        return text

    def _create_tweet_response(self, tweet_data: Optional[Dict] = None) -> Dict[str, Any]:
        """创建标准化的推文响应"""
        if tweet_data and 'data' in tweet_data:
            tweet = tweet_data['data']
            return {
                'id': tweet.get('id'),
                'text': tweet.get('text'),
                'created_at': tweet.get('created_at') or datetime.utcnow().isoformat(),
                'success': True,
                'dry_run': self.dry_run
            }
        return {
            'id': None,
            'text': None,
            'created_at': datetime.utcnow().isoformat(),
            'success': False,
            'dry_run': self.dry_run,
            'error': 'No tweet data received'
        }

    def _handle_api_error(self, error: TweepyException, attempt: int) -> bool:
        """处理API错误，决定是否重试"""
        error_msg = str(error)

        if any(n in error_msg.lower() for n in ['connection', 'timeout', 'network', 'socket']):
            self.logger.warning("网络错误 (尝试 %d/%d): %s", attempt, self.max_retries, error_msg)
            return True

        if 'rate limit' in error_msg.lower() or '429' in error_msg:
            self.logger.warning("速率限制 (尝试 %d/%d)，等待 %d 秒后重试", attempt, self.max_retries, self.retry_delay * 2)
            time.sleep(self.retry_delay * 2)
            return True

        if any(n in error_msg.lower() for n in ['auth', 'authenticate', '401', '403']):
            self.logger.error("认证错误: %s", error_msg)
            return False

        if attempt < self.max_retries:
            self.logger.warning("临时错误 (尝试 %d/%d): %s", attempt, self.max_retries, error_msg)
            return True

        return False

    def post_tweet(self, text: str) -> Dict[str, Any]:
        """发布推文到X平台"""
        validated_text = self._validate_tweet_text(text)
        self.logger.info("准备发布推文 (dry_run=%s, length=%d)", self.dry_run, len(validated_text))

        if self.dry_run:
            self.logger.info("Dry-run模式：跳过实际发布")
            return {
                'id': 'dry-run-simulated-id',
                'text': validated_text,
                'created_at': datetime.utcnow().isoformat(),
                'success': True,
                'dry_run': True,
                'message': 'Dry-run mode: tweet not actually posted'
            }

        for attempt in range(1, self.max_retries + 1):
            try:
                self.logger.debug("发布推文 (尝试 %d/%d)", attempt, self.max_retries)
                response = self.client.create_tweet(text=validated_text)
                self.logger.info("推文发布成功 (ID: %s, 长度: %d)", response.data['id'], len(validated_text))
                return self._create_tweet_response(response)
            except TweepyException as e:
                if not self._handle_api_error(e, attempt) or attempt == self.max_retries:
                    self.logger.error("推文发布失败 (尝试 %d/%d): %s", attempt, self.max_retries, str(e))
                    raise
                time.sleep(self.retry_delay)

        raise TweepyException(f"推文发布失败，已达到最大重试次数 ({self.max_retries})")

    def test_connection(self) -> bool:
        """测试与X平台的连接"""
        try:
            if self.dry_run:
                self.logger.info("Dry-run模式：连接测试跳过，返回成功")
                return True
            user = self.client.get_me()
            if user and user.data:
                self.logger.info("X平台连接测试成功 (用户: %s)", user.data.username)
                return True
            return False
        except Exception as e:
            self.logger.warning("X平台连接测试失败: %s", str(e))
            return False


if __name__ == "__main__":
    import os
    publisher = XPublisher(
        api_key=os.environ.get("X_API_KEY", ""),
        api_key_secret=os.environ.get("X_API_KEY_SECRET", ""),
        access_token=os.environ.get("X_ACCESS_TOKEN", ""),
        access_token_secret=os.environ.get("X_ACCESS_TOKEN_SECRET", ""),
        dry_run=True
    )
    publisher.test_connection()
