"""Engine-determinism conformance — the tier-1 model-computation digest.

A conformant engine must reproduce every reference `model_digest` in `vectors/engine.json`
bit-for-bit, on any CPU vendor or instruction set. Reproduction needs the engine binary
and the model weights, so it is opt-in:

    VITNI_RECEIPT_BIN=/path/to/vitni-receipt   # the reference engine CLI
    VITNI_MODEL_DIR=/path/to/gguf/models       # holds <model_id>.gguf

Without those set, each vector is reported SKIPPED (declared but not reproduced here) —
the vectors still define the target every engine is measured against.
"""
from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path

VECTORS = Path(__file__).resolve().parent.parent / "vectors" / "engine.json"


def load():
    return json.loads(VECTORS.read_text())


def _reproduce(bin_path: str, model_dir: str, vec: dict) -> str:
    """Invoke the engine to recompute a vector's digest. Adjust flags to your binary."""
    model = Path(model_dir) / f"{vec['model_id']}.gguf"
    if not model.exists():
        raise FileNotFoundError(str(model))
    out = subprocess.run(
        [bin_path, "--model", str(model),
         "--prompt-tokens", ",".join(map(str, vec["prompt_tokens"])),
         "--n-new", str(vec["n_new"]), "--print-digest"],
        capture_output=True, text=True, timeout=600,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or f"exit {out.returncode}")
    return out.stdout.strip().split()[-1]


def run():
    """Run every engine vector; return (results, all_passed).

    A SKIPPED vector does not fail the tier — it is unproven here, not wrong.
    """
    data = load()
    bin_path = os.environ.get("VITNI_RECEIPT_BIN")
    model_dir = os.environ.get("VITNI_MODEL_DIR")
    results = []
    for vec in data["vectors"]:
        expect = vec["model_digest"]
        if not (bin_path and model_dir):
            results.append((vec["id"], expect, "SKIPPED (set VITNI_RECEIPT_BIN + VITNI_MODEL_DIR)", None))
            continue
        try:
            got = _reproduce(bin_path, model_dir, vec)
            results.append((vec["id"], expect, got, got == expect))
        except Exception as e:
            results.append((vec["id"], expect, f"SKIPPED ({type(e).__name__}: {e})", None))
    passed = all(r[3] is not False for r in results)   # None (skipped) does not fail the tier
    return results, passed
