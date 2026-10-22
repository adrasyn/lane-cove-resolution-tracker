# Local daily updates

The complete daily workflow runs in ChatGPT on James's laptop. Discovery, PDF downloads, physical extraction, issue matching, summaries, source review, verification and GitHub pushes all happen locally. GitHub Actions checks the accepted commit and republishes the website. There is no hybrid PDF transfer or second processing pipeline.

## Binding and schedule

- Configuration: `monitor/execution.json`, currently `location: local`.
- Checkout: `~/Documents/Claude/Projects/lanecovetracker/github-repo` on macOS. The outer project folder is not the Git checkout.
- Native desktop schedule: **Lane Cove tracker daily update — local**, ID `lane-cove-tracker-daily-update-local`.
- Daily **07:17 Australia/Sydney**, with an explicit `DTSTART;TZID=Australia/Sydney` recurrence saved through the native scheduler API. This follows Sydney daylight saving.
- The heartbeat continues local thread `01a15ec0-f120-7f12-bfc7-0a39f5f3e45a`; its prompt explicitly changes to the checkout above and reads the shared workflow from fresh main.
- The previous cloud automation `6ad9bfafcb008191bb370849b46a3f47` must remain **paused**. Do not enable both publishers.

Manage the local schedule in **Scheduled in the desktop app**. Its heartbeat belongs to this local chat; the separate web/cloud Scheduled view may not list it. The automation is configured using the app's supported API, not a hand-written launch agent, crontab or daemon.

The computer must be on, the desktop app running, the project available, and network/GitHub access working. Sleep, offline operation and missed-run catch-up have not been verified; do not assume a missed run will be replayed. No wake, security or permission settings were changed. Review the first timer-triggered result in this chat before relying on unattended operation. Manual workflow testing does not prove that a future scheduled wake occurred.

## Shared workflow and preflight

`docs/DAILY-TASK.md` is the one complete processing prompt for both local and future cloud operation. Install its existing shared dependencies with:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-cloud.txt
```

The dependency filename is retained for compatibility; local operation uses the same pinned extractor. Git, curl, Node and GitHub CLI must already be available. Use the existing GitHub identity; no Council or AI API key is needed.

Before each run:

```sh
.venv/bin/python scripts/update_preflight.py --location local
git fetch origin main
git merge --ff-only origin/main
.venv/bin/python scripts/update_preflight.py --location local
```

Reread AGENTS.md, execution configuration and the daily workflow after refreshing main. The read-only preflight verifies selected execution location, actual macOS checkout path, origin, main branch, clean working tree, pinned PDF dependencies and existing GitHub push permission. It stops on unfinished work, a stale cloud location, another checkout or missing access. This prevents accidental use of the wrong runtime; it is not a security attestation against an actor deliberately bypassing the checks. A normal verified push proves the publishing credential separately.

Follow the daily workflow after preflight. Scanner/extractor output remains proposals. No-change days need no commit. Network failures must remain visible errors; uncertain extraction, identifiers, grouping or source revisions require one deduplicated review proposal. Never advance the baseline until the source is incorporated and validated.

## Activation evidence — 22 October 2026

`monitor/trials/local-activation-2026-10-22.json` and `local-scan-2026-10-22.json` record the local tests:

- Live scan: 36 agendas, 20 PDFs, zero errors, zero changes.
- The real October PDF downloaded locally matches the accepted SHA-256. Physical extraction returns 64 rows across 65 pages, zero warnings and zero physical field differences. Only Council's temporary resolved download URL changed; its permanent record and bytes match.
- The isolated historical October acceptance rehearsal in PR #1 exercised 25 new minute items, retained 837 earlier rows and all prior routes, checked item-specific summaries and issue links, and rejected a stale inventory. The same processing code is used locally.
- 33 unit tests and all catalogue, route, source-link, browsing and JavaScript checks pass. No simulated edition or changed tracker data was published.

The cloud PDF failure was a proxy upstream connection timeout; local access succeeds. The existing manual GitHub diagnostic scan was cancelled and is not a production schedule. Keep the cloud worker's rehearsal branch/PR as historical evidence.

## Future all-cloud switch

Keep this workflow, dependencies, source checks and publication rules. Resolve document-host transport in the saved cloud environment and its scheduler-launched child. Verify repository/write access and real-PDF processing there. Pause the local schedule, review `location: cloud` in execution configuration, refresh and run the preflight with `--location cloud`, verify the saved cloud schedule's binding and an actual test result, then enable only that schedule. The local checkout binding remains available for a future switch back. Do not duplicate processing logic or introduce a hybrid transfer system.

See [cloud settings](CLOUD-SETUP.md) for the retained environment/network configuration and [the official local scheduling documentation](https://learn.chatgpt.com/docs/automations) for app availability requirements.
