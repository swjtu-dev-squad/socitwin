"""
Unit tests for Polarization Analyzer

Tests the polarization analysis functionality including:
- Stance calculation metrics
- JSON parsing
- Database operations
"""

import pytest
import numpy as np
import sqlite3
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from oasis_dashboard.polarization_analyzer import PolarizationAnalyzer
from oasis_dashboard.context.config import ModelRuntimeSpec


class TestPolarizationCalculator:
    """测试极化率计算器"""

    def test_polarization_extreme(self):
        """测试极端极化（两端分布）"""
        # 导入真实的计算函数
        from oasis_dashboard.polarization_analyzer import PolarizationAnalyzer

        # 完全两极化：[0, 0, 1, 1]
        stances = [0.0, 0.1, 0.9, 1.0]
        result = PolarizationAnalyzer._calculate_polarization_metrics(None, stances)

        assert result['polarization'] > 0.7, "极端极化应该有很高的极化率"
        assert result['std'] > 0.4, "极端极化应该有很高的标准差"
        assert result['r_metric'] > 0.7, "极端极化应该有很高的R指标"
        assert result['sample_size'] == 4

    def test_polarization_neutral(self):
        """测试中立分布"""
        from oasis_dashboard.polarization_analyzer import PolarizationAnalyzer

        # 完全中立：[0.5, 0.5, 0.5, 0.5]
        stances = [0.5, 0.5, 0.5, 0.5]
        result = PolarizationAnalyzer._calculate_polarization_metrics(None, stances)

        assert result['polarization'] < 0.2, "中立分布应该有很低的极化率"
        assert result['std'] < 0.1, "中立分布应该有很低的标准差"
        assert result['sample_size'] == 4

    def test_polarization_mixed(self):
        """测试混合分布"""
        from oasis_dashboard.polarization_analyzer import PolarizationAnalyzer

        # 混合分布
        stances = [0.2, 0.4, 0.5, 0.6, 0.8]
        result = PolarizationAnalyzer._calculate_polarization_metrics(None, stances)

        # 中度极化
        assert 0.3 < result['polarization'] < 0.7, "混合分布应该有中度的极化率"
        assert result['sample_size'] == 5

    def test_polarization_empty(self):
        """测试空列表"""
        from oasis_dashboard.polarization_analyzer import PolarizationAnalyzer

        stances = []
        result = PolarizationAnalyzer._calculate_polarization_metrics(None, stances)

        assert result['polarization'] == 0.0
        assert result['std'] == 0.0
        assert result['sample_size'] == 0


class TestJSONParsing:
    """测试JSON解析功能"""

    def test_parse_valid_json(self):
        """测试解析有效的JSON"""
        from oasis_dashboard.polarization_analyzer import PolarizationAnalyzer

        text = "[0.2, 0.7, 0.5, 0.3]"
        stances = PolarizationAnalyzer._parse_stance_json(None, text, 4)

        assert len(stances) == 4
        assert stances == [0.2, 0.7, 0.5, 0.3]

    def test_parse_json_with_markdown(self):
        """测试解析带markdown的JSON"""
        from oasis_dashboard.polarization_analyzer import PolarizationAnalyzer

        text = '''```json
[0.2, 0.7, 0.5]
```'''
        stances = PolarizationAnalyzer._parse_stance_json(None, text, 3)

        assert len(stances) == 3
        assert stances == [0.2, 0.7, 0.5]

    def test_parse_json_with_extra_text(self):
        """测试解析带额外文本的JSON"""
        from oasis_dashboard.polarization_analyzer import PolarizationAnalyzer

        text = "Some text here [0.2, 0.7, 0.5] some more text"
        stances = PolarizationAnalyzer._parse_stance_json(None, text, 3)

        assert len(stances) == 3
        assert stances == [0.2, 0.7, 0.5]

    def test_parse_clips_out_of_range(self):
        """测试超出范围的值被裁剪"""
        from oasis_dashboard.polarization_analyzer import PolarizationAnalyzer

        text = "[-0.5, 0.5, 1.5]"
        stances = PolarizationAnalyzer._parse_stance_json(None, text, 3)

        # 负值变为0，大于1的值变为1
        assert stances[0] == 0.0
        assert stances[1] == 0.5
        assert stances[2] == 1.0

    def test_parse_invalid_json(self):
        """测试解析无效的JSON"""
        from oasis_dashboard.polarization_analyzer import PolarizationAnalyzer

        text = "not valid json at all"
        stances = PolarizationAnalyzer._parse_stance_json(None, text, 3)

        assert stances == []

    def test_parse_wrong_count(self):
        """测试数量不匹配"""
        from oasis_dashboard.polarization_analyzer import PolarizationAnalyzer

        text = "[0.2, 0.7]"  # 只有2个，但期望3个
        stances = PolarizationAnalyzer._parse_stance_json(None, text, 3)

        # 数量不匹配应该返回空
        assert stances == []


class TestTextTruncation:
    """测试文本截断功能"""

    def test_truncate_short_text(self):
        """测试截断短文本（不截断）"""
        text = "This is a short text"
        result = PolarizationAnalyzer._truncate_text(text, 100)

        assert result == text

    def test_truncate_long_text(self):
        """测试截断长文本"""
        text = "This is a very long text that should be truncated"
        result = PolarizationAnalyzer._truncate_text(text, 20)

        assert len(result) <= 23  # 20 chars + "..."
        assert result.endswith("...")


class TestDatabaseOperations:
    """测试数据库操作"""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """创建临时数据库"""
        db_path = tmp_path / "test.db"
        return str(db_path)

    def test_init_cache_table(self, temp_db):
        """测试初始化缓存表"""
        # 创建mock model spec
        model_spec = ModelRuntimeSpec(
            model_platform="ollama",
            model_type="qwen3:8b",
            url="http://localhost:11434/v1"
        )

        analyzer = PolarizationAnalyzer(
            db_path=temp_db,
            model_spec=model_spec,
            topic="test"
        )

        # 验证表已创建
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='polarization_cache'
        """)
        result = cursor.fetchone()

        assert result is not None, "缓存表应该被创建"

        conn.close()

    def test_save_and_prune_cache(self, temp_db):
        """测试保存和清理缓存"""
        model_spec = ModelRuntimeSpec(
            model_platform="ollama",
            model_type="qwen3:8b",
            url="http://localhost:11434/v1"
        )

        analyzer = PolarizationAnalyzer(
            db_path=temp_db,
            model_spec=model_spec,
            topic="test",
            cache_size=3  # 只保留3条
        )

        # 保存5条结果
        post_ids = [1, 2, 3, 4, 5]
        stances = [0.2, 0.7, 0.5, 0.3, 0.8]
        analyzer._save_analysis_results(post_ids, stances)

        # 验证只有3条保留（最新的）
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM polarization_cache")
        count = cursor.fetchone()[0]

        assert count == 3, f"应该只保留3条，实际保留了{count}条"

        # 验证保留的是post_id 3, 4, 5（最大的3个）
        cursor.execute(
            "SELECT post_id FROM polarization_cache ORDER BY post_id"
        )
        remaining_ids = [row[0] for row in cursor.fetchall()]

        assert remaining_ids == [3, 4, 5], "应该保留最新的3条"

        conn.close()


class TestHistoricalFallback:
    """测试历史平均值降级"""

    def test_get_historical_fallback_with_history(self):
        """测试有历史数据时的降级"""
        model_spec = ModelRuntimeSpec(
            model_platform="ollama",
            model_type="qwen3:8b",
            url="http://localhost:11434/v1"
        )

        analyzer = PolarizationAnalyzer(
            db_path=":memory:",
            model_spec=model_spec,
            topic="test"
        )
        analyzer.history = [0.3, 0.5, 0.7, 0.6]

        result = analyzer._get_historical_fallback()

        assert result['polarization'] == pytest.approx(0.525, rel=1e-3)  # 平均值
        assert result['degraded'] is True

    def test_get_historical_fallback_without_history(self):
        """测试无历史数据时的降级"""
        model_spec = ModelRuntimeSpec(
            model_platform="ollama",
            model_type="qwen3:8b",
            url="http://localhost:11434/v1"
        )

        analyzer = PolarizationAnalyzer(
            db_path=":memory:",
            model_spec=model_spec,
            topic="test"
        )
        analyzer.history = []

        result = analyzer._get_historical_fallback()

        assert result['polarization'] == 0.0
        assert result['error'] is True


class TestGetNewPosts:
    """测试获取新帖子功能"""

    @pytest.fixture
    def populated_db(self, tmp_path):
        """创建带测试数据的数据库"""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 创建post表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS post (
                post_id INTEGER PRIMARY KEY,
                content TEXT,
                num_likes INTEGER DEFAULT 0
            )
        """)

        # 插入测试数据
        test_posts = [
            (1, "Post 1 content", 5),
            (2, "Post 2 content", 3),
            (3, "Post 3 content", 0),
            (4, "Post 4 content", 2),
        ]

        for post_id, content, num_likes in test_posts:
            cursor.execute(
                "INSERT INTO post (post_id, content, num_likes) VALUES (?, ?, ?)",
                (post_id, content, num_likes)
            )

        conn.commit()
        conn.close()

        return str(db_path)

    def test_get_new_posts_none_cached(self, populated_db):
        """测试获取新帖子（无缓存）"""
        model_spec = ModelRuntimeSpec(
            model_platform="ollama",
            model_type="qwen3:8b",
            url="http://localhost:11434/v1"
        )

        analyzer = PolarizationAnalyzer(
            db_path=populated_db,
            model_spec=model_spec,
            topic="test",
            sample_size=10
        )

        posts = analyzer._get_new_posts()

        # 应该获取所有4条帖子
        assert len(posts) == 4

        # 验证结构
        assert 'post_id' in posts[0]
        assert 'content' in posts[0]
        assert 'num_likes' in posts[0]

        # 验证last_analyzed_post_id已更新
        assert analyzer.last_analyzed_post_id == 4

    def test_get_new_posts_with_cache(self, populated_db):
        """测试获取新帖子（有缓存）"""
        model_spec = ModelRuntimeSpec(
            model_platform="ollama",
            model_type="qwen3:8b",
            url="http://localhost:11434/v1"
        )

        analyzer = PolarizationAnalyzer(
            db_path=populated_db,
            model_spec=model_spec,
            topic="test",
            sample_size=10
        )

        # 添加一些缓存记录
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO polarization_cache (post_id, stance_score, topic)
            VALUES (1, 0.5, 'test'), (2, 0.6, 'test')
        """)

        conn.commit()
        conn.close()

        # 获取新帖子
        posts = analyzer._get_new_posts()

        # 应该只获取post 3和4（post 1和2已缓存）
        assert len(posts) == 2
        post_ids = [p['post_id'] for p in posts]
        assert 3 in post_ids
        assert 4 in post_ids
        assert 1 not in post_ids
        assert 2 not in post_ids


@pytest.mark.asyncio
class TestAnalyzeBatch:
    """测试批量分析功能"""

    async def test_analyze_batch_success(self):
        """测试成功的批量分析"""
        model_spec = ModelRuntimeSpec(
            model_platform="ollama",
            model_type="qwen3:8b",
            url="http://localhost:11434/v1"
        )

        analyzer = PolarizationAnalyzer(
            db_path=":memory:",
            model_spec=model_spec,
            topic="test"
        )

        posts = [
            {'post_id': 1, 'content': 'I agree with this'},
            {'post_id': 2, 'content': 'I disagree with this'},
        ]

        # Mock LLM响应
        from camel.messages import BaseMessage

        mock_response = MagicMock()
        mock_response.msgs = [MagicMock()]
        mock_response.msgs[0].content = "[0.8, 0.2]"

        with patch.object(analyzer.model, 'astep', return_value=mock_response):
            stances = await analyzer._analyze_batch(posts)

        assert len(stances) == 2
        assert stances[0] == 0.8
        assert stances[1] == 0.2

    async def test_analyze_batch_retry_on_failure(self):
        """测试LLM失败时的重试"""
        model_spec = ModelRuntimeSpec(
            model_platform="ollama",
            model_type="qwen3:8b",
            url="http://localhost:11434/v1"
        )

        analyzer = PolarizationAnalyzer(
            db_path=":memory:",
            model_spec=model_spec,
            topic="test"
        )

        posts = [
            {'post_id': 1, 'content': 'Test post'},
        ]

        # Mock LLM响应：前2次失败，第3次成功
        mock_response_success = MagicMock()
        mock_response_success.msgs = [MagicMock()]
        mock_response_success.msgs[0].content = "[0.5]"

        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("LLM error")
            return mock_response_success

        with patch.object(analyzer.model, 'astep', side_effect=side_effect):
            stances = await analyzer._analyze_batch(posts)

        assert call_count == 3  # 应该重试3次
        assert len(stances) == 1
        assert stances[0] == 0.5

    async def test_analyze_batch_all_retries_fail(self):
        """测试所有重试都失败"""
        model_spec = ModelRuntimeSpec(
            model_platform="ollama",
            model_type="qwen3:8b",
            url="http://localhost:11434/v1"
        )

        analyzer = PolarizationAnalyzer(
            db_path=":memory:",
            model_spec=model_spec,
            topic="test"
        )

        posts = [
            {'post_id': 1, 'content': 'Test post'},
        ]

        # Mock LLM响应：总是失败
        async def always_fail(*args, **kwargs):
            raise Exception("LLM error")

        with patch.object(analyzer.model, 'astep', side_effect=always_fail):
            stances = await analyzer._analyze_batch(posts)

        # 应该返回默认中立值
        assert stances == [0.5]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
