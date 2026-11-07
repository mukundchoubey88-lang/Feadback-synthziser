"""Database custom types.

Provides portable types such as PortableVector, which seamlessly compiles to
pgvector.sqlalchemy.Vector on PostgreSQL and sa.JSON on SQLite and other dialects.
"""

import math
from typing import Any, List, Optional
import sqlalchemy as sa
from sqlalchemy.types import TypeDecorator

try:
    from pgvector.sqlalchemy import Vector as PGVector
except ImportError:
    PGVector = None


class PortableVector(TypeDecorator):
    """Renders pgvector.sqlalchemy.Vector on PostgreSQL and sa.JSON on SQLite."""

    impl = sa.JSON
    cache_ok = True

    def __init__(self, dim: int = 768, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect: sa.engine.Dialect) -> Any:
        if dialect.name == "postgresql" and PGVector is not None:
            return dialect.type_descriptor(PGVector(self.dim))
        return dialect.type_descriptor(sa.JSON())

    def process_bind_param(self, value: Any, dialect: sa.engine.Dialect) -> Any:
        if value is None:
            return None
        if hasattr(value, "tolist"):
            value = value.tolist()
        if not isinstance(value, (list, tuple)):
            raise ValueError(f"PortableVector expects a list of floats, got {type(value).__name__}")
        if len(value) != self.dim:
            raise ValueError(f"PortableVector expects {self.dim} dimensions, got {len(value)}")

        floats: List[float] = []
        for idx, x in enumerate(value):
            try:
                fx = float(x)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Vector value at index {idx} cannot be converted to float: {x}") from e
            if not math.isfinite(fx):
                raise ValueError(f"Vector contains non-finite value ({fx}) at index {idx}")
            floats.append(fx)
        return floats

    def process_result_value(self, value: Any, dialect: sa.engine.Dialect) -> Optional[List[float]]:
        if value is None:
            return None
        if hasattr(value, "tolist"):
            return [float(x) for x in value.tolist()]
        if isinstance(value, (list, tuple)):
            return [float(x) for x in value]
        return list(value)
