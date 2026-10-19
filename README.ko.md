# onenote-export

Microsoft OneNote 노트북 **전체**를 로컬 마크다운으로 내보내는 Claude Code 플러그인입니다. 내보낸 파일은 Claude가 읽고 검색할 수 있습니다.

[English](README.md)

> 비공식 커뮤니티 프로젝트입니다. Microsoft와 관련이 없으며 Microsoft의 보증이나 지원을 받지 않습니다. OneNote와 Microsoft Graph는 Microsoft의 상표입니다.

- 페이지 하나가 `.md` 파일 하나가 됩니다.
  - 구조는 `노트북/[섹션그룹/]섹션/제목.md`입니다. 제목이 같으면 `제목 (2).md`가 됩니다.
  - OneNote 순서대로 정리된 전체 목차는 `INDEX.md`에 있습니다.
- 이미지와 첨부파일도 함께 받고, 원본 HTML도 보관합니다.
- 다시 실행하면 새로 생기거나 바뀐 페이지만 받습니다. 중간에 끊겨도 이어서 받습니다.
- **Azure 앱 등록이 필요 없습니다.** 토큰은 Microsoft 공식 [Graph Explorer](https://developer.microsoft.com/graph/graph-explorer)에서 받습니다. 권한은 읽기 전용 `Notes.Read`입니다.
- 개인 Microsoft 계정에서 동작합니다. 회사·학교 계정도 테넌트가 Graph Explorer를 허용하면 됩니다.

## 왜 필요한가
- OneNote에는 "전체 내보내기" 버튼이 없습니다. 노트북 전체를 PDF로 내보낼 수도 없고, 웹 버전은 페이지를 다른 도메인의 iframe 안에 보여 줍니다.
- Microsoft Graph OneNote API로는 전부 읽을 수 있습니다. 하지만 토큰이 필요하고, 페이지가 많으면 요청 제한이 심합니다.
- 이 플러그인이 두 문제를 모두 처리하고, 필요한 단계는 Claude가 안내합니다.

## 설치
Claude Code에서 실행합니다:
```
/plugin marketplace add alldaycoding21/claude-onenote-export
/plugin install onenote-export@onenote-export
```
- 로컬 사본에서 설치하려면 `/plugin marketplace add ./claude-onenote-export`.

필요한 것:
- **내 컴퓨터의 Claude Code** (CLI 또는 데스크톱 앱). 로컬 클립보드와 파일을 써야 해서 claude.ai 채팅이나 Cowork에서는 동작하지 않습니다.
- Python 3.9 이상
- [`uv`](https://docs.astral.sh/uv/) 권장 (없으면 스킬이 venv를 만듭니다)
- 데스크톱 클립보드: macOS, Windows, 또는 `wl-clipboard`/`xclip`이 있는 Linux

## 사용
Claude에게 "원노트 전체를 ./onenote에 백업해줘"라고 말하거나 `/onenote-export:export`를 실행합니다. Claude가 다음을 진행합니다.
1. 토큰을 클립보드에 복사해 달라고 요청합니다(아래). 토큰은 채팅에 붙여넣지 않습니다.
2. 내보내기를 백그라운드에서 실행하고 진행 상황을 알려 줍니다.
3. 암호 섹션 처리를 안내하고, 결과를 검증하고, `CLAUDE.md`에 위치를 기록할지 묻습니다.

### 토큰 받기 (직접 하는 부분, 1분 정도)
1. [Graph Explorer](https://developer.microsoft.com/graph/graph-explorer)를 열고, 오른쪽 위에서 노트북 주인 Microsoft 계정으로 **로그인**합니다.
2. 처음 한 번만: **Modify permissions**를 열어 **Notes.Read**를 찾고 **Consent**를 누른 뒤, Microsoft 창에서 수락합니다.
3. `GET https://graph.microsoft.com/v1.0/me/onenote/notebooks`로 **Run query**를 누릅니다. `OK - 200`과 내 노트북 목록이 보이면 됩니다.
4. **Access token** 탭에서 **복사** 아이콘을 누르고, Claude에게 "복사함"이라고 말합니다.

토큰은 약 1시간 유효합니다. Claude가 새 토큰을 달라고 하면 Graph Explorer를 새로고침하고 **Run query**를 누른 뒤 다시 복사하세요. 멈춘 곳부터 이어서 받습니다.

### 속도 제한
OneNote는 요청이 수백 건을 넘으면 강하게 제한합니다(429, 요청마다 15초~5분 대기). 수백 페이지면 몇 시간이 걸릴 수 있습니다.

### 갱신과 활용
- **갱신:** 다시 "원노트 갱신해줘"라고 하면 새로 생기거나 바뀐 페이지만 받습니다.
- **활용:** "원노트에서 예산 관련 메모 찾아줘"처럼 물어보면 Claude가 `INDEX.md`와 페이지를 검색합니다. `CLAUDE.md`에 위치를 기록해 두면 다음 세션에서도 바로 찾습니다.

문제가 생기면 [문제 해결 문서](skills/export/references/troubleshooting.md)(영문)를 보세요.

## 결과물
```
onenote/
  INDEX.md                 섹션 → 페이지, 수정일, OneNote에서 지운 페이지, 실패 목록
  <노트북>/<섹션>/<제목>.md       제목이 같으면 "<제목> (2).md"; 순서가 바뀌어도 이름은 그대로
  <노트북>/<섹션>/_files/      이미지·첨부
  _raw/…/*.html            원본 HTML (오프라인 재변환용)
  _state.json              페이지 id → 경로·수정 시각 (증분 갱신에 사용, 지우지 마세요)
  _failures.md             마지막 실행의 문제 목록
```
각 페이지 맨 위에는 위치, 만든 시각과 수정 시각, OneNote로 돌아가는 `Source:` 링크가 있습니다.

## Claude 없이 실행
Graph Explorer에서 토큰을 복사한 뒤 실행합니다:
```
uv run --locked skills/export/scripts/onenote_export.py --out ./onenote
uv run --locked skills/export/scripts/onenote_export.py --out ./onenote --only "노트북" "노트북/그룹/섹션"
uv run --locked skills/export/scripts/onenote_export.py --out ./onenote --verify
```
종료 코드 2는 유효한 토큰이 없다는 뜻입니다. 다시 복사하고 같은 명령을 실행하세요.

## 업데이트·삭제
```
claude plugin update onenote-export@onenote-export
claude plugin uninstall onenote-export@onenote-export
```
Claude Code 안에서는 `/plugin` 메뉴로도 할 수 있습니다. 플러그인을 지워도 내보낸 노트는 지워지지 않습니다.

## 한계
- **암호 보호 섹션:** 잠금을 풀어도 API로 읽을 수 없습니다. 암호를 잠시 **제거**하고 동기화한 뒤 `--only`로 받고, 바로 다시 암호를 거세요.
- 손글씨, 이미지 속 글자, 임베드 동영상은 텍스트로 변환되지 않습니다.
- OneNote에서 지운 페이지는 로컬에 남기고 `INDEX.md`에 표시합니다.
- SharePoint와 Teams 그룹 노트북은 대상이 아닙니다.
- macOS와 개인 계정에서 검증했습니다. Windows와 Linux 클립보드 경로는 구현만 되어 있고 실기 테스트 전입니다.

## 실행·읽기·전송·저장하는 것
- **실행:** 공개 소스 Python 스크립트 하나(`skills/export/scripts/onenote_export.py`).
  - uv가 있으면 `uv run --locked`로 실행합니다. 의존성 버전은 `onenote_export.py.lock`에 고정되어 있고 PyPI에서 받습니다(markdownify 1.2.3, beautifulsoup4 4.15.0).
  - uv가 없으면 같은 버전으로 venv를 만들어 실행합니다.
- **읽기:**
  - 실행할 때마다 클립보드를 한 번 읽습니다(macOS `pbpaste`, Windows는 Python 내장 tkinter, Linux `wl-paste` 또는 `xclip`).
  - 토큰처럼 보일 때만 클립보드를 비우고, 다른 내용이면 그대로 둡니다.
  - 내 OneNote 노트북·섹션·페이지와 이미지·첨부를 읽습니다.
- **전송:** `https://graph.microsoft.com`(Microsoft Graph OneNote API)으로 HTTPS `GET` 요청만 보냅니다.
  - 다른 서버, 사용 통계, 분석 기능은 없습니다.
  - OneNote의 내용을 만들거나 바꾸거나 지우지 않습니다.
- **저장:** 사용자가 고른 출력 폴더 안에만 저장합니다. 토큰은 어디에도 저장하지 않습니다.

## 보안
개인정보 처리방침 전문: [PRIVACY.md](PRIVACY.md)
- 통신은 내 PC와 `graph.microsoft.com` 사이에서만 일어납니다. 페이지 안에 다른 사이트 링크가 있어도 토큰은 그쪽으로 보내지 않습니다.
- 토큰은 클립보드에서 읽은 즉시 클립보드를 비웁니다. 출력, 로그, 파일 어디에도 남기지 않습니다.
- 내보낸 폴더에는 민감정보가 있을 수 있습니다(예: 원래 암호가 걸려 있던 섹션). 커밋하거나 공유하지 마세요.
- 권한을 회수하려면 <https://account.live.com/consent/Manage> 에서 Graph Explorer를 제거합니다(개인 계정). 회사·학교 계정은 관리자에게 요청하세요.

## 라이선스
MIT
