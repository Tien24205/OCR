import pytest
from app.services.agent_orchestrator import AgenticOrchestrator, Action

def test_orchestrator_success():
    orchestrator = AgenticOrchestrator()
    def task():
        return "success"
    
    result = orchestrator.execute_with_retry("test_agent", task)
    assert result == "success"
    
    decisions = orchestrator.get_decisions_log()
    assert len(decisions) == 1
    assert decisions[0]["agent"] == "test_agent"
    assert decisions[0]["action"] == Action.PROCEED.value

def test_orchestrator_retry_then_success():
    orchestrator = AgenticOrchestrator()
    attempts = 0
    def task():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ValueError("First attempt failed")
        return "success_on_second"
    
    result = orchestrator.execute_with_retry("test_agent", task, max_retries=1)
    assert result == "success_on_second"
    
    decisions = orchestrator.get_decisions_log()
    assert len(decisions) == 2
    assert decisions[0]["action"] == Action.RETRY.value
    assert decisions[1]["action"] == Action.PROCEED.value

def test_orchestrator_escalate_after_max_retries():
    orchestrator = AgenticOrchestrator()
    def task():
        raise ValueError("Always fails")
    
    with pytest.raises(ValueError):
        orchestrator.execute_with_retry("test_agent", task, max_retries=2)
    
    decisions = orchestrator.get_decisions_log()
    assert len(decisions) == 3
    assert decisions[0]["action"] == Action.RETRY.value
    assert decisions[1]["action"] == Action.RETRY.value
    assert decisions[2]["action"] == Action.ESCALATE.value
