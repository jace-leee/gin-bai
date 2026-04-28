# gin-bai

<p align="center">
  <img src="assets/readme.png" alt="gin-bai" width="240">
</p>

> GitHub 레포 → graphify 클러스터링 + git 히스토리 + 디자인 문서 인테이크 → god-node 점수로 라우팅된 딥다이브 서브에이전트 → Obsidian 볼트 안에 만들어지는 Karpathy 스타일 LLM 위키 (철학 & 불변식 페이지 포함).

---

## 개요

> 긴빠이는 해병대의 유구한 문화로써, 옆 소대 빨래줄에 걸린 전투복부터 행정반 책상 위 믹스커피 한 봉지까지 **"필요하면 챙긴다"**는 숭고한 정신을 담고 있다. 본디 윗선에 들키지 않고, 흔적 없이, 그러나 확실하게 가져오는 것이 핵심이다.

`gin-bai`는 이 정신을 21세기 소프트웨어 엔지니어링에 이식한 도구다.

GitHub에 흩뿌려진 남의 레포에서 **지식만 쏙 빼다가** 내 Obsidian 볼트로 옮겨오는 Claude Code 슬래시 커맨드. 클론한 레포는 임무 완수 후 **흔적 없이 자결**(ephemeral cleanup)하고, 알맹이 — README 분석, git 히스토리, 디자인 철학, 클러스터별 딥다이브, 하네스 배선도, 파이프라인 추적 — 만 볼트에 차곡차곡 정렬되어 남는다.

요약하자면:

- **들키지 않고** — 레포는 임시 디렉터리에서만 살다 죽음. 디스크에 흔적 0.
- **흔적 없이** — 클론 경로는 실행 종료 시 `rm -rf`. 남는 건 위키뿐.
- **확실하게** — graphify가 god-node를 짚어주고, opus/sonnet/haiku 서브에이전트가 가치에 비례한 분량으로 핵심을 약탈해온다.

선임이 묻거든 "공부 좀 했습니다"라고 답하면 된다. 위키가 증거로 남으니까.

---

## 동작 방식

GitHub URL이 주어지면 `gin-bai`는 다음 단계를 수행합니다.

1. **클론** — 임시 디렉터리로 `--depth=500` shallow / single-branch 클론 (히스토리 분석이 의미 있을 정도의 깊이).
2. **README + 매니페스트 + 디자인 문서 인테이크** — `package.json`, `pyproject.toml`, `Cargo.toml` 등 매니페스트 한 개와 README, 그리고 `CLAUDE.md`, `AGENTS.md`, `ARCHITECTURE.md`, `DESIGN.md`, `CONTRIBUTING.md`, `ROADMAP.md`, ADR/`docs/architecture/`, `docs/design/`, `docs/adr/` 트리를 함께 읽어 한 페이지짜리 오리엔테이션 노트와 디자인 문서 인덱스(`design_docs.json`) 작성.
3. **Claude Code 하네스 감지** — `.claude/commands`, `.claude/agents`, `.claude/skills`, `settings.json`, `mcp.json` 등을 탐지해 **command → agent → skill → hook** 배선 맵을 결정론적으로 추출.
4. **Git 히스토리 추출** — 최근 12개월 커밋 케이던스, 상위 기여자, 릴리스 태그 타임라인, BREAKING / 마이그레이션 / 리라이트 커밋, hot files(가장 자주 수정된 경로 상위 20), 커밋 메시지 컨벤션(Conventional / Gitmoji / Issue-tagged / freeform)을 `history_analysis.md`로 정리.
5. **클러스터링** — [`graphify`](https://pypi.org/project/graphifyy/)로 코드베이스를 커뮤니티로 묶고, 각 커뮤니티의 god-node(핵심 파일/심볼)를 식별.
6. **클러스터 캡 + 모델 라우팅** — 클러스터가 10개를 넘으면 god-score 상위 10개만 1급으로 두고 나머지는 단일 `Misc` 클러스터로 합쳐 haiku 한 번으로 처리. 라우팅은 opus를 단 하나(최상위 god-cluster)에만 예약:
   - `top 1 by god score` → **opus** *(god-cluster, 정확히 1개)*
   - `median ≤ score < top` → **sonnet**
   - `score < median` → **haiku**
   - `Misc (merged tail)` → **haiku**
7. **딥다이브 서브에이전트 병렬 실행** — 커뮤니티마다 한 개씩, **단일 메시지에서 모두 동시에** 호출 (Step 6 Parallel Execution Contract). 각 에이전트는 책임 범위 / 공개 인터페이스 / 불변식 / 내부 흐름 / 리스크 / 교차 참조 + **Design philosophy & invariants**(인용 필수, 추측 금지) 섹션을 담은 180~280줄짜리 마크다운을 생성. 클론이 살아있는 동안 `git log --follow`, `git blame`도 활용 가능.
8. **위키 합성** — 상위 페이지들 작성:
   - `index.md` — 모든 페이지를 한 줄로 요약하는 Karpathy 스타일 카탈로그.
   - `pipeline.md` — 한 번의 요청(또는 하네스라면 한 번의 사용자 호출) 흐름을 클러스터를 가로질러 추적, 끝에 cross-cutting principles 스냅샷 포함.
   - `philosophy.md` — 모든 클러스터의 철학 섹션을 cross-cutting / cluster-specific / stated-but-not-observed 세 그룹으로 합성. **모든 주장에 인용 필수**.
   - `log.md` — append-only 인제스트 히스토리.
9. **클린업** — 임시 클론 디렉터리 삭제.

---

## 설치

`gin-bai`는 Claude Code 슬래시 커맨드로 동작합니다. `gin-bai.md`를 프로젝트 또는 사용자 단위 커맨드 디렉터리에 배치하세요.

```
.claude/commands/gin-bai.md
```

요구 사항:

- [Claude Code](https://claude.com/claude-code)
- `git`
- `python3` + [`graphifyy`](https://pypi.org/project/graphifyy/) (최초 실행 시 자동 설치 시도)
- Obsidian 볼트 — 경로는 자유. `GIN_BAI_VAULT` 환경 변수 또는 커맨드의 `VAULT_ROOT` 상수만 본인 환경에 맞게 수정하면 됩니다.

설치 후 `GIN_BAI_VAULT` 환경 변수를 본인 볼트 경로로 지정하거나, `.claude/commands/gin-bai.md` 상단의 `VAULT_ROOT` 기본값을 바꿔주세요. (자세한 내용은 [설정](#설정) 참고)

---

## 사용법

```
/gin-bai <github-url>
```

지원하는 URL 형태:

- `https://github.com/owner/repo`
- `https://github.com/owner/repo.git`
- `git@github.com:owner/repo.git`
- `owner/repo` (단축형)

인자 없이 `/gin-bai`만 입력하면 한 번 묻고 멈춥니다.

### 예시

```
/gin-bai anthropics/claude-code
```

출력:

```
Ingesting anthropics/claude-code → <VAULT>/gin-bai/anthropics__claude-code

Community 0 (Auth Layer)        score=4.21  → opus    [god-cluster]
Community 1 (Data Loading)      score=2.10  → sonnet
Community 2 (CLI Entrypoints)   score=0.40  → haiku
Misc (3 small clusters)         score=0.05  → haiku   [merged tail]

Spawning 4 deep-dive subagents in parallel: Auth Layer, Data Loading, CLI Entrypoints, Misc
…

Wiki: <VAULT>/gin-bai/anthropics__claude-code
  index.md             — 여기서 시작
  README_analysis.md   — 스택, 엔트리포인트, stated principles
  history_analysis.md  — git 히스토리 스냅샷
  pipeline.md          — 엔드투엔드 흐름
  philosophy.md        — 인용 포함 디자인 원칙
  communities/         — N개의 딥다이브
  log.md               — 인제스트 히스토리
  .graphify/           — 원본 그래프 + 리포트
```

---

## 산출물 구조

```
<VAULT>/gin-bai/<owner>__<repo>/
├── index.md                # 카탈로그 — 여기부터 읽기
├── README_analysis.md      # 스택, 엔트리포인트, 빌드/테스트, stated principles
├── history_analysis.md     # 기여자, 케이던스, 릴리스, hot files, notable commits
├── pipeline.md             # 클러스터 간 흐름 추적 + cross-cutting 스냅샷
├── philosophy.md           # 디자인 원칙 (인용 포함, 추측 제외)
├── harness_map.md          # (Claude Code 하네스로 감지된 경우에만)
├── communities/
│   ├── <slug-1>.md         # frontmatter 포함 딥다이브 (model, god_score, …)
│   └── …
├── log.md                  # append-only 인제스트 히스토리
└── .graphify/
    ├── graph.json
    ├── analysis.json
    ├── labels.json
    ├── design_docs.json    # 디자인 문서 인덱스
    ├── GRAPH_REPORT.md
    └── graph.html          # 인터랙티브 시각화
```

같은 레포에 다시 돌리면 `log.md`를 제외한 모든 파일이 덮어써지고, `log.md`에는 새 엔트리가 추가됩니다.

---

## 하네스 모드

대상 레포가 Claude Code 플러그인, 하네스, 에이전트 키트(예: `oh-my-claudecode`, 플러그인 마켓플레이스, 커맨드를 번들한 MCP 서버 등)인 경우 `gin-bai`는 **하네스 모드**로 전환됩니다.

- `.claude/commands/`, `.claude/agents/`, `.claude/skills/` 아래 모든 `.md`를 순회하며 YAML frontmatter에서 `name`, `description`, `model`, `tools`, `trigger`를 추출.
- `settings.json`에서 hook 이벤트, `mcp.json`에서 MCP 서버 정보를 파싱.
- `harness_map.md`에 모든 표와 함께 `Cross-References` 엣지 리스트(`/foo → agent:executor`, `agent:executor → skill:simplify`, …) 기록.
- `pipeline.md`는 **한 번의 사용자 호출**을 추적하는 형태로 작성됨 (슬래시 커맨드 → pre-hooks → 에이전트 오케스트레이션 → 스킬 → post-hooks → 상태 영속화 → 실패 모드).
- 각 딥다이브의 공개 인터페이스는 함수가 아니라 슬래시 커맨드 / 에이전트 / 스킬로 표현되며, `[[command/foo]]`, `[[agent/executor]]`, `[[skill/autopilot]]` 위키링크로 `harness_map.md` 행과 상호 연결됩니다.

이 단계 덕분에 import 그래프가 아니라 마크다운 frontmatter와 JSON 설정 안에 숨어있는 **하중을 받는 토폴로지**(load-bearing topology)를 놓치지 않습니다. 순수 AST 클러스터러로는 보이지 않는 부분이죠.

---

## 병렬 실행 계약 (Step 6)

이 커맨드의 #1 역사적 실패 모드는 "병렬이라고 적혀있어도 순차로 돌아간다"는 점이었습니다. v2는 이를 **하드 컨트랙트**로 강제합니다:

- 스폰 직전 단 한 줄의 검증 핸드셰이크: `Spawning N deep-dive subagents in parallel: <c1>, <c2>, …`
- 다음 어시스턴트 메시지는 **N개의 `Agent` 툴 호출 + 0줄의 텍스트**. 산문 한 줄도 위반.
- "일단 3개 먼저 띄우고 다음 4개" 같은 배치 분할 금지. `run_in_background: true` 금지(Step 7가 동기 출력 필요).
- 클러스터 캡 ≤ 10 + Misc로 fan-out 폭을 11 이내로 제한.

순차 N=12는 18분, 병렬 N=12는 약 2분. 사용자가 차이를 알아챕니다.

---

## 설정

환경 변수 `GIN_BAI_VAULT`로 볼트 경로를 지정하거나, `.claude/commands/gin-bai.md` 상단의 기본값을 수정하세요.

```bash
# 기본값
VAULT_ROOT="${GIN_BAI_VAULT:-$HOME/Documents/ObsidianVault}"
GIN_BAI_ROOT="$VAULT_ROOT/gin-bai"

# 예: 기존 노트 폴더를 쓰는 경우
export GIN_BAI_VAULT="$HOME/Desktop/note"
```

레포는 각자 자기 폴더로 들어갑니다: `$GIN_BAI_ROOT/<owner>__<repo>/`.

> **Tip.** Obsidian을 쓰지 않더라도 그냥 마크다운 폴더로 동작합니다. VS Code의 [Foam](https://foambubble.github.io/), [Logseq](https://logseq.com/), [Dendron](https://www.dendron.so/) 등 위키 링크(`[[…]]`)를 인식하는 도구라면 어디든 OK.

---

## 실패 처리

| 상황 | 동작 |
|------|------|
| 클론 실패 | 중단 후 새로 만든 볼트 폴더 삭제, 로그 미기록. |
| 커밋 히스토리 없음 (`COMMITS == 0`) | `history_analysis.md`에 한 줄만 기록 후 계속 진행. |
| graphify가 빈 그래프 반환 | `EMPTY.md` 한 장 작성 후 클린업, 로그에 `Notes: empty graph` 추가. |
| 서브에이전트 실패 | `communities/<slug>.md`에 "rerun /gin-bai to retry" placeholder만 남기고 `philosophy.md` 합성 시 해당 클러스터 스킵, 로그에 누락 기재. |
| 클린업 실패 | 정확한 경로를 함께 경고만 출력 (수동으로 `rm -rf`). 실행 자체는 중단하지 않음. |

---

## 이름의 유래

이중 펀(pun)입니다.

- **긴빠이** — 군대 슬랭. "필요하면 챙겨온다." (위 [개요](#개요) 참고)
- **김밥** — 작은 재료들이 한 줄로 말려 한입에 들어가는 것처럼, 수많은 파일과 서브에이전트가 한 권의 위키로 말려 들어간다.

발음 따라 골라 읽으세요.

---

## 기여하기

이슈 / PR 환영합니다. 큰 변경은 먼저 이슈로 논의해주세요.

작업 영역 아이디어:

- 다른 클러스터링 백엔드 지원 (graphify 외)
- 비-Obsidian 위키 포맷 출력 어댑터
- 추가 하네스 패턴 감지 (다른 에이전트 프레임워크의 배선)
- 캐시 / 증분 인제스트 (전체 재실행 없이 변경분만 갱신)
- 깊은 히스토리 분석 옵션 (depth=500 너머)

스타일은 기존 `.claude/commands/gin-bai.md` 톤을 따라가면 됩니다 — 결정론적 단계, 명시적 실패 처리, 부작용 최소화, 인용 가능한 합성.

---

## 크레딧

- **클러스터링 엔진** — [graphify](https://pypi.org/project/graphifyy/)
- **LLM Wiki 컨셉** — [Andrej Karpathy](https://karpathy.ai/) 의 코드베이스 위키 스펙에서 영감
- **하네스** — [Claude Code](https://claude.com/claude-code) (Anthropic)

---

## 라이선스

[MIT](LICENSE)
