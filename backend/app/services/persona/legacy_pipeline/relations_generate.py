from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple, cast


class Config:
    BASE_DATE = datetime(2024, 1, 1)
    DATE_RANGE_DAYS = 365
    PROB_FOLLOW_BASE = 0.20
    PROB_FOLLOW_NO_COMMON_CATEGORY = 0.00
    PROB_FOLLOW_ONE_COMMON_CATEGORY = 0.10
    PROB_FOLLOW_TWO_COMMON_CATEGORY = 0.15
    PROB_FOLLOW_ONE_SAME_TOPIC = 0.15
    PROB_FOLLOW_TWO_SAME_TOPIC = 0.25
    PROB_ECHO_CHAMBER = 0.60
    PROB_ACTIVE = 0.90
    PROB_KOL_FOLLOW_KOL = 0.10
    PROB_KOL_FOLLOW_NORMAL = 0.10
    PROB_PEER_EXTENDED = 0.10
    KOL_FOLLOW_MIN = 5
    KOL_FOLLOW_MAX = 12
    PEER_CONNECTION_MIN = 3
    PEER_CONNECTION_MAX = 8
    PEER_NETWORK_NORMAL_RATIO = 0.20
    KOL_POPULARITY_EXPONENT = 1.5
    TOP_KOL_RATIO = 0.2
    TOPIC_CATEGORIES: Dict[str, List[str]] = {}


@dataclass
class SocialRelationship:
    id: str
    fromUserId: str  # noqa: N815
    toUserId: str  # noqa: N815
    type: str
    createdAt: datetime  # noqa: N815
    updatedAt: datetime  # noqa: N815
    isActive: bool  # noqa: N815

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "fromUserId": self.fromUserId,
            "toUserId": self.toUserId,
            "type": self.type,
            "createdAt": self.createdAt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "updatedAt": self.updatedAt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "isActive": self.isActive,
        }


class UserNetwork:
    def __init__(self, user_id: str):
        self.userId = user_id
        self.followers: List[SocialRelationship] = []
        self.follows: List[SocialRelationship] = []
        self.friends: List[SocialRelationship] = []
        self.statistics = {
            "followersCount": 0,
            "followsCount": 0,
            "friendsCount": 0,
            "lastUpdated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "userId": self.userId,
            "followers": [x.to_dict() for x in self.followers],
            "follows": [x.to_dict() for x in self.follows],
            "friends": [x.to_dict() for x in self.friends],
            "statistics": self.statistics,
        }


class RelationshipGenerator:
    def __init__(self, users_file: Path, topics_file: Path):
        self.users = self._coerce_users_payload(json.loads(users_file.read_text(encoding="utf-8")))
        self.topics_classification = json.loads(topics_file.read_text(encoding="utf-8"))
        self.user_topics_map: Dict[str, List[str]] = {}
        self.kol_users: List[Dict[str, Any]] = []
        self.normal_users: List[Dict[str, Any]] = []
        self.kol_popularity_weights: List[float] = []
        self.peer_network_size = 0
        self.relationships: List[SocialRelationship] = []
        self.user_networks: Dict[str, UserNetwork] = {}
        self._rel_index = 1
        self._created_pairs: Set[Tuple[str, str]] = set()
        self._load_topic_categories()
        self._preprocess_data()
        self._calculate_kol_popularity_weights()

    @staticmethod
    def _coerce_users_payload(raw: Any) -> List[Dict[str, Any]]:
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict) and isinstance(raw.get("data"), list):
            return raw["data"]
        raise ValueError("users.json 顶层格式不正确")

    def _load_topic_categories(self) -> None:
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
        else:
            Config.TOPIC_CATEGORIES = {"Politics": [], "Economics": [], "Society": []}

    def _generate_user_id(self, agent_id: int) -> str:
        return f"user_{agent_id}"

    def _uid(self, user: Dict[str, Any]) -> str:
        return self._generate_user_id(int(user["agent_id"]))

    def _generate_relationship_id(self) -> str:
        out = f"rel_{self._rel_index:06d}"
        self._rel_index += 1
        return out

    def _generate_timestamp(self, offset_days: int) -> datetime:
        return Config.BASE_DATE + timedelta(days=offset_days)

    def _preprocess_data(self) -> None:
        for user in self.users:
            uid = self._generate_user_id(int(user["agent_id"]))
            topics = user.get("profile", {}).get("other_info", {}).get("topics", [])
            self.user_topics_map[uid] = topics if isinstance(topics, list) else []
            if user.get("user_type") == "kol":
                self.kol_users.append(user)
            else:
                self.normal_users.append(user)
            self.user_networks[uid] = UserNetwork(uid)
        self.peer_network_size = int(len(self.normal_users) * Config.PEER_NETWORK_NORMAL_RATIO)

    def _get_user_topic_categories(self, topics: List[str]) -> Dict[str, List[str]]:
        out = {"Politics": [], "Economics": [], "Society": [], "Unknown": []}
        for t in topics:
            low = str(t).lower()
            matched = "Unknown"
            for category, arr in Config.TOPIC_CATEGORIES.items():
                for ct in arr:
                    c_low = str(ct).lower()
                    if c_low == low or low in c_low or c_low in low:
                        matched = category
                        break
                if matched != "Unknown":
                    break
            out[matched].append(str(t))
        return out

    def _calculate_follow_probability(self, topics1: List[str], topics2: List[str]) -> float:
        if not topics1 or not topics2:
            return Config.PROB_FOLLOW_NO_COMMON_CATEGORY
        categories1 = self._get_user_topic_categories(topics1)
        categories2 = self._get_user_topic_categories(topics2)
        common_categories = 0
        for category in ("Politics", "Economics", "Society"):
            if categories1.get(category) and categories2.get(category):
                common_categories += 1
        set1 = {str(x).lower() for x in topics1}
        set2 = {str(x).lower() for x in topics2}
        same = len(set1 & set2)
        if same >= 2:
            return Config.PROB_FOLLOW_TWO_SAME_TOPIC
        if same == 1:
            return Config.PROB_FOLLOW_ONE_SAME_TOPIC
        if common_categories >= 2:
            return Config.PROB_FOLLOW_TWO_COMMON_CATEGORY
        if common_categories == 1:
            return Config.PROB_FOLLOW_ONE_COMMON_CATEGORY
        return Config.PROB_FOLLOW_NO_COMMON_CATEGORY

    def _is_political_echo_chamber(self, topics1: List[str], topics2: List[str]) -> bool:
        c1 = self._get_user_topic_categories(topics1)
        c2 = self._get_user_topic_categories(topics2)
        return bool(c1.get("Politics")) and bool(c2.get("Politics"))

    def _create_relationship(self, from_id: str, to_id: str, rel_type: str) -> SocialRelationship:
        return SocialRelationship(
            id=self._generate_relationship_id(),
            fromUserId=from_id,
            toUserId=to_id,
            type=rel_type,
            createdAt=self._generate_timestamp(random.randint(0, 180)),
            updatedAt=self._generate_timestamp(random.randint(180, Config.DATE_RANGE_DAYS)),
            isActive=random.random() < Config.PROB_ACTIVE,
        )

    def _add_relationship_to_network(self, rel: SocialRelationship) -> None:
        if rel.type == "follow":
            self.user_networks[rel.fromUserId].follows.append(rel)
            self.user_networks[rel.fromUserId].statistics["followsCount"] += 1
            self.user_networks[rel.toUserId].followers.append(rel)
            self.user_networks[rel.toUserId].statistics["followersCount"] += 1
        elif rel.type == "friend":
            self.user_networks[rel.fromUserId].friends.append(rel)
            self.user_networks[rel.fromUserId].statistics["friendsCount"] += 1
            self.user_networks[rel.toUserId].friends.append(rel)
            self.user_networks[rel.toUserId].statistics["friendsCount"] += 1

    def _append_relationship(self, src: str, dst: str, rel_type: str, pair_key: Tuple[str, str]) -> None:
        rel = self._create_relationship(src, dst, rel_type)
        self.relationships.append(rel)
        self._add_relationship_to_network(rel)
        self._created_pairs.add(pair_key)
        if rel_type == "friend":
            rev = self._create_relationship(dst, src, "friend")
            self.relationships.append(rev)
            self._add_relationship_to_network(rev)

    def _calculate_kol_popularity_weights(self) -> None:
        n = len(self.kol_users)
        if n <= 0:
            self.kol_popularity_weights = []
            return
        arr = [(i + 1) ** (-Config.KOL_POPULARITY_EXPONENT) for i in range(n)]
        s = sum(arr) or 1.0
        self.kol_popularity_weights = [x / s for x in arr]

    def generate_scale_free_relationships(self) -> None:
        if not self.kol_users:
            return
        kol_ids = [self._uid(k) for k in self.kol_users]
        for normal_user in self.normal_users:
            normal_id = self._uid(normal_user)
            normal_topics = self.user_topics_map.get(normal_id, [])
            num_kol_follows = random.randint(Config.KOL_FOLLOW_MIN, Config.KOL_FOLLOW_MAX)
            selected = set(random.choices(range(len(self.kol_users)), weights=self.kol_popularity_weights, k=num_kol_follows))
            for idx in selected:
                kol_id = kol_ids[idx]
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
                    self._append_relationship(normal_id, kol_id, "follow", pair_key)

    def generate_kol_relationships(self) -> None:
        kol_ids = [self._uid(k) for k in self.kol_users]
        for i, kol_user in enumerate(self.kol_users):
            kol_id = kol_ids[i]
            kol_topics = self.user_topics_map.get(kol_id, [])
            other = [j for j in range(len(self.kol_users)) if j != i]
            for j in random.sample(other, min(len(other), random.randint(20, 30))):
                target_id = kol_ids[j]
                pair_key = (kol_id, target_id)
                if pair_key in self._created_pairs:
                    continue
                target_topics = self.user_topics_map.get(target_id, [])
                topic_prob = self._calculate_follow_probability(kol_topics, target_topics)
                follow_prob = Config.PROB_KOL_FOLLOW_KOL
                if self._is_political_echo_chamber(kol_topics, target_topics):
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
                    self._append_relationship(kol_id, target_id, "follow", pair_key)

        for kol_user in self.kol_users:
            kol_id = self._generate_user_id(int(kol_user["agent_id"]))
            kol_topics = self.user_topics_map.get(kol_id, [])
            candidate_scores: List[Tuple[str, List[str], float]] = []
            for normal_user in self.normal_users:
                nid = self._uid(normal_user)
                nt = self.user_topics_map.get(nid, [])
                tp = self._calculate_follow_probability(kol_topics, nt)
                if tp > 0:
                    candidate_scores.append((nid, nt, tp))
            candidate_scores.sort(key=lambda x: x[2], reverse=True)
            if not candidate_scores:
                continue
            limit = min(50, len(candidate_scores))
            weights = [candidate_scores[i][2] + 0.01 for i in range(limit)]
            s = sum(weights) or 1.0
            weights = [w / s for w in weights]
            picked = set(random.choices(range(limit), weights=weights, k=random.randint(4, 7)))
            for idx in picked:
                normal_id, normal_topics, topic_prob = candidate_scores[idx]
                pair_key = (kol_id, normal_id)
                if pair_key in self._created_pairs:
                    continue
                follow_prob = Config.PROB_KOL_FOLLOW_NORMAL
                if self._is_political_echo_chamber(kol_topics, normal_topics):
                    follow_prob = Config.PROB_KOL_FOLLOW_NORMAL * 3
                elif topic_prob >= Config.PROB_FOLLOW_TWO_SAME_TOPIC:
                    follow_prob = min(0.30, Config.PROB_KOL_FOLLOW_NORMAL * 4)
                elif topic_prob >= Config.PROB_FOLLOW_ONE_SAME_TOPIC:
                    follow_prob = min(0.20, Config.PROB_KOL_FOLLOW_NORMAL * 2.5)
                elif topic_prob >= Config.PROB_FOLLOW_TWO_COMMON_CATEGORY:
                    follow_prob = min(0.10, Config.PROB_KOL_FOLLOW_NORMAL * 1.5)
                if random.random() < follow_prob:
                    self._append_relationship(kol_id, normal_id, "follow", pair_key)

    def generate_peer_relationships(self) -> None:
        core_users = self.normal_users[: self.peer_network_size]
        for i, u1 in enumerate(core_users):
            id1 = self._uid(u1)
            topics1 = self.user_topics_map.get(id1, [])
            peer_range = random.randint(Config.PEER_CONNECTION_MIN, Config.PEER_CONNECTION_MAX)
            candidates = core_users[i + 1 : i + 1 + peer_range * 2]
            for u2 in candidates:
                id2 = self._uid(u2)
                pair_key = cast(Tuple[str, str], tuple(sorted([id1, id2])))
                if pair_key in self._created_pairs:
                    continue
                topics2 = self.user_topics_map.get(id2, [])
                topic_prob = self._calculate_follow_probability(topics1, topics2)
                rel_type = "follow"
                follow_prob = Config.PROB_FOLLOW_BASE
                if self._is_political_echo_chamber(topics1, topics2):
                    follow_prob = Config.PROB_ECHO_CHAMBER
                elif topic_prob >= Config.PROB_FOLLOW_TWO_SAME_TOPIC:
                    rel_type = "friend"
                    follow_prob = 0.80
                elif topic_prob >= Config.PROB_FOLLOW_ONE_SAME_TOPIC:
                    follow_prob = 0.75
                else:
                    follow_prob = 0.65
                if random.random() < follow_prob:
                    self._append_relationship(id1, id2, rel_type, pair_key)

        ext_users = self.normal_users[self.peer_network_size :]
        for i, u1 in enumerate(ext_users):
            id1 = self._uid(u1)
            topics1 = self.user_topics_map.get(id1, [])
            candidates = ext_users[i + 1 : i + 1 + random.randint(2, 5) * 2]
            if core_users and random.random() < 0.3:
                candidates.extend(random.sample(core_users, min(len(core_users), random.randint(4, 5))))
            for u2 in candidates:
                id2 = self._uid(u2)
                pair_key = cast(Tuple[str, str], tuple(sorted([id1, id2])))
                if pair_key in self._created_pairs:
                    continue
                topics2 = self.user_topics_map.get(id2, [])
                topic_prob = self._calculate_follow_probability(topics1, topics2)
                rel_type = "follow"
                follow_prob = Config.PROB_PEER_EXTENDED
                if self._is_political_echo_chamber(topics1, topics2):
                    follow_prob = Config.PROB_PEER_EXTENDED * 4
                elif topic_prob >= Config.PROB_FOLLOW_TWO_SAME_TOPIC:
                    rel_type = "friend"
                    follow_prob = min(0.25, Config.PROB_PEER_EXTENDED * 5)
                elif topic_prob >= Config.PROB_FOLLOW_ONE_SAME_TOPIC:
                    follow_prob = min(0.18, Config.PROB_PEER_EXTENDED * 3.5)
                elif topic_prob >= Config.PROB_FOLLOW_TWO_COMMON_CATEGORY:
                    follow_prob = min(0.12, Config.PROB_PEER_EXTENDED * 2.5)
                elif topic_prob >= Config.PROB_FOLLOW_ONE_COMMON_CATEGORY:
                    follow_prob = min(0.08, Config.PROB_PEER_EXTENDED * 1.5)
                if random.random() < follow_prob:
                    self._append_relationship(id1, id2, rel_type, pair_key)

    def generate_all(self) -> None:
        self.generate_scale_free_relationships()
        self.generate_kol_relationships()
        self.generate_peer_relationships()


def generate_relationship_and_network_files(data_dir: Path) -> dict[str, Any]:
    users_file = data_dir / "users.json"
    topics_file = data_dir / "topics.json"
    if not users_file.is_file():
        raise FileNotFoundError(f"未找到 {users_file}")
    if not topics_file.is_file():
        raise FileNotFoundError(f"未找到 {topics_file}")
    generator = RelationshipGenerator(users_file, topics_file)
    generator.generate_all()
    rels_path = data_dir / "relationships.json"
    nets_path = data_dir / "user_networks.json"
    rel_data = [x.to_dict() for x in generator.relationships]
    net_data = [x.to_dict() for x in generator.user_networks.values()]
    rels_path.write_text(json.dumps(rel_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    nets_path.write_text(json.dumps(net_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    total_users = len(generator.users)
    total_possible = total_users * (total_users - 1)
    density_ratio = len(generator.relationships) / total_possible if total_possible > 0 else 0.0
    metrics = {
        "user_count": total_users,
        "relationship_edge_count": len(generator.relationships),
        "network_density_ratio": density_ratio,
        "network_density_percent": density_ratio * 100.0,
    }
    (data_dir / "graph_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metrics
