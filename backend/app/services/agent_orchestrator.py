"""Agentic AI Orchestrator: Multi-step reasoning and self-correction."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Any

from app.models import utcnow

logger = logging.getLogger(__name__)


class Action(str, Enum):
    PROCEED = "proceed"
    RETRY = "retry"
    ESCALATE = "escalate"
    SKIP = "skip"


@dataclass
class AgentDecision:
    agent: str
    action: Action
    reason: str
    confidence: float
    metadata: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=utcnow)


class AgenticOrchestrator:
    def __init__(self):
        self.decisions: list[AgentDecision] = []

    def run(self, scan_id, config, session_factory):
        """Run bounded, result-dependent policies with persistent evidence."""
        from app.services.agent_runner import run
        run(self, scan_id, config, session_factory)
        return self.get_decisions_log()

    def record_decision(self, agent: str, action: Action, reason: str, confidence: float, **metadata) -> AgentDecision:
        decision = AgentDecision(
            agent=agent,
            action=action,
            reason=reason,
            confidence=confidence,
            metadata=metadata
        )
        self.decisions.append(decision)
        logger.info(f"Agent [{agent}] decided to {action.value}: {reason} (Confidence: {confidence:.2f})")
        return decision

    def execute_with_retry(self, agent_name: str, task: Callable[[], Any], max_retries: int = 2, retry_condition: Callable[[Exception], bool] | None = None) -> Any:
        """Executes a task and automatically retries if it fails, recording agent decisions."""
        for attempt in range(1, max_retries + 2):
            try:
                result = task()
                self.record_decision(
                    agent=agent_name,
                    action=Action.PROCEED,
                    reason=f"Task succeeded on attempt {attempt}",
                    confidence=1.0,
                    attempt=attempt
                )
                return result
            except Exception as exc:
                should_retry = attempt <= max_retries and (retry_condition is None or retry_condition(exc))
                if should_retry:
                    self.record_decision(
                        agent=agent_name,
                        action=Action.RETRY,
                        reason="Task failed. Retrying an eligible error.",
                        confidence=0.5,
                        attempt=attempt,
                        error_type=type(exc).__name__
                    )
                else:
                    self.record_decision(
                        agent=agent_name,
                        action=Action.ESCALATE,
                        reason=f"Task stopped after {attempt} attempts.",
                        confidence=0.0,
                        attempt=attempt,
                        error_type=type(exc).__name__
                    )
                    raise

    def get_decisions_log(self) -> list[dict]:
        return [
            {
                "agent": d.agent,
                "action": d.action.value,
                "reason": d.reason,
                "confidence": d.confidence,
                "metadata": d.metadata,
                "timestamp": d.timestamp
            }
            for d in self.decisions
        ]
