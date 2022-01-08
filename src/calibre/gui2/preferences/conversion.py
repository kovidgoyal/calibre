#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import importlib

from qt.core import (
    QIcon, Qt, QStringListModel, QListView, QSizePolicy, QHBoxLayout, QSize,
    QStackedWidget, pyqtSignal, QScrollArea)

from calibre.gui2.preferences import ConfigWidgetBase, test_widget, AbortCommit
from calibre.ebooks.conversion.plumber import Plumber
from calibre.utils.logging import Log
from calibre.gui2.convert.look_and_feel import LookAndFeelWidget
from calibre.gui2.convert.heuristics import HeuristicsWidget
from calibre.gui2.convert.search_and_replace import SearchAndReplaceWidget
from calibre.gui2.convert.page_setup import PageSetupWidget
from calibre.gui2.convert.structure_detection import StructureDetectionWidget
from calibre.gui2.convert.toc import TOCWidget
from calibre.customize.ui import input_format_plugins, output_format_plugins
from calibre.gui2.convert import config_widget_for_input_plugin


class Model(QStringListModel):

    def __init__(self, widgets):
        QStringListModel.__init__(self)
        self.widgets = widgets
        self.setStringList([w.TITLE for w in widgets])

    def data(self, index, role):
        if role == Qt.ItemDataRole.DecorationRole:
            w = self.widgets[index.row()]
            if w.ICON:
                return QIcon.ic(w.ICON)
        return QStringListModel.data(self, index, role)


class ListView(QListView):

    current_changed = pyqtSignal(object, object)

    def __init__(self, parent=None):
        QListView.__init__(self, parent)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Expanding)
        f = self.font()
        f.setBold(True)
        self.setFont(f)
        self.setIconSize(QSize(48, 48))
        self.setFlow(QListView.Flow.TopToBottom)
        self.setSpacing(10)

    def currentChanged(self, cur, prev):
        QListView.currentChanged(self, cur, prev)
        self.current_changed.emit(cur, prev)


class Base(ConfigWidgetBase):

    restore_defaults_desc = _('Restore settings to default values. '
            'Only settings for the currently selected section '
            'are restored.')

    def setupUi(self, x):
        self.resize(720, 603)
        self.l = l = QHBoxLayout(self)
        self.list = lv = ListView(self)
        l.addWidget(lv)
        self.stack = s = QStackedWidget(self)
        l.addWidget(s, stretch=10)

    def genesis(self, gui):
        log = Log()
        log.outputs = []

        self.plumber = Plumber('dummy.epub', 'dummy.epub', log, dummy=True,
                merge_plugin_recs=False)

        def widget_factory(cls):
            plugin = getattr(cls, 'conv_plugin', None)
            if plugin is None:
                hfunc = self.plumber.get_option_help
            else:
                options = plugin.options.union(plugin.common_options)

                def hfunc(name):
                    for rec in options:
                        if rec.option == name:
                            ans = getattr(rec, 'help', None)
                            if ans is not None:
                                return ans.replace('%default', str(rec.recommended_value))
            return cls(self, self.plumber.get_option_by_name, hfunc, None, None)

        self.load_conversion_widgets()
        widgets = list(map(widget_factory, self.conversion_widgets))
        self.model = Model(widgets)
        self.list.setModel(self.model)

        for w in widgets:
            w.changed_signal.connect(self.changed_signal)
            w.layout().setContentsMargins(6, 6, 6, 6)
            sa = QScrollArea(self)
            sa.setWidget(w)
            sa.setWidgetResizable(True)
            self.stack.addWidget(sa)
            if isinstance(w, TOCWidget):
                w.manually_fine_tune_toc.hide()

        self.list.current_changed.connect(self.category_current_changed)
        self.list.setCurrentIndex(self.model.index(0))

    def initialize(self):
        ConfigWidgetBase.initialize(self)

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.stack.currentWidget().widget().restore_defaults(self.plumber.get_option_by_name)
        self.changed_signal.emit()

    def commit(self):
        for widget in self.model.widgets:
            if not widget.pre_commit_check():
                raise AbortCommit('abort')
            widget.commit(save_defaults=True)
        return ConfigWidgetBase.commit(self)

    def category_current_changed(self, n, p):
        self.stack.setCurrentIndex(n.row())


class CommonOptions(Base):

    def load_conversion_widgets(self):
        self.conversion_widgets = [LookAndFeelWidget, HeuristicsWidget,
                PageSetupWidget,
                StructureDetectionWidget, TOCWidget, SearchAndReplaceWidget,]


class InputOptions(Base):

    def load_conversion_widgets(self):
        self.conversion_widgets = []
        for plugin in input_format_plugins():
            pw = config_widget_for_input_plugin(plugin)
            if pw is not None:
                pw.conv_plugin = plugin
                self.conversion_widgets.append(pw)


class OutputOptions(Base):

    def load_conversion_widgets(self):
        self.conversion_widgets = []
        for plugin in output_format_plugins():
            name = plugin.name.lower().replace(' ', '_')
            try:
                output_widget = importlib.import_module(
                        'calibre.gui2.convert.'+name)
                pw = output_widget.PluginWidget
                pw.conv_plugin = plugin
                self.conversion_widgets.append(pw)
            except ImportError:
                continue


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    # test_widget('Conversion', 'Input Options')
    test_widget('Conversion', 'Common Options')
    # test_widget('Conversion', 'Output Options')
