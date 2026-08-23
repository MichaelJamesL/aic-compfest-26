"""The MaintenanceEngine facade - the only surface the backend touches.

Orchestration only: signals -> context -> model. The heavy lifting of
structured-output validation and retry is owned by pydantic_ai's Agent, not
hand-rolled here.
"""
from __future__ import annotations

from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.deepseek import DeepSeekProvider
from pydantic_ai.settings import ModelSettings

from . import config, context, prompts
from .schemas import AnalysisRequest, AnalysisResult, TechnicianResult, VerificationResult, WorkOrder

_MODEL_SETTINGS = ModelSettings(
    max_tokens=config.MAX_OUTPUT_TOKENS,
    temperature=0.2,
    timeout=config.CLIENT_TIMEOUT_S,
)


def _build_model() -> Model:
    return OpenAIChatModel(
        config.MODEL,
        provider=DeepSeekProvider(api_key=config.DEEPSEEK_API_KEY),
    )


class MaintenanceEngine:
    def __init__(
        self,
        model: Model | str | None = None,
        budget_tokens: int | None = None,
    ) -> None:
        self.model = model or _build_model()
        self.budget_tokens = budget_tokens or config.CONTEXT_BUDGET_TOKENS

        # Two agents share the model: a typed one for `analyze`, a plain one
        # for Starter Q&A. retries=1 is pydantic_ai's built-in re-prompt on
        # validation failure (the PLAN's "retry is not optional").
        self._analysis_agent = Agent(
            self.model,
            name="maintenance_analysis",
            system_prompt=prompts.SYSTEM,
            output_type=AnalysisResult,
            retries=1,
            model_settings=_MODEL_SETTINGS,
        )
        self._ask_agent = Agent(
            self.model,
            name="maintenance_ask",
            system_prompt=prompts.SYSTEM,
            retries=1,
            model_settings=_MODEL_SETTINGS,
        )
        self._verification_agent = Agent(
            self.model,
            name="maintenance_verification",
            system_prompt=(
                "Verify whether the technician's evidence resolves the work order. "
                "Return resolved only when the requested work is complete and the evidence supports it. "
                "Use partial when some work remains and not_resolved when the fault remains."
            ),
            output_type=VerificationResult,
            retries=1,
            model_settings=_MODEL_SETTINGS,
        )
        # Last run's usage, so callers (e.g. the demo) can read cache metrics.
        self.last_usage: Any | None = None

    def analyze(self, request: AnalysisRequest) -> AnalysisResult:
        bundle = context.select_context(request, self.budget_tokens)
        user_turn = prompts.build_user_turn(bundle, request.tier)
        run = self._analysis_agent.run_sync(user_turn)
        result = run.output
        self.last_usage = run.usage

        # The model never gets to set the defensible numbers or the audit trail.
        result.health_score = bundle.health_score
        result.anomalies = bundle.anomalies
        result.defects = bundle.defects
        result.sources = bundle.source_names
        result.tier = request.tier
        result.model = config.MODEL
        return result

    def ask(self, request: AnalysisRequest, question: str) -> str:
        """Starter-tier Q&A: plain text answer grounded in the retrieved corpus."""
        bundle = context.select_context(request, self.budget_tokens)
        user_turn = prompts.build_ask_turn(bundle, question)
        run = self._ask_agent.run_sync(user_turn)
        self.last_usage = run.usage
        return run.output

    def verify(self, work_order: WorkOrder, technician_result: TechnicianResult) -> VerificationResult:
        """Make exactly one synchronous, typed verification call."""
        prompt = (
            f"Work order:\n{work_order.model_dump_json()}\n\n"
            f"Technician result:\n{technician_result.model_dump_json()}"
        )
        run = self._verification_agent.run_sync(prompt)
        self.last_usage = run.usage
        return run.output
