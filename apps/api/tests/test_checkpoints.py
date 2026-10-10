"""P07.S1.T3 (CHECKPOINTS-01): formative checkpoint blocks inside a lesson. A question checkpoint has 2 to 6 options,
one key among them and an explanation; a self-check has a prompt and what to look for, and no key. Checkpoints are
formative only: nothing is stored or scored and they never feed learning evidence. Fixture text only."""

from __future__ import annotations

from typing import Any

import pytest

from portal_api.modules.content import blocks

PARA = {"type": "paragraph", "text": "Fixture explanation."}


def _q(**over: Any) -> dict[str, Any]:
    return {
        "type": "checkpoint",
        "mode": "question",
        "prompt": "Fixture prompt?",
        "options": [{"id": "a", "text": "First"}, {"id": "b", "text": "Second"}],
        "answer_id": "a",
        "explanation": "Fixture reason.",
        **over,
    }


def test_valid_checkpoints_publish_on_every_supported_client() -> None:
    self_check = {
        "type": "checkpoint",
        "mode": "self_check",
        "prompt": "Explain it aloud.",
        "explanation": "Look for X.",
    }
    v = blocks.validate_body({"blocks": [PARA, _q(), self_check]}, for_publication=True)
    assert v.ok, v.errors
    assert "checkpoint" in v.block_types and v.warnings == []


@pytest.mark.parametrize(
    "bad",
    [
        _q(answer_id="z"),  # key not among the options
        _q(answer_id=None),  # a question needs a key
        _q(options=[{"id": "a", "text": "Only"}]),  # at least two options
        _q(options=[{"id": "a", "text": "One"}, {"id": "a", "text": "Two"}]),  # unique option ids
        {"type": "checkpoint", "mode": "self_check", "prompt": "P", "explanation": "E", "answer_id": "a"},
        _q(explanation=""),  # the reason is always shown after answering
    ],
)
def test_invalid_checkpoints_are_rejected(bad: dict[str, Any]) -> None:
    assert not blocks.validate_body({"blocks": [PARA, bad]}, for_publication=True).ok
