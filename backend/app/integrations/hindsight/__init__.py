"""Hindsight Persistent Memory integration (Part 9).

Cognitive memory layer alongside PostgreSQL as the structured source of truth.
Provides asynchronous client for retaining, recalling, and reflecting upon
historical customer feedback, themes, product changes, and synthesized insights.
"""

from app.integrations.hindsight.client import HindsightClient

__all__ = ["HindsightClient"]
