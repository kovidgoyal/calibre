# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import shutil

from PyQt5.Qt import QModelIndex, QDialog

from calibre.gui2.convert.single import (Config, sort_formats_by_preference,
    GroupModel, gprefs, get_output_formats)
from calibre.gui2.convert.look_and_feel import LookAndFeelWidget
from calibre.gui2.convert.heuristics import HeuristicsWidget
from calibre.gui2.convert.search_and_replace import SearchAndReplaceWidget
from calibre.gui2.convert.page_setup import PageSetupWidget
from calibre.gui2.convert.structure_detection import StructureDetectionWidget
from calibre.gui2.convert.toc import TOCWidget
from calibre.gui2.convert import GuiRecommendations
from calibre.ebooks.conversion.plumber import Plumber
from calibre.utils.config import prefs
from calibre.utils.logging import Log


class BulkConfig(Config):

    def __init__(self, parent, db, preferred_output_format=None,
            has_saved_settings=True):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.setup_output_formats(db, preferred_output_format)
        self.db = db

        self.setup_pipeline()

        self.input_label.hide()
        self.input_formats.hide()
        self.opt_individual_saved_settings.setVisible(True)
        self.opt_individual_saved_settings.setChecked(True)
        self.opt_individual_saved_settings.setToolTip(_('For '
            'settings that cannot be specified in this dialog, use the '
            'values saved in a previous conversion (if they exist) instead '
            'of using the defaults specified in the Preferences'))

        self.output_formats.currentIndexChanged[str].connect(self.setup_pipeline)
        self.groups.activated[(QModelIndex)].connect(self.show_pane)
        self.groups.clicked[(QModelIndex)].connect(self.show_pane)
        self.groups.entered[(QModelIndex)].connect(self.show_group_help)
        rb = self.buttonBox.button(self.buttonBox.RestoreDefaults)
        rb.setVisible(False)
        self.groups.setMouseTracking(True)
        if not has_saved_settings:
            o = self.opt_individual_saved_settings
            o.setEnabled(False)
            o.setToolTip(_('None of the selected books have saved conversion '
                'settings.'))
            o.setChecked(False)

        geom = gprefs.get('convert_bulk_dialog_geom', None)
        if geom:
            self.restoreGeometry(geom)
        else:
            self.resize(self.sizeHint())

    def setup_pipeline(self, *args):
        oidx = self.groups.currentIndex().row()
        output_format = self.output_format

        input_path = 'dummy.epub'
        output_path = 'dummy.'+output_format
        log = Log()
        log.outputs = []
        self.plumber = Plumber(input_path, output_path, log, merge_plugin_recs=False)
        self.plumber.merge_plugin_recs(self.plumber.output_plugin)

        def widget_factory(cls):
            return cls(self.stack, self.plumber.get_option_by_name,
                self.plumber.get_option_help, self.db)

        self.setWindowTitle(_('Bulk convert'))
        lf = widget_factory(LookAndFeelWidget)
        hw = widget_factory(HeuristicsWidget)
        sr = widget_factory(SearchAndReplaceWidget)
        ps = widget_factory(PageSetupWidget)
        sd = widget_factory(StructureDetectionWidget)
        toc = widget_factory(TOCWidget)
        toc.manually_fine_tune_toc.hide()

        output_widget = self.plumber.output_plugin.gui_configuration_widget(
                self.stack, self.plumber.get_option_by_name,
                self.plumber.get_option_help, self.db)

        while True:
            c = self.stack.currentWidget()
            if not c:
                break
            self.stack.removeWidget(c)

        widgets = [lf, hw, ps, sd, toc, sr]
        if output_widget is not None:
            widgets.append(output_widget)
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

    def setup_output_formats(self, db, preferred_output_format):
        if preferred_output_format:
            preferred_output_format = preferred_output_format.upper()
        output_formats = get_output_formats(preferred_output_format)
        preferred_output_format = preferred_output_format if \
            preferred_output_format and preferred_output_format \
            in output_formats else sort_formats_by_preference(output_formats,
                    [prefs['output_format']])[0]
        self.output_formats.addItems(list(map(unicode, [x.upper() for x in
            output_formats])))
        self.output_formats.setCurrentIndex(output_formats.index(preferred_output_format))

    def accept(self):
        recs = GuiRecommendations()
        for w in self._groups_model.widgets:
            if not w.pre_commit_check():
                return
            x = w.commit(save_defaults=False)
            recs.update(x)
        self._recommendations = recs
        QDialog.accept(self)

    def done(self, r):
        if self.isVisible():
            gprefs['convert_bulk_dialog_geom'] = \
                bytearray(self.saveGeometry())
        return QDialog.done(self, r)
