#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["markdownify==1.2.3", "beautifulsoup4==4.15.0"]
# ///
"""Export Microsoft OneNote notebooks to local Markdown through Microsoft Graph.

Token: Graph Explorer (https://developer.microsoft.com/graph/graph-explorer) -> sign in -> Access token tab -> copy.
The token is read from the clipboard, then the clipboard is cleared. It is never printed or saved.

  onenote_export.py [--out DIR] [--only NOTEBOOK[/GROUP/SECTION] ...]   export (incremental, resumable)
  onenote_export.py [--out DIR] --verify | --rerender                     offline check / re-convert from _raw
  onenote_export.py --selftest

Exit 2 = no token, or token expired/invalid -> copy a fresh token and rerun the same command
(pages already exported are skipped).
"""
import argparse, hashlib, json, mimetypes, re, shutil, subprocess, sys, tempfile, time
import urllib.error, urllib.parse, urllib.request
from datetime import date
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify

G = 'https://graph.microsoft.com/v1.0/me/onenote'
RESERVED = {'CON', 'PRN', 'AUX', 'NUL', *(f'{p}{i}' for p in ('COM', 'LPT') for i in range(1, 10))}


class TokenExpired(Exception):
    pass


def safe(name, limit=80):
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', (name or '').strip())[:limit].strip(' .')
    if s.split('.')[0].upper() in RESERVED:  # Windows device names
        s = '_' + s
    return s or '(untitled)'


def is_graph(url):
    p = urllib.parse.urlsplit(url or '')
    return p.scheme == 'https' and p.hostname == 'graph.microsoft.com'


def get(url, tok):
    if not is_graph(url):  # page HTML is untrusted: the token only ever goes to Graph
        raise ValueError(f'refusing to send the token to {urllib.parse.urlsplit(url or "").hostname}')
    for i in range(10):
        time.sleep(0.5)  # ponytail: fixed pacing; OneNote throttling (429) is handled by the backoff below
        req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + tok})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 401:
                raise TokenExpired(e.read().decode('utf-8', 'replace')[:300])
            if e.code not in (429, 500, 502, 503, 504) or i == 9:
                e.detail = e.read().decode('utf-8', 'replace')[:300]
                raise
            wait = max(int(e.headers.get('Retry-After') or 0), min(300, 15 * 2 ** i))
            print(f'  {e.code} -> waiting {wait}s', flush=True)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError):
            if i == 5:
                raise
            time.sleep(5 * 2 ** i)


def items(url, tok):
    while url:
        d = json.loads(get(url, tok))
        yield from d['value']
        url = d.get('@odata.nextLink')


def walk(tok, base, path):
    for s in items(base + '/sections', tok):
        yield path + [s['displayName']], s
    for g in items(base + '/sectionGroups', tok):
        yield from walk(tok, f'{G}/sectionGroups/{g["id"]}', path + [g['displayName']])


def rid(url):
    m = re.search(r'/resources/([^/]+)/', url or '')
    return safe(m.group(1)) if m else hashlib.sha1((url or '').encode()).hexdigest()[:16]


def render(html, save):
    """OneNote page HTML -> Markdown. save(url, filename) returns the local relative link."""
    soup = BeautifulSoup(html, 'html.parser')
    for img in soup.find_all('img'):
        url = img.get('data-fullres-src') or img.get('src')
        if url and '/resources/' in url:
            mime = img.get('data-fullres-src-type') or img.get('data-src-type') or ''
            img['src'] = save(url, rid(url) + (mimetypes.guess_extension(mime) or '.png'))
    for o in soup.find_all('object'):
        name = o.get('data-attachment') or 'attachment'
        fname = re.sub(r'[()\[\]]', '_', re.sub(r'\s+', '_', safe(name)))  # spaces/brackets break md links
        a = soup.new_tag('a', href=save(o.get('data'), rid(o.get('data')) + '_' + fname))
        a.string = '📎 ' + name
        o.replace_with(a)
    for t in soup.select('[data-tag]'):
        if 'to-do' in t['data-tag']:
            t.insert(0, '[x] ' if 'completed' in t['data-tag'] else '[ ] ')
    md = markdownify(str(soup.body or soup), heading_style='ATX', bullets='-', table_infer_header=True,
                     escape_underscores=False, escape_asterisks=False)  # keep identifiers greppable
    return re.sub(r'\n{3,}', '\n\n', md).strip()


def load_state(out):
    f = out / '_state.json'
    return json.loads(f.read_text(encoding='utf-8')) if f.exists() else {}


def save_state(out, st):
    tmp = out / '_state.json.tmp'  # write-then-rename: a killed run never leaves a truncated state
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding='utf-8')
    tmp.replace(out / '_state.json')


def write_index(out, st, fails, gone):
    tree = {}
    for p in st.values():
        tree.setdefault(p['section'], []).append(p)
    lines = [f'# OneNote export ({date.today()})', '',
             "- One `.md` per page. Images/attachments in each section's `_files/`, original HTML in `_raw/`.",
             '- Refresh: rerun the exporter; only changed pages are downloaded again.',
             '- ⚠️ May contain sensitive content (e.g. formerly password-protected sections). '
             'Do not share, upload or commit this folder.', '']
    for sec in sorted(tree):
        pages = sorted(tree[sec], key=lambda p: p['order'])
        lines.append(f'## {sec} ({len(pages)})')
        for p in pages:
            lines.append(f'{"  " * p["level"]}- [{p["title"] or "(untitled)"}](<{p["path"]}>) · {p["modified"][:10]}')
        lines.append('')
    if gone:
        lines += ['## Removed in OneNote (kept locally)', ''] + [f'- <{g}>' for g in gone] + ['']
    if fails:
        lines += ['## Failures', ''] + [f'- {f}' for f in fails]
    (out / 'INDEX.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def unique_path(st, pid, sdir, title):
    """'Title.md', or 'Title (2).md'… if another page (incl. ones removed upstream) already owns the name."""
    taken = {p['path'].lower() for i, p in st.items() if i != pid}  # case-insensitive file systems
    base = (sdir / safe(title)).as_posix()
    rel, k = base + '.md', 2
    while rel.lower() in taken:
        rel, k = f'{base} ({k}).md', k + 1
    return rel


def export(tok, out, only):
    out.mkdir(parents=True, exist_ok=True)
    st, fails, seen, failed_secs, done = load_state(out), [], set(), set(), False
    try:
        for nb in items(f'{G}/notebooks', tok):
            if only and not any(o.split('/')[0] == nb['displayName'] for o in only):
                continue
            for path, sec in walk(tok, f'{G}/notebooks/{nb["id"]}', [nb['displayName']]):
                if only and not any('/'.join(path + ['']).startswith(o.rstrip('/') + '/') for o in only):
                    continue
                label = ' / '.join(path)
                sdir = Path(*map(safe, path))
                try:
                    pages = sorted(items(f'{G}/sections/{sec["id"]}/pages?pagelevel=true&$top=100', tok),
                                   key=lambda p: p.get('order', 0))
                except urllib.error.HTTPError as e:
                    fails.append(f'{label}: cannot open section {e.code} {getattr(e, "detail", "")}')
                    failed_secs.add(label)
                    print('FAIL', label, e.code, flush=True)
                    continue
                new = 0
                for n, pg in enumerate(pages, 1):
                    seen.add(pg['id'])
                    old = st.get(pg['id'])
                    if (old and old['modified'] == pg['lastModifiedDateTime'] and old['section'] == label
                            and (out / old['path']).exists()):
                        old.update(order=n, level=pg.get('level', 0))  # order lives in INDEX, not file names
                        continue
                    if old and old['section'] == label and old['title'] == pg.get('title'):
                        rel = old['path']  # file names are stable once assigned
                    else:
                        rel = unique_path(st, pg['id'], sdir, pg.get('title'))
                    try:
                        html = get(f'{G}/pages/{pg["id"]}/content', tok).decode('utf-8')
                    except urllib.error.HTTPError as e:
                        fails.append(f'{label} / {pg.get("title")}: {e.code} {getattr(e, "detail", "")}')
                        continue

                    def save(url, fname):
                        if not is_graph(url):  # external link: keep as is, never fetch with the token
                            return url or ''
                        f = out / sdir / '_files' / fname
                        if not (f.exists() and f.stat().st_size):
                            try:
                                data = get(url, tok)
                            except urllib.error.HTTPError as e:
                                fails.append(f'{label} / {pg.get("title")}: resource {fname} {e.code}')
                                return url
                            f.parent.mkdir(parents=True, exist_ok=True)
                            f.write_bytes(data)
                        return f'_files/{fname}'

                    body = render(html, save)
                    head = [f'# {pg.get("title") or "(untitled)"}', '',
                            f'- Location: {label}' + (f' (subpage level {pg["level"]})' if pg.get('level') else ''),
                            f'- Created: {pg["createdDateTime"]} · Modified: {pg["lastModifiedDateTime"]}',
                            f'- Source: {pg.get("links", {}).get("oneNoteWebUrl", {}).get("href", "")}', '', '---', '', '']
                    (out / rel).parent.mkdir(parents=True, exist_ok=True)
                    (out / rel).write_text('\n'.join(head) + body + '\n', encoding='utf-8')
                    raw = out / '_raw' / Path(rel).with_suffix('.html')
                    raw.parent.mkdir(parents=True, exist_ok=True)
                    raw.write_text(html, encoding='utf-8')
                    if old and old['path'] != rel and (out / old['path']).exists():
                        (out / old['path']).unlink()
                    st[pg['id']] = dict(path=rel, section=label, title=pg.get('title'), order=n,
                                        level=pg.get('level', 0), modified=pg['lastModifiedDateTime'])
                    save_state(out, st)
                    new += 1
                print(f'{label}: {len(pages)}p (+{new})', flush=True)
        done = True
    finally:
        gone = sorted(p['path'] for i, p in st.items()
                      if i not in seen and p['section'] not in failed_secs) if done and not only else []
        save_state(out, st)
        write_index(out, st, fails, gone)
        (out / '_failures.md').write_text('# Failures\n\n' + ''.join(f'- {f}\n' for f in fails), encoding='utf-8')
    return fails, gone


def rerender(out):
    """Conversion rules changed: rebuild every .md from _raw HTML (no network; uses already-saved files)."""
    for p in load_state(out).values():
        md = out / p['path']
        head = md.read_text(encoding='utf-8').split('\n---\n', 1)[0]
        html = (out / '_raw' / Path(p['path']).with_suffix('.html')).read_text(encoding='utf-8')
        md.write_text(head + '\n---\n\n' + render(html, lambda url, f: f'_files/{f}') + '\n', encoding='utf-8')
    print('rerender ok')


def verify(out):
    """State <-> disk, and every _files link in the .md points to an existing non-empty file."""
    st, bad = load_state(out), []
    for p in st.values():
        md = out / p['path']
        if not md.exists():
            bad.append(f'missing: {p["path"]}')
            continue
        for link in re.findall(r'\]\((_files/[^)\s]+)\)', md.read_text(encoding='utf-8')):
            f = md.parent / link
            if not (f.exists() and f.stat().st_size):
                bad.append(f'broken link: {p["path"]} -> {link}')
    print(f'pages {len(st)} · sections {len({p["section"] for p in st.values()})} · problems {len(bad)}',
          *bad[:20], sep='\n')
    return 1 if bad else 0


def clipboard():
    """(clipboard text, function that clears the clipboard)."""
    if sys.platform == 'win32':
        import tkinter  # ships with Python on Windows
        tk = tkinter.Tk()
        tk.withdraw()
        try:
            text = tk.clipboard_get()
        except tkinter.TclError:  # empty or non-text clipboard
            text = ''

        def clear():
            tk.clipboard_clear()
            tk.update()
            tk.destroy()
        return text, clear
    if sys.platform == 'darwin':
        paste, wipe = ['pbpaste'], ['pbcopy']
    elif shutil.which('wl-paste'):
        paste, wipe = ['wl-paste', '-n'], ['wl-copy', '--clear']
    else:
        paste, wipe = ['xclip', '-o', '-selection', 'clipboard'], ['xclip', '-i', '-selection', 'clipboard']
    try:
        text = subprocess.run(paste, capture_output=True, text=True, encoding='utf-8', errors='replace').stdout
    except FileNotFoundError:
        sys.exit(f'Clipboard tool not found: {paste[0]}')
    return text, lambda: subprocess.run(wipe, input='', text=True)


def read_token():
    text, clear = clipboard()
    tok = text.strip().removeprefix('Bearer ')
    if len(tok) < 100 or not tok.isascii() or any(c.isspace() for c in tok):
        return None  # not a token: leave whatever the user copied untouched
    clear()  # don't leave the token on the clipboard
    return tok


def selftest():
    html = ('<html><head><title>t</title></head><body><div><p data-tag="to-do:completed">done</p>'
            '<p data-tag="to-do">todo</p><img src="https://g/onenote/resources/0-ab!1-cd/$value" data-src-type="image/png">'
            '<object data-attachment="report (final) v2.pdf" type="application/pdf" '
            'data="https://g/onenote/resources/0-ef/$value"></object>'
            '<p>ss_no_override **x**</p><table><tr><td>a</td><td>b</td></tr></table></div></body></html>')
    got = []
    md = render(html, lambda url, f: got.append(url) or f'_files/{f}')
    assert '[x] done' in md and '[ ] todo' in md, md
    assert '](_files/0-ab!1-cd.png)' in md, md
    assert '[📎 report (final) v2.pdf](_files/0-ef_report__final__v2.pdf)' in md, md
    assert '| a | b |' in md and 't\n' not in md, md
    assert 'ss_no_override **x**' in md, md
    assert len(got) == 2
    assert safe('a/b:c?') == 'a_b_c_' and safe('  ') == '(untitled)'
    assert safe('CON') == '_CON' and safe('nul.txt') == '_nul.txt' and safe('x' * 79 + ' y') == 'x' * 79
    assert is_graph('https://graph.microsoft.com/v1.0/x') and not is_graph('https://evil.example/resources/1/$value')
    assert not is_graph('http://graph.microsoft.com/x') and not is_graph('https://graph.microsoft.com.evil.example/x')
    assert not is_graph(None)
    assert rid('https://x/y?z') == rid('https://x/y?z') and len(rid('https://x/y?z')) == 16
    with tempfile.TemporaryDirectory() as d:  # utf-8 round trip + index + verify on a fake export
        out = Path(d)
        rel = 'Notizbuch/섹션/001_日本語.md'
        (out / 'Notizbuch/섹션/_files').mkdir(parents=True)
        (out / 'Notizbuch/섹션/_files/a.png').write_bytes(b'x')
        (out / rel).write_text('# 日本語\n\n---\n\n![](_files/a.png) ü', encoding='utf-8')
        save_state(out, {'p1': dict(path=rel, section='Notizbuch / 섹션', title='日本語', order=1, level=0,
                                    modified='2026-01-01T00:00:00Z')})
        write_index(out, load_state(out), [], [])
        assert f'(<{rel}>)' in (out / 'INDEX.md').read_text(encoding='utf-8')
        assert verify(out) == 0
        (out / 'Notizbuch/섹션/_files/a.png').unlink()
        assert verify(out) == 1
    selftest_export()
    print('selftest ok')


def selftest_export():
    """export() against a fake Graph: incremental skip, same-title pages, reorder, edits, removals."""
    spec, fetched = {}, []

    def fake_get(url, tok):
        assert is_graph(url), url
        u = url.split('/me/onenote', 1)[1]
        part = u.split('/')
        js = lambda v: json.dumps({'value': v}).encode()
        if u == '/notebooks':
            return js([{'id': 'nb', 'displayName': 'NB'}])
        if u == '/notebooks/nb/sections':
            return js([{'id': s, 'displayName': s} for s in spec])
        if u.endswith('/sectionGroups'):
            return js([])
        if part[1] == 'sections':
            return js([dict(id=i, title=t, order=n, lastModifiedDateTime=m, createdDateTime=m)
                       for n, (i, t, m) in enumerate(spec[part[2]])])
        if part[1] == 'pages':
            fetched.append(part[2])
            return (f'<html><body><p>id-{part[2]}</p><img src="{G}/resources/r1/$value">'
                    '<img src="https://evil.example/resources/r2/$value"></body></html>').encode()
        return b'png'

    def run(pages):
        spec.clear(); spec.update(pages); fetched.clear()
        export('t', out, [])
        return load_state(out)

    real_get, globals()['get'] = get, fake_get
    try:
        with tempfile.TemporaryDirectory() as d:
            out, v1, v2 = Path(d), '2026-01-01T00:00:00Z', '2026-02-01T00:00:00Z'
            st = run({'A': [('p1', 'Meet', v1), ('p2', 'Meet', v1)]})
            assert fetched == ['p1', 'p2'] and [st[i]['path'] for i in ('p1', 'p2')] == ['NB/A/Meet.md', 'NB/A/Meet (2).md']
            md = (out / 'NB/A/Meet.md').read_text(encoding='utf-8')
            assert 'id-p1' in md and '](_files/r1.png)' in md and 'https://evil.example/' in md, md
            st = run({'A': [('p1', 'Meet', v1), ('p2', 'Meet', v1)]})
            assert fetched == []
            st = run({'A': [('p3', 'Meet', v1), ('p2', 'Meet', v1), ('p1', 'Meet', v1)]})  # new on top + reorder
            assert fetched == ['p3'] and st['p3']['path'] == 'NB/A/Meet (3).md' and st['p1']['order'] == 3
            assert all(f'id-{i}' in (out / p['path']).read_text(encoding='utf-8') for i, p in st.items())
            st = run({'A': [('p3', 'Meet', v1), ('p1', 'Meet', v2)]})  # p2 removed upstream, p1 edited
            assert fetched == ['p1'] and st['p1']['path'] == 'NB/A/Meet.md' and (out / 'NB/A/Meet (2).md').exists()
            assert '- <NB/A/Meet (2).md>' in (out / 'INDEX.md').read_text(encoding='utf-8')
            assert verify(out) == 0
    finally:
        globals()['get'] = real_get


def main():
    sys.stdout.reconfigure(errors='replace')  # non-UTF-8 consoles must not crash on emoji/CJK titles
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, default=Path('onenote'), help='output folder (default: ./onenote)')
    ap.add_argument('--only', nargs='+', default=[], metavar='NOTEBOOK[/GROUP/SECTION]',
                    help='limit to these notebooks or section paths')
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--verify', action='store_true', help='check the export on disk (offline)')
    mode.add_argument('--rerender', action='store_true', help='rebuild .md from _raw HTML (offline)')
    mode.add_argument('--selftest', action='store_true', help='run built-in checks')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.verify:
        return verify(a.out)
    if a.rerender:
        return rerender(a.out)
    tok = read_token()
    if not tok:
        print('No access token on the clipboard. Graph Explorer -> Access token tab -> copy, then rerun.')
        return 2
    print(f'Exporting to {a.out.resolve()}', flush=True)
    try:
        fails, gone = export(tok, a.out, a.only)
    except TokenExpired as e:
        hint = (' Notes.Read is not consented: Graph Explorer -> Modify permissions -> Notes.Read -> Consent.'
                if '40001' in str(e) else '')
        print(f'401 Unauthorized: token expired or invalid.{hint} Copy a fresh token and rerun the same command.')
        return 2
    print(f'Done. failures {len(fails)} (see _failures.md) · removed in OneNote {len(gone)} (listed in INDEX.md)')


if __name__ == '__main__':
    sys.exit(main())
