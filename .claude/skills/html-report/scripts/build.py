#!/usr/bin/env python3
"""html-report build script.

Reads a markdown file, wraps it in the bundled HTML template, links or inlines
the bundled CSS, and adds a Mermaid CDN script tag. Output: a single .html file
(plus report.css next to it, unless --inline-css).

Usage:
    python3 build.py --input report.md --output report.html [flags]

See SKILL.md for full flag documentation.
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
    "  securityLevel: 'loose'\n"
    "}});\n"
    "</script>"
)

MERMAID_FENCE_RE = re.compile(
    r"^```mermaid[ \t]*\n(.*?)^```[ \t]*$",
    re.DOTALL | re.MULTILINE,
)

H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build a styled HTML report from markdown.")
    p.add_argument("--input", required=True, type=Path, help="Markdown source path.")
    p.add_argument(
        "--output",
        default=None,
        type=Path,
        help="HTML output path. Defaults to <input-stem>.html alongside the input.",
    )
    p.add_argument("--title", default=None, help="Page title (default: first H1).")
    p.add_argument(
        "--inline-css",
        action="store_true",
        help="Inline CSS in <style> tag instead of linking a copied file.",
    )
    p.add_argument(
        "--theme",
        choices=("light", "dark", "auto"),
        default="auto",
        help="Color scheme (default: auto).",
    )
    p.add_argument(
        "--mermaid-version",
        default="10",
        help="Mermaid major version to load (default: 10).",
    )
    p.add_argument(
        "--no-mermaid",
        action="store_true",
        help="Skip the Mermaid CDN script tag.",
    )
    return p.parse_args()


def extract_mermaid_blocks(md: str) -> tuple[str, list[str]]:
    """Replace ```mermaid``` fences with sentinels; return (modified_md, blocks)."""
    blocks: list[str] = []

    def repl(match: re.Match[str]) -> str:
        blocks.append(match.group(1).rstrip())
        return f"\n[[MERMAID_BLOCK_{len(blocks) - 1}]]\n"

    return MERMAID_FENCE_RE.sub(repl, md), blocks


MINDMAP_RE = re.compile(r"^\s*mindmap\b", re.IGNORECASE)
BR_TAG_RE = re.compile(r"<br\s*/?\s*>", re.IGNORECASE)


def sanitize_mermaid_block(block: str) -> str:
    """Auto-fix common mermaid pitfalls before rendering.

    - mindmap does not accept HTML tags; strip <br/> variants.
    - Other diagram types are left untouched.
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
        # quote=False keeps apostrophes/quotes raw — html.escape would emit
        # &#x27;/&quot; which the mermaid parser sometimes treats as literal
        # entity text and refuses to parse.
        replacement = f'<pre class="mermaid">{html.escape(clean, quote=False)}</pre>'
        for pat in sentinel_patterns:
            if pat in html_body:
                html_body = html_body.replace(pat, replacement, 1)
                break
    return html_body


def render_markdown(md: str) -> str:
    """Render markdown to HTML. Try python-markdown; fall back to a minimal converter."""
    try:
        import markdown  # type: ignore
    except ImportError:
        # Try to install. If that fails, fall back.
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
    """Bare-bones markdown rendering when the markdown library is unavailable.

    Handles: headings, paragraphs, fenced code, inline code, bold, italic, links,
    unordered lists, ordered lists, horizontal rules, blockquotes, simple tables.
    Not as polished as python-markdown but covers most report content.
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
            i += 1  # skip closing fence
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
            i += 2  # skip header + separator
            rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            out.append("<table><thead><tr>")
            for h in headers:
                out.append(f"<th>{inline(h)}</th>")
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


def main() -> int:
    args = parse_args()

    if not args.input.is_file():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 1

    if args.output is None:
        args.output = args.input.with_suffix(".html")

    args.output.parent.mkdir(parents=True, exist_ok=True)

    md = args.input.read_text(encoding="utf-8")

    title = args.title
    if title is None:
        m = H1_RE.search(md)
        title = m.group(1).strip() if m else "Report"
        if m:
            md = md.replace(m.group(0), "", 1)

    md_no_mermaid, mermaid_blocks = extract_mermaid_blocks(md)
    body_html = render_markdown(md_no_mermaid)
    body_html = reinsert_mermaid_blocks(body_html, mermaid_blocks)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    css_tag = make_css_tag(args.output, args.inline_css)
    mermaid_tag = make_mermaid_tag(args.mermaid_version, args.no_mermaid)
    generated_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    final = (
        template
        .replace("{{TITLE}}", html.escape(title))
        .replace("{{THEME}}", args.theme)
        .replace("{{CSS_TAG}}", css_tag)
        .replace("{{MERMAID_TAG}}", mermaid_tag)
        .replace("{{GENERATED_AT}}", generated_at)
        .replace("{{BODY}}", body_html)
    )

    args.output.write_text(final, encoding="utf-8")

    extra = ""
    if not args.inline_css:
        extra = f" (+ {(args.output.parent / 'report.css').resolve()})"
    print(f"wrote {args.output.resolve()}{extra}")
    print(f"  title: {title}")
    print(f"  mermaid blocks: {len(mermaid_blocks)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
