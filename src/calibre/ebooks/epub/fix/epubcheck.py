#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.epub.fix import ePubFixer, InvalidEpub
from calibre.utils.date import parse_date, strptime


class Epubcheck(ePubFixer):

    name = 'Workaround epubcheck bugs'

    @property
    def short_description(self):
        return _('Workaround epubcheck bugs')

    @property
    def long_description(self):
        return _('Workarounds for bugs in the latest release of epubcheck. '
                'epubcheck reports many things as errors that are not '
                'actually errors. epub-fix will try to detect these and replace '
                'them with constructs that epubcheck likes. This may cause '
                'significant changes to your epub, complain to the epubcheck '
                'project.')

    @property
    def fix_name(self):
        return 'epubcheck'

    def fix_pubdates(self):
        dirtied = False
        opf = self.container.opf
        for dcdate in opf.xpath('//dc:date',
                namespaces={'dc':'http://purl.org/dc/elements/1.1/'}):
            raw = dcdate.text
            if not raw: raw = ''
            default = strptime('2000-1-1', '%Y-%m-%d', as_utc=True)
            try:
                ts = parse_date(raw, assume_utc=False, as_utc=True,
                        default=default)
            except:
                raise InvalidEpub('Invalid date set in OPF', raw)
            try:
                sval = ts.strftime('%Y-%m-%d')
            except:
                from calibre import strftime
                sval = strftime('%Y-%m-%d', ts.timetuple())
            if sval != raw:
                self.log.error(
                    'OPF contains date', raw, 'that epubcheck does not like')
                if self.fix:
                    dcdate.text = sval
                    self.log('\tReplaced', raw, 'with', sval)
                    dirtied = True
        if dirtied:
            self.container.set(self.container.opf_name, opf)

    def fix_preserve_aspect_ratio(self):
        for name in self.container.name_map:
            mt = self.container.mime_map.get(name, '')
            if mt.lower() == 'application/xhtml+xml':
                root = self.container.get(name)
                dirtied = False
                for svg in root.xpath('//svg:svg[@preserveAspectRatio="none"]',
                        namespaces={'svg':'http://www.w3.org/2000/svg'}):
                    self.log.error('Found <svg> element with'
                            ' preserveAspectRatio="none" which epubcheck '
                            'cannot handle')
                    if self.fix:
                        svg.set('preserveAspectRatio', 'xMidYMid meet')
                        dirtied = True
                        self.log('\tReplaced none with xMidYMid meet')
                if dirtied:
                    self.container.set(name, root)


    def run(self, container, opts, log, fix=False):
        self.container = container
        self.opts = opts
        self.log = log
        self.fix = fix
        self.fix_pubdates()
        self.fix_preserve_aspect_ratio()
