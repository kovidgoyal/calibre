#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from collections import namedtuple
from functools import partial

from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.stats import StatsCollector
from calibre.ebooks.oeb.polish.subset import subset_all_fonts
from calibre.ebooks.oeb.polish.cover import set_cover
from calibre.utils.logging import Log

ALL_OPTS = {
    'subset': False,
    'opf': None,
    'cover': None,
}

SUPPORTED = {'EPUB', 'AZW3'}

# Help {{{
HELP = {'about': _(
'''\
<p><i>Polishing books</i> is all about putting the shine of perfection onto
your carefully crafted ebooks.</p>

<p>Polishing tries to minimize the changes to the internal code of your ebook.
Unlike conversion, it <i>does not</i> flatten CSS, rename files, change font
sizes, adjust margins, etc. Every action performs only the minimum set of
changes needed for the desired effect.</p>

<p>You should use this tool as the last step in your ebook creation process.</p>

<p>Note that polishing only works on files in the <b>%s</b> formats.</p>
''')%_(' or ').join(SUPPORTED),

'subset': _('''\
<p>Subsetting fonts means reducing an embedded font to contain
only the characters used from that font in the book. This
greatly reduces the size of the font files (halving the font
file sizes is common).</p>

<p>For example, if the book uses a specific font for headers,
then subsetting will reduce that font to contain only the
characters present in the actual headers in the book. Or if the
book embeds the bold and italic versions of a font, but bold
and italic text is relatively rare, or absent altogether, then
the bold and italic fonts can either be reduced to only a few
characters or completely removed.</p>

<p>The only downside to subsetting fonts is that if, at a later
date you decide to add more text to your books, the newly added
text might not be covered by the subset font.</p>
'''),
}

def hfix(name, raw):
    if name == 'about':
        return raw
    raw = raw.replace('\n\n', '__XX__')
    raw = raw.replace('\n', ' ')
    raw = raw.replace('__XX__', '\n')
    return raw

CLI_HELP = {x:hfix(x, re.sub('<.*?>', '', y)) for x, y in HELP.iteritems()}
# }}}

def polish(file_map, opts, log, report):
    rt = lambda x: report('\n### ' + x)
    for inbook, outbook in file_map.iteritems():
        report('Polishing: %s'%(inbook.rpartition('.')[-1].upper()))
        ebook = get_container(inbook, log)

        if opts.subset:
            stats = StatsCollector(ebook)

        if opts.subset:
            rt('Subsetting embedded fonts')
            subset_all_fonts(ebook, stats.font_stats, report)
            report('')

        if opts.cover:
            rt('Setting cover')
            set_cover(ebook, opts.cover, report)
            report('')

        ebook.commit(outbook)

def gui_polish(data):
    files = data.pop('files')
    file_map = {x:x for x in files}
    opts = ALL_OPTS.copy()
    opts.update(data)
    O = namedtuple('Options', ' '.join(data.iterkeys()))
    opts = O(**opts)
    log = Log(level=Log.DEBUG)
    report = []
    polish(file_map, opts, log, report.append)
    log('\n', '-'*30, ' REPORT ', '-'*30)
    for msg in report:
        log(msg)

def option_parser():
    from calibre.utils.config import OptionParser
    USAGE = '%prog [options] input_file [output_file]\n\n' + re.sub(
        r'<.*?>', '', CLI_HELP['about'])
    parser = OptionParser(usage=USAGE)
    a = parser.add_option
    o = partial(a, default=False, action='store_true')
    o('--subset-fonts', '-f', dest='subset', help=CLI_HELP['subset'])
    a('--cover', help=_(
        'Path to a cover image. Changes the cover specified in the ebook. '
        'If no cover is present, inserts a new cover.'))
    o('--verbose', help=_('Produce more verbose output, useful for debugging.'))

    return parser

def main():
    parser = option_parser()
    opts, args = parser.parse_args()
    log = Log(level=Log.DEBUG if opts.verbose else Log.INFO)
    if not args:
        parser.print_help()
        log.error(_('You must provide the input file to polish'))
        raise SystemExit(1)
    if len(args) > 2:
        parser.print_help()
        log.error(_('Unknown extra arguments'))
        raise SystemExit(1)
    if len(args) == 1:
        inbook = args[0]
        base, ext = inbook.rpartition('.')[0::2]
        outbook = base + '_polished.' + ext
    else:
        inbook, outbook = args

    popts = ALL_OPTS.copy()
    for k, v in popts.iteritems():
        popts[k] = getattr(opts, k, None)

    O = namedtuple('Options', ' '.join(popts.iterkeys()))
    popts = O(**popts)
    report = []
    something = False
    for name in ALL_OPTS:
        if name not in {'opf', }:
            if getattr(popts, name):
                something = True

    if not something:
        parser.print_help()
        log.error(_('You must specify at least one action to perform'))
        raise SystemExit(1)

    polish({inbook:outbook}, popts, log, report.append)
    log('\n', '-'*30, ' REPORT ', '-'*30)
    for msg in report:
        log(msg)

    log('Output written to:', outbook)

if __name__ == '__main__':
    main()

