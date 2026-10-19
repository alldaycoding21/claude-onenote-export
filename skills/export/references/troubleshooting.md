# Troubleshooting

## Graph Explorer
Use these when driving Graph Explorer with browser automation, or when the user gets stuck.
- **Signed in?** The top right shows the account. A personal account shows `Tenant: Personal`.
- **`401` with `code 40001` on Run query:** Notes.Read is not consented.
  - Open Modify permissions → Notes.Read → Consent.
  - Once consented, the row shows **Unconsent**.
- **`Scope consent failed - interaction_in_progress`:** an earlier sign-in popup is still pending. Reload the page and try again.
- **The token shown is stale after it expires.** Reload the page, click Run query again, and only then copy.
- **Copy did not land on the clipboard.**
  - The exporter says "No access token on the clipboard" and leaves the clipboard untouched.
  - With browser automation, a click through an element ref sometimes does not trigger the copy. Take a screenshot, find the copy icon next to the "Access token" heading, and click it by coordinates.
- **Work/school accounts:** the tenant may block Graph Explorer, or require admin consent for Notes.Read. Only the tenant admin can fix that.

## Exporter messages
| Output | Meaning / action |
|---|---|
| exit 2, `No access token on the clipboard` | Copy failed, or the clipboard holds something else. Copy again and rerun |
| exit 2, `401 Unauthorized` | Token expired (about 60–90 min) or invalid. Reload Graph Explorer → Run query → copy → rerun the same command. Finished pages are skipped |
| `429 -> waiting Ns` | OneNote throttling. Expected after a few hundred requests. The backoff goes up to 300 s and 10 tries per request. Let it run |
| Restart is slow | While throttled, even listing finished sections costs minutes. Use `--only` for the notebooks that are not done yet |
| `FAIL … 403` + `20185` | Password-protected section. See SKILL.md step 5. The password must be **removed**, not just unlocked, and the notebook synced |
| other `FAIL`/4xx in `_failures.md` | Rerun once; transient errors clear. A persistent error text comes from Graph, so search it |
| `refusing to send the token to <host>` | A URL outside graph.microsoft.com reached the fetcher. That is a bug; report it |
| `Clipboard tool not found` (Linux) | Install `wl-clipboard` (Wayland) or `xclip` (X11) |

## Behaviour to know
- **Incremental:** a page is downloaded again only if its `lastModifiedDateTime` changed or it moved to another section. File names are fixed when a page is first exported (`Title.md`, or `Title (2).md` for duplicates). Reordering never renames files; the order is shown in `INDEX.md`. A retitled page gets a new file name.
- **Deleted pages:** the local file stays. A full run (without `--only`) lists them in `INDEX.md` under "Removed in OneNote (kept locally)".
- **Renamed section or notebook:** its pages are downloaded again into the new folder. The old `_files/` folder stays behind.
- **Not converted to text:**
  - ink and drawings
  - text inside images (no OCR)
  - embedded videos (iframes)
  - Empty rows in source tables stay.
- **Notebooks covered:** only those returned by `/me/onenote/notebooks`. SharePoint and Teams group notebooks are not included.
- **Changing conversion:** edit `render()` in `scripts/onenote_export.py`, then run `--rerender`. It works offline from `_raw/` and reuses the already downloaded files.
