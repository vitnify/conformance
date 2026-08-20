"""Runner: `python -m conformance` — reports whether the installed implementation
reproduces the reference vectors and rejects the forgeries.

Exit 0 iff every receipt case has the expected verdict AND no engine vector is wrong
(engine vectors may be SKIPPED when the engine binary/model are absent — see engine.py).
"""
from __future__ import annotations
import argparse
import sys

from conformance import receipt, engine

GREEN, RED, YELLOW, DIM, OFF = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def _impl_banner():
    try:
        import vitnify
    except Exception as e:
        print(f"{RED}cannot import an implementation to test (`pip install vitnify`): {e}{OFF}")
        sys.exit(2)
    v = getattr(vitnify, "__version__", None)
    if not v:
        try:
            from importlib.metadata import version
            v = version("vitnify")
        except Exception:
            v = "?"
    return f"implementation under test: vitnify {v}"


def main() -> int:
    ap = argparse.ArgumentParser(prog="python -m conformance", description=__doc__)
    ap.add_argument("--adapter", default="vitnify-py",
                    help="verifier adapter for the receipt tier (default: vitnify-py)")
    opts = ap.parse_args()

    print(f"{DIM}vitnify conformance kit — {_impl_banner()}  ·  adapter: {opts.adapter}{OFF}\n")

    # -- receipt-verifier conformance (must-reject + must-accept) --
    print("RECEIPT CONFORMANCE  (forgeries rejected, valid receipts accepted)")
    r_results, r_ok = receipt.run(opts.adapter)
    for cid, desc, exp_ok, got, passed in r_results:
        mark = f"{GREEN}PASS{OFF}" if passed else f"{RED}FAIL{OFF}"
        verdict = "reject" if exp_ok is False else "accept"
        print(f"  [{mark}] {cid}  must {verdict:<6}  {desc}")
        if not passed:
            print(f"          {RED}expected ok={exp_ok}, verifier returned ok={got}{OFF}")
    n_pass = sum(1 for r in r_results if r[4])
    print(f"  → {n_pass}/{len(r_results)} receipt cases as specified\n")

    # -- engine-determinism conformance (reference digests) --
    print("ENGINE CONFORMANCE  (reference model-computation digests reproduced bit-for-bit)")
    e_results, e_ok = engine.run()
    for vid, expect, got, passed in e_results:
        if passed is None:
            print(f"  [{YELLOW}SKIP{OFF}] {vid}\n          {DIM}{got}{OFF}")
        else:
            mark = f"{GREEN}PASS{OFF}" if passed else f"{RED}FAIL{OFF}"
            print(f"  [{mark}] {vid}")
            if not passed:
                print(f"          {RED}expected {expect}\n          got      {got}{OFF}")
    n_repro = sum(1 for r in e_results if r[3] is True)
    n_skip = sum(1 for r in e_results if r[3] is None)
    print(f"  → {n_repro} reproduced, {n_skip} skipped of {len(e_results)} vectors\n")

    ok = r_ok and e_ok
    print(f"{'='*60}")
    if ok:
        print(f"{GREEN}CONFORMANT{OFF} — implementation matches the vitnify-receipt corpus.")
    else:
        print(f"{RED}NON-CONFORMANT{OFF} — see failures above.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
