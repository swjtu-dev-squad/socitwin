"""
Facebook 议题数据采集脚本。

运行示例:
    cd backend
    uv run python scripts/datasets/fetch_facebook_data.py
    uv run python scripts/datasets/fetch_facebook_data.py --preview --topics "climate change" "AI ethics"
    uv run python scripts/datasets/fetch_facebook_data.py --topics "climate change" "remote work" --max-posts 10
    uv run python scripts/datasets/fetch_facebook_data.py --topics "climate change" --max-posts 10 --max-replies-per-post 5

参数说明:
    --topics
        指定 Facebook 搜索词列表。不传时使用脚本内置默认议题。
    --max-topics
        未传 --topics 时，从默认议题中取前 N 个。
    --max-posts
        每个议题抓取的帖子上限。
    --max-replies-per-post
        每条帖子抓取的评论 / 回复上限，默认 0，不抓评论。
    --search-type
        Facebook 搜索类型，默认 latest。
    --days-back
        默认 0，不自动加日期范围。需要限制时间时传具体天数。
    --start-date / --end-date
        日期过滤，格式 YYYY-MM-DD。显式传 --start-date 时优先使用该值。
    --preview
        只输出结构化 JSON，不写数据库。

写库说明:
    脚本固定写入 backend/data/datasets/oasis_datasets.db。
    每次运行前只清空 platform=facebook 的旧数据。
"""

import argparse
import json
import sys
from pathlib import Path

from facebook.dataset_collector import (
    DEFAULT_DAYS_BACK,
    DEFAULT_MAX_POSTS,
    DEFAULT_MAX_REPLIES_PER_POST,
    DEFAULT_MAX_TOPICS,
    DEFAULT_SEARCH_TYPE,
    run_fetch_pipeline,
)
from utils.facebook_dataset_writer import import_facebook_payload_to_sqlite

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_DB_PATH = BACKEND_ROOT / "data" / "datasets" / "oasis_datasets.db"


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="抓取 Facebook 搜索帖子并写入统一 SQLite 数据库")
    parser.add_argument("--preview", action="store_true", help="只输出抓取结果 JSON，不写入 SQLite")
    parser.add_argument(
        "--topics",
        nargs="*",
        help="要抓取的 Facebook 搜索词；默认使用脚本内置公共议题",
    )
    parser.add_argument(
        "--max-topics",
        type=int,
        default=DEFAULT_MAX_TOPICS,
        help=f"未传 --topics 时，默认 topic 数量上限，默认 {DEFAULT_MAX_TOPICS}",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=DEFAULT_MAX_POSTS,
        help=f"每个 topic 抓取的帖子上限，默认 {DEFAULT_MAX_POSTS}",
    )
    parser.add_argument(
        "--max-replies-per-post",
        type=int,
        default=DEFAULT_MAX_REPLIES_PER_POST,
        help=f"每条帖子抓取的评论 / 回复上限，默认 {DEFAULT_MAX_REPLIES_PER_POST}",
    )
    parser.add_argument(
        "--search-type",
        default=DEFAULT_SEARCH_TYPE,
        choices=["latest", "top"],
        help=f"Facebook 搜索类型，默认 {DEFAULT_SEARCH_TYPE}",
    )
    parser.add_argument("--start-date", help="开始日期，格式 YYYY-MM-DD")
    parser.add_argument("--end-date", help="结束日期，格式 YYYY-MM-DD")
    parser.add_argument(
        "--days-back",
        type=int,
        default=DEFAULT_DAYS_BACK,
        help=f"未传 --start-date 时抓最近 N 天，0 表示不自动加日期范围，默认 {DEFAULT_DAYS_BACK}",
    )
    return parser


def _run_cli(argv: list[str]) -> int:
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    fetch_options = {
        "topics": args.topics or [],
        "max_topics": args.max_topics,
        "max_posts": args.max_posts,
        "max_replies_per_post": args.max_replies_per_post,
        "search_type": args.search_type,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "days_back": args.days_back,
    }

    try:
        payload = run_fetch_pipeline(
            topics=args.topics,
            max_topics=args.max_topics,
            max_posts=args.max_posts,
            max_replies_per_post=args.max_replies_per_post,
            search_type=args.search_type,
            start_date=args.start_date,
            end_date=args.end_date,
            days_back=args.days_back,
        )
        if args.preview:
            print(json.dumps(payload, ensure_ascii=False), flush=True)
        else:
            result = import_facebook_payload_to_sqlite(
                payload=payload,
                fetch_options=fetch_options,
                db_path=DEFAULT_DB_PATH.resolve(),
            )
            print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        error_payload = (
            {
                "error": str(exc),
                "type": type(exc).__name__,
            }
            if args.preview
            else {
                "status": "error",
                "status_code": 500,
                "type": type(exc).__name__,
                "message": str(exc),
            }
        )
        print(json.dumps(error_payload, ensure_ascii=False), flush=True)
        return 1


def main() -> int:
    return _run_cli(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
