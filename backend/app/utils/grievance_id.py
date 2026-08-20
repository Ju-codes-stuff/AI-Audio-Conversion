"""
Grievance ID generator.

Format: GRV-YYYY-NNNNNN
  GRV     → platform prefix
  YYYY    → 4-digit year
  NNNNNN  → zero-padded 6-digit sequential counter (per year)

The counter is derived from the database sequence, ensuring global uniqueness
even with multiple API workers running concurrently.
"""
from __future__ import annotations

from datetime import datetime, timezone


def format_grievance_id(year: int, sequence: int) -> str:
    """
    Build a human-readable grievance ID.

    Args:
        year:     Calendar year (e.g. 2026).
        sequence: Sequential integer for this year (1-based).

    Returns:
        Formatted ID such as ``GRV-2026-000142``.
    """
    return f"GRV-{year}-{sequence:06d}"


def current_year() -> int:
    return datetime.now(timezone.utc).year


def parse_grievance_id(grv_id: str) -> tuple[int, int]:
    """
    Parse a grievance ID string back into (year, sequence).

    Raises:
        ValueError: If the format is invalid.
    """
    parts = grv_id.split("-")
    if len(parts) != 3 or parts[0] != "GRV":
        raise ValueError(f"Invalid grievance ID format: {grv_id!r}")
    try:
        return int(parts[1]), int(parts[2])
    except ValueError:
        raise ValueError(f"Invalid grievance ID format: {grv_id!r}")
