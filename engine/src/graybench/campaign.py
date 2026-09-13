"""Single-step durable generation scheduling; no hidden retry loops or answer replacement.

Each step dispatches at most one request. Callers can sleep or exit on a deferred result;
the database, not in-memory state, enforces backoff after restart. This is the generation
component of the campaign, not task eligibility certification or a complete scoring runner.
"""

from graybench.contracts import PreparedRequest
from graybench.ledger import Ledger, StateError
from graybench.model_discovery import observe_run
from graybench.provenance import source_manifest
from graybench.providers import adapter
from graybench.transport import Delivery, Transport


class GenerationRunner:
    def __init__(
        self,
        ledger: Ledger,
        run_id: str,
        requests: dict[str, PreparedRequest],
        transport: Transport,
    ):
        self.ledger, self.run_id = ledger, run_id
        self.requests, self.transport = dict(requests), transport

    def step(self) -> dict:
        protocol = self.ledger.protocol(self.run_id)
        if source_manifest()["digest"] != protocol.generation_code_digest:
            raise StateError("Generation source differs from frozen experiment")
        if self.transport.spec != protocol.model:
            raise StateError("Transport model or endpoint differs from frozen experiment")
        if set(self.requests) != set(protocol.task_keys) or any(
            self.requests[key].digest != protocol.request_digests[key] for key in protocol.task_keys
        ):
            raise StateError("Prepared requests differ from frozen experiment")
        self.ledger.verify()
        if self.ledger.model_identity(self.run_id)["status"] == "unresolved":
            return {"state": "stopped", "reason": "model_identity_unresolved"}
        samples = self.ledger.samples(self.run_id)
        states = [(sample, self.ledger.dispatch_state(sample["id"])) for sample in samples]
        if any(state["state"] == "unresolved_delivery" for _, state in states):
            return {"state": "stopped", "reason": "unresolved_delivery"}
        for sample, state in states:
            if state["state"] != "ready":
                continue
            request = self.requests[sample["task_key"]]
            if self.ledger.discovery_status(self.run_id)["status"] != "not_observed":
                if observe_run(self.ledger, self.run_id, self.transport)["status"] == "unresolved":
                    return {"state": "stopped", "reason": "model_discovery_unresolved"}
            # Concurrent dispatch claims and the clock are rechecked inside the transaction.
            attempt = self.ledger.begin_attempt(sample["id"], request)
            try:
                delivery = self.transport.generate(request, adapter(protocol.model.adapter))
            except Exception as exc:
                # Unknown transport exceptions may occur after remote execution. Keep the
                # diagnostic type only, since arbitrary exception strings can contain secrets.
                delivery = Delivery("ambiguous", None, {"error_type": type(exc).__name__})
            self.ledger.finish_attempt(
                attempt, delivery.kind, delivery.evidence, delivery.status, delivery.generation
            )
            return {"state": "dispatched", "attempt_id": attempt, "delivery": delivery.kind}
        deferred = [state["not_before"] for _, state in states if state["state"] == "deferred"]
        if deferred:
            return {"state": "deferred", "not_before": min(deferred)}
        return {
            "state": "generation_complete"
            if all(s["state"] == "returned" for _, s in states)
            else "stopped",
            "reason": "all_returned"
            if all(s["state"] == "returned" for _, s in states)
            else "retry_exhausted",
        }
