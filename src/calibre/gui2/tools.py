#!/usr/bin/env  python2
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Logic for setting up conversion jobs
'''

import cPickle, os

from PyQt5.Qt import QDialog, QProgressDialog, QTimer

from calibre.ptempfile import PersistentTemporaryFile
from calibre.gui2 import warning_dialog, question_dialog
from calibre.gui2.convert.single import Config as SingleConfig
from calibre.gui2.convert.bulk import BulkConfig
from calibre.gui2.convert.metadata import create_opf_file, create_cover_file
from calibre.customize.conversion import OptionRecommendation
from calibre.utils.config import prefs
from calibre.ebooks.conversion.config import (
        GuiRecommendations, load_defaults, load_specifics, save_specifics,
        get_input_format_for_book, NoSupportedInputFormats)
from calibre.gui2.convert import bulk_defaults_for_input_format


def convert_single_ebook(parent, db, book_ids, auto_conversion=False,  # {{{
        out_format=None, show_no_format_warning=True):
    changed = False
    jobs = []
    bad = []

    total = len(book_ids)
    if total == 0:
        return None, None, None

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
                # if not convert_existing(parent, db, [book_id], d.output_format):
                #    continue

                mi = db.get_metadata(book_id, True)
                in_file = PersistentTemporaryFile('.'+d.input_format)
                with in_file:
                    input_fmt = db.original_fmt(book_id, d.input_format).lower()
                    same_fmt = input_fmt == d.output_format.lower()
                    db.copy_format_to(book_id, input_fmt, in_file,
                            index_is_id=True)

                out_file = PersistentTemporaryFile('.' + d.output_format)
                out_file.write(d.output_format)
                out_file.close()
                temp_files = [in_file]

                try:
                    dtitle = unicode(mi.title)
                except:
                    dtitle = repr(mi.title)
                desc = _('Convert book %(num)d of %(total)d (%(title)s)') % \
                        {'num':i + 1, 'total':total, 'title':dtitle}

                recs = cPickle.loads(d.recommendations)
                if d.opf_file is not None:
                    recs.append(('read_metadata_from_opf', d.opf_file.name,
                        OptionRecommendation.HIGH))
                    temp_files.append(d.opf_file)
                if d.cover_file is not None:
                    recs.append(('cover', d.cover_file.name,
                        OptionRecommendation.HIGH))
                    temp_files.append(d.cover_file)
                args = [in_file.name, out_file.name, recs]
                temp_files.append(out_file)
                func = 'gui_convert_override'
                parts = []
                if not auto_conversion and d.manually_fine_tune_toc:
                    parts.append('manually_fine_tune_toc')
                if same_fmt:
                    parts.append('same_fmt')
                if parts:
                    func += ':%s'%(';'.join(parts))
                jobs.append((func, args, desc, d.output_format.upper(), book_id, temp_files))

                changed = True
                d.break_cycles()
        except NoSupportedInputFormats as nsif:
            bad.append((book_id, nsif.available_formats))

    if bad and show_no_format_warning:
        if len(bad) == 1 and not bad[0][1]:
            title = db.title(bad[0][0], True)
            warning_dialog(parent, _('Could not convert'), '<p>'+ _(
                'Could not convert <b>%s</b> as it has no e-book files. If you '
                'think it should have files, but calibre is not finding '
                'them, that is most likely because you moved the book\'s '
                'files around outside of calibre. You will need to find those files '
                'and re-add them to calibre.')%title, show=True)
        else:
            res = []
            for id, available_formats in bad:
                title = db.title(id, True)
                if available_formats:
                    msg = _('No supported formats (Available formats: %s)')%(
                        ', '.join(available_formats))
                else:
                    msg = _('This book has no actual e-book files')
                res.append('%s - %s'%(title, msg))

            msg = '%s' % '\n'.join(res)
            warning_dialog(parent, _('Could not convert some books'),
                ngettext(
                    'Could not convert the book because no supported source format was found',
                    'Could not convert {num} of {tot} books, because no supported source formats were found.',
                    len(res)).format(num=len(res), tot=total),
                msg).exec_()

    return jobs, changed, bad
# }}}

# Bulk convert {{{


def convert_bulk_ebook(parent, queue, db, book_ids, out_format=None, args=[]):
    total = len(book_ids)
    if total == 0:
        return None, None, None

    has_saved_settings = db.has_conversion_options(book_ids)

    d = BulkConfig(parent, db, out_format,
            has_saved_settings=has_saved_settings)
    if d.exec_() != QDialog.Accepted:
        return None

    output_format = d.output_format
    user_recs = cPickle.loads(d.recommendations)

    book_ids = convert_existing(parent, db, book_ids, output_format)
    use_saved_single_settings = d.opt_individual_saved_settings.isChecked()
    return QueueBulk(parent, book_ids, output_format, queue, db, user_recs,
            args, use_saved_single_settings=use_saved_single_settings)


class QueueBulk(QProgressDialog):

    def __init__(self, parent, book_ids, output_format, queue, db, user_recs,
            args, use_saved_single_settings=True):
        QProgressDialog.__init__(self, '',
                None, 0, len(book_ids), parent)
        self.setWindowTitle(_('Queueing books for bulk conversion'))
        self.book_ids, self.output_format, self.queue, self.db, self.args, self.user_recs = \
                book_ids, output_format, queue, db, args, user_recs
        self.parent = parent
        self.use_saved_single_settings = use_saved_single_settings
        self.i, self.bad, self.jobs, self.changed = 0, [], [], False
        QTimer.singleShot(0, self.do_book)
        self.exec_()

    def do_book(self):
        if self.i >= len(self.book_ids):
            return self.do_queue()
        book_id = self.book_ids[self.i]
        self.i += 1

        temp_files = []

        try:
            input_format = get_input_format_for_book(self.db, book_id, None)[0]
            input_fmt = self.db.original_fmt(book_id, input_format).lower()
            same_fmt = input_fmt == self.output_format.lower()
            mi, opf_file = create_opf_file(self.db, book_id)
            in_file = PersistentTemporaryFile('.'+input_format)
            with in_file:
                self.db.copy_format_to(book_id, input_fmt, in_file,
                        index_is_id=True)

            out_file = PersistentTemporaryFile('.' + self.output_format)
            out_file.write(self.output_format)
            out_file.close()
            temp_files = [in_file]

            combined_recs = GuiRecommendations()
            default_recs = bulk_defaults_for_input_format(input_format)
            for key in default_recs:
                combined_recs[key] = default_recs[key]
            if self.use_saved_single_settings:
                specific_recs = load_specifics(self.db, book_id)
                for key in specific_recs:
                    combined_recs[key] = specific_recs[key]
            for item in self.user_recs:
                combined_recs[item[0]] = item[1]
            save_specifics(self.db, book_id, combined_recs)
            lrecs = list(combined_recs.to_recommendations())
            from calibre.customize.ui import plugin_for_output_format
            op = plugin_for_output_format(self.output_format)
            if op and op.recommendations:
                prec = {x[0] for x in op.recommendations}
                for i, r in enumerate(list(lrecs)):
                    if r[0] in prec:
                        lrecs[i] = (r[0], r[1], OptionRecommendation.HIGH)

            cover_file = create_cover_file(self.db, book_id)

            if opf_file is not None:
                lrecs.append(('read_metadata_from_opf', opf_file.name,
                    OptionRecommendation.HIGH))
                temp_files.append(opf_file)
            if cover_file is not None:
                lrecs.append(('cover', cover_file.name,
                    OptionRecommendation.HIGH))
                temp_files.append(cover_file)

            for x in list(lrecs):
                if x[0] == 'debug_pipeline':
                    lrecs.remove(x)
            try:
                dtitle = unicode(mi.title)
            except:
                dtitle = repr(mi.title)
            if len(dtitle) > 50:
                dtitle = dtitle[:50].rpartition(' ')[0]+'...'
            self.setLabelText(_('Queueing ')+dtitle)
            desc = _('Convert book %(num)d of %(tot)d (%(title)s)') % dict(
                    num=self.i, tot=len(self.book_ids), title=dtitle)

            args = [in_file.name, out_file.name, lrecs]
            temp_files.append(out_file)
            func = 'gui_convert_override'
            if same_fmt:
                func += ':same_fmt'
            self.jobs.append((func, args, desc, self.output_format.upper(), book_id, temp_files))

            self.changed = True
            self.setValue(self.i)
        except NoSupportedInputFormats:
            self.bad.append(book_id)
        QTimer.singleShot(0, self.do_book)

    def do_queue(self):
        self.hide()
        if self.bad != []:
            res = []
            for id in self.bad:
                title = self.db.title(id, True)
                res.append('%s'%title)

            msg = '%s' % '\n'.join(res)
            warning_dialog(self.parent, _('Could not convert some books'),
                _('Could not convert %(num)d of %(tot)d books, because no suitable '
                'source format was found.') % dict(num=len(res), tot=len(self.book_ids)),
                msg).exec_()
        self.parent = None
        self.jobs.reverse()
        self.queue(self.jobs, self.changed, self.bad, *self.args)

# }}}


def fetch_scheduled_recipe(arg):  # {{{
    fmt = prefs['output_format'].lower()
    # Never use AZW3 for periodicals...
    if fmt == 'azw3':
        fmt = 'mobi'
    pt = PersistentTemporaryFile(suffix='_recipe_out.%s'%fmt.lower())
    pt.close()
    recs = []
    ps = load_defaults('page_setup')
    if 'output_profile' in ps:
        recs.append(('output_profile', ps['output_profile'],
            OptionRecommendation.HIGH))
    for edge in ('left', 'top', 'bottom', 'right'):
        edge = 'margin_' + edge
        if edge in ps:
            recs.append((edge, ps[edge], OptionRecommendation.HIGH))

    lf = load_defaults('look_and_feel')
    if lf.get('base_font_size', 0.0) != 0.0:
        recs.append(('base_font_size', lf['base_font_size'],
            OptionRecommendation.HIGH))
        recs.append(('keep_ligatures', lf.get('keep_ligatures', False),
            OptionRecommendation.HIGH))

    lr = load_defaults('lrf_output')
    if lr.get('header', False):
        recs.append(('header', True, OptionRecommendation.HIGH))
        recs.append(('header_format', '%t', OptionRecommendation.HIGH))

    epub = load_defaults('epub_output')
    if epub.get('epub_flatten', False):
        recs.append(('epub_flatten', True, OptionRecommendation.HIGH))

    if fmt == 'pdf':
        pdf = load_defaults('pdf_output')
        from calibre.customize.ui import plugin_for_output_format
        p = plugin_for_output_format('pdf')
        for opt in p.options:
            recs.append((opt.option.name, pdf.get(opt.option.name, opt.recommended_value), OptionRecommendation.HIGH))

    args = [arg['recipe'], pt.name, recs]
    if arg['username'] is not None:
        recs.append(('username', arg['username'], OptionRecommendation.HIGH))
    if arg['password'] is not None:
        recs.append(('password', arg['password'], OptionRecommendation.HIGH))

    return 'gui_convert', args, _('Fetch news from %s')%arg['title'], fmt.upper(), [pt]

# }}}


def generate_catalog(parent, dbspec, ids, device_manager, db):  # {{{
    from calibre.gui2.dialogs.catalog import Catalog

    # Build the Catalog dialog in gui2.dialogs.catalog
    d = Catalog(parent, dbspec, ids, db)

    if d.exec_() != d.Accepted:
        return None

    # Create the output file
    out = PersistentTemporaryFile(suffix='_catalog_out.'+d.catalog_format.lower())

    # Profile the connected device
    # Parallel initialization in calibre.db.cli.cmd_catalog
    connected_device = {
                         'is_device_connected': device_manager.is_device_present,
                         'kind': device_manager.connected_device_kind,
                         'name': None,
                         'save_template': None,
                         'serial': None,
                         'storage': None
                       }

    if device_manager.is_device_present:
        device = device_manager.device
        connected_device['name'] = device.get_gui_name()
        try:
            storage = []
            if device._main_prefix:
                storage.append(os.path.join(device._main_prefix, device.EBOOK_DIR_MAIN))
            if device._card_a_prefix:
                storage.append(os.path.join(device._card_a_prefix, device.EBOOK_DIR_CARD_A))
            if device._card_b_prefix:
                storage.append(os.path.join(device._card_b_prefix, device.EBOOK_DIR_CARD_B))
            connected_device['storage'] = storage
            connected_device['serial'] = device.detected_device.serial if \
                                          hasattr(device.detected_device,'serial') else None
            connected_device['save_template'] = device.save_template()
        except:
            pass

    # These args are passed inline to gui2.convert.gui_conversion:gui_catalog
    args = [
        d.catalog_format,
        d.catalog_title,
        dbspec,
        ids,
        out.name,
        d.catalog_sync,
        d.fmt_options,
        connected_device
        ]
    out.close()

    # This returns to gui2.actions.catalog:generate_catalog()
    # Which then calls gui2.convert.gui_conversion:gui_catalog() with the args inline
    return 'gui_catalog', args, _('Generate catalog'), out.name, d.catalog_sync, \
            d.catalog_title
# }}}


def convert_existing(parent, db, book_ids, output_format):  # {{{
    already_converted_ids = []
    already_converted_titles = []
    for book_id in book_ids:
        if db.has_format(book_id, output_format, index_is_id=True):
            already_converted_ids.append(book_id)
            already_converted_titles.append(db.get_metadata(book_id, True).title)

    if already_converted_ids:
        if not question_dialog(parent, _('Convert existing'),
                _('The following books have already been converted to the %s format. '
                   'Do you wish to reconvert them?') % output_format.upper(),
                det_msg='\n'.join(already_converted_titles), skip_dialog_name='confirm_bulk_reconvert'):
            book_ids = [x for x in book_ids if x not in already_converted_ids]

    return book_ids
# }}}
