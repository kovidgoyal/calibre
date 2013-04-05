#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import cPickle, shutil

from PyQt4.Qt import QString, SIGNAL, QAbstractListModel, Qt, QVariant, QFont

from calibre.gui2 import ResizableDialog, NONE, gprefs
from calibre.ebooks.conversion.config import (GuiRecommendations, save_specifics,
        load_specifics)
from calibre.gui2.convert.single_ui import Ui_Dialog
from calibre.gui2.convert.metadata import MetadataWidget
from calibre.gui2.convert.look_and_feel import LookAndFeelWidget
from calibre.gui2.convert.heuristics import HeuristicsWidget
from calibre.gui2.convert.search_and_replace import SearchAndReplaceWidget
from calibre.gui2.convert.page_setup import PageSetupWidget
from calibre.gui2.convert.structure_detection import StructureDetectionWidget
from calibre.gui2.convert.toc import TOCWidget
from calibre.gui2.convert.debug import DebugWidget


from calibre.ebooks.conversion.plumber import (Plumber,
        supported_input_formats, ARCHIVE_FMTS)
from calibre.ebooks.conversion.config import delete_specifics
from calibre.customize.ui import available_output_formats
from calibre.customize.conversion import OptionRecommendation
from calibre.utils.config import prefs
from calibre.utils.logging import Log

class NoSupportedInputFormats(Exception):

    def __init__(self, available_formats):
        Exception.__init__(self)
        self.available_formats = available_formats

def sort_formats_by_preference(formats, prefs):
    uprefs = [x.upper() for x in prefs]
    def key(x):
        try:
            return uprefs.index(x.upper())
        except ValueError:
            pass
        return len(prefs)
    return sorted(formats, key=key)

class GroupModel(QAbstractListModel):

    def __init__(self, widgets):
        self.widgets = widgets
        QAbstractListModel.__init__(self)

    def rowCount(self, *args):
        return len(self.widgets)

    def data(self, index, role):
        try:
            widget = self.widgets[index.row()]
        except:
            return NONE
        if role == Qt.DisplayRole:
            return QVariant(widget.config_title())
        if role == Qt.DecorationRole:
            return QVariant(widget.config_icon())
        if role == Qt.FontRole:
            f = QFont()
            f.setBold(True)
            return QVariant(f)
        return NONE

def get_preferred_input_format_for_book(db, book_id):
    recs = load_specifics(db, book_id)
    if recs:
        return recs.get('gui_preferred_input_format',  None)

def get_available_formats_for_book(db, book_id):
    available_formats = db.formats(book_id, index_is_id=True)
    if not available_formats:
        available_formats = ''
    return set([x.lower() for x in
        available_formats.split(',')])

def get_supported_input_formats_for_book(db, book_id):
    available_formats = get_available_formats_for_book(db, book_id)
    input_formats = set([x.lower() for x in supported_input_formats()])
    input_formats = sorted(available_formats.intersection(input_formats))
    if not input_formats:
        raise NoSupportedInputFormats(tuple(x for x in available_formats if x))
    return input_formats


def get_input_format_for_book(db, book_id, pref):
    '''
    Return (preferred input format, list of available formats) for the book
    identified by book_id. Raises an error if the book has no input formats.

    :param pref: If None, the format used as input for the last conversion, if
    any, on this book is used. If not None, should be a lowercase format like
    'epub' or 'mobi'. If you do not want the last converted format to be used,
    set pref=False.
    '''
    if pref is None:
        pref = get_preferred_input_format_for_book(db, book_id)
    if hasattr(pref, 'lower'):
        pref = pref.lower()
    input_formats = get_supported_input_formats_for_book(db, book_id)
    input_format = pref if pref in input_formats else \
        sort_formats_by_preference(input_formats, prefs['input_format_order'])[0]
    return input_format, input_formats


class Config(ResizableDialog, Ui_Dialog):
    '''
    Configuration dialog for single book conversion. If accepted, has the
    following important attributes

    output_format - Output format (without a leading .)
    input_format  - Input format (without a leading .)
    opf_path - Path to OPF file with user specified metadata
    cover_path - Path to user specified cover (can be None)
    recommendations - A pickled list of 3 tuples in the same format as the
    recommendations member of the Input/Output plugins.
    '''

    def __init__(self, parent, db, book_id,
            preferred_input_format=None, preferred_output_format=None):
        ResizableDialog.__init__(self, parent)
        self.opt_individual_saved_settings.setVisible(False)
        self.db, self.book_id = db, book_id

        self.setup_input_output_formats(self.db, self.book_id, preferred_input_format,
                preferred_output_format)
        self.setup_pipeline()

        self.connect(self.input_formats, SIGNAL('currentIndexChanged(QString)'),
                self.setup_pipeline)
        self.connect(self.output_formats, SIGNAL('currentIndexChanged(QString)'),
                self.setup_pipeline)
        self.connect(self.groups, SIGNAL('activated(QModelIndex)'),
                self.show_pane)
        self.connect(self.groups, SIGNAL('clicked(QModelIndex)'),
                self.show_pane)
        self.connect(self.groups, SIGNAL('entered(QModelIndex)'),
                self.show_group_help)
        rb = self.buttonBox.button(self.buttonBox.RestoreDefaults)
        self.connect(rb, SIGNAL('clicked()'), self.restore_defaults)
        self.groups.setMouseTracking(True)
        geom = gprefs.get('convert_single_dialog_geom', None)
        if geom:
            self.restoreGeometry(geom)

    def restore_defaults(self):
        delete_specifics(self.db, self.book_id)
        self.setup_pipeline()

    @property
    def input_format(self):
        return unicode(self.input_formats.currentText()).lower()

    @property
    def output_format(self):
        return unicode(self.output_formats.currentText()).lower()

    @property
    def manually_fine_tune_toc(self):
        for i in xrange(self.stack.count()):
            w = self.stack.widget(i)
            if hasattr(w, 'manually_fine_tune_toc'):
                return w.manually_fine_tune_toc.isChecked()

    def setup_pipeline(self, *args):
        oidx = self.groups.currentIndex().row()
        input_format = self.input_format
        output_format = self.output_format
        output_path = 'dummy.'+output_format
        log = Log()
        log.outputs = []
        input_file = 'dummy.'+input_format
        if input_format in ARCHIVE_FMTS:
            input_file = 'dummy.html'
        self.plumber = Plumber(input_file, output_path, log)

        def widget_factory(cls):
            return cls(self.stack, self.plumber.get_option_by_name,
                self.plumber.get_option_help, self.db, self.book_id)


        self.mw = widget_factory(MetadataWidget)
        self.setWindowTitle(_('Convert')+ ' ' + unicode(self.mw.title.text()))
        lf = widget_factory(LookAndFeelWidget)
        hw = widget_factory(HeuristicsWidget)
        sr = widget_factory(SearchAndReplaceWidget)
        ps = widget_factory(PageSetupWidget)
        sd = widget_factory(StructureDetectionWidget)
        toc = widget_factory(TOCWidget)
        from calibre.gui2.actions.toc_edit import SUPPORTED
        toc.manually_fine_tune_toc.setVisible(output_format.upper() in SUPPORTED)
        debug = widget_factory(DebugWidget)

        output_widget = self.plumber.output_plugin.gui_configuration_widget(
                self.stack, self.plumber.get_option_by_name,
                self.plumber.get_option_help, self.db, self.book_id)
        input_widget = self.plumber.input_plugin.gui_configuration_widget(
                self.stack, self.plumber.get_option_by_name,
                self.plumber.get_option_help, self.db, self.book_id)
        while True:
            c = self.stack.currentWidget()
            if not c: break
            self.stack.removeWidget(c)

        widgets = [self.mw, lf, hw, ps, sd, toc, sr]
        if input_widget is not None:
            widgets.append(input_widget)
        if output_widget is not None:
            widgets.append(output_widget)
        widgets.append(debug)
        for w in widgets:
            self.stack.addWidget(w)
            self.connect(w, SIGNAL('set_help(PyQt_PyObject)'),
                    self.help.setPlainText)

        self._groups_model = GroupModel(widgets)
        self.groups.setModel(self._groups_model)

        idx = oidx if -1 < oidx < self._groups_model.rowCount() else 0
        self.groups.setCurrentIndex(self._groups_model.index(idx))
        self.stack.setCurrentIndex(idx)
        try:
            shutil.rmtree(self.plumber.archive_input_tdir, ignore_errors=True)
        except:
            pass


    def setup_input_output_formats(self, db, book_id, preferred_input_format,
            preferred_output_format):
        if preferred_output_format:
            preferred_output_format = preferred_output_format.lower()
        output_formats = sorted(available_output_formats(),
                key=lambda x:{'EPUB':'!A', 'MOBI':'!B'}.get(x.upper(), x))
        output_formats.remove('oeb')
        input_format, input_formats = get_input_format_for_book(db, book_id,
                preferred_input_format)
        preferred_output_format = preferred_output_format if \
            preferred_output_format in output_formats else \
            sort_formats_by_preference(output_formats,
                    prefs['output_format'])[0]
        self.input_formats.addItems(list(map(QString, [x.upper() for x in
            input_formats])))
        self.output_formats.addItems(list(map(QString, [x.upper() for x in
            output_formats])))
        self.input_formats.setCurrentIndex(input_formats.index(input_format))
        self.output_formats.setCurrentIndex(output_formats.index(preferred_output_format))

    def show_pane(self, index):
        self.stack.setCurrentIndex(index.row())

    def accept(self):
        recs = GuiRecommendations()
        for w in self._groups_model.widgets:
            if not w.pre_commit_check():
                return
            x = w.commit(save_defaults=False)
            recs.update(x)
        self.opf_file, self.cover_file = self.mw.opf_file, self.mw.cover_file
        self._recommendations = recs
        if self.db is not None:
            recs['gui_preferred_input_format'] = self.input_format
            save_specifics(self.db, self.book_id, recs)
        self.break_cycles()
        ResizableDialog.accept(self)

    def reject(self):
        self.break_cycles()
        ResizableDialog.reject(self)

    def done(self, r):
        if self.isVisible():
            gprefs['convert_single_dialog_geom'] = \
                bytearray(self.saveGeometry())
        return ResizableDialog.done(self, r)

    def break_cycles(self):
        for i in range(self.stack.count()):
            w = self.stack.widget(i)
            w.break_cycles()

    @property
    def recommendations(self):
        recs = [(k, v, OptionRecommendation.HIGH) for k, v in
                self._recommendations.items()]
        return cPickle.dumps(recs, -1)

    def show_group_help(self, index):
        widget = self._groups_model.widgets[index.row()]
        self.help.setPlainText(widget.HELP)



