# vitnify/conformance

**The executable definition of a conformant vitnify receipt.** Point it at an
implementation; it tells you whether that implementation reproduces the reference
vectors and rejects the forgeries.

A vitnify receipt makes two claims: *this computation happened* (a deterministic
model-computation digest) and *this run was contained and unaltered* (a signed,
capability-checked event log). An implementation is **conformant** only if it does
both the way this kit specifies — so a receipt one tool issues means the same thing
to a tool built by someone else. This repo is that specification, in runnable form.

```
pip install vitnify
python -m conformance
```

```
RECEIPT CONFORMANCE  (forgeries rejected, valid receipts accepted)
  [PASS] R01  must reject  reject: unsigned receipt
  ...
  [PASS] A04  must accept  accept: hosted integrity-only
  → 16/16 receipt cases as specified

ENGINE CONFORMANCE  (reference model-computation digests reproduced bit-for-bit)
  [SKIP] tinyllama-1.1b-chat-q4km-once-upon-a-time-20
  → 0 reproduced, 1 skipped of 1 vectors

CONFORMANT — implementation matches the vitnify-receipt corpus.
```

Exit code is `0` iff every receipt case gets the specified verdict and no engine
vector is reproduced *wrong*. A skipped engine vector (binary/model absent) is
unproven, not failed.

## Two tiers, mirroring the receipt

### Receipt conformance — [`conformance/receipt.py`](conformance/receipt.py)
Fully runnable, pure Python. Two sets of cases a conformant *verifier* must handle:

- **Reject (R01–R12)** — the forgery classes. Unsigned or keyless-HMAC receipts, an
  ungranted tool, an edited / deleted / reordered event, an edited model digest, a
  tampered chain pointer, a backdated timestamp, a decision-string or relabelled-kind
  evasion, and an attacker re-sign against a pinned key. Each must come back `ok=false`.
- **Accept (A01–A04)** — the receipts a verifier must *not* wrongly reject: an honest
  enforced receipt, a valid older-format (v1) receipt, an observe-only receipt (accepted
  but flagged `containment_enforced=false`), and a hosted integrity-only receipt.

This is the negative *and* positive space of "what a verifier does" — a forgery filter
that also rejects honest receipts is not conformant.

### Engine conformance — [`conformance/engine.py`](conformance/engine.py) · [`vectors/engine.json`](vectors/engine.json)
The reference model-computation digests. A conformant engine must reproduce each
`model_digest` **bit-for-bit on any CPU vendor or instruction set** — that
cross-hardware determinism is the whole tier-1 claim. Reproduction needs the engine
binary and weights, so it is opt-in:

```
VITNI_RECEIPT_BIN=/path/to/vitni-receipt \
VITNI_MODEL_DIR=/path/to/gguf/models \
python -m conformance
```

The seed vector is the conformance anchor
`9c0754458633e863e0fb5bb2bd00df0d8b813934687b9a4097a1a9a4179f3b0f` —
TinyLlama-1.1B-Chat Q4_K_M, prompt `"Once upon a time,"`, 20 new tokens. Without the
binary and model set, the vector is reported `SKIPPED`; it still defines the target
every engine is measured against.

## Adding to the corpus

- **A new forgery class** — add a builder and a `("Rnn", …)` row to `CASES` in
  [`conformance/receipt.py`](conformance/receipt.py). A receipt that survives it today
  is a finding; a receipt that survives it after is a regression.
- **A new determinism vector** — add an entry to [`vectors/engine.json`](vectors/engine.json)
  with the model, prompt tokens, `n_new`, and the reproduced `model_digest`.

Reference receipts are currently constructed via the reference implementation's helpers,
which tests the Python verifier. Freezing them as static JSON receipt vectors — so a
verifier in any language can be tested against the same bytes — is the next step, and
the reason the runner is structured around data, not a fixed API.

## Specification

The normative format is the [vitnify-receipt spec](https://github.com/vitnify/vitnify-receipt-spec).
This kit is the spec's conformance suite: when the spec and this kit disagree, that is a
bug in one of them — open an issue.

## License

Apache-2.0. The reference vectors and probe definitions are meant to be copied,
re-run, and extended.
