#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import cPickle, shutil

from PyQt5.Qt import QAbstractListModel, Qt, QFont, QModelIndex, QDialog, QCoreApplication, QSize

from calibre.gui2 import gprefs
from calibre.ebooks.conversion.config import (
        GuiRecommendations, save_specifics, sort_formats_by_preference, get_input_format_for_book, get_output_formats)
from calibre.gui2.convert.single_ui import Ui_Dialog
from calibre.gui2.convert.metadata import MetadataWidget
from calibre.gui2.convert.look_and_feel import LookAndFeelWidget
from calibre.gui2.convert.heuristics import HeuristicsWidget
from calibre.gui2.convert.search_and_replace import SearchAndReplaceWidget
from calibre.gui2.convert.page_setup import PageSetupWidget
from calibre.gui2.convert.structure_detection import StructureDetectionWidget
from calibre.gui2.convert.toc import TOCWidget
from calibre.gui2.convert.debug import DebugWidget


from calibre.ebooks.conversion.plumber import create_dummy_plumber
from calibre.ebooks.conversion.config import delete_specifics
from calibre.customize.conversion import OptionRecommendation
from calibre.utils.config import prefs


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
            return None
        if role == Qt.DisplayRole:
            return (widget.config_title())
        if role == Qt.DecorationRole:
            return (widget.config_icon())
        if role == Qt.FontRole:
            f = QFont()
            f.setBold(True)
            return (f)
        return None


class Config(QDialog, Ui_Dialog):
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
        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.opt_individual_saved_settings.setVisible(False)
        self.db, self.book_id = db, book_id

        self.setup_input_output_formats(self.db, self.book_id, preferred_input_format,
                preferred_output_format)
        self.setup_pipeline()

        self.input_formats.currentIndexChanged[str].connect(self.setup_pipeline)
        self.output_formats.currentIndexChanged[str].connect(self.setup_pipeline)
        self.groups.setSpacing(5)
        self.groups.activated[(QModelIndex)].connect(self.show_pane)
        self.groups.clicked[(QModelIndex)].connect(self.show_pane)
        self.groups.entered[(QModelIndex)].connect(self.show_group_help)
        rb = self.buttonBox.button(self.buttonBox.RestoreDefaults)
        rb.setText(_('Restore &defaults'))
        rb.clicked.connect(self.restore_defaults)
        self.groups.setMouseTracking(True)
        geom = gprefs.get('convert_single_dialog_geom', None)
        if geom:
            self.restoreGeometry(geom)
        else:
            self.resize(self.sizeHint())

    def sizeHint(self):
        desktop = QCoreApplication.instance().desktop()
        geom = desktop.availableGeometry(self)
        nh, nw = max(300, geom.height()-100), max(400, geom.width()-70)
        return QSize(nw, nh)

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
        self.plumber = create_dummy_plumber(input_format, output_format)

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
            if not c:
                break
            self.stack.removeWidget(c)

        widgets = [self.mw, lf, hw, ps, sd, toc, sr]
        if input_widget is not None:
            widgets.append(input_widget)
        if output_widget is not None:
            widgets.append(output_widget)
        widgets.append(debug)
        for w in widgets:
            self.stack.addWidget(w)
            w.set_help_signal.connect(self.help.setPlainText)

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
            preferred_output_format = preferred_output_format.upper()
        output_formats = get_output_formats(preferred_output_format)
        input_format, input_formats = get_input_format_for_book(db, book_id,
                preferred_input_format)
        preferred_output_format = preferred_output_format if \
            preferred_output_format in output_formats else \
            sort_formats_by_preference(output_formats,
                    [prefs['output_format']])[0]
        self.input_formats.addItems(list(map(unicode, [x.upper() for x in
            input_formats])))
        self.output_formats.addItems(list(map(unicode, [x.upper() for x in
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
        QDialog.accept(self)

    def reject(self):
        self.break_cycles()
        QDialog.reject(self)

    def done(self, r):
        if self.isVisible():
            gprefs['convert_single_dialog_geom'] = \
                bytearray(self.saveGeometry())
        return QDialog.done(self, r)

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
