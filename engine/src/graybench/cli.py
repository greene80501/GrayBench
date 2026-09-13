"""Inspection commands for the replacement engine; campaign release gates remain explicit."""

import argparse
import json
from pathlib import Path

from graybench.campaign_setup import CampaignSetup, build_setup, execution_context, validate_host
from graybench.contracts import ModelSpec, Protocol
from graybench.datasets import EXTERNAL_IDS, inventory, load_suite
from graybench.evaluation_campaign import UpstreamCampaign
from graybench.identity import canonical
from graybench.ledger import Ledger
from graybench.model_discovery import observe_run
from graybench.provenance import environment
from graybench.providers import adapter
from graybench.reference_scan import inspect_reference_scan, run_reference_scan
from graybench.transport import Transport
from graybench.upstream import UpstreamJudge


def main():
    parser = argparse.ArgumentParser(description="GrayBench 3 replacement engine (development)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Record relevant runtime and source provenance")
    reference = commands.add_parser(
        "reference-scan", help="Calibrate pinned references; never a model score"
    )
    reference.add_argument("cache", type=Path)
    reference.add_argument("output", type=Path)
    reference.add_argument("--image", required=True)
    reference.add_argument("--docker", default="docker")
    reference.add_argument("--suite", choices=("normal", "hard", "both"), default="both")
    reference.add_argument(
        "--offline", action="store_true", help="Explicitly omit known external-service tasks"
    )
    inspect_scan = commands.add_parser(
        "reference-inspect", help="Verify reference evidence and identify incomplete invocations"
    )
    inspect_scan.add_argument("path", type=Path)
    validate = commands.add_parser(
        "validate-protocol", help="Validate a frozen experiment contract"
    )
    validate.add_argument("path", type=Path)
    verify = commands.add_parser("verify-ledger", help="Verify artifact hashes and event chain")
    verify.add_argument("path", type=Path)
    summary = commands.add_parser("summary", help="Report completeness before computing a score")
    summary.add_argument("path", type=Path)
    summary.add_argument("run_id")
    discover = commands.add_parser("discover", help="Read model/server metadata without generation")
    discover.add_argument("model_spec", type=Path)
    observe = commands.add_parser(
        "campaign-observe", help="Save provider metadata and establish a discovery baseline"
    )
    observe.add_argument("ledger", type=Path)
    observe.add_argument("run_id")
    catalog = commands.add_parser(
        "inventory", help="Import both pinned suites and emit review cards"
    )
    catalog.add_argument("cache", type=Path)
    catalog.add_argument("--download", action="store_true")
    plan = commands.add_parser(
        "campaign-plan", help="Freeze selected tasks and requests offline; no generations"
    )
    plan.add_argument("model_spec", type=Path)
    plan.add_argument("cache", type=Path)
    plan.add_argument("output", type=Path)
    plan.add_argument("--image", required=True)
    plan.add_argument("--name", required=True)
    plan.add_argument("--repeats", type=int, default=1)
    plan.add_argument("--system-prompt", type=Path)
    selection = plan.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--task", action="append", help="Exact suite/task key; repeat for multiple tasks"
    )
    selection.add_argument("--suite", choices=("normal", "hard", "both"))
    create = commands.add_parser(
        "campaign-create", help="Validate and save a development campaign; no generations"
    )
    create.add_argument("setup", type=Path)
    create.add_argument("cache", type=Path)
    create.add_argument("ledger", type=Path)
    step = commands.add_parser(
        "campaign-step", help="Perform at most one generation or protected judgment"
    )
    step.add_argument("ledger", type=Path)
    step.add_argument("run_id")
    step.add_argument("cache", type=Path)
    step.add_argument("--docker", default="docker")
    args = parser.parse_args()
    if args.command == "doctor":
        result = environment()
    elif args.command == "reference-inspect":
        result = inspect_reference_scan(args.path)
    elif args.command == "reference-scan":
        all_tasks = tuple(
            task
            for suite in ("normal", "hard")
            if args.suite in (suite, "both")
            for task in load_suite(suite, args.cache)
        )
        excluded = {
            f"{t.public.suite}/{t.public.task_id}": t.digest
            for t in all_tasks
            if args.offline and int(t.public.task_id.rsplit("/", 1)[1]) in EXTERNAL_IDS
        }
        tasks = tuple(
            t for t in all_tasks if f"{t.public.suite}/{t.public.task_id}" not in excluded
        )
        result = run_reference_scan(
            tasks,
            UpstreamJudge(image=args.image, docker=args.docker),
            args.output,
            selection={"offline": args.offline, "excluded": excluded},
        )
    elif args.command == "campaign-observe":
        if not args.ledger.is_file():
            parser.error("Ledger does not exist")
        ledger = Ledger(args.ledger)
        try:
            ledger.verify()
            transport = Transport(ledger.protocol(args.run_id).model)
            try:
                result = observe_run(ledger, args.run_id, transport)
            finally:
                transport.close()
        finally:
            ledger.close()
    elif args.command == "campaign-plan":
        model = ModelSpec.model_validate_json(args.model_spec.read_bytes())
        all_tasks = tuple(
            task for suite in ("normal", "hard") for task in load_suite(suite, args.cache)
        )
        if args.task:
            if len(set(args.task)) != len(args.task):
                parser.error("Duplicate task selection")
            keyed = {f"{t.public.suite}/{t.public.task_id}": t for t in all_tasks}
            if set(args.task) - keyed.keys():
                parser.error("Unknown task selection")
            tasks = tuple(keyed[key] for key in args.task)
        else:
            tasks = tuple(
                t for t in all_tasks if args.suite == "both" or t.public.suite == args.suite
            )
        setup = build_setup(
            args.name,
            model,
            tasks,
            args.image,
            repeats=args.repeats,
            system_prompt=args.system_prompt.read_text(encoding="utf-8")
            if args.system_prompt
            else None,
        )
        # Exclusive creation preserves an existing experiment instead of silently rewriting it.
        with args.output.open("x", encoding="utf-8") as output:
            output.write(setup.model_dump_json(indent=2) + "\n")
        result = {
            "setup_digest": setup.digest,
            "planned_samples": len(tasks) * args.repeats,
            "certification": "not_certified",
            "purpose": "development",
            "external_task_keys": [
                f"{t.public.suite}/{t.public.task_id}"
                for t in tasks
                if int(t.public.task_id.rsplit("/", 1)[1]) in EXTERNAL_IDS
            ],
        }
    elif args.command == "campaign-create":
        setup = CampaignSetup.model_validate_json(args.setup.read_bytes())
        setup.tasks(args.cache)
        context = execution_context(setup)
        ledger = Ledger(args.ledger)
        try:
            result = {
                "run_id": ledger.create_run(setup.protocol, context),
                "certification": "not_certified",
            }
        finally:
            ledger.close()
    elif args.command == "campaign-step":
        if not args.ledger.is_file():
            parser.error("Ledger does not exist")
        ledger = Ledger(args.ledger)
        try:
            ledger.verify()
            context = ledger.context(args.run_id)
            setup = CampaignSetup.model_validate_json(canonical(context["setup"]))
            if setup.protocol != ledger.protocol(args.run_id):
                parser.error("Stored setup does not match the run protocol")
            validate_host(context)
            tasks = setup.tasks(args.cache)
            transport = Transport(
                setup.protocol.model,
                timeout_seconds=setup.http_timeout,
                max_response_bytes=setup.response_limit,
            )
            try:
                result = UpstreamCampaign(
                    ledger, args.run_id, tasks, setup.judge(args.docker), transport
                ).step()
                result["summary"] = ledger.summary(args.run_id)
            finally:
                transport.close()
        finally:
            ledger.close()
    elif args.command == "validate-protocol":
        protocol = Protocol.model_validate_json(args.path.read_bytes())
        result = {
            "valid": True,
            "protocol_digest": protocol.digest,
            "release_validation": "not_performed",
        }
    elif args.command in {"verify-ledger", "summary"}:
        if not args.path.is_file():
            parser.error("Ledger does not exist")
        ledger = Ledger(args.path)
        try:
            result = (
                ledger.verify() if args.command == "verify-ledger" else ledger.summary(args.run_id)
            )
        finally:
            ledger.close()
    elif args.command == "discover":
        spec = ModelSpec.model_validate_json(args.model_spec.read_bytes())
        transport = Transport(spec)
        try:
            result = {
                "model": spec.model_dump(mode="json"),
                "observations": [
                    o.model_dump(mode="json") for o in transport.discover(adapter(spec.adapter))
                ],
            }
        finally:
            transport.close()
    else:
        tasks = load_suite("normal", args.cache, download=args.download) + load_suite(
            "hard", args.cache, download=args.download
        )
        result = inventory(tasks)
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
