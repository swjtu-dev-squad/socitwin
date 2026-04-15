"""
智能体属性配置枚举

存储所有智能体可能使用的属性值，用于随机生成多样化的智能体。
"""

from typing import List, Dict, Any

# ============================================================================
# 年龄配置
# ============================================================================

AGE_GROUPS = {
    "18-24": (18, 24),
    "25-34": (25, 34),
    "35-44": (35, 44),
    "45-54": (45, 54),
    "55-64": (55, 64),
    "65+": (65, 80)
}

# ============================================================================
# 性别配置
# ============================================================================

GENDERS = ["male", "female", "non-binary", "prefer not to say"]

# ============================================================================
# 地区配置
# ============================================================================

COUNTRIES = [
    "United States",
    "United Kingdom",
    "Canada",
    "Australia",
    "Germany",
    "France",
    "Japan",
    "South Korea",
    "Brazil",
    "India",
    "Singapore",
    "Netherlands",
    "Sweden",
    "Switzerland",
    "China"
]

REGIONS = {
    "North America": ["United States", "Canada"],
    "Europe": ["United Kingdom", "Germany", "France", "Netherlands", "Sweden", "Switzerland"],
    "Asia Pacific": ["Australia", "Japan", "South Korea", "Singapore", "China", "India"],
    "South America": ["Brazil"]
}

# ============================================================================
# 兴趣标签（按类别分组）
# ============================================================================

INTERESTS = {
    "technology": [
        "Artificial Intelligence", "Machine Learning", "Blockchain", "Cybersecurity",
        "Cloud Computing", "Data Science", "Programming", "Gadgets", "Tech News"
    ],
    "sports": [
        "Football", "Basketball", "Tennis", "Swimming", "Running", "Fitness",
        "Yoga", "Cycling", "Hiking", "Extreme Sports"
    ],
    "entertainment": [
        "Movies", "TV Series", "Music", "Gaming", "Anime", "Books",
        "Podcasts", "Stand-up Comedy", "Theater", "Concerts"
    ],
    "lifestyle": [
        "Travel", "Food & Cooking", "Fashion", "Photography", "Art & Design",
        "DIY & Crafts", "Gardening", "Pets", "Home Decor", "Sustainability"
    ],
    "business": [
        "Entrepreneurship", "Investing", "Personal Finance", "Marketing",
        "E-commerce", "Startups", "Leadership", "Productivity", "Networking"
    ],
    "science": [
        "Physics", "Biology", "Chemistry", "Astronomy", "Psychology",
        "Neuroscience", "Climate Change", "Medicine", "Research"
    ],
    "social_issues": [
        "Environmental Protection", "Social Justice", "Education Reform",
        "Healthcare Access", "Human Rights", "Mental Health Awareness",
        "Gender Equality", "Racial Equality", "LGBTQ+ Rights"
    ]
}

# 扁平化的兴趣列表（用于随机选择）
ALL_INTERESTS = [interest for category in INTERESTS.values() for interest in category]

# ============================================================================
# MBTI 性格类型
# ============================================================================

MBTI_TYPES = [
    "INTJ", "INTP", "ENTJ", "ENTP",  # Analysts
    "INFJ", "INFP", "ENFJ", "ENFP",  # Diplomats
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",  # Sentinels
    "ISTP", "ISFP", "ESTP", "ESFP"   # Explorers
]

# ============================================================================
# 职业类型
# ============================================================================

PROFESSIONS = [
    "Software Engineer", "Data Scientist", "Product Manager",
    "Teacher", "Doctor", "Nurse", "Lawyer", "Accountant",
    "Marketing Specialist", "Sales Representative", "Journalist",
    "Graphic Designer", "Architect", "Civil Engineer",
    "Psychologist", "Social Worker", "Police Officer",
    "Chef", "Writer", "Musician", "Artist",
    "Student", "Retired", "Freelancer", "Entrepreneur"
]

# ============================================================================
# Bio 模板（支持变量替换）
# ============================================================================

BIO_TEMPLATES = [
    # 原有模板（不包含政治倾向）
    "A {profession} passionate about {main_interest}. Based in {country}.",
    "{profession} | {mbti} | Love {main_interest} and {secondary_interest}",
    "Exploring the world of {main_interest}. {profession} by day, {hobby} by night.",
    "Just another {profession} who loves {main_interest}. Always curious about {secondary_interest}.",
    "{profession} with a passion for {main_interest} and {secondary_interest}. Living in {country}.",
    "Building things and exploring {main_interest}. {profession} | {mbti}",
    "{profession} interested in {main_interest}, {secondary_interest}, and {hobby}.",
    " lifelong learner passionate about {main_interest}. Working as a {profession}.",
    "Sharing my journey in {main_interest}. {profession} based in {country}.",
    "Enthusiast of {main_interest} and {secondary_interest}. {profession} | {country}",

    # 新增模板（包含政治倾向）
    "{profession} | {mbti} | {political_leaning} | Passionate about {main_interest}",
    "{profession} with {political_leaning} views. Love {main_interest} and {secondary_interest}. Based in {country}.",
    "{political_leaning_title} {profession} interested in {main_interest}. {mbti} | {country}",
    "{profession} | {political_leaning} | {mbti} | Exploring {main_interest} and {secondary_interest}",
    "Just a {profession} with {political_leaning} perspectives. Passionate about {main_interest}. Living in {country}.",
    "{profession} | {mbti} | {political_leaning} | Love {main_interest}, {hobby}, and {secondary_interest}",
    "{profession} based in {country}. {political_leaning} views on {main_interest} and social issues.",
    "{profession} | {political_leaning} | {mbti} | {country} | Interest in {main_interest} and {secondary_interest}",
    "{political_leaning} {profession} passionate about {main_interest}. {mbti} | Living in {country}."
]

HOBBIES = [
    "photography", "gaming", "cooking", "reading", "traveling",
    "hiking", "painting", "music", "sports", "writing"
]

# ============================================================================
# 政治倾向（用于观点极化研究）
# ============================================================================

POLITICAL_LEANINGS = [
    "far-left", "left", "center-left", "center",
    "center-right", "right", "far-right"
]

# ============================================================================
# 话题倾向（影响智能体发布的内容类型）
# ============================================================================

TOPIC_PREFERENCES = [
    "technology", "politics", "sports", "entertainment",
    "lifestyle", "business", "science", "social_issues",
    "health", "education", "environment", "arts"
]

# ============================================================================
# 活跃度级别
# ============================================================================

ACTIVITY_LEVELS = {
    "low": {
        "posts_per_day": (0.1, 0.5),
        "comments_per_day": (0.5, 2),
        "likes_per_day": (1, 5)
    },
    "medium": {
        "posts_per_day": (0.5, 2),
        "comments_per_day": (2, 5),
        "likes_per_day": (5, 15)
    },
    "high": {
        "posts_per_day": (2, 5),
        "comments_per_day": (5, 10),
        "likes_per_day": (15, 30)
    }
}

# ============================================================================
# 辅助函数
# ============================================================================

def get_interests_by_category(count: int = 3) -> List[str]:
    """
    随机选择多个类别的兴趣

    Args:
        count: 要选择的兴趣数量

    Returns:
        兴趣列表
    """
    import random
    selected = random.sample(ALL_INTERESTS, min(count, len(ALL_INTERESTS)))
    return selected


def get_demographics_by_age_range(age_group: str) -> Dict[str, Any]:
    """
    根据年龄组获取推荐的人口统计特征

    Args:
        age_group: 年龄组（如 "18-24"）

    Returns:
        推荐的职业、兴趣等
    """
    # 这里可以根据年龄组返回不同的推荐
    # 简化版本，实际可以更复杂
    return {
        "likely_professions": PROFESSIONS[:10],
        "likely_interests": ALL_INTERESTS[:15]
    }
