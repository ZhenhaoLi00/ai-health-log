---
name: health-log-coach
description: Use this skill when the user asks an AI assistant to log meals or workouts, review sleep and body metrics, produce a daily or weekly health summary, suggest a training progression, or build a personal health-tracking workflow from a private AI Health Log repository.
license: MIT
compatibility: Read/write access to a local private health-log checkout; optional SynFit and health-data connectors. No network or health credentials required for read-only reports.
---

# Health Log Coach

Make personal health tracking repeatable and portable across AI assistants.
This is a task workflow, not a standalone service or clinical protocol.

The primary repository rules are in the root AGENTS.md. If those rules and this
skill differ, follow the more restrictive privacy and data-integrity rule.

## When to activate

Use for:
- Daily check-ins and end-of-day reports about sleep, food, training, weight.
- Logging a meal from notes or before/after meal photographs.
- Reviewing completed workouts and suggesting the next training session.
- Weekly trends, coverage and adherence reviews.
- Helping the user understand or improve their AI-assisted health-data workflow.

Do not run daily sync, install software, schedule recurring tasks, export data or
write to a third-party API solely because this skill is available. Do so only
when the user requests it and the required access/confirmation is available.

## 1. Determine the working context

1. Verify the current directory is the user's PRIVATE health-log checkout.
   The public ai-health-log template is documentation/code only. Do not add
   real personal health records to it.
2. Read README.md, AGENTS.md, profile.md, and the relevant date(s) in
   data/daily/. Read SUMMARY.md for orientation, but prefer dated raw records
   over generated summaries when numbers disagree.
3. Identify which sources actually exist: SynFit under data/workouts/,
   user-entered meals under data/meals/, device-derived metrics under
   data/metrics/, and sleep in data/daily/. Do not assume an integration is
   configured because README mentions it.
4. If repository files are inaccessible, ask for the relevant records or
   permissions. Do not fabricate a log or imply that data was synchronized.
5. Use the timezone in the user's profile/configuration where available.
   Otherwise ask or state what date/time assumption is being used.

## 2. Log observations without inventing measurements

Apply to EVERY observation:
- Keep an ISO date; include local time/timezone when available.
- Name its source (user, SynFit, Apple Health, wearable, food label, AI estimate).
- Keep units explicit: kg, g, kcal, minutes, hours, sets and reps.
- Mark estimates with an explicit "estimated" tag, along with key assumptions.
- Distinguish "not logged" from "0", "no training", "did not eat" or "slept 0h".
- Preserve the original evidence or reference and the user's corrections.

### Meals (photo or text)
- A before-and-after photo pair can help estimate how much was eaten.
  Ask which dishes, sauces, beverages or shared portions were consumed when
  the photo is ambiguous. A single photo is still useful with lower certainty.
- Estimate portions, calories and protein as ranges when uncertain. Do not
  describe image-based estimates as exact calorimetry.
- When a nutrition label or weighed ingredient exists, prefer its measured
  values over an image estimate. Avoid double-counting leftovers or snacks.
- Propose a record under data/meals/ with date, meal type/time, components,
  source, kcal/protein estimate and assumptions. Link it from the daily log
  without duplicating the same meal.

### Training (SynFit, notes or video)
- Prefer recorded SynFit sets, reps and loads as the workout source of truth.
  The script-owned data/workouts/ JSON and the legacy XUNJI SYNC block are
  managed data; never rewrite them manually.
- A video may help discuss technique, but do not infer an exact weight,
  repetition count, heart rate or completed exercise when not observable.
  Treat form feedback as tentative, not a substitute for a qualified coach.
- For progression, compare at least two relevant sessions, completed sets,
  repetition range, effort (if available) and recovery feedback. Suggest
  gradual changes only when evidence supports them; otherwise recommend
  holding steady and collecting more data.
- Distinguish strength training from other activity sources; avoid counting
  the same session twice if it appears in a wearable and SynFit.

### Sleep and body metrics
- Record sleep duration and measurement source; interpret sleep stages from
  consumer wearables cautiously.
- For weight trends, prefer comparable conditions and a rolling average
  rather than a single day's fluctuations.
- Never infer body-fat percentage, laboratory results or diagnosis from photos.

## 3. Daily review (on user request)

Summarize:
1. Coverage: which of meals, sleep, training, body metrics are available.
2. Observations: numbers with units, source, timing and estimate markers.
3. Goal comparison: use profile.md goals only if user has actually set them.
4. One to three actionable next steps, clearly separated from observations.
5. Uncertainty and missing information that may change the recommendation.

Suggested human-readable format:

~~~markdown
# Daily Health Review — YYYY-MM-DD
## Data coverage
- Meals: recorded / incomplete / unavailable
- Sleep: recorded / unavailable
- Training: recorded / unavailable
- Body metrics: recorded / unavailable

## Observations
- [measurement or explicitly labeled estimate, unit, source]

## Against my goals
- [use targets from profile.md; do not invent targets]

## Next steps
- [specific, achievable actions]

## Notes and uncertainty
- [what is missing or approximate]
~~~

If saving a report, propose reports/daily/YYYY-MM-DD.md and check whether a
script or another assistant owns that file. Never overwrite another writer's
output silently. Reports can be advisory without mutating the repository.

## 4. Weekly review (on user request)

Use the last seven CALENDAR days, not the last seven files. Show the precise
window, reporting coverage, and data gaps. When available:
- Sessions completed vs. planned, major lifts and volume/progression context.
- Average or trend in logged sleep duration.
- Meal logging completeness and estimated nutrition against user-defined goals.
- Weight trend with sample count and measurement conditions.
- Recovery/fatigue observations that the user actually reported.

Offer a small number of testable adjustments and what to look for next week.
Avoid unsupported causal statements, scoring someone's lifespan, or treating
estimated calorie expenditure minus food estimates as a precise deficit.

## 5. Safe write and handoff

- First show exactly what will be created/changed and where. Ask when intent
  is ambiguous; require explicit approval before writes to external services
  such as SynFit, Apple Health or third-party APIs.
- Preserve human-written daily notes, append corrections rather than silently
  replacing observations, and respect generated-file ownership in AGENTS.md.
- Pull/reconcile current Git history before editing; never force-push.
- Never publish health data in a public repo, issue, PR, discussion or log.
- Do not upload photographs, health records or identifiers to external services
  without informed user approval. Read access granted to a cloud AI assistant
  is itself a data-sharing decision.
- If you lack permission/tools, output a proposed patch or record instead
  of claiming to have committed or synchronized it.

## 6. Boundaries and provenance

This skill was informed by the *workflow concepts* discussed in the Alan Shao
and Justin Sun interview (meal photos, wearable data, training logs, Markdown,
portable AI agents and daily reviews):
https://www.youtube.com/watch?v=0Z-vhBvBmUY

It intentionally does NOT endorse the interview's unverified medical,
nutrition, longevity or calorie-balance claims. It does not make medical
diagnoses or prescribe treatment. Escalate urgent or concerning symptoms to
appropriate medical services rather than treating an AI-generated report as
medical advice.
