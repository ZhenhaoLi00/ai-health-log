#!/usr/bin/env python3
"""Daily sync: pull Xunji training data into your health log repo.

Configuration (environment variables):
  HEALTH_LOG_REPO      Local clone of your health log repo.
                       Default: the repo containing this script.
  XUNJI_API_KEY_FILE   File holding your Xunji Open API key (chmod 600).
                       Default: ~/.config/xunji/api_key
  HEALTH_LOG_TZ        Your timezone, e.g. America/Chicago.
                       Default: system local time.
  GIT_SSH_COMMAND      Optional custom ssh command (e.g. for a deploy key).

What it does:
- git pull --rebase
- Fetches yesterday + today from Xunji (light read), cached by date
  (a date already fetched today is skipped).
- Saves raw JSON to data/workouts/YYYY-MM-DD.json
- Updates the ## Training section of data/daily/YYYY-MM-DD.md
- Writes a short report to reports/daily/YYYY-MM-DD.md
- Regenerates SUMMARY.md
- Commits + pushes only when something changed.

Rate limits: light reads >= 15s apart (we sleep 16s between calls).
"""
import datetime
import glob
import json
import os
import re
import subprocess
import sys
import time

REPO = os.environ.get(
    "HEALTH_LOG_REPO",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KEY_FILE = os.path.expanduser(os.environ.get(
    "XUNJI_API_KEY_FILE", "~/.config/xunji/api_key"))
TZ = os.environ.get("HEALTH_LOG_TZ", "")
API = "https://trains.xunjiapp.cn/api_trains_for_llm_v2"


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO)


def _date_cmd(offset_days=0):
    base = ["date", "+%F"] if not offset_days else \
        ["date", "-d", f"{offset_days} day", "+%F"]
    env = dict(os.environ)
    if TZ:
        env["TZ"] = TZ
    return subprocess.run(base, capture_output=True, text=True, env=env).stdout.strip()


def today():
    return _date_cmd(0)


def fetch(datestr, key):
    out = os.path.join(REPO, "data", "workouts", f"{datestr}.json")
    if os.path.exists(out):
        mdate = datetime.date.fromtimestamp(os.path.getmtime(out)).isoformat()
        if mdate >= today():
            print(f"skip {datestr} (already fetched today)")
            return out
    time.sleep(16)
    body = json.dumps(
        {"schema_version": "train_open_api_v2", "datestr": datestr,
         "include_full_data": False}
    )
    r = subprocess.run(
        ["curl", "-s", "--compressed", "--max-time", "30", "-X", "POST", API,
         "-H", f"Authorization: Bearer {key}",
         "-H", "Content-Type: application/json",
         "-H", "Accept-Encoding: gzip",
         "-d", body],
        capture_output=True, text=True)
    try:
        data = json.loads(r.stdout)
    except Exception as e:
        print(f"fetch {datestr}: bad response ({e})")
        return None
    if isinstance(data.get("res"), str):
        print(f"fetch {datestr}: API error: {data.get('res')}")
        return None
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"fetched {datestr}")
    return out


def summarize(path):
    with open(path) as f:
        data = json.load(f)
    trains = data.get("res", {}).get("trains", [])
    if not trains:
        return None
    lines = []
    for t in trains:
        title = t.get("title") or "Training"
        parts = []
        for m in t.get("movements", []):
            done = [s for s in m.get("sets", []) if s.get("done")]
            if not done:
                continue
            grp = {}
            for s in done:
                w = s.get("weight") or s.get("weight_kg")
                if not w and s.get("selfWeight"):
                    w = "BW"
                w = str(w or "?")
                reps = str(s.get("reps") or s.get("time") or s.get("duration_s") or "?")
                k = (w, reps)
                grp[k] = grp.get(k, 0) + 1
            desc = ", ".join(
                f"{w}{'kg' if w not in ('BW', '?') else ''}x{r}x{c}"
                for (w, r), c in grp.items())
            parts.append(f"{m.get('name')}: {desc}")
        lines.append(f"- {title}: " + ("; ".join(parts) if parts else "no completed sets"))
    return "\n".join(lines)


def update_daily_md(datestr, training_text):
    path = os.path.join(REPO, "data", "daily", f"{datestr}.md")
    if os.path.exists(path):
        content = open(path).read()
    else:
        content = (f"# {datestr}\n\n## Sleep\n- (None)\n\n## Meals\n- (None)\n\n"
                   f"## Training\n- (None)\n\n## Body metrics\n- (None)\n\n## Notes\n- (None)\n")
    new_section = "## Training\n" + (
        training_text + "\n(source: Xunji API)" if training_text else "- (None)")
    if "## Training" in content:
        content = re.sub(r"## Training\n(?:.*\n)*?(?=## |\Z)", new_section + "\n", content)
    else:
        content = content.rstrip() + "\n\n" + new_section + "\n"
    open(path, "w").write(content)


def write_report(datestr, training_text):
    path = os.path.join(REPO, "reports", "daily", f"{datestr}.md")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    body = (f"# Daily report {datestr}\n\n## Training\n"
            + (training_text or "- No training logged"))
    open(path, "w").write(body + "\n")


def section_items(content, header):
    m = re.search(rf"^## {re.escape(header)}\n((?:.*\n)*?)(?=^## |\Z)", content, re.M)
    if not m:
        return []
    return [l.strip() for l in m.group(1).splitlines()
            if l.strip().startswith("- ") and l.strip() != "- (None)"]


def build_summary():
    daily_files = sorted(glob.glob(os.path.join(REPO, "data", "daily", "*.md")))
    workout_files = sorted(glob.glob(os.path.join(REPO, "data", "workouts", "*.json")))

    per_date_train = {}
    train_days = 0
    total_sets = 0
    for wf in workout_files:
        d = os.path.basename(wf)[:10]
        try:
            data = json.load(open(wf))
        except Exception:
            continue
        trains = data.get("res", {}).get("trains", [])
        if not trains:
            continue
        train_days += 1
        one = []
        for t in trains:
            nsets = sum(1 for m in t.get("movements", [])
                        for s in m.get("sets", []) if s.get("done"))
            total_sets += nsets
            one.append(f"{t.get('title') or 'Training'} ({nsets} sets)")
        per_date_train[d] = "; ".join(one)

    dates = sorted({os.path.basename(f)[:10] for f in daily_files})
    rows = []
    for d in dates[-14:]:
        content = open(os.path.join(REPO, "data", "daily", f"{d}.md")).read()
        tr = per_date_train.get(d, "—")
        meals = section_items(content, "Meals")
        meal_txt = f"{len(meals)} logged" if meals else "—"
        sleep = section_items(content, "Sleep")
        sleep_txt = sleep[0][2:].strip() if sleep else "—"
        if len(sleep_txt) > 60:
            sleep_txt = sleep_txt[:57] + "..."
        rows.append((d, tr, meal_txt, sleep_txt))

    last7 = dates[-7:]
    trained7 = sum(1 for d in last7 if d in per_date_train)

    goal_lines = []
    try:
        prof = open(os.path.join(REPO, "profile.md")).read()
        m = re.search(r"^## Current phase goal\n((?:.*\n)*?)(?=^## |\Z)", prof, re.M)
        if m:
            goal_lines = [l.rstrip() for l in m.group(1).splitlines() if l.strip()]
    except FileNotFoundError:
        pass
    goal_txt = "\n".join(goal_lines) if goal_lines else "- (not filled in yet)"

    L = []
    L.append("# Health Log Summary")
    L.append(f"_Last updated: {today()}_")
    L.append("")
    L.append("## Goals")
    L.append(goal_txt)
    L.append("")
    L.append("## Overall")
    if dates:
        L.append(f"- Days logged: {len(dates)} ({dates[0]} → {dates[-1]})")
    else:
        L.append("- Days logged: 0")
    L.append(f"- Training days: {train_days}")
    L.append(f"- Total completed sets: {total_sets}")
    L.append(f"- Trained {trained7} of last {len(last7)} days")
    L.append("")
    L.append("## Recent days")
    L.append("")
    L.append("| Date | Training | Meals | Sleep |")
    L.append("|------|----------|-------|-------|")
    for d, tr, meals, sleep in rows:
        L.append(f"| {d} | {tr} | {meals} | {sleep} |")
    L.append("")
    L.append("## Where things live")
    L.append("")
    L.append("- Daily logs: `data/daily/`")
    L.append("- Raw training data: `data/workouts/`")
    L.append("- Meal records: `data/meals/`")
    L.append("- Daily reports: `reports/daily/`")
    L.append("")
    open(os.path.join(REPO, "SUMMARY.md"), "w").write("\n".join(L))
    print("SUMMARY.md regenerated")


def main():
    if not os.path.exists(KEY_FILE):
        print(f"API key file not found: {KEY_FILE}\nSee SETUP.md step 3.",
              file=sys.stderr)
        return 1
    key = open(KEY_FILE).read().strip()
    if not key:
        print("empty API key", file=sys.stderr)
        return 1
    r = sh(["git", "pull", "--rebase"])
    print("pull:", (r.stdout.strip() or r.stderr.strip())[:120])
    day = today()
    ok = True
    for d in (_date_cmd(-1), day):
        p = fetch(d, key)
        if not p:
            ok = False
            continue
        t = summarize(p)
        update_daily_md(d, t)
        write_report(d, t)
    build_summary()
    r = sh(["git", "status", "--porcelain"])
    if not r.stdout.strip():
        print("no changes")
        return 0 if ok else 1
    sh(["git", "add", "-A"])
    sh(["git", "commit", "-m", f"Daily sync {day}: Xunji training data"])
    r = sh(["git", "push"])
    out = (r.stdout + r.stderr).strip()
    print("push:", out[-200:] if out else "ok")
    if r.returncode != 0:
        print("PUSH FAILED", file=sys.stderr)
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
