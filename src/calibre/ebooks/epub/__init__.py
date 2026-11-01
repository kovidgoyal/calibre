# License: GPLv3 Copyright: 2008, Kovid Goyal kovid@kovidgoyal.net

"""
Conversion to EPUB.
"""

from typing import TYPE_CHECKING

from calibre.utils.zipfile import ZIP_STORED, ZipFile

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from css_parser.css import CSSStyleRule, CSSStyleSheet


def rules(stylesheets: Iterable[CSSStyleSheet]) -> Iterator[CSSStyleRule]:
    for s in stylesheets:
        if hasattr(s, 'cssText'):
            for r in s:
                if r.type == r.STYLE_RULE:
                    yield r


def simple_container_xml(opf_path: str, extra_entries: str = '') -> str:
    return f'''\
<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
   <rootfiles>
      <rootfile full-path="{opf_path}" media-type="application/oebps-package+xml"/>
      {extra_entries}
   </rootfiles>
</container>
    '''


def initialize_container(
    path_to_container: str, opf_name: str = 'metadata.opf', extra_entries: Sequence[tuple[str, str, bytes | str]] | None = None
) -> ZipFile:
    """
    Create an empty EPUB document, with a default skeleton.
    """
    if extra_entries is None:
        extra_entries = []
    rootfiles = ''
    for path, mimetype, _ in extra_entries:
        rootfiles += f'<rootfile full-path="{path}" media-type="{mimetype}"/>'
    CONTAINER = simple_container_xml(opf_name, rootfiles).encode('utf-8')
    zf = ZipFile(path_to_container, 'w')
    zf.writestr('mimetype', b'application/epub+zip', compression=ZIP_STORED)
    zf.writestr('META-INF/', b'', 0o755)
    zf.writestr('META-INF/container.xml', CONTAINER)
    for path, _, data in extra_entries:
        zf.writestr(path, data)
    return zf
