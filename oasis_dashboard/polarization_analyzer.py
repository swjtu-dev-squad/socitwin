"""
Polarization Analyzer for OASIS Dashboard

This module provides LLM-based polarization analysis for social media simulations.
It analyzes post content to determine stance positions and calculates polarization metrics.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
import json
import logging
import os
import re
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from camel.messages import BaseMessage
from camel.types import OpenAIBackendRole

from oasis_dashboard.context import ModelRuntimeSpec, build_shared_model

logger = logging.getLogger(__name__)


class PolarizationAnalyzer:
    """
    极化率分析器

    功能：
    - 智能采样代表性帖子
    - 批量LLM立场分析
    - 计算多种极化指标
    - 缓存分析结果
    """

    def __init__(
        self,
        db_path: str,
        model_spec: ModelRuntimeSpec | list[ModelRuntimeSpec],
        topic: str,
        sample_size: int = 30,
        cache_size: int = 500,
    ):
        """
        初始化极化率分析器

        Args:
            db_path: SQLite数据库路径
            model_spec: LLM模型运行配置
            topic: 分析主题（如"地球是平的"）
            sample_size: 每次采样的帖子数
            cache_size: 缓存最近N条分析结果
        """
        self.db_path = db_path
        self.model_spec = self._prepare_model_spec_for_analysis(model_spec)
        self.topic = topic
        self.sample_size = sample_size
        self.cache_size = cache_size
        self.analysis_timeout_s = float(
            os.environ.get("OASIS_POLARIZATION_TIMEOUT", "30")
        )
        self.request_timeout_s = float(
            os.environ.get("OASIS_POLARIZATION_REQUEST_TIMEOUT", "12")
        )
        self.max_retries = int(
            os.environ.get("OASIS_POLARIZATION_MAX_RETRIES", "3")
        )
        self.chunk_size = max(
            1,
            int(os.environ.get("OASIS_POLARIZATION_CHUNK_SIZE", "8")),
        )

        # 初始化模型
        resolved_model = build_shared_model(self.model_spec)
        self.model = resolved_model.model

        # 状态追踪
        self.last_analyzed_post_id = 0
        self.history: List[float] = []  # 最近的分析结果用于降级
        self.last_result: Dict = {}

        # 初始化数据库缓存表
        self._init_cache_table()

        logger.info(
            f"✅ 极化率分析器已初始化: topic={topic}, sample_size={sample_size}"
        )

    def _init_cache_table(self):
        """初始化数据库缓存表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 创建缓存表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS polarization_cache (
                    post_id INTEGER PRIMARY KEY,
                    stance_score REAL NOT NULL,
                    confidence REAL DEFAULT 0.8,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    topic TEXT NOT NULL
                )
            """)

            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_polarization_topic_time
                ON polarization_cache(topic, analyzed_at)
            """)

            # 启用WAL模式以提高并发性能
            cursor.execute("PRAGMA journal_mode=WAL")

            conn.commit()
            conn.close()

            logger.debug("数据库缓存表已初始化")

        except Exception as e:
            logger.error(f"初始化缓存表失败: {e}")

    async def analyze(self) -> Dict:
        """
        执行极化率分析（主入口）

        Returns:
            {
                'polarization': float,  # 综合极化分数 0-1
                'std': float,          # 标准差极化率
                'r_metric': float,     # R指标极化率
                'bimodality': float,    # 双峰系数
                'sample_size': int,    # 分析的帖子数
            }
        """
        try:
            # 1. 获取未分析的新帖子
            new_posts = self._get_new_posts()

            # 2. 如果没有新帖子，返回缓存结果
            if not new_posts:
                logger.debug("没有新帖子，返回缓存结果")
                return self.get_cached_result()

            # 3. 性能保护：设置超时
            try:
                result = await asyncio.wait_for(
                    self._analyze_posts(new_posts),
                    timeout=self.analysis_timeout_s,
                )
                self.last_result = result
                return result

            except asyncio.TimeoutError:
                logger.warning("极化分析超时，尝试启发式降级")
                fallback_stances = self._heuristic_stance_batch(new_posts)
                if fallback_stances:
                    self._save_analysis_results(
                        [p["post_id"] for p in new_posts],
                        fallback_stances,
                        confidence=0.35,
                    )
                    result = self._calculate_polarization_metrics(fallback_stances)
                    result["degraded"] = True
                    result["source"] = "heuristic_timeout_fallback"
                    self.last_result = result
                    return result
                return self.get_cached_result()

        except Exception as e:
            logger.error(f"极化率分析失败: {e}，使用历史平均值")
            return self._get_historical_fallback()

    async def _analyze_posts(self, posts: List[Dict]) -> Dict:
        """
        分析帖子列表并计算极化率

        Args:
            posts: 帖子列表

        Returns:
            极化率指标字典
        """
        # 1. 批量LLM立场分析（含分块降级）
        logger.debug(f"开始分析 {len(posts)} 条帖子...")
        stances = await self._analyze_with_chunk_fallback(posts)

        if not stances:
            logger.warning("LLM分析返回空结果，使用启发式降级")
            stances = self._heuristic_stance_batch(posts)
            if not stances:
                return self._get_historical_fallback()
            confidence = 0.35
            degraded = True
            source = "heuristic_empty_llm_fallback"
        else:
            confidence = 0.8
            degraded = False
            source = "llm"

        # 2. 保存分析结果到缓存
        self._save_analysis_results(
            [p['post_id'] for p in posts],
            stances,
            confidence=confidence,
        )

        # 3. 计算极化率
        result = self._calculate_polarization_metrics(stances)

        # 4. 更新历史记录
        self.history.append(result['polarization'])
        if len(self.history) > 100:
            self.history.pop(0)

        logger.info(
            f"✅ 极化率分析完成: {result['polarization']:.3f} "
            f"(N={result['sample_size']}, std={result['std']:.3f})"
        )
        if degraded:
            result["degraded"] = True
        result["source"] = source

        return result

    async def _analyze_with_chunk_fallback(self, posts: List[Dict]) -> List[float]:
        """
        先整批分析，失败后按 chunk 分块分析，避免单次大请求整体失败。
        """
        full_batch = await self._analyze_batch(posts)
        if full_batch:
            return self._normalize_stance_count(full_batch, len(posts))

        logger.warning(
            "整批极化分析失败，切换分块模式（chunk_size=%s）",
            self.chunk_size,
        )
        merged: List[float] = []
        for idx in range(0, len(posts), self.chunk_size):
            chunk = posts[idx: idx + self.chunk_size]
            chunk_stances = await self._analyze_batch(chunk)
            if not chunk_stances:
                chunk_stances = self._heuristic_stance_batch(chunk)
                if chunk_stances:
                    logger.warning(
                        "分块 %s-%s 使用启发式降级",
                        idx,
                        idx + len(chunk) - 1,
                    )
            if not chunk_stances:
                logger.warning(
                    "分块 %s-%s 仍失败，填充中立值",
                    idx,
                    idx + len(chunk) - 1,
                )
                chunk_stances = [0.5] * len(chunk)
            merged.extend(
                self._normalize_stance_count(chunk_stances, len(chunk))
            )
        return self._normalize_stance_count(merged, len(posts))

    def _get_new_posts(self) -> List[Dict]:
        """
        获取未分析的新帖子

        Returns:
            帖子列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    p.post_id,
                    p.content,
                    p.num_likes
                FROM post p
                LEFT JOIN polarization_cache pc
                    ON p.post_id = pc.post_id
                    AND pc.topic = ?
                WHERE pc.post_id IS NULL
                ORDER BY p.post_id DESC
                LIMIT ?
            """, (self.topic, self.sample_size))

            posts = []
            for row in cursor.fetchall():
                posts.append({
                    'post_id': row[0],
                    'content': row[1],
                    'num_likes': row[2] or 0,
                })

            conn.close()

            if posts:
                # 更新最后分析的post_id
                self.last_analyzed_post_id = max(p['post_id'] for p in posts)
                logger.debug(f"获取到 {len(posts)} 条新帖子")

            return posts

        except Exception as e:
            logger.error(f"获取新帖子失败: {e}")
            return []

    async def _analyze_batch(self, posts: List[Dict]) -> List[float]:
        """
        批量分析帖子立场（1次LLM调用）

        Args:
            posts: 帖子列表

        Returns:
            立场分数列表 (0-1)
        """
        if not posts:
            return []

        # 1. 构建批量prompt
        post_texts = "\n".join([
            f"{i+1}. {self._truncate_text(p['content'], 200)}"
            for i, p in enumerate(posts)
        ])

        prompt = f"""You are analyzing social media posts about "{self.topic}".

For each post, determine the stance on a scale of 0-1:
- 0.0: Strongly opposed/against
- 0.3: Leaning opposed
- 0.5: Neutral/mixed
- 0.7: Leaning supportive
- 1.0: Strongly supportive

Posts:
{post_texts}

IMPORTANT: Return ONLY a valid JSON array of stance scores (numbers only).
Example format: [0.2, 0.7, 0.5, 0.3, 0.8]

Your response:"""

        # 2. 调用LLM（带重试）
        # 注意：CAMEL-AI 模型后端使用 run()/arun() 方法，需要 OpenAI 格式消息
        max_retries = self.max_retries
        for attempt in range(max_retries):
            try:
                # 创建 BaseMessage 并转换为 OpenAI 格式
                base_message = BaseMessage.make_user_message(
                    role_name="user",
                    content=prompt
                )
                openai_message = base_message.to_openai_message(
                    OpenAIBackendRole.USER
                )

                # 优先使用异步方法，如果不可用则用线程池包装同步方法
                if hasattr(self.model, 'arun'):
                    response = await asyncio.wait_for(
                        self.model.arun([openai_message]),
                        timeout=self.request_timeout_s,
                    )
                elif hasattr(self.model, 'run'):
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            self.model.run,
                            [openai_message]
                        ),
                        timeout=self.request_timeout_s,
                    )
                else:
                    raise AttributeError("模型不支持 arun() 或 run() 方法")

                result_text = self._extract_response_text(response)
                if not result_text:
                    logger.warning(
                        f"LLM返回空内容（尝试 {attempt+1}/{max_retries}）"
                    )
                    continue

                # 记录原始响应用于调试
                logger.debug(f"LLM 原始响应 (前200字符): {result_text[:200]}")

                stances = self._parse_stance_json(result_text, len(posts))

                if stances:
                    return stances

                logger.warning(f"LLM解析失败（尝试 {attempt+1}/{max_retries}），响应: {result_text[:100]}")

            except Exception as e:
                logger.warning(f"LLM调用失败（尝试 {attempt+1}/{max_retries}）: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)  # 短暂等待后重试

        # 3. 所有重试失败，返回空列表，交给上层分块/启发式兜底
        logger.error("所有LLM重试失败")
        return []

    def _parse_stance_json(self, text: str, expected_count: int) -> List[float]:
        """
        解析LLM返回的JSON立场分数（增强容错）

        Args:
            text: LLM响应文本
            expected_count: 期望的立场数量

        Returns:
            立场分数列表
        """
        # 尝试多种解析策略
        strategies = [
            self._parse_as_json_array,
            self._parse_as_number_list,
            self._extract_numbers_from_text,
        ]

        for strategy in strategies:
            try:
                stances = strategy(text, expected_count)
                if stances:
                    normalized = self._normalize_stance_count(
                        stances, expected_count
                    )
                    logger.debug(
                        "成功使用 %s 解析并归一化到 %s 个立场",
                        strategy.__name__,
                        len(normalized),
                    )
                    return normalized
            except Exception as e:
                logger.debug(f"{strategy.__name__} 失败: {e}")
                continue

        logger.error(f"所有解析策略失败，原始文本: {text[:200]}")
        return []

    def _parse_as_json_array(self, text: str, expected_count: int) -> List[float]:
        """策略1: 解析为标准 JSON 数组"""
        # 处理可能的 markdown 代码块
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        # 查找 JSON 数组（使用非贪婪匹配）
        matches = re.findall(r'\[[\s\S]*?\]', text)
        for json_str in matches:
            try:
                data = json.loads(json_str)
                if isinstance(data, list):
                    stances = []
                    for item in data:
                        if isinstance(item, (int, float)):
                            stance = float(item)
                            # 归一化到 0-1 范围
                            stance = max(0.0, min(1.0, stance))
                            stances.append(stance)

                    if stances:
                        return stances
            except json.JSONDecodeError:
                continue

        raise ValueError("未找到有效的 JSON 数组")

    def _parse_as_number_list(self, text: str, expected_count: int) -> List[float]:
        """策略2: 解析逗号分隔的数字列表"""
        # 提取所有数字（包括小数）
        numbers = re.findall(r'\d+\.?\d*', text)

        if numbers:
            stances = []
            for num_str in numbers:
                try:
                    num = float(num_str)
                    # 归一化到 0-1 范围
                    if num > 1:
                        num = num / 10.0  # 假设是 1-10 的评分
                    num = max(0.0, min(1.0, num))
                    stances.append(num)
                except ValueError:
                    continue

            if stances:
                return stances

        raise ValueError("未能提取足够的数字")

    def _extract_numbers_from_text(self, text: str, expected_count: int) -> List[float]:
        """策略3: 从文本中提取所有可能的分数"""
        # 查找 "0.0", "1.0", "0.5" 等模式
        pattern = r'\b0?\.\d+\b|\b[01]\.0\b'
        matches = re.findall(pattern, text)

        if matches:
            stances = []
            for match in matches:
                try:
                    stance = float(match)
                    stance = max(0.0, min(1.0, stance))
                    stances.append(stance)
                except ValueError:
                    continue

            if stances:
                return stances

        raise ValueError("未能从文本中提取有效分数")

    @staticmethod
    def _normalize_stance_count(
        stances: List[float], expected_count: int
    ) -> List[float]:
        """将分数数量归一化到预期长度，避免因数量不一致整批失败。"""
        cleaned = [max(0.0, min(1.0, float(s))) for s in stances]
        if len(cleaned) >= expected_count:
            return cleaned[:expected_count]

        fill_value = (
            sum(cleaned) / len(cleaned)
            if cleaned
            else 0.5
        )
        return cleaned + [fill_value] * (expected_count - len(cleaned))

    @staticmethod
    def _extract_response_text(response: Any) -> str:
        """兼容不同后端响应格式，尽量提取可解析文本。"""
        choices = getattr(response, "choices", None) or []
        if not choices:
            return ""

        message = getattr(choices[0], "message", None)
        if message is None:
            return ""

        content = getattr(message, "content", "")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            if parts:
                return "\n".join(parts)

        # 某些模型会把关键信息放在 tool call 的 arguments 里
        tool_calls = getattr(message, "tool_calls", None) or []
        for tool_call in tool_calls:
            func = getattr(tool_call, "function", None)
            if func is None:
                continue
            arguments = getattr(func, "arguments", None)
            if isinstance(arguments, str) and arguments.strip():
                return arguments.strip()

        return ""

    @staticmethod
    def _prepare_model_spec_for_analysis(
        model_spec: ModelRuntimeSpec | list[ModelRuntimeSpec],
    ) -> ModelRuntimeSpec | list[ModelRuntimeSpec]:
        """
        极化分析只需要稳定纯文本输出，禁用 tool-calling 避免空响应。
        """
        specs = model_spec if isinstance(model_spec, list) else [model_spec]
        patched_specs: List[ModelRuntimeSpec] = []
        for spec in specs:
            config = dict(spec.model_config_dict or {})
            config.pop("tool_choice", None)
            # 分析任务更适合低温，提升可解析性
            config.setdefault("temperature", 0.2)
            patched_specs.append(
                replace(spec, model_config_dict=config)
            )

        if isinstance(model_spec, list):
            return patched_specs
        return patched_specs[0]

    def _calculate_polarization_metrics(self, stances: List[float]) -> Dict:
        """
        计算多种极化指标

        Args:
            stances: 立场分数列表

        Returns:
            极化率指标字典
        """
        if not stances:
            return {
                'polarization': 0.0,
                'std': 0.0,
                'r_metric': 0.0,
                'bimodality': 0.0,
                'sample_size': 0,
            }

        stances_arr = np.array(stances)

        # 1. 标准差（观点分散度）
        std = float(np.std(stances_arr))

        # 2. R指标（两端聚集程度）
        extreme_ratio = float(np.mean([abs(s - 0.5) for s in stances_arr]) * 2)

        # 3. 双峰系数（分布形态）
        bimodality = 0.0
        if len(stances) >= 10:
            try:
                from scipy import stats
                gamma1 = stats.skew(stances_arr)  # 偏度
                kappa = stats.kurtosis(stances_arr)  # 峰度
                bimodality = (std**2 + gamma1**2) / (kappa + 3)
                bimodality = max(0.0, min(1.0, abs(bimodality)))
            except ImportError:
                logger.warning("scipy未安装，跳过双峰系数计算")
            except Exception as e:
                logger.warning(f"计算双峰系数失败: {e}")

        # 4. 综合极化分数（加权平均）
        polarization = (
            0.4 * std +
            0.4 * extreme_ratio +
            0.2 * bimodality
        )
        polarization = max(0.0, min(1.0, polarization))

        return {
            'polarization': polarization,
            'std': std,
            'r_metric': extreme_ratio,
            'bimodality': bimodality,
            'sample_size': len(stances),
        }

    def _save_analysis_results(
        self,
        post_ids: List[int],
        stances: List[float],
        confidence: float = 0.8,
    ):
        """
        保存分析结果到数据库缓存

        Args:
            post_ids: 帖子ID列表
            stances: 立场分数列表
        """
        if not post_ids or not stances:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            now = datetime.now().isoformat()

            for post_id, stance in zip(post_ids, stances):
                cursor.execute("""
                    INSERT OR REPLACE INTO polarization_cache
                    (post_id, stance_score, confidence, analyzed_at, topic)
                    VALUES (?, ?, ?, ?, ?)
                """, (post_id, stance, confidence, now, self.topic))

            conn.commit()

            # 清理旧缓存（保留最近N条）
            self._prune_cache(cursor)

            conn.close()

            logger.debug(f"已保存 {len(post_ids)} 条分析结果到缓存")

        except Exception as e:
            logger.error(f"保存分析结果失败: {e}")

    def _prune_cache(self, cursor: sqlite3.Cursor):
        """清理缓存，保留最近N条"""
        try:
            cursor.execute("""
                DELETE FROM polarization_cache
                WHERE post_id NOT IN (
                    SELECT post_id FROM polarization_cache
                    WHERE topic = ?
                    ORDER BY analyzed_at DESC
                    LIMIT ?
                )
                AND topic = ?
            """, (self.topic, self.cache_size, self.topic))

            logger.debug(f"缓存已清理，保留最近 {self.cache_size} 条")

        except Exception as e:
            logger.warning(f"清理缓存失败: {e}")

    def get_cached_result(self) -> Dict:
        """
        获取缓存的分析结果

        Returns:
            极化率指标字典
        """
        if self.last_result:
            return self.last_result

        cached_stances = self._load_cached_stances()
        if cached_stances:
            result = self._calculate_polarization_metrics(cached_stances)
            result["cached"] = True
            result["source"] = "db_cache"
            return result

        # 如果有历史数据，返回平均值
        if self.history:
            avg_pol = sum(self.history) / len(self.history)
            return {
                'polarization': avg_pol,
                'std': 0.0,
                'r_metric': 0.0,
                'bimodality': 0.0,
                'sample_size': 0,
                'cached': True,
            }

        # 默认返回0
        return {
            'polarization': 0.0,
            'std': 0.0,
            'r_metric': 0.0,
            'bimodality': 0.0,
            'sample_size': 0,
            'cached': True,
            'source': 'empty_cache',
        }

    def _get_historical_fallback(self) -> Dict:
        """
        获取历史平均值作为降级策略

        Returns:
            极化率指标字典
        """
        if self.history:
            avg_pol = sum(self.history) / len(self.history)
            logger.info(f"使用历史平均值: {avg_pol:.3f}")
            return {
                'polarization': avg_pol,
                'std': 0.0,
                'r_metric': 0.0,
                'bimodality': 0.0,
                'sample_size': 0,
                'degraded': True,
                'source': 'history',
            }

        cached_stances = self._load_cached_stances()
        if cached_stances:
            result = self._calculate_polarization_metrics(cached_stances)
            result["degraded"] = True
            result["source"] = "db_cache_fallback"
            return result

        logger.warning("无历史数据，返回默认值0")
        return {
            'polarization': 0.0,
            'std': 0.0,
            'r_metric': 0.0,
            'bimodality': 0.0,
            'sample_size': 0,
            'error': True,
            'source': 'hard_zero_fallback',
        }

    def _load_cached_stances(self, limit: int = 100) -> List[float]:
        """从缓存表读取最近的立场分数。"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT stance_score
                FROM polarization_cache
                WHERE topic = ?
                ORDER BY analyzed_at DESC
                LIMIT ?
                """,
                (self.topic, limit),
            )
            rows = cursor.fetchall()
            conn.close()
            return [float(row[0]) for row in rows if row and row[0] is not None]
        except Exception as e:
            logger.warning(f"读取极化缓存失败: {e}")
            return []

    def _heuristic_stance_batch(self, posts: List[Dict]) -> List[float]:
        """无需LLM的启发式估计，用于超时/空响应时保底。"""
        stances: List[float] = []
        for post in posts:
            text = str(post.get("content") or "")
            likes = int(post.get("num_likes") or 0)
            stances.append(self._heuristic_stance_from_text(text, likes))
        return stances

    @staticmethod
    def _heuristic_stance_from_text(text: str, likes: int = 0) -> float:
        normalized = text.lower()
        support_words = [
            "support", "agree", "advocate", "promote", "progressive",
            "sustainability", "renewable", "equity", "justice",
            "inclusive", "solidarity", "champion", "must",
        ]
        oppose_words = [
            "oppose", "against", "reject", "deny", "harmful",
            "stifle", "overreach", "radical", "ban", "cannot",
        ]

        support_hits = sum(1 for w in support_words if w in normalized)
        oppose_hits = sum(1 for w in oppose_words if w in normalized)

        score = 0.5 + 0.08 * (support_hits - oppose_hits)
        score += min(0.08, likes * 0.01)
        return max(0.0, min(1.0, score))

    @staticmethod
    def _truncate_text(text: str, max_length: int) -> str:
        """
        截断文本到指定长度

        Args:
            text: 原始文本
            max_length: 最大长度

        Returns:
            截断后的文本
        """
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
