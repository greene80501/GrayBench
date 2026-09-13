"""Inspection commands for the replacement engine; campaign release gates remain explicit."""

import argparse
import json
from pathlib import Path

from graybench.campaign_setup import CampaignSetup, execution_context, validate_host
from graybench.contracts import ModelSpec, Protocol
from graybench.datasets import inventory, load_suite
from graybench.evaluation_campaign import UpstreamCampaign
from graybench.identity import canonical
from graybench.ledger import Ledger
from graybench.provenance import environment
from graybench.providers import adapter
from graybench.transport import Transport


def main():
    parser = argparse.ArgumentParser(description="GrayBench 3 replacement engine (development)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Record relevant runtime and source provenance")
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
    catalog = commands.add_parser(
        "inventory", help="Import both pinned suites and emit review cards"
    )
    catalog.add_argument("cache", type=Path)
    catalog.add_argument("--download", action="store_true")
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
