#!/usr/bin/env python3
"""主CLI入口 - 集成DatabaseClient、LLMAnalyzer、XPublisher完成多角度观点生成和发布流程"""

import argparse
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from database import DatabaseClient
    from llm_analyzer import LLMAnalyzer
    from prompt_loader import PromptLoader
    from x_publisher import XPublisher
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保以下模块在相同目录下:")
    print("  - database.py\n  - llm_analyzer.py\n  - x_publisher.py\n  - prompt_loader.py")
    print("\n请安装所需依赖:\n  pip install openai tweepy pyyaml")
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

    try:
        from dotenv import dotenv_values
        config_dict = dotenv_values(env_file)
    except ImportError:
        config_dict = {}
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    config_dict[key.strip()] = value.strip().strip('"').strip("'")

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
    prompt_loader = PromptLoader()
    perspectives = prompt_loader.list_perspectives()
    perspective_keys = [p["key"] for p in perspectives]

    parser = argparse.ArgumentParser(
        description='多角度观点Agent - 分析话题多数观点并以选定角度生成内容',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""示例:
  %(prog)s --topic "climate_change" --sample-size 20
  %(prog)s --topic "ai_ethics" --perspective neutral_analysis --dry-run
  %(prog)s --topic "data_privacy" --db-path /custom/path/to/database.db
  %(prog)s --list-perspectives"""
    )

    parser.add_argument('--topic', help='话题key（数据库中的话题关键词）')
    parser.add_argument('--sample-size', type=int, default=20, help='样本大小（默认: 20）')
    parser.add_argument('--dry-run', action='store_true', help='干运行模式，不实际发布推文')
    parser.add_argument('--db-path', help='自定义数据库路径（覆盖配置中的路径）')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出模式')
    parser.add_argument('--platform', default='twitter', choices=['twitter', 'reddit'],
                        help='平台类型（默认: twitter）')
    keys_str = ", ".join(perspective_keys)
    parser.add_argument('--perspective', default='counterargument', choices=perspective_keys,
                        help=f'观点角度（默认: counterargument）。可选: {keys_str}')
    parser.add_argument('--list-perspectives', action='store_true',
                        help='列出所有可用观点角度并退出')

    return parser.parse_args()


def display_perspectives():
    """显示所有可用观点角度"""
    prompt_loader = PromptLoader()
    perspectives = prompt_loader.list_perspectives()
    print(f"\n可用观点角度 ({len(perspectives)}):")
    print("-" * 50)
    for p in perspectives:
        print(f"  [{p['key']}] {p['label']}")
        print(f"       {p['description']}")
    print()


def main() -> None:
    """主入口点"""
    args = parse_arguments()

    if args.list_perspectives:
        display_perspectives()
        return

    if not args.topic:
        print("错误: 需要指定 --topic 参数（或使用 --list-perspectives 查看可用角度）")
        sys.exit(1)

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("多角度观点Agent启动")
    logger.info("=" * 60)
    logger.info("话题: %s | 样本: %d | 平台: %s | 角度: %s | Dry-run: %s",
                args.topic, args.sample_size, args.platform, args.perspective, args.dry_run)

    try:
        logger.info("步骤1: 加载配置...")
        config = load_config()
        logger.info("✓ 配置加载成功")

        db_path = args.db_path or config.oasis_db_path
        logger.info("数据库路径: %s", db_path)

        logger.info("步骤2: 初始化模块客户端...")
        prompt_loader = PromptLoader()
        db_client = DatabaseClient(db_path)
        logger.info("✓ DatabaseClient初始化成功")

        llm_analyzer = LLMAnalyzer(config.deepseek_api_key, prompt_loader=prompt_loader)
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
            logger.error("✗ 未找到话题: %s", args.topic)
            sys.exit(1)
        logger.info("✓ 话题: %s | 帖子: %d | 回复: %d",
                    topic_info.get('topic_label', 'N/A'),
                    topic_info.get('post_count', 0),
                    topic_info.get('reply_count', 0))

        logger.info("步骤5: 抽样帖子样本...")
        samples = db_client.get_majority_opinion_samples(
            args.topic, platform=args.platform, sample_size=args.sample_size
        )
        if not samples:
            logger.error("✗ 未找到有效的帖子样本")
            sys.exit(1)
        logger.info("✓ 成功抽取 %d 个样本", len(samples))

        logger.info("步骤6: 分析多数观点...")
        majority_opinion = llm_analyzer.analyze_majority_opinion(samples)
        logger.info("✓ %s", majority_opinion)

        logger.info("步骤7: 生成观点（角度: %s）...", args.perspective)
        topic_label = topic_info.get('topic_label', args.topic)
        content = llm_analyzer.generate_perspective(
            majority_opinion, topic_label, perspective=args.perspective
        )
        logger.info("✓ 生成内容 (%d 字符): %s", len(content), content)

        logger.info("步骤8: 发布推文...")
        result = x_publisher.post_tweet(content)
        if result['success']:
            if args.dry_run:
                logger.info("✓ Dry-run: %s", result['text'])
            else:
                logger.info("✓ 推文发布成功 ID=%s https://x.com/user/status/%s",
                            result['id'], result['id'])

        logger.info("=" * 60)
        logger.info("✓ 执行完成!")
        logger.info("=" * 60)

    except KeyboardInterrupt:
        logger.info("\n⚠ 用户中断执行")
        sys.exit(130)
    except Exception as e:
        logger.error("✗ 执行失败: %s", e)
        import traceback
        logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
