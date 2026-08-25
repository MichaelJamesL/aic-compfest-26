"""Environment configuration for the src package.

All secrets and tunables live behind env vars with sane defaults, so the
package runs out of the box for tests and demos while still being configurable
in production.
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

# Load DEEPSEEK_API_KEY (and other vars) from ai-engine/.env if present.
load_dotenv()

# --- DeepSeek API -----------------------------------------------------------
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# The single place the model id lives. Escalating the hardest call to
# deepseek-reasoner is a one-line change here (see PLAN.md).
MODEL: str = os.getenv("AIENGINE_MODEL", "deepseek-chat")
REASONER_MODEL: str = os.getenv("AIENGINE_REASONER_MODEL", "deepseek-reasoner")

# --- Knowledge base ---------------------------------------------------------
# Deliberately NOT `DATABASE_URL`: the backend imports this package into its own
# process and uses that name for the application database (SQLite by default).
# Sharing the name pointed one of them at the wrong store. `DATABASE_URL` is
# still honoured as a fallback so the package works standalone.
DATABASE_URL: str = os.getenv(
    "AIENGINE_DATABASE_URL",
    os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/aic26"),
)

# --- Budgets ----------------------------------------------------------------
# Token budget for the prompt corpus, leaving room for output + margin inside
# the ~64K window. Counted with tiktoken as an estimate (DeepSeek's tokenizer
# differs), so keep the margin generous.
CONTEXT_BUDGET_TOKENS: int = int(os.getenv("AIENGINE_CONTEXT_BUDGET", "40_000"))
# Max output tokens for the JSON analysis call.
MAX_OUTPUT_TOKENS: int = int(os.getenv("AIENGINE_MAX_OUTPUT", "4000"))
# Client timeout for a single non-streaming completion.
CLIENT_TIMEOUT_S: float = float(os.getenv("AIENGINE_TIMEOUT", "120"))

# How many filled-in readings are required before a tag is scored.
MIN_POINTS_PER_TAG: int = 8

# --- Vision / PatchCore -----------------------------------------------------
BANK_DIR: str = os.getenv("AIENGINE_BANK_DIR", "ai-engine/.banks")
DEFECT_THRESHOLD: float | None = (
    float(v) if (v := os.getenv("AIENGINE_DEFECT_THRESHOLD")) else None
)
PATCHCORE_BACKBONE: str = os.getenv("AIENGINE_PATCHCORE_BACKBONE", "wide_resnet50_2")

# --- Sensor baselines -------------------------------------------------------
# One IsolationForest per tag per machine, fitted from historical readings.
BASELINE_DIR: str = os.getenv("AIENGINE_BASELINE_DIR", os.path.join(BANK_DIR, "baselines"))