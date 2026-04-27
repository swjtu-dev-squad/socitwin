#!/usr/bin/env python3
"""主CLI入口 - 集成DatabaseClient、LLMAnalyzer、XPublisher完成对抗性观点生成和发布流程"""

import argparse
import logging
import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

try:
    from database import DatabaseClient
    from llm_analyzer import LLMAnalyzer
    from x_publisher import XPublisher
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保以下模块在相同目录下:")
    print("  - database.py\n  - llm_analyzer.py\n  - x_publisher.py")
    print("\n请安装所需依赖:\n  pip install openai tweepy")
    sys.exit(1)


@dataclass
class Config:
    """配置数据类"""
    deepseek_api_key: str
    x_api_key: str
    x_api_key_secret: str
    x_access_token: str
    x_access_token_secret: str
    oasis_db_path: str


def load_config() -> Config:
    """从.env文件加载配置"""
    env_paths = []
    if env_file_env := os.environ.get("ENV_FILE"):
        env_paths.append(Path(env_file_env))
    env_paths += [
        Path(__file__).parent.parent / ".env",
        Path.cwd() / ".env",
        Path(__file__).parent.parent.parent / "backend" / ".env",
    ]

    env_file = None
    for path in env_paths:
        if path.exists():
            env_file = path
            logging.info(f"找到.env文件: {env_file}")
            break

    if not env_file:
        raise FileNotFoundError("未找到.env文件，请确保配置文件存在")

    config_dict = {}
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                config_dict[key.strip()] = value.strip()

    required_keys = [
        'DEEPSEEK_API_KEY', 'X_API_KEY', 'X_API_KEY_SECRET',
        'X_ACCESS_TOKEN', 'X_ACCESS_TOKEN_SECRET',
    ]
    missing_keys = [key for key in required_keys if key not in config_dict]
    if missing_keys:
        raise ValueError(f"缺少必需的配置项: {', '.join(missing_keys)}")

    oasis_db_path = config_dict.get('OASIS_DB_PATH', './data/datasets/oasis_datasets.db')
    if not Path(oasis_db_path).is_absolute():
        oasis_db_path = str(env_file.parent / oasis_db_path)

    return Config(
        deepseek_api_key=config_dict['DEEPSEEK_API_KEY'],
        x_api_key=config_dict['X_API_KEY'],
        x_api_key_secret=config_dict['X_API_KEY_SECRET'],
        x_access_token=config_dict['X_ACCESS_TOKEN'],
        x_access_token_secret=config_dict['X_ACCESS_TOKEN_SECRET'],
        oasis_db_path=oasis_db_path
    )


def setup_logging(verbose: bool = False) -> None:
    """设置日志配置"""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('contrarian_agent.log', encoding='utf-8')
        ]
    )


def parse_arguments() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='对抗性观点Agent - 分析Twitter话题多数观点并生成反驳论点',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  %(prog)s --topic "climate_change" --sample-size 20
  %(prog)s --topic "ai_ethics" --dry-run --verbose
  %(prog)s --topic "data_privacy" --db-path /custom/path/to/database.db"""
    )

    parser.add_argument('--topic', required=True, help='话题key（数据库中的话题关键词）')
    parser.add_argument('--sample-size', type=int, default=20, help='样本大小（默认: 20）')
    parser.add_argument('--dry-run', action='store_true', help='干运行模式，不实际发布推文')
    parser.add_argument('--db-path', help='自定义数据库路径（覆盖配置中的路径）')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出模式')
    parser.add_argument('--platform', default='twitter', choices=['twitter', 'reddit'], help='平台类型（默认: twitter）')

    return parser.parse_args()


def main() -> None:
    """主入口点"""
    args = parse_arguments()
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("对抗性观点Agent启动")
    logger.info("=" * 60)
    logger.info(f"话题: {args.topic} | 样本大小: {args.sample_size} | 平台: {args.platform} | Dry-run: {args.dry_run}")

    try:
        logger.info("步骤1: 加载配置...")
        config = load_config()
        logger.info("✓ 配置加载成功")

        db_path = args.db_path or config.oasis_db_path
        logger.info(f"数据库路径: {db_path}")

        logger.info("步骤2: 初始化模块客户端...")
        db_client = DatabaseClient(db_path)
        logger.info("✓ DatabaseClient初始化成功")

        llm_analyzer = LLMAnalyzer(config.deepseek_api_key)
        logger.info("✓ LLMAnalyzer初始化成功")

        x_publisher = XPublisher(
            api_key=config.x_api_key,
            api_key_secret=config.x_api_key_secret,
            access_token=config.x_access_token,
            access_token_secret=config.x_access_token_secret,
            dry_run=args.dry_run
        )
        logger.info("✓ XPublisher初始化成功")

        logger.info("步骤3: 测试连接...")
        if db_client.test_connection():
            logger.info("✓ 数据库连接成功")
        else:
            logger.error("✗ 数据库连接失败")
            sys.exit(1)

        if not args.dry_run:
            if x_publisher.test_connection():
                logger.info("✓ X平台连接成功")
            else:
                logger.warning("⚠ X平台连接测试失败，但继续执行...")

        logger.info("步骤4: 获取话题信息...")
        topic_info = db_client.get_topic_info(args.topic, args.platform)
        if not topic_info:
            logger.error(f"✗ 未找到话题: {args.topic}")
            sys.exit(1)
        logger.info(f"✓ 话题: {topic_info.get('topic_label', 'N/A')} | 帖子: {topic_info.get('post_count', 0)} | 回复: {topic_info.get('reply_count', 0)}")

        logger.info("步骤5: 抽样帖子样本...")
        samples = db_client.get_majority_opinion_samples(
            args.topic, platform=args.platform, sample_size=args.sample_size
        )
        if not samples:
            logger.error("✗ 未找到有效的帖子样本")
            sys.exit(1)
        logger.info(f"✓ 成功抽取 {len(samples)} 个样本")

        logger.info("步骤6: 分析多数观点...")
        majority_opinion = llm_analyzer.analyze_majority_opinion(samples)
        logger.info(f"✓ {majority_opinion}")

        logger.info("步骤7: 生成反驳论点...")
        topic_label = topic_info.get('topic_label', args.topic)
        counterargument = llm_analyzer.generate_counterargument(majority_opinion, topic_label)
        logger.info(f"✓ 反驳论点 ({len(counterargument)} 字符): {counterargument}")

        logger.info("步骤8: 发布推文...")
        result = x_publisher.post_tweet(counterargument)
        if result['success']:
            if args.dry_run:
                logger.info(f"✓ Dry-run: {result['text']}")
            else:
                logger.info(f"✓ 推文发布成功 ID={result['id']} https://x.com/user/status/{result['id']}")

        logger.info("=" * 60)
        logger.info("✓ 执行完成!")
        logger.info("=" * 60)

    except KeyboardInterrupt:
        logger.info("\n⚠ 用户中断执行")
        sys.exit(130)
    except Exception as e:
        logger.error(f"✗ 执行失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
