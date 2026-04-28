"""
Topic Loader - Configuration management for simulation topics

Handles loading, validation, and hot-reloading of topic configurations from YAML files.
"""

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from app.models.topics import Topic, TopicConfig

logger = logging.getLogger(__name__)


class TopicLoadError(Exception):
    """Topic loading error"""
    pass


class TopicValidationError(Exception):
    """Topic validation error"""
    pass


class TopicLoader:
    """
    Topic configuration loader with hot-reload support

    Singleton pattern for consistent access across the application.
    Manages loading and validation of topic configurations from YAML files.
    """

    _instance: Optional['TopicLoader'] = None

    def __new__(cls, config_path: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        if self._initialized:
            return

        # Set default config path if not provided
        if config_path is None:
            # Default path relative to the backend directory
            backend_dir = Path(__file__).parent.parent.parent
            config_path = str(backend_dir / "config" / "topics.yaml")

        self._config_path = config_path
        self._topics: Dict[str, Topic] = {}
        self._last_loaded: Optional[float] = None
        self._config: Optional[TopicConfig] = None

        # Load configuration on initialization
        self._load_config()

        # Mark as initialized
        self._initialized = True

        logger.info(f"Topic Loader initialized with config: {self._config_path}")

    def _load_config(self) -> None:
        """
        Load and validate topics from YAML configuration file

        Raises:
            TopicLoadError: If file cannot be read
            TopicValidationError: If configuration is invalid
        """
        try:
            # Check if file exists
            if not os.path.exists(self._config_path):
                logger.warning(f"Topics config file not found: {self._config_path}")
                # Create empty config
                self._config = TopicConfig(topics=[])
                self._topics = {}
                self._last_loaded = time.time()
                return

            # Read YAML file
            with open(self._config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if not data or 'topics' not in data:
                logger.warning(f"No topics found in config file: {self._config_path}")
                self._config = TopicConfig(topics=[])
                self._topics = {}
                self._last_loaded = time.time()
                return

            # Validate and parse configuration
            self._config = TopicConfig(**data)

            # Build topic lookup dictionary
            self._topics = {}
            for topic in self._config.topics:
                if topic.id in self._topics:
                    logger.warning(f"Duplicate topic ID: {topic.id}. Overwriting.")
                self._topics[topic.id] = topic

            self._last_loaded = time.time()

            logger.info(f"Loaded {len(self._topics)} topics from {self._config_path}")

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML config: {e}")
            raise TopicLoadError(f"Invalid YAML format: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to load topics config: {e}")
            raise TopicLoadError(f"Configuration loading failed: {str(e)}")

    def reload(self) -> Dict[str, Any]:
        """
        Reload configuration from disk

        Returns:
            Dictionary with reload status and statistics

        Raises:
            TopicLoadError: If reload fails
        """
        try:
            start_time = time.time()
            old_count = len(self._topics)

            # Reload configuration
            self._load_config()

            reload_time = time.time() - start_time
            new_count = len(self._topics)

            return {
                "success": True,
                "message": f"Reloaded {new_count} topics in {reload_time:.3f}s",
                "topics_loaded": new_count,
                "previous_count": old_count,
                "reload_time": reload_time,
            }

        except Exception as e:
            logger.error(f"Failed to reload topics: {e}")
            raise TopicLoadError(f"Reload failed: {str(e)}")

    def get_topic(self, topic_id: str) -> Optional[Topic]:
        """
        Get a topic by ID

        Args:
            topic_id: Unique topic identifier

        Returns:
            Topic if found, None otherwise
        """
        return self._topics.get(topic_id)

    def list_topics(self) -> List[Topic]:
        """
        Get all available topics

        Returns:
            List of all topics
        """
        return list(self._topics.values())

    def get_all_ids(self) -> List[str]:
        """
        Get all topic IDs

        Returns:
            List of topic IDs
        """
        return list(self._topics.keys())

    def count(self) -> int:
        """
        Get total number of topics

        Returns:
            Number of topics
        """
        return len(self._topics)

    def exists(self, topic_id: str) -> bool:
        """
        Check if a topic exists

        Args:
            topic_id: Topic identifier

        Returns:
            True if topic exists, False otherwise
        """
        return topic_id in self._topics

    def get_last_loaded_time(self) -> Optional[float]:
        """
        Get the timestamp when configuration was last loaded

        Returns:
            Unix timestamp or None if never loaded
        """
        return self._last_loaded

    def get_config_path(self) -> str:
        """
        Get the configuration file path

        Returns:
            Path to configuration file
        """
        return self._config_path

    def is_empty(self) -> bool:
        """
        Check if no topics are loaded

        Returns:
            True if no topics loaded, False otherwise
        """
        return len(self._topics) == 0


# ============================================================================
# Singleton access function
# ============================================================================

_topic_loader: Optional[TopicLoader] = None


def get_topic_loader(config_path: Optional[str] = None) -> TopicLoader:
    """
    Get the TopicLoader singleton instance

    Args:
        config_path: Optional custom configuration path

    Returns:
        TopicLoader singleton instance
    """
    global _topic_loader

    if _topic_loader is None:
        _topic_loader = TopicLoader(config_path)
        logger.info("Topic Loader singleton created")

    return _topic_loader


def reset_topic_loader():
    """
    Reset the TopicLoader singleton (mainly for testing)

    Warning: This should only be used in testing scenarios
    """
    global _topic_loader
    _topic_loader = None
    logger.info("Topic Loader singleton reset")
