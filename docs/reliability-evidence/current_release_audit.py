"""Read-only current-source prompt rendering and release-gate audit; no API calls."""

import argparse
import json
from pathlib import Path

from graybench.contracts import ModelSpec
from graybench.datasets import EXTERNAL_IDS, PINS, load_suite
from graybench.identity import identity
from graybench.protected_task_registry import VALUE_TASKS
from graybench.provenance import source_manifest
from graybench.task_admission import AdmissionInventory, admission_blockers

from graybench.providers import BUILTINS, adapter


def expected_body(name, model, prompt):
    if name in {"openai-chat", "openai-compatible-chat", "ollama"}:
        result = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        if name != "ollama":
            result["n"] = 1
        return result
    if name == "openai-responses":
        return {"model": model, "input": prompt, "store": False, "stream": False}
    if name == "gemini":
        return {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    raise ValueError("Unknown built-in adapter")


def audit(cache: Path, inventory_path: Path):
    tasks = tuple(task for suite in ("normal", "hard") for task in load_suite(suite, cache))
    if len(tasks) != 302:
        raise ValueError("Pinned normal and hard population is not 302")
    inventory = AdmissionInventory.model_validate_json(inventory_path.read_text(encoding="utf-8"))
    if inventory.source_pins != PINS:
        raise ValueError("Inventory source pins differ from pinned data")
    pinned = {(task.public.suite, task.public.task_id): task.digest for task in tasks}
    if any(
        pinned.get((card.source_suite, card.source_key.split("/", 1)[1])) != card.source_task_digest
        for card in inventory.cards
    ):
        raise ValueError("Inventory task digests differ from pinned tasks")
    rendering = {}
    for name in BUILTINS:
        base_url = "http://localhost:11434" if name == "ollama" else "https://example.test/v1"
        spec = ModelSpec(adapter=name, model="probe-model", base_url=base_url)
        provider = adapter(name)
        rows = []
        for task in tasks:
            request = provider.prepare(spec, task.public, None)
            if request.body != expected_body(name, spec.model, task.public.prompt):
                raise ValueError(f"{name} changed a public prompt or added request content")
            rows.append((task.public.suite, task.public.task_id, request.digest))
        rendering[name] = {"requests": len(rows), "request_manifest_digest": identity(rows)}
    source = source_manifest()["digest"]
    return {
        "kind": "graybench_current_release_audit_v1",
        "scope": "local pinned data and adapter preparation; no model or Docker call",
        "engine_source_digest": source,
        "suite_tasks": {"normal": 151, "hard": 151},
        "offline_tasks_per_suite": 151 - len(EXTERNAL_IDS),
        "protected_value_task_families": sorted(VALUE_TASKS),
        "adapter_rendering": rendering,
        "admission": {
            "inventory_digest": inventory.digest,
            "inventory_source_digest": inventory.source_digest,
            "inventory_matches_current_source": inventory.source_digest == source,
            "cards": len(inventory.cards),
            "cards_with_public_contract": sum(
                card.public_contract_digest is not None for card in inventory.cards
            ),
            "cards_with_protected_judge": sum(
                card.protected_judge_digest is not None for card in inventory.cards
            ),
            "cards_with_review": sum(bool(card.reviews) for card in inventory.cards),
            "cards_without_structural_blockers": sum(
                not admission_blockers(card) for card in inventory.cards
            ),
            "publication_eligible": inventory.publication_eligible,
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.cache, args.inventory), sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
