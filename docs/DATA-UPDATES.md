# Keeping the tracker current

## Chosen workflow

ChatGPT Cloud performs the complete daily data workflow: discovery, PDF extraction, comparison, connecting minute items into issues, AI summaries, source checks, building and pushing accepted content. GitHub Actions checks the resulting commit and publishes the verified `dist/` files to https://lanecovetracker.wlsn.me/. Actions does not perform AI processing or run a daily scan schedule.

See [CLOUD-SETUP.md](CLOUD-SETUP.md) for environment settings, allowed domains, dependencies, credentials and the first-run prompt. [DAILY-TASK.md](DAILY-TASK.md) is the durable scheduled-task prompt. The cloud environment and schedule still need to be created, tested and activated.

## What is implemented

The scanner checks all listed Council agendas for the current and previous years, including supplementary and extraordinary agendas. It finds Resolution Tracker attachments, follows Council redirects, validates PDF identity and compares full-byte SHA-256 hashes with `monitor/baseline.json`. New documents, changed bytes at an existing address and reused PDFs are distinguished. Errors, missing known agendas and missing expected attachments fail visibly rather than being reported as no changes.

The portable extractor separates the seven physical table columns and joins page continuations. It validates the downloaded hash and page count against the scan report. It stages proposed rows, including warnings, without changing the accepted catalogue or baseline. Exit code 2 means source review is needed. It is a research-derived extractor, not a general PDF-table guarantee.

The catalogue builder retains complete rows, quoted wording, dates and source references. Reviewed officer-comment summaries must match minute item, dated update and exact source wording with whitespace normalised; missing or ambiguous bindings stop the build. This prevents the earlier cross-item summary-reuse error.

The Pages workflow runs after checks pass on main. It publishes only `dist/`, not research scripts, credentials or archived PDFs. PRs receive checks without deployment. The manual scan workflow remains available as a diagnostic; it is not the daily scheduler.

## Trial evidence

On 22 October 2026 the original trial checked 17 listed 2026 agendas and all nine tracker PDFs, matching the reviewed archive. The two-year trial checked 36 agendas and 20 PDFs with no errors or changes; its report is in `monitor/trials/2026-10-22.json`. The cloud-readiness live check on the same day again checked 36 agendas and 20 PDFs with no differences or errors.

## What must be rehearsed before unattended updates

A no-change scan does not exercise a new edition. In the cloud environment, replay a changed edition on a disposable branch and test extraction warnings, row comparison, new minute items, evidence-based issue grouping, historical links, source-bound summaries, complete-history preservation and release inventory/coverage updates. There is no one-command automatic acceptance/import stage yet; the cloud agent must do and verify this editorial work.

Coverage date and counts are explicit in the current release. The checked inventory has nine 2026 editions and 221 minute items. A new edition must update the independently derived inventory, coverage date, visible source date and asset cache versions together. Do not remove source-completeness checks to bypass a changed count. Retain existing 2026 issues across New Year; decide scope for new 2027 items explicitly.

After the changed-edition rehearsal passes, activate a cloud task, suggested daily at 07:17 Australia/Sydney. Routine unambiguous updates may be pushed after full validation under that task's authorization. Ambiguity must produce a review proposal without changing accepted production data. Deduplicate pending work by edition and PDF hash.

## Evidence and interpretation rules

| Change | Treatment |
| --- | --- |
| New minute item | Retain number and meeting year; link to an existing issue only with evidence. |
| Dated officer comment | Retain its date separately from decision and publication dates. |
| Repeated unchanged comment | Preserve the monthly row without inventing a progress event. |
| Status or target changed | Date the observation to the edition; do not infer a delivery promise. |
| Completed item | Explain the specific task; do not automatically close the broader issue. |
| Row missing | Flag it; do not infer completion. |
| Blank, malformed or duplicated identifier | Inspect the source and adopted minutes; do not guess. |
| Different bytes at the same URL | Preserve both versions, hashes and first-seen metadata. |
| Same PDF under another agenda | Record the reference without inventing a fresh edition. |
| Unavailable source or changed layout | Report the error and preserve published data. |

Preserve accepted future PDFs under `monitor/accepted/<sha256>.pdf`, with a change/source report outside `dist/`. Preserve unresolved evidence on its review branch. Do not leave the only copy in a temporary cloud workspace or an expiring artifact. The original historical PDF research archive is not bundled; structured rows and source hashes remain in the repository.

The scanner compares against the accepted catalogue, not the previous scan. Pending changes remain visible until actually incorporated. Advance the baseline only when acceptance and validation are complete. The website's “Records through” date means the latest accepted source edition; a successful scan date is a separate fact.

## Limits

- Rechecks current/previous-year PDFs for revisions; it does not perpetually re-audit every historic source or find unlinked attachments.
- Depends on Council's ASP.NET form, agenda HTML and document redirects; a source redesign requires investigation.
- Extraction warnings and warning-free output both need source-aware review; AI copy still requires factual checking.
- The cloud task needs tested write access and durable GitHub state. Each new workspace must begin from fresh main content.
- GitHub Pages and the original ChatGPT Sites preview are separate deployments. Production updates target Pages.

## Sources

- [Council agenda archive](https://lanecove.infocouncil.biz/)
- [Cloud environment setup](https://learn.chatgpt.com/docs/environments/cloud-environments)
- [Scheduled tasks](https://learn.chatgpt.com/docs/automations)
- [GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
