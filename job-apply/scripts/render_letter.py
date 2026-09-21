#!/usr/bin/env python3
"""Render a markdown cover letter to a one-page PDF using Typst.

Many application forms want a cover letter as a file upload rather than a
textarea, and pandoc on macOS usually has no PDF engine installed. RenderCV
already depends on the `typst` Python package, so this reuses that rather than
adding a dependency.

    python3 render_letter.py cover-letter.md /abs/path/Lastname_Company_CoverLetter.pdf \
        --name "Ada Lovelace" --location "London, United Kingdom" \
        --email ada@example.com --phone "+44 7700 900000"

If the interpreter running this does not have `typst`, re-run it with RenderCV's:
    ~/.local/share/uv/tools/rendercv/bin/python render_letter.py ...

The contact header is optional. Pass only what the user actually has, since a
letter is not the place to invent a phone number.
"""

import argparse
import pathlib
import sys

# Typst treats these as markup. A letter is plain prose, so escape all of them
# rather than trying to preserve formatting. `@` matters most: an email address
# otherwise parses as a label reference and fails the whole compile.
_ESCAPES = [
    ("\\", "\\\\"), ('"', '\\"'), ("#", "\\#"), ("$", "\\$"),
    ("@", "\\@"), ("<", "\\<"), (">", "\\>"), ("*", "\\*"), ("_", "\\_"),
]

_SIGNOFFS = ("best regards", "kind regards", "sincerely", "yours", "regards,")


def esc(s: str) -> str:
    for a, b in _ESCAPES:
        s = s.replace(a, b)
    return s


def to_paragraphs(text: str) -> list[str]:
    """Split on blank lines, collapsing soft wraps except inside the signoff."""
    out = []
    for block in text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        if block.lower().startswith(_SIGNOFFS):
            # Keep "Best regards," and the name on separate lines.
            out.append("\x00".join(line.strip() for line in block.split("\n")))
        else:
            out.append(block.replace("\n", " "))
    return out


def build_typst(paragraphs: list[str], header_lines: list[str]) -> str:
    body = "\n\n".join(
        "#par[%s]" % esc(p).replace("\x00", " \\\n") for p in paragraphs
    )
    head = ""
    if header_lines:
        head = "#align(right)[%s]\n#v(1.2em)\n" % " \\\n".join(
            esc(h) for h in header_lines
        )
    return (
        '#set page(paper: "a4", margin: (x: 2cm, y: 2cm))\n'
        '#set text(font: ("Times New Roman", "Liberation Serif", "DejaVu Serif"), size: 11pt)\n'
        "#set par(justify: false, leading: 0.65em, spacing: 1.1em)\n"
        + head
        + body
        + "\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("markdown")
    ap.add_argument("out_pdf")
    for flag in ("name", "location", "email", "phone"):
        ap.add_argument("--" + flag, default=None)
    ap.add_argument("--preview-png", default=None,
                    help="also render a PNG, to eyeball the layout")
    args = ap.parse_args()

    try:
        import typst
    except ImportError:
        sys.stderr.write(
            "typst not importable. Re-run with RenderCV's interpreter:\n"
            "  ~/.local/share/uv/tools/rendercv/bin/python "
            + " ".join(sys.argv) + "\n"
        )
        return 1

    text = pathlib.Path(args.markdown).read_text()
    header = [v for v in (args.name, args.location, args.email, args.phone) if v]
    typ = build_typst(to_paragraphs(text), header)

    src = pathlib.Path(args.out_pdf).with_suffix(".typ")
    src.write_text(typ)
    typst.compile(str(src), output=args.out_pdf)
    if args.preview_png:
        typst.compile(str(src), output=args.preview_png, ppi=70)
    src.unlink(missing_ok=True)

    print("wrote", args.out_pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
