"""
智能体模板生成器

提供预定义的智能体模板和配置生成功能，
支持快速创建特定类型的智能体群体。
"""

import logging
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentProfile:
    """智能体配置文件"""
    user_name: str
    name: str
    description: str
    bio: Optional[str] = None
    interests: List[str] = field(default_factory=list)
    age: Optional[int] = None
    gender: Optional[str] = None
    mbti: Optional[str] = None
    country: Optional[str] = None
    behavior_profile: Optional[Dict[str, Any]] = None


class AgentTemplates:
    """
    智能体模板集合

    提供各种预定义的智能体类型模板，用于快速生成特定特征的智能体。
    """

    # 科技爱好者模板
    TECH_ENTHUSIAST = {
        "interests": ["AI", "machine learning", "technology", "programming", "gadgets"],
        "behavior": "active",
        "posting_frequency": "high",
        "interaction_style": "technical",
        "description_templates": [
            "Tech enthusiast passionate about {topic}",
            "Software developer interested in {topic}",
            "AI researcher exploring {topic}",
        ]
    }

    # 休闲用户模板
    CASUAL_USER = {
        "interests": ["daily life", "entertainment", "music", "movies", "food"],
        "behavior": "passive",
        "posting_frequency": "low",
        "interaction_style": "casual",
        "description_templates": [
            "Just sharing my daily life",
            "Love {topic} and chilling",
            "Here for entertainment and fun",
        ]
    }

    # 商业专业人士模板
    BUSINESS_PROFESSIONAL = {
        "interests": ["business", "finance", "entrepreneurship", "marketing", "networking"],
        "behavior": "formal",
        "posting_frequency": "medium",
        "interaction_style": "professional",
        "description_templates": [
            "Business professional focused on {topic}",
            "Entrepreneur interested in {topic}",
            "Marketing expert sharing insights on {topic}",
        ]
    }

    # 学生模板
    STUDENT = {
        "interests": ["study", "education", "campus life", "learning", "homework"],
        "behavior": "curious",
        "posting_frequency": "medium",
        "interaction_style": "academic",
        "description_templates": [
            "Student studying {topic}",
            "Learning about {topic}",
            "Here to share my academic journey",
        ]
    }

    # 活动家模板
    ACTIVIST = {
        "interests": ["social justice", "environment", "politics", "activism", "causes"],
        "behavior": "passionate",
        "posting_frequency": "high",
        "interaction_style": "advocacy",
        "description_templates": [
            "Advocate for {topic}",
            "Fighting for {topic} awareness",
            "Social activist focused on {topic}",
        ]
    }

    # 艺术家模板
    ARTIST = {
        "interests": ["art", "design", "creativity", "music", "photography"],
        "behavior": "creative",
        "posting_frequency": "medium",
        "interaction_style": "artistic",
        "description_templates": [
            "Artist exploring {topic}",
            "Creative mind interested in {topic}",
            "Designer working with {topic}",
        ]
    }


class AgentGenerator:
    """
    智能体生成器

    根据模板或自定义配置生成智能体配置文件。
    """

    def __init__(self):
        """初始化生成器"""
        self.templates = AgentTemplates()
        self.names_db = self._load_names_database()

    def _load_names_database(self) -> Dict[str, List[str]]:
        """加载名字数据库"""
        return {
            "male": [
                "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
                "Thomas", "Charles", "Christopher", "Daniel", "Matthew", "Anthony", "Mark"
            ],
            "female": [
                "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica",
                "Sarah", "Karen", "Nancy", "Lisa", "Betty", "Margaret", "Sandra", "Ashley"
            ],
            "last": [
                "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
                "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson"
            ]
        }

    def generate_from_template(
        self,
        template_name: str,
        count: int,
        platform: str = "twitter"
    ) -> List[AgentProfile]:
        """
        从模板生成智能体配置

        Args:
            template_name: 模板名称
            count: 生成数量
            platform: 目标平台

        Returns:
            智能体配置列表
        """
        try:
            template = getattr(self.templates, template_name.upper(), None)
            if not template:
                raise ValueError(f"Template not found: {template_name}")

            profiles = []

            for i in range(count):
                profile = self._generate_profile_from_template(template, i, platform)
                profiles.append(profile)

            logger.info(f"Generated {count} profiles from template: {template_name}")
            return profiles

        except Exception as e:
            logger.error(f"Failed to generate from template: {e}")
            raise

    def _generate_profile_from_template(
        self, template: Dict[str, Any], index: int, platform: str
    ) -> AgentProfile:
        """从模板生成单个配置"""
        # 生成用户名
        user_name = self._generate_username(template["interests"][0], index)

        # 生成姓名
        gender = random.choice(["male", "female"])
        name = self._generate_name(gender)

        # 生成描述
        interest = random.choice(template["interests"])
        description_template = random.choice(template["description_templates"])
        description = description_template.format(topic=interest)

        # 生成其他属性
        bio = self._generate_bio(template, interest)

        return AgentProfile(
            user_name=user_name,
            name=name,
            description=description,
            bio=bio,
            interests=template["interests"],
            behavior_profile={
                "behavior": template["behavior"],
                "posting_frequency": template["posting_frequency"],
                "interaction_style": template["interaction_style"],
            }
        )

    def _generate_username(self, interest: str, index: int) -> str:
        """生成用户名"""
        interest_part = interest.lower().replace(" ", "_")[:10]
        return f"{interest_part}_user_{index}"

    def _generate_name(self, gender: str) -> str:
        """生成姓名"""
        first_name = random.choice(self.names_db[gender])
        last_name = random.choice(self.names_db["last"])
        return f"{first_name} {last_name}"

    def _generate_bio(self, template: Dict[str, Any], interest: str) -> str:
        """生成简介"""
        bios = [
            f"Passionate about {interest}",
            f"Love discussing {interest}",
            f"Sharing thoughts on {interest}",
            f"Here to connect with {interest} enthusiasts",
        ]
        return random.choice(bios)

    def generate_mixed_population(
        self, total_count: int, distribution: Dict[str, int]
    ) -> List[AgentProfile]:
        """
        生成混合类型智能体群体

        Args:
            total_count: 总数量
            distribution: 类型分布 {template_name: count}

        Returns:
            智能体配置列表
        """
        profiles = []
        agent_id = 0

        for template_name, count in distribution.items():
            template_profiles = self.generate_from_template(template_name, count)
            profiles.extend(template_profiles)
            agent_id += count

        # 如果分布总数不匹配，补充随机用户
        if len(profiles) < total_count:
            additional = total_count - len(profiles)
            random_profiles = self.generate_from_template("CASUAL_USER", additional)
            profiles.extend(random_profiles)

        return profiles[:total_count]

    def generate_custom_profile(
        self, custom_config: Dict[str, Any]
    ) -> AgentProfile:
        """
        生成自定义智能体配置

        Args:
            custom_config: 自定义配置

        Returns:
            智能体配置
        """
        return AgentProfile(
            user_name=custom_config.get("user_name", "custom_user"),
            name=custom_config.get("name", "Custom User"),
            description=custom_config.get("description", ""),
            bio=custom_config.get("bio"),
            interests=custom_config.get("interests", []),
            behavior_profile=custom_config.get("behavior_profile"),
        )


class PlatformSpecificGenerator:
    """
    平台特定生成器

    为不同社交平台生成特定格式的智能体配置。
    """

    @staticmethod
    def generate_twitter_csv(profiles: List[AgentProfile], output_path: str):
        """
        生成 Twitter 用户 CSV 文件

        Args:
            profiles: 智能体配置列表
            output_path: 输出文件路径
        """
        import csv

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # 写入表头
            writer.writerow([
                "name", "username", "user_char", "description"
            ])

            # 写入数据
            for profile in profiles:
                writer.writerow([
                    profile.name,
                    profile.user_name,
                    profile.description[:50],  # Twitter 简短描述
                    profile.description
                ])

        logger.info(f"Generated Twitter CSV with {len(profiles)} profiles: {output_path}")

    @staticmethod
    def generate_reddit_json(profiles: List[AgentProfile], output_path: str):
        """
        生成 Reddit 用户 JSON 文件

        Args:
            profiles: 智能体配置列表
            output_path: 输出文件路径
        """
        import json

        reddit_profiles = []

        for profile in profiles:
            reddit_profile = {
                "realname": profile.name,
                "username": profile.user_name,
                "bio": profile.bio or profile.description,
                "persona": profile.description,
                "age": profile.age or random.randint(18, 65),
                "gender": profile.gender or random.choice(["male", "female"]),
                "mbti": profile.mbti or random.choice([
                    "INTJ", "INTP", "ENTJ", "ENTP",
                    "INFJ", "INFP", "ENFJ", "ENFP",
                    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
                    "ISTP", "ISFP", "ESTP", "ESFP"
                ]),
                "country": profile.country or "USA"
            }
            reddit_profiles.append(reddit_profile)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(reddit_profiles, f, indent=2, ensure_ascii=False)

        logger.info(f"Generated Reddit JSON with {len(profiles)} profiles: {output_path}")


# ============================================================================
# 便捷函数
# ============================================================================

def create_quick_agent_profiles(
    agent_count: int = 10,
    platform: str = "twitter"
) -> List[AgentProfile]:
    """
    快速创建智能体配置文件

    Args:
        agent_count: 智能体数量
        platform: 目标平台

    Returns:
        智能体配置列表
    """
    generator = AgentGenerator()

    # 使用混合分布
    distribution = {
        "TECH_ENTHUSIAST": agent_count // 4,
        "CASUAL_USER": agent_count // 3,
        "BUSINESS_PROFESSIONAL": agent_count // 5,
        "STUDENT": agent_count // 5,
    }

    return generator.generate_mixed_population(agent_count, distribution)
