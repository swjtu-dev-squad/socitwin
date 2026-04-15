"""
Metrics Manager - Orchestration and caching layer for OASIS metrics

This module provides centralized management for all metrics calculation
with caching, coordination, and error handling.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from app.core.llm_evaluator import get_llm_evaluator
from app.models.metrics import MetricsSummary
from app.services.metrics.herd_effect_service import HerdEffectService
from app.services.metrics.polarization_service import PolarizationService
from app.services.metrics.propagation_service import PropagationService
from app.utils import metrics_db

logger = logging.getLogger(__name__)


class TTLCache:
    """
    Simple TTL-based cache for metric results

    Attributes:
        maxsize: Maximum number of entries
        ttl: Time-to-live in seconds
    """

    def __init__(self, maxsize: int = 1000, ttl: int = 300):
        """
        Initialize cache

        Args:
            maxsize: Maximum number of entries
            ttl: Time-to-live in seconds
        """
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: Dict[str, tuple] = {}  # key -> (value, timestamp)

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache if not expired

        Args:
            key: Cache key

        Returns:
            Cached value or None if expired/not found
        """
        if key in self._cache:
            value, timestamp = self._cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.ttl):
                return value
            else:
                # Expired
                del self._cache[key]
        return None

    async def set(self, key: str, value: Any):
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
        """
        if len(self._cache) >= self.maxsize:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[key] = (value, datetime.now())

    async def invalidate(self, key: str):
        """
        Invalidate specific cache entry

        Args:
            key: Cache key to invalidate
        """
        if key in self._cache:
            del self._cache[key]

    async def clear(self):
        """Clear all cache entries"""
        self._cache.clear()


class MetricsManager:
    """
    Centralized metrics calculation and caching

    Orchestrates all three metric services with intelligent caching
    and parallel computation.
    """

    def __init__(self, db_path: str, enable_db_persistence: bool = True):
        """
        Initialize metrics manager

        Args:
            db_path: Path to SQLite database
            enable_db_persistence: Whether to save metrics to database
        """
        self.db_path = db_path
        self.enable_db_persistence = enable_db_persistence
        self.current_step = 0

        # Initialize services
        self.propagation_service = PropagationService(db_path)
        self.herd_service = HerdEffectService(db_path)

        # Polarization service needs LLM evaluator
        llm_evaluator = get_llm_evaluator()
        self.polarization_service = PolarizationService(db_path, llm_evaluator)

        # Get cache TTL from config
        from app.core.config import get_settings
        settings = get_settings()
        cache_ttl = getattr(settings, 'METRICS_CACHE_TTL', 300)

        # Cache with configurable TTL (0 means disabled)
        # If cache_ttl is 0, all caches are disabled (metrics always recalculated)
        if cache_ttl == 0:
            logger.info("Metrics cache disabled (TTL=0)")
            self.caches = {
                'propagation': TTLCache(maxsize=1, ttl=0),
                'polarization': TTLCache(maxsize=1, ttl=0),
                'herd_effect': TTLCache(maxsize=1, ttl=0),
            }
        else:
            # Use different TTLs per metric based on config base
            self.caches = {
                'propagation': TTLCache(maxsize=100, ttl=cache_ttl),  # Use config TTL
                'polarization': TTLCache(maxsize=100, ttl=max(cache_ttl, 3600)),  # At least 1 hour for expensive LLM
                'herd_effect': TTLCache(maxsize=100, ttl=max(cache_ttl // 2, 60)),  # Half of config TTL, min 1 min
            }
            logger.info(f"Metrics cache enabled with TTL: propagation={cache_ttl}s, polarization={max(cache_ttl, 3600)}s, herd_effect={max(cache_ttl // 2, 60)}s")

        # Create metrics table if persistence enabled
        if self.enable_db_persistence:
            metrics_db.create_metrics_table(db_path)
            logger.info(f"MetricsManager initialized with db persistence: {db_path}")
        else:
            logger.info(f"MetricsManager initialized without db persistence: {db_path}")

    async def update_all_metrics(
        self,
        current_step: int,
        force_polarization: bool = False
    ):
        """
        Update all metrics asynchronously

        Calculates metrics in parallel where possible, respecting cache TTL.

        Args:
            current_step: Current simulation step
            force_polarization: Force polarization calculation regardless of step interval
        """
        # Store current step for database persistence
        self.current_step = current_step
        logger.info(f"📊 update_all_metrics called: step={current_step}, force_polarization={force_polarization}")

        try:
            tasks = []
            metrics_to_update = []

            # Check cache and schedule updates
            propagation_expired = await self._is_cache_expired('propagation')
            logger.info(f"  propagation_expired: {propagation_expired}")
            if propagation_expired:
                tasks.append(self._update_propagation())
                metrics_to_update.append('propagation')

            herd_expired = await self._is_cache_expired('herd_effect')
            logger.info(f"  herd_expired: {herd_expired}")
            if herd_expired:
                tasks.append(self._update_herd_effect())
                metrics_to_update.append('herd_effect')

            # Polarization: check if we should calculate
            polarization_expired = await self._is_cache_expired('polarization')
            should_calculate_polarization = force_polarization or polarization_expired
            logger.info(f"  polarization_expired: {polarization_expired}, should_calculate: {should_calculate_polarization}")

            if should_calculate_polarization:
                tasks.append(self._update_polarization())
                metrics_to_update.append('polarization')

            if tasks:
                logger.info(
                    f"⚡ Updating metrics: {metrics_to_update} "
                    f"at step {current_step}"
                )

                # Run all updates in parallel
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Log any exceptions
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"  ❌ Metric {metrics_to_update[i]} update failed: {result}")

                logger.info(f"✅ Metrics update completed at step {current_step}")
            else:
                logger.info(f"⏸️  All metrics cached (skip update) at step {current_step}")

        except Exception as e:
            logger.error(f"Failed to update metrics: {e}")

    async def get_metrics_summary(self) -> MetricsSummary:
        """
        Get current metrics summary

        Returns cached or freshly calculated metrics.

        Returns:
            MetricsSummary with all three metrics
        """
        try:
            # Try to get from cache first
            propagation = await self.caches['propagation'].get('propagation')
            polarization = await self.caches['polarization'].get('polarization')
            herd_effect = await self.caches['herd_effect'].get('herd_effect')

            # Calculate missing metrics
            if not propagation:
                propagation = await self.propagation_service.get_metrics()
                await self.caches['propagation'].set('propagation', propagation)

            if not polarization:
                try:
                    polarization = await self.polarization_service.get_metrics()
                    await self.caches['polarization'].set('polarization', polarization)
                except Exception as e:
                    logger.warning(f"Failed to calculate polarization: {e}")
                    polarization = None

            if not herd_effect:
                herd_effect = await self.herd_service.get_metrics()
                await self.caches['herd_effect'].set('herd_effect', herd_effect)

            # Get current step from database
            current_step = await self._get_current_step()

            return MetricsSummary(
                propagation=propagation,
                polarization=polarization,
                herd_effect=herd_effect,
                current_step=current_step,
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.error(f"Failed to get metrics summary: {e}")
            raise

    async def _update_propagation(self):
        """Update propagation metrics"""
        try:
            metrics = await self.propagation_service.get_metrics()
            await self.caches['propagation'].set('propagation', metrics)

            # Save to database if enabled
            if self.enable_db_persistence:
                metrics_db.save_metrics(
                    self.db_path,
                    self.current_step,
                    'propagation',
                    metrics
                )

            logger.debug(f"Propagation metrics updated: scale={metrics.scale}")
        except Exception as e:
            logger.error(f"Failed to update propagation: {e}")

    async def _update_polarization(self):
        """Update polarization metrics"""
        try:
            metrics = await self.polarization_service.get_metrics()
            await self.caches['polarization'].set('polarization', metrics)

            # Save to database if enabled
            if self.enable_db_persistence:
                metrics_db.save_metrics(
                    self.db_path,
                    self.current_step,
                    'polarization',
                    metrics
                )

            logger.debug(
                f"Polarization metrics updated: "
                f"direction={metrics.average_direction}, "
                f"magnitude={metrics.average_magnitude:.2f}"
            )
        except Exception as e:
            logger.error(f"Failed to update polarization: {e}")
            # Don't cache failed polarization
            raise

    async def _update_herd_effect(self):
        """Update herd effect metrics"""
        try:
            metrics = await self.herd_service.get_metrics()
            await self.caches['herd_effect'].set('herd_effect', metrics)

            # Save to database if enabled
            if self.enable_db_persistence:
                metrics_db.save_metrics(
                    self.db_path,
                    self.current_step,
                    'herd_effect',
                    metrics
                )

            logger.debug(
                f"Herd effect metrics updated: "
                f"conformity={metrics.conformity_index:.2f}"
            )
        except Exception as e:
            logger.error(f"Failed to update herd effect: {e}")

    async def _is_cache_expired(self, metric_name: str) -> bool:
        """
        Check if cache for a metric is expired

        Args:
            metric_name: Name of metric ('propagation', 'polarization', 'herd_effect')

        Returns:
            True if cache expired or missing, False otherwise
        """
        value = await self.caches[metric_name].get(metric_name)
        return value is None

    async def _get_current_step(self) -> int:
        """
        Get current simulation step from database

        Returns:
            Current step number
        """
        import os
        import sqlite3

        try:
            if not os.path.exists(self.db_path):
                return 0

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM post")
                # Approximate: use post count as step proxy
                return cursor.fetchone()[0] or 0
        except Exception as e:
            logger.warning(f"Failed to get current step: {e}")
            return 0


# ============================================================================
# Singleton Instance
# ============================================================================

_metrics_manager: Optional[MetricsManager] = None


async def get_metrics_manager(db_path: Optional[str] = None) -> Optional[MetricsManager]:
    """
    Get metrics manager singleton instance

    Args:
        db_path: Optional database path (uses OASIS default if None)

    Returns:
        MetricsManager instance or None if no database available
    """
    global _metrics_manager

    if _metrics_manager is None:
        if db_path is None:
            # Try to get from OASIS manager
            from app.core.dependencies import get_oasis_manager
            oasis_manager = await get_oasis_manager()
            db_path = oasis_manager._db_path

        if db_path and os.path.exists(db_path):
            _metrics_manager = MetricsManager(db_path)
            logger.info(f"Metrics Manager singleton created with db: {db_path}")
        else:
            logger.warning("Cannot create Metrics Manager: no valid database path")
            return None

    return _metrics_manager


def reset_metrics_manager():
    """Reset metrics manager singleton (mainly for testing)"""
    global _metrics_manager
    _metrics_manager = None
    logger.info("Metrics Manager singleton reset")
