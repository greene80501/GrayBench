"""
Command-line interface for graybench.

Provides commands for:
- Running benchmarks
- Managing models and providers
- Viewing and exporting results
- Validation and testing
"""

import asyncio
import json
import sys
import time
from threading import Event
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table

from graybench import __version__
from graybench.config import Config, get_config, PRICING
from graybench.dataset import DatasetLoader, Dataset, Task
from graybench.execution import ExecutionHarness, Outcome
from graybench.storage import ResultStorage, JSONLExporter

# Initialize CLI app
app = typer.Typer(
    name="graybench",
    help="Gray Area Labs Benchmark Suite for Qiskit HumanEval",
    add_completion=False,
    pretty_exceptions_show_locals=False,
)

console = Console()
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


# Sub-command groups
models_app = typer.Typer(help="Manage models and providers", pretty_exceptions_show_locals=False)
results_app = typer.Typer(help="View and export results", pretty_exceptions_show_locals=False)
validate_app = typer.Typer(help="Validation commands", pretty_exceptions_show_locals=False)

app.add_typer(models_app, name="models")
app.add_typer(results_app, name="results")
app.add_typer(validate_app, name="validate")


@app.callback()
def main_callback(
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
):
    """Gray Area Labs Benchmark Suite for Qiskit HumanEval."""
    if version:
        console.print(f"graybench version {__version__}")
        raise typer.Exit()


# ============================================================================
# Models commands
# ============================================================================


@models_app.command("list")
def models_list():
    """List all available models by provider."""
    config = get_config()

    table = Table(title="Available Models")
    table.add_column("Provider", style="cyan")
    table.add_column("Model ID", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Input $/M", justify="right")
    table.add_column("Output $/M", justify="right")

    for provider_name, provider_config in config.providers.items():
        status = "✓ configured" if provider_config.is_configured else "✗ no API key"

        for model in provider_config.models:
            pricing = PRICING.get(provider_name, {}).get(model, {})
            if pricing:
                input_low = pricing.get("input", "?")
                input_high = pricing.get("input_high")
                output_low = pricing.get("output", "?")
                output_high = pricing.get("output_high")
                input_price = f"${input_low} / ${input_high}" if input_high else f"${input_low}"
                output_price = (
                    f"${output_low} / ${output_high}" if output_high else f"${output_low}"
                )
            else:
                input_price = "?"
                output_price = "?"

            table.add_row(
                provider_config.name,
                model,
                status,
                input_price,
                output_price,
            )

    console.print(table)


@models_app.command("check")
def models_check():
    """Check which providers have valid API keys configured."""
    config = get_config()

    console.print("\n[bold]Provider Configuration Status[/bold]\n")

    for provider_name, provider_config in config.providers.items():
        if provider_config.is_configured:
            console.print(f"  [green]✓[/green] {provider_config.name}: API key configured")
        else:
            console.print(
                f"  [red]✗[/red] {provider_config.name}: Missing {provider_config.api_key_env}"
            )

    # Check IBM Quantum
    if config.ibm_quantum_token:
        console.print(f"  [green]✓[/green] IBM Quantum: Token configured")
    else:
        console.print(f"  [yellow]![/yellow] IBM Quantum: Missing IBM_QUANTUM_TOKEN (optional)")

    console.print()


# ============================================================================
# Run commands
# ============================================================================


@app.command("run")
def run_benchmark(
    provider: str = typer.Option(
        ..., "--provider", "-p", help="Provider name (openai, anthropic, etc.)"
    ),
    model: str = typer.Option(..., "--model", "-m", help="Model ID to benchmark"),
    suite: str = typer.Option("normal", "--suite", "-s", help="Dataset suite: 'normal' or 'hard'"),
    workers: int = typer.Option(4, "--workers", "-w", help="Number of concurrent tasks"),
    timeout: int = typer.Option(120, "--timeout", "-t", help="Timeout per task in seconds"),
    max_tokens: int = typer.Option(16384, "--max-tokens", help="Maximum tokens to generate"),
    temperature: float = typer.Option(0.0, "--temperature", help="Sampling temperature"),
    limit: Optional[int] = typer.Option(
        None, "--limit", "-l", help="Limit number of tasks (for testing)"
    ),
    task_ids: Optional[str] = typer.Option(
        None, "--task-ids", help="Comma-separated task IDs to run"
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output directory for results"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be run without executing"
    ),
    preflight: Optional[Path] = typer.Option(
        None, "--preflight", help="Validated reference report; required for live runs"
    ),
    budget: Optional[float] = typer.Option(
        None, "--budget", help="Maximum estimated USD cost for this run", min=0.01
    ),
    reasoning_effort: Optional[str] = typer.Option(
        None, "--reasoning-effort", help="OpenAI reasoning effort: low, medium or high"
    ),
    prompt_profile: str = typer.Option(
        "official", "--prompt-profile", help="official or environment; different comparison tracks"
    ),
):
    """
    Run benchmark on a specific provider/model combination.

    Example:
        graybench run -p openai -m gpt-4o -s normal -w 8
    """
    config = get_config()
    if prompt_profile not in ("official", "environment"):
        raise typer.BadParameter("prompt-profile must be official or environment")
    system_prompt = None
    if prompt_profile == "environment":
        system_prompt = (
            "The execution environment is Python 3.12, Qiskit 2.4.2, "
            "qiskit-aer 0.17.0, and qiskit-ibm-runtime 0.45.0. "
            "Implement the requested task for these versions. Return Python code only."
        )

    # Validate provider
    provider_config = config.get_provider(provider)
    if not provider_config:
        console.print(f"[red]Error:[/red] Unknown provider '{provider}'")
        console.print(f"Available: {', '.join(config.list_all_providers())}")
        raise typer.Exit(1)

    if reasoning_effort is not None:
        if provider != "openai" or reasoning_effort not in ("low", "medium", "high"):
            raise typer.BadParameter("reasoning-effort requires OpenAI and low, medium or high")
        from dataclasses import replace

        provider_config = replace(
            provider_config,
            default_params={**provider_config.default_params, "reasoning_effort": reasoning_effort},
        )

    if not provider_config.is_configured and not dry_run:
        console.print(f"[red]Error:[/red] {provider_config.name} API key not configured")
        console.print(f"Set environment variable: {provider_config.api_key_env}")
        raise typer.Exit(1)

    # Validate model
    if model not in provider_config.models:
        console.print(
            f"[yellow]Warning:[/yellow] Model '{model}' not in known models for {provider}"
        )
        console.print(f"Known models: {', '.join(provider_config.models)}")
        # Exact API snapshot IDs are allowed without an interactive prompt.

    # Load dataset
    console.print(f"\n[bold]Loading {suite} dataset...[/bold]")
    loader = DatasetLoader()
    try:
        dataset = loader.load(suite=suite)
        console.print(f"  Loaded {len(dataset)} tasks")
    except Exception as e:
        console.print(f"[red]Error loading dataset:[/red] {e}")
        raise typer.Exit(1)

    # Filter tasks if specified
    tasks = list(dataset.tasks)

    if task_ids:
        task_id_list = [t.strip() for t in task_ids.split(",")]
        missing = set(task_id_list) - {t.task_id for t in tasks}
        if missing:
            raise typer.BadParameter(f"Unknown task IDs: {sorted(missing)}")
        tasks = [t for t in tasks if t.task_id in task_id_list]
        console.print(f"  Filtered to {len(tasks)} tasks by ID")

    if limit is not None:
        if limit < 1:
            raise typer.BadParameter("limit must be positive")
        tasks = tasks[:limit]
        console.print(f"  Limited to {len(tasks)} tasks")

    if not tasks or workers < 1 or timeout < 1 or max_tokens < 1:
        raise typer.BadParameter("Tasks, workers, timeout and max-tokens must be positive")

    if dry_run:
        console.print(f"\n[bold]Dry run - would execute:[/bold]")
        console.print(f"  Provider: {provider_config.name}")
        console.print(f"  Model: {model}")
        console.print(f"  Suite: {suite}")
        console.print(f"  Tasks: {len(tasks)}")
        console.print(f"  Workers: {workers}")
        console.print(f"  Timeout: {timeout}s")
        raise typer.Exit(0)

    if preflight is None:
        raise typer.BadParameter("Live runs require --preflight from validate canonical --output")
    from graybench.preflight import verify_report

    report = json.loads(preflight.read_text(encoding="utf-8"))
    eligible = set(verify_report(report, dataset))
    if timeout != report.get("timeout"):
        raise typer.BadParameter("Run timeout must match reference preflight timeout")
    if report.get("backend") != "docker":
        raise typer.BadParameter(
            "Live model execution requires a Docker preflight; local reports are reference audits only"
        )
    tasks = [task for task in tasks if task.task_id in eligible]
    if not tasks:
        raise typer.BadParameter("No selected tasks passed reference validation")
    console.print(
        f"Reference-validated coverage: {len(tasks)}/{len(dataset)}; this is an offline subset score."
    )

    # Initialize components
    from graybench.providers import get_adapter

    adapter_kwargs = {"timeout": timeout}
    if provider_config.base_url:
        adapter_kwargs["base_url"] = provider_config.base_url
    adapter = get_adapter(provider, **adapter_kwargs)
    if budget is None:
        raise typer.BadParameter("Live runs require an explicit --budget in USD")
    from graybench.providers import TokenUsage

    reservations = [
        adapter.calculate_cost(
            TokenUsage(
                input_tokens=len(task.prompt.encode("utf-8")) + 4096, output_tokens=max_tokens
            ),
            model,
        )
        for task in tasks
    ]
    if any(cost is None for cost in reservations):
        raise typer.BadParameter(
            "No known cost estimate for this model; verify pricing before running"
        )
    estimated_ceiling = sum(reservations)
    if estimated_ceiling > budget:
        raise typer.BadParameter(
            f"Estimated token-cap cost ${estimated_ceiling:.2f} exceeds budget ${budget:.2f}"
        )
    console.print(f"Estimated token-cap cost: ${estimated_ceiling:.2f}; budget ${budget:.2f}")
    from graybench.execution.container import image_id

    evaluator_image = image_id(report["image"])
    harness = ExecutionHarness(timeout_seconds=timeout, backend="docker", image=evaluator_image)
    storage = ResultStorage()

    # Create run
    run_id = storage.create_run(
        suite=suite,
        provider=provider,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=timeout,
        dataset_version=dataset.version,
        dataset_hash=dataset.dataset_hash,
        manifest={
            "preflight": report["fingerprint"],
            "protocol": "graybench-v2",
            "task_ids": [t.task_id for t in tasks],
            "full_suite": len(tasks) == len(dataset),
            "dataset_size": len(dataset),
            "track": "agent_system" if provider == "graygate" else "single_generation",
            "prompt_policy": (
                "official_verbatim" if prompt_profile == "official" else "environment_declared"
            ),
            "system_prompt": system_prompt,
            "extraction": "fences_or_raw_no_repair",
            "extra_params": provider_config.default_params,
            "workers": workers,
            "execution_backend": "docker",
            "evaluator_image": evaluator_image,
            "evaluator_code": report["evaluator"],
            "budget_usd": budget,
            "estimated_token_cap_cost_usd": estimated_ceiling,
        },
    )

    console.print(f"\n[bold]Starting run {run_id}[/bold]")
    console.print(f"  Provider: {provider_config.name}")
    console.print(f"  Model: {model}")
    console.print(f"  Suite: {suite}")
    console.print(f"  Tasks: {len(tasks)}")
    console.print(f"  Workers: {workers}")
    console.print()

    # Run benchmark
    results = _run_benchmark(
        adapter=adapter,
        harness=harness,
        storage=storage,
        run_id=run_id,
        model=model,
        tasks=tasks,
        workers=workers,
        temperature=temperature,
        max_tokens=max_tokens,
        extra_params=provider_config.default_params,
        system_prompt=system_prompt,
    )

    # Complete run
    storage.complete_run(run_id)

    # Show summary
    scores = storage.get_scores(run_id)
    _print_summary(run_id, scores)

    # Export if output specified
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        exporter = JSONLExporter(storage)
        exporter.export_run(run_id, output_dir)
        console.print(f"\n[green]Results exported to {output_dir}[/green]")


def _run_benchmark(
    adapter,
    harness: ExecutionHarness,
    storage: ResultStorage,
    run_id: str,
    model: str,
    tasks: List[Task],
    workers: int,
    temperature: float,
    max_tokens: int,
    extra_params: Optional[dict[str, Any]] = None,
    system_prompt: Optional[str] = None,
):
    """Run the benchmark with progress tracking."""

    passed = 0
    failed = 0
    extra_params = extra_params or {}
    stop_run = Event()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:

        task_progress = progress.add_task(f"Running {len(tasks)} tasks...", total=len(tasks))

        def process_task(task: Task):
            """Process a single task."""
            from graybench.providers import GenerationRequest, RateLimitError, AuthenticationError
            from graybench.execution import ExecutionResult, Outcome

            if stop_run.is_set():
                return task.task_id, False, Outcome.API_ERROR

            # Create generation request
            request = GenerationRequest(
                prompt=task.prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                extra_params=dict(extra_params),
                system_prompt=system_prompt,
            )

            # One returned generation per task, including empty completions.
            gen_result = None
            rate_limit_attempts = 0
            max_rate_limit_retries = 5
            for _ in range(1):
                try:
                    while True:
                        try:
                            gen_result = adapter.generate(request)
                            break
                        except RateLimitError as e:
                            rate_limit_attempts += 1
                            if rate_limit_attempts > max_rate_limit_retries:
                                raise
                            # Use provider hint if available, otherwise exponential backoff
                            backoff_s = e.retry_after or min(60, 2**rate_limit_attempts)
                            time.sleep(backoff_s)
                except Exception as e:
                    # Account-wide failures invalidate a run; don't charge through the queue.
                    if isinstance(e, AuthenticationError) or any(
                        term in str(e).lower()
                        for term in (
                            "insufficient_quota",
                            "billing",
                            "credit balance",
                            "model_not_found",
                        )
                    ):
                        stop_run.set()
                    # Handle generation error
                    gen_result = None
                    exec_result = ExecutionResult(
                        passed=False,
                        outcome=Outcome.API_ERROR,
                        error_type=type(e).__name__,
                        error_message=str(e),
                    )

                    # Record the attempt
                    storage.record_attempt(
                        run_id=run_id,
                        task_id=task.task_id,
                        prompt=task.prompt,
                        completion="",
                        extracted_code="",
                        extraction_success=False,
                        outcome=exec_result.outcome.value,
                        passed=False,
                        error_type=exec_result.error_type,
                        error_message=exec_result.error_message,
                        stdout="",
                        stderr="",
                        generation_latency_ms=0,
                        execution_time_ms=0,
                        input_tokens=0,
                        output_tokens=0,
                        total_tokens=0,
                        cost_usd=None,
                        raw_response={
                            "usage_status": "unknown_after_api_error",
                            "rate_limit_retries": rate_limit_attempts,
                        },
                    )
                    return task.task_id, False, exec_result.outcome

                # Break if we have a non-empty completion
                if gen_result and gen_result.completion_text and gen_result.completion_text.strip():
                    break

            if gen_result and (
                not gen_result.completion_text or not gen_result.completion_text.strip()
            ):
                gen_result.error = gen_result.error or "Empty completion"

            # Execute and test
            if gen_result.success:
                try:
                    exec_result = harness.execute(task, gen_result.completion_text)
                except Exception as error:
                    exec_result = ExecutionResult(
                        passed=False,
                        outcome=Outcome.ERROR_OTHER,
                        error_type=type(error).__name__,
                        error_message=str(error),
                    )
            else:
                exec_result = ExecutionResult(
                    passed=False,
                    outcome=(
                        Outcome.EMPTY_COMPLETION
                        if not gen_result.completion_text.strip()
                        else Outcome.API_ERROR
                    ),
                    error_message=gen_result.error or "Generation failed",
                )

            # Record the attempt
            storage.record_attempt(
                run_id=run_id,
                task_id=task.task_id,
                prompt=task.prompt,
                completion=gen_result.completion_text if gen_result else "",
                extracted_code=exec_result.extracted_code,
                extraction_success=exec_result.extraction_success,
                outcome=exec_result.outcome.value,
                passed=exec_result.passed,
                error_type=exec_result.error_type,
                error_message=exec_result.error_message,
                stdout=exec_result.stdout,
                stderr=exec_result.stderr,
                generation_latency_ms=gen_result.latency_ms if gen_result else 0,
                execution_time_ms=exec_result.execution_time_ms,
                input_tokens=gen_result.usage.input_tokens if gen_result else 0,
                output_tokens=gen_result.usage.output_tokens if gen_result else 0,
                total_tokens=gen_result.usage.total_tokens if gen_result else 0,
                cost_usd=gen_result.cost_usd if gen_result else 0,
                raw_response=gen_result.raw_response if gen_result else {},
            )

            return task.task_id, exec_result.passed, exec_result.outcome

        # Run tasks with thread pool
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(process_task, task): task for task in tasks}

            for future in as_completed(futures):
                task = futures[future]
                try:
                    task_id, task_passed, outcome = future.result()
                    if task_passed:
                        passed += 1
                    else:
                        failed += 1
                except Exception as e:
                    console.print(f"[red]Error on {task.task_id}:[/red] {e}")
                    failed += 1

                progress.update(task_progress, advance=1)
    if stop_run.is_set():
        raise RuntimeError(
            "Run stopped after an account/model access error; inspect the recorded API error before continuing"
        )

    return {"passed": passed, "failed": failed}


def _print_summary(run_id: str, scores: dict):
    """Print benchmark summary."""
    console.print(f"\n[bold]═══ Run {run_id} Complete ═══[/bold]\n")

    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Pass Rate", f"[green]{scores['pass_rate']*100:.1f}%[/green]")
    table.add_row("Passed", f"{scores['passed']}/{scores['total_tasks']}")
    table.add_row("", "")
    table.add_row("Failed (Test)", str(scores["failed_test"]))
    table.add_row("Failed (Syntax)", str(scores["failed_syntax"]))
    table.add_row("Failed (Import)", str(scores["failed_import"]))
    table.add_row("Failed (Runtime)", str(scores["failed_runtime"]))
    table.add_row("Timeouts", str(scores["timeouts"]))
    table.add_row("Extraction Failed", str(scores["extraction_failed"]))
    table.add_row("", "")
    table.add_row(
        "Total Tokens", f"{scores['total_input_tokens'] + scores['total_output_tokens']:,}"
    )
    table.add_row(
        "Total Cost",
        (f"${scores['total_cost_usd']:.4f}" if scores["total_cost_usd"] is not None else "unknown"),
    )
    table.add_row("Avg Latency", f"{scores['avg_generation_latency_ms']:.0f}ms")

    console.print(table)


@app.command("sweep")
def run_sweep(
    matrix_file: Path = typer.Argument(..., help="Path to matrix YAML file"),
    workers: int = typer.Option(4, "--workers", "-w", help="Number of concurrent tasks"),
    timeout: int = typer.Option(120, "--timeout", "-t", help="Timeout per task"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory"),
):
    """
    Run multiple benchmarks from a matrix configuration.

    Matrix YAML format:
        - suite: normal
          provider: openai
          models: [gpt-4o, gpt-4o-mini]
        - suite: hard
          provider: anthropic
          models: [claude-4.5-sonnet-latest]
    """
    import yaml

    with open(matrix_file) as f:
        matrix = yaml.safe_load(f)

    console.print(f"\n[bold]Running sweep from {matrix_file}[/bold]\n")

    total_runs = sum(len(entry.get("models", [])) for entry in matrix)
    console.print(f"Total runs to execute: {total_runs}\n")

    results = []

    for entry in matrix:
        suite = entry.get("suite", "normal")
        provider = entry["provider"]
        models = entry.get("models", [])

        for model in models:
            console.print(f"\n{'='*60}")
            console.print(f"[bold]Running: {provider}/{model} on {suite}[/bold]")
            console.print("=" * 60)

            try:
                # Invoke run command
                run_benchmark(
                    provider=provider,
                    model=model,
                    suite=suite,
                    workers=workers,
                    timeout=timeout,
                    output_dir=output_dir,
                    max_tokens=entry.get("max_tokens", 16384),
                    temperature=0.0,
                    limit=None,
                    task_ids=None,
                    dry_run=False,
                    preflight=Path(entry["preflight"]) if entry.get("preflight") else None,
                    budget=entry.get("budget"),
                    reasoning_effort=entry.get("reasoning_effort"),
                    prompt_profile=entry.get("prompt_profile", "official"),
                )
                results.append(
                    {
                        "provider": provider,
                        "model": model,
                        "suite": suite,
                        "status": "completed",
                    }
                )
            except Exception as e:
                console.print(f"[red]Run failed:[/red] {e}")
                results.append(
                    {
                        "provider": provider,
                        "model": model,
                        "suite": suite,
                        "status": "failed",
                        "error": str(e),
                    }
                )

    # Summary
    console.print(f"\n\n[bold]═══ Sweep Complete ═══[/bold]\n")
    completed = sum(1 for r in results if r["status"] == "completed")
    console.print(f"Completed: {completed}/{total_runs}")


# ============================================================================
# Results commands
# ============================================================================


@results_app.command("list")
def results_list(
    provider: Optional[str] = typer.Option(None, "--provider", "-p"),
    model: Optional[str] = typer.Option(None, "--model", "-m"),
    suite: Optional[str] = typer.Option(None, "--suite", "-s"),
    limit: int = typer.Option(20, "--limit", "-l"),
):
    """List benchmark runs."""
    storage = ResultStorage()
    runs = storage.list_runs(provider=provider, model=model, suite=suite, limit=limit)

    if not runs:
        console.print("No runs found.")
        return

    table = Table(title=f"Recent Runs (showing {len(runs)})")
    table.add_column("Run ID", style="cyan")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Suite")
    table.add_column("Status")
    table.add_column("Pass Rate", justify="right")
    table.add_column("Created")

    for run in runs:
        scores = storage.get_scores(run["run_id"])
        pass_rate = f"{scores['pass_rate']*100:.1f}%" if scores else "-"

        table.add_row(
            run["run_id"],
            run["provider"],
            run["model"],
            run["suite"],
            run["status"],
            pass_rate,
            run["created_at"][:16],
        )

    console.print(table)


@results_app.command("show")
def results_show(
    run_id: str = typer.Argument(..., help="Run ID to show"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed info"),
):
    """Show details for a specific run."""
    storage = ResultStorage()

    run = storage.get_run(run_id)
    if not run:
        console.print(f"[red]Run {run_id} not found[/red]")
        raise typer.Exit(1)

    scores = storage.get_scores(run_id)

    console.print(f"\n[bold]Run {run_id}[/bold]\n")

    # Run info
    info_table = Table(show_header=False, box=None)
    info_table.add_column("", style="cyan")
    info_table.add_column("")

    info_table.add_row("Provider", run["provider"])
    info_table.add_row("Model", run["model"])
    info_table.add_row("Suite", run["suite"])
    info_table.add_row("Status", run["status"])
    info_table.add_row("Created", run["created_at"])
    if run["completed_at"]:
        info_table.add_row("Completed", run["completed_at"])

    console.print(info_table)

    if scores:
        _print_summary(run_id, scores)

    if verbose:
        # Show failure breakdown
        attempts = storage.get_attempts(run_id)
        failures = [a for a in attempts if not a["passed"]]

        if failures:
            console.print(f"\n[bold]Failed Tasks ({len(failures)})[/bold]\n")

            fail_table = Table()
            fail_table.add_column("Task ID")
            fail_table.add_column("Outcome")
            fail_table.add_column("Error")

            for attempt in failures[:20]:  # Limit to first 20
                fail_table.add_row(
                    attempt["task_id"],
                    attempt["outcome"],
                    (attempt["error_message"] or "")[:50],
                )

            console.print(fail_table)

            if len(failures) > 20:
                console.print(f"... and {len(failures) - 20} more")


@results_app.command("leaderboard")
def results_leaderboard(
    suite: str = typer.Option("normal", "--suite", "-s"),
):
    """Show leaderboard of best results."""
    storage = ResultStorage()
    leaderboard = storage.get_leaderboard(suite)

    if not leaderboard:
        console.print(f"No completed runs for {suite} suite.")
        return

    table = Table(title=f"Leaderboard - {suite.title()} Suite")
    table.add_column("Cohort / run")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Pass Rate", justify="right", style="green")
    table.add_column("Passed", justify="right")
    table.add_column("Cost", justify="right")

    for idx, entry in enumerate(leaderboard, 1):
        table.add_row(
            entry["cohort"] + " / " + entry["run_id"],
            entry["provider"],
            entry["model"],
            f"{entry['pass_rate']*100:.1f}%",
            f"{entry['passed']}/{entry['total_tasks']}",
            (
                f"${entry['total_cost_usd']:.4f}"
                if entry["total_cost_usd"] is not None
                else "unknown"
            ),
        )

    console.print(table)


@results_app.command("export")
def results_export(
    run_id: Optional[str] = typer.Option(None, "--run", "-r", help="Export specific run"),
    output_dir: Path = typer.Option(Path("./exports"), "--output", "-o"),
    format: str = typer.Option("jsonl", "--format", "-f", help="Export format: jsonl, json"),
):
    """Export results to files."""
    storage = ResultStorage()
    exporter = JSONLExporter(storage)

    if format not in ("jsonl", "json"):
        raise typer.BadParameter("format must be jsonl or json")

    output_dir.mkdir(parents=True, exist_ok=True)

    if format == "json":
        runs = [storage.get_run(run_id)] if run_id else storage.list_runs(limit=10000)
        if any(run is None for run in runs):
            raise typer.BadParameter("Unknown run")
        payload = [
            {
                "run": run,
                "attempts": storage.get_attempts(run["run_id"]),
                "scores": storage.get_scores(run["run_id"]),
            }
            for run in runs
        ]
        (output_dir / "runs.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    elif run_id:
        exporter.export_run(run_id, output_dir)
        console.print(f"[green]Exported run {run_id} to {output_dir}[/green]")
    else:
        exporter.export_all(output_dir)
        console.print(f"[green]Exported all runs to {output_dir}[/green]")

    # Also export leaderboards
    for suite in ["normal", "hard"]:
        exporter.export_leaderboard(output_dir / f"leaderboard_{suite}.json", suite)
    console.print(f"[green]Exported leaderboards[/green]")


@results_app.command("delete")
def results_delete(
    run_id: str = typer.Argument(..., help="Run ID(s) to delete (comma-separated allowed)"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Delete one or more runs and their results."""
    storage = ResultStorage()
    run_ids = [rid.strip() for rid in run_id.split(",") if rid.strip()]

    if not run_ids:
        console.print("[red]No run IDs provided[/red]")
        raise typer.Exit(1)

    missing = []
    for rid in run_ids:
        run = storage.get_run(rid)
        if not run:
            missing.append(rid)
            continue

        if not force:
            if not typer.confirm(f"Delete run {rid} ({run['provider']}/{run['model']})?"):
                continue

        storage.delete_run(rid)
        console.print(f"[green]Deleted run {rid}[/green]")

    if missing:
        console.print(f"[yellow]Run(s) not found:[/yellow] {', '.join(missing)}")


@results_app.command("rescore")
def results_rescore(
    run_id: str = typer.Argument(...),
    preflight: Path = typer.Option(..., "--preflight"),
    output: Path = typer.Option(..., "--output", "-o"),
    workers: int = typer.Option(4, "--workers", min=1),
):
    """Score saved answers in a newly validated evaluator; never generate or overwrite answers."""
    from graybench.rescore import rescore_run

    report = rescore_run(
        ResultStorage(), run_id, json.loads(preflight.read_text(encoding="utf-8")), workers
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    console.print(
        f"Rescored {report['passed']}/{report['total_tasks']}; no new API calls. Report: {output}"
    )


# ============================================================================
# Validate commands
# ============================================================================


@validate_app.command("canonical")
def validate_canonical(
    suite: str = typer.Option("normal", "--suite", "-s"),
    workers: int = typer.Option(4, "--workers", "-w", min=1),
    limit: Optional[int] = typer.Option(None, "--limit", "-l", min=1),
    output: Path = typer.Option(Path("data/preflight.json"), "--output", "-o"),
    backend: str = typer.Option(
        "local", "--backend", help="local for reference audits; docker for live runs"
    ),
):
    """Validate official references before model generation; never modify tests to fit outputs."""
    from graybench.preflight import validate_dataset

    dataset = DatasetLoader().load(suite)
    if limit is not None:
        dataset = Dataset(dataset.tasks[:limit], dataset.suite, dataset.version, dataset.source)
    if backend not in ("local", "docker"):
        raise typer.BadParameter("backend must be local or docker")
    report = validate_dataset(dataset, workers=workers, backend=backend)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    console.print(f"Reference validation: {len(report['task_ids'])}/{len(dataset)} passed")
    for result in report["results"]:
        if not result["passed"]:
            console.print(
                f"  {result['task_id']}: {result['outcome']} - {result.get('error_message', '')}"
            )
    console.print(f"Report saved: {output}")
    if len(report["task_ids"]) != len(dataset):
        raise typer.Exit(1)


@validate_app.command("imports")
def validate_imports(
    suite: str = typer.Option("normal", "--suite", "-s"),
):
    """Analyze required imports across all tasks."""
    loader = DatasetLoader()
    dataset = loader.load(suite=suite)

    imports = loader.analyze_imports(dataset)

    table = Table(title=f"Import Analysis - {suite.title()} Suite")
    table.add_column("Module", style="cyan")
    table.add_column("Count", justify="right")

    for module, count in imports.items():
        table.add_row(module, str(count))

    console.print(table)


@validate_app.command("environment")
def validate_environment():
    """Check environment configuration."""
    console.print("\n[bold]Environment Check[/bold]\n")

    # Python version
    console.print(f"  Python: {sys.version}")

    # Check Qiskit
    try:
        import qiskit

        console.print(f"  [green]✓[/green] Qiskit: {qiskit.__version__}")
    except ImportError:
        console.print(f"  [red]✗[/red] Qiskit: Not installed")

    # Check Qiskit Aer
    try:
        import qiskit_aer

        console.print(f"  [green]✓[/green] Qiskit Aer: {qiskit_aer.__version__}")
    except ImportError:
        console.print(f"  [red]✗[/red] Qiskit Aer: Not installed")

    # Check Qiskit IBM Runtime
    try:
        import qiskit_ibm_runtime

        console.print(f"  [green]✓[/green] Qiskit IBM Runtime: {qiskit_ibm_runtime.__version__}")
    except ImportError:
        console.print(f"  [red]✗[/red] Qiskit IBM Runtime: Not installed")

    # Check API keys
    console.print("\n[bold]API Keys[/bold]\n")
    models_check()


# ============================================================================
# Dataset commands
# ============================================================================


@app.command("dataset")
def dataset_info(
    suite: str = typer.Option("normal", "--suite", "-s"),
):
    """Show dataset information."""
    loader = DatasetLoader()
    dataset = loader.load(suite=suite)

    console.print(f"\n[bold]Dataset: {dataset.name}[/bold]\n")
    console.print(f"  Suite: {dataset.suite}")
    console.print(f"  Tasks: {len(dataset)}")
    console.print(f"  Version: {dataset.version}")
    console.print(f"  Source: {dataset.source}")
    console.print(f"  Hash: {dataset.dataset_hash}")

    # Difficulty distribution
    dist = loader.get_difficulty_distribution(dataset)
    if dist:
        console.print(f"\n[bold]Difficulty Distribution[/bold]")
        for level, count in sorted(dist.items()):
            console.print(f"  {level}: {count}")


if __name__ == "__main__":
    app()
