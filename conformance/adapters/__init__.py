"""Verifier adapters.

An adapter turns a frozen receipt vector into a verdict. Its one job:

    verify(vector: dict) -> dict          # a checks dict containing at least "ok"

`vector["certificate"]` and `vector["log"]` are the wire bytes; `vector["verify_kwargs"]`
carries any verifier options (e.g. `pinned_pubkeys`). The default adapter wraps the
Python `vitnify` verifier. To conformance-test an implementation in another language,
write an adapter (or a runner in that language) that reads the same JSON and returns
`{"ok": ...}` plus any flags the vectors assert.
"""
from __future__ import annotations

from . import vitnify_py

_ADAPTERS = {"vitnify-py": vitnify_py.verify}


def get_adapter(name: str = "vitnify-py"):
    try:
        return _ADAPTERS[name]
    except KeyError:
        raise SystemExit(f"unknown adapter {name!r}; available: {', '.join(_ADAPTERS)}")
