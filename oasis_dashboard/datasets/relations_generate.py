#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
社交关系数据生成脚本
基于 Scale-free 网络 + Echo Chamber + Interest-based Follow 机制
"""

import json
import os
import random
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Any
from collections import defaultdict


# ==================== 配置参数 ====================

class Config:
    """关系生成配置参数"""

    # 时间配置
    BASE_DATE = datetime(2024, 1, 1)
    DATE_RANGE_DAYS = 365

    # 关系概率配置
    PROB_FOLLOW_BASE = 0.20  # 基础概率
    PROB_FOLLOW_NO_COMMON_CATEGORY = 0.00  # 无共同大类的关注概率
    PROB_FOLLOW_ONE_COMMON_CATEGORY = 0.10  # 一个共同大类的关注概率
    PROB_FOLLOW_TWO_COMMON_CATEGORY = 0.15  # 两个共同大类的关注概率
    PROB_FOLLOW_ONE_SAME_TOPIC = 0.15  # 一个话题完全相同的关注概率
    PROB_FOLLOW_TWO_SAME_TOPIC = 0.25  # 两个话题完全相同的关注概率
    PROB_ECHO_CHAMBER = 0.60
    PROB_ACTIVE = 0.90

    # 【新增】KOL 关系概率配置
    PROB_KOL_FOLLOW_KOL = 0.10  # KOL 关注其他 KOL 的概率（与普通用户关注 KOL 相同）
    PROB_KOL_FOLLOW_NORMAL = 0.10  # KOL 关注普通用户的概率（大大减少）

    # 【新增】普通用户扩展关系概率配置
    PROB_PEER_EXTENDED = 0.10  # 核心小图之外普通用户之间的连接概率（大大减少）

    # 网络结构配置（适配 1890 用户规模）
    KOL_FOLLOW_MIN = 5
    KOL_FOLLOW_MAX = 12
    PEER_CONNECTION_MIN = 3
    PEER_CONNECTION_MAX = 8
    PEER_NETWORK_NORMAL_RATIO = 0.20  # 核心小图规模 = 普通用户数 × 该比例（向下取整）

    # 幂律分布参数
    KOL_POPULARITY_EXPONENT = 1.5
    TOP_KOL_RATIO = 0.2

    # 话题分类
    TOPIC_CATEGORIES = {}


# ==================== 数据结构定义 ====================

class SocialRelationship:
    """社交关系数据类"""

    def __init__(self, id: str, from_user_id: str, to_user_id: str,
                 rel_type: str, created_at: datetime, updated_at: datetime,
                 is_active: bool):
        self.id = id
        self.fromUserId = from_user_id
        self.toUserId = to_user_id
        self.type = rel_type
        self.createdAt = created_at
        self.updatedAt = updated_at
        self.isActive = is_active

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "fromUserId": self.fromUserId,
            "toUserId": self.toUserId,
            "type": self.type,
            "createdAt": self.createdAt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "updatedAt": self.updatedAt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "isActive": self.isActive
        }


class UserNetwork:
    """用户网络结构类"""

    def __init__(self, user_id: str):
        self.userId = user_id
        self.followers: List[SocialRelationship] = []
        self.follows: List[SocialRelationship] = []
        self.friends: List[SocialRelationship] = []
        self.statistics = {
            "followersCount": 0,
            "followsCount": 0,
            "friendsCount": 0,
            "lastUpdated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "userId": self.userId,
            "followers": [r.to_dict() for r in self.followers],
            "follows": [r.to_dict() for r in self.follows],
            "friends": [r.to_dict() for r in self.friends],
            "statistics": self.statistics
        }


# ==================== 核心生成器类 ====================

class RelationshipGenerator:
    """关系数据生成器"""

    def __init__(self, users_file: str, topics_file: str):
        self.users = self._coerce_users_payload(self._load_json(users_file))
        self.topics_classification = self._load_json(topics_file)
        self.user_topics_map: Dict[str, List[str]] = {}
        self.user_topic_categories_map: Dict[str, Dict[str, List[str]]] = {}
        self.kol_users: List[Dict] = []
        self.kol_popularity_weights: List[float] = []
        self.normal_users: List[Dict] = []
        self.peer_network_size = 0  # 核心小图包含的普通用户数，见 _preprocess_data
        self.relationships: List[SocialRelationship] = []
        self.user_networks: Dict[str, UserNetwork] = {}
        self._rel_index = 1
        self._created_pairs: Set[Tuple[str, str]] = set()

        self._load_topic_categories()
        self._preprocess_data()
        self._calculate_kol_popularity_weights()

    def _load_json(self, filepath: str) -> Any:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def _coerce_users_payload(raw: Any) -> List[Dict[str, Any]]:
        """支持用户数组，或 Persona API 导出格式 {\"data\": [用户...]}。"""
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict) and isinstance(raw.get("data"), list):
            return raw["data"]
        raise ValueError(
            "用户 JSON 须为数组，或含 data 数组的对象（如 Persona API 的 users 导出）"
        )

    def _load_topic_categories(self):
        tc = self.topics_classification
        if isinstance(tc, dict) and isinstance(tc.get("data"), list):
            merged: Dict[str, List[str]] = {"Politics": [], "Economics": [], "Society": []}
            for item in tc["data"]:
                if not isinstance(item, dict):
                    continue
                cat = item.get("category")
                topics = item.get("topics")
                if cat in merged and isinstance(topics, list):
                    merged[cat] = list(topics)
            Config.TOPIC_CATEGORIES = merged
        elif isinstance(tc, dict):
            Config.TOPIC_CATEGORIES = {
                "Politics": list(tc.get("Politics", []) or []),
                "Economics": list(tc.get("Economics", []) or []),
                "Society": list(tc.get("Society", []) or []),
            }
        else:
            Config.TOPIC_CATEGORIES = {"Politics": [], "Economics": [], "Society": []}
        print(f"已加载话题分类：Politics({len(Config.TOPIC_CATEGORIES['Politics'])}), "
              f"Economics({len(Config.TOPIC_CATEGORIES['Economics'])}), "
              f"Society({len(Config.TOPIC_CATEGORIES['Society'])})")

    def _get_topic_category(self, topic: str) -> str:
        topic_lower = topic.lower()
        for category, topics in Config.TOPIC_CATEGORIES.items():
            for classified_topic in topics:
                if classified_topic.lower() == topic_lower or topic_lower in classified_topic.lower() or classified_topic.lower() in topic_lower:
                    return category
        return "Unknown"

    def _get_user_topic_categories(self, topics: List[str]) -> Dict[str, List[str]]:
        category_map = {"Politics": [], "Economics": [], "Society": [], "Unknown": []}
        for topic in topics:
            category = self._get_topic_category(topic)
            category_map[category].append(topic)
        return category_map

    def _calculate_follow_probability(self, topics1: List[str], topics2: List[str]) -> float:
        if not topics1 or not topics2:
            return Config.PROB_FOLLOW_NO_COMMON_CATEGORY

        categories1 = self._get_user_topic_categories(topics1)
        categories2 = self._get_user_topic_categories(topics2)

        common_categories = []
        for category in ["Politics", "Economics", "Society"]:
            if categories1.get(category, []) and categories2.get(category, []):
                common_categories.append(category)

        set1 = set(topic.lower() for topic in topics1)
        set2 = set(topic.lower() for topic in topics2)
        same_topics = set1 & set2
        same_topic_count = len(same_topics)

        if same_topic_count >= 2:
            return Config.PROB_FOLLOW_TWO_SAME_TOPIC
        elif same_topic_count == 1:
            return Config.PROB_FOLLOW_ONE_SAME_TOPIC
        elif len(common_categories) >= 2:
            return Config.PROB_FOLLOW_TWO_COMMON_CATEGORY
        elif len(common_categories) == 1:
            return Config.PROB_FOLLOW_ONE_COMMON_CATEGORY
        else:
            return Config.PROB_FOLLOW_NO_COMMON_CATEGORY

    def _calculate_kol_popularity_weights(self):
        n = len(self.kol_users)
        self.kol_popularity_weights = []
        for i in range(n):
            weight = (i + 1) ** (-Config.KOL_POPULARITY_EXPONENT)
            self.kol_popularity_weights.append(weight)

        total_weight = sum(self.kol_popularity_weights)
        self.kol_popularity_weights = [w / total_weight for w in self.kol_popularity_weights]

        print(
            f"KOL 热度权重计算完成：头部{int(n * Config.TOP_KOL_RATIO)}个 KOL 权重占比{sum(self.kol_popularity_weights[:int(n * Config.TOP_KOL_RATIO)]):.1%}")

    def _preprocess_data(self):
        for user in self.users:
            user_id = self._generate_user_id(user['agent_id'])
            topics = user.get('profile', {}).get('other_info', {}).get('topics', [])
            self.user_topics_map[user_id] = topics
            self.user_topic_categories_map[user_id] = self._get_user_topic_categories(topics)

            if user.get('user_type') == 'kol':
                self.kol_users.append(user)
            else:
                self.normal_users.append(user)

        for user in self.users:
            user_id = self._generate_user_id(user['agent_id'])
            self.user_networks[user_id] = UserNetwork(user_id)

        n_normal = len(self.normal_users)
        self.peer_network_size = int(n_normal * Config.PEER_NETWORK_NORMAL_RATIO)

    def _generate_user_id(self, agent_id: int) -> str:
        return f"user_{agent_id}"

    def _generate_relationship_id(self) -> str:
        rel_id = f"rel_{self._rel_index:06d}"
        self._rel_index += 1
        return rel_id

    def _generate_timestamp(self, offset_days: int) -> datetime:
        return Config.BASE_DATE + timedelta(days=offset_days)

    def _is_political_echo_chamber(self, topics1: List[str], topics2: List[str]) -> bool:
        categories1 = self._get_user_topic_categories(topics1)
        categories2 = self._get_user_topic_categories(topics2)
        return bool(categories1.get("Politics", [])) and bool(categories2.get("Politics", []))

    def _create_relationship(self, from_id: str, to_id: str, rel_type: str,
                             created_offset: int, updated_offset: int,
                             is_active: bool) -> SocialRelationship:
        rel = SocialRelationship(
            id=self._generate_relationship_id(),
            from_user_id=from_id,
            to_user_id=to_id,
            rel_type=rel_type,
            created_at=self._generate_timestamp(created_offset),
            updated_at=self._generate_timestamp(updated_offset),
            is_active=is_active
        )
        return rel

    def _add_relationship_to_network(self, rel: SocialRelationship):
        from_id = rel.fromUserId
        to_id = rel.toUserId

        if rel.type == 'follow':
            if from_id in self.user_networks:
                self.user_networks[from_id].follows.append(rel)
                self.user_networks[from_id].statistics['followsCount'] += 1
            if to_id in self.user_networks:
                self.user_networks[to_id].followers.append(rel)
                self.user_networks[to_id].statistics['followersCount'] += 1
        elif rel.type == 'friend':
            if from_id in self.user_networks:
                self.user_networks[from_id].friends.append(rel)
                self.user_networks[from_id].statistics['friendsCount'] += 1
            if to_id in self.user_networks:
                self.user_networks[to_id].friends.append(rel)
                self.user_networks[to_id].statistics['friendsCount'] += 1

    def generate_scale_free_relationships(self):
        """普通用户关注 KOL 的关系生成"""
        print(f"开始生成 Scale-free 网络关系...")
        print(f"  KOL 用户数：{len(self.kol_users)}")
        print(f"  普通用户数：{len(self.normal_users)}")

        kol_ids = [self._generate_user_id(kol['agent_id']) for kol in self.kol_users]

        for normal_user in self.normal_users:
            normal_id = self._generate_user_id(normal_user['agent_id'])
            normal_topics = self.user_topics_map.get(normal_id, [])

            num_kol_follows = random.randint(Config.KOL_FOLLOW_MIN, Config.KOL_FOLLOW_MAX)

            selected_kol_indices = random.choices(
                range(len(self.kol_users)),
                weights=self.kol_popularity_weights,
                k=num_kol_follows
            )
            selected_kol_indices = list(set(selected_kol_indices))

            for kol_index in selected_kol_indices:
                kol_user = self.kol_users[kol_index]
                kol_id = kol_ids[kol_index]
                pair_key = (normal_id, kol_id)

                if pair_key in self._created_pairs:
                    continue

                kol_topics = self.user_topics_map.get(kol_id, [])
                topic_prob = self._calculate_follow_probability(normal_topics, kol_topics)

                follow_prob = Config.PROB_FOLLOW_BASE

                if self._is_political_echo_chamber(normal_topics, kol_topics):
                    follow_prob = Config.PROB_ECHO_CHAMBER
                elif topic_prob > Config.PROB_FOLLOW_ONE_SAME_TOPIC:
                    follow_prob = min(0.95, follow_prob + topic_prob)
                else:
                    follow_prob = max(0.70, follow_prob - (0.15 - topic_prob))

                if random.random() < follow_prob:
                    rel = self._create_relationship(
                        from_id=normal_id,
                        to_id=kol_id,
                        rel_type='follow',
                        created_offset=random.randint(0, 180),
                        updated_offset=random.randint(180, Config.DATE_RANGE_DAYS),
                        is_active=random.random() < Config.PROB_ACTIVE
                    )
                    self.relationships.append(rel)
                    self._add_relationship_to_network(rel)
                    self._created_pairs.add(pair_key)

        print(f"  生成 Scale-free 关系数：{len(self.relationships)}")

    def generate_kol_relationships(self):
        """
        【新增】KOL 关注其他用户的算法
        1. KOL 与 KOL 之间依据话题重合度建立关系，概率与普通用户关注 KOL 相同
        2. KOL 也会少量关注普通用户，依据话题重合度建立，但概率大大减少
        """
        print(f"开始生成 KOL 关系网络...")
        kol_start_count = len(self.relationships)

        kol_ids = [self._generate_user_id(kol['agent_id']) for kol in self.kol_users]
        normal_ids = [self._generate_user_id(user['agent_id']) for user in self.normal_users]

        # ===== KOL 关注其他 KOL =====
        for i, kol_user in enumerate(self.kol_users):
            kol_id = kol_ids[i]
            kol_topics = self.user_topics_map.get(kol_id, [])

            # 每个 KOL 关注 2-5 个其他 KOL
            num_kol_follows = random.randint(20, 30)
            other_kol_indices = [j for j in range(len(self.kol_users)) if j != i]

            if len(other_kol_indices) < num_kol_follows:
                num_kol_follows = len(other_kol_indices)

            selected_indices = random.sample(other_kol_indices, num_kol_follows)

            for kol_index in selected_indices:
                target_kol_id = kol_ids[kol_index]
                pair_key = (kol_id, target_kol_id)

                if pair_key in self._created_pairs:
                    continue

                target_kol_topics = self.user_topics_map.get(target_kol_id, [])
                topic_prob = self._calculate_follow_probability(kol_topics, target_kol_topics)

                # KOL 关注 KOL 的概率与普通用户关注 KOL 相同
                follow_prob = Config.PROB_KOL_FOLLOW_KOL

                if self._is_political_echo_chamber(kol_topics, target_kol_topics):
                    follow_prob = Config.PROB_ECHO_CHAMBER
                elif topic_prob >= Config.PROB_FOLLOW_TWO_SAME_TOPIC:
                    follow_prob = min(0.85, follow_prob + topic_prob)
                elif topic_prob >= Config.PROB_FOLLOW_ONE_SAME_TOPIC:
                    follow_prob = min(0.75, follow_prob + topic_prob * 0.8)
                elif topic_prob >= Config.PROB_FOLLOW_TWO_COMMON_CATEGORY:
                    follow_prob = min(0.60, follow_prob + topic_prob * 0.6)
                elif topic_prob >= Config.PROB_FOLLOW_ONE_COMMON_CATEGORY:
                    follow_prob = min(0.45, follow_prob + topic_prob * 0.4)

                if random.random() < follow_prob:
                    rel = self._create_relationship(
                        from_id=kol_id,
                        to_id=target_kol_id,
                        rel_type='follow',
                        created_offset=random.randint(0, 180),
                        updated_offset=random.randint(180, Config.DATE_RANGE_DAYS),
                        is_active=random.random() < Config.PROB_ACTIVE
                    )
                    self.relationships.append(rel)
                    self._add_relationship_to_network(rel)
                    self._created_pairs.add(pair_key)

        # ===== KOL 关注普通用户（概率大大减少）=====
        for kol_user in self.kol_users:
            kol_id = kol_ids[self.kol_users.index(kol_user)]
            kol_topics = self.user_topics_map.get(kol_id, [])

            # 每个 KOL 只关注 4-7 个普通用户
            num_normal_follows = random.randint(4, 7)

            # 基于话题重合度筛选候选普通用户
            candidate_scores = []
            for normal_user in self.normal_users:
                normal_id = self._generate_user_id(normal_user['agent_id'])
                normal_topics = self.user_topics_map.get(normal_id, [])
                topic_prob = self._calculate_follow_probability(kol_topics, normal_topics)
                if topic_prob > 0:
                    candidate_scores.append((normal_id, normal_topics, topic_prob))

            # 按话题重合度排序，优先选择话题重合度高的
            candidate_scores.sort(key=lambda x: x[2], reverse=True)

            # 从候选中选择（如果候选不足则随机补充）
            if len(candidate_scores) >= num_normal_follows:
                # 加权随机选择（话题重合度越高概率越大）
                weights = [score[2] + 0.01 for score in candidate_scores[:50]]  # 只考虑前 50 个
                total_weight = sum(weights)
                weights = [w / total_weight for w in weights]

                selected_indices = random.choices(
                    range(min(50, len(candidate_scores))),
                    weights=weights,
                    k=num_normal_follows
                )
                selected_indices = list(set(selected_indices))
            else:
                selected_indices = list(range(len(candidate_scores)))

            for idx in selected_indices:
                if idx >= len(candidate_scores):
                    continue

                normal_id, normal_topics, topic_prob = candidate_scores[idx]
                pair_key = (kol_id, normal_id)

                if pair_key in self._created_pairs:
                    continue

                # KOL 关注普通用户的概率大大减少
                follow_prob = Config.PROB_KOL_FOLLOW_NORMAL

                # 根据话题重合度调整概率
                if self._is_political_echo_chamber(kol_topics, normal_topics):
                    follow_prob = Config.PROB_KOL_FOLLOW_NORMAL * 3  # 政治回音室效应稍微提高
                elif topic_prob >= Config.PROB_FOLLOW_TWO_SAME_TOPIC:
                    follow_prob = min(0.30, Config.PROB_KOL_FOLLOW_NORMAL * 4)
                elif topic_prob >= Config.PROB_FOLLOW_ONE_SAME_TOPIC:
                    follow_prob = min(0.20, Config.PROB_KOL_FOLLOW_NORMAL * 2.5)
                elif topic_prob >= Config.PROB_FOLLOW_TWO_COMMON_CATEGORY:
                    follow_prob = min(0.10, Config.PROB_KOL_FOLLOW_NORMAL * 1.5)

                if random.random() < follow_prob:
                    rel = self._create_relationship(
                        from_id=kol_id,
                        to_id=normal_id,
                        rel_type='follow',
                        created_offset=random.randint(0, 180),
                        updated_offset=random.randint(180, Config.DATE_RANGE_DAYS),
                        is_active=random.random() < Config.PROB_ACTIVE
                    )
                    self.relationships.append(rel)
                    self._add_relationship_to_network(rel)
                    self._created_pairs.add(pair_key)

        print(f"  生成 KOL 关系数：{len(self.relationships) - kol_start_count}")

    def generate_peer_relationships(self):
        """
        普通用户之间的关系生成
        1. 核心小图（普通用户数的 PEER_NETWORK_NORMAL_RATIO，见 self.peer_network_size）：原有算法和概率
        2. 其余普通用户：算法相同，但概率大大减少
        """
        print(f"开始生成普通用户关系网络...")
        print(f"  核心小图普通用户数：{self.peer_network_size}（普通用户总数 {len(self.normal_users)} 的 {Config.PEER_NETWORK_NORMAL_RATIO:.0%}）")
        peer_start_count = len(self.relationships)

        # ===== 核心小图内普通用户（原有逻辑）=====
        peer_users_first_300 = self.normal_users[: self.peer_network_size]
        first_300_count = 0

        for i, user1 in enumerate(peer_users_first_300):
            user1_id = self._generate_user_id(user1['agent_id'])
            user1_topics = self.user_topics_map.get(user1_id, [])

            peer_range = random.randint(Config.PEER_CONNECTION_MIN, Config.PEER_CONNECTION_MAX)
            peer_candidates = peer_users_first_300[i + 1:i + 1 + peer_range * 2]

            for user2 in peer_candidates:
                user2_id = self._generate_user_id(user2['agent_id'])
                pair_key = tuple(sorted([user1_id, user2_id]))

                if pair_key in self._created_pairs:
                    continue

                user2_topics = self.user_topics_map.get(user2_id, [])
                topic_prob = self._calculate_follow_probability(user1_topics, user2_topics)

                follow_prob = Config.PROB_FOLLOW_BASE
                rel_type = 'follow'

                if self._is_political_echo_chamber(user1_topics, user2_topics):
                    follow_prob = Config.PROB_ECHO_CHAMBER
                elif topic_prob >= Config.PROB_FOLLOW_TWO_SAME_TOPIC:
                    rel_type = 'friend'
                    follow_prob = 0.80
                elif topic_prob >= Config.PROB_FOLLOW_ONE_SAME_TOPIC:
                    rel_type = 'follow'
                    follow_prob = 0.75
                else:
                    rel_type = 'follow'
                    follow_prob = 0.65

                if random.random() < follow_prob:
                    rel = self._create_relationship(
                        from_id=user1_id,
                        to_id=user2_id,
                        rel_type=rel_type,
                        created_offset=random.randint(0, 180),
                        updated_offset=random.randint(180, Config.DATE_RANGE_DAYS),
                        is_active=random.random() < Config.PROB_ACTIVE
                    )
                    self.relationships.append(rel)
                    self._add_relationship_to_network(rel)
                    self._created_pairs.add(pair_key)
                    first_300_count += 1

                    if rel_type == 'friend':
                        rel_reverse = self._create_relationship(
                            from_id=user2_id,
                            to_id=user1_id,
                            rel_type='friend',
                            created_offset=random.randint(0, 180),
                            updated_offset=random.randint(180, Config.DATE_RANGE_DAYS),
                            is_active=random.random() < Config.PROB_ACTIVE
                        )
                        self.relationships.append(rel_reverse)
                        self._add_relationship_to_network(rel_reverse)
                        first_300_count += 1

        # ===== 核心小图外普通用户（概率大大减少）=====
        peer_users_extended = self.normal_users[self.peer_network_size :]
        extended_count = 0

        if peer_users_extended:
            print(f"  处理扩展用户数：{len(peer_users_extended)}")

            for i, user1 in enumerate(peer_users_extended):
                user1_id = self._generate_user_id(user1['agent_id'])
                user1_topics = self.user_topics_map.get(user1_id, [])

                # 连接范围适当减少
                peer_range = random.randint(2, 5)

                # 可以在扩展用户内部建立关系，也可以与核心小图内用户建立关系
                all_candidates = peer_users_extended[i + 1:i + 1 + peer_range * 2]

                # 随机添加一些核心小图用户作为候选（增加网络连通性）
                if peer_users_first_300 and random.random() < 0.3:
                    num_first_300_candidates = random.randint(4, 5)
                    additional_candidates = random.sample(
                        peer_users_first_300,
                        min(num_first_300_candidates, len(peer_users_first_300))
                    )
                    all_candidates.extend(additional_candidates)

                for user2 in all_candidates:
                    user2_id = self._generate_user_id(user2['agent_id'])
                    pair_key = tuple(sorted([user1_id, user2_id]))

                    if pair_key in self._created_pairs:
                        continue

                    user2_topics = self.user_topics_map.get(user2_id, [])
                    topic_prob = self._calculate_follow_probability(user1_topics, user2_topics)

                    # 基础概率大大减少
                    follow_prob = Config.PROB_PEER_EXTENDED
                    rel_type = 'follow'

                    # 根据话题重合度调整概率
                    if self._is_political_echo_chamber(user1_topics, user2_topics):
                        follow_prob = Config.PROB_PEER_EXTENDED * 4  # 政治回音室效应
                    elif topic_prob >= Config.PROB_FOLLOW_TWO_SAME_TOPIC:
                        rel_type = 'friend'
                        follow_prob = min(0.25, Config.PROB_PEER_EXTENDED * 5)
                    elif topic_prob >= Config.PROB_FOLLOW_ONE_SAME_TOPIC:
                        rel_type = 'follow'
                        follow_prob = min(0.18, Config.PROB_PEER_EXTENDED * 3.5)
                    elif topic_prob >= Config.PROB_FOLLOW_TWO_COMMON_CATEGORY:
                        rel_type = 'follow'
                        follow_prob = min(0.12, Config.PROB_PEER_EXTENDED * 2.5)
                    elif topic_prob >= Config.PROB_FOLLOW_ONE_COMMON_CATEGORY:
                        rel_type = 'follow'
                        follow_prob = min(0.08, Config.PROB_PEER_EXTENDED * 1.5)

                    if random.random() < follow_prob:
                        rel = self._create_relationship(
                            from_id=user1_id,
                            to_id=user2_id,
                            rel_type=rel_type,
                            created_offset=random.randint(0, 180),
                            updated_offset=random.randint(180, Config.DATE_RANGE_DAYS),
                            is_active=random.random() < Config.PROB_ACTIVE
                        )
                        self.relationships.append(rel)
                        self._add_relationship_to_network(rel)
                        self._created_pairs.add(pair_key)
                        extended_count += 1

                        if rel_type == 'friend':
                            rel_reverse = self._create_relationship(
                                from_id=user2_id,
                                to_id=user1_id,
                                rel_type='friend',
                                created_offset=random.randint(0, 180),
                                updated_offset=random.randint(180, Config.DATE_RANGE_DAYS),
                                is_active=random.random() < Config.PROB_ACTIVE
                            )
                            self.relationships.append(rel_reverse)
                            self._add_relationship_to_network(rel_reverse)
                            extended_count += 1

        print(f"  生成核心小图内用户关系数：{first_300_count}")
        print(f"  生成扩展用户关系数：{extended_count}")
        print(f"  生成普通用户关系总数：{len(self.relationships) - peer_start_count}")

    def generate_all(self):
        print("=" * 60)
        print("开始生成社交关系数据")
        print("=" * 60)

        self.generate_scale_free_relationships()  # 普通用户关注 KOL
        self.generate_kol_relationships()  # 【新增】KOL 关注其他用户
        self.generate_peer_relationships()  # 普通用户之间关系（含扩展）

        print("=" * 60)
        print(f"生成完成！总关系数：{len(self.relationships)}")
        print("=" * 60)

    def save_relationships(self, output_file: str):
        data = [rel.to_dict() for rel in self.relationships]
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"关系数据已保存至：{output_file}")

    def save_user_networks(self, output_file: str):
        data = [network.to_dict() for network in self.user_networks.values()]
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"用户网络数据已保存至：{output_file}")

    def print_statistics(self):
        print("\n" + "=" * 60)
        print("关系数据统计")
        print("=" * 60)

        follow_count = sum(1 for r in self.relationships if r.type == 'follow')
        friend_count = sum(1 for r in self.relationships if r.type == 'friend')

        print(f"总关系数：{len(self.relationships)}")
        print(f"  - Follow (单向): {follow_count}")
        print(f"  - Friend (双向): {friend_count}")

        active_count = sum(1 for r in self.relationships if r.isActive)
        print(f"活跃关系数：{active_count} ({active_count / len(self.relationships) * 100:.1f}%)")

        print("\nKOL 粉丝数 Top 10:")
        kol_stats = []
        for user in self.kol_users:
            user_id = self._generate_user_id(user['agent_id'])
            if user_id in self.user_networks:
                count = self.user_networks[user_id].statistics['followersCount']
                kol_stats.append((user_id, user.get('user_name', ''), count))

        kol_stats.sort(key=lambda x: x[2], reverse=True)
        for i, (uid, name, count) in enumerate(kol_stats[:10], 1):
            print(f"  {i}. {name}: {count} 粉丝")

        if kol_stats:
            top_10_total = sum(s[2] for s in kol_stats[:10])
            total_follows = sum(s[2] for s in kol_stats)
            print(f"\n  头部 10 个 KOL 粉丝占比：{top_10_total / total_follows * 100:.1f}%")
            print(f"  KOL 平均粉丝数：{total_follows / len(kol_stats):.1f}")

        # 【新增】KOL 关注统计
        print("\nKOL 关注统计:")
        kol_follows_count = 0
        kol_follows_normal_count = 0
        for user in self.kol_users:
            user_id = self._generate_user_id(user['agent_id'])
            if user_id in self.user_networks:
                follows = self.user_networks[user_id].follows
                kol_follows_count += len(follows)
                for rel in follows:
                    if rel.toUserId.startswith('user_'):
                        target_id = rel.toUserId
                        if target_id not in [self._generate_user_id(k['agent_id']) for k in self.kol_users]:
                            kol_follows_normal_count += 1

        print(f"  KOL 总关注数：{kol_follows_count}")
        print(f"  KOL 关注其他 KOL 数：{kol_follows_count - kol_follows_normal_count}")
        print(f"  KOL 关注普通用户数：{kol_follows_normal_count}")

        print("\n网络结构统计:")
        total_users = len(self.users)
        total_possible = total_users * (total_users - 1)
        density = len(self.relationships) / total_possible * 100 if total_possible > 0 else 0
        print(f"  用户总数：{total_users}")
        print(f"  网络密度：{density:.4f}%")
        print(f"  人均关系数：{len(self.relationships) / total_users:.2f}")


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    USERS_FILE = os.path.join(data_dir, "users.json")
    TOPICS_FILE = os.path.join(data_dir, "topics.json")
    RELATIONSHIPS_OUTPUT = os.path.join(data_dir, "relationships.json")
    NETWORKS_OUTPUT = os.path.join(data_dir, "user_networks.json")

    generator = RelationshipGenerator(USERS_FILE, TOPICS_FILE)
    generator.generate_all()
    generator.save_relationships(RELATIONSHIPS_OUTPUT)
    generator.save_user_networks(NETWORKS_OUTPUT)
    generator.print_statistics()

    total_users = len(generator.users)
    total_possible = total_users * (total_users - 1)
    density_ratio = (
        len(generator.relationships) / total_possible if total_possible > 0 else 0.0
    )
    metrics_path = os.path.join(data_dir, "graph_metrics.json")
    metrics = {
        "user_count": total_users,
        "relationship_edge_count": len(generator.relationships),
        "network_density_ratio": density_ratio,
        "network_density_percent": density_ratio * 100.0,
    }
    with open(metrics_path, "w", encoding="utf-8") as mf:
        json.dump(metrics, mf, ensure_ascii=False, indent=2)
    print(f"指标已写入：{metrics_path}")

    print("\n" + "=" * 60)
    print("生成完成！")
    print("=" * 60)


if __name__ == '__main__':
    main()