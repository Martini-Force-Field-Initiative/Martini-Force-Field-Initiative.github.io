"""The unit of validator output.

Every check produces `Finding` objects. Nothing prints directly: renderers in
`report.py` decide how a finding appears (console, GitHub annotation, JSON).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class Severity(enum.IntEnum):
    """Ordered so `max()` picks the worst severity seen."""

    NOTICE = 0
    WARNING = 1
    ERROR = 2

    @classmethod
    def parse(cls, text: str) -> "Severity":
        try:
            return cls[str(text).strip().upper()]
        except KeyError:
            raise ValueError(
                f"unknown severity {text!r} (expected notice, warning or error)"
            ) from None

    @property
    def label(self) -> str:
        return self.name.lower()


@dataclass(frozen=True)
class Finding:
    """One problem, anchored to a file and (where known) a line.

    `rule` is a stable dotted identifier such as ``announcement.date-format``.
    It is the key contributors search for and the key the baseline file
    records, so renaming one is a breaking change.

    `hint` is not decoration. Contributors are domain scientists, not web
    developers; every ERROR should tell them what to type.
    """

    rule: str
    severity: Severity
    path: str
    message: str
    line: int | None = None
    hint: str | None = None

    @property
    def key(self) -> str:
        """Identity used by the baseline file."""
        return f"{self.rule}::{self.path}"

    def location(self) -> str:
        return f"{self.path}:{self.line}" if self.line else self.path

    def sort_key(self) -> tuple:
        return (-int(self.severity), self.path, self.line or 0, self.rule)


def error(rule: str, path: str, message: str, line: int | None = None,
          hint: str | None = None) -> Finding:
    return Finding(rule, Severity.ERROR, path, message, line, hint)


def warning(rule: str, path: str, message: str, line: int | None = None,
            hint: str | None = None) -> Finding:
    return Finding(rule, Severity.WARNING, path, message, line, hint)


def notice(rule: str, path: str, message: str, line: int | None = None,
           hint: str | None = None) -> Finding:
    return Finding(rule, Severity.NOTICE, path, message, line, hint)
