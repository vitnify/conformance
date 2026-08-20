"""Default adapter — the reference Python `vitnify` verifier.

Reconstructs the implementation's certificate and event-log objects from the frozen
JSON (the receipt's signed body is rebuilt from its own fields, so a v1 receipt still
verifies under a v2 verifier) and returns the full checks dict.
"""
from __future__ import annotations


def verify(vector: dict) -> dict:
    from vitnify.certificate import ExecutionCertificate, verify_certificate
    from vitnify.events import Event, EventLog

    cert = ExecutionCertificate(**vector["certificate"])
    log = EventLog.from_events([Event(**e) for e in vector["log"]])
    return verify_certificate(cert, log, **(vector.get("verify_kwargs") or {}))
