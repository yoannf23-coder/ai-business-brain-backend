"""Génération du balisage Gutenberg à partir de sections simples du JSON."""

import html
import json


def esc(text):
    return html.escape(text, quote=False)


def _heading(text, level=2, align=None):
    attrs = {"level": level}
    if align:
        attrs["textAlign"] = align
    json_attrs = json.dumps(attrs, separators=(",", ":"))
    cls = f' class="has-text-align-{align}"' if align else ""
    return (
        f"<!-- wp:heading {json_attrs} -->\n"
        f"<h{level}{cls}>{esc(text)}</h{level}>\n"
        "<!-- /wp:heading -->"
    )


def _paragraph(text, align=None):
    attrs = f' {{"align":"{align}"}}' if align else ""
    cls = f' class="has-text-align-{align}"' if align else ""
    return (
        f"<!-- wp:paragraph{attrs} -->\n"
        f"<p{cls}>{esc(text)}</p>\n"
        "<!-- /wp:paragraph -->"
    )


def _button(label, url):
    return (
        '<!-- wp:buttons {"layout":{"type":"flex","justifyContent":"center"}} -->\n'
        '<div class="wp-block-buttons">\n'
        "<!-- wp:button -->\n"
        '<div class="wp-block-button">'
        f'<a class="wp-block-button__link wp-element-button" href="{esc(url)}">{esc(label)}</a>'
        "</div>\n"
        "<!-- /wp:button -->\n"
        "</div>\n"
        "<!-- /wp:buttons -->"
    )


def hero(section):
    inner = [_heading(section["title"], level=1, align="center")]
    if section.get("subtitle"):
        inner.append(_paragraph(section["subtitle"], align="center"))
    if section.get("button"):
        inner.append(_button(section["button"]["label"], section["button"]["url"]))
    body = "\n\n".join(inner)
    return (
        '<!-- wp:group {"align":"full","layout":{"type":"constrained"}} -->\n'
        '<div class="wp-block-group alignfull">\n'
        f"{body}\n"
        "</div>\n"
        "<!-- /wp:group -->"
    )


def text(section):
    parts = []
    if section.get("title"):
        parts.append(_heading(section["title"]))
    for para in section.get("paragraphs", []):
        parts.append(_paragraph(para))
    return "\n\n".join(parts)


def features(section):
    columns = []
    for item in section["items"]:
        inner = [_heading(item["title"], level=3)]
        if item.get("text"):
            inner.append(_paragraph(item["text"]))
        columns.append(
            "<!-- wp:column -->\n"
            '<div class="wp-block-column">\n'
            + "\n\n".join(inner)
            + "\n</div>\n"
            "<!-- /wp:column -->"
        )
    head = _heading(section["title"]) + "\n\n" if section.get("title") else ""
    return (
        head
        + "<!-- wp:columns -->\n"
        '<div class="wp-block-columns">\n'
        + "\n\n".join(columns)
        + "\n</div>\n"
        "<!-- /wp:columns -->"
    )


def listing(section):
    parts = []
    if section.get("title"):
        parts.append(_heading(section["title"]))
    if section.get("intro"):
        parts.append(_paragraph(section["intro"]))
    items = "\n".join(f"<li>{esc(item)}</li>" for item in section["items"])
    parts.append(
        '<!-- wp:list -->\n<ul class="wp-block-list">\n'
        + items
        + "\n</ul>\n<!-- /wp:list -->"
    )
    return "\n\n".join(parts)


def cta(section):
    parts = [_heading(section["title"], align="center")]
    if section.get("text"):
        parts.append(_paragraph(section["text"], align="center"))
    if section.get("button"):
        parts.append(_button(section["button"]["label"], section["button"]["url"]))
    return "\n\n".join(parts)


def contact(section):
    parts = []
    if section.get("title"):
        parts.append(_heading(section["title"]))
    lines = []
    for key, label in (("email", "Email"), ("phone", "Téléphone"), ("address", "Adresse")):
        if section.get(key):
            lines.append(f"<li>{esc(label)} : {esc(section[key])}</li>")
    if lines:
        parts.append(
            "<!-- wp:list -->\n<ul class=\"wp-block-list\">\n"
            + "\n".join(lines)
            + "\n</ul>\n<!-- /wp:list -->"
        )
    if section.get("note"):
        parts.append(_paragraph(section["note"]))
    return "\n\n".join(parts)


RENDERERS = {
    "hero": hero,
    "text": text,
    "list": listing,
    "features": features,
    "cta": cta,
    "contact": contact,
}


def render(sections):
    out = []
    for section in sections:
        kind = section.get("type")
        if kind not in RENDERERS:
            raise ValueError(f"Type de section inconnu : {kind!r}")
        out.append(RENDERERS[kind](section))
    return "\n\n".join(out)
