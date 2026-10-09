#!/usr/bin/env python3
"""Sync SynFit workouts into a private, AI-readable health-log repository.

Only the fenced SynFit block inside a daily Training section is managed by
this script. User-authored notes and other sections are preserved.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import re
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

REPO = Path(os.environ.get("HEALTH_LOG_REPO", Path(__file__).resolve().parent.parent)).expanduser().resolve()
KEY_FILE = Path(os.environ.get("XUNJI_API_KEY_FILE", "~/.config/xunji/api_key")).expanduser()
TIMEZONE = os.environ.get("HEALTH_LOG_TZ", "")
API = "https://trains.xunjiapp.cn/api_trains_for_llm_v2"  # SynFit legacy API hostname
START_MARKER = "<!-- BEGIN XUNJI SYNC -->"
END_MARKER = "<!-- END XUNJI SYNC -->"
TRAINING_SECTION = re.compile(r"(?ms)^## Training\n.*?(?=^## |\Z)")


def local_now() -> dt.datetime:
    """Use a single timezone for dates and cache timestamps."""
    return dt.datetime.now(ZoneInfo(TIMEZONE)) if TIMEZONE else dt.datetime.now().astimezone()


def today() -> dt.date:
    return local_now().date()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=".health-log-", delete=False) as f:
            temp_name = f.name
            f.write(content)
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def validate_response(data: object) -> dict:
    """Reject malformed/error API responses before they enter the cache."""
    if not isinstance(data, dict):
        raise ValueError("response must be a JSON object")
    if data.get("success") is False:
        raise ValueError("API returned success=false")
    result = data.get("res")
    if not isinstance(result, dict) or not isinstance(result.get("trains"), list):
        raise ValueError("response must contain res.trains (list)")
    return data


def cache_metadata_path(day: dt.date) -> Path:
    return REPO / "data" / "workouts" / f"{day.isoformat()}.meta.json"


def cache_is_fresh(day: dt.date) -> bool:
    """Use explicit fetch time, not Git checkout / file modification time."""
    dest = REPO / "data" / "workouts" / f"{day.isoformat()}.json"
    metadata_file = cache_metadata_path(day)
    if not dest.is_file() or not metadata_file.is_file():
        return False
    try:
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        fetched_at = dt.datetime.fromisoformat(metadata["fetched_at"])
        if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
            return False
        if metadata.get("date") != day.isoformat():
            return False
        if fetched_at.astimezone(local_now().tzinfo).date() != today():
            return False
        validate_response(json.loads(dest.read_text(encoding="utf-8")))
        return True
    except (OSError, ValueError, TypeError, KeyError):
        return False


def fetch_workouts(day: dt.date, key: str, force: bool = False) -> Path:
    dest = REPO / "data" / "workouts" / f"{day.isoformat()}.json"
    if not force and cache_is_fresh(day):
        print(f"cached {day}")
        return dest

    request_body = json.dumps({
        "schema_version": "train_open_api_v2",
        "datestr": day.isoformat(),
        "include_full_data": False,
    }).encode("utf-8")
    request = Request(API, data=request_body, method="POST", headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    })
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            if response.headers.get("Content-Encoding", "").lower() == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            data = validate_response(json.loads(raw.decode("utf-8")))
    except (HTTPError, URLError, OSError, ValueError, UnicodeError) as exc:
        raise RuntimeError(f"SynFit fetch failed for {day}: {type(exc).__name__}") from None

    # Write the raw API record first; a missing metadata file forces a
    # re-fetch rather than accepting a partially updated cache as fresh.
    atomic_write(dest, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    metadata = {
        "date": day.isoformat(),
        "fetched_at": local_now().astimezone(dt.timezone.utc).isoformat(),
        "source": "SynFit",
    }
    atomic_write(cache_metadata_path(day), json.dumps(metadata, indent=2) + "\n")
    print(f"fetched {day}")
    return dest

def completed_sets(train: dict) -> int:
    return sum(1 for move in train.get("movements", [])
               for item in move.get("sets", []) if item.get("done"))


def summarize_workouts(path: Path) -> str | None:
    trains = validate_response(json.loads(path.read_text(encoding="utf-8")))["res"]["trains"]
    if not trains:
        return None
    lines = []
    for train in trains:
        parts = []
        for move in train.get("movements", []):
            groups: dict[tuple[str, str], int] = {}
            for item in move.get("sets", []):
                if not item.get("done"):
                    continue
                weight = item.get("weight")
                if weight is None:
                    weight = item.get("weight_kg")
                w = "BW" if weight is None and item.get("selfWeight") else (
                    "?" if weight is None else f"{weight}kg")
                reps = next((item[k] for k in ("reps", "time", "duration_s")
                             if item.get(k) is not None), "?")
                identity = (str(w), str(reps))
                groups[identity] = groups.get(identity, 0) + 1
            if groups:
                desc = ", ".join(f"{w} x {reps} x {count}"
                                 for (w, reps), count in groups.items())
                parts.append(f"{move.get('name') or 'Movement'}: {desc}")
        lines.append(f"- {train.get('title') or 'Training'}: " +
                     ("; ".join(parts) if parts else "no completed sets"))
    return "\n".join(lines)


def update_daily(day: dt.date, training_text: str | None) -> None:
    path = REPO / "data" / "daily" / f"{day.isoformat()}.md"
    content = (path.read_text(encoding="utf-8") if path.exists() else
               f"# {day}\n\n## Sleep\n- (None)\n\n## Meals\n- (None)\n\n"
               "## Training\n\n## Body metrics\n- (None)\n\n## Notes\n- (None)\n")
    managed = f"{START_MARKER}\n{training_text or '- No training logged'}\n{END_MARKER}"
    match = TRAINING_SECTION.search(content)
    if match:
        section = match.group()
        body = section[len("## Training\n"):]
        if body.count(START_MARKER) != body.count(END_MARKER) or body.count(START_MARKER) > 1:
            raise ValueError(f"invalid managed markers in {path}")
        if START_MARKER in body:
            body = re.sub(re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
                          lambda _: managed, body, count=1, flags=re.S)
        else:
            if body.strip() == "- (None)":
                body = ""
            body = body.rstrip() + "\n\n" + managed
        replacement = "## Training\n" + body.strip("\n") + "\n\n"
        content = content[:match.start()] + replacement + content[match.end():]
    else:
        content = content.rstrip() + "\n\n## Training\n" + managed + "\n"
    atomic_write(path, content)


def write_report(day: dt.date, training_text: str | None) -> None:
    atomic_write(REPO / "reports" / "daily" / f"{day.isoformat()}.md",
                 f"# Daily report {day}\n\n## Training\n" +
                 (training_text or "- No training logged") + "\n")


def section_items(content: str, header: str) -> list[str]:
    match = re.search(rf"(?ms)^## {re.escape(header)}\n(.*?)(?=^## |\Z)", content)
    return [line.strip() for line in match.group(1).splitlines()
            if line.strip().startswith("- ") and line.strip() != "- (None)"] if match else []


def escape_md(text: object) -> str:
    return str(text).replace("|", r"\|").replace("\n", " ")


def build_summary(as_of: dt.date | None = None) -> None:
    as_of = as_of or today()
    workout_files = sorted((REPO / "data" / "workouts").glob("????-??-??.json"))
    daily_files = sorted((REPO / "data" / "daily").glob("*.md"))
    training_by_day: dict[str, str] = {}
    sets_count = 0
    for file in workout_files:
        try:
            trains = validate_response(json.loads(file.read_text(encoding="utf-8")))["res"]["trains"]
        except (ValueError, OSError):
            continue
        if not trains:
            continue
        sets_count += sum(completed_sets(t) for t in trains)
        training_by_day[file.stem] = "; ".join(
            f"{t.get('title') or 'Training'} ({completed_sets(t)} sets)" for t in trains)

    dates = sorted(file.stem for file in daily_files)
    last_7 = [(as_of - dt.timedelta(days=i)).isoformat() for i in range(7)]
    trained_7 = sum(d in training_by_day for d in last_7)
    profile = REPO / "profile.md"
    goal_text = "- (not filled in yet)"
    if profile.exists():
        goals = re.search(r"(?ms)^## Current phase goal\n(.*?)(?=^## |\Z)",
                          profile.read_text(encoding="utf-8"))
        if goals and goals.group(1).strip():
            goal_text = goals.group(1).strip()

    lines = [
        "# Health Log Summary",
        f"_Last updated: {as_of.isoformat()}_",
        "",
        "## Goals",
        goal_text, "",
        "## Overall",
        f"- Days logged: {len(dates)}" +
        (f" ({dates[0]} → {dates[-1]})" if dates else ""),
        f"- Training days: {len(training_by_day)}",
        f"- Total completed sets: {sets_count}",
        f"- Trained {trained_7} of the last 7 calendar days",
        "",
        "## Recent days", "",
        "| Date | Training | Meals | Sleep |",
        "|------|----------|-------|-------|",
    ]
    for day in dates[-14:]:
        day_text = (REPO / "data" / "daily" / f"{day}.md").read_text(encoding="utf-8")
        meals = section_items(day_text, "Meals")
        sleep = section_items(day_text, "Sleep")
        sleep_info = sleep[0][2:].strip()[:60] if sleep else "—"
        meals_info = f"{len(meals)} logged" if meals else "—"
        lines.append(f"| {day} | {escape_md(training_by_day.get(day, '—'))} | "
                     f"{meals_info} | {escape_md(sleep_info)} |")
    lines += [
        "",
        "## Where things live", "",
        "- Daily logs: data/daily/",
        "- Raw training data: data/workouts/",
        "- Meal records: data/meals/",
        "- Daily reports: reports/daily/",
        "",
    ]
    atomic_write(REPO / "SUMMARY.md", "\n".join(lines))
    print("SUMMARY.md regenerated")


def git(*args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise RuntimeError(f"git {' '.join(args)} failed: {detail[-1] if detail else result.returncode}")
    return result


def parse_github_remote(remote: str) -> str:
    """Accept GitHub HTTPS/SSH remotes only; return owner/repo."""
    remote = remote.strip()
    if remote.startswith("git@github.com:"):
        path = remote[len("git@github.com:"):]
    elif remote.startswith("ssh://git@github.com/"):
        path = remote[len("ssh://git@github.com/"):]
    else:
        parsed = urlsplit(remote)
        if (parsed.scheme != "https" or parsed.hostname != "github.com"
                or parsed.username or parsed.password or parsed.port is not None):
            raise RuntimeError("Push remote must be a GitHub HTTPS or SSH URL")
        path = parsed.path.lstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", path):
        raise RuntimeError("Cannot identify GitHub repository from push remote")
    return path


def github_api_token() -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token.strip()
    if shutil.which("gh"):
        result = subprocess.run(["gh", "auth", "token"], capture_output=True,
                                text=True, timeout=15)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    raise RuntimeError(
        "Private repository visibility cannot be verified. Authenticate "
        "GitHub CLI (gh auth login) or provide GH_TOKEN/GITHUB_TOKEN "
        "with access to the private repository. No push attempted."
    )


def assert_private_push_remote() -> None:
    """Fail closed unless every origin push URL is confirmed private by GitHub."""
    remotes = git("remote", "get-url", "--push", "--all", "origin").stdout.splitlines()
    if not remotes:
        raise RuntimeError("No GitHub origin push URL configured; refusing sync")
    names = [parse_github_remote(url) for url in remotes]
    token = github_api_token()
    for name in names:
        request = Request(f"https://api.github.com/repos/{name}", headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "ai-health-log-sync",
        })
        try:
            with urlopen(request, timeout=15) as response:
                metadata = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, OSError, ValueError, UnicodeError):
            raise RuntimeError(
                f"Cannot verify that GitHub push destination {name} is private; "
                "check GitHub authentication/network access. No push attempted."
            ) from None
        if not isinstance(metadata, dict) or metadata.get("private") is not True:
            raise RuntimeError(
                f"Refusing to push health data: GitHub repository {name} "
                "is public or its visibility is unverified."
            )
        print(f"verified private GitHub push destination: {name}")

def sync_git_pull() -> None:
    if git("status", "--porcelain").stdout.strip():
        raise RuntimeError("working tree is not clean; refusing to overwrite local changes")
    git("pull", "--ff-only")


def sync_git_push(day: dt.date) -> None:
    # Recheck immediately before staging/committing in case remote changed.
    assert_private_push_remote()
    git("add", "-A", "--", "data/daily", "data/workouts", "reports/daily", "SUMMARY.md")
    if not git("diff", "--cached", "--name-only").stdout.strip():
        print("no changes")
        return
    git("commit", "-m", f"Daily sync {day}: SynFit training data")
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
    git("push", "origin", f"HEAD:refs/heads/{branch}")

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force-refresh", action="store_true",
                        help="Refetch workouts even if cached today")
    parser.add_argument("--no-git", action="store_true",
                        help="Update local files without git pull/commit/push")
    args = parser.parse_args(argv)
    try:
        if not KEY_FILE.is_file():
            raise RuntimeError(f"API key file not found: {KEY_FILE}")
        key = KEY_FILE.read_text(encoding="utf-8").strip()
        if not key:
            raise RuntimeError("SynFit API key file is empty")
        if not args.no_git:
            assert_private_push_remote()  # before touching personal files
            sync_git_pull()
        day = today()
        fetch_days = [day - dt.timedelta(days=1), day]
        ok = True
        for index, d in enumerate(fetch_days):
            # 16s between potential API reads (Xunji light-read limit: 15s).
            if index:
                time.sleep(16)
            try:
                raw = fetch_workouts(d, key, force=args.force_refresh)
                summary = summarize_workouts(raw)
                update_daily(d, summary)
                write_report(d, summary)
            except (RuntimeError, ValueError, OSError) as exc:
                print(f"WARNING: skipped {d}: {exc}", file=sys.stderr)
                ok = False
        build_summary(day)
        # Never publish a partial sync.
        if not ok:
            print("sync incomplete; no git commit/push", file=sys.stderr)
            return 1
        if not args.no_git:
            sync_git_push(day)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
