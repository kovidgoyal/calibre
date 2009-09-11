#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Logic for setting up conversion jobs
'''

import cPickle

from PyQt4.Qt import QDialog

from calibre.ptempfile import PersistentTemporaryFile
from calibre.gui2 import warning_dialog, question_dialog
from calibre.gui2.convert.single import NoSupportedInputFormats
from calibre.gui2.convert.single import Config as SingleConfig
from calibre.gui2.convert.bulk import BulkConfig
from calibre.customize.conversion import OptionRecommendation
from calibre.utils.config import prefs
from calibre.ebooks.conversion.config import GuiRecommendations, \
    load_defaults, load_specifics, save_specifics

def convert_single_ebook(parent, db, book_ids, auto_conversion=False, out_format=None):
    changed = False
    jobs = []
    bad = []

    total = len(book_ids)
    if total == 0:
        return None, None, None
    parent.status_bar.showMessage(_('Starting conversion of %d books') % total, 2000)

    for i, book_id in enumerate(book_ids):
        temp_files = []

        try:
            d = SingleConfig(parent, db, book_id, None, out_format)

            if auto_conversion:
                d.accept()
                result = QDialog.Accepted
            else:
                result = d.exec_()

            if result == QDialog.Accepted:
                #if not convert_existing(parent, db, [book_id], d.output_format):
                #    continue

                mi = db.get_metadata(book_id, True)
                in_file = db.format_abspath(book_id, d.input_format, True)

                out_file = PersistentTemporaryFile('.' + d.output_format)
                out_file.write(d.output_format)
                out_file.close()
                temp_files = []

                try:
                    dtitle = unicode(mi.title)
                except:
                    dtitle = repr(mi.title)
                desc = _('Convert book %d of %d (%s)') % (i + 1, total, dtitle)

                recs = cPickle.loads(d.recommendations)
                if d.opf_file is not None:
                    recs.append(('read_metadata_from_opf', d.opf_file.name,
                        OptionRecommendation.HIGH))
                    temp_files.append(d.opf_file)
                if d.cover_file is not None:
                    recs.append(('cover', d.cover_file.name,
                        OptionRecommendation.HIGH))
                    temp_files.append(d.cover_file)
                args = [in_file, out_file.name, recs]
                temp_files.append(out_file)
                jobs.append(('gui_convert', args, desc, d.output_format.upper(), book_id, temp_files))

                changed = True
        except NoSupportedInputFormats:
            bad.append(book_id)

    if bad != []:
        res = []
        for id in bad:
            title = db.title(id, True)
            res.append('%s'%title)

        msg = '%s' % '\n'.join(res)
        warning_dialog(parent, _('Could not convert some books'),
            _('Could not convert %d of %d books, because no suitable source'
               ' format was found.') % (len(res), total),
            msg).exec_()

    return jobs, changed, bad

def convert_bulk_ebook(parent, db, book_ids, out_format=None):
    changed = False
    jobs = []
    bad = []

    total = len(book_ids)
    if total == 0:
        return None, None, None
    parent.status_bar.showMessage(_('Starting conversion of %d books') % total, 2000)

    d = BulkConfig(parent, db, out_format)
    if d.exec_() != QDialog.Accepted:
        return jobs, changed, bad

    output_format = d.output_format
    user_recs = cPickle.loads(d.recommendations)

    book_ids = convert_existing(parent, db, book_ids, output_format)
    for i, book_id in enumerate(book_ids):
        temp_files = []

        try:
            d = SingleConfig(parent, db, book_id, None, output_format)
            d.accept()

            mi = db.get_metadata(book_id, True)
            in_file = db.format_abspath(book_id, d.input_format, True)

            out_file = PersistentTemporaryFile('.' + output_format)
            out_file.write(output_format)
            out_file.close()
            temp_files = []

            combined_recs = GuiRecommendations()
            default_recs = load_defaults('%s_input' % d.input_format)
            specific_recs = load_specifics(db, book_id)
            for key in default_recs:
                combined_recs[key] = default_recs[key]
            for key in specific_recs:
                combined_recs[key] = specific_recs[key]
            for item in user_recs:
                combined_recs[item[0]] = item[1]
            save_specifics(db, book_id, combined_recs)
            lrecs = list(combined_recs.to_recommendations())

            if d.opf_file is not None:
                lrecs.append(('read_metadata_from_opf', d.opf_file.name,
                    OptionRecommendation.HIGH))
                temp_files.append(d.opf_file)
            if d.cover_file is not None:
                lrecs.append(('cover', d.cover_file.name,
                    OptionRecommendation.HIGH))
                temp_files.append(d.cover_file)

            for x in list(lrecs):
                if x[0] == 'debug_pipeline':
                    lrecs.remove(x)

            desc = _('Convert book %d of %d (%s)') % (i + 1, total, repr(mi.title))

            args = [in_file, out_file.name, lrecs]
            temp_files.append(out_file)
            jobs.append(('gui_convert', args, desc, d.output_format.upper(), book_id, temp_files))

            changed = True
        except NoSupportedInputFormats:
            bad.append(book_id)

    if bad != []:
        res = []
        for id in bad:
            title = db.title(id, True)
            res.append('%s'%title)

        msg = '%s' % '\n'.join(res)
        warning_dialog(parent, _('Could not convert some books'),
            _('Could not convert %d of %d books, because no suitable '
            'source format was found.') % (len(res), total),
            msg).exec_()

    return jobs, changed, bad

def fetch_scheduled_recipe(recipe, script):
    from calibre.gui2.dialogs.scheduler import config
    from calibre.ebooks.conversion.config import load_defaults
    fmt = prefs['output_format'].lower()
    pt = PersistentTemporaryFile(suffix='_recipe_out.%s'%fmt.lower())
    pt.close()
    recs = []
    ps = load_defaults('page_setup')
    if 'output_profile' in ps:
        recs.append(('output_profile', ps['output_profile'],
            OptionRecommendation.HIGH))
    lf = load_defaults('look_and_feel')
    if lf.get('base_font_size', 0.0) != 0.0:
        recs.append(('base_font_size', lf['base_font_size'],
            OptionRecommendation.HIGH))

    lr = load_defaults('lrf_output')
    if lr.get('header', False):
        recs.append(('header', True, OptionRecommendation.HIGH))
        recs.append(('header_format', '%t', OptionRecommendation.HIGH))

    args = [script, pt.name, recs]
    if recipe.needs_subscription:
        x = config.get('recipe_account_info_%s'%recipe.id, False)
        if not x:
            raise ValueError(_('You must set a username and password for %s')%recipe.title)
        recs.append(('username', x[0], OptionRecommendation.HIGH))
        recs.append(('password', x[1], OptionRecommendation.HIGH))


    return 'gui_convert', args, _('Fetch news from ')+recipe.title, fmt.upper(), [pt]

def convert_existing(parent, db, book_ids, output_format):
    already_converted_ids = []
    already_converted_titles = []
    for book_id in book_ids:
        if db.has_format(book_id, output_format, index_is_id=True):
            already_converted_ids.append(book_id)
            already_converted_titles.append(db.get_metadata(book_id, True).title)

    if already_converted_ids:
        if not question_dialog(parent, _('Convert existing'),
                _('The following books have already been converted to %s format. '
                   'Do you wish to reconvert them?') % output_format,
                '\n'.join(already_converted_titles)):
            book_ids = [x for x in book_ids if x not in already_converted_ids]

    return book_ids
