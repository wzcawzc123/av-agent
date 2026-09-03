import pytest
from app.orchestrator.state_machine import ConversationState, InvalidTransition


def test_valid_flow():
    s = ConversationState("IDLE")
    s.transition("COLLECTING")
    s.transition("CONFIRMING")
    s.transition("GENERATING")
    s.transition("DELIVERED")
    assert s.status == "DELIVERED"


def test_invalid_transition_raises():
    s = ConversationState("IDLE")
    with pytest.raises(InvalidTransition):
        s.transition("GENERATING")


def test_collecting_loopback():
    s = ConversationState("COLLECTING")
    s.transition("COLLECTING")  # 追问后仍处采集
    assert s.status == "COLLECTING"
