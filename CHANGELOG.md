# Changelog

## 0.2.0 — 2026-08-20

Made receipt conformance implementation-independent.

- **Static receipt vectors** — the 16 receipt cases are now frozen as language-agnostic
  JSON in `vectors/receipts/` (wire bytes + expected verdict), with a schema doc. A
  verifier in any language can be tested against the same bytes; conformance no longer
  runs receipts through the Python API in process.
- **Adapters** — the runner feeds each vector to a pluggable adapter
  (`conformance/adapters/`, default `vitnify-py`); `python -m conformance --adapter <name>`
  selects one. Bring-your-own-verifier is the extension point.
- **Generator** — `tools/gen_receipt_vectors.py` builds the vectors from the reference
  implementation; the committed JSON, not the generator, is the corpus.

## 0.1.0 — 2026-08-20

Initial conformance kit.

- **Receipt conformance** — 16 cases against an installed implementation's verifier:
  12 forgery classes it must reject (R01–R12) and 4 valid receipts it must accept
  (A01–A04, including v1 back-compat, observe-only flagging, and hosted integrity-only).
- **Engine conformance** — reference model-computation digests in `vectors/engine.json`,
  seeded with the conformance anchor `9c0754…f3b0f` (TinyLlama-1.1B-Chat Q4_K_M). The
  reproducer runs when `VITNI_RECEIPT_BIN` + `VITNI_MODEL_DIR` are set, and skips
  (without failing) otherwise.
- **Runner** — `python -m conformance` reports both tiers and exits non-zero on any
  wrong verdict.
- **CI** — runs the kit against the published `vitnify` on every push and weekly, so a
  release drifting out of conformance fails a build.
