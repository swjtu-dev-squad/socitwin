"""
Polarization Service - Group polarization metrics using LLM evaluation

This service calculates group polarization by comparing initial opinions
to current opinions using LLM-based evaluation.
"""

import asyncio
import logging
import sqlite3
from typing import Any, Dict, List, Optional

from app.core.llm_evaluator import LLMAPIError, get_llm_evaluator
from app.models.metrics import AgentPolarization, PolarizationDirection, PolarizationMetrics

logger = logging.getLogger(__name__)


class PolarizationService:
    """
    Calculate group polarization using LLM evaluation

    Compares agents' initial opinions to their current opinions to measure
    opinion shift and extremification.
    """

    def __init__(self, db_path: str, llm_evaluator=None):
        """
        Initialize polarization service

        Args:
            db_path: Path to SQLite database
            llm_evaluator: Optional LLM evaluator instance
        """
        self.db_path = db_path
        self.llm_evaluator = llm_evaluator or get_llm_evaluator()
        logger.info(f"PolarizationService initialized with db: {db_path}")

    async def get_metrics(
        self,
        agent_ids: Optional[List[int]] = None,
        batch_size: int = 10
    ) -> PolarizationMetrics:
        """
        Get polarization metrics

        Args:
            agent_ids: Specific agents to evaluate, or None for all
            batch_size: Number of agents to evaluate per LLM batch

        Returns:
            PolarizationMetrics with direction, magnitude, and per-agent details

        Raises:
            LLMAPIError: If LLM evaluation fails
        """
        try:
            # Get agents to evaluate
            agents = await self._get_agents_to_evaluate(agent_ids)

            if not agents:
                logger.info("No agents found for polarization evaluation")
                return PolarizationMetrics(
                    average_direction=PolarizationDirection.NEUTRAL,
                    average_magnitude=0.0,
                    agent_polarization=[],
                    total_agents_evaluated=0
                )

            # Batch evaluate agents
            agent_polarization = await self._evaluate_agents_batch(
                agents,
                batch_size=batch_size
            )

            if not agent_polarization:
                logger.warning("All agent evaluations failed")
                return PolarizationMetrics(
                    average_direction=PolarizationDirection.NEUTRAL,
                    average_magnitude=0.0,
                    agent_polarization=[],
                    total_agents_evaluated=0
                )

            # Calculate aggregate metrics
            avg_direction = self._calculate_average_direction(agent_polarization)
            avg_magnitude = sum(
                a['magnitude'] for a in agent_polarization
            ) / len(agent_polarization)

            logger.info(
                f"Polarization metrics: direction={avg_direction}, "
                f"magnitude={avg_magnitude:.2f}, agents={len(agent_polarization)}"
            )

            return PolarizationMetrics(
                average_direction=avg_direction,
                average_magnitude=avg_magnitude,
                agent_polarization=[
                    AgentPolarization(**a) for a in agent_polarization
                ],
                total_agents_evaluated=len(agent_polarization)
            )

        except LLMAPIError as e:
            logger.error(f"LLM evaluation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to calculate polarization metrics: {e}")
            raise

    async def _get_agents_to_evaluate(
        self,
        agent_ids: Optional[List[int]]
    ) -> List[Dict[str, Any]]:
        """
        Get agent data from database

        Args:
            agent_ids: Optional list of specific agent IDs

        Returns:
            List of agent dictionaries with metadata
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if agent_ids:
                placeholders = ','.join('?' * len(agent_ids))
                query = f"""
                    SELECT
                        p.user_id,
                        u.user_name,
                        MIN(p.post_id) as first_post_id,
                        MAX(p.post_id) as last_post_id,
                        COUNT(*) as post_count
                    FROM post p
                    JOIN user u ON p.user_id = u.user_id
                    WHERE p.user_id IN ({placeholders})
                    GROUP BY p.user_id
                """
                cursor.execute(query, agent_ids)
            else:
                cursor.execute("""
                    SELECT
                        p.user_id,
                        u.user_name,
                        MIN(p.post_id) as first_post_id,
                        MAX(p.post_id) as last_post_id,
                        COUNT(*) as post_count
                    FROM post p
                    JOIN user u ON p.user_id = u.user_id
                    GROUP BY p.user_id
                    HAVING post_count >= 2
                    ORDER BY p.user_id
                """)

            return [dict(row) for row in cursor.fetchall()]

    async def _evaluate_agents_batch(
        self,
        agents: List[Dict[str, Any]],
        batch_size: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Evaluate agents in batches using LLM

        Args:
            agents: List of agent metadata
            batch_size: Number of agents per batch

        Returns:
            List of polarization evaluation results
        """
        results = []

        for i in range(0, len(agents), batch_size):
            batch = agents[i:i + batch_size]
            logger.info(f"Evaluating batch {i//batch_size + 1}: {len(batch)} agents")

            # Parallel evaluation within batch
            batch_results = await asyncio.gather(
                *[
                    self._evaluate_single_agent(agent)
                    for agent in batch
                ],
                return_exceptions=True
            )

            for agent, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.warning(
                        f"Failed to evaluate agent {agent['user_id']}: {result}"
                    )
                    continue

                results.append(result)

        return results

    async def _evaluate_single_agent(
        self,
        agent: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate polarization for a single agent

        Args:
            agent: Agent metadata dictionary

        Returns:
            Dictionary with polarization assessment
        """
        # Get agent's first and last posts (by post_id, not timestamp)
        initial_opinion = await self._get_agent_opinion_by_post_id(
            agent['user_id'],
            agent['first_post_id']
        )

        current_opinion = await self._get_agent_opinion_by_post_id(
            agent['user_id'],
            agent['last_post_id']
        )

        # LLM evaluation
        evaluation = await self.llm_evaluator.evaluate_polarization(
            initial_opinion=initial_opinion,
            current_opinion=current_opinion,
            context="social media discussion"
        )

        return {
            'agent_id': agent['user_id'],
            'agent_name': agent['user_name'],
            'direction': evaluation['direction'],
            'magnitude': evaluation['magnitude'],
            'reasoning': evaluation.get('reasoning', '')
        }

    async def _get_agent_opinion_by_post_id(
        self,
        agent_id: int,
        reference_post_id: int,
        window_size: int = 2
    ) -> str:
        """
        Extract agent's opinion from posts around a reference post_id

        Args:
            agent_id: Agent user ID
            reference_post_id: Reference post ID to use as anchor
            window_size: Number of posts before/after to include

        Returns:
            Concatenated post content as opinion string
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get posts within a window around the reference post_id
            cursor.execute("""
                SELECT content
                FROM post
                WHERE user_id = ?
                AND post_id BETWEEN ? AND ?
                ORDER BY post_id
                LIMIT 5
            """, (agent_id, reference_post_id - window_size, reference_post_id + window_size))

            posts = [row['content'] for row in cursor.fetchall()]
            return ' '.join(posts) if posts else "No posts available"

    def _calculate_average_direction(
        self,
        agent_polarization: List[Dict[str, Any]]
    ) -> PolarizationDirection:
        """
        Calculate average polarization direction

        Args:
            agent_polarization: List of agent polarization results

        Returns:
            Most common polarization direction
        """
        if not agent_polarization:
            return PolarizationDirection.NEUTRAL

        # Count directions
        direction_counts = {d.value: 0 for d in PolarizationDirection}

        for agent in agent_polarization:
            direction_counts[agent['direction']] += 1

        # Return most common direction
        most_common = max(direction_counts.keys(), key=lambda k: direction_counts[k])

        try:
            return PolarizationDirection(most_common)
        except ValueError:
            logger.warning(f"Invalid direction: {most_common}, defaulting to NEUTRAL")
            return PolarizationDirection.NEUTRAL
