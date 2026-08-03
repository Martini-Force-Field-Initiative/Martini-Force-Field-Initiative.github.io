"""Parser for Pandoc fenced divs (`::: name` ... `:::`).

Several contribution types are structural rather than field-based: a tool
entry is a `::: software-card` whose first child must be an `### ` heading
(the CSS attaches the gear glyph and the underline to `.software-card h3`,
so a card using `##` or `####` renders unstyled and nothing reports it), and
a tutorial registration is a `::: tutorial-item` with a specific inner shape.

The most common contributor mistake here is a missing closing `:::`, which
silently swallows the rest of the page into the preceding card.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Opening fence: ':::' (or more) followed by either a bare class name or a
# brace-delimited attribute block.
FENCE_RE = re.compile(
    r"^(?P<colons>:{3,})\s*"
    r"(?:\{(?P<attrs>[^}]*)\}|(?P<bare>[A-Za-z][\w-]*))?\s*$"
)
CLASS_RE = re.compile(r"\.([A-Za-z][\w-]*)")
ID_RE = re.compile(r"#([A-Za-z][\w-]*)")
HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<text>.*?)\s*$")


@dataclass
class Div:
    classes: list[str]
    ident: str | None
    start_line: int
    end_line: int | None = None
    parent: "Div | None" = None
    children: list["Div"] = field(default_factory=list)
    # (line_number, text) for lines at this div's own level, excluding those
    # belonging to nested divs.
    own_lines: list[tuple[int, str]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.classes[0] if self.classes else "(anonymous)"

    def has_class(self, name: str) -> bool:
        return name in self.classes

    def first_significant(self) -> tuple[str, int, str] | None:
        """The first meaningful thing inside this div.

        Returns ``("heading", level, text)``, ``("div", 0, classname)`` or
        ``("text", 0, text)``. Blank lines and HTML comments are skipped.
        """
        first_child = self.children[0] if self.children else None

        in_comment = False
        for lineno, text in self.own_lines:
            stripped = text.strip()
            if not stripped:
                continue
            if in_comment:
                if "-->" in stripped:
                    in_comment = False
                continue
            if stripped.startswith("<!--"):
                if "-->" not in stripped:
                    in_comment = True
                continue

            if first_child and first_child.start_line < lineno:
                return ("div", 0, first_child.name)

            heading = HEADING_RE.match(stripped)
            if heading:
                return ("heading", len(heading.group("hashes")), heading.group("text"))
            return ("text", 0, stripped)

        if first_child:
            return ("div", 0, first_child.name)
        return None

    def text(self) -> str:
        return "\n".join(t for _, t in self.own_lines)


@dataclass
class DivParseResult:
    divs: list[Div]              # every div, flattened
    roots: list[Div]             # top-level divs only
    unclosed: list[Div]          # opened but never closed
    stray_closes: list[int]      # line numbers of unmatched ':::'


def parse_divs(lines) -> DivParseResult:
    """Parse an iterable of (line_number, text) into a div tree.

    Pandoc actually matches fences by colon count; in this repository every
    close is a bare ``:::``, so "a bare fence closes the innermost open div"
    is both correct here and produces far better error messages.
    """
    all_divs: list[Div] = []
    roots: list[Div] = []
    stack: list[Div] = []
    stray: list[int] = []

    for lineno, text in lines:
        match = FENCE_RE.match(text.strip())
        if not match:
            if stack:
                stack[-1].own_lines.append((lineno, text))
            continue

        attrs = match.group("attrs")
        bare = match.group("bare")

        if attrs is None and bare is None:
            # A bare fence: close the innermost div, or an anonymous open.
            if stack:
                closed = stack.pop()
                closed.end_line = lineno
            else:
                stray.append(lineno)
            continue

        if attrs is not None:
            classes = CLASS_RE.findall(attrs)
            ident_match = ID_RE.search(attrs)
            ident = ident_match.group(1) if ident_match else None
            if not classes:
                bare_word = attrs.strip().split()
                classes = [w for w in bare_word if not w.startswith(("#", "."))][:1]
        else:
            classes = [bare]
            ident = None

        div = Div(classes=classes, ident=ident, start_line=lineno)
        if stack:
            div.parent = stack[-1]
            stack[-1].children.append(div)
        else:
            roots.append(div)
        all_divs.append(div)
        stack.append(div)

    return DivParseResult(
        divs=all_divs, roots=roots, unclosed=list(stack), stray_closes=stray
    )


def slugify(heading_text: str) -> str:
    """Reproduce Pandoc's heading-to-anchor conversion.

    Pandoc's rule: strip formatting, drop everything up to the first letter,
    remove all characters except letters, digits, and ``_ - .``, replace
    spaces with hyphens, lowercase.

    Note that ``.`` and ``_`` SURVIVE -- a heading "using martinize.py"
    anchors as ``using-martinize.py``. Stripping them (the obvious reading of
    "remove punctuation") makes the checker report phantom breakage on every
    heading containing a filename, of which this repository has many.
    """
    text = re.sub(r"\{[^}]*\}\s*$", "", heading_text)       # trailing {#id .attrs}
    text = re.sub(r"<[^>]+>", "", text)                     # inline HTML (fa icons)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links -> their text
    text = re.sub(r"[`*]", "", text)                        # emphasis / code marks
    text = text.strip().lower()
    # Pandoc drops everything before the first letter.
    match = re.search(r"[^\W\d_]", text, flags=re.UNICODE)
    if match:
        text = text[match.start():]
    text = re.sub(r"[^\w\s.\-]", "", text, flags=re.UNICODE)
    # One hyphen per space, not per run of spaces. Pandoc deletes punctuation
    # in place and only then substitutes, so "Martini + elastic network" loses
    # the '+' and keeps both surrounding spaces: martini--elastic-network.
    text = re.sub(r"\s", "-", text)
    return text.strip("-")


def explicit_id(heading_text: str) -> str | None:
    """An author-supplied ``{#custom-id}`` overrides the generated slug.

    ``.`` is part of the identifier, not the start of a class: Pandoc only
    begins a class when a ``.`` follows whitespace. Stopping at the first dot
    turns ``{#part-i.-protein-complexes-at-equilibrium}`` into ``part-i`` and
    makes every link to the real anchor look broken.
    """
    match = re.search(r"\{#([A-Za-z][\w.-]*)[^}]*\}\s*$", heading_text)
    return match.group(1) if match else None


def heading_slugs(lines) -> dict[str, int]:
    """Map anchor slug -> line number for every heading in the given lines.

    Pandoc guarantees identifiers are unique: the second heading that slugifies
    to ``analysis`` anchors as ``analysis-1``, the third as ``analysis-2``.
    Tutorials with repeated section names link to those suffixed forms, and
    they are correct -- recording only the first would report them broken.

    An author-supplied ``{#id}`` is emitted verbatim and never renumbered, so
    only generated slugs take part in the disambiguation.
    """
    slugs: dict[str, int] = {}
    for lineno, text in lines:
        match = HEADING_RE.match(text.strip())
        if not match:
            continue
        raw = match.group("text")
        explicit = explicit_id(raw)
        slug = explicit or slugify(raw)
        if not slug:
            continue
        if explicit is None:
            base = slug
            suffix = 1
            while slug in slugs:
                slug = f"{base}-{suffix}"
                suffix += 1
        slugs.setdefault(slug, lineno)
    return slugs
