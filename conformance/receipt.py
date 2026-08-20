"""Receipt-verifier conformance — what a conformant vitnify verifier MUST do.

Negative cases: a forged or tampered receipt the verifier must REJECT (`ok` false).
Positive cases: a valid receipt it must ACCEPT (`ok` true), with the right flags —
a genuine v1 receipt still verifies, an observe-only receipt is flagged
`containment_enforced=false`, a hosted receipt is integrity-only.

Runs against whatever `vitnify` is installed. Forged receipts are constructed via
the reference implementation's own helpers; freezing them as static JSON vectors so
any implementation (not just this one) can be tested is the next step for the corpus.
"""
from __future__ import annotations
import copy

from vitnify.events import EventLog, Kind
from vitnify.certificate import (
    ExecutionCertificate, issue_certificate, verify_certificate, gen_ed25519,
    _canon, _digest32,
)
from vitnify._vendor.pck.cas import MerkleCAS

PRIV, PUB = gen_ed25519()


def _honest_log():
    log = EventLog()
    log.append_llm_call("ph", [1, 2, 3], seed=0, model_digest="dd")
    log.append(Kind.TOOL_CALL, {"tool": "read_docs", "decision": "ALLOW", "result": "r", "result_hash": "h"})
    return log


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
    log = _honest_log(); cas = MerkleCAS(log.chunks())
    body = {"v": "vitnify-receipt v1", "program_hash": "p", "capabilities": ["read_docs"],
            "event_root": cas.root, "n_events": len(log), "head_hash": log.head(),
            "model_digests": log.model_digests()}
    sig = PRIV.sign(bytes.fromhex(_digest32(_canon(body).encode()))).hex()
    cert = ExecutionCertificate("p", ["read_docs"], cas.root, len(log), log.head(), model_digests=log.model_digests())
    cert.v, cert.sig, cert.sig_alg, cert.pubkey = "vitnify-receipt v1", sig, "ed25519", PUB
    cert.issued_at = "2019-01-01T00:00:00Z"
    return cert, log, {}

def _decision_string():
    log = EventLog(); log.append(Kind.TOOL_CALL, {"tool": "wire_transfer", "decision": "PERMIT", "result": "x"})
    return issue_certificate("p", ["read_docs"], log, priv=PRIV)[0], log, {}

def _relabel_kind():
    log = EventLog(); log.append("TOOL_CALL", {"tool": "wire_transfer", "decision": "ALLOW", "result": "x"})
    return issue_certificate("p", ["read_docs"], log, priv=PRIV)[0], log, {}

def _resign_unpinned():
    log = EventLog(); log.append(Kind.TOOL_CALL, {"tool": "read_docs", "decision": "ALLOW", "result": "x", "result_hash": "h"})
    apriv, _ = gen_ed25519()
    cert, _ = issue_certificate("p", ["read_docs"], log, priv=apriv)   # attacker's key
    return cert, log, {"pinned_pubkeys": [PUB]}                        # pinned to the trusted key -> reject


# ---- positive: the verifier MUST accept (expect ok=True + flags) ----------------

def _honest():
    log = _honest_log()
    return issue_certificate("p", ["read_docs"], log, priv=PRIV)[0], log, {}

def _v1_receipt():
    log = _honest_log(); cas = MerkleCAS(log.chunks())
    body = {"v": "vitnify-receipt v1", "program_hash": "p", "capabilities": ["read_docs"],
            "event_root": cas.root, "n_events": len(log), "head_hash": log.head(),
            "model_digests": log.model_digests()}
    sig = PRIV.sign(bytes.fromhex(_digest32(_canon(body).encode()))).hex()
    cert = ExecutionCertificate("p", ["read_docs"], cas.root, len(log), log.head(), model_digests=log.model_digests())
    cert.v, cert.sig, cert.sig_alg, cert.pubkey = "vitnify-receipt v1", sig, "ed25519", PUB
    return cert, log, {}

def _observe_only():
    log = EventLog(); log.append(Kind.TOOL_CALL, {"tool": "read_docs", "decision": "OBSERVED", "result": "x"})
    return issue_certificate("p", ["read_docs"], log, priv=PRIV)[0], log, {}

def _hosted_integrity_only():
    log = EventLog()
    log.append_llm_call("ph", [1, 2], seed=0, model_digest="",   # hosted: no computation bound
                        provider={"provider": "openai", "model_version": "gpt-x"})
    return issue_certificate("p", [], log, priv=PRIV)[0], log, {}


# id, description, expected {ok, flags?}, builder
CASES = [
    # negative
    ("R01", "reject: unsigned receipt",              {"ok": False}, _unsigned),
    ("R02", "reject: keyless HMAC",                  {"ok": False}, _keyless_hmac),
    ("R03", "reject: ungranted tool in caps",        {"ok": False}, _out_of_policy),
    ("R04", "reject: edited event",                  {"ok": False}, _edited_event),
    ("R05", "reject: deleted event",                 {"ok": False}, _deleted_event),
    ("R06", "reject: reordered events",              {"ok": False}, _reordered),
    ("R07", "reject: edited model digest",           {"ok": False}, _edited_digest),
    ("R08", "reject: tampered chain pointer",        {"ok": False}, _tampered_chain),
    ("R09", "reject: backdated v1 timestamp",        {"ok": False}, _backdated_v1),
    ("R10", "reject: decision-string evasion",       {"ok": False}, _decision_string),
    ("R11", "reject: relabelled event kind",         {"ok": False}, _relabel_kind),
    ("R12", "reject: unpinned attacker re-sign",     {"ok": False}, _resign_unpinned),
    # positive
    ("A01", "accept: honest enforced receipt",       {"ok": True, "flags": {"containment_enforced": True}}, _honest),
    ("A02", "accept: valid v1 receipt (back-compat)", {"ok": True}, _v1_receipt),
    ("A03", "accept: observe-only (flagged)",        {"ok": True, "flags": {"containment_enforced": False}}, _observe_only),
    ("A04", "accept: hosted integrity-only",         {"ok": True, "flags": {"model_digests_match": True}}, _hosted_integrity_only),
]


def run():
    """Run every receipt case; return (results, all_passed)."""
    results = []
    for cid, desc, expect, build in CASES:
        try:
            cert, log, kwargs = build()
            checks = verify_certificate(cert, log, **kwargs)
            ok = checks.get("ok")
            passed = (ok is expect["ok"])
            for k, v in expect.get("flags", {}).items():
                passed = passed and (checks.get(k) is v)
        except Exception as e:
            ok, passed = f"raised {type(e).__name__}", False
        results.append((cid, desc, expect["ok"], ok, passed))
    return results, all(r[4] for r in results)
