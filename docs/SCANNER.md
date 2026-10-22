# Tracker discovery and conditional PDF cache

Run the same scanner locally or in a future cloud environment:

```sh
.venv/bin/python scripts/scan_trackers.py
```

The current and previous Sydney calendar years are scanned. The accepted identity/hash baseline remains `monitor/baseline.json`; discovery, downloads and caching never advance it or change the website.

## Discovery evidence

The scanner reads agenda item boundaries, attachment rows, link titles/filenames and surrounding paragraphs. It recognises tracker/register/progress variants, and follows an explicit item-scoped reference such as “Resolution Tracker [AT-2]” even when the linked row has a different name. Unicode attachment-number hyphens are normalised. Neighbouring snapshot, budget and police attachments are excluded; unrelated external PDF links are ignored. An actual tracker candidate pointing outside the allowed Council HTTPS hosts fails visibly.

Every candidate must resolve to PDF bytes with a tracker/register identity and the expected minute-number, resolution, Council-meeting, target-date, status and comments columns. A title mention inside an ordinary report is insufficient. This is an identity/layout check, not approval of extracted rows; the daily workflow must still inspect physical columns and validate editorial changes.

Missing known documents, unfulfilled explicit attachment references, ambiguous links and unrecognised tracker-like patterns fail visibly. A new monthly Council Snapshot item without an identifiable tracker also requires review, rather than silently returning no changes. This is deliberately bounded discovery, not an attempt to download every attachment or understand arbitrary future Council layouts.

The February 2026 agenda contains a real inconsistency: narrative text identifies AT-1, while its explicitly labelled, previously accepted tracker link is AT-2. That existing source identity resolves the conflict; the scanner selects the known explicit tracker row and emits a discovery diagnostic instead of downloading the snapshot. Without that extra known-source evidence, contradictory or missing references require review. One matched tracker cannot hide another missing tracker on the same agenda.

## Cache and correction detection

The default `.tracker-http-cache/` directory is ignored by Git and sits outside `dist/` and `scan-output/`. It contains observed PDF bytes indexed by SHA-256 and minimal exact-resource metadata: URL, strong ETag, byte count and hash. It is disposable transport state, never evidence that an edition was accepted. Cookies, raw response headers and form state exist only in the temporary request directory. They are not retained in the cache or website.

- Re-resolve each authoritative permanent Council link every run. Never assume its previous temporary download URL is still authoritative.
- Send `If-None-Match` only for an intact cached PDF at that exact requested URL. Redirects are followed explicitly and get their own validator lookup; a validator is never forwarded to another resource. New temporary URLs require a full fetch.
- A cache hit requires `304`, the same strong response ETag, compatible representation headers, and an independent size/SHA-256 check of the cached bytes before reuse. Weak tags, Last-Modified alone, incompatible Vary/content encoding and no-store cannot establish exact-byte reuse here. An unverifiable conditional response retries unconditionally or fails visibly.
- Missing, corrupt or mismatched cache state causes an unconditional fetch. Storage/request failures remain visible; the scanner never substitutes stale bytes after a network error. Writes replace complete files atomically.
- Hash and classify the resulting bytes against the accepted baseline every time, including cache hits. A pending revision remains `revised` on a later `304`, and is staged again in fresh scan output until explicitly incorporated. Reused hashes on new agenda links remain `reused_pdf`.

Use `--no-cache` to force full fetching, or `--cache-dir PATH` for a separate persistent cache. Keep custom cache directories untracked and outside published content; the scanner rejects a cache under `dist/`. Deleting the cache only removes the optimisation. Do not copy it into an accepted source archive or advance the baseline from cache metadata.

## Metrics and measured limits

Reports include HTTP requests, conditional requests, full PDF downloads, validated cache hits, reused cached bytes, repaired cache entries and PDF/all-response payload bytes. Byte counters are **curl-reported response bodies**, excluding HTTP/TLS headers and potentially automatic retry overhead; they are not exact wire-traffic measurements. Discovery and cache diagnostics remain in the report, with discovery notices also in its summary.

The bounded local test on 22 October 2026 found a strong ETag on the real 633,836-byte October PDF. Revalidating its exact URL returned `304` and transferred **zero PDF bytes**, reusing all 633,836 cached bytes with matching hash/content validation.

**The normal repeated permanent-link path demonstrated zero download saving.** Council generated a new temporary `documents_TE` URL on the second resolution. Both runs therefore safely downloaded the full 633,836 PDF bytes (634,363 response-body bytes including the redirect HTML). The cache cannot safely transfer a validator to a different URL merely because the filename or observed ETag looks similar. It helps when the authoritative resource URL remains stable; it does not currently eliminate the daily PDF downloads observed in this test.

Evidence: `monitor/trials/cache-discovery-2026-10-22.json`. Offline checks also matched all 41 saved agenda fixtures and validated the 20 accepted 2025–2026 PDFs without further network downloads. No accepted catalogue, baseline, schedule or website data changed.

The conditional request and strong/weak validator distinctions follow [HTTP semantics](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-none-match). This implementation uses a stricter exact-byte reuse policy than semantic equivalence alone.
