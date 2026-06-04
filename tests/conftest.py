"""Shared pytest setup for the CeliacMap agent tests.

Ensures the repository root is importable so ``agents`` / ``config`` / ``scripts``
resolve regardless of where pytest is launched from. All external services
(Supabase, Google Places, Anthropic) are mocked in the tests themselves, so the
suite runs fully offline and needs no ``.env``.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
