"""
智能体生成器

负责随机组合各种属性，生成多样化的智能体配置。
遵循工厂模式，确保智能体生成的可配置性和可扩展性。
"""

import random
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from app.core.agent_profiles import (
    AGE_GROUPS, GENDERS, COUNTRIES, REGIONS,
    INTERESTS, ALL_INTERESTS, MBTI_TYPES,
    PROFESSIONS, BIO_TEMPLATES, HOBBIES,
    POLITICAL_LEANINGS, TOPIC_PREFERENCES,
    ACTIVITY_LEVELS, get_interests_by_category
)

logger = logging.getLogger(__name__)


@dataclass
class AgentProfile:
    """智能体完整配置"""
    agent_id: int
    user_name: str
    name: str
    age: int
    gender: str
    country: str
    mbti: str
    profession: str
    interests: List[str]
    bio: str
    political_leaning: Optional[str] = None
    topic_preference: Optional[str] = None
    activity_level: str = "medium"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "agent_id": self.agent_id,
            "user_name": self.user_name,
            "name": self.name,
            "age": self.age,
            "gender": self.gender,
            "country": self.country,
            "mbti": self.mbti,
            "profession": self.profession,
            "interests": self.interests,
            "bio": self.bio,
            "political_leaning": self.political_leaning,
            "topic_preference": self.topic_preference,
            "activity_level": self.activity_level,
            "profile": {
                "interests": self.interests,
                "mbti": self.mbti,
                "age": self.age,
                "gender": self.gender,
                "country": self.country,
                "profession": self.profession
            }
        }


class AgentGenerator:
    """
    智能体生成器工厂

    负责随机组合各种属性，生成多样化的智能体配置。
    """

    def __init__(self, seed: Optional[int] = None):
        """
        初始化生成器

        Args:
            seed: 随机种子（用于可重复的生成）
        """
        if seed is not None:
            random.seed(seed)
        logger.info(f"AgentGenerator initialized with seed: {seed}")

    def generate_single(self, agent_id: int, platform: str = "twitter") -> AgentProfile:
        """
        生成单个智能体配置

        Args:
            agent_id: 智能体ID
            platform: 社交平台类型

        Returns:
            AgentProfile: 智能体完整配置
        """
        # 1. 随机选择基础属性
        age_group = random.choice(list(AGE_GROUPS.keys()))
        age = random.randint(*AGE_GROUPS[age_group])
        gender = random.choice(GENDERS)
        country = random.choice(COUNTRIES)
        mbti = random.choice(MBTI_TYPES)
        profession = random.choice(PROFESSIONS)

        # 2. 随机选择兴趣（3-6个）
        num_interests = random.randint(3, 6)
        interests = random.sample(ALL_INTERESTS, num_interests)

        # 3. 生成用户名和姓名
        user_name = self._generate_user_name(agent_id, platform)
        name = self._generate_name(gender, country)

        # 4. 生成 Bio
        bio = self._generate_bio(profession, interests, country, mbti)

        # 5. 可选属性（用于高级研究）
        political_leaning = random.choice(POLITICAL_LEANINGS)
        topic_preference = random.choice(TOPIC_PREFERENCES)
        activity_level = random.choice(list(ACTIVITY_LEVELS.keys()))

        profile = AgentProfile(
            agent_id=agent_id,
            user_name=user_name,
            name=name,
            age=age,
            gender=gender,
            country=country,
            mbti=mbti,
            profession=profession,
            interests=interests,
            bio=bio,
            political_leaning=political_leaning,
            topic_preference=topic_preference,
            activity_level=activity_level
        )

        logger.debug(f"Generated agent {agent_id}: {user_name} ({mbti}, {country})")
        return profile

    def generate_batch(self, count: int, platform: str = "twitter") -> List[AgentProfile]:
        """
        批量生成智能体配置

        Args:
            count: 生成的智能体数量
            platform: 社交平台类型

        Returns:
            List[AgentProfile]: 智能体配置列表
        """
        logger.info(f"Generating {count} agents for platform: {platform}")
        profiles = [self.generate_single(i, platform) for i in range(count)]
        logger.info(f"Successfully generated {len(profiles)} agent profiles")
        return profiles

    def _generate_user_name(self, agent_id: int, platform: str) -> str:
        """
        生成用户名

        Args:
            agent_id: 智能体ID
            platform: 平台类型

        Returns:
            用户名字符串
        """
        # 简单的生成逻辑，可以扩展
        prefixes = ["user", "player", "member", "creator", "explorer"]
        prefix = random.choice(prefixes)

        # 有一定概率使用数字后缀
        if random.random() < 0.5:
            return f"{prefix}_{agent_id}"
        else:
            return f"{prefix}_{random.randint(1000, 9999)}"

    def _generate_name(self, gender: str, country: str) -> str:
        """
        生成真实姓名（基于性别和国家）

        Args:
            gender: 性别
            country: 国家

        Returns:
            姓名字符串
        """
        # 简化版本，实际可以使用更复杂的姓名生成库
        first_names = {
            "male": ["James", "John", "Robert", "Michael", "David", "William", "Richard", "Joseph", "Thomas", "Chris"],
            "female": ["Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen"],
            "non-binary": ["Alex", "Taylor", "Jordan", "Casey", "Riley", "Jamie", "Morgan", "Avery", "Quinn", "Skyler"]
        }

        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]

        first_name = random.choice(first_names.get(gender, first_names["non-binary"]))
        last_name = random.choice(last_names)

        return f"{first_name} {last_name}"

    def _generate_bio(self, profession: str, interests: List[str],
                     country: str, mbti: str) -> str:
        """
        生成个人简介

        Args:
            profession: 职业
            interests: 兴趣列表
            country: 国家
            mbti: MBTI类型

        Returns:
            Bio字符串
        """
        # 选择主要和次要兴趣
        if len(interests) >= 2:
            main_interest = random.choice(interests)
            remaining = [i for i in interests if i != main_interest]
            secondary_interest = random.choice(remaining) if remaining else main_interest
        else:
            main_interest = interests[0] if interests else "technology"
            secondary_interest = main_interest

        hobby = random.choice(HOBBIES)

        # 选择模板并填充
        template = random.choice(BIO_TEMPLATES)

        bio = template.format(
            profession=profession,
            main_interest=main_interest,
            secondary_interest=secondary_interest,
            country=country,
            mbti=mbti,
            hobby=hobby
        )

        return bio

    def generate_with_constraints(
        self,
        agent_id: int,
        platform: str = "twitter",
        age_range: Optional[tuple] = None,
        countries: Optional[List[str]] = None,
        mbti_types: Optional[List[str]] = None,
        interest_categories: Optional[List[str]] = None
    ) -> AgentProfile:
        """
        带约束条件的智能体生成

        Args:
            agent_id: 智能体ID
            platform: 平台类型
            age_range: 年龄范围限制 (min, max)
            countries: 国家列表限制
            mbti_types: MBTI类型限制
            interest_categories: 兴趣类别限制

        Returns:
            AgentProfile: 智能体配置
        """
        # 临时修改全局配置（用于生成）
        # 这里可以扩展更复杂的约束逻辑
        profile = self.generate_single(agent_id, platform)

        # 应用约束条件
        if age_range:
            profile.age = random.randint(*age_range)

        if countries:
            profile.country = random.choice(countries)

        if mbti_types:
            profile.mbti = random.choice(mbti_types)

        if interest_categories:
            # 根据类别选择兴趣
            selected_interests = []
            for category in interest_categories:
                if category in INTERESTS:
                    selected_interests.extend(random.sample(INTERESTS[category], min(2, len(INTERESTS[category]))))
            profile.interests = selected_interests[:6]  # 限制最多6个

        return profile


# ============================================================================
# 单例模式（可选）
# ============================================================================

_default_generator: Optional[AgentGenerator] = None


def get_agent_generator(seed: Optional[int] = None) -> AgentGenerator:
    """
    获取智能体生成器实例（单例模式）

    Args:
        seed: 随机种子

    Returns:
        AgentGenerator: 生成器实例
    """
    global _default_generator
    if _default_generator is None or seed is not None:
        _default_generator = AgentGenerator(seed)
    return _default_generator
