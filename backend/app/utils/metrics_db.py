"""
Metrics Database Utilities - 指标数据库持久化工具

提供指标历史记录的创建、写入和查询功能。
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


# SQL statements to create metrics history table
METRICS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS metrics_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_number INTEGER NOT NULL,
    metric_type TEXT NOT NULL,
    metric_data JSON NOT NULL,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(step_number) REFERENCES simulation_step(step_id)
);

CREATE INDEX IF NOT EXISTS idx_metrics_step ON metrics_history(step_number);
CREATE INDEX IF NOT EXISTS idx_metrics_type ON metrics_history(metric_type);
CREATE INDEX IF NOT EXISTS idx_metrics_calculated_at ON metrics_history(calculated_at);
"""


def create_metrics_table(db_path: str) -> bool:
    """
    为指定数据库创建指标历史表

    Args:
        db_path: SQLite数据库文件路径

    Returns:
        bool: 成功返回True，失败返回False
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            # 执行多条SQL语句
            for statement in METRICS_TABLE_SQL.split(';'):
                statement = statement.strip()
                if statement and not statement.startswith('CREATE INDEX'):
                    # 跳过空行和CREATE INDEX（它们在同一个字符串中）
                    if 'CREATE TABLE' in statement or 'CREATE INDEX' in statement:
                        cursor.execute(statement)

            conn.commit()
            logger.info(f"Metrics table created successfully: {db_path}")
            return True

    except sqlite3.Error as e:
        logger.error(f"Failed to create metrics table: {e}")
        return False


def save_metrics(
    db_path: str,
    step_number: int,
    metric_type: str,
    metric_data: Any
) -> bool:
    """
    保存指标到数据库

    Args:
        db_path: 数据库路径
        step_number: 步骤编号
        metric_type: 指标类型 ('propagation', 'polarization', 'herd_effect')
        metric_data: 指标数据（可以是dict或Pydantic模型）

    Returns:
        bool: 成功返回True
    """
    try:
        # 确保表存在
        create_metrics_table(db_path)

        # 转换为JSON
        if hasattr(metric_data, 'model_dump'):
            # Pydantic model - 使用mode='json'自动序列化datetime
            data_dict = metric_data.model_dump(mode='json')
            data_json = json.dumps(data_dict, ensure_ascii=False)
        elif isinstance(metric_data, dict):
            # Dict - 使用自定义编码器处理datetime
            def datetime_handler(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(repr(obj) + " is not JSON serializable")

            data_json = json.dumps(metric_data, ensure_ascii=False, default=datetime_handler)
        else:
            logger.error(f"Unsupported metric data type: {type(metric_data)}")
            return False

        # 写入数据库
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO metrics_history (step_number, metric_type, metric_data)
                VALUES (?, ?, ?)
            """, (step_number, metric_type, data_json))
            conn.commit()

        logger.debug(
            f"Saved {metric_type} metrics at step {step_number}"
        )
        return True

    except (sqlite3.Error, TypeError) as e:
        logger.error(f"Failed to save metrics: {e}")
        return False


def get_metrics_history(
    db_path: str,
    metric_type: Optional[str] = None,
    step_from: Optional[int] = None,
    step_to: Optional[int] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    查询指标历史记录

    Args:
        db_path: 数据库路径
        metric_type: 指标类型过滤，None表示全部
        step_from: 起始步骤，None表示不限
        step_to: 结束步骤，None表示不限
        limit: 返回数量限制

    Returns:
        指标历史列表
    """
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 构建查询
            query = "SELECT * FROM metrics_history WHERE 1=1"
            params = []

            if metric_type:
                query += " AND metric_type = ?"
                params.append(metric_type)

            if step_from is not None:
                query += " AND step_number >= ?"
                params.append(step_from)

            if step_to is not None:
                query += " AND step_number <= ?"
                params.append(step_to)

            query += " ORDER BY step_number DESC, calculated_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)

            results = []
            for row in cursor.fetchall():
                results.append({
                    'id': row['id'],
                    'step_number': row['step_number'],
                    'metric_type': row['metric_type'],
                    'metric_data': json.loads(row['metric_data']),
                    'calculated_at': row['calculated_at']
                })

            return results

    except sqlite3.Error as e:
        logger.error(f"Failed to query metrics history: {e}")
        return []


def get_latest_metrics(
    db_path: str,
    metric_type: str
) -> Optional[Dict[str, Any]]:
    """
    获取最新的指标记录

    Args:
        db_path: 数据库路径
        metric_type: 指标类型

    Returns:
        最新指标数据，如果不存在返回None
    """
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM metrics_history
                WHERE metric_type = ?
                ORDER BY step_number DESC, calculated_at DESC
                LIMIT 1
            """, (metric_type,))

            row = cursor.fetchone()
            if row:
                return {
                    'id': row['id'],
                    'step_number': row['step_number'],
                    'metric_type': row['metric_type'],
                    'metric_data': json.loads(row['metric_data']),
                    'calculated_at': row['calculated_at']
                }
            return None

    except sqlite3.Error as e:
        logger.error(f"Failed to get latest metrics: {e}")
        return None


def ensure_oasis_databases_have_metrics_tables(
    db_directory: str = "./data/simulations"
) -> Dict[str, bool]:
    """
    确保所有OASIS数据库都有指标表

    Args:
        db_directory: 数据库目录

    Returns:
        数据库文件名 -> 成功状态的字典
    """
    results = {}
    db_files = list(Path(db_directory).glob("*.db"))

    logger.info(f"Found {len(db_files)} databases for metrics table creation")

    for db_file in db_files:
        db_path = str(db_file)
        results[db_file.name] = create_metrics_table(db_path)

    success_count = sum(1 for status in results.values() if status)
    logger.info(f"Metrics tables created: {success_count}/{len(results)}")

    return results


def main():
    """命令行入口"""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        from app.core.config import get_settings
        settings = get_settings()
        db_directory = settings.OASIS_DB_PATH
        db_files = list(Path(db_directory).glob("*.db"))
        if not db_files:
            logger.error(f"No databases found in {db_directory}")
            sys.exit(1)
        db_path = str(db_files[0])

    logger.info(f"Creating metrics table in: {db_path}")

    if create_metrics_table(db_path):
        print("✓ Metrics table created successfully")
        sys.exit(0)
    else:
        print("✗ Failed to create metrics table")
        sys.exit(1)


if __name__ == "__main__":
    main()
