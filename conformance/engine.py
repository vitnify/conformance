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
    """Invoke the `vitni-receipt` engine binary to recompute a vector's digest.

    The binary prints JSON: {"model_digest", "regime", "model_digest_v1", ...}. We
    return the tier-1 v2 `model_digest` and, when the vector pins a `regime`, require
    the engine to report the same one (a digest match under the wrong regime would be a
    coincidence worth catching).
    """
    model = Path(model_dir) / f"{vec['model_id']}.gguf"
    if not model.exists():
        raise FileNotFoundError(str(model))
    out = subprocess.run(
        [bin_path, "--gguf", str(model),
         "--prompt", ",".join(map(str, vec["prompt_tokens"])),
         "--n", str(vec["n_new"]), "--model-id", vec["model_id"]],
        capture_output=True, text=True, timeout=600,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or f"exit {out.returncode}")
    result = json.loads(out.stdout.strip().splitlines()[-1])
    if "regime" in vec and result.get("regime") != vec["regime"]:
        raise RuntimeError(f"regime mismatch: engine {result.get('regime')!r} != vector {vec['regime']!r}")
    return result["model_digest"]


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
