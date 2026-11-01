# License: GPLv3 Copyright: 2008, Marshall T. Vandegrift <llasram@gmail.com>

"""
OPF manifest trimming transform.
"""

from typing import TYPE_CHECKING, Self
from urllib.parse import urldefrag

from lxml import etree

from calibre.ebooks.oeb.base import CSS_MIME, OEB_DOCS, iterlinks, urlnormalize

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.conversion.plumber import OptionValues
    from calibre.ebooks.oeb.base import Manifest, OEBBook


class ManifestTrimmer:
    @classmethod
    def config[T](cls, cfg: T) -> T:
        return cfg

    @classmethod
    def generate(cls, opts: Values) -> Self:
        return cls()

    def __call__(self, oeb: OEBBook, context: Values | OptionValues) -> None:
        import css_parser

        oeb.logger.info('Trimming unused files from manifest...')
        self.opts = context
        used: set[Manifest.Item] = set()
        for term in oeb.metadata:
            for item in oeb.metadata[term]:
                if item.value in oeb.manifest.hrefs:
                    used.add(oeb.manifest.hrefs[item.value])
                elif item.value in oeb.manifest.ids:
                    used.add(oeb.manifest.ids[item.value])
        for ref in oeb.guide.values():
            path, _ = urldefrag(ref.href)
            if path in oeb.manifest.hrefs:
                used.add(oeb.manifest.hrefs[path])
        # TOC items are required to be in the spine
        for item in oeb.spine:
            used.add(item)
        unchecked = used
        while unchecked:
            new: set[Manifest.Item] = set()
            for item in unchecked:
                if (item.media_type in OEB_DOCS or item.media_type[-4:] in ('/xml', '+xml')) and (root := item.data) is not None:
                    assert isinstance(root, etree._Element)  # (X)HTML and XML items are parsed, iterlinks() asserted this too
                    hrefs = [r[2] for r in iterlinks(root)]
                    for href in hrefs:
                        if isinstance(href, bytes):
                            href = href.decode('utf-8')
                        try:
                            href = item.abshref(urlnormalize(href))
                        except Exception:
                            continue
                        if href in oeb.manifest.hrefs:
                            found = oeb.manifest.hrefs[href]
                            if found not in used:
                                new.add(found)
                elif item.media_type == CSS_MIME:
                    for href in css_parser.getUrls(item.data):
                        href = item.abshref(urlnormalize(href))
                        if href in oeb.manifest.hrefs:
                            found = oeb.manifest.hrefs[href]
                            if found not in used:
                                new.add(found)
            used.update(new)
            unchecked = new
        for item in oeb.manifest.values():
            if item not in used:
                oeb.logger.info(f'Trimming {item.href!r} from manifest')
                oeb.manifest.remove(item)
