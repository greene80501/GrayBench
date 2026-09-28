"""Inspection commands for the replacement engine; campaign release gates remain explicit."""

import argparse
import json
from pathlib import Path

from graybench.campaign_setup import CampaignSetup, build_setup, execution_context, validate_host
from graybench.comparison import ComparisonPlan, compare_runs, make_plan
from graybench.contracts import ModelObservationTiming, ModelSpec, Protocol
from graybench.datasets import EXTERNAL_IDS, inventory, load_suite
from graybench.evaluation_campaign import UpstreamCampaign
from graybench.evaluation_recipes import RECIPES
from graybench.extraction import EXTRACTION_POLICIES
from graybench.identity import canonical
from graybench.ledger import Ledger
from graybench.model_discovery import observe_run
from graybench.native_campaign import NativeCampaign, NativeCampaignSetup, build_native_setup
from graybench.native_cohort import NATIVE_EXCEPTION_POLICIES, freeze_native_cohort, task_key
from graybench.protected_campaign import (
    ProtectedCampaign,
    ProtectedCampaignSetup,
    build_protected_setup,
    freeze_protected_cohort,
)
from graybench.protected_task_registry import VALUE_TASKS, revised_value_task
from graybench.provenance import environment
from graybench.providers import adapter
from graybench.reference_scan import (
    inspect_reference_scan,
    run_native_reference_scan,
    run_reference_scan,
)
from graybench.task_admission import admission_blockers, build_pending_inventory
from graybench.transport import Transport
from graybench.upstream import UpstreamJudge


def _comparison_setup(payload: bytes):
    track = json.loads(payload).get("protocol", {}).get("track")
    setup_type = {
        "qhe-pinned-native-v1": NativeCampaignSetup,
        "graybench-protected-semantic-v1": ProtectedCampaignSetup,
    }.get(track, CampaignSetup)
    return setup_type.model_validate_json(payload)


def _comparison_tasks(setup, cache: Path):
    if isinstance(setup, NativeCampaignSetup):
        tasks = setup.tasks(cache)
        setup.validate_for_run(cache, setup.protocol, tasks=tasks)
        return tasks
    if isinstance(setup, ProtectedCampaignSetup):
        setup.validate_for_run(cache, setup.protocol)
        return setup.tasks
    return setup.tasks(cache)


def main():
    parser = argparse.ArgumentParser(description="GrayBench 3 replacement engine (development)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Record relevant runtime and source provenance")
    comparison_plan = commands.add_parser(
        "comparison-plan", help="Freeze an explicit paired family analysis"
    )
    comparison_plan.add_argument("left_setup", type=Path)
    comparison_plan.add_argument("right_setup", type=Path)
    comparison_plan.add_argument("cache", type=Path)
    comparison_plan.add_argument("output", type=Path)
    comparison_plan.add_argument("--seed", type=int, required=True)
    comparison_plan.add_argument("--resamples", type=int, default=10000)
    comparison_plan.add_argument("--confidence", type=float, default=0.95)
    comparison_plan.add_argument("--configuration-comparison", required=True)
    comparison = commands.add_parser(
        "compare", help="Compare complete frozen cohorts; development only"
    )
    comparison.add_argument("plan", type=Path)
    comparison.add_argument("left_ledger", type=Path)
    comparison.add_argument("left_run")
    comparison.add_argument("right_ledger", type=Path)
    comparison.add_argument("right_run")
    comparison.add_argument("cache", type=Path)
    comparison.add_argument("output", type=Path)
    reference = commands.add_parser(
        "reference-scan", help="Calibrate pinned references; never a model score"
    )
    reference.add_argument("cache", type=Path)
    reference.add_argument("output", type=Path)
    reference.add_argument("--image", required=True)
    reference.add_argument("--docker", default="docker")
    reference.add_argument("--bridge-protocol", type=int, choices=(3, 4), default=3)
    reference.add_argument("--suite", choices=("normal", "hard", "both"), default="both")
    reference.add_argument(
        "--offline", action="store_true", help="Explicitly omit known external-service tasks"
    )
    native_reference = commands.add_parser(
        "native-reference-scan",
        help="Calibrate canonical answers in the native track; no model score",
    )
    native_reference.add_argument("cache", type=Path)
    native_reference.add_argument("output", type=Path)
    native_reference.add_argument("--suite", choices=("normal", "hard"), required=True)
    native_reference.add_argument("--image", required=True)
    native_reference.add_argument("--docker", default="docker")
    native_reference.add_argument("--extraction", choices=EXTRACTION_POLICIES, required=True)
    native_reference.add_argument(
        "--exception-policy",
        choices=NATIVE_EXCEPTION_POLICIES,
        default="conservative_unattributed_v1",
    )
    native_reference.add_argument("--task", action="append", default=[])
    native_reference.add_argument("--include-external", action="store_true")
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
    admission = commands.add_parser(
        "admission-inventory", help="Write all 302 pinned task cards as pending review"
    )
    admission.add_argument("cache", type=Path)
    admission.add_argument("output", type=Path)
    plan = commands.add_parser(
        "campaign-plan", help="Freeze selected tasks and requests offline; no generations"
    )
    plan.add_argument("model_spec", type=Path)
    plan.add_argument("cache", type=Path)
    plan.add_argument("output", type=Path)
    plan.add_argument("--image", required=True)
    plan.add_argument("--parser-image", help="Immutable task82 QPY parser image digest")
    plan.add_argument("--name", required=True)
    plan.add_argument("--evaluation-recipe", choices=RECIPES, default="upstream")
    plan.add_argument(
        "--extraction",
        choices=EXTRACTION_POLICIES,
        default="raw_or_single_python_fence_v1",
    )
    plan.add_argument("--repeats", type=int, default=1)
    plan.add_argument("--protocol-version", choices=("3.1", "3.2", "3.3"), default="3.1")
    plan.add_argument("--max-pre-observation-age", type=float)
    plan.add_argument("--max-post-observation-delay", type=float)
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
    native_plan = commands.add_parser(
        "native-plan", help="Freeze one pinned native QHE suite; development only"
    )
    native_plan.add_argument("model_spec", type=Path)
    native_plan.add_argument("cache", type=Path)
    native_plan.add_argument("output", type=Path)
    native_plan.add_argument("--name", required=True)
    native_plan.add_argument("--label", required=True)
    native_plan.add_argument("--suite", choices=("normal", "hard"), required=True)
    native_plan.add_argument(
        "--population", choices=("offline_143", "custom_development"), default="offline_143"
    )
    native_plan.add_argument("--image", required=True)
    native_plan.add_argument(
        "--task", action="append", help="Exact suite/task key for a custom cohort"
    )
    native_plan.add_argument(
        "--extraction", choices=EXTRACTION_POLICIES, default="raw_or_single_python_fence_v1"
    )
    native_plan.add_argument(
        "--exception-policy",
        choices=NATIVE_EXCEPTION_POLICIES,
        default="conservative_unattributed_v1",
    )
    native_plan.add_argument("--repeats", type=int, default=1)
    native_plan.add_argument("--system-prompt", type=Path)
    native_create = commands.add_parser(
        "native-create", help="Create a frozen native development run"
    )
    native_create.add_argument("setup", type=Path)
    native_create.add_argument("cache", type=Path)
    native_create.add_argument("ledger", type=Path)
    native_step = commands.add_parser(
        "native-step", help="Perform one native generation or judgment"
    )
    native_step.add_argument("ledger", type=Path)
    native_step.add_argument("run_id")
    native_step.add_argument("cache", type=Path)
    native_step.add_argument("--docker", default="docker")
    protected_plan = commands.add_parser(
        "protected-plan", help="Freeze reviewed value tasks and all exclusions; development only"
    )
    protected_plan.add_argument("model_spec", type=Path)
    protected_plan.add_argument("cache", type=Path)
    protected_plan.add_argument("output", type=Path)
    protected_plan.add_argument("--name", required=True)
    protected_plan.add_argument("--label", required=True)
    protected_plan.add_argument("--suite", choices=("normal", "hard"), required=True)
    protected_plan.add_argument("--task", action="append", required=True)
    protected_plan.add_argument("--image", required=True)
    protected_plan.add_argument("--repeats", type=int, default=1)
    protected_plan.add_argument("--system-prompt", type=Path)
    protected_create = commands.add_parser(
        "protected-create", help="Create a frozen protected development run"
    )
    protected_create.add_argument("setup", type=Path)
    protected_create.add_argument("cache", type=Path)
    protected_create.add_argument("ledger", type=Path)
    protected_step = commands.add_parser(
        "protected-step", help="Perform one protected generation or judgment"
    )
    protected_step.add_argument("ledger", type=Path)
    protected_step.add_argument("run_id")
    protected_step.add_argument("cache", type=Path)
    protected_step.add_argument("--docker", default="docker")
    args = parser.parse_args()
    if args.command == "doctor":
        result = environment()
    elif args.command == "comparison-plan":
        left = _comparison_setup(args.left_setup.read_bytes())
        right = _comparison_setup(args.right_setup.read_bytes())
        tasks = _comparison_tasks(left, args.cache)
        _comparison_tasks(right, args.cache)
        plan = make_plan(
            left.protocol,
            right.protocol,
            tasks,
            seed=args.seed,
            resamples=args.resamples,
            confidence=args.confidence,
            configuration_comparison=args.configuration_comparison,
        )
        with args.output.open("xb") as stream:
            stream.write(canonical(plan.model_dump(mode="json")))
        result = {
            "plan_digest": plan.digest,
            "output": str(args.output),
            "publication_eligible": False,
        }
    elif args.command == "compare":
        plan = ComparisonPlan.model_validate_json(args.plan.read_bytes())
        tasks = ()
        if plan.left.track == "upstream":
            tasks = tuple(
                task
                for suite in ("normal", "hard")
                for task in load_suite(suite, args.cache)
                if f"{suite}/{task.public.task_id}" in plan.left.task_keys
            )
        if not args.left_ledger.is_file() or not args.right_ledger.is_file():
            parser.error("Comparison ledgers must already exist")
        left, right = Ledger(args.left_ledger), Ledger(args.right_ledger)
        try:
            if plan.left.track != "upstream":
                setups = [
                    _comparison_setup(canonical(book.context(run)["setup"]))
                    for book, run in ((left, args.left_run), (right, args.right_run))
                ]
                for setup, expected in zip(setups, (plan.left, plan.right), strict=True):
                    if setup.protocol != expected:
                        parser.error("Stored setup differs from comparison protocol")
                    _comparison_tasks(setup, args.cache)
                tasks = _comparison_tasks(setups[0], args.cache)
            report = compare_runs(plan, left, args.left_run, right, args.right_run, tasks=tasks)
        finally:
            left.close()
            right.close()
        with args.output.open("xb") as stream:
            stream.write(canonical(report))
        result = {
            "output": str(args.output),
            "status": report["status"],
            "comparison": report["comparison"],
        }
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
            UpstreamJudge(image=args.image, docker=args.docker, protocol=args.bridge_protocol),
            args.output,
            selection={"offline": args.offline, "excluded": excluded},
        )
    elif args.command == "native-reference-scan":
        result = run_native_reference_scan(
            args.cache,
            args.output,
            suite=args.suite,
            image=args.image,
            extraction=args.extraction,
            exception_policy=args.exception_policy,
            task_keys=tuple(args.task),
            include_external=args.include_external,
            docker=args.docker,
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
        if args.protocol_version != "3.3" and (
            args.max_pre_observation_age is not None or args.max_post_observation_delay is not None
        ):
            parser.error("Model-observation timing bounds require protocol 3.3")
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
            evaluation_recipe=args.evaluation_recipe,
            extraction=args.extraction,
            protocol_version=args.protocol_version,
            model_observation_timing=(
                ModelObservationTiming(
                    max_pre_age_seconds=args.max_pre_observation_age
                    if args.max_pre_observation_age is not None
                    else 30.0,
                    max_post_delay_seconds=args.max_post_observation_delay
                    if args.max_post_observation_delay is not None
                    else 120.0,
                )
                if args.protocol_version == "3.3"
                else None
            ),
            parser_image=args.parser_image,
            system_prompt=args.system_prompt.read_text(encoding="utf-8")
            if args.system_prompt
            else None,
        )
        # Exclusive creation preserves an existing experiment instead of silently rewriting it.
        with args.output.open("x", encoding="utf-8") as output:
            output.write(setup.model_dump_json(indent=2) + "\n")
        result = {
            "setup_digest": setup.digest,
            "evaluation_recipe": setup.evaluation_recipe,
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
                "evaluation_recipe": setup.evaluation_recipe,
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
    elif args.command == "native-plan":
        if args.population == "offline_143" and args.task:
            parser.error("The offline_143 population cannot have a custom task selection")
        if args.population == "custom_development" and not args.task:
            parser.error("Custom native cohorts require at least one --task")
        all_tasks = load_suite(args.suite, args.cache)
        selected = set(args.task or ())
        valid = {task_key(task) for task in all_tasks}
        if len(selected) != len(args.task or ()) or selected - valid:
            parser.error("Native task selection must contain unique keys from one pinned suite")
        if args.population == "offline_143":
            selected = {
                task_key(task)
                for task in all_tasks
                if int(task.public.task_id.rsplit("/", 1)[1]) not in EXTERNAL_IDS
            }
        tasks = tuple(task for task in all_tasks if task_key(task) in selected)
        excluded = {
            task_key(task): (
                "external_service"
                if args.population == "offline_143"
                else "out_of_scope_development"
            )
            for task in all_tasks
            if task_key(task) not in selected
        }
        cohort = freeze_native_cohort(
            tasks,
            cache=args.cache,
            suite=args.suite,
            population=args.population,
            image=args.image,
            extraction=args.extraction,
            exception_policy=args.exception_policy,
            label=args.label,
            excluded=excluded,
        )
        model = ModelSpec.model_validate_json(args.model_spec.read_bytes())
        setup = build_native_setup(
            args.name,
            model,
            cohort,
            tasks,
            cache=args.cache,
            repeats=args.repeats,
            system_prompt=args.system_prompt.read_text(encoding="utf-8")
            if args.system_prompt
            else None,
        )
        with args.output.open("x", encoding="utf-8") as output:
            output.write(setup.model_dump_json(indent=2) + "\n")
        result = {
            "setup_digest": setup.digest,
            "track": setup.protocol.track,
            "suite": cohort.suite,
            "population": cohort.population,
            "extraction_policy": cohort.extraction,
            "exception_policy": cohort.exception_policy,
            "planned_samples": len(tasks) * args.repeats,
            "publication_eligible": False,
            "output": str(args.output),
        }
    elif args.command == "native-create":
        setup = NativeCampaignSetup.model_validate_json(args.setup.read_bytes())
        setup.validate_for_run(args.cache, setup.protocol)
        context = execution_context(setup)
        ledger = Ledger(args.ledger)
        try:
            result = {
                "run_id": ledger.create_run(setup.protocol, context),
                "track": setup.protocol.track,
                "suite": setup.cohort.suite,
                "population": setup.cohort.population,
                "extraction_policy": setup.cohort.extraction,
                "exception_policy": setup.cohort.exception_policy,
                "publication_eligible": False,
            }
        finally:
            ledger.close()
    elif args.command == "native-step":
        if not args.ledger.is_file():
            parser.error("Ledger does not exist")
        ledger = Ledger(args.ledger)
        try:
            ledger.verify()
            context = ledger.context(args.run_id)
            setup = NativeCampaignSetup.model_validate(context["setup"])
            validate_host(context)
            setup.validate_for_run(args.cache, ledger.protocol(args.run_id), docker=args.docker)
            transport = Transport(
                setup.protocol.model,
                timeout_seconds=setup.http_timeout,
                max_response_bytes=setup.response_limit,
            )
            try:
                result = NativeCampaign(
                    ledger, args.run_id, setup, args.cache, transport, docker=args.docker
                ).step()
                result["summary"] = ledger.summary(args.run_id)
            finally:
                transport.close()
        finally:
            ledger.close()
    elif args.command == "protected-plan":
        requested = set(args.task)
        reviewed = {f"{args.suite}/{task_id}" for task_id in VALUE_TASKS}
        if len(requested) != len(args.task) or not requested <= reviewed:
            parser.error("Each --task must be a distinct reviewed value task in the selected suite")
        pinned = load_suite(args.suite, args.cache)
        tasks = tuple(
            revised_value_task(source)
            for source in pinned
            if f"{args.suite}/{source.public.task_id}" in requested
        )
        if len(tasks) != len(requested):
            parser.error("Requested protected tasks are missing from the pinned suite")
        excluded = {
            f"{args.suite}/qiskitHumanEval/{number}": (
                "external_service_unqualified"
                if number in EXTERNAL_IDS
                else "unreviewed_or_unsupported"
            )
            for number in range(151)
            if f"{args.suite}/qiskitHumanEval/{number}" not in requested
        }
        cohort = freeze_protected_cohort(
            tasks,
            cache=args.cache,
            suite=args.suite,
            image=args.image,
            label=args.label,
            excluded=excluded,
        )
        model = ModelSpec.model_validate_json(args.model_spec.read_bytes())
        setup = build_protected_setup(
            args.name,
            model,
            cohort,
            tasks,
            cache=args.cache,
            repeats=args.repeats,
            system_prompt=args.system_prompt.read_text(encoding="utf-8")
            if args.system_prompt
            else None,
        )
        with args.output.open("x", encoding="utf-8") as output:
            output.write(setup.model_dump_json(indent=2) + "\n")
        result = {
            "setup_digest": setup.digest,
            "track": setup.protocol.track,
            "suite": cohort.suite,
            "population": cohort.population,
            "planned_samples": len(cohort.task_keys) * args.repeats,
            "excluded": cohort.excluded,
            "publication_eligible": False,
            "output": str(args.output),
        }
    elif args.command == "protected-create":
        setup = ProtectedCampaignSetup.model_validate_json(args.setup.read_bytes())
        setup.validate_for_run(args.cache, setup.protocol)
        context = execution_context(setup)
        ledger = Ledger(args.ledger)
        try:
            result = {
                "run_id": ledger.create_run(setup.protocol, context),
                "track": setup.protocol.track,
                "suite": setup.cohort.suite,
                "population": setup.cohort.population,
                "publication_eligible": False,
            }
        finally:
            ledger.close()
    elif args.command == "protected-step":
        if not args.ledger.is_file():
            parser.error("Ledger does not exist")
        ledger = Ledger(args.ledger)
        try:
            ledger.verify()
            context = ledger.context(args.run_id)
            setup = ProtectedCampaignSetup.model_validate(context["setup"])
            validate_host(context)
            setup.validate_for_run(args.cache, ledger.protocol(args.run_id), docker=args.docker)
            transport = Transport(
                setup.protocol.model,
                timeout_seconds=setup.http_timeout,
                max_response_bytes=setup.response_limit,
            )
            try:
                result = ProtectedCampaign(
                    ledger, args.run_id, setup, args.cache, transport, docker=args.docker
                ).step()
                result["summary"] = ledger.summary(args.run_id)
            finally:
                transport.close()
        finally:
            ledger.close()
    elif args.command == "admission-inventory":
        admission_inventory = build_pending_inventory(args.cache)
        with args.output.open("x", encoding="utf-8") as output:
            output.write(admission_inventory.model_dump_json(indent=2) + "\n")
        result = {
            "inventory_digest": admission_inventory.digest,
            "task_count": len(admission_inventory.cards),
            "pending_cards": sum(
                bool(admission_blockers(card)) for card in admission_inventory.cards
            ),
            "external_service_cards": sum(
                card.external_service for card in admission_inventory.cards
            ),
            "publication_eligible": admission_inventory.publication_eligible,
            "output": str(args.output),
        }
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
