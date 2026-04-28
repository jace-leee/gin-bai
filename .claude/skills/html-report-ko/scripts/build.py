#!/usr/bin/env python3
"""html-report-ko 빌드 스크립트.

마크다운 파일을 읽어 한글 보고서용 HTML 템플릿에 합성하고, CSS와
Mermaid CDN 스크립트를 주입한다. 결과물은 단일 .html 파일
(외부 링크 모드일 때는 report.css도 함께 출력 디렉터리에 복사).

사용법:
    python3 build.py --input report.md --output report.html [플래그]

자세한 플래그 설명은 SKILL.md 참고.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import shutil
import subprocess
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
ASSETS = SKILL_ROOT / "assets"
CSS_PATH = ASSETS / "report.css"
TEMPLATE_PATH = ASSETS / "template.html"

MERMAID_CDN_TAG_TEMPLATE = (
    '<script src="https://cdn.jsdelivr.net/npm/mermaid@{ver}/dist/mermaid.min.js"></script>\n'
    "<script>\n"
    "mermaid.initialize({{\n"
    "  startOnLoad: true,\n"
    "  theme: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'default',\n"
    "  securityLevel: 'loose',\n"
    "  fontFamily: '\"Pretendard Variable\", Pretendard, -apple-system, \"Apple SD Gothic Neo\", \"Malgun Gothic\", \"Noto Sans KR\", sans-serif'\n"
    "}});\n"
    "</script>"
)

KOREAN_WEBFONT_TAG = (
    '<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>\n'
    '<link rel="stylesheet" '
    'href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">'
)

MERMAID_FENCE_RE = re.compile(
    r"^```mermaid[ \t]*\n(.*?)^```[ \t]*$",
    re.DOTALL | re.MULTILINE,
)

H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="마크다운에서 한국어 HTML 보고서를 생성합니다."
    )
    p.add_argument("--input", required=True, type=Path, help="마크다운 입력 파일 경로")
    p.add_argument(
        "--output",
        default=None,
        type=Path,
        help="HTML 출력 경로 (생략 시 입력 파일과 같은 디렉터리에 .html 확장자로 생성)",
    )
    p.add_argument("--title", default=None, help="페이지 제목 (기본: 첫 H1)")
    p.add_argument(
        "--inline-css",
        action="store_true",
        help="CSS를 <style> 태그로 인라인 (단일 파일 출력)",
    )
    p.add_argument(
        "--theme",
        choices=("light", "dark", "auto"),
        default="auto",
        help="색상 모드 (기본: auto, prefers-color-scheme 따라감)",
    )
    p.add_argument(
        "--mermaid-version",
        default="10",
        help="CDN에서 로드할 Mermaid 메이저 버전 (기본: 10)",
    )
    p.add_argument(
        "--no-mermaid",
        action="store_true",
        help="Mermaid CDN 스크립트 태그 생략",
    )
    p.add_argument(
        "--korean-webfont",
        action="store_true",
        help="Pretendard 웹폰트를 jsDelivr CDN에서 추가 로드",
    )
    return p.parse_args()


def extract_mermaid_blocks(md: str) -> tuple[str, list[str]]:
    """```mermaid``` fence를 sentinel로 치환. (변환된_md, 블록_리스트) 반환."""
    blocks: list[str] = []

    def repl(match: re.Match[str]) -> str:
        blocks.append(match.group(1).rstrip())
        return f"\n[[MERMAID_BLOCK_{len(blocks) - 1}]]\n"

    return MERMAID_FENCE_RE.sub(repl, md), blocks


MINDMAP_RE = re.compile(r"^\s*mindmap\b", re.IGNORECASE)
BR_TAG_RE = re.compile(r"<br\s*/?\s*>", re.IGNORECASE)


def sanitize_mermaid_block(block: str) -> str:
    """Mermaid 파서가 자주 실패하는 흔한 실수를 자동 보정한다.

    - mindmap 블록은 HTML 태그를 지원하지 않으므로 <br/> 류를 공백으로 치환.
    - 그 외 다이어그램은 손대지 않는다 (사용자 의도 보존).
    """
    first_line = block.lstrip().splitlines()[0] if block.strip() else ""
    if MINDMAP_RE.match(first_line):
        block = BR_TAG_RE.sub(" ", block)
    return block


def reinsert_mermaid_blocks(html_body: str, blocks: list[str]) -> str:
    for i, block in enumerate(blocks):
        sentinel_patterns = [
            f"<p>[[MERMAID_BLOCK_{i}]]</p>",
            f"[[MERMAID_BLOCK_{i}]]",
        ]
        clean = sanitize_mermaid_block(block)
        # quote=False: 작은따옴표·큰따옴표는 텍스트 노드 안에서 이스케이프 불필요.
        # mermaid 파서가 &#x27; 같은 엔티티를 그대로 보고 깨지는 경우를 방지.
        replacement = f'<pre class="mermaid">{html.escape(clean, quote=False)}</pre>'
        for pat in sentinel_patterns:
            if pat in html_body:
                html_body = html_body.replace(pat, replacement, 1)
                break
    return html_body


def render_markdown(md: str) -> str:
    """마크다운 → HTML 변환. python-markdown 우선, 없으면 폴백 컨버터 사용."""
    try:
        import markdown  # type: ignore
    except ImportError:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--user", "--quiet", "markdown"],
                stderr=subprocess.DEVNULL,
            )
            import markdown  # type: ignore  # noqa: F401
        except Exception:
            return _fallback_markdown(md)

    import markdown  # type: ignore

    return markdown.markdown(
        md,
        extensions=[
            "tables",
            "fenced_code",
            "footnotes",
            "toc",
            "sane_lists",
            "attr_list",
        ],
        output_format="html5",
    )


def _fallback_markdown(md: str) -> str:
    """python-markdown이 없을 때 사용하는 최소 컨버터.

    헤딩, 단락, 펜스 코드, 인라인 코드, 굵게, 기울임, 링크, 불릿/순서 리스트,
    수평선, 인용구, 단순 표를 처리. python-markdown만큼 폴리시는 안 되지만
    대부분의 보고서 콘텐츠를 다룰 수 있음.
    """
    out: list[str] = []
    lines = md.splitlines()
    i = 0
    in_list = False
    list_kind = "ul"

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append(f"</{list_kind}>")
            in_list = False

    def inline(s: str) -> str:
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
        return s

    while i < len(lines):
        line = lines[i]

        if line.strip().startswith("```"):
            close_list()
            lang = line.strip()[3:].strip()
            i += 1
            buf: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = f' class="language-{lang}"' if lang else ""
            out.append(f"<pre><code{cls}>{html.escape(chr(10).join(buf))}</code></pre>")
            continue

        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if m:
            close_list()
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue

        if re.match(r"^\s*[-*]\s+", line):
            if not in_list or list_kind != "ul":
                close_list()
                out.append("<ul>")
                in_list = True
                list_kind = "ul"
            content = re.sub(r"^\s*[-*]\s+", "", line)
            out.append(f"<li>{inline(content)}</li>")
            i += 1
            continue

        if re.match(r"^\s*\d+\.\s+", line):
            if not in_list or list_kind != "ol":
                close_list()
                out.append("<ol>")
                in_list = True
                list_kind = "ol"
            content = re.sub(r"^\s*\d+\.\s+", "", line)
            out.append(f"<li>{inline(content)}</li>")
            i += 1
            continue

        if line.startswith(">"):
            close_list()
            out.append(f"<blockquote>{inline(line.lstrip('> ').rstrip())}</blockquote>")
            i += 1
            continue

        if re.match(r"^\s*([-*_])\1{2,}\s*$", line):
            close_list()
            out.append("<hr>")
            i += 1
            continue

        if "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i + 1]):
            close_list()
            headers = [c.strip() for c in line.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            out.append("<table><thead><tr>")
            for h_ in headers:
                out.append(f"<th>{inline(h_)}</th>")
            out.append("</tr></thead><tbody>")
            for row in rows:
                out.append("<tr>")
                for c in row:
                    out.append(f"<td>{inline(c)}</td>")
                out.append("</tr>")
            out.append("</tbody></table>")
            continue

        if line.strip() == "":
            close_list()
            i += 1
            continue

        close_list()
        out.append(f"<p>{inline(line)}</p>")
        i += 1

    close_list()
    return "\n".join(out)


def make_css_tag(output_path: Path, inline_css: bool) -> str:
    if inline_css:
        css_text = CSS_PATH.read_text(encoding="utf-8")
        return f"<style>\n{css_text}\n</style>"
    css_dest = output_path.parent / "report.css"
    if css_dest.resolve() != CSS_PATH.resolve():
        shutil.copyfile(CSS_PATH, css_dest)
    return '<link rel="stylesheet" href="report.css">'


def make_mermaid_tag(version: str, no_mermaid: bool) -> str:
    if no_mermaid:
        return ""
    return MERMAID_CDN_TAG_TEMPLATE.format(ver=version)


def make_korean_webfont_tag(use_webfont: bool) -> str:
    return KOREAN_WEBFONT_TAG if use_webfont else ""


def main() -> int:
    args = parse_args()

    if not args.input.is_file():
        print(f"오류: 입력 파일을 찾을 수 없습니다 — {args.input}", file=sys.stderr)
        return 1

    if args.output is None:
        args.output = args.input.with_suffix(".html")

    args.output.parent.mkdir(parents=True, exist_ok=True)

    md = args.input.read_text(encoding="utf-8")

    title = args.title
    if title is None:
        m = H1_RE.search(md)
        title = m.group(1).strip() if m else "보고서"
        if m:
            md = md.replace(m.group(0), "", 1)

    md_no_mermaid, mermaid_blocks = extract_mermaid_blocks(md)
    body_html = render_markdown(md_no_mermaid)
    body_html = reinsert_mermaid_blocks(body_html, mermaid_blocks)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    css_tag = make_css_tag(args.output, args.inline_css)
    mermaid_tag = make_mermaid_tag(args.mermaid_version, args.no_mermaid)
    webfont_tag = make_korean_webfont_tag(args.korean_webfont)
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    final = (
        template
        .replace("{{TITLE}}", html.escape(title))
        .replace("{{THEME}}", args.theme)
        .replace("{{CSS_TAG}}", css_tag)
        .replace("{{MERMAID_TAG}}", mermaid_tag)
        .replace("{{KOREAN_WEBFONT_TAG}}", webfont_tag)
        .replace("{{GENERATED_AT}}", generated_at)
        .replace("{{BODY}}", body_html)
    )

    args.output.write_text(final, encoding="utf-8")

    extra = ""
    if not args.inline_css:
        extra = f"  (+ {(args.output.parent / 'report.css').resolve()})"
    print(f"작성 완료: {args.output.resolve()}{extra}")
    print(f"  제목: {title}")
    print(f"  Mermaid 블록: {len(mermaid_blocks)}개")
    if args.korean_webfont:
        print("  Pretendard 웹폰트: 활성화")
    return 0


if __name__ == "__main__":
    sys.exit(main())
