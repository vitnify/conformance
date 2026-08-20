"""Generate the static receipt vectors in `vectors/receipts/`.

Each case is built once via the reference implementation, then frozen to JSON — the
signed certificate and the event log as wire bytes, plus the expected verdict. The
frozen files ARE the corpus; a verifier in any language is tested against these exact
bytes (see vectors/receipts/README.md for the schema). Run:

    python tools/gen_receipt_vectors.py

Regenerating rotates the ed25519 keys, nonces, and timestamps baked into the vectors
(the bytes change; the verdicts do not) — so regenerate deliberately, then commit.
"""
from __future__ import annotations
import copy
import json
import re
from dataclasses import asdict
from pathlib import Path

from vitnify.events import EventLog, Kind
from vitnify.certificate import (
    ExecutionCertificate, issue_certificate, gen_ed25519, _canon, _digest32,
)
from vitnify._vendor.pck.cas import MerkleCAS

OUT = Path(__file__).resolve().parent.parent / "vectors" / "receipts"

# A fixed trusted signer for this generation (its public key is baked into the
# vectors it signs; the pinning case pins THIS key and is signed by another).
PRIV, PUB = gen_ed25519()


def _honest_log():
    log = EventLog()
    log.append_llm_call("ph", [1, 2, 3], seed=0, model_digest="dd")
    log.append(Kind.TOOL_CALL, {"tool": "read_docs", "decision": "ALLOW", "result": "r", "result_hash": "h"})
    return log


def _v1_signed(log, caps, *, issued_at=None):
    """A genuine v1 receipt: body reconstructed under the v1 domain, ed25519-signed."""
    cas = MerkleCAS(log.chunks())
    body = {"v": "vitnify-receipt v1", "program_hash": "p", "capabilities": caps,
            "event_root": cas.root, "n_events": len(log), "head_hash": log.head(),
            "model_digests": log.model_digests()}
    sig = PRIV.sign(bytes.fromhex(_digest32(_canon(body).encode()))).hex()
    cert = ExecutionCertificate("p", caps, cas.root, len(log), log.head(), model_digests=log.model_digests())
    cert.v, cert.sig, cert.sig_alg, cert.pubkey = "vitnify-receipt v1", sig, "ed25519", PUB
    if issued_at is not None:
        cert.issued_at = issued_at
    return cert


# ---- negative: the verifier MUST reject (expect ok=False) ------------------------

def _unsigned():
    log = EventLog(); log.append(Kind.TOOL_CALL, {"tool": "wire_transfer", "decision": "ALLOW", "result": "SENT"})
    return issue_certificate("p", ["wire_transfer"], log)[0], log, {}

def _keyless_hmac():
    log = _honest_log()
    return issue_certificate("p", ["read_docs"], log, key=b"secret")[0], log, {}

def _out_of_policy():
    log = EventLog(); log.append(Kind.TOOL_CALL, {"tool": "wire_transfer", "decision": "ALLOW", "result": "x", "result_hash": "h"})
    return issue_certificate("p", ["read_docs"], log, priv=PRIV)[0], log, {}

def _edited_event():
    log = _honest_log(); cert, _ = issue_certificate("p", ["read_docs"], log, priv=PRIV)
    log.events[1].payload["decision"] = "DENY"
    return cert, log, {}

def _deleted_event():
    log = _honest_log(); cert, _ = issue_certificate("p", ["read_docs"], log, priv=PRIV)
    log.events.pop()
    return cert, log, {}

def _reordered():
    log = _honest_log(); log.append(Kind.AGENT_STEP, {"state": "x"})
    cert, _ = issue_certificate("p", ["read_docs"], log, priv=PRIV)
    log.events[0], log.events[1] = log.events[1], log.events[0]
    return cert, log, {}

def _edited_digest():
    log = _honest_log(); cert, _ = issue_certificate("p", ["read_docs"], log, priv=PRIV)
    bad = copy.deepcopy(cert); bad.model_digests = ["0" * 64]
    return bad, log, {}

def _tampered_chain():
    log = _honest_log(); cert, _ = issue_certificate("p", ["read_docs"], log, priv=PRIV)
    log.events[1].prev = "00" * 32
    return cert, log, {}

def _backdated_v1():
    log = _honest_log()
    cert = _v1_signed(log, ["read_docs"], issued_at="2019-01-01T00:00:00Z")
    return cert, log, {}

def _decision_string():
    log = EventLog(); log.append(Kind.TOOL_CALL, {"tool": "wire_transfer", "decision": "PERMIT", "result": "x"})
    return issue_certificate("p", ["read_docs"], log, priv=PRIV)[0], log, {}

def _relabel_kind():
    log = EventLog(); log.append("TOOL_CALL", {"tool": "wire_transfer", "decision": "ALLOW", "result": "x"})
    return issue_certificate("p", ["read_docs"], log, priv=PRIV)[0], log, {}

def _resign_pinned():
    log = EventLog(); log.append(Kind.TOOL_CALL, {"tool": "read_docs", "decision": "ALLOW", "result": "x", "result_hash": "h"})
    apriv, _ = gen_ed25519()
    cert, _ = issue_certificate("p", ["read_docs"], log, priv=apriv)   # signed by an attacker key
    return cert, log, {"pinned_pubkeys": [PUB]}                        # but pinned to the trusted key


# ---- positive: the verifier MUST accept (expect ok=True + flags) ----------------

def _honest():
    log = _honest_log()
    return issue_certificate("p", ["read_docs"], log, priv=PRIV)[0], log, {}

def _v1_receipt():
    log = _honest_log()
    return _v1_signed(log, ["read_docs"]), log, {}

def _observe_only():
    log = EventLog(); log.append(Kind.TOOL_CALL, {"tool": "read_docs", "decision": "OBSERVED", "result": "x"})
    return issue_certificate("p", ["read_docs"], log, priv=PRIV)[0], log, {}

def _hosted_integrity_only():
    log = EventLog()
    log.append_llm_call("ph", [1, 2], seed=0, model_digest="",
                        provider={"provider": "openai", "model_version": "gpt-x"})
    return issue_certificate("p", [], log, priv=PRIV)[0], log, {}


# id, description, expected {ok, flags?}, builder
CASES = [
    ("R01", "reject: unsigned receipt",               {"ok": False}, _unsigned),
    ("R02", "reject: keyless HMAC",                    {"ok": False}, _keyless_hmac),
    ("R03", "reject: ungranted tool in caps",         {"ok": False}, _out_of_policy),
    ("R04", "reject: edited event",                   {"ok": False}, _edited_event),
    ("R05", "reject: deleted event",                  {"ok": False}, _deleted_event),
    ("R06", "reject: reordered events",               {"ok": False}, _reordered),
    ("R07", "reject: edited model digest",            {"ok": False}, _edited_digest),
    ("R08", "reject: tampered chain pointer",         {"ok": False}, _tampered_chain),
    ("R09", "reject: backdated v1 timestamp",         {"ok": False}, _backdated_v1),
    ("R10", "reject: decision-string evasion",        {"ok": False}, _decision_string),
    ("R11", "reject: relabelled event kind",          {"ok": False}, _relabel_kind),
    ("R12", "reject: unpinned attacker re-sign",      {"ok": False}, _resign_pinned),
    ("A01", "accept: honest enforced receipt",        {"ok": True, "flags": {"containment_enforced": True}}, _honest),
    ("A02", "accept: valid v1 receipt (back-compat)", {"ok": True}, _v1_receipt),
    ("A03", "accept: observe-only (flagged)",         {"ok": True, "flags": {"containment_enforced": False}}, _observe_only),
    ("A04", "accept: hosted integrity-only",          {"ok": True, "flags": {"model_digests_match": True}}, _hosted_integrity_only),
]


def _slug(cid: str, desc: str) -> str:
    tail = re.sub(r"^(reject|accept):\s*", "", desc)
    tail = re.sub(r"[^a-z0-9]+", "-", tail.lower()).strip("-")
    return f"{cid}-{tail}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json"):
        old.unlink()
    index = []
    for cid, desc, expect, build in CASES:
        cert, log, verify_kwargs = build()
        slug = _slug(cid, desc)
        vector = {
            "id": cid,
            "description": desc,
            "expect": expect,
            "verify_kwargs": verify_kwargs,
            "certificate": asdict(cert),
            "log": [asdict(e) for e in log.events],
        }
        (OUT / f"{slug}.json").write_text(json.dumps(vector, indent=2, sort_keys=True) + "\n")
        index.append({"id": cid, "description": desc, "file": f"{slug}.json",
                      "expect": expect})
    (OUT / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(f"wrote {len(index)} receipt vectors + index.json to {OUT}")


if __name__ == "__main__":
    main()
