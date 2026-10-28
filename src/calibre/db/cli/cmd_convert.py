#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import os

from calibre import prints
from calibre.utils.localization import _

readonly = False
version = 0  # change this if you change signature of implementation()
no_remote = True


def implementation(db, notify_changes, *args):
    raise NotImplementedError()


def option_parser(get_parser, args):
    parser = get_parser(
        _(
            '''\
%prog convert [options] book_id output_format [-- ebook-convert options]

Convert the book identified by book_id to output_format, for example EPUB,
and add the result to the formats of the book, as the Convert books action in
the calibre interface does. The metadata and cover of the book in the library
are used for the converted book.

The input format is chosen as in the calibre interface, unless the
--input-format option is used. The conversion settings saved for the book by
previous conversions in the calibre interface are used, and options from
ebook-convert can be specified after --, for example:

%prog convert 12 EPUB -- --smarten-punctuation --change-justification justify

Options for calibredb, such as --with-library, must come before the --.
To see the ebook-convert options for the input and output formats, use:
ebook-convert dummy.input_format dummy.output_format --help
'''
        )
    )
    parser.add_option(
        '--input-format',
        default=None,
        help=_('The format of the book to convert, for example MOBI. Default is to choose it as the calibre interface does.'),
    )
    parser.add_option(
        '--ignore-saved-settings',
        default=False,
        action='store_true',
        help=_('Do not use the conversion settings saved for the book by previous conversions in the calibre interface'),
    )
    parser.add_option(
        '--dont-replace',
        default=False,
        action='store_true',
        help=_('Do not convert the book if it already has the output format'),
    )
    return parser


def user_recommendations(input_path, output_path, args, log):
    # Only the ebook-convert options that are specified are used, so that they
    # do not override the saved settings with their defaults
    from calibre.customize.conversion import OptionRecommendation
    from calibre.ebooks.conversion.cli import create_option_parser, normalize_options

    full_args = ['ebook-convert', input_path, output_path] + list(args)
    parser = create_option_parser(full_args, log)[0]
    opts, leftover_args = parser.parse_args(full_args)
    if len(leftover_args) > 3:
        raise SystemExit(_('Error: Extra arguments not understood: {}').format(' '.join(leftover_args[3:])))
    defaults = parser.get_default_values()
    if not normalize_options(opts, log):
        raise SystemExit(1)
    return [
        (o.dest, getattr(opts, o.dest), OptionRecommendation.HIGH)
        for o in parser.options_iter()
        if o.dest and getattr(opts, o.dest) != getattr(defaults, o.dest, None)
    ]


def run_conversion(input_path, output_path, recommendations):
    "Run in a worker process to convert the book"
    from calibre.ebooks.conversion.plumber import Plumber
    from calibre.utils.logging import Log

    plumber = Plumber(input_path, output_path, Log(), override_input_metadata=True)
    plumber.merge_ui_recommendations(recommendations)
    plumber.run()


def print_worker_log(path, log):
    if path and os.path.exists(path):
        with open(path, 'rb') as f:
            raw = f.read().decode('utf-8', 'replace').strip()
        os.remove(path)
        if raw:
            log(raw)


def convert(ldb, book_id, output_format, input_format=None, use_saved_settings=True, convert_args=(), log=None):
    "Convert the book to output_format, as is done by the Convert books action in the GUI, adding the result to the book"
    from tempfile import TemporaryDirectory

    from calibre.customize.conversion import OptionRecommendation
    from calibre.customize.ui import plugin_for_output_format, run_plugins_on_postconvert
    from calibre.ebooks.conversion.config import GuiRecommendations, get_input_format_for_book, load_specifics
    from calibre.ebooks.metadata.opf2 import metadata_to_opf
    from calibre.utils.config import tweaks
    from calibre.utils.ipc.simple_worker import WorkerError, fork_job
    from calibre.utils.logging import Log

    db = ldb.new_api
    log = log or Log()
    pref = input_format.lower() if input_format else None
    input_format, input_formats = get_input_format_for_book(ldb, book_id, pref)
    if pref and pref not in input_formats:
        raise ValueError(_('The {} format cannot be converted').format(pref.upper()))
    original_format = ldb.original_fmt(book_id, input_format)
    same_format = original_format.lower() == output_format.lower()
    with TemporaryDirectory('_calibredb_convert') as tdir:
        input_path = os.path.join(tdir, 'input.' + input_format.lower())
        output_path = os.path.join(tdir, 'output.' + output_format.lower())
        db.copy_format_to(book_id, original_format, input_path)

        recs = GuiRecommendations()
        if use_saved_settings:
            recs.update(load_specifics(ldb, book_id))
        recs.pop('debug_pipeline', None)
        lrecs = list(recs.to_recommendations())
        op = plugin_for_output_format(output_format)
        if op is not None and op.recommendations:
            prec = {x[0] for x in op.recommendations}
            lrecs = [(r[0], r[1], OptionRecommendation.HIGH) if r[0] in prec else r for r in lrecs]
        lrecs.extend(user_recommendations(input_path, output_path, convert_args, log))

        mi = db.get_metadata(book_id)
        cover = db.cover(book_id)
        mi.cover = None
        mi.application_id = mi.uuid
        opf_path = os.path.join(tdir, 'metadata.opf')
        with open(opf_path, 'wb') as f:
            f.write(metadata_to_opf(mi, mark_fallback_language=True))
        lrecs.append(('read_metadata_from_opf', opf_path, OptionRecommendation.HIGH))
        if cover:
            cover_path = os.path.join(tdir, 'cover.jpg')
            with open(cover_path, 'wb') as f:
                f.write(cover)
            lrecs.append(('cover', cover_path, OptionRecommendation.HIGH))

        # Conversion is run in a worker process, as in the GUI, since it can
        # need a QApplication
        try:
            res = fork_job('calibre.db.cli.cmd_convert', 'run_conversion', (input_path, output_path, lrecs), heartbeat=lambda: True)
        except WorkerError as e:
            print_worker_log(e.log_path, log)
            raise Exception(_('Conversion failed: {}').format(e.orig_tb or e))
        print_worker_log(res.get('stdout_stderr'), log)
        if os.path.getsize(output_path) < 1:
            raise Exception(_('Empty output file, probably the conversion process crashed'))
        if same_format and tweaks['save_original_format']:
            ldb.save_original_format(book_id, output_format, notify=False)
        with open(output_path, 'rb') as f:
            ldb.add_format(book_id, output_format, f, index_is_id=True)
        run_plugins_on_postconvert(ldb, book_id, output_format)
    return input_format


def main(opts, args, dbctx):
    from calibre.customize.ui import available_output_formats
    from calibre.ebooks.conversion.config import NoSupportedInputFormats

    if len(args) < 2:
        raise SystemExit(_('Error: You must specify a book id and an output format'))
    try:
        book_id = int(args[0])
    except ValueError:
        raise SystemExit(_('Error: The book id must be a number'))
    output_format = args[1].upper()
    if output_format.lower() not in {x.lower() for x in available_output_formats()} or output_format == 'OEB':
        raise SystemExit(_('Error: Cannot convert to the {} format').format(output_format))
    db = dbctx.db
    if not db.new_api.has_id(book_id):
        raise SystemExit(_('Error: No book with id: {}').format(book_id))
    formats = {x.upper() for x in db.new_api.formats(book_id)}
    if opts.input_format and opts.input_format.upper() not in formats:
        raise SystemExit(_('Error: Book {0} does not have the {1} format').format(book_id, opts.input_format.upper()))
    if opts.dont_replace and output_format in formats:
        raise SystemExit(_('Error: Book {0} already has the {1} format, not replacing').format(book_id, output_format))
    try:
        input_format = convert(db, book_id, output_format, opts.input_format, not opts.ignore_saved_settings, args[2:])
    except NoSupportedInputFormats:
        raise SystemExit(_('Error: Book {} has no formats that can be converted').format(book_id))
    except ValueError as e:
        raise SystemExit(_('Error: {}').format(e))
    prints(_('Converted book {0} from {1} to {2}').format(book_id, input_format.upper(), output_format))
    return 0
