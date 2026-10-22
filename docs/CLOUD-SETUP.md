# Cloud environment and daily update setup

**Current operation is all-local.** See [LOCAL-SETUP.md](LOCAL-SETUP.md). This guide retains the future cloud configuration; its older cloud-only schedule instructions are superseded by `monitor/execution.json`. Do not activate the cloud schedule while local execution is selected. Real-PDF rehearsal passed, but cloud access to Council’s document host still returns proxy upstream timeouts. Before migrating, verify source transport in the saved environment and scheduler-launched child, pause the local schedule, review `location: cloud`, run the common preflight/workflow and verify the cloud binding before enabling it. Never run both production schedules.

Production: <https://lanecovetracker.wlsn.me/>. Repository: <https://github.com/adrasyn/lane-cove-resolution-tracker>, branch `main`.

## Architecture and current readiness

The ChatGPT cloud task performs the whole editorial workflow: scan Council, download and hash PDFs, extract rows, compare changes, connect minute items to issues, draft and check summaries, build, verify and push accepted content. GitHub Actions performs deterministic checks and deploys `dist/` after those checks pass. There is no AI call, API key or daily scan schedule in Actions.

Ready in the repository:

- Scanner: `scripts/scan_trackers.py`, accepted identity/hash baseline in `monitor/baseline.json`.
- Portable physical-column extractor: `scripts/extract_tracker_rows.py`. It stages proposals; it does not approve or import them.
- Reviewed data and reproducible builder in `catalogue/`, plus minute/date/source-bound summary validation.
- One verification command: `bash scripts/verify.sh`.
- A Pages deployment job after successful checks on `main`.
- Durable run instructions in `docs/DAILY-TASK.md` and project instructions in `AGENTS.md`.

Not yet an unattended end-to-end importer: there is no single command that accepts a PDF and produces approved new issues and summaries. The cloud agent must execute that editorial work using the run instructions. Before enabling automatic publication, rehearse a changed edition in a disposable branch, including table warnings, new minute items, historical links, summary bindings and the coverage inventory. The existing source data can be used for replay. A successful no-change scan alone does not test this path.

The coverage date (`2026-10-22`), the 2026 membership policy and verified inventory assertions are currently explicit in the builder/checks. The first changed-edition rehearsal must make the release inventory and coverage-date update process repeatable; do not simply remove those assertions. Retain 2026 issues across New Year and explicitly agree scope for new 2027 items.

## Create the environment

| Setting | Value |
| --- | --- |
| Name | Lane Cove tracker updates |
| Repository | `adrasyn/lane-cove-resolution-tracker` |
| Starting branch | `main` |
| Access | Only me |
| Runtime | Python 3.12, Node.js 22 or newer, Git, curl, GitHub CLI (`gh`) |
| Internet | Enabled during setup AND task execution |
| Network preset | Package managers, plus the additional hosts below |
| Long-running service | None; a static preview server is needed only during visual review |
| AI/Council API secrets | None |

Additional allowed domains (hostnames, no URL paths):

```text
lanecove.infocouncil.biz
ecouncil.lanecove.nsw.gov.au
api.github.com
raw.githubusercontent.com
lanecovetracker.wlsn.me
adrasyn.github.io
```

The Package managers preset supplies `github.com`, `codeload.github.com`, `release-assets.githubusercontent.com`, `pypi.org` and `files.pythonhosted.org`. If using Custom domains only instead, add those five hosts as well. Add another redirect/download host only when an observed request needs it. If HTTP methods can be restricted, allow GET/HEAD for sources plus POST for Council's read-only ASP.NET index form and the write methods required for authenticated GitHub updates. A domain allowlist does not provide GitHub write access.

Setup commands, from the checked-out repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-cloud.txt
bash scripts/verify.sh
git diff --exit-code -- dist
```

Ask the environment builder to install missing runtimes/tools before those commands. Keep `.venv/` untracked. There is no npm install or website build service. For PDF visual review, the pinned `pdfplumber` dependency includes a PDF rendering library; Poppler is optional.

## GitHub credentials

Connect the GitHub account with access to this repository. Test separately that the cloud task can read it, create a branch/commit and push or create a draft PR. A repository being checked out does not by itself prove write access, and this computer's GitHub CLI login does not transfer to cloud tasks.

Prefer the managed GitHub connection when it supports these writes. If a separate credential is necessary, use a fine-grained token scoped only to this repository: **Contents: read/write**, **Pull requests: read/write**, and **Actions: read** to inspect CI. Metadata read is implicit. Store it in the environment's secret facility; for `gh`, use the key `GH_TOKEN` and allow its HTTPS destinations `api.github.com` and `github.com`. Test both API calls and the chosen push mechanism. Do not paste the value into chat or commit it. No Pages administration or Workflows write permission is needed for routine data updates.

Do not use a workflow's built-in `GITHUB_TOKEN` as the external publisher identity: pushes made with that token generally do not trigger a new workflow. The Pages workflow uses its own short-lived token only to deploy the already checked commit.

## First task in the published environment

Paste this in a new cloud task after publishing the environment:

> Prepare this repository for its daily ChatGPT cloud update task. Read AGENTS.md, docs/CLOUD-SETUP.md and docs/DAILY-TASK.md. All scanning, extraction, issue matching and AI summaries must run here; GitHub Actions only checks and deploys the result. Confirm the required hosts and GitHub write access, run the verification suite, and run a live scan. Then rehearse a changed tracker edition on a disposable branch without altering the accepted production baseline or merging it: exercise extraction, new/changed rows, minute-item issue matching, summary bindings, release inventory/coverage updates and unchanged-history checks. Resolve the remaining importer/release gaps and make the process repeatable. Report the diff, source evidence, tests and deployment path. Do not enable the schedule until the changed-edition rehearsal passes.

## Schedule after the rehearsal

Create it in the cloud task that has the tested environment and repository access. Suggested cadence: **daily at 07:17, Australia/Sydney**, which follows Sydney daylight saving. The prompt is in `docs/DAILY-TASK.md`. Choose Cloud explicitly, rather than a local desktop automation; verify the saved task retains that environment and its tools. If the scheduling surface cannot attach the published cloud environment, resolve that limitation before activation rather than substituting a desktop-only task.

Run once manually through the scheduler and inspect its saved result before relying on daily operation. Notify James about accepted updates, review items and failures; a successful unchanged scan should return a short no-change result in its run history. Persist source evidence in GitHub before the cloud workspace disappears. No new commit is necessary on unchanged days.

The schedule is not created by adding this guide. It still needs the environment, tested credentials, changed-edition rehearsal and activation in ChatGPT.

## Production deployment

`.github/workflows/checks.yml` verifies source completeness, summary provenance, generated data, routes and browsing behaviour. Only a successful `main` run uploads `dist/` and deploys to the `github-pages` environment. Failed checks leave the preceding website deployed. PRs are checked but not published. The custom domain is a GitHub Pages setting; a CNAME file is not required with an Actions deployment. Keep its setting as `lanecovetracker.wlsn.me`, HTTPS enforced, and Hover's CNAME pointing to `adrasyn.github.io`.

The older ChatGPT Sites preview is a separate deployment. Routine cloud updates target the production GitHub Pages website; they do not need the original preview's credentials.

## Official references

- [Cloud environments, internet access, variables and network secrets](https://learn.chatgpt.com/docs/environments/cloud-environments)
- [Scheduled tasks and manual testing](https://learn.chatgpt.com/docs/automations)
- [GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)
- [Custom domain configuration](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site)

## Reviewed release inventory

`catalogue/release-inventory.json` is the accepted release contract: exact 2026 minute-item membership, each physical source-file hash and row count, coverage date and membership policy. It is derived independently of issue grouping and summaries. The builder rejects source changes until this inventory is reviewed, and the JavaScript checks compare all 2026 memberships and editions against it. The policy retains 2026 across New Year; review scope explicitly before importing 2027 items.

After source/editorial review, run `.venv/bin/python scripts/derive_release_inventory.py --output scan-output/release-candidate.json`. Inspect its diff against the accepted inventory, including every added/removed minute item and source hash, before copying the candidate to `catalogue/release-inventory.json`. This is approval of already checked sources, not an importer. Run `bash scripts/verify.sh`. The builder sets the reference/visible coverage dates and content-addressed data/source/evidence/app cache versions from accepted content. Never advance coverage on a scan alone.

Cloud shell network commands require the execution tool's network permission as well as the environment allowlist. Preserve the inherited proxy and TLS trust. A sandbox-denied proxy connection does not show that the six configured hosts are blocked.

## Diagnosing upstream source failures

An Envoy 503 body saying `upstream connect error ... connection timeout` means the cloud request failed to establish its upstream connection before origin response headers arrived. It does not establish that Council returned an application-level 503 or that a PDF was revised. Retest the permanent link and a currently resolved URL through the configured proxy with TLS verification; transient `documents_TE` paths can expire. Compare the document-host homepage and the agenda host. If the local permanent link works but the cloud document host consistently times out, resolve cloud egress/origin reachability rather than editing identifiers or guessing download paths.

The scanner retains HTTP status and labels this failure explicitly. After curl's bounded retries, it defers the remaining requests to that host for the current run, records each unverified attachment as an error, and still discovers the agendas. The next run retries the host. Deferred sources are never classified unchanged and the baseline is never advanced. This avoids repeating the same failed upstream connection twenty times.

The scanner still verifies and hashes every discovered tracker against the accepted baseline. It now supports a separate persistent strong-ETag cache with exact-resource conditional requests; see [SCANNER.md](SCANNER.md). Local testing verified a same-URL 304, but the normal permanent-link path generated a new temporary URL and saved no PDF transfer. Do not infer byte identity across URLs, skip historical PDFs or claim full revision checking from agenda-only discovery. Cloud document-host transport remains a separate unresolved limitation.
