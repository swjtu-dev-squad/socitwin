#!/usr/bin/env python3
"""实时获取热点话题 → 对抗性观点生成 → 发帖"""

import argparse
import logging
import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from llm_analyzer import LLMAnalyzer
from x_publisher import XPublisher
from contrarian_agent import load_config

logger = logging.getLogger(__name__)

BACKEND_URL = "http://localhost:8000"


def _build_url_opener() -> urllib.request.OpenerDirector:
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or ""
    if proxy:
        handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        return urllib.request.build_opener(handler)
    return urllib.request.build_opener()


def fetch_trending_from_api(max_per_axis: int = 5, max_age_hours: int = 24) -> list[dict]:
    """调用 backend /api/topics/twitter/trending-topics 获取实时热点"""
    url = (
        f"{BACKEND_URL}/api/topics/twitter/trending-topics"
        f"?max_per_axis={max_per_axis}&max_age_hours={max_age_hours}"
    )
    try:
        opener = _build_url_opener()
        resp = opener.open(url, timeout=15)
        data = json.loads(resp.read().decode())
        return data.get("topics") if data.get("success") else []
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as e:
        logger.warning("Backend API 不可用: %s", e)
        return []


def generate_trending_from_llm(analyzer: LLMAnalyzer) -> list[dict]:
    """回退方案：让 LLM 生成当前各领域热点话题列表"""
    prompt = (
        "你是一个社交媒体趋势分析师。请列出当前 X (Twitter) 上最受关注的 15 个热点话题，"
        "涵盖政治、经济、科技、社会、文化等领域。\n\n"
        "请返回 JSON 数组，格式如下（不要加解释）：\n"
        '[\n'
        '  {"name": "话题名称", "axis": "所属领域", "summary": "一句话说明为什么这个话题热门"},\n'
        '  ...\n'
        ']\n\n'
        "要求：\n"
        "1. 话题必须是当前真实存在的热门讨论\n"
        "2. 每个话题用英文名称，但可以涉及全球任何地区\n"
        "3. axis 字段从 politics / economy / technology / society / culture 中选择\n"
        "4. summary 用中文描述热度原因"
    )
    messages = [
        {"role": "system", "content": "你是 X/Twitter 趋势分析师，熟悉全球热点话题。"},
        {"role": "user", "content": prompt},
    ]
    raw = analyzer._call_api_with_retry(messages, temperature=0.5, max_tokens=2000)
    if not raw:
        raise RuntimeError("LLM 未能生成热点话题列表")

    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()

    try:
        topics = json.loads(raw)
        if isinstance(topics, list):
            for i, t in enumerate(topics, 1):
                t.setdefault("trend_rank", i)
            return topics
    except json.JSONDecodeError:
        pass

    import re
    match = re.search(r"\[.*?\]", raw, re.DOTALL)
    if match:
        try:
            topics = json.loads(match.group())
            if isinstance(topics, list):
                for i, t in enumerate(topics, 1):
                    t.setdefault("trend_rank", i)
                return topics
        except json.JSONDecodeError:
            pass

    raise RuntimeError(f"无法解析 LLM 返回的话题列表:\n{raw[:500]}")


def display_topics(topics: list[dict]) -> None:
    """打印话题列表供用户选择"""
    print(f"\n{'='*70}")
    print(f"  当前热点话题 ({len(topics)} 个)")
    print(f"{'='*70}")
    for t in topics:
        axis = t.get("axis", "?")
        rank = t.get("trend_rank", "?")
        name = t.get("name", "?")
        summary = t.get("summary", "")
        print(f"  [{rank}] ({axis}) {name}")
        if summary:
            print(f"       {summary}")
    print()


def select_topic(topics: list[dict], auto: bool = False, topic_name: Optional[str] = None) -> dict:
    """选择要处理的话题"""
    if topic_name:
        for t in topics:
            if topic_name.lower() in t.get("name", "").lower():
                return t
        return {"name": topic_name, "axis": "custom", "trend_rank": 0, "summary": ""}

    if auto:
        chosen = topics[0]
        print(f"  → 自动选择: [{chosen.get('trend_rank')}] {chosen.get('name')}\n")
        return chosen

    while True:
        try:
            choice = input("  请输入话题编号 (1-{}): ".format(len(topics))).strip()
            idx = int(choice) - 1
            if 0 <= idx < len(topics):
                return topics[idx]
        except (ValueError, IndexError):
            pass
        print("  输入无效，请重新输入。")


def infer_majority_opinion(analyzer: LLMAnalyzer, topic: dict) -> str:
    """让 LLM 推断该话题的主流观点"""
    name = topic.get("name", "this topic")
    summary = topic.get("summary", "")

    prompt = f"关于当前热点话题「{name}」，请分析 X (Twitter) 上大多数用户的普遍看法。\n"
    if summary:
        prompt += f"背景：{summary}\n\n"
    prompt += (
        "请从以下角度综合判断主流舆论：\n"
        "1. 媒体和意见领袖的主流叙事\n"
        "2. 普通用户最常见的立场\n"
        "3. 被广泛认可的核心假设\n\n"
        "用 2-3 句话总结多数观点（中文）。"
    )

    messages = [
        {"role": "system", "content": "你是一名社交媒体分析师，擅长从海量信息中识别主流舆论。"},
        {"role": "user", "content": prompt},
    ]
    result = analyzer._call_api_with_retry(messages, temperature=0.3, max_tokens=300)
    if not result:
        raise RuntimeError("推断多数观点失败")
    return result


def generate_contrarian_view(analyzer: LLMAnalyzer, majority_opinion: str, topic_name: str) -> str:
    """生成对抗性观点"""
    return analyzer.generate_counterargument(majority_opinion, topic_name)


def parse_args():
    parser = argparse.ArgumentParser(description="Live Contrarian Agent - 实时热点 → 对抗性观点 → 发帖")
    parser.add_argument("--topic", help="直接指定话题名称（跳过选择）")
    parser.add_argument("--auto", action="store_true", help="自动选择第一个话题")
    parser.add_argument("--dry-run", action="store_true", help="试运行模式，不实际发帖")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    parser.add_argument("--no-api", action="store_true", help="跳过 backend API，直接使用 LLM 生成话题")
    return parser.parse_args()


def main():
    args = parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout)])

    config = load_config()
    analyzer = LLMAnalyzer(config.deepseek_api_key)
    x_pub = XPublisher(
        api_key=config.x_api_key,
        api_key_secret=config.x_api_key_secret,
        access_token=config.x_access_token,
        access_token_secret=config.x_access_token_secret,
        dry_run=args.dry_run,
    )

    print("\n" + "=" * 60)
    print("  步骤 1: 获取当前热点话题")
    print("=" * 60)

    topics = []
    if not args.no_api:
        print("  → 尝试从 backend API 获取...")
        topics = fetch_trending_from_api()
        if topics:
            print(f"  ✓ 成功获取 {len(topics)} 个热点话题\n")
        else:
            print("  ⚠ Backend API 未返回数据，切换到 LLM 生成...\n")

    if not topics:
        print("  → 使用 DeepSeek 生成当前热点话题列表...")
        try:
            topics = generate_trending_from_llm(analyzer)
            print(f"  ✓ LLM 生成了 {len(topics)} 个热点话题\n")
        except RuntimeError as e:
            logger.error(str(e))
            sys.exit(1)

    display_topics(topics)

    print("=" * 60)
    print("  步骤 2: 选择话题")
    print("=" * 60)
    topic = select_topic(topics, auto=args.auto, topic_name=args.topic)
    print(f"  ✓ 已选择: [{topic.get('trend_rank')}] {topic.get('name')}\n")

    print("=" * 60)
    print("  步骤 3: 推断主流观点")
    print("=" * 60)
    try:
        majority = infer_majority_opinion(analyzer, topic)
        print(f"  ✓ 多数观点:\n    {majority}\n")
    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(1)

    print("=" * 60)
    print("  步骤 4: 生成对抗性观点")
    print("=" * 60)
    topic_label = topic.get("name", "trending_topic")
    try:
        counter = generate_contrarian_view(analyzer, majority, topic_label)
        print(f"  ✓ 对抗性观点 ({(len(counter))} 字符):\n    {counter}\n")
    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(1)

    print("=" * 60)
    print("  步骤 5: 发布到 X")
    print("=" * 60)
    try:
        result = x_pub.post_tweet(counter)
        if result["success"]:
            if args.dry_run:
                print(f"  ✓ Dry-run 完成，未实际发布\n  内容: {result['text']}")
            else:
                print(f"  ✓ 推文发布成功!\n  链接: https://x.com/user/status/{result['id']}")
        else:
            print(f"  ✗ 发布失败: {result.get('error', '未知错误')}")
    except Exception as e:
        logger.error(f"发布失败: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("  执行完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
