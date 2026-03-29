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
            os.environ.get("OASIS_POLARIZATION_TIMEOUT", "600")  # 10分钟
        )
        self.request_timeout_s = float(
            os.environ.get("OASIS_POLARIZATION_REQUEST_TIMEOUT", "600")  # 10分钟
        )
        self.max_retries = int(
            os.environ.get("OASIS_POLARIZATION_MAX_RETRIES", "3")
        )
        self.chunk_size = max(
            1,
            int(os.environ.get("OASIS_POLARIZATION_CHUNK_SIZE", "20")),
        )

        # 初始化模型
        resolved_model = build_shared_model(self.model_spec)
        self.model = resolved_model.model

        # 状态追踪
        self.last_analyzed_post_id = 0
        self.history: List[float] = []  # 最近的分析结果用于降级
        self.last_result: Dict = {}
        self.round_0_baseline: Dict = {}  # Round 0 基线数据（用于对比）

        # 🆕 增量累积统计：维护所有历史立场分数，避免重复计算
        self.cumulative_stances: List[float] = []  # 所有已分析帖子的立场分数
        self.max_cached_stances = 100000  # 最多缓存10万条记录（内存限制）

        # 🆕 加载自定义极化提示词
        self.polarization_prompts = self._load_polarization_prompts()
        self.custom_prompt = self._find_prompt_for_topic(topic)

        # 初始化数据库缓存表
        self._init_cache_table()

        # 🆕 启动时从数据库加载历史立场分数到内存
        self._load_cumulative_stances_from_db()

        logger.info(
            f"✅ 极化率分析器已初始化: topic={topic}, sample_size={sample_size}"
        )

    def _init_cache_table(self):
        """初始化数据库缓存表（支持 post 和 comment）"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 检查是否需要迁移旧表结构
            cursor.execute("""
                SELECT sql FROM sqlite_master
                WHERE type='table' AND name='polarization_cache'
            """)
            result = cursor.fetchone()

            if result:
                existing_sql = result[0]
                # 如果旧表结构存在（没有 content_type 字段），需要迁移
                if 'content_type' not in existing_sql:
                    logger.info("检测到旧版 polarization_cache 表，开始迁移...")
                    self._migrate_cache_table(cursor)

            # 创建缓存表（新结构）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS polarization_cache (
                    content_type TEXT NOT NULL,
                    item_id INTEGER NOT NULL,
                    stance_score REAL NOT NULL,
                    confidence REAL DEFAULT 0.8,
                    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    topic TEXT NOT NULL,
                    PRIMARY KEY (content_type, item_id, topic)
                )
            """)

            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_polarization_topic_time
                ON polarization_cache(topic, analyzed_at)
            """)

            # 启用WAL模式以提高并发性能
            cursor.execute("PRAGMA journal_mode=WAL")

            # 如果进行了迁移，恢复备份数据
            if result and 'content_type' not in result[0]:
                self._restore_backup_data(cursor)

            conn.commit()
            conn.close()

            logger.debug("数据库缓存表已初始化")

        except Exception as e:
            logger.error(f"初始化缓存表失败: {e}")

    def _migrate_cache_table(self, cursor: sqlite3.Cursor):
        """
        迁移旧版 polarization_cache 表到新结构
        旧结构: post_id INTEGER PRIMARY KEY
        新结构: (content_type, item_id, topic) PRIMARY KEY
        """
        try:
            # 1. 备份旧数据到永久表（不是临时表，因为需要在不同的 cursor 间共享）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS polarization_cache_migration AS
                SELECT * FROM polarization_cache
            """)
            logger.info(f"已创建迁移备份表")

            # 2. 删除旧表
            cursor.execute("DROP TABLE polarization_cache")

            # 3. 删除旧索引
            cursor.execute("""
                DROP INDEX IF EXISTS idx_polarization_topic_time
            """)

            logger.info("旧表结构已删除，新表将在 _init_cache_table 中创建")

        except Exception as e:
            logger.error(f"迁移缓存表失败: {e}")
            raise

    def _restore_backup_data(self, cursor: sqlite3.Cursor):
        """从备份恢复数据到新表结构"""
        try:
            # 检查备份是否存在
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='polarization_cache_migration'
            """)
            if not cursor.fetchone():
                logger.debug("没有备份数据需要恢复")
                return

            # 获取备份数据数量
            cursor.execute("SELECT COUNT(*) FROM polarization_cache_migration")
            backup_count = cursor.fetchone()[0]

            # 恢复数据（旧数据都是 post 类型）
            cursor.execute("""
                INSERT OR IGNORE INTO polarization_cache
                (content_type, item_id, stance_score, confidence, analyzed_at, topic)
                SELECT
                    'post' as content_type,
                    post_id as item_id,
                    stance_score,
                    confidence,
                    analyzed_at,
                    topic
                FROM polarization_cache_migration
            """)

            logger.info(f"已恢复 {backup_count} 条历史数据到新表结构")

            # 删除备份表
            cursor.execute("DROP TABLE polarization_cache_migration")

        except Exception as e:
            logger.error(f"恢复备份数据失败: {e}")

    def _load_polarization_prompts(self) -> Dict:
        """
        从外部配置文件加载极化提示词

        Returns:
            提示词配置字典
        """
        try:
            # 尝试从多个位置加载
            possible_paths = [
                os.path.join(os.path.dirname(__file__), "prompts", "polarization.json"),
                os.path.join(os.path.dirname(__file__), "..", "oasis_dashboard", "prompts", "polarization.json"),
                "/app/oasis_dashboard/prompts/polarization.json",
            ]

            for path in possible_paths:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                    logger.info(f"✅ 已加载极化提示词配置: {path}")
                    logger.info(f"   可用话题: {list(config.get('topics', {}).keys())}")
                    return config

            # 如果找不到文件，返回默认配置
            logger.warning("⚠️  未找到 polarization.json，使用默认提示词")
            return {"topics": {"default": {"prompt_template": None}}}

        except Exception as e:
            logger.warning(f"⚠️  加载极化提示词失败: {e}，使用默认提示词")
            return {"topics": {"default": {"prompt_template": None}}}

    def _find_prompt_for_topic(self, topic: str) -> Dict:
        """
        根据topic查找对应的提示词配置

        Args:
            topic: 话题名称

        Returns:
            提示词配置 {dimension, prompt_template, ...}
        """
        if not self.polarization_prompts or "topics" not in self.polarization_prompts:
            return {}

        topics_config = self.polarization_prompts["topics"]
        topic_upper = topic.upper()

        # 精确匹配
        if topic_upper in topics_config:
            config = topics_config[topic_upper]
            logger.info(f"✅ 找到精确匹配的提示词: {topic_upper} - {config.get('dimension', 'N/A')}")
            return config

        # 子串匹配（支持 MiddleEast → MIDDLEEAST）
        for key, config in topics_config.items():
            if key != "default" and key in topic_upper:
                logger.info(f"✅ 找到子串匹配: {topic_upper} → {key} - {config.get('dimension', 'N/A')}")
                return config

        # 未找到，使用默认
        logger.warning(f"⚠️  未找到topic '{topic}' 的提示词，使用默认提示词")
        return topics_config.get("default", {})

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
                        new_posts,
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
        分析帖子列表并计算极化率（增量累积统计版本）

        核心改进：
        1. 只分析新帖子的立场（避免重复计算）
        2. 将新立场追加到累积列表
        3. 基于所有历史帖子计算极化率

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

        # 2. 保存分析结果到数据库缓存
        self._save_analysis_results(
            posts,
            stances,
            confidence=confidence,
        )

        # 3. 🆕 增量累积：将新立场分数追加到累积列表
        new_stances_count = len(stances)
        self.cumulative_stances.extend(stances)

        # 内存保护：超过上限时移除最旧的记录
        if len(self.cumulative_stances) > self.max_cached_stances:
            removed = len(self.cumulative_stances) - self.max_cached_stances
            self.cumulative_stances = self.cumulative_stances[-self.max_cached_stances:]
            logger.warning(f"累积缓存超限，移除了 {removed} 条最旧记录")

        # 4. 🆕 基于所有历史帖子（累积数据）计算极化率
        result = self._calculate_polarization_metrics(self.cumulative_stances)

        # 5. 更新历史记录（用于降级）
        self.history.append(result['polarization'])
        if len(self.history) > 100:
            self.history.pop(0)

        # 6. 🆕 添加额外统计信息
        result['new_posts_analyzed'] = new_stances_count
        result['total_posts_cumulative'] = len(self.cumulative_stances)
        result['cumulative_mode'] = True

        logger.info(
            f"✅ 极化率分析完成（累积模式）: {result['polarization']:.3f} "
            f"(新帖子={new_stances_count}, 累积总数={len(self.cumulative_stances)}, "
            f"std={result['std']:.3f})"
        )

        if degraded:
            result["degraded"] = True
        result["source"] = f"{source}_cumulative"

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
        获取未分析的新帖子和新评论

        Returns:
            内容列表（包含 posts 和 comments）
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            contents = []

            # 1. 获取未分析的新帖子
            cursor.execute("""
                SELECT
                    p.post_id,
                    p.content,
                    p.num_likes,
                    'post' as content_type
                FROM post p
                LEFT JOIN polarization_cache pc
                    ON pc.content_type = 'post'
                    AND pc.item_id = p.post_id
                    AND pc.topic = ?
                WHERE pc.item_id IS NULL
                ORDER BY p.post_id DESC
                LIMIT ?
            """, (self.topic, self.sample_size))

            for row in cursor.fetchall():
                contents.append({
                    'item_id': row[0],
                    'content': row[1],
                    'num_likes': row[2] or 0,
                    'content_type': 'post',
                })

            # 2. 获取未分析的新评论
            cursor.execute("""
                SELECT
                    c.comment_id,
                    c.content,
                    c.num_likes,
                    'comment' as content_type
                FROM comment c
                LEFT JOIN polarization_cache pc
                    ON pc.content_type = 'comment'
                    AND pc.item_id = c.comment_id
                    AND pc.topic = ?
                WHERE pc.item_id IS NULL
                ORDER BY c.comment_id DESC
                LIMIT ?
            """, (self.topic, self.sample_size))

            for row in cursor.fetchall():
                contents.append({
                    'item_id': row[0],
                    'content': row[1],
                    'num_likes': row[2] or 0,
                    'content_type': 'comment',
                })

            conn.close()

            if contents:
                logger.debug(f"获取到 {len(contents)} 条未分析内容（posts + comments）")

            return contents

        except Exception as e:
            logger.error(f"获取新内容失败: {e}")
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

        # 🆕 使用自定义提示词（如果配置了）
        prompt_template = self.custom_prompt.get("prompt_template")
        if prompt_template:
            # 使用自定义提示词
            prompt = prompt_template.format(topic=self.topic, posts=post_texts)
            logger.debug(f"使用自定义提示词 (dimension: {self.custom_prompt.get('dimension', 'N/A')})")
        else:
            # 使用默认提示词（向后兼容）
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
                logger.warning(f"LLM调用失败（尝试 {attempt+1}/{max_retries}）: {type(e).__name__}: {e}")
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
        posts: List[Dict],
        stances: List[float],
        confidence: float = 0.8,
    ):
        """
        保存分析结果到数据库缓存（支持 post 和 comment）

        Args:
            posts: 内容列表，每个包含 item_id 和 content_type
            stances: 立场分数列表
        """
        if not posts or not stances:
            return

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            now = datetime.now().isoformat()

            for post, stance in zip(posts, stances):
                content_type = post.get('content_type', 'post')
                item_id = post.get('item_id') or post.get('post_id')
                cursor.execute("""
                    INSERT OR REPLACE INTO polarization_cache
                    (content_type, item_id, stance_score, confidence, analyzed_at, topic)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (content_type, item_id, stance, confidence, now, self.topic))

            conn.commit()

            # 清理旧缓存（保留最近N条）
            self._prune_cache(cursor)

            conn.close()

            logger.debug(f"已保存 {len(posts)} 条分析结果到缓存")

        except Exception as e:
            logger.error(f"保存分析结果失败: {e}")

    def _prune_cache(self, cursor: sqlite3.Cursor):
        """清理缓存，保留最近N条（同时包含 post 和 comment）"""
        try:
            cursor.execute("""
                DELETE FROM polarization_cache
                WHERE (content_type, item_id) NOT IN (
                    SELECT content_type, item_id FROM polarization_cache
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
        获取缓存的分析结果（增量累积统计版本）

        逻辑：
        1. 如果有上一次结果，直接返回（避免重复计算）
        2. 如果没有，基于内存中的累积立场列表计算
        3. 如果内存为空，从数据库加载
        """
        # 1. 优先返回上一次的分析结果（已经基于累积数据）
        if self.last_result:
            total_samples = self.last_result.get('total_posts_cumulative',
                                                self.last_result.get('sample_size', 0))
            if total_samples > 0:
                logger.debug(
                    f"使用缓存的极化率结果: {self.last_result.get('polarization'):.3f} "
                    f"(累积样本={total_samples})"
                )
                return self.last_result

        # 2. 如果没有 last_result，基于内存中的累积立场计算
        if self.cumulative_stances:
            logger.info(
                f"基于内存累积数据计算极化率: {len(self.cumulative_stances)} 条记录"
            )
            result = self._calculate_polarization_metrics(self.cumulative_stances)
            result['total_posts_cumulative'] = len(self.cumulative_stances)
            result['new_posts_analyzed'] = 0
            result['cumulative_mode'] = True
            result['cached'] = True
            result['source'] = 'cumulative_cache'
            self.last_result = result
            return result

        # 3. 内存为空，从数据库加载（初始化场景）
        logger.warning("内存累积缓存为空，尝试从数据库加载")
        cached_stances = self._load_cached_stances(limit=10000)
        if cached_stances:
            logger.info(f"从数据库加载了 {len(cached_stances)} 条 stance 记录")
            # 加载到内存
            self.cumulative_stances = cached_stances
            # 计算极化率
            result = self._calculate_polarization_metrics(cached_stances)
            result['total_posts_cumulative'] = len(cached_stances)
            result['new_posts_analyzed'] = 0
            result['cumulative_mode'] = True
            result['cached'] = True
            result['source'] = 'db_cumulative_init'
            self.last_result = result
            return result

        logger.warning("数据库中无 stance 记录")

        # 如果有历史数据，返回平均值
        if self.history:
            avg_pol = sum(self.history) / len(self.history)
            logger.info(f"使用历史平均极化率: {avg_pol:.3f} (history_len={len(self.history)})")
            return {
                'polarization': avg_pol,
                'std': 0.0,
                'r_metric': 0.0,
                'bimodality': 0.0,
                'sample_size': 0,
                'cached': True,
                'source': 'history_fallback',
            }

        # 默认返回0（仅当数据库完全为空时）
        logger.error("极化缓存为空且无历史数据，返回零值")
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

    def _load_cached_stances(self, limit: int = 10000) -> List[float]:
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

    def _load_cumulative_stances_from_db(self) -> None:
        """
        从数据库加载所有历史立场分数到内存（增量累积统计）

        只在初始化时调用一次，之后每次只追加新分析的帖子
        """
        try:
            # 加载所有历史立场分数
            all_stances = self._load_cached_stances(limit=self.max_cached_stances)

            if all_stances:
                self.cumulative_stances = all_stances
                logger.info(
                    f"✅ 加载了 {len(self.cumulative_stances)} 条历史立场记录到累积缓存"
                )
            else:
                logger.info("📊 数据库中无历史立场记录，累积缓存为空")
                self.cumulative_stances = []

        except Exception as e:
            logger.error(f"加载累积立场缓存失败: {e}")
            self.cumulative_stances = []

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

    # ========== Round Comparison Methods (OASIS Paper Metrics) ==========

    async def _save_round_0_baseline(self):
        """
        保存 Round 0 的基线数据

        采样 Round 0 的帖子，分析立场，保存到数据库作为后续对比的基准。
        """
        try:
            logger.info("正在保存 Round 0 极化基线...")

            # 采样 Round 0 的帖子（使用 sample_size）
            posts = self._get_round_posts(round_number=0, sample_size=self.sample_size)

            if not posts:
                logger.warning("Round 0 没有找到帖子，跳过基线保存")
                return

            # 分析立场
            stances = await self._analyze_with_chunk_fallback(posts)

            if not stances:
                logger.warning("Round 0 立场分析失败，使用启发式估计")
                stances = self._heuristic_stance_batch(posts)

            # 计算基线统计
            import numpy as np
            self.round_0_baseline = {
                'mean_stance': float(np.mean(stances)),
                'std_stance': float(np.std(stances)),
                'extreme_ratio': float(np.mean([abs(s - 0.5) * 2 for s in stances])),
                'stances': stances,
                'sample_size': len(stances),
                'timestamp': datetime.now().isoformat(),
            }

            # 持久化到数据库
            self._save_baseline_to_db(self.round_0_baseline)

            logger.info(
                f"✅ Round 0 基线已保存: "
                f"mean={self.round_0_baseline['mean_stance']:.3f}, "
                f"std={self.round_0_baseline['std_stance']:.3f}, "
                f"sample_size={len(stances)}"
            )

        except Exception as e:
            logger.error(f"保存 Round 0 基线失败: {e}")
            self.round_0_baseline = {}

    def _get_round_posts(
        self,
        round_number: int,
        sample_size: int = 30
    ) -> List[Dict]:
        """
        获取指定 Round 的帖子

        Args:
            round_number: Round 编号
            sample_size: 采样数量

        Returns:
            帖子列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 简化实现：使用 post_id 范围近似 round
            # 生产环境应使用 step 字段或 created_at
            if round_number == 0:
                # Round 0: 最早的帖子
                cursor.execute("""
                    SELECT
                        p.post_id,
                        p.content,
                        p.num_likes
                    FROM post p
                    ORDER BY p.post_id ASC
                    LIMIT ?
                """, (sample_size,))
            else:
                # Round N: 后续帖子
                start_id = round_number * sample_size
                cursor.execute("""
                    SELECT
                        p.post_id,
                        p.content,
                        p.num_likes
                    FROM post p
                    WHERE p.post_id >= ?
                    ORDER BY p.post_id ASC
                    LIMIT ?
                """, (start_id, sample_size))

            posts = []
            for row in cursor.fetchall():
                posts.append({
                    'post_id': row[0],
                    'content': row[1],
                    'num_likes': row[2] or 0,
                })

            conn.close()
            return posts

        except Exception as e:
            logger.error(f"获取 Round {round_number} 帖子失败: {e}")
            return []

    def _save_baseline_to_db(self, baseline: Dict):
        """
        保存基线到数据库

        Args:
            baseline: 基线数据字典
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 确保 polarization_baseline 表存在
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS polarization_baseline (
                    round_number INTEGER PRIMARY KEY,
                    baseline_data TEXT NOT NULL,
                    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 保存基线
            cursor.execute("""
                INSERT OR REPLACE INTO polarization_baseline
                (round_number, baseline_data, saved_at)
                VALUES (0, ?, CURRENT_TIMESTAMP)
            """, (json.dumps(baseline),))

            conn.commit()
            conn.close()

            logger.debug("基线已保存到数据库")

        except Exception as e:
            logger.error(f"保存基线到数据库失败: {e}")

    async def compare_rounds(self, round_n: int) -> Dict:
        """
        对比 Round N vs Round 0 的极化变化

        使用 LLM (GPT-4o-mini) 评估立场变化，分类为：
        - More Extreme/Conservative: 更极端/保守
        - More Progressive: 更进步
        - Unchanged: 无显著变化

        Args:
            round_n: 当前 Round 编号

        Returns:
            {
                'round_n': int,
                'round_0_baseline': dict,
                'comparison': {
                    'more_extreme': float,  # 0-1
                    'more_progressive': float,  # 0-1
                    'unchanged': float,  # 0-1
                },
                'llm_evaluation': str,
                'confidence': float,
                'sample_size': int,
            }
        """
        try:
            if not self.round_0_baseline:
                logger.warning("Round 0 基线不存在，无法对比")
                return {
                    'round_n': round_n,
                    'error': 'no_baseline',
                    'comparison': None
                }

            # 获取 Round N 的帖子
            round_n_posts = self._get_round_posts(round_n, self.sample_size)

            if not round_n_posts:
                logger.warning(f"Round {round_n} 没有帖子，无法对比")
                return {
                    'round_n': round_n,
                    'error': 'no_posts',
                    'comparison': None
                }

            # 分析 Round N 的立场
            round_n_stances = await self._analyze_with_chunk_fallback(round_n_posts)

            if not round_n_stances:
                logger.warning(f"Round {round_n} 立场分析失败")
                round_n_stances = self._heuristic_stance_batch(round_n_posts)

            # LLM 对比评估
            comparison = await self._llm_compare_rounds(round_n_stances)

            # 保存对比结果到数据库
            self._save_comparison_to_db(round_n, comparison)

            result = {
                'round_n': round_n,
                'round_0_baseline': {
                    'mean_stance': self.round_0_baseline.get('mean_stance', 0),
                    'std_stance': self.round_0_baseline.get('std_stance', 0),
                    'extreme_ratio': self.round_0_baseline.get('extreme_ratio', 0),
                },
                'comparison': comparison.get('comparison', {}),
                'llm_evaluation': comparison.get('llm_evaluation', ''),
                'confidence': comparison.get('confidence', 0.8),
                'sample_size': len(round_n_stances),
            }

            logger.info(
                f"✅ Round {round_n} vs Round 0 对比完成: "
                f"more_extreme={comparison['comparison'].get('more_extreme', 0):.2f}, "
                f"more_progressive={comparison['comparison'].get('more_progressive', 0):.2f}"
            )

            return result

        except Exception as e:
            logger.error(f"Round 对比失败: {e}")
            return {
                'round_n': round_n,
                'error': str(e),
                'comparison': None
            }

    async def _llm_compare_rounds(self, round_n_stances: List[float]) -> Dict:
        """
        使用 LLM 对比 Round N vs Round 0

        Args:
            round_n_stances: Round N 的立场分数列表

        Returns:
            {
                'comparison': {more_extreme, more_progressive, unchanged},
                'llm_evaluation': str,
                'confidence': float
            }
        """
        try:
            import numpy as np

            # 准备数据摘要
            round_0_summary = {
                'mean': self.round_0_baseline.get('mean_stance', 0.5),
                'std': self.round_0_baseline.get('std_stance', 0),
                'extreme': self.round_0_baseline.get('extreme_ratio', 0),
                'distribution': self._get_distribution_description(self.round_0_baseline.get('stances', []))
            }

            round_n_summary = {
                'mean': float(np.mean(round_n_stances)),
                'std': float(np.std(round_n_stances)),
                'extreme': float(np.mean([abs(s - 0.5) * 2 for s in round_n_stances])),
                'distribution': self._get_distribution_description(round_n_stances)
            }

            # 构建 LLM prompt
            prompt = f"""You are analyzing polarization shifts in social media discussions about "{self.topic}".

Round 0 Baseline (Initial State):
- Mean stance: {round_0_summary['mean']:.3f} (0=opposed, 1=supportive, 0.5=neutral)
- Std deviation: {round_0_summary['std']:.3f}
- Extreme ratio: {round_0_summary['extreme']:.3f} (0=centered, 1=extreme)
- Distribution: {round_0_summary['distribution']}

Round Current State:
- Mean stance: {round_n_summary['mean']:.3f}
- Std deviation: {round_n_summary['std']:.3f}
- Extreme ratio: {round_n_summary['extreme']:.3f}
- Distribution: {round_n_summary['distribution']}

Task: Classify the stance changes from Round 0 to Round Current into three categories:
1. More Extreme/Conservative: Users moved toward extreme positions (closer to 0 or 1)
2. More Progressive: Users moved toward moderate/center positions (closer to 0.5)
3. Unchanged: No significant shift

IMPORTANT: Return ONLY a valid JSON object with exact keys:
{{"more_extreme": <float between 0-1>, "more_progressive": <float between 0-1>, "unchanged": <float between 0-1>, "reasoning": "<brief explanation>"}}

The three values must sum to 1.0.

Your response:"""

            # 调用 LLM
            base_message = BaseMessage.make_user_message(
                role_name="user",
                content=prompt
            )
            openai_message = base_message.to_openai_message(OpenAIBackendRole.USER)

            response = await asyncio.wait_for(
                self.model.arun([openai_message]),
                timeout=self.request_timeout_s
            )

            result_text = self._extract_response_text(response)

            # 解析 JSON
            comparison = json.loads(result_text)

            # 验证和归一化
            more_extreme = float(comparison.get('more_extreme', 0.33))
            more_progressive = float(comparison.get('more_progressive', 0.33))
            unchanged = float(comparison.get('unchanged', 0.34))

            # 确保和为 1.0
            total = more_extreme + more_progressive + unchanged
            if total > 0:
                more_extreme /= total
                more_progressive /= total
                unchanged /= total

            return {
                'comparison': {
                    'more_extreme': round(more_extreme, 4),
                    'more_progressive': round(more_progressive, 4),
                    'unchanged': round(unchanged, 4),
                },
                'llm_evaluation': comparison.get('reasoning', ''),
                'confidence': 0.8
            }

        except Exception as e:
            logger.error(f"LLM 对比失败: {e}")
            # 降级：使用统计方法估计
            return self._fallback_statistical_comparison(round_n_stances)

    def _get_distribution_description(self, stances: List[float]) -> str:
        """
        生成立场分布的文字描述

        Args:
            stances: 立场分数列表

        Returns:
            分布描述字符串
        """
        import numpy as np

        if not stances:
            return "No data"

        left = sum(1 for s in stances if s < 0.4)
        center = sum(1 for s in stances if 0.4 <= s <= 0.6)
        right = sum(1 for s in stances if s > 0.6)

        total = len(stances)
        return f"Left: {left/total:.1%}, Center: {center/total:.1%}, Right: {right/total:.1%}"

    def _fallback_statistical_comparison(self, round_n_stances: List[float]) -> Dict:
        """
        LLM 失败时的统计方法降级

        Args:
            round_n_stances: Round N 的立场分数

        Returns:
            对比结果字典
        """
        import numpy as np

        round_n_mean = np.mean(round_n_stances)
        round_0_mean = self.round_0_baseline.get('mean_stance', 0.5)

        # 简单判断：均值是否向极端方向移动
        if abs(round_n_mean - 0.5) > abs(round_0_mean - 0.5):
            # 向极端移动
            more_extreme = 0.6
            more_progressive = 0.2
            unchanged = 0.2
        elif abs(round_n_mean - 0.5) < abs(round_0_mean - 0.5):
            # 向中心移动
            more_extreme = 0.2
            more_progressive = 0.6
            unchanged = 0.2
        else:
            # 无显著变化
            more_extreme = 0.2
            more_progressive = 0.2
            unchanged = 0.6

        return {
            'comparison': {
                'more_extreme': round(more_extreme, 4),
                'more_progressive': round(more_progressive, 4),
                'unchanged': round(unchanged, 4),
            },
            'llm_evaluation': 'Statistical fallback (LLM unavailable)',
            'confidence': 0.5,
            'degraded': True
        }

    def _save_comparison_to_db(self, round_n: int, comparison: Dict):
        """
        保存对比结果到数据库

        Args:
            round_n: Round 编号
            comparison: 对比结果字典
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 确保 polarization_comparison 表存在
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS polarization_comparison (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    round_n INTEGER NOT NULL UNIQUE,
                    comparison_result TEXT NOT NULL,
                    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 保存对比结果
            cursor.execute("""
                INSERT OR REPLACE INTO polarization_comparison
                (round_n, comparison_result, computed_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (round_n, json.dumps(comparison),))

            conn.commit()
            conn.close()

            logger.debug(f"Round {round_n} 对比结果已保存到数据库")

        except Exception as e:
            logger.error(f"保存对比结果失败: {e}")

    def get_round_baseline(self, round_number: int = 0) -> Dict:
        """
        从数据库获取基线数据

        Args:
            round_number: Round 编号（默认 0）

        Returns:
            基线数据字典
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT baseline_data FROM polarization_baseline
                WHERE round_number = ?
            """, (round_number,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return json.loads(row[0])

            return {}

        except Exception as e:
            logger.warning(f"读取基线失败: {e}")
            return {}
