"""
清空指定平台的数据

用法：
    uv run python scripts/datasets/utils/clear_platform_data.py instagram
    uv run python scripts/datasets/utils/clear_platform_data.py twitter
"""

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATASETS_DIR = SCRIPT_DIR.parent
BACKEND_ROOT = DATASETS_DIR.parents[1]
DEFAULT_DB_PATH = BACKEND_ROOT / "data" / "datasets" / "oasis_datasets.db"
from utils.db_utils import DatasetDB
# 将 scripts/datasets 加入模块搜索路径
sys.path.insert(0, str(DATASETS_DIR))



def clear_platform(platform: str, db_path: Path, confirm: bool = False) -> dict:
    """清空指定平台的数据"""

    with DatasetDB(db_path) as db:
        db.ensure_schema()

        # 统计要删除的数据
        stats = {}
        for table in ["users", "contents", "topics", "content_topics", "user_topics"]:
            cursor = db.conn.execute(f"SELECT COUNT(*) FROM {table} WHERE platform = ?", (platform,))
            stats[table] = cursor.fetchone()[0]

        total = sum(stats.values())
        if total == 0:
            return {"status": "no_data", "platform": platform, "stats": stats}

        print(f"平台 [{platform}] 数据统计:")
        for table, count in stats.items():
            print(f"  {table}: {count}")
        print(f"总计: {total} 条")

        if not confirm:
            response = input("\n确认删除? (yes/no): ")
            if response.lower() != "yes":
                return {"status": "cancelled", "platform": platform}

        # 删除数据
        db.begin_transaction()
        db.conn.execute("DELETE FROM user_topics WHERE platform = ?", (platform,))
        db.conn.execute("DELETE FROM content_topics WHERE platform = ?", (platform,))
        db.conn.execute("DELETE FROM contents WHERE platform = ?", (platform,))
        db.conn.execute("DELETE FROM topics WHERE platform = ?", (platform,))
        db.conn.execute("DELETE FROM users WHERE platform = ?", (platform,))
        db.conn.commit()

        return {"status": "success", "platform": platform, "deleted": stats}


def main():
    parser = argparse.ArgumentParser(description="清空指定平台的数据")
    parser.add_argument("platform", help="平台名称 (instagram/twitter)")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("-y", "--yes", action="store_true", help="跳过确认")
    args = parser.parse_args()

    result = clear_platform(args.platform, args.db_path, confirm=args.yes)
    print(f"\n{result}")


if __name__ == "__main__":
    main()
