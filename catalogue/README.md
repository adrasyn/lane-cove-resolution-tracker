# Catalogue provenance

The 2026 membership inventory comes from all nine ordinary tracker editions published through 22 October. Eight listed supplementary/extraordinary 2026 agenda documents were also checked; none contains another Resolution Tracker attachment. No January ordinary edition is listed.

Historical ordinary editions were checked back to the tracker's April 2023 introduction. September 2023 is unavailable; December 2023 duplicates November. All available 2024 and 2025 ordinary tracker attachments were downloaded. Public archive indexes list no January ordinary meeting in these years and no September 2024 ordinary edition.

The source extractor uses PDF table-cell boundaries to separate minute number, title, resolution, meeting date, target, status and comments, and joins physical page continuations. Multiline numbers, the printed `\25` identifier, blank-number rows and duplicate source paragraphs were audited. Blank-number aliases are matched by unique title and meeting date; the Staff Interaction alias is additionally verified against adopted minutes.

The builder groups only explicit same-issue decisions and reviewed historical links. It preserves every complete scoped row. Officer notes are dated using PDF headings and sentence context, rather than treating a future date inside a sentence as an update. Identical notes are deduplicated while changed source wording remains accessible. Every date can contain several separately sourced records.

`historical-minutes-verification.json` contains official minutes citations for the combined Children/Families decision, Canberra Avenue consultation and closure, and Staff Interaction policy. Council's smart-glasses identifier `1/2026` and Austin Crescent/Street wording inconsistency are preserved with explanations.

## Officer-comment summaries and the 22 October 2026 correction

`note-summaries.json` is the active reviewed summary source. Every record names its minute item, dated update and full source comment. Only whitespace is normalised when matching. The build rejects missing, duplicate or unmatched bindings before generating the site.

The earlier batch files (`note-editorial-input.json`, `note-output-0.json`, `note-output-1.json`, and `note-output-extra.json`) are retained as historical editorial inputs. They are no longer read by the builder. Their former text-only lookup reused project-specific headings on unrelated minute items when officer comments were identical.

The audit covered all 682 officer-comment updates. It identified 58 uses of copy originally prepared for a different minute item, including harmless generic wording and incorrect project references. Reviewing those cases and the 32 comment patterns shared by current minute items resulted in 55 revised headings or summaries across 38 issue pages. Ten summary bodies changed; the remaining changes were headings. Repeated comments within the same item on different dates and the 18 whitespace/punctuation differences in legacy comment matching were also checked.

`summary-context-audit.json` records the source comment, previous copy, revised copy and minute-item provenance for the reviewed cases. All 1,110 original quotations, 901 full tracker rows, update dates, issue memberships and source links were unchanged by this correction. Tests cover the Greenwich Road/Austin Crescent error, CCTV/Kindy Cove and performance-review/transport mix-ups, missing reviews, changed source text, new dates and duplicate bindings.

This audit addresses summary association and repeated-comment reuse; it is not a claim that every AI paraphrase has undergone a new independent semantic review.
