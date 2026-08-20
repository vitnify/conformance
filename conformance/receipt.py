"""Receipt-verifier conformance — what a conformant vitnify verifier MUST do.

Reads the static vectors in `vectors/receipts/` (frozen wire bytes, not built in
process) and runs each through a verifier adapter, checking the verdict matches the
vector's declared expectation:

- reject (R*): a forged or tampered receipt — the verifier must return `ok=false`.
- accept (A*): a valid receipt — `ok=true`, with any asserted flags (e.g. an
  observe-only receipt is accepted but flagged `containment_enforced=false`).

The vectors are language-agnostic JSON; the adapter is the only implementation-specific
part. See `conformance/adapters/` and `vectors/receipts/README.md`.
"""
from __future__ import annotations
import json
from pathlib import Path

from conformance.adapters import get_adapter

VECTORS = Path(__file__).resolve().parent.parent / "vectors" / "receipts"


def load():
    index = json.loads((VECTORS / "index.json").read_text())
    return [(e, json.loads((VECTORS / e["file"]).read_text())) for e in index]


def run(adapter_name: str = "vitnify-py"):
    """Run every receipt vector through the adapter; return (results, all_passed)."""
    verify = get_adapter(adapter_name)
    results = []
    for entry, vector in load():
        expect = vector["expect"]
        try:
            checks = verify(vector)
            got = checks.get("ok")
            passed = (got is expect["ok"])
            for k, v in expect.get("flags", {}).items():
                passed = passed and (checks.get(k) is v)
        except Exception as e:
            got, passed = f"raised {type(e).__name__}", False
        results.append((vector["id"], vector["description"], expect["ok"], got, passed))
    return results, all(r[4] for r in results)
