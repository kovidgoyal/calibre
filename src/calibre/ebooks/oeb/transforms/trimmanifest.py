'''
OPF manifest trimming transform.
'''


__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

from calibre.ebooks.oeb.base import CSS_MIME, OEB_DOCS
from calibre.ebooks.oeb.base import urlnormalize, iterlinks
from polyglot.urllib import urldefrag


class ManifestTrimmer(object):

    @classmethod
    def config(cls, cfg):
        return cfg

    @classmethod
    def generate(cls, opts):
        return cls()

    def __call__(self, oeb, context):
        import css_parser
        oeb.logger.info('Trimming unused files from manifest...')
        self.opts = context
        used = set()
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
            new = set()
            for item in unchecked:
                if (item.media_type in OEB_DOCS or
                    item.media_type[-4:] in ('/xml', '+xml')) and \
                   item.data is not None:
                    hrefs = [r[2] for r in iterlinks(item.data)]
                    for href in hrefs:
                        if isinstance(href, bytes):
                            href = href.decode('utf-8')
                        try:
                            href = item.abshref(urlnormalize(href))
                        except:
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
                oeb.logger.info('Trimming %r from manifest' % item.href)
                oeb.manifest.remove(item)
