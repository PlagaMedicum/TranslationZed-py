#!/usr/bin/env python3
"""Evaluate mutation-promotion readiness from scheduled CI run artifacts."""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

EPSILON = 1e-9
EXIT_READY = 0
EXIT_NOT_READY = 1
EXIT_INVALID_INPUT = 2


@dataclass(frozen=True, slots=True)
class RunQualification:
    """Represent one workflow-run qualification result."""

    run_id: int
    run_number: int | None
    run_attempt: int | None
    run_created_at: str | None
    run_html_url: str | None
    artifact_name: str
    artifact_state: str
    qualifies: bool
    reasons: list[str]
    mode: str | None
    passed: bool | None
    warned: bool | None
    actionable_total: int | None
    killed_percent: float | None


@dataclass(frozen=True, slots=True)
class PromotionEvaluation:
    """Represent promotion-readiness verdict across scheduled runs."""

    ready: bool
    repo: str
    workflow: str
    branch: str
    event: str
    required_consecutive: int
    min_killed_percent: float
    require_mode: str
    qualifying_tail_streak: int
    total_runs_considered: int
    results: list[RunQualification]


def _require_int(value: Any, *, field: str) -> int:
    """Return validated integer value."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Invalid '{field}': expected integer.")
    return value


def _require_float(value: Any, *, field: str) -> float:
    """Return validated numeric value as float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Invalid '{field}': expected numeric value.")
    return float(value)


def _require_bool(value: Any, *, field: str) -> bool:
    """Return validated boolean value."""
    if not isinstance(value, bool):
        raise ValueError(f"Invalid '{field}': expected boolean.")
    return value


def _github_request_json(*, url: str, token: str) -> dict[str, Any]:
    """Fetch a GitHub API endpoint and parse JSON object payload."""
    request = urllib.request.Request(
        url=url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "translationzed-mutation-promotion-checker",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ValueError(f"GitHub API request failed ({exc.code}) for '{url}'.") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"GitHub API request failed for '{url}': {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"GitHub API returned invalid JSON for '{url}': {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid GitHub API payload for '{url}': expected object.")
    return payload


def _github_download_bytes(*, url: str, token: str) -> bytes:
    """Download binary content from a GitHub API artifact URL."""
    request = urllib.request.Request(
        url=url,
        headers={
            "Accept": "application/octet-stream",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "translationzed-mutation-promotion-checker",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise ValueError(
            f"Artifact download failed ({exc.code}) for '{url}'."
        ) from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Artifact download failed for '{url}': {exc}") from exc


def _fetch_completed_runs(
    *,
    repo: str,
    workflow: str,
    branch: str,
    event: str,
    token: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Fetch latest completed runs for a workflow filtered by branch/event."""
    query = urllib.parse.urlencode(
        {
            "branch": branch,
            "event": event,
            "status": "completed",
            "per_page": str(max(limit, 1)),
        }
    )
    url = (
        f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs?{query}"
    )
    payload = _github_request_json(url=url, token=token)
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise ValueError("Invalid workflow-runs payload: 'workflow_runs' must be a list.")
    validated: list[dict[str, Any]] = []
    for index, value in enumerate(runs):
        if not isinstance(value, dict):
            raise ValueError(f"Invalid workflow-runs payload at index {index}: expected object.")
        validated.append(value)
    return validated


def _fetch_named_artifact(
    *,
    repo: str,
    run_id: int,
    artifact_name: str,
    token: str,
) -> dict[str, Any] | None:
    """Fetch the newest named artifact for one workflow run, if present."""
    url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100"
    payload = _github_request_json(url=url, token=token)
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError(
            f"Invalid artifacts payload for run {run_id}: "
            "'artifacts' must be a list."
        )
    candidates: list[dict[str, Any]] = []
    for index, value in enumerate(artifacts):
        if not isinstance(value, dict):
            raise ValueError(
                f"Invalid artifacts payload for run {run_id} at index {index}: expected object."
            )
        if value.get("name") == artifact_name:
            candidates.append(value)
    if not candidates:
        return None
    candidates.sort(key=lambda artifact: _require_int(artifact.get("id"), field="artifact.id"))
    return candidates[-1]


def _extract_summary_payload(*, zip_bytes: bytes, run_id: int) -> dict[str, Any]:
    """Extract and parse summary JSON payload from an artifact ZIP archive."""
    buffer = io.BytesIO(zip_bytes)
    if not zipfile.is_zipfile(buffer):
        raise ValueError(f"Unreadable artifact archive for run {run_id}: not a ZIP file.")

    buffer.seek(0)
    try:
        with zipfile.ZipFile(buffer) as archive:
            names = sorted(archive.namelist())
            summary_names = [name for name in names if name.endswith("summary.json")]
            if not summary_names:
                raise ValueError(
                    f"Artifact for run {run_id} is missing summary.json payload."
                )
            target_name = summary_names[0]
            raw = archive.read(target_name)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"Unreadable artifact archive for run {run_id}: {exc}") from exc
    except OSError as exc:
        raise ValueError(f"Unable to read artifact archive for run {run_id}: {exc}") from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"Artifact summary payload for run {run_id} is not valid UTF-8."
        ) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Unreadable artifact summary JSON for run {run_id}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(
            f"Invalid artifact summary payload for run {run_id}: expected object."
        )
    return payload


def _evaluate_summary(
    *,
    run: dict[str, Any],
    summary: dict[str, Any],
    artifact_name: str,
    require_mode: str,
    min_killed_percent: float,
) -> RunQualification:
    """Evaluate one summary payload against strict promotion criteria."""
    run_id = _require_int(run.get("id"), field="run.id")
    run_number = run.get("run_number")
    run_attempt = run.get("run_attempt")
    run_created_at = run.get("created_at")
    run_html_url = run.get("html_url")
    if run_number is not None:
        run_number = _require_int(run_number, field="run.run_number")
    if run_attempt is not None:
        run_attempt = _require_int(run_attempt, field="run.run_attempt")
    if run_created_at is not None and not isinstance(run_created_at, str):
        raise ValueError(f"Invalid 'run.created_at' for run {run_id}: expected string.")
    if run_html_url is not None and not isinstance(run_html_url, str):
        raise ValueError(f"Invalid 'run.html_url' for run {run_id}: expected string.")

    mode = summary.get("mode")
    if not isinstance(mode, str):
        raise ValueError(f"Invalid 'mode' in run {run_id} summary payload.")
    passed = _require_bool(summary.get("passed"), field="passed")
    warned = _require_bool(summary.get("warned"), field="warned")

    summary_data = summary.get("summary")
    if not isinstance(summary_data, dict):
        raise ValueError(f"Invalid 'summary' object in run {run_id} summary payload.")
    actionable_total = _require_int(
        summary_data.get("actionable_total"), field="summary.actionable_total"
    )
    killed_percent = _require_float(
        summary_data.get("killed_percent"), field="summary.killed_percent"
    )

    reasons: list[str] = []
    if mode != require_mode:
        reasons.append(f"mode={mode!r} != {require_mode!r}")
    if not passed:
        reasons.append("passed=false")
    if warned:
        reasons.append("warned=true")
    if actionable_total <= 0:
        reasons.append("actionable_total<=0")
    if killed_percent + EPSILON < min_killed_percent:
        reasons.append(
            f"killed_percent={killed_percent:.2f} < {min_killed_percent:.2f}"
        )

    return RunQualification(
        run_id=run_id,
        run_number=run_number,
        run_attempt=run_attempt,
        run_created_at=run_created_at,
        run_html_url=run_html_url,
        artifact_name=artifact_name,
        artifact_state="ok",
        qualifies=not reasons,
        reasons=reasons,
        mode=mode,
        passed=passed,
        warned=warned,
        actionable_total=actionable_total,
        killed_percent=killed_percent,
    )


def _build_missing_artifact_qualification(
    *,
    run: dict[str, Any],
    artifact_name: str,
    artifact_state: str,
    reason: str,
) -> RunQualification:
    """Build non-qualifying result for runs without a usable artifact."""
    run_id = _require_int(run.get("id"), field="run.id")
    run_number = run.get("run_number")
    run_attempt = run.get("run_attempt")
    run_created_at = run.get("created_at")
    run_html_url = run.get("html_url")
    if run_number is not None:
        run_number = _require_int(run_number, field="run.run_number")
    if run_attempt is not None:
        run_attempt = _require_int(run_attempt, field="run.run_attempt")
    if run_created_at is not None and not isinstance(run_created_at, str):
        raise ValueError(f"Invalid 'run.created_at' for run {run_id}: expected string.")
    if run_html_url is not None and not isinstance(run_html_url, str):
        raise ValueError(f"Invalid 'run.html_url' for run {run_id}: expected string.")

    return RunQualification(
        run_id=run_id,
        run_number=run_number,
        run_attempt=run_attempt,
        run_created_at=run_created_at,
        run_html_url=run_html_url,
        artifact_name=artifact_name,
        artifact_state=artifact_state,
        qualifies=False,
        reasons=[reason],
        mode=None,
        passed=None,
        warned=None,
        actionable_total=None,
        killed_percent=None,
    )


def evaluate_promotion_readiness(
    *,
    repo: str,
    workflow: str,
    branch: str,
    event: str,
    artifact_name: str,
    required_consecutive: int,
    min_killed_percent: float,
    require_mode: str,
    token: str,
    work_dir: Path,
) -> PromotionEvaluation:
    """Evaluate promotion readiness from scheduled heavy-run artifacts."""
    if required_consecutive < 1:
        raise ValueError("--required-consecutive must be >= 1.")
    if min_killed_percent < 0:
        raise ValueError("--min-killed-percent must be >= 0.")

    runs = _fetch_completed_runs(
        repo=repo,
        workflow=workflow,
        branch=branch,
        event=event,
        token=token,
        limit=max(required_consecutive, 10),
    )
    selected = runs[:required_consecutive]
    selected.reverse()

    results: list[RunQualification] = []
    for run in selected:
        run_id = _require_int(run.get("id"), field="run.id")
        artifact = _fetch_named_artifact(
            repo=repo,
            run_id=run_id,
            artifact_name=artifact_name,
            token=token,
        )
        if artifact is None:
            results.append(
                _build_missing_artifact_qualification(
                    run=run,
                    artifact_name=artifact_name,
                    artifact_state="missing",
                    reason=f"artifact '{artifact_name}' not found",
                )
            )
            continue

        if _require_bool(artifact.get("expired"), field="artifact.expired"):
            results.append(
                _build_missing_artifact_qualification(
                    run=run,
                    artifact_name=artifact_name,
                    artifact_state="expired",
                    reason=f"artifact '{artifact_name}' expired",
                )
            )
            continue

        archive_url = artifact.get("archive_download_url")
        if not isinstance(archive_url, str) or not archive_url:
            raise ValueError(
                f"Invalid artifact payload for run {run_id}: missing archive URL."
            )
        zip_bytes = _github_download_bytes(url=archive_url, token=token)
        zip_path = work_dir / f"run-{run_id}-{artifact_name}.zip"
        zip_path.write_bytes(zip_bytes)

        summary_payload = _extract_summary_payload(zip_bytes=zip_bytes, run_id=run_id)
        results.append(
            _evaluate_summary(
                run=run,
                summary=summary_payload,
                artifact_name=artifact_name,
                require_mode=require_mode,
                min_killed_percent=min_killed_percent,
            )
        )

    tail_streak = 0
    for result in reversed(results):
        if result.qualifies:
            tail_streak += 1
            continue
        break

    ready = len(results) >= required_consecutive and tail_streak >= required_consecutive
    return PromotionEvaluation(
        ready=ready,
        repo=repo,
        workflow=workflow,
        branch=branch,
        event=event,
        required_consecutive=required_consecutive,
        min_killed_percent=min_killed_percent,
        require_mode=require_mode,
        qualifying_tail_streak=tail_streak,
        total_runs_considered=len(results),
        results=results,
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for CI readiness evaluation."""
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate mutation-promotion readiness from scheduled workflow-run "
            "artifacts in GitHub Actions."
        )
    )
    parser.add_argument("--repo", required=True, help="GitHub repo slug owner/name.")
    parser.add_argument("--workflow", default="ci.yml", help="Workflow file name.")
    parser.add_argument("--branch", required=True, help="Git branch to evaluate.")
    parser.add_argument("--event", default="schedule", help="Workflow event filter.")
    parser.add_argument(
        "--artifact-name",
        default="heavy-mutation-summary",
        help="Artifact name expected on heavy runs.",
    )
    parser.add_argument(
        "--required-consecutive",
        type=int,
        default=2,
        help="Required qualifying tail streak (default: 2).",
    )
    parser.add_argument(
        "--min-killed-percent",
        type=float,
        default=25.0,
        help="Minimum required killed-percent (default: 25).",
    )
    parser.add_argument(
        "--require-mode",
        choices=("warn", "fail", "off"),
        default="fail",
        help="Required score mode for qualification (default: fail).",
    )
    parser.add_argument(
        "--token-env",
        default="GITHUB_TOKEN",
        help="Environment variable name containing GitHub token.",
    )
    parser.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="Optional JSON report output path.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Optional temporary working directory for downloaded artifacts.",
    )
    return parser


def _print_report(evaluation: PromotionEvaluation) -> None:
    """Print concise readiness report."""
    print(
        "mutation promotion readiness: "
        f"ready={evaluation.ready} "
        f"tail_streak={evaluation.qualifying_tail_streak}/"
        f"{evaluation.required_consecutive} "
        f"runs_considered={evaluation.total_runs_considered} "
        f"required_mode={evaluation.require_mode} "
        f"min_killed_percent={evaluation.min_killed_percent:.2f}"
    )
    if evaluation.total_runs_considered < evaluation.required_consecutive:
        print(
            "NOT_READY insufficient completed runs: "
            f"{evaluation.total_runs_considered} < {evaluation.required_consecutive}"
        )
    for result in evaluation.results:
        run_ref = (
            f"run_id={result.run_id} "
            f"run_number={result.run_number} "
            f"attempt={result.run_attempt}"
        )
        if result.qualifies:
            print(
                "OK "
                f"{run_ref} "
                f"mode={result.mode} "
                f"killed_percent={result.killed_percent:.2f} "
                f"actionable_total={result.actionable_total}"
            )
            continue
        print(
            "FAIL "
            f"{run_ref} "
            f"artifact_state={result.artifact_state}: "
            f"{'; '.join(result.reasons)}"
        )


def _write_report_json(path: Path, evaluation: PromotionEvaluation) -> None:
    """Write evaluation report JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(evaluation), ensure_ascii=True, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    """Run CI mutation-promotion readiness evaluation."""
    args = _build_parser().parse_args()
    token = os.getenv(args.token_env, "").strip()
    if not token:
        print(
            f"mutation promotion readiness input error: missing token in {args.token_env}",
            file=sys.stderr,
        )
        return EXIT_INVALID_INPUT

    try:
        if args.work_dir is not None:
            work_dir = args.work_dir.resolve()
            work_dir.mkdir(parents=True, exist_ok=True)
            evaluation = evaluate_promotion_readiness(
                repo=args.repo,
                workflow=args.workflow,
                branch=args.branch,
                event=args.event,
                artifact_name=args.artifact_name,
                required_consecutive=args.required_consecutive,
                min_killed_percent=float(args.min_killed_percent),
                require_mode=str(args.require_mode),
                token=token,
                work_dir=work_dir,
            )
        else:
            with tempfile.TemporaryDirectory(prefix="mutation-promotion-ci-") as temp_dir:
                evaluation = evaluate_promotion_readiness(
                    repo=args.repo,
                    workflow=args.workflow,
                    branch=args.branch,
                    event=args.event,
                    artifact_name=args.artifact_name,
                    required_consecutive=args.required_consecutive,
                    min_killed_percent=float(args.min_killed_percent),
                    require_mode=str(args.require_mode),
                    token=token,
                    work_dir=Path(temp_dir),
                )
    except ValueError as exc:
        print(f"mutation promotion readiness input error: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT

    if args.out_json is not None:
        _write_report_json(args.out_json, evaluation)
    _print_report(evaluation)
    if evaluation.ready:
        return EXIT_READY
    return EXIT_NOT_READY


if __name__ == "__main__":
    raise SystemExit(main())
