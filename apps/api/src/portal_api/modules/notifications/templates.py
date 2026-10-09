"""Notification events and templates (P15.S1.T1).

Every event has one template: its category, the channels it may use, whether it is urgent (ignores quiet hours and
the hourly cap: something the learner must act on), the parameters it needs and its text. Categories keep service
notices apart from optional content (roadmap: "separate service notices from optional promotional content"):

* ``service``: about the learner's own account, work or money. Always in the inbox; email/push follow preferences.
* ``reminder``: study reminders the learner can switch off.
* ``promotional``: optional news; nothing is sent unless the learner opted in.

Texts are short and factual. They never contain marks, answer keys, tokens or personal data beyond what the link
opens for the signed-in learner. Events whose source feature doesn't exist yet (payments, mocks, revision plans) are
defined here so their emitters plug in without a schema change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Category = Literal["service", "reminder", "promotional"]
Channel = Literal["email", "push"]


@dataclass(frozen=True)
class Template:
    category: Category
    channels: tuple[Channel, ...]
    urgent: bool
    params: tuple[str, ...]
    title: str
    body: str


TEMPLATES: dict[str, Template] = {
    # Account and money
    "account.verification": Template(
        "service", ("email",), True, ("code",), "Your verification code", "Your Punjab Learning Portal code is {code}."
    ),
    "payment.receipt": Template(
        "service", ("email",), False, ("plan", "amount"), "Payment received", "Thank you. {plan} is active ({amount})."
    ),
    "trial.ending": Template(
        "service",
        ("email", "push"),
        False,
        ("ends",),
        "Your free trial ends soon",
        "Your free trial ends on {ends}. Your saved work and results stay in your account.",
    ),
    # Written practice and results
    "written.result_released": Template(
        "service",
        ("email", "push"),
        False,
        ("summary",),
        "Your written test has been marked",
        "{summary} Open the test to see your marks and the teacher's reasons.",
    ),
    "written.action_required": Template(
        "service",
        ("email", "push"),
        True,
        ("question", "deadline"),
        "Action needed on your written test",
        "A teacher needs your help with question {question}. Please act by {deadline}, or the question is left "
        "unmarked and its allowance returned.",
    ),
    "score.revised": Template(
        "service",
        ("email", "push"),
        False,
        ("reason",),
        "A result of yours was updated",
        "{reason} Your earlier marks stay in your result history.",
    ),
    # Help
    "support.reply": Template(
        "service",
        ("email", "push"),
        False,
        ("subject",),
        "Reply to your help request",
        "Support replied to “{subject}”.",
    ),
    "support.resolved": Template(
        "service",
        ("email", "push"),
        False,
        ("subject",),
        "Your help request was resolved",
        "Your help request \u201c{subject}\u201d was resolved. Reply if you still need help.",
    ),
    # Schedule-driven (emitters land with their features)
    "mock.reminder": Template(
        "reminder", ("email", "push"), False, ("mock", "starts"), "Mock test reminder", "{mock} starts at {starts}."
    ),
    "revision.reminder": Template(
        "reminder", ("push",), False, ("topic",), "Time to revise", "You planned to revise {topic} today."
    ),
    "app.update_required": Template(
        "service",
        ("push",),
        True,
        ("version",),
        "Update the app",
        "This version can no longer open some content. Update to version {version} or later.",
    ),
    "content.available": Template(
        "promotional",
        ("email", "push"),
        False,
        ("what",),
        "New in your subjects",
        "{what} is now available.",
    ),
}


def render(event: str, params: dict[str, str]) -> tuple[Template, str, str]:
    t = TEMPLATES.get(event)
    if t is None:
        raise KeyError(f"unknown notification event {event!r}")
    missing = [p for p in t.params if p not in params]
    if missing:
        raise ValueError(f"notification {event!r} is missing parameters {missing}")
    values = {k: str(v)[:300] for k, v in params.items()}
    return t, t.title.format(**values), t.body.format(**values)
