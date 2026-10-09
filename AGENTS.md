# Instructions for AI assistants

This repository is a personal health-data store, **not** a place to invent observations or give medical diagnoses.

## Before editing
1. Read README.md, profile.md, and the relevant daily log.
2. Treat imported records as source data. Never replace real measurements with estimates.
3. Store all access credentials outside the repository. Do not print tokens or private responses in logs.
4. Never push real personal health data to a public repository; use a private copy.
   The sync script verifies all GitHub origin push URLs before writing/pushing
   (requires an authenticated GitHub CLI or GitHub API token).

## Ownership and provenance
- data/workouts/YYYY-MM-DD.json: raw SynFit response, owned by sync script; do not hand-edit.
- data/daily/YYYY-MM-DD.md: human/agent notes plus an automatically owned SynFit block.
- reports/daily/ and SUMMARY.md: generated outputs; do not hand-edit.
- data/meals/: meal entries authored by the user or an assistant.
- data/metrics/: body metrics from an identified source.

The two markers inside a daily Training section delimit an auto-managed block:

<!-- BEGIN XUNJI SYNC -->
- Imported workout entries only
<!-- END XUNJI SYNC -->

Preserve everything outside these markers. Never edit or delete the markers manually.
The `XUNJI SYNC` marker spelling is a legacy internal identifier retained for
existing logs; SynFit is the app's English name.

## Record conventions
- Use ISO 8601 dates (YYYY-MM-DD) and explicit timezone for timestamps.
- Record measurement units: kg, cm, hours, kcal, and g.
- Include source (e.g. SynFit, Apple Health, user), timestamp and confidence/estimated flag when relevant.
- For meals, distinguish estimates from verified nutrition-label values.
- Missing data means unknown, not zero. Do not claim a rest day because there is no workout record.
- Check whether a record already exists before adding another one for the same event.

## Writes and conflicts
1. Pull the latest revision before modifying a file. If another assistant changed it, reconcile rather than overwriting.
2. Present a concise summary of proposed changes before writing to third-party APIs. Get explicit approval first.
3. A local health-log update may follow the user's request, but preserve human notes and all other providers' data.
4. Do not force push, erase history, or silently overwrite conflicting records.
5. Do not automatically send personal data to external analysis services. Seek permission before changing integrations.

## Analysis
- Derive trends from dated observations and state the analysis window.
- Explain gaps in data coverage and avoid clinical diagnoses.
- Keep advice separate from underlying observations.
