# onenote-export

A Claude Code plugin that exports **all** your Microsoft OneNote notebooks to local Markdown, so Claude can read and search them.

[한국어](README.ko.md)

> Unofficial community project. Not affiliated with, endorsed by or supported by Microsoft. OneNote and Microsoft Graph are trademarks of Microsoft.

- One `.md` per page, organized as `Notebook/[Section group/]Section/Title.md`, with an `INDEX.md` of everything in OneNote order.
- Images and attachments are downloaded next to the pages. The original page HTML is kept too.
- Refresh any time: only new or changed pages are downloaded again. Interrupted runs resume where they stopped.
- **No Azure app registration.** The token comes from Microsoft's own [Graph Explorer](https://developer.microsoft.com/graph/graph-explorer), with read-only `Notes.Read` access.
- Works with personal Microsoft accounts. Work/school accounts work too, if your tenant allows Graph Explorer.

## Why
OneNote has no "export everything" button. Whole-notebook PDF export is not available, and the web app renders pages inside a cross-origin iframe. The Microsoft Graph OneNote API can read everything, but it needs a token and copes badly with large accounts because of heavy throttling. This plugin handles both, and Claude walks you through the steps.

## Install
In Claude Code:
```
/plugin marketplace add alldaycoding21/claude-onenote-export
/plugin install onenote-export@onenote-export
```
- From a local clone, use `/plugin marketplace add ./claude-onenote-export`.

Requirements:
- **Claude Code on your own computer** (CLI or desktop app). It does not work in claude.ai chat or Cowork, because it needs your local clipboard and file system.
- Python 3.9+
- [`uv`](https://docs.astral.sh/uv/) is recommended. Without it, the skill creates a small venv.
- A desktop clipboard: macOS, Windows, or Linux with `wl-clipboard`/`xclip`.

## Use
Ask Claude, for example: *"Export my OneNote to ./onenote"*, *"원노트 백업해줘"*, or run `/onenote-export:export`. Claude will:
1. Ask you to copy a token (below). You never paste the token into the chat.
2. Run the exporter in the background and report progress.
3. Help with password-protected sections, check the result, and offer to note the export in your `CLAUDE.md`.

### Getting the token (your part, about a minute)
1. Open [Graph Explorer](https://developer.microsoft.com/graph/graph-explorer) and **sign in** (top right) with the Microsoft account that owns the notebooks.
2. First time only: open **Modify permissions**, find **Notes.Read**, click **Consent**, and accept the Microsoft popup.
3. Click **Run query** with `GET https://graph.microsoft.com/v1.0/me/onenote/notebooks`. You should see `OK - 200` and your notebooks.
4. Open the **Access token** tab, click the **copy** icon, and tell Claude "copied".

Tokens last about an hour. When Claude asks for a fresh one, reload Graph Explorer, click **Run query** and copy again. The export continues where it stopped.

### Expect throttling
OneNote throttles hard after a few hundred requests (`429`, 15 s to 5 min per request). A few hundred pages can take a few hours.

### Refresh and use
- **Refresh:** ask again, for example *"Refresh my OneNote export"*. Only new or changed pages are downloaded.
- **Use:** ask questions such as *"Find my OneNote notes about the budget"*. Claude searches `INDEX.md` and the pages. If you accepted the `CLAUDE.md` line, later sessions know where the export is.

Something wrong? See [troubleshooting](skills/export/references/troubleshooting.md).

## Output
```
onenote/
  INDEX.md                 sections → pages, modified dates, removed pages, failures
  <Notebook>/<Section>/<Title>.md       duplicates become "<Title> (2).md"; names never change on reorder
  <Notebook>/<Section>/_files/      images and attachments
  _raw/…/*.html            original page HTML (for offline re-conversion)
  _state.json              page id → path and modified time (drives incremental refresh; keep it)
  _failures.md             problems from the last run
```
Each page starts with its location, created/modified times and a `Source:` link back to OneNote.

## Standalone (without Claude)
Copy a token from Graph Explorer, then run:
```
uv run --locked skills/export/scripts/onenote_export.py --out ./onenote
uv run --locked skills/export/scripts/onenote_export.py --out ./onenote --only "Notebook" "Notebook/Group/Section"
uv run --locked skills/export/scripts/onenote_export.py --out ./onenote --verify
```
Exit code 2 means there is no valid token: copy one and rerun.

## Update or remove
```
claude plugin update onenote-export@onenote-export
claude plugin uninstall onenote-export@onenote-export
```
Inside Claude Code, the `/plugin` menu does the same. Removing the plugin does not delete your exported notes.

## Limitations
- **Password-protected sections** cannot be read by the API, even when unlocked. Remove the password temporarily, sync, export that section with `--only`, then set the password again.
- Not converted to text:
  - ink and drawings
  - text inside images
  - embedded videos
- **Deleted pages** are kept locally and listed in `INDEX.md`.
- **SharePoint/Teams group notebooks** are not included.
- Tested on macOS with a personal account. The Windows and Linux clipboard paths are implemented but not yet tested on real machines.

## What this plugin runs, reads, sends and writes
- **Runs:** one readable Python script, `skills/export/scripts/onenote_export.py`.
  - With uv: `uv run --locked`. Dependencies are pinned in `onenote_export.py.lock`: markdownify 1.2.3, beautifulsoup4 4.15.0 and their dependencies, from PyPI.
  - Without uv: a venv in the plugin's data folder, with the same pinned versions.
- **Reads:**
  - The clipboard, once per run (`pbpaste` on macOS, Python's built-in tkinter on Windows, `wl-paste` or `xclip` on Linux).
    If the content looks like an access token, it is cleared (`pbcopy`, tkinter, `wl-copy --clear` or `xclip`).
    Anything else is left untouched.
  - Your OneNote notebooks, sections and pages, with their images and attachments.
- **Sends:** HTTPS `GET` requests to `https://graph.microsoft.com` (Microsoft Graph OneNote API) only, with your token as the Bearer header.
  - No other hosts, no telemetry, no analytics.
  - Nothing in OneNote is created, changed or deleted.
- **Writes:** only inside the output folder you choose: Markdown, images/attachments, raw HTML, `INDEX.md`, `_state.json` and `_failures.md`.
  The token is never written anywhere.

## Security and privacy
Full policy: [PRIVACY.md](PRIVACY.md).
- Data goes only between your machine and `graph.microsoft.com`. The token is sent to no other host, even if a page links elsewhere.
- The token is read from the clipboard, then the clipboard is cleared. The token is never printed, logged or saved. It expires in about an hour.
- Your export may contain secrets, for example notes from formerly protected sections. Do not commit or share it. The repo's `.gitignore` ignores `onenote/`.
- To revoke Graph Explorer's access, remove it at <https://account.live.com/consent/Manage> (personal accounts), or ask your admin (work/school).

## License
MIT
