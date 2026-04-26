"""
Instagram 议题数据采集脚本。

运行示例:
    cd backend
    uv run python scripts/datasets/fetch_instagram_data.py --preview --topics climatechange aiethics
    uv run python scripts/datasets/fetch_instagram_data.py --topics climatechange artificialintelligence remotework --max-posts 10
    uv run python scripts/datasets/fetch_instagram_data.py --topics climatechange --max-posts 10 --max-replies-per-post 5

参数说明:
    --topics
        指定 hashtag 列表，不带 #。不传时使用脚本内置默认议题。
    --max-topics
        未传 --topics 时，从默认议题中取前 N 个。
    --max-posts
        每个议题抓取的帖子上限。
    --max-replies-per-post
        每条帖子抓取的评论 / 回复上限，默认 0，不抓评论。
    --only-posts-newer-than
        Apify 的时间过滤参数，例如 7 days、30 days、2026-04-01。
    --preview
        只输出结构化 JSON，不写数据库。

写库说明:
    脚本固定写入 backend/data/datasets/oasis_datasets.db。
    每次运行前只清空 platform=instagram 的旧数据，不会删除或覆盖已有的 twitter 数据。
"""

import argparse
import json
import sys
from pathlib import Path

from instagram.dataset_collector import (
    DEFAULT_MAX_POSTS,
    DEFAULT_MAX_REPLIES_PER_POST,
    DEFAULT_MAX_TOPICS,
    DEFAULT_ONLY_POSTS_NEWER_THAN,
    run_fetch_pipeline,
)
from utils.instagram_dataset_writer import import_instagram_payload_to_sqlite

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_DB_PATH = BACKEND_ROOT / "data" / "datasets" / "oasis_datasets.db"


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="抓取 Instagram hashtag 数据并写入统一 SQLite 数据库")
    parser.add_argument("--preview", action="store_true", help="只输出抓取结果 JSON，不写入 SQLite")
    parser.add_argument(
        "--topics",
        nargs="*",
        help="要抓取的 hashtag 列表，不带 #；默认使用脚本内置公共议题",
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
        "--only-posts-newer-than",
        default=DEFAULT_ONLY_POSTS_NEWER_THAN,
        help=f"Apify 的 onlyPostsNewerThan 过滤，默认 {DEFAULT_ONLY_POSTS_NEWER_THAN}",
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
        "only_posts_newer_than": args.only_posts_newer_than,
    }

    try:
        payload = run_fetch_pipeline(
            topics=args.topics,
            max_topics=args.max_topics,
            max_posts=args.max_posts,
            max_replies_per_post=args.max_replies_per_post,
            only_posts_newer_than=args.only_posts_newer_than,
        )
        if args.preview:
            print(json.dumps(payload, ensure_ascii=False), flush=True)
        else:
            result = import_instagram_payload_to_sqlite(
                payload=payload,
                fetch_options=fetch_options,
                db_path=DEFAULT_DB_PATH.resolve(),
            )
            print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0
    except Exception as e:
        error_payload = {
            "error": str(e),
            "type": type(e).__name__,
        } if args.preview else {
            "status": "error",
            "status_code": 500,
            "type": type(e).__name__,
            "message": str(e),
        }
        print(json.dumps(error_payload, ensure_ascii=False), flush=True)
        return 1


def main() -> int:
    return _run_cli(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
