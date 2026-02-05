"""
Export utilities for benchmark results.

Supports:
- JSONL export for data exchange
- JSON export for leaderboards
- CSV export for analysis
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from graybench.storage.database import Database
from graybench.execution.outcomes import Outcome


def _json_serializer(obj):
    """JSON serializer for non-standard types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Outcome):
        return obj.value
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    return str(obj)


class JSONLExporter:
    """Export results to JSONL format."""
    
    def __init__(self, storage: Database):
        self.storage = storage
    
    def export_run(self, run_id: str, output_dir: Path):
        """Export a single run to JSONL files."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Export run metadata
        run = self.storage.get_run(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")
        
        with open(output_dir / f"{run_id}_run.jsonl", "w") as f:
            f.write(json.dumps(run, default=_json_serializer) + "\n")
        
        # Export attempts
        attempts = self.storage.get_attempts(run_id)
        with open(output_dir / f"{run_id}_attempts.jsonl", "w") as f:
            for attempt in attempts:
                f.write(json.dumps(attempt, default=_json_serializer) + "\n")
        
        # Export scores
        scores = self.storage.get_scores(run_id)
        if scores:
            with open(output_dir / f"{run_id}_scores.jsonl", "w") as f:
                f.write(json.dumps(scores, default=_json_serializer) + "\n")
    
    def export_all(self, output_dir: Path):
        """Export all runs to JSONL files."""
        runs = self.storage.list_runs(limit=10000)
        for run in runs:
            self.export_run(run['run_id'], output_dir)
    
    def export_leaderboard(self, output_path: Path, suite: str = "normal"):
        """Export leaderboard to JSON."""
        leaderboard = self.storage.get_leaderboard(suite)
        with open(output_path, "w") as f:
            json.dump(leaderboard, f, indent=2, default=_json_serializer)


class CSVExporter:
    """Export results to CSV format for analysis."""
    
    def __init__(self, storage: Database):
        self.storage = storage
    
    def export_attempts(self, run_id: str, output_path: Path):
        """Export attempts for a run to CSV."""
        attempts = self.storage.get_attempts(run_id)
        if not attempts:
            return
        
        # Get all unique keys
        keys = set()
        for attempt in attempts:
            keys.update(attempt.keys())
        keys = sorted(keys)
        
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for attempt in attempts:
                writer.writerow(attempt)
    
    def export_summary(self, output_path: Path, suite: Optional[str] = None):
        """Export summary of all runs to CSV."""
        runs = self.storage.list_runs(suite=suite, limit=10000)
        
        if not runs:
            return
        
        fieldnames = [
            "run_id", "created_at", "suite", "provider", "model",
            "pass_rate", "passed", "total_tasks", "total_cost_usd",
            "status"
        ]
        
        with open(output_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for run in runs:
                scores = self.storage.get_scores(run["run_id"])
                row = {
                    "run_id": run["run_id"],
                    "created_at": run["created_at"],
                    "suite": run["suite"],
                    "provider": run["provider"],
                    "model": run["model"],
                    "pass_rate": scores["pass_rate"] if scores else None,
                    "passed": scores["passed"] if scores else None,
                    "total_tasks": scores["total_tasks"] if scores else None,
                    "total_cost_usd": scores["total_cost_usd"] if scores else None,
                    "status": run["status"],
                }
                writer.writerow(row)


class WebsiteExporter:
    """Export results in a format suitable for website display."""
    
    def __init__(self, storage: Database):
        self.storage = storage
    
    def export_website_data(self, output_dir: Path):
        """Export all data needed for a website leaderboard."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Export leaderboards for both suites
        for suite in ["normal", "hard"]:
            leaderboard = self.storage.get_leaderboard(suite)
            
            # Format for website
            website_data = {
                "suite": suite,
                "updated_at": datetime.utcnow().isoformat(),
                "entries": [],
            }
            
            for idx, entry in enumerate(leaderboard, 1):
                website_data["entries"].append({
                    "rank": idx,
                    "provider": entry["provider"],
                    "model": entry["model"],
                    "pass_rate": round(entry["pass_rate"] * 100, 2),
                    "passed": entry["passed"],
                    "total": entry["total_tasks"],
                    "cost_usd": round(entry["total_cost_usd"], 4) if entry["total_cost_usd"] else 0,
                    "run_id": entry["run_id"],
                    "date": entry["created_at"],
                })
            
            with open(output_dir / f"leaderboard_{suite}.json", "w") as f:
                json.dump(website_data, f, indent=2)
        
        # Export run metadata index
        runs = self.storage.list_runs(limit=1000)
        runs_index = []
        for run in runs:
            scores = self.storage.get_scores(run["run_id"])
            runs_index.append({
                "run_id": run["run_id"],
                "suite": run["suite"],
                "provider": run["provider"],
                "model": run["model"],
                "status": run["status"],
                "created_at": run["created_at"],
                "pass_rate": scores["pass_rate"] if scores else None,
            })
        
        with open(output_dir / "runs_index.json", "w") as f:
            json.dump(runs_index, f, indent=2)
