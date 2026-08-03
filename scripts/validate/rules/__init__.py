"""Registry of relational rules.

The declarative schemas handle everything expressible as "this field must look
like that". Rules registered here handle checks that must look outside a
single field: at the file's directory, at its siblings, at another file's
contents, or at a downstream consumer's parser.

A schema naming a rule that is not registered is a fatal error, never a silent
skip -- a check that quietly does nothing is worse than no check at all when
the framework is being cited as evidence of validation.
"""

from __future__ import annotations

from collections.abc import Callable

RULE_REGISTRY: dict[str, Callable] = {}


def rule(name: str):
    """Decorator registering a relational rule under a stable name."""

    def decorate(func):
        if name in RULE_REGISTRY:
            raise RuntimeError(f"duplicate rule registration: {name}")
        RULE_REGISTRY[name] = func
        return func

    return decorate


def get(name: str) -> Callable:
    try:
        return RULE_REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"unknown rule {name!r}; registered rules are {sorted(RULE_REGISTRY)}"
        ) from None


def load_all() -> None:
    """Import the rule modules so their decorators run."""
    from . import announcements, publications
