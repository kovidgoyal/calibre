#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, sys, os, time
from collections import namedtuple
from functools import partial

from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.stats import StatsCollector
from calibre.ebooks.oeb.polish.subset import subset_all_fonts
from calibre.ebooks.oeb.polish.cover import set_cover
from calibre.ebooks.oeb.polish.jacket import (
    replace_jacket, add_or_replace_jacket, find_existing_jacket, remove_jacket)
from calibre.utils.logging import Log

ALL_OPTS = {
    'subset': False,
    'opf': None,
    'cover': None,
    'jacket': False,
    'remove_jacket':False,
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

<p>Note that polishing only works on files in the %s formats.</p>
''')%_(' or ').join('<b>%s</b>'%x for x in SUPPORTED),

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

'jacket': _('''\
<p>Insert a "book jacket" page at the start of the book that contains
all the book metadata such as title, tags, authors, series, commets,
etc.</p>'''),

'remove_jacket': _('''\
<p>Remove a previous inserted book jacket page.</p>
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

def update_metadata(ebook, new_opf):
    from calibre.ebooks.metadata.opf2 import OPF
    from calibre.ebooks.metadata.epub import update_metadata
    opfpath = ebook.name_to_abspath(ebook.opf_name)
    with ebook.open(ebook.opf_name, 'r+b') as stream, open(new_opf, 'rb') as ns:
        opf = OPF(stream, basedir=os.path.dirname(opfpath), populate_spine=False,
                  unquote_urls=False)
        mi = OPF(ns, unquote_urls=False,
                      populate_spine=False).to_book_metadata()
        mi.cover, mi.cover_data = None, (None, None)

        update_metadata(opf, mi, apply_null=True, update_timestamp=True)
        stream.seek(0)
        stream.truncate()
        stream.write(opf.render())

def polish(file_map, opts, log, report):
    rt = lambda x: report('\n### ' + x)
    st = time.time()
    for inbook, outbook in file_map.iteritems():
        report(_('## Polishing: %s')%(inbook.rpartition('.')[-1].upper()))
        ebook = get_container(inbook, log)
        jacket = None

        if opts.subset:
            stats = StatsCollector(ebook)

        if opts.opf:
            rt(_('Updating metadata'))
            update_metadata(ebook, opts.opf)
            jacket = find_existing_jacket(ebook)
            if jacket is not None:
                replace_jacket(ebook, jacket)
                report(_('Updated metadata jacket'))
            report(_('Metadata updated\n'))

        if opts.subset:
            rt(_('Subsetting embedded fonts'))
            subset_all_fonts(ebook, stats.font_stats, report)
            report('')

        if opts.cover:
            rt(_('Setting cover'))
            set_cover(ebook, opts.cover, report)
            report('')

        if opts.jacket:
            rt(_('Inserting metadata jacket'))
            if jacket is None:
                if add_or_replace_jacket(ebook):
                    report(_('Existing metadata jacket replaced'))
                else:
                    report(_('Metadata jacket inserted'))
            else:
                report(_('Existing metadata jacket replaced'))
            report('')

        if opts.remove_jacket:
            rt(_('Removing metadata jacket'))
            if remove_jacket(ebook):
                report(_('Metadata jacket removed'))
            else:
                report(_('No metadata jacket found'))
            report('')

        ebook.commit(outbook)
        report('-'*70)
    report(_('Polishing took: %.1f seconds')%(time.time()-st))

REPORT = '{0} REPORT {0}'.format('-'*30)

def gui_polish(data):
    files = data.pop('files')
    if not data.pop('metadata'):
        data.pop('opf')
        data.pop('cover')
    file_map = {x:x for x in files}
    opts = ALL_OPTS.copy()
    opts.update(data)
    O = namedtuple('Options', ' '.join(ALL_OPTS.iterkeys()))
    opts = O(**opts)
    log = Log(level=Log.DEBUG)
    report = []
    polish(file_map, opts, log, report.append)
    log('')
    log(REPORT)
    for msg in report:
        log(msg)
    return '\n\n'.join(report)

def option_parser():
    from calibre.utils.config import OptionParser
    USAGE = '%prog [options] input_file [output_file]\n\n' + re.sub(
        r'<.*?>', '', CLI_HELP['about'])
    parser = OptionParser(usage=USAGE)
    a = parser.add_option
    o = partial(a, default=False, action='store_true')
    o('--subset-fonts', '-f', dest='subset', help=CLI_HELP['subset'])
    a('--cover', '-c', help=_(
        'Path to a cover image. Changes the cover specified in the ebook. '
        'If no cover is present, or the cover is not properly identified, inserts a new cover.'))
    a('--opf', '-o', help=_(
        'Path to an OPF file. The metadata in the book is updated from the OPF file.'))
    o('--jacket', '-j', help=CLI_HELP['jacket'])
    o('--remove-jacket', help=CLI_HELP['remove_jacket'])

    o('--verbose', help=_('Produce more verbose output, useful for debugging.'))

    return parser

def main(args=None):
    parser = option_parser()
    opts, args = parser.parse_args(args or sys.argv[1:])
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
    if not tuple(filter(None, (getattr(popts, name) for name in ALL_OPTS))):
        parser.print_help()
        log.error(_('You must specify at least one action to perform'))
        raise SystemExit(1)

    polish({inbook:outbook}, popts, log, report.append)
    log('')
    log(REPORT)
    for msg in report:
        log(msg)

    log('Output written to:', outbook)

if __name__ == '__main__':
    main()

