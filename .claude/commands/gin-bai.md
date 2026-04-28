---
name: gin-bai-v2
description: GitHub repo → graphify clusters + git history + design-doc intake → god-node-routed deep-dive subagents → karpathy LLM Wiki with philosophy & invariants page in Obsidian vault. Clone is ephemeral.
---

# /gin-bai-v2 - Repo to LLM Wiki (with philosophy & history)

Take a GitHub URL, ephemerally clone it (with bounded history), cluster it
with graphify, fan out deep-dive subagents per community (model chosen by
god-node score), and synthesize a Karpathy-style LLM Wiki into the user's
Obsidian vault.

The clone is **ephemeral** - it lives only while this command runs and is
deleted at the end. All durable artifacts live in the vault.

**What's new vs `/gin-bai` (v1):**

- Reads explicit design docs (`CLAUDE.md`, `AGENTS.md`, `ADR/`,
  `ARCHITECTURE.md`, `DESIGN.md`, `CONTRIBUTING.md`, `ROADMAP.md`).
- Extracts **git history** — contributors, cadence, tags, notable commits,
  message-style — into `history_analysis.md`.
- Subagents now produce a **Design philosophy & invariants** section
  (evidence-cited, no speculation) per cluster.
- New top-level page `philosophy.md` aggregates cross-cutting principles.
- Clone depth bumped to 500 commits so history-aware reads actually work.
- **Hard parallel-execution contract on Step 6** — past v1 runs took
  18+ minutes by spawning subagents one-at-a-time. v2 makes this a
  contract violation, requires a verification handshake line before the
  spawn, and self-checks wall-time vs. parallel expectation in `log.md`.
- **Cluster cap (≤10 + Misc) and tighter routing** — exactly 1 cluster
  gets opus (the god-cluster); tail clusters merge into a single
  haiku-routed `Misc` deep-dive. Bounds total fan-out width and wall time.
- **Subagent budget** — 180–280 lines (was 250–450), ~90s soft wall
  budget, prioritized sections so partial work is still useful.

## Usage

```
/gin-bai-v2 <github-url>
```

`$ARGUMENTS` is the GitHub URL. Accept any of:
- `https://github.com/owner/repo`
- `https://github.com/owner/repo.git`
- `git@github.com:owner/repo.git`
- `owner/repo` (shorthand)

If `$ARGUMENTS` is empty, ask the user for a URL once and stop.

## Constants

```bash
VAULT_ROOT="${GIN_BAI_VAULT:-$HOME/Documents/ObsidianVault}"
GIN_BAI_ROOT="$VAULT_ROOT/gin-bai"
```

Override via `GIN_BAI_VAULT` env var, or edit the default. Each repo gets
its own subfolder: `$GIN_BAI_ROOT/<owner>__<repo>/`.

## Step 1 - Parse URL and prepare paths

Extract `owner` and `repo` from `$ARGUMENTS`. Strip trailing `.git`.
Compute:
- `SLUG="<owner>__<repo>"`
- `WORK="/tmp/gin-bai-${SLUG}"` (ephemeral clone path)
- `VAULT="$GIN_BAI_ROOT/$SLUG"` (durable wiki path)
- `STAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)`

Print one line: `Ingesting <owner>/<repo> → $VAULT`.

If `$WORK` already exists from a previous failed run, `rm -rf "$WORK"` first.
Create `$VAULT` (`mkdir -p "$VAULT/communities" "$VAULT/.graphify"`).

## Step 2 - Ephemeral clone (bounded history)

```bash
git clone --depth=500 --single-branch "<normalized-https-url>" "$WORK" 2>&1 | tail -20
```

Depth=500 is enough for a meaningful history view on most repos while still
much faster than a full clone. If the repo has fewer than 500 commits we
just get all of them. If we want deeper analysis on a known-old repo, the
user can rerun after manually `git fetch --unshallow` inside `$WORK` — but
that's out of scope for the default flow.

If clone fails, abort, delete `$VAULT` if it was newly created, and tell the
user. Do not silently continue.

## Step 3 - README + manifest + design-doc intake

Read these files from `$WORK` if present (skip silently if absent):

**Project intake:**
- `README.md`, `README.rst`, `README` (root)
- One manifest, in priority order: `package.json`, `pyproject.toml`,
  `Cargo.toml`, `go.mod`, `pom.xml`, `build.gradle`, `Gemfile`, `composer.json`
- `LICENSE`, `.github/workflows/*.yml` (just list filenames, do not deep-read)

**Explicit design docs (new in v2):**
- `CLAUDE.md`, `AGENTS.md` (root and `.claude/`)
- `ARCHITECTURE.md`, `DESIGN.md`, `PHILOSOPHY.md`, `PRINCIPLES.md`
- `CONTRIBUTING.md`, `STYLEGUIDE.md`, `CODE_OF_CONDUCT.md`
- `ROADMAP.md`, `CHANGELOG.md`
- Any markdown under `docs/architecture*/`, `docs/design*/`,
  `docs/adr*/`, `docs/decisions*/`, `adr/`, `decisions/` (recursively)

These are the load-bearing source for "stated philosophy". They get inlined
into the subagent prompts in Step 6 and cited in `philosophy.md` in Step 7.

Write `$VAULT/README_analysis.md` containing:
- One-paragraph "what this project is" in your own words (do not copy README)
- Stack/runtime/language (from manifest)
- Entry points (from manifest `main`/`scripts`/`bin`, or guessed from layout)
- Build/test commands you'd run
- Stated principles found in design docs (one bullet per doc, cite path)
- Any non-obvious caveats spotted (license oddities, monorepo, etc.)

Keep this under 250 lines. This is the orientation page.

Also write `$VAULT/.graphify/design_docs.json` — a small JSON index so
subagents and Step 7 can find quotes deterministically:

```json
{
  "design_docs": [
    {"path": "CLAUDE.md", "size": 4203, "headings": ["Operating principles", "Delegation rules", ...]},
    {"path": "docs/adr/0001-pick-graphify.md", "size": 812, "headings": ["Status", "Context", "Decision"]},
    ...
  ]
}
```

Subagents can grep this index to know which docs are worth opening.

## Step 3b - Claude Code harness detection (deterministic)

(Unchanged from v1.)

Many target repos are Claude Code plugins, harnesses, or agent kits (e.g.
`oh-my-claudecode`, plugin marketplaces, MCP servers with bundled commands).
For these, graphify's default AST clustering misses the load-bearing
topology: **command → agent → skill → hook**. These edges live in markdown
frontmatter and `settings.json`, not in import graphs. We extract them
deterministically here and pass the result to subagents in Step 6.

### Detect

```bash
HARNESS=()
[ -d "$WORK/.claude/commands" ]     && HARNESS+=("commands:$WORK/.claude/commands")
[ -d "$WORK/.claude/agents" ]       && HARNESS+=("agents:$WORK/.claude/agents")
[ -d "$WORK/.claude/skills" ]       && HARNESS+=("skills:$WORK/.claude/skills")
[ -d "$WORK/.claude/hooks" ]        && HARNESS+=("hooks:$WORK/.claude/hooks")
[ -f "$WORK/.claude/settings.json" ] && HARNESS+=("settings:$WORK/.claude/settings.json")
[ -f "$WORK/CLAUDE.md" ]            && HARNESS+=("claude-md:$WORK/CLAUDE.md")
[ -f "$WORK/AGENTS.md" ]            && HARNESS+=("agents-md:$WORK/AGENTS.md")
[ -d "$WORK/commands" ] && [ -d "$WORK/agents" ] && HARNESS+=("plugin-root:$WORK")
[ -f "$WORK/mcp.json" ] || [ -f "$WORK/.mcp.json" ] && HARNESS+=("mcp")
```

If `HARNESS` is empty, set `IS_HARNESS=0` and proceed. Otherwise set
`IS_HARNESS=1` and run the extraction (same as v1 — produces
`harness_map.md` with command/agent/skill/hook tables and Cross-References).

See v1 spec for full extraction logic; the output format is unchanged.

## Step 3c - Git history intake (NEW in v2)

```bash
cd "$WORK"
```

Extract a compact picture of *how the repo got here*. This catches some of
the tacit knowledge that pure code/docs reads miss — e.g. "this used to be
X, then got rewritten" shows up as a `feat:` or `BREAKING:` commit cluster.

### Probe

```bash
COMMITS=$(git rev-list --count HEAD 2>/dev/null || echo 0)
SHALLOW=$([ -f .git/shallow ] && echo "true" || echo "false")
HEAD_SHA=$(git rev-parse --short HEAD 2>/dev/null)
DEFAULT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
FIRST_COMMIT=$(git log --reverse --format='%aI %h %s' 2>/dev/null | head -1)
LAST_COMMIT=$(git log -1 --format='%aI %h %s' 2>/dev/null)
```

If `COMMITS == 0` (somehow no history at all), skip this step entirely and
write a one-line `history_analysis.md` saying so.

### Pull the data

Run these (each output capped — we're going to read this, not store the
universe):

```bash
# Top contributors
git shortlog -sn HEAD | head -15

# Tag/release timeline (most recent 30)
git for-each-ref --sort=-creatordate --count=30 \
  --format='%(creatordate:short) %(refname:short)' refs/tags

# Recent commit message sample (last 80, for cadence + style)
git log --format='%aI %h %s' -n 80

# Merge commits (often = feature integration points)
git log --format='%aI %h %s' --merges -n 30

# "Big" semantic moments — heuristic greps over commit messages
git log --format='%aI %h %s' --grep='BREAKING' --grep='breaking change' \
  --grep='^feat!' --grep='rewrite' --grep='migrate' --regexp-ignore-case \
  --extended-regexp -n 30

# File-level churn — top 20 most-modified paths (proxy for hot spots)
git log --pretty=format: --name-only | sort | uniq -c | sort -rn | head -20

# Cadence: commits per month for last 12 months
git log --format='%aI' | awk '{print substr($1,1,7)}' | sort | uniq -c | tail -12
```

If `SHALLOW=true` and `COMMITS==500`, we hit the depth boundary — note this
in the output ("history truncated at 500 commits"). Don't try to deepen
automatically; that's the user's call.

### Detect commit message convention

Look at the recent 80-message sample. Classify (heuristic, not strict):
- **Conventional Commits** if ≥40% match `^(feat|fix|chore|docs|refactor|test|build|ci|perf|style|revert)(\(.+\))?!?:`
- **Gitmoji** if ≥40% start with an emoji shortcode `:[a-z_]+:` or actual emoji
- **Issue-tagged** if ≥40% contain `#\d+` or `[A-Z]+-\d+` (Jira-style)
- Otherwise: **freeform**

### Write `$VAULT/history_analysis.md`

```markdown
# Git history snapshot

> Auto-extracted by /gin-bai-v2 at <STAMP>. Source: shallow clone, depth=500.

## Vital stats

- **Commits seen**: <COMMITS> <(history truncated at 500 commits) if applicable>
- **First commit (in window)**: <date> · <sha> · "<subject>"
- **Latest commit**: <date> · <sha> · "<subject>"
- **Default branch**: <DEFAULT_BRANCH>
- **Project age (visible window)**: <duration>
- **Commit message style**: <Conventional Commits | Gitmoji | Issue-tagged | freeform>

## Top contributors (in window)

| Commits | Author |
|---------|--------|
| 312     | Alice  |
| 89      | Bob    |
| ...     | ...    |

## Release timeline

| Date | Tag |
|------|-----|
| 2025-12-04 | v2.1.0 |
| ...        | ...    |

(Cap at 30 rows. If more, write "…and N earlier tags" footnote.)

## Cadence (last 12 months)

| Month   | Commits |
|---------|---------|
| 2026-04 | 47      |
| 2026-03 | 62      |
| ...     | ...     |

## Hot files (most-modified, top 20)

| Changes | Path |
|---------|------|
| 184     | src/core/router.ts |
| ...     | ... |

These are likely god-node candidates — Step 4's graphify scoring will
confirm or refute.

## Notable commits (heuristic)

Breaking changes, rewrites, migrations, large merges. **These are clues, not
gospel** — read the commit to confirm narrative weight.

- 2025-08-14 · `a3f9c2b` · `feat!: replace legacy auth with OAuth2 flow`
- 2025-05-02 · `7e1d0aa` · `BREAKING: drop Node 16 support`
- ...

## Inferred narrative arc

(One paragraph, ≤6 sentences. Synthesize from the above: when the project
started, periods of high vs low activity, what the breaking changes suggest
about the project's evolution. **No speculation about motivation** —
stick to what the commits actually say.)
```

Cap each table at the row counts noted. If a section has zero entries
(e.g. no tags), drop the section header.

This page becomes a first-class wiki page (linked from `index.md` in
Step 7b) and is inlined into Step 6 subagent prompts.

## Step 4 - Run graphify against the clone, output to vault

(Unchanged from v1.)

```bash
cd "$WORK"
GRAPHIFY_BIN=$(which graphify 2>/dev/null)
if [ -n "$GRAPHIFY_BIN" ]; then
  PYTHON=$(head -1 "$GRAPHIFY_BIN" | tr -d '#!' | awk '{print $1}')
  case "$PYTHON" in *[!a-zA-Z0-9/_.-]*) PYTHON="python3" ;; esac
else
  PYTHON="python3"
fi
"$PYTHON" -c "import graphify" 2>/dev/null \
  || "$PYTHON" -m pip install graphifyy -q 2>/dev/null \
  || "$PYTHON" -m pip install graphifyy -q --break-system-packages
```

Run graphify SKILL Steps 2-6 with `INPUT_PATH=$WORK`, `OBSIDIAN_DIR=$VAULT`,
`--obsidian` and `--wiki`. Skip Step 7 (HTML viz stays in `$WORK`).

After graphify finishes, copy artifacts:

```bash
cp "$WORK/graphify-out/graph.json"            "$VAULT/.graphify/graph.json"
cp "$WORK/graphify-out/.graphify_analysis.json" "$VAULT/.graphify/analysis.json"
cp "$WORK/graphify-out/.graphify_labels.json"   "$VAULT/.graphify/labels.json"
cp "$WORK/graphify-out/GRAPH_REPORT.md"        "$VAULT/.graphify/GRAPH_REPORT.md"
[ -f "$WORK/graphify-out/graph.html" ] && cp "$WORK/graphify-out/graph.html" "$VAULT/.graphify/graph.html"
```

If graphify produced zero nodes, abort (same as v1).

## Step 5 - Score communities, cap, route to models

Read `analysis.json` and `labels.json`. Per-community god score = max
god-node score across nodes in that community.

### 5a. Cluster cap (NEW in v2 — bounds total wall time)

If `len(communities) > 10`, keep the **top 10 by god score** as
first-class clusters and merge the remainder into one synthetic cluster
labeled `Misc (N small clusters)` with the union of their nodes. The
merged cluster gets a single haiku-routed deep-dive that covers the tail
in aggregate, not per-cluster.

This caps the parallel fan-out width at **11 agents (10 + Misc)**, which
is what the prompt cache and a single assistant message can handle
comfortably. More than that and (a) the orchestrator starts splitting
across messages, (b) wall time gets dominated by tail clusters that
nobody reads, and (c) `philosophy.md` synthesis becomes noisy.

If `len(communities) ≤ 10`, no merge — use them all.

### 5b. Routing (model assignment)

**Opus is reserved.** Only the **single highest-scoring cluster** gets
opus. This is the spec's god-cluster — the one with the project's
load-bearing topology. Spreading opus across multiple clusters multiplies
the slowest-agent wall time without proportional quality gain.

```
top_1_by_god_score                 → opus    (exactly one cluster)
median ≤ score < top_1             → sonnet
score < median                     → haiku
Misc (if merged in 5a)             → haiku
```

Edge cases:
- `len(communities) == 1` → that one gets sonnet (not opus — single
  cluster doesn't need the headroom).
- `len(communities) == 2` → top=sonnet, other=haiku.
- `median == 0` → sonnet for all (degenerate score distribution).

Print routing table to user with this exact format (one line per cluster):

```
Community 0 (Auth Layer)        score=4.21  → opus    [god-cluster]
Community 1 (Data Loading)      score=2.10  → sonnet
Community 2 (CLI Entrypoints)   score=0.40  → haiku
Misc (3 small clusters)         score=0.05  → haiku   [merged tail]
```

## Step 6 - Fan out deep-dive subagents in parallel

> ### ⛔ PARALLEL EXECUTION CONTRACT — READ TWICE BEFORE PROCEEDING
>
> Step 6 has historically failed by going **sequential** even when the
> spec said "parallel". This is the most common bug in this command.
> The rules below are not suggestions.
>
> **Hard rules:**
>
> 1. **All Agent tool calls for Step 6 MUST be emitted in a single
>    assistant message.** Not "the next few messages". Not "two
>    batches". One message containing exactly N parallel `Agent`
>    tool-use blocks, where N = number of clusters from Step 5 (≤11).
>
> 2. **Before that message, emit exactly one announcement line:**
>
>    ```
>    Spawning N deep-dive subagents in parallel: <c1>, <c2>, …, <cN>
>    ```
>
>    This is your verification handshake — if you don't print this line,
>    you didn't earn the right to spawn anything yet. The user uses this
>    line to confirm parallel execution.
>
> 3. **The spawn message contains NOTHING ELSE.** No prose, no
>    explanation, no "I will now…". Pure tool calls. Any text in that
>    message is a contract violation.
>
> 4. **Forbidden patterns:**
>    - Emitting one Agent call, waiting for its result, emitting the
>      next. ❌ Sequential.
>    - "Let me spawn the first 3, then the next 4." ❌ Two batches is
>      sequential at the batch level.
>    - "I'll spawn the opus one first since it's the most important." ❌
>      No prioritization. All N go in one message.
>    - `run_in_background: true` on the Agent calls. ❌ We need their
>      outputs synchronously for Step 7.
>
> 5. **If you find yourself about to emit fewer than N Agent calls in
>    the spawn message, STOP.** Re-read this contract and emit all N at
>    once. Wall time scales with the slowest single agent (~90s), not
>    with N. Sequential N=12 is 18 minutes. Parallel N=12 is ~2 minutes.
>    The user will notice the difference.

Spawn protocol — for each community from Step 5, prepare one `Agent`
tool call with `model` = the routing tier. Build all N prompts first,
then emit them together. Each prompt must be self-contained:

```
You are doing a deep-dive on one cluster of a repository that was just
clustered with graphify.

CLONE_PATH: <WORK>            (this path will be deleted after you return —
                               do all reads now, including any `git log`
                               queries you want, do not assume it persists)
COMMUNITY_LABEL: <plain name from labels.json>
COMMUNITY_NODES: <list of file paths / symbol ids in this community>
GOD_NODES: <subset of these nodes that are god-nodes, with scores>
README_ANALYSIS: <inline contents of $VAULT/README_analysis.md>
HISTORY_ANALYSIS: <inline contents of $VAULT/history_analysis.md>
DESIGN_DOCS_INDEX: <inline contents of $VAULT/.graphify/design_docs.json>
IS_HARNESS: <0 or 1, from Step 3b>
HARNESS_MAP: <if IS_HARNESS=1, inline contents of $VAULT/harness_map.md.
              source of truth for command/agent/skill/hook wiring — your
              deep-dive must reconcile with it. Use [[command/foo]],
              [[agent/executor]], [[skill/autopilot]] wiki-links.>

Tools you can use against CLONE_PATH (before it's deleted):
  - Read any file
  - `git log --follow --format='%aI %h %s' -- <path>` for files in your
    cluster — useful for "when did this responsibility appear"
  - `git log -p -n 1 <sha>` to read a specific commit referenced in
    HISTORY_ANALYSIS
  - `git blame <path>` for hot spots if needed (use sparingly)

Produce a markdown deep-dive (**target 180–280 lines, hard cap 320**)
covering the sections below.

**Time/length budget (read this first):**
- Soft wall budget: ~90 seconds. If you're approaching that, ship what
  you have rather than digging deeper.
- Section priority if you run short on budget: 1, 2, 3, 7 are required;
  4 is important; 5, 6, 8 are nice-to-have. Don't pad sections to hit a
  line count — terse and cited beats long and hand-wavy.
- File reads from CLONE_PATH should be **targeted** — read god-nodes in
  full, sample 2–3 representative non-god files, skim the rest by
  filename only. Reading every file is not the goal.

1. **What this cluster is** - one paragraph, plain English. What
   responsibility does it own?
2. **Public surface** - functions/classes/endpoints other clusters call
   into. List with one-line summaries.

   *If IS_HARNESS=1:* the public surface is slash commands, agents, and
   skills (not functions). Link back to harness_map rows.

3. **Key invariants & contracts** - what must callers respect? What does
   this cluster assume about its inputs?
4. **Internal flow** - god-nodes are load-bearing. Walk through how a
   typical operation flows through them.
5. **Risks / smells / TODOs** - bugs, footguns, "remove once X" comments,
   silent failure modes, missing tests.
6. **Cross-references** - which other clusters does this depend on or get
   called by? Use [[Community Name]] wiki-links.
7. **Design philosophy & invariants** *(NEW in v2 — be disciplined here)*
   What design principles does this cluster *demonstrably* follow?

   **Hard rules:**
   - Cite evidence inline. Every principle bullet must reference a
     concrete source: `code:path/to/file.py:42`, `doc:CLAUDE.md#delegation`,
     `commit:a3f9c2b`, `comment:src/foo.ts:88`. No bare claims.
   - If you can't cite it, don't include it. Speculation is forbidden in
     this section. (Speculation belongs in section 5 as a smell.)
   - Lift principles from: docstrings, inline comments stating intent
     ("// we do X because Y"), DESIGN_DOCS_INDEX entries, and commit
     messages from HISTORY_ANALYSIS that explain *why* a change happened.
   - 3–5 bullets. If you can't find any, write
     `_No explicit design statements found in this cluster._` and stop.

   Format:
   ```
   - **<short principle>** — <one-line explanation>.
     Source: `<citation>`, `<citation>`.
   ```

8. **History notes** *(NEW in v2 — optional, only if relevant)*
   If `git log --follow` on this cluster's god-nodes surfaces something
   that changes how a reader should interpret the code (a recent rewrite,
   a deprecation in flight, a long-stable file vs a hot one), call it out
   in 1-3 bullets. Otherwise omit this section.

Output ONLY the markdown body. No preamble.
```

Save each subagent's output to `$VAULT/communities/<slug-of-label>.md` with
YAML frontmatter:

```yaml
---
community: <plain name>
god_score: <number>
model: <opus|sonnet|haiku>
ingested: <STAMP>
---
```

## Step 7 - Synthesize the LLM Wiki (Karpathy style)

Once all deep dives exist, write the top-level wiki pages.

### 7a. `$VAULT/pipeline.md`

Cross-cluster synthesis. Shape depends on IS_HARNESS:

**If IS_HARNESS=0:** Trace **one full request / one full data flow** through
the system end-to-end. Use `[[Community Name]]` wiki-links. Include entry
point(s), sequenced inter-community hops, and a "what could go wrong"
section synthesized from per-community Risks sections.

**If IS_HARNESS=1:** Trace **one full user invocation** (slash command →
pre-hooks → agent orchestration → skills → post-hooks → state persistence
→ failure modes). Use `[[command/foo]]`, `[[agent/executor]]`,
`[[skill/autopilot]]`, `[[hook/<event>/<script>]]` link conventions.

Length: 150-300 lines.

**Append a final section, regardless of harness mode:**

```markdown
## Cross-cutting principles (snapshot)

> Synthesized from each cluster's "Design philosophy & invariants"
> section. For full citations and per-cluster breakdowns, see
> [[philosophy]].

- **<recurring principle>** — appears in [[communities/foo|Foo]],
  [[communities/bar|Bar]]. Example: <one-line>.
- ...
```

3-7 bullets. Only include principles that appear in 2+ clusters
(genuinely cross-cutting). Single-cluster principles stay in the
per-cluster pages and `philosophy.md`.

### 7b. `$VAULT/index.md`

```markdown
# <owner>/<repo>

> One-sentence summary.

## Orientation
- [[README_analysis]] — stack, entry points, build/test, stated principles
- [[history_analysis]] — *(new in v2)* contributors, cadence, notable commits
- [[philosophy]] — *(new in v2)* design principles with citations
- [[pipeline]] — end-to-end flow across clusters
- [[harness_map]] — *(only if IS_HARNESS=1)* command/agent/skill/hook wiring

## Clusters (deep dives)
- [[communities/<slug>|<Plain Name>]] — one-line summary (god_score=N, model=tier)
- ...

## God-nodes (load-bearing files/symbols)
- `<node>` — score N, lives in [[communities/<slug>|<cluster>]]
- ... (top 10)

## Claude Code surface *(only if IS_HARNESS=1)*
- Commands: N · Agents: M · Skills: K · Hooks: H · MCP servers: S
- Most-invoked agent: `<name>` (called from N commands)
- Hook coverage: events with hooks attached: `<list>`
- See [[harness_map]] for full tables.

## Graphify artifacts
- `.graphify/GRAPH_REPORT.md` — raw clustering report
- `.graphify/graph.json` — full graph data
- `.graphify/graph.html` — interactive viz
- `.graphify/design_docs.json` — *(new in v2)* design doc index
- `graph.canvas` — Obsidian Canvas view of communities
```

### 7c. `$VAULT/philosophy.md` (NEW in v2)

Aggregate every cluster's section 7 into one page. Group by recurring
themes when possible; keep singletons in their own subsection. Every
bullet keeps its citation — this page is "design principles, with
receipts".

```markdown
# Design philosophy & invariants

> Aggregated from per-cluster deep dives. **Every claim is cited** —
> if you don't see a `Source:` line, the claim was dropped. Speculation
> intentionally excluded.
>
> Generated <STAMP>.

## Cross-cutting principles

Principles that appear in 2+ clusters. Higher confidence — these are
likely intentional, not coincidence.

### <Principle name 1>

<One-paragraph synthesis.>

- **In [[communities/foo|Foo]]**: <bullet from cluster's section 7>
  Source: `<citation>`, `<citation>`.
- **In [[communities/bar|Bar]]**: <bullet>
  Source: `<citation>`.

### <Principle name 2>

...

## Cluster-specific principles

Principles that appear in only one cluster. Lower confidence as
"project philosophy" but valuable as local context.

### [[communities/foo|Foo]]

- **<principle>** — <one-line>. Source: `<citation>`.
- ...

### [[communities/bar|Bar]]

- ...

## Principles found in stated docs (not yet observed in code)

> Things `CLAUDE.md`, `ARCHITECTURE.md`, ADRs, etc. say the project
> believes — but which no cluster's section 7 surfaced. Either the
> principle is too high-level to manifest in any one cluster, or it's
> aspirational. Useful gap signal.

- **<principle>** from `doc:CLAUDE.md#operating-principles`:
  <quoted line or short paraphrase>.
- ...

## Notes on method

- "Cross-cutting" = appears in **2 or more** cluster section-7s with
  compatible meaning (LLM-judged similarity, not exact string match).
- Citation formats: `code:<path>:<line>`, `doc:<path>#<heading>`,
  `commit:<sha>`, `comment:<path>:<line>`.
- Re-running `/gin-bai-v2` overwrites this page.
```

How to build this page (orchestrator instructions):
1. Collect every `communities/*.md` file's section 7. Skip clusters that
   wrote `_No explicit design statements found_`.
2. Group bullets by similarity (semantic, not string-equal — e.g.
   "fail loudly" and "no silent fallbacks" are the same principle).
3. Bullets in 2+ clusters → `## Cross-cutting principles`.
4. Bullets in 1 cluster → `## Cluster-specific principles`.
5. For each design doc in `design_docs.json`, scan for principle-shaped
   statements (imperative or normative sentences in CLAUDE.md, ADRs,
   ARCHITECTURE.md). If a stated principle has no matching code-side
   evidence in any cluster, list it under
   `## Principles found in stated docs (not yet observed in code)`.
   Cap at 10 to avoid noise.

### 7d. `$VAULT/log.md` (append-only, was 7c in v1)

If exists, append. Else create with heading. Each entry:

```markdown
## <STAMP> — ingest (v2)

- Source: <github-url>
- Commit: <HEAD_SHA>
- Commits seen: <COMMITS> <(truncated at 500) if applicable>
- Communities: N (<plain names, comma-separated>)
- Routing: opus=A, sonnet=B, haiku=C
- Cross-cutting principles found: <count>
- Notes: <one line on anything surprising>
```

Never rewrite existing log entries.

## Step 8 - Cleanup

```bash
rm -rf "$WORK"
[ ! -d "$WORK" ] && echo "Cleanup OK" || echo "WARN: $WORK still present"
```

## Step 9 - Report to the user

```
Wiki: <VAULT>
  index.md             — start here
  README_analysis.md   — stack, entry points, stated principles
  history_analysis.md  — git history snapshot (NEW)
  pipeline.md          — end-to-end flow (or user-invocation flow)
  philosophy.md        — design principles with citations (NEW)
  harness_map.md       — (if IS_HARNESS=1) command/agent/skill/hook wiring
  communities/         — N deep dives
  log.md               — ingest history
  .graphify/           — raw graph + report

Open the vault in Obsidian and start at index.md.
```

If `obsidian` CLI is on PATH, offer (but do not run):

```
obsidian open "$VAULT/index.md"
```

## Failure handling

- Clone fails → abort, delete empty `$VAULT` if newly created, no log entry.
- Git history empty (`COMMITS == 0`) → write minimal `history_analysis.md`
  ("no commit history available"), continue. Subagents handle missing
  HISTORY_ANALYSIS gracefully (it's just empty inputs).
- Graphify produces empty graph → write `$VAULT/EMPTY.md` and skip
  Steps 5-7. Still cleanup. Log with `Notes: empty graph`.
- A subagent fails → placeholder `communities/<slug>.md` with
  `_Deep dive failed - rerun /gin-bai-v2 to retry._`. `philosophy.md`
  synthesis just skips that cluster; note the omission in `log.md`.
- Cleanup fails → warn with the exact path. Do not abort.

## Notes for the orchestrator

### Critical: parallel discipline at Step 6

This is the spec's #1 historical failure mode. Re-read the
**PARALLEL EXECUTION CONTRACT** in Step 6 before running. Concretely:

- The "Spawning N deep-dive subagents in parallel: …" announcement
  line is mandatory. Without it, you have not met the contract.
- The very next assistant message after the announcement must contain
  exactly N `Agent` tool-use blocks **and zero text content**. If you're
  about to write any prose in that message, you've already failed —
  delete the prose, keep only the tool calls.
- Past runs have failed by emitting one Agent call per message ("I'll
  spawn community 0… now community 1… now community 2…"). That is
  sequential, not parallel, and turns a 2-minute step into 18 minutes.
  Do not do this under any framing ("for clarity", "to handle errors
  gracefully", "to be careful").
- After the spawn message, your next assistant turn will receive all N
  results together. Step 7 starts there.

### Other discipline points

- Steps 2–3c are sequential (clone → reads). Only Step 6 fans out.
- Do NOT use `run_in_background: true` for the Step 6 Agent calls —
  Step 7 needs their outputs synchronously. Background mode breaks the
  data flow.
- The clone disappears at Step 8. Subagents must do all `git log`,
  `git blame`, and file reads against `CLONE_PATH` BEFORE they return.
- Step 5a's cluster cap (≤10 + Misc) protects the parallel fan-out from
  exceeding what a single message can comfortably hold. Don't bypass it.
- Re-running `/gin-bai-v2` on the same repo overwrites `README_analysis.md`,
  `history_analysis.md`, `harness_map.md`, `pipeline.md`, `philosophy.md`,
  `index.md`, `communities/*.md`, `.graphify/*` — and appends to `log.md`.
- v1 (`/gin-bai`) and v2 (`/gin-bai-v2`) coexist. They write to the same
  vault folder; the last one wins for overlapping files. `log.md`
  distinguishes runs by the `(v2)` tag in the heading.

### Self-check before claiming done

Before the Step 9 report, verify:

1. `log.md` got a new `(v2)` entry — confirms the run reached the end.
2. `philosophy.md` exists and is not empty — confirms Step 7c ran.
3. The number of files in `communities/` matches the number of Agent
   calls you emitted in Step 6 (with `_failed` placeholders counted).
   Mismatch = a subagent's output never landed; investigate.
4. The wall time for Step 6 was roughly the time of your **slowest**
   single subagent, not the sum. If it was the sum, you went sequential
   — note this in `log.md` Notes line so the next run is on alert.
