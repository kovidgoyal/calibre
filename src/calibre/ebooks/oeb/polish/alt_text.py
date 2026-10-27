#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

# Find all images in a book and set their alternative text, used by the Edit
# book tool for describing images

from typing import NamedTuple

from calibre.ebooks.oeb.base import OEB_DOCS, XHTML
from calibre.ebooks.oeb.polish.container import Container

IMG = XHTML('img')
CONTEXT_TAGS = frozenset(map(XHTML, ('p', 'figure', 'li', 'td', 'th', 'dd', 'blockquote', 'section', 'div', 'body')))
MAX_CONTEXT_LENGTH = 300


class ImageUse(NamedTuple):
    html_name: str  # The HTML file containing the <img> tag
    index: int  # The position of the <img> tag among all <img> tags in the HTML file
    image_name: str | None  # The image file, None if it is missing or remote
    sourceline: int | None
    alt: str | None  # None when the alt attribute is missing, an empty string means the image is decorative
    context: str  # Text surrounding the image, to help describe it


def html_names(container: Container) -> list[str]:
    # Spine order first, then any HTML files not in the spine
    ans = [name for name, linear in container.spine_names]
    seen = set(ans)
    ans.extend(sorted(name for name, mt in container.mime_map.items() if mt in OEB_DOCS and name not in seen))
    return ans


def context_text(img) -> str:
    parent = img.getparent()
    while parent is not None and parent.tag not in CONTEXT_TAGS:
        parent = parent.getparent()
    if parent is None:
        return ''
    if parent.tag == XHTML('figure'):
        for caption in parent.iter(XHTML('figcaption')):
            text = ' '.join(''.join(caption.itertext()).split())
            if text:
                return text
    text = ' '.join(''.join(parent.itertext()).split())
    if len(text) > MAX_CONTEXT_LENGTH:
        text = text[: MAX_CONTEXT_LENGTH - 1].rstrip() + '…'
    return text


def image_uses(container: Container) -> list[ImageUse]:
    ans = []
    for name in html_names(container):
        root = container.parsed(name)
        for i, img in enumerate(root.iter(IMG)):
            src = (img.get('src') or '').strip()
            image_name = container.href_to_name(src, name) if src else None
            if image_name is not None and not container.has_name(image_name):
                image_name = None
            ans.append(ImageUse(name, i, image_name, img.sourceline, img.get('alt'), context_text(img)))
    return ans


def set_alt_text(container: Container, changes: dict[tuple[str, int], str | None]) -> set[str]:
    """
    Set the alternative text of images. ``changes`` maps (html_name, index), as
    in :class:`ImageUse`, to the new alternative text. Use an empty string for
    decorative images and None to remove the alt attribute. Returns the names
    of the changed HTML files.
    """
    by_name: dict[str, dict[int, str | None]] = {}
    for (name, index), alt in changes.items():
        by_name.setdefault(name, {})[index] = alt
    changed = set()
    for name, alts in by_name.items():
        root = container.parsed(name)
        for i, img in enumerate(root.iter(IMG)):
            if i not in alts:
                continue
            alt = alts[i]
            if alt == img.get('alt'):
                continue
            if alt is None:
                del img.attrib['alt']
            else:
                img.set('alt', alt)
            changed.add(name)
        if name in changed:
            container.dirty(name)
    return changed
