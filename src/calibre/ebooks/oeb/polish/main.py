#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

import re
import sys
import time
from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING, NamedTuple, TypedDict, cast

from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.cover import set_cover
from calibre.ebooks.oeb.polish.css import remove_unused_css
from calibre.ebooks.oeb.polish.download import download_external_resources, get_external_resources, replace_resources
from calibre.ebooks.oeb.polish.embed import embed_all_fonts
from calibre.ebooks.oeb.polish.hyphenation import add_soft_hyphens, remove_soft_hyphens
from calibre.ebooks.oeb.polish.images import compress_images, remove_unused_images
from calibre.ebooks.oeb.polish.jacket import add_or_replace_jacket, find_existing_jacket, remove_jacket, replace_jacket
from calibre.ebooks.oeb.polish.pretty import fix_all_html, pretty_all
from calibre.ebooks.oeb.polish.replace import smarten_punctuation
from calibre.ebooks.oeb.polish.stats import StatsCollector
from calibre.ebooks.oeb.polish.subset import iter_subsettable_fonts, subset_all_fonts
from calibre.ebooks.oeb.polish.upgrade import upgrade_book
from calibre.utils.localization import _, ngettext
from calibre.utils.logging import Log

if TYPE_CHECKING:
    from calibre.ebooks.oeb.polish.container import Container
    from calibre.utils.config import OptionParser

type Report = Callable[[str], object]


class Opts(NamedTuple):
    embed: bool = False
    subset: bool = False
    opf: str | None = None
    cover: str | None = None
    jacket: bool = False
    remove_jacket: bool = False
    smarten_punctuation: bool = False
    remove_unused_css: bool = False
    remove_unused_images: bool = False
    compress_images: bool = False
    upgrade_book: bool = False
    add_soft_hyphens: bool = False
    remove_soft_hyphens: bool = False
    download_external_resources: bool = False
    cleanup: bool = False


class PolishActions(TypedDict, total=False):
    embed: bool
    subset: bool
    opf: str | None
    cover: str | None
    jacket: bool
    remove_jacket: bool
    smarten_punctuation: bool
    remove_unused_css: bool
    remove_unused_images: bool
    compress_images: bool
    upgrade_book: bool
    add_soft_hyphens: bool
    remove_soft_hyphens: bool
    download_external_resources: bool
    cleanup: bool


class GuiPolishData(PolishActions, total=False):
    files: list[str]
    metadata: bool
    do_cover: bool


ALL_OPTS = Opts._field_defaults.copy()

CUSTOMIZATION = {
    'remove_unused_classes': False,
    'merge_identical_selectors': False,
    'merge_rules_with_identical_properties': False,
    'remove_unreferenced_sheets': True,
    'remove_ncx': True,
}

SUPPORTED = {'EPUB', 'AZW3', 'KEPUB'}

# Help {{{
HELP = {
    'about': _(
        '''\
<p><i>Polishing books</i> is all about putting the shine of perfection onto
your carefully crafted e-books.</p>

<p>Polishing tries to minimize the changes to the internal code of your e-book.
Unlike conversion, it <i>does not</i> flatten CSS, rename files, change font
sizes, adjust margins, etc. Every action performs only the minimum set of
changes needed for the desired effect.</p>

<p>You should use this tool as the last step in your e-book creation process.</p>
{0}
<p>Note that polishing only works on files in the %s formats.</p>\
'''
    )
    % _(' or ').join(sorted(f'<b>{x}</b>' for x in SUPPORTED)),
    'embed': _('''\
<p>Embed all fonts that are referenced in the document and are not already embedded.
This will scan your computer for the fonts, and if they are found, they will be
embedded into the document.</p>
<p>Please ensure that you have the proper license for embedding the fonts used in this document.</p>
'''),
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
all the book metadata such as title, tags, authors, series, comments,
etc. Any previous book jacket will be replaced.</p>'''),
    'remove_jacket': _('''\
<p>Remove a previous inserted book jacket page.</p>
'''),
    'smarten_punctuation': _('''\
<p>Convert plain text dashes, ellipsis, quotes, multiple hyphens, etc. into their
typographically correct equivalents.</p>
<p>Note that the algorithm can sometimes generate incorrect results, especially
when single quotes at the start of contractions are involved.</p>
'''),
    'remove_unused_css': _('''\
<p>Remove all unused CSS rules from stylesheets and &lt;style&gt; tags. Some books
created from production templates can have a large number of extra CSS rules
that don't match any actual content. These extra rules can slow down readers
that need to parse them all.</p>
'''),
    'compress_images': _('''\
<p>Losslessly compress images in the book, to reduce the filesize, without
affecting image quality.</p>
'''),
    'upgrade_book': _('''\
<p>Upgrade the internal structures of the book, if possible. For instance,
upgrades EPUB 2 books to EPUB 3 books.</p>
'''),
    'add_soft_hyphens': _('''\
<p>Add soft hyphens to all words in the book. This allows the book to be rendered
better when the text is justified, in readers that do not support hyphenation.</p>
'''),
    'remove_soft_hyphens': _('''\
<p>Remove soft hyphens from all text in the book.</p>
'''),
    'download_external_resources': _('''\
<p>Download external resources such as images, stylesheets, etc. that point to URLs instead of files in the book.
All such resources will be downloaded and added to the book so that the book no longer references any external resources.
</p>
'''),
    'cleanup': _('''\
<p>Clean up the internals of the book. This performs the following actions:</p>
<ul>
<li>Fix any errors in the HTML markup of all HTML files in the book, such as unclosed tags.
This is the same as the <i>Fix HTML - all files</i> tool in the calibre e-book editor.</li>
<li>Remove all images that are not referenced by any HTML file in the book or by
any stylesheet used by those files. The cover image is always kept.</li>
<li>Check the book for errors and automatically fix all errors that can be fixed automatically.
This is the same as running <i>Check book</i> in the calibre e-book editor and then
using <i>Try to fix all fixable errors automatically</i>. Rules that you have chosen
to skip in the <i>Check book</i> tool of the editor are skipped here as well.
Errors that cannot be fixed automatically are listed in the report.</li>
<li>Beautify (pretty print) all HTML, CSS and XML files in the book, making them easier to read
and edit. This is the same as the <i>Beautify all files</i> tool in the calibre e-book editor.</li>
</ul>
<p>Note that unlike the other actions, this re-formats the code of the
book and can rename files, so it changes the internals of the book a lot more.</p>
'''),
}


def hfix(name: str, raw: str) -> str:
    if name == 'about':
        return raw.format('')
    raw = raw.replace('\n\n', '__XX__')
    raw = raw.replace('\n', ' ')
    raw = raw.replace('__XX__', '\n')
    raw = raw.replace('&lt;', '<').replace('&gt;', '>')
    return raw


CLI_HELP = {x: hfix(x, re.sub(r'<.*?>', '', y)) for x, y in HELP.items()}
# }}}


def update_metadata(ebook: Container, new_opf: str) -> None:
    from calibre.ebooks.metadata.opf import get_metadata, set_metadata

    with ebook.open(ebook.opf_name, 'r+b') as stream, open(new_opf, 'rb') as ns:
        mi = get_metadata(ns)[0]
        mi.cover, mi.cover_data = None, (None, None)
        opfbytes = set_metadata(stream, mi, apply_null=True, update_timestamp=True)[0]
        stream.seek(0)
        stream.truncate()
        stream.write(opfbytes)


def download_resources(ebook: Container, report: Report) -> bool:
    changed = False
    url_to_referrer_map = get_external_resources(ebook)
    if url_to_referrer_map:
        n = len(url_to_referrer_map)
        report(ngettext('Downloading one external resource', 'Downloading {} external resources', n).format(n))
        replacements, failures = download_external_resources(ebook, url_to_referrer_map)
        if not failures:
            report(_('Successfully downloaded all resources'))
        else:
            tb = [f'{url}\n\t{err}\n' for url, err in failures.items()]
            if replacements:
                report(_('Failed to download some resources, see details below:'))
            else:
                report(_('Failed to download all resources, see details below:'))
            report(''.join(tb))
        if replacements:
            if replace_resources(ebook, url_to_referrer_map, replacements):
                changed = True
    else:
        report(_('No external resources found in book'))
    return changed


def check_book_skipped_rules() -> frozenset[str]:
    # The rules the user has chosen to skip in the Check book tool of the
    # editor, read directly from the editor preferences to avoid importing GUI
    # code in the polishing worker
    from calibre.utils.config import JSONConfig

    return frozenset(JSONConfig('tweak_book_gui').get('check_book_skipped_rules', None) or ())


def check_and_fix(ebook: Container, report: Report, skipped_rules: frozenset[str] | None = None) -> bool:
    from calibre.ebooks.oeb.polish.check.base import WARN, BaseError
    from calibre.ebooks.oeb.polish.check.main import fix_errors, run_checks

    def key(err: BaseError) -> tuple[str, str, str]:
        return type(err).__name__, err.name, err.msg

    if skipped_rules is None:
        skipped_rules = check_book_skipped_rules()
    remaining = run_checks(ebook, skipped_rules)
    if not remaining:
        report(_('No errors found'))
        return False
    seen = {key(e) for e in remaining}
    changed = False
    # Fixing some errors, such as fatal parsing errors, allows further checks
    # to run, which can find more errors to fix, so do a few passes, stopping
    # when a pass makes no progress
    for _pass in range(3):
        if not fix_errors(ebook, remaining, skipped_rules):
            break
        changed = True
        before = {key(e) for e in remaining}
        remaining = run_checks(ebook, skipped_rules)
        after = {key(e) for e in remaining}
        seen |= after
        if not remaining or after == before:
            break
    num = len(seen)
    report(ngettext('Found one error', 'Found {} errors', num).format(num))
    fixed = len(seen - {key(e) for e in remaining})
    report(ngettext('Fixed one error', 'Fixed {} errors', fixed).format(fixed))
    if remaining:
        n = len(remaining)
        report(ngettext('One error could not be fixed automatically:', '{} errors could not be fixed automatically:', n).format(n))
        for err in remaining:
            loc = err.name if err.line is None else f'{err.name}:{err.line}'
            level = _('Error') if err.level > WARN else _('Warning') if err.level == WARN else _('Info')
            report(f'  [{level}] {loc}: {err.msg}')
        if any(err.level > WARN for err in remaining):
            report(_('Some checks are only run once there are no errors, so the book may have more problems than are listed above.'))
    return changed


def polish_one(ebook: Container, opts: Opts, report: Report, customization: dict[str, bool] | None = None) -> bool:
    def rt(x: str) -> object:
        return report('\n### ' + x)

    jacket = None
    changed = False
    customization = customization or CUSTOMIZATION.copy()

    # Fixing HTML and errors runs first as it can change the HTML of the book
    # and rename files, which the other actions, such as font subsetting,
    # depend on. Unused images are removed before checking so that errors in
    # them, such as corrupted images, which prevent other checks from running,
    # are not reported.
    if opts.cleanup:
        rt(_('Fixing HTML'))
        fix_all_html(ebook)
        changed = True
        report(_('All HTML files fixed\n'))
        rt(_('Removing unused images'))
        if remove_unused_images(ebook, report):
            changed = True
        report('')
        rt(_('Checking book and fixing errors'))
        if check_and_fix(ebook, report):
            changed = True
        report('')

    has_subsettable_fonts = False
    for x in iter_subsettable_fonts(ebook):
        has_subsettable_fonts = True
        break

    if (opts.subset and has_subsettable_fonts) or opts.embed:
        stats = StatsCollector(ebook, do_embed=opts.embed)

    if opts.opf:
        changed = True
        rt(_('Updating metadata'))
        update_metadata(ebook, opts.opf)
        jacket = find_existing_jacket(ebook)
        if jacket is not None:
            replace_jacket(ebook, jacket)
            report(_('Updated metadata jacket'))
        report(_('Metadata updated\n'))

    if opts.cover:
        changed = True
        rt(_('Setting cover'))
        set_cover(ebook, opts.cover, report)
        report('')

    if opts.jacket:
        changed = True
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
            changed = True
        else:
            report(_('No metadata jacket found'))
        report('')

    if opts.smarten_punctuation:
        rt(_('Smartening punctuation'))
        if smarten_punctuation(ebook, report):
            changed = True
        report('')

    if opts.embed:
        rt(_('Embedding referenced fonts'))
        if embed_all_fonts(ebook, stats, report):
            changed = True
            has_subsettable_fonts = True
        report('')

    if opts.subset:
        if has_subsettable_fonts:
            rt(_('Subsetting embedded fonts'))
            if subset_all_fonts(ebook, stats.font_stats, report):
                changed = True
        else:
            rt(_('No embedded fonts to subset'))
        report('')

    if opts.remove_unused_css:
        rt(_('Removing unused CSS rules'))
        if remove_unused_css(
            ebook,
            report,
            remove_unused_classes=customization['remove_unused_classes'],
            merge_rules=customization['merge_identical_selectors'],
            merge_rules_with_identical_properties=customization['merge_rules_with_identical_properties'],
            remove_unreferenced_sheets=customization['remove_unreferenced_sheets'],
        ):
            changed = True
        report('')

    if opts.remove_unused_images and not opts.cleanup:
        rt(_('Removing unused images'))
        if remove_unused_images(ebook, report):
            changed = True
        report('')

    if opts.compress_images:
        rt(_('Losslessly compressing images'))
        if compress_images(ebook, report)[0]:
            changed = True
        report('')

    if opts.upgrade_book:
        rt(_('Upgrading book, if possible'))
        if upgrade_book(ebook, report, remove_ncx=customization['remove_ncx']):
            changed = True
        report('')

    if opts.remove_soft_hyphens:
        rt(_('Removing soft hyphens'))
        remove_soft_hyphens(ebook, report)
        changed = True
    elif opts.add_soft_hyphens:
        rt(_('Adding soft hyphens'))
        add_soft_hyphens(ebook, report)
        changed = True

    if opts.download_external_resources:
        rt(_('Downloading external resources'))
        try:
            download_resources(ebook, report)
        except Exception:
            import traceback

            report(_('Failed to download resources with error:'))
            report(traceback.format_exc())
        report('')

    # Beautifying runs last so that it formats the output of all the other actions
    if opts.cleanup:
        rt(_('Beautifying all files'))
        pretty_all(ebook)
        changed = True
        report(_('All files beautified\n'))

    return changed


def polish(file_map: dict[str, str], opts: Opts, log: Log, report: Report) -> None:
    st = time.time()
    for inbook, outbook in file_map.items():
        report(_('## Polishing: %s') % (inbook.rpartition('.')[-1].upper()))
        ebook = get_container(inbook, log)
        polish_one(ebook, opts, report)
        ebook.commit(outbook)
        report('-' * 70)
    report(_('Polishing took: %.1f seconds') % (time.time() - st))


REPORT = '{0} REPORT {0}'.format('-' * 30)


def gui_polish(data: GuiPolishData) -> str:
    files = data.pop('files')
    if not data.pop('metadata'):
        data.pop('opf')
    if not data.pop('do_cover'):
        data.pop('cover', None)
    file_map = {x: x for x in files}
    opts = Opts(**cast('PolishActions', data))  # the pops above leave only Opts fields in data
    log = Log(level=Log.DEBUG)
    report: list[str] = []
    polish(file_map, opts, log, report.append)
    log('')
    log(REPORT)
    for msg in report:
        log(msg)
    return '\n\n'.join(report)


def tweak_polish(container: Container, actions: PolishActions, customization: dict[str, bool] | None = None) -> tuple[list[str], bool]:
    opts = Opts(**actions)
    report: list[str] = []
    changed = polish_one(container, opts, report.append, customization=customization)
    return report, changed


def option_parser() -> OptionParser:
    from calibre.utils.config import OptionParser

    USAGE = _('%prog [options] input_file [output_file]\n\n') + re.sub(r'<.*?>', '', CLI_HELP['about'])
    parser = OptionParser(usage=USAGE)
    a = parser.add_option
    o = partial(a, default=False, action='store_true')
    o('--embed-fonts', '-e', dest='embed', help=CLI_HELP['embed'])
    o('--subset-fonts', '-f', dest='subset', help=CLI_HELP['subset'])
    a(
        '--cover',
        '-c',
        help=_(
            'Path to a cover image. Changes the cover specified in the e-book. '
            'If no cover is present, or the cover is not properly identified, inserts a new cover.'
        ),
    )
    a('--opf', '-o', help=_('Path to an OPF file. The metadata in the book is updated from the OPF file.'))
    o('--jacket', '-j', help=CLI_HELP['jacket'])
    o('--remove-jacket', help=CLI_HELP['remove_jacket'])
    o('--smarten-punctuation', '-p', help=CLI_HELP['smarten_punctuation'])
    o('--remove-unused-css', '-u', help=CLI_HELP['remove_unused_css'])
    o('--compress-images', '-i', help=CLI_HELP['compress_images'])
    o('--add-soft-hyphens', '-H', help=CLI_HELP['add_soft_hyphens'])
    o('--remove-soft-hyphens', help=CLI_HELP['remove_soft_hyphens'])
    o('--upgrade-book', '-U', help=CLI_HELP['upgrade_book'])
    o('--download-external-resources', '-d', help=CLI_HELP['download_external_resources'])
    o('--cleanup', help=CLI_HELP['cleanup'])

    o('--verbose', help=_('Produce more verbose output, useful for debugging.'))

    return parser


def main(args: list[str] | None = None) -> None:
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
    for k, v in popts.items():
        popts[k] = getattr(opts, k, None)

    popts = Opts(**popts)
    report: list[str] = []
    if not tuple(filter(None, (getattr(popts, name) for name in ALL_OPTS))):
        parser.print_help()
        log.error(_('You must specify at least one action to perform'))
        raise SystemExit(1)

    polish({inbook: outbook}, popts, log, report.append)
    log('')
    log(REPORT)
    for msg in report:
        log(msg)

    log('Output written to:', outbook)


if __name__ == '__main__':
    main()
