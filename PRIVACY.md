# Privacy policy

onenote-export runs entirely on your own computer. The author runs no server, so the author never receives any of your data.

- **What it reads:** your OneNote notebooks, sections, pages, images and attachments.
  - It reads them from Microsoft Graph (`https://graph.microsoft.com`) with an access token that you copy from Microsoft Graph Explorer.
  - It reads your clipboard once per run to pick up that token.
- **Where it sends data:** nowhere except Microsoft Graph, and only read (`GET`) requests.
  - There is no telemetry, no analytics and no third-party service.
- **What it stores:** your notes, as files in the output folder you choose on your computer. They stay there until you delete them.
- **The token:**
  - It is kept in memory for a single run. It is never written to disk or logged.
  - The clipboard is cleared after the token is read.
  - The token expires after about an hour.
- **Microsoft:** how Microsoft handles your data is covered by the [Microsoft Privacy Statement](https://privacy.microsoft.com/privacystatement). You can revoke Graph Explorer's access at <https://account.live.com/consent/Manage>.
- **Questions:** open an issue at <https://github.com/alldaycoding21/claude-onenote-export/issues>.
