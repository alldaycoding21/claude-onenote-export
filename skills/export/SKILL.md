---
name: export
description: Export, back up or sync Microsoft OneNote notebooks to local Markdown files so Claude can read and search them (all notebooks, section groups, sections and pages, with images, attachments and raw HTML; incremental refresh). Use when the user wants to export, back up, download or sync OneNote, make OneNote notes readable by Claude, or refresh an existing OneNote export. Also triggers on "원노트 내보내기", "원노트 백업", "원노트 전체 저장", "원노트 갱신".
argument-hint: "[output folder] [--only Notebook[/Section]]"
---

# OneNote → local Markdown

Exports the user's OneNote through Microsoft Graph with a **Graph Explorer access token**. Graph Explorer is Microsoft's own web tool, so no Azure app registration is needed. The token is delegated and the scope is read-only `Notes.Read`. The script reads the token from the clipboard and clears it.

Arguments from the user, if any: $ARGUMENTS

## Ground rules
- **Never put the token in the conversation.**
  - Do not ask the user to paste it into the chat.
  - Do not read it with JavaScript, `get_page_text` or `read_page`.
  - Do not echo the clipboard.
  - If the user pastes it anyway, tell them it is now in the transcript (it expires in about an hour) and do not reuse it.
- **The user signs in and consents.** Claude never types passwords.
- **One export at a time per output folder.** Two runs overwrite each other's `_state.json`. Stop the running one before starting another.
- The output can contain secrets, for example notes that were password-protected. Never upload, share or commit it.

## 1. Set up (once per machine)
Pick the runner and call it `PY` below.
- **`uv` on PATH (preferred):**
  - `PY` = `uv run --locked -q "${CLAUDE_SKILL_DIR}/scripts/onenote_export.py"`
  - uv installs the pinned dependencies from `onenote_export.py.lock`.
- **Otherwise**, with Python 3.9+:
  ```
  python3 -m venv "${CLAUDE_PLUGIN_DATA}/venv"
  "${CLAUDE_PLUGIN_DATA}/venv/bin/python" -m pip install -q markdownify==1.2.3 beautifulsoup4==4.15.0
  ```
  - `PY` = `"${CLAUDE_PLUGIN_DATA}/venv/bin/python" "${CLAUDE_SKILL_DIR}/scripts/onenote_export.py"`
  - On Windows, use `python` instead of `python3` and `venv/Scripts/python.exe` instead of `venv/bin/python`.

Check the runner with `PY --selftest`. It should print `selftest ok`.

## 2. Choose the output folder
- Use the folder the user named. Otherwise use `./onenote` in the current project, and tell the user.
- If it is inside a git repository and not ignored (`git check-ignore -q <dir>`), warn the user and offer to add it to `.gitignore`.
- If the folder already has `_state.json`, this is a **refresh**. Only new or changed pages are downloaded.

## 3. Get a token onto the clipboard
Ask the user to do these steps and reply "copied". Tell them **not** to paste the token into the chat.
1. Open https://developer.microsoft.com/graph/graph-explorer and **sign in** (top right) with the Microsoft account that owns the notebooks.
2. **First time only:** open **Modify permissions**, find **Notes.Read**, click **Consent**, and accept the Microsoft popup.
3. Set the query to `GET https://graph.microsoft.com/v1.0/me/onenote/notebooks` and click **Run query**. Expect `OK - 200` and a list of their notebooks.
4. Open the **Access token** tab and click the **copy** icon next to the heading.

If Claude in Chrome tools are available, Claude may drive these steps instead:
- The user chooses the browser and does the sign-in and consent clicks.
- Pitfalls are in [troubleshooting](references/troubleshooting.md#graph-explorer).
- Screenshots of the Access token tab show the token, so prefer the user clicking Copy themselves.

## 4. Run
Run in the background and watch the output. Use the Monitor tool if available, matching `p \(\+|FAIL|Traceback|Error|401|Done|No access token`:
```
PY --out "<DIR>" [--only "Notebook" "Notebook/Group/Section" ...] 2>&1
```
- **Progress:** one line per section, like `Notebook / Section: 12p (+3)`. That means 12 pages, 3 downloaded now.
- **`429 -> waiting Ns` is normal.**
  - OneNote throttles hard after a few hundred requests.
  - A few hundred pages can take hours.
  - Keep the user informed rather than restarting.
- **Exit 2** means no token on the clipboard, or the token expired (after about 60–90 min).
  - Ask the user to reload Graph Explorer, click **Run query**, and copy again.
  - Then rerun the **same command**. Finished pages are skipped.
- **Restarting while throttled is slow.** Every section is listed again. Pass `--only` with only the notebooks that are not finished yet.

## 5. Failures
Read `<DIR>/_failures.md`.
- **`403` with `20185 Encrypted sections are not accessible`** is a password-protected section. The API cannot read it, even when unlocked. If the user wants it included:
  1. In OneNote desktop, right-click the section → Password Protection → **Remove Password**. Unlocking is not enough.
  2. Sync the notebook.
  3. Rerun with `--only "Notebook/Section"`.
  4. **Immediately remind the user to set the password again.**
- **Other errors:** rerun the same command first; transient errors usually clear. Then see [troubleshooting](references/troubleshooting.md).

## 6. Finish
1. Run `PY --out "<DIR>" --verify`. Expect `problems 0`; it checks pages on disk and image/attachment links.
2. Report the counts, the location of `<DIR>/INDEX.md` and any failures.
   - If `INDEX.md` lists "Removed in OneNote (kept locally)", mention them. Those files are never deleted automatically.
3. Offer, and only with the user's yes, to add one line to the project's `CLAUDE.md` so future sessions know about the export. For example:
   `OneNote export: <DIR>/INDEX.md (one .md per page; search with grep). Refresh: /onenote-export:export`

## Using the export later
- Answer questions about the notes with Grep and Read on `<DIR>`. `INDEX.md` maps sections to pages.
- Each page header has a `Source:` link back to OneNote.
- To change how HTML is converted: edit `render()` in the script, then run `PY --out "<DIR>" --rerender`. This works offline from `_raw/`.
