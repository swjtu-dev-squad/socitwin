"""
Unit tests for MetricsAnalyzer

Tests for:
- Information velocity calculation
- Herd effect HHI calculation
- Metric caching
"""

import os
import tempfile
import sqlite3
import pytest
from datetime import datetime, timedelta

from oasis_dashboard.metrics_analyzer import MetricsAnalyzer


class TestVelocityCalculation:
    """Test velocity calculation with various scenarios"""

    def test_velocity_normal_case(self):
        """Test velocity calculation with normal data"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name

        try:
            analyzer = MetricsAnalyzer(db_path)

            # Test normal case: 5 posts in 5 seconds = 1.0 posts/s
            result = analyzer.calculate_velocity(
                step_number=1,
                current_posts=10,
                previous_posts=5,
                step_duration_s=5.0
            )

            assert result["velocity"] == 1.0
            assert result["delta_posts"] == 5
            assert result["step_duration"] == 5.0
            assert result["step_number"] == 1
            assert "error" not in result

        finally:
            os.unlink(db_path)

    def test_velocity_zero_duration(self):
        """Test velocity calculation with zero duration (should handle gracefully)"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name

        try:
            analyzer = MetricsAnalyzer(db_path)

            result = analyzer.calculate_velocity(
                step_number=2,
                current_posts=10,
                previous_posts=5,
                step_duration_s=0.0
            )

            assert result["velocity"] == 0.0
            assert "error" in result
            assert result["error"] == "invalid_time_delta"

        finally:
            os.unlink(db_path)

    def test_velocity_negative_duration(self):
        """Test velocity calculation with negative duration"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name

        try:
            analyzer = MetricsAnalyzer(db_path)

            result = analyzer.calculate_velocity(
                step_number=3,
                current_posts=10,
                previous_posts=5,
                step_duration_s=-1.0
            )

            assert result["velocity"] == 0.0
            assert "error" in result

        finally:
            os.unlink(db_path)

    def test_velocity_no_new_posts(self):
        """Test velocity calculation when no new posts are created"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name

        try:
            analyzer = MetricsAnalyzer(db_path)

            result = analyzer.calculate_velocity(
                step_number=4,
                current_posts=10,
                previous_posts=10,
                step_duration_s=5.0
            )

            assert result["velocity"] == 0.0
            assert result["delta_posts"] == 0

        finally:
            os.unlink(db_path)

    def test_velocity_high_precision(self):
        """Test that velocity is rounded to 4 decimal places"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name

        try:
            analyzer = MetricsAnalyzer(db_path)

            # 3 posts in 7 seconds = 0.428571...
            result = analyzer.calculate_velocity(
                step_number=5,
                current_posts=13,
                previous_posts=10,
                step_duration_s=7.0
            )

            assert result["velocity"] == round(3/7, 4)
            assert len(str(result["velocity"]).split(".")[-1]) <= 4

        finally:
            os.unlink(db_path)


class TestHHICalculation:
    """Test HHI calculation with various action distributions"""

    def test_hhi_single_action_type(self):
        """Test HHI when all agents perform the same action (maximum concentration)"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name

        try:
            # Setup test database with trace data
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE trace (
                    user_id INTEGER,
                    created_at DATETIME,
                    action TEXT,
                    info TEXT,
                    PRIMARY KEY(user_id, created_at, action, info)
                )
            """)

            # Insert test data: all refresh actions
            now = datetime.now()
            actions = [
                (1, now.isoformat(), "refresh", "info1"),
                (2, now.isoformat(), "refresh", "info2"),
                (3, now.isoformat(), "refresh", "info3"),
            ]
            cursor.executemany("INSERT INTO trace VALUES (?, ?, ?, ?)", actions)
            conn.commit()
            conn.close()

            analyzer = MetricsAnalyzer(db_path)
            result = analyzer.calculate_herd_hhi(step_number=1)

            # Single action type = maximum concentration = HHI = 1.0
            assert result["herd_hhi"] == 1.0
            assert result["raw_hhi"] == 1.0
            assert result["n_action_types"] == 1
            assert result["total_actions"] == 3
            assert "error" not in result

        finally:
            os.unlink(db_path)

    def test_hhi_multiple_action_types(self):
        """Test HHI with multiple action types"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name

        try:
            # Setup test database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE trace (
                    user_id INTEGER,
                    created_at DATETIME,
                    action TEXT,
                    info TEXT,
                    PRIMARY KEY(user_id, created_at, action, info)
                )
            """)

            # Insert test data: 3 action types with uneven distribution
            # refresh: 2, create_post: 1, like_post: 1
            now = datetime.now()
            actions = [
                (1, now.isoformat(), "refresh", "info1"),
                (2, now.isoformat(), "refresh", "info2"),
                (3, now.isoformat(), "create_post", "info3"),
                (4, now.isoformat(), "like_post", "info4"),
            ]
            cursor.executemany("INSERT INTO trace VALUES (?, ?, ?, ?)", actions)
            conn.commit()
            conn.close()

            analyzer = MetricsAnalyzer(db_path)
            result = analyzer.calculate_herd_hhi(step_number=1)

            # Distribution: 0.5, 0.25, 0.25
            # Raw HHI = 0.5² + 0.25² + 0.25² = 0.375
            # Normalized HHI = (0.375 - 1/3) / (1 - 1/3) = 0.0625 / 0.667 = 0.09375
            assert "herd_hhi" in result
            assert "raw_hhi" in result
            assert result["total_actions"] == 4
            assert result["n_action_types"] == 3
            assert 0 <= result["herd_hhi"] <= 1

            # Check action distribution
            dist = result["action_distribution"]
            assert dist["refresh"] == 0.5
            assert dist["create_post"] == 0.25
            assert dist["like_post"] == 0.25

        finally:
            os.unlink(db_path)

    def test_hhi_no_trace_data(self):
        """Test HHI calculation when trace table is empty"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name

        try:
            # Setup empty trace table
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE trace (
                    user_id INTEGER,
                    created_at DATETIME,
                    action TEXT,
                    info TEXT,
                    PRIMARY KEY(user_id, created_at, action, info)
                )
            """)
            conn.commit()
            conn.close()

            analyzer = MetricsAnalyzer(db_path)
            result = analyzer.calculate_herd_hhi(step_number=1)

            # Should use fallback
            assert result["herd_hhi"] == 0.0
            assert result.get("degraded") is True
            assert "error" in result

        finally:
            os.unlink(db_path)

    def test_hhi_time_window_filtering(self):
        """Test that HHI only considers actions within the time window"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name

        try:
            # Setup test database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE trace (
                    user_id INTEGER,
                    created_at DATETIME,
                    action TEXT,
                    info TEXT,
                    PRIMARY KEY(user_id, created_at, action, info)
                )
            """)

            # Insert test data with different timestamps
            now = datetime.now()
            old_time = now - timedelta(seconds=120)  # 2 minutes ago

            actions = [
                (1, now.isoformat(), "refresh", "recent"),
                (2, now.isoformat(), "create_post", "recent"),
                (3, old_time.isoformat(), "like_post", "old"),  # Should be filtered out
            ]
            cursor.executemany("INSERT INTO trace VALUES (?, ?, ?, ?)", actions)
            conn.commit()
            conn.close()

            analyzer = MetricsAnalyzer(db_path)
            # Use 60 second window
            result = analyzer.calculate_herd_hhi(step_number=1, time_window_s=60.0)

            # Should only count recent actions (2)
            assert result["total_actions"] == 2
            assert result["n_action_types"] == 2
            assert "like_post" not in result["action_distribution"]

        finally:
            os.unlink(db_path)


class TestMetricCaching:
    """Test metric caching and retrieval"""

    def test_velocity_caching(self):
        """Test that velocity metrics are cached correctly"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name

        try:
            analyzer = MetricsAnalyzer(db_path)

            # Calculate and cache metric
            analyzer.calculate_velocity(
                step_number=1,
                current_posts=10,
                previous_posts=5,
                step_duration_s=5.0
            )

            # Retrieve cached metric
            cached = analyzer.get_cached_velocity(step_number=1)

            assert cached["velocity"] == 1.0
            assert cached["delta_posts"] == 5
            assert cached["step_number"] == 1

        finally:
            os.unlink(db_path)

    def test_hhi_caching(self):
        """Test that HHI metrics are cached correctly"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name

        try:
            # Setup test database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE trace (
                    user_id INTEGER,
                    created_at DATETIME,
                    action TEXT,
                    info TEXT,
                    PRIMARY KEY(user_id, created_at, action, info)
                )
            """)

            now = datetime.now()
            actions = [
                (1, now.isoformat(), "refresh", "info1"),
                (2, now.isoformat(), "create_post", "info2"),
            ]
            cursor.executemany("INSERT INTO trace VALUES (?, ?, ?, ?)", actions)
            conn.commit()
            conn.close()

            analyzer = MetricsAnalyzer(db_path)
            analyzer.calculate_herd_hhi(step_number=1)

            # Retrieve cached metric
            cached = analyzer.get_cached_hhi(step_number=1)

            assert "herd_hhi" in cached
            assert cached["step_number"] == 1
            assert cached["total_actions"] == 2

        finally:
            os.unlink(db_path)

    def test_cache_overwrite(self):
        """Test that recalculating overwrites the cache"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name

        try:
            analyzer = MetricsAnalyzer(db_path)

            # First calculation
            analyzer.calculate_velocity(
                step_number=1,
                current_posts=10,
                previous_posts=5,
                step_duration_s=5.0
            )

            # Second calculation (different values)
            analyzer.calculate_velocity(
                step_number=1,
                current_posts=20,
                previous_posts=10,
                step_duration_s=2.0
            )

            # Should get the latest value
            cached = analyzer.get_cached_velocity(step_number=1)
            assert cached["velocity"] == 5.0  # 10 posts / 2 seconds

        finally:
            os.unlink(db_path)

    def test_cache_cleanup(self):
        """Test that old cache entries are cleaned up"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name

        try:
            analyzer = MetricsAnalyzer(db_path, cache_size=3)

            # Add 5 metrics
            for i in range(5):
                analyzer.calculate_velocity(
                    step_number=i,
                    current_posts=10 + i,
                    previous_posts=5 + i,
                    step_duration_s=5.0
                )

            # Check that only 3 entries remain
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM metrics_cache WHERE metric_type='velocity'")
            count = cursor.fetchone()[0]
            conn.close()

            assert count == 3

        finally:
            os.unlink(db_path)

    def test_get_latest_metrics(self):
        """Test getting all metrics for a step"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name

        try:
            # Setup test database
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE trace (
                    user_id INTEGER,
                    created_at DATETIME,
                    action TEXT,
                    info TEXT,
                    PRIMARY KEY(user_id, created_at, action, info)
                )
            """)

            now = datetime.now()
            actions = [
                (1, now.isoformat(), "refresh", "info1"),
            ]
            cursor.executemany("INSERT INTO trace VALUES (?, ?, ?, ?)", actions)
            conn.commit()
            conn.close()

            analyzer = MetricsAnalyzer(db_path)

            # Calculate both metrics
            analyzer.calculate_velocity(
                step_number=1,
                current_posts=10,
                previous_posts=5,
                step_duration_s=5.0
            )
            analyzer.calculate_herd_hhi(step_number=1)

            # Get all metrics
            metrics = analyzer.get_latest_metrics(step_number=1)

            assert "velocity" in metrics
            assert "herd_hhi" in metrics
            assert metrics["velocity"]["velocity"] == 1.0
            assert "herd_hhi" in metrics["herd_hhi"]

        finally:
            os.unlink(db_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
