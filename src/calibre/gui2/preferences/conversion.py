#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid@kovidgoyal.net>

import importlib
from typing import TYPE_CHECKING, cast

from qt.core import QHBoxLayout, QIcon, QListView, QScrollArea, QSize, QSizePolicy, QStackedWidget, QStringListModel, Qt, pyqtSignal

from calibre.customize.ui import input_format_plugins, output_format_plugins
from calibre.ebooks.conversion.plumber import Plumber
from calibre.gui2.convert import config_widget_for_input_plugin
from calibre.gui2.convert.heuristics import HeuristicsWidget
from calibre.gui2.convert.look_and_feel import LookAndFeelWidget
from calibre.gui2.convert.page_setup import PageSetupWidget
from calibre.gui2.convert.search_and_replace import SearchAndReplaceWidget
from calibre.gui2.convert.structure_detection import StructureDetectionWidget
from calibre.gui2.convert.toc import TOCWidget
from calibre.gui2.preferences import AbortCommit, ConfigWidgetBase, test_widget
from calibre.utils.localization import _
from calibre.utils.logging import Log

if TYPE_CHECKING:
    from collections.abc import Callable

    from qt.core import QModelIndex, QWidget

    from calibre.gui2.convert import GetHelp, GetOption, Widget
    from calibre.gui2.ui import Main

    # The concrete conversion widget classes all accept these constructor arguments
    type ConversionWidgetFactory = Callable[[QWidget, GetOption, GetHelp, None, None], Widget]


class Model(QStringListModel):
    def __init__(self, widgets: list[Widget]) -> None:
        QStringListModel.__init__(self)
        self.widgets = widgets
        self.setStringList([w.TITLE for w in widgets])

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if role == Qt.ItemDataRole.DecorationRole:
            w = self.widgets[index.row()]
            if w.ICON:
                return QIcon.ic(w.ICON)
        return QStringListModel.data(self, index, role)


class ListView(QListView):
    current_changed = pyqtSignal(object, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        QListView.__init__(self, parent)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Expanding)
        f = self.font()
        f.setBold(True)
        self.setFont(f)
        self.setIconSize(QSize(48, 48))
        self.setFlow(QListView.Flow.TopToBottom)
        self.setSpacing(10)

    def currentChanged(self, current: QModelIndex, previous: QModelIndex) -> None:
        QListView.currentChanged(self, current, previous)
        self.current_changed.emit(current, previous)


class Base(ConfigWidgetBase):
    conversion_widgets: list[type[Widget]]
    restore_defaults_desc = _('Restore settings to default values. Only settings for the currently selected section are restored.')

    def load_conversion_widgets(self) -> None: ...

    def setupUi(self, x: object) -> None:
        self.resize(720, 603)
        self.l = l = QHBoxLayout(self)
        self.list = lv = ListView(self)
        l.addWidget(lv)
        self.stack = s = QStackedWidget(self)
        l.addWidget(s, stretch=10)

    def genesis(self, gui: Main) -> None:
        log = Log()
        log.outputs = []

        self.plumber = Plumber('dummy.epub', 'dummy.epub', log, dummy=True, merge_plugin_recs=False)

        def widget_factory(cls: type[Widget]) -> Widget:
            plugin = getattr(cls, 'conv_plugin', None)
            if plugin is None:
                hfunc = self.plumber.get_option_help
            else:
                options = plugin.options.union(plugin.common_options)

                def hfunc(name: str) -> str | None:
                    for rec in options:
                        if rec.option == name:
                            ans = getattr(rec, 'help', None)
                            if ans is not None:
                                return ans.replace('%default', str(rec.recommended_value))

            return cast('ConversionWidgetFactory', cls)(self, self.plumber.get_option_by_name, hfunc, None, None)

        self.load_conversion_widgets()
        widgets = list(map(widget_factory, self.conversion_widgets))
        self.model = Model(widgets)
        self.list.setModel(self.model)

        for w in widgets:
            w.changed_signal.connect(self.changed_signal)
            wl = w.layout()
            assert wl is not None
            wl.setContentsMargins(6, 6, 6, 6)
            sa = QScrollArea(self)
            sa.setWidget(w)
            sa.setWidgetResizable(True)
            self.stack.addWidget(sa)
            if isinstance(w, TOCWidget):
                w.manually_fine_tune_toc.hide()

        self.list.current_changed.connect(self.category_current_changed)
        self.list.setCurrentIndex(self.model.index(0))

    def initialize(self) -> None:
        ConfigWidgetBase.initialize(self)

    def restore_defaults(self, *args: object) -> None:
        ConfigWidgetBase.restore_defaults(self)
        sa = self.stack.currentWidget()
        assert isinstance(sa, QScrollArea)
        inner = sa.widget()
        assert inner is not None
        restore = getattr(inner, 'restore_defaults', None)
        if restore is not None:
            restore(self.plumber.get_option_by_name)
        self.changed_signal.emit()

    def commit(self, *args: object) -> bool:
        for widget in self.model.widgets:
            if not widget.pre_commit_check():
                raise AbortCommit('abort')
            widget.commit(save_defaults=True)
        return ConfigWidgetBase.commit(self)

    def category_current_changed(self, n: QModelIndex, p: QModelIndex) -> None:
        self.stack.setCurrentIndex(n.row())


class CommonOptions(Base):
    def load_conversion_widgets(self) -> None:
        self.conversion_widgets = [
            LookAndFeelWidget,
            HeuristicsWidget,
            PageSetupWidget,
            StructureDetectionWidget,
            TOCWidget,
            SearchAndReplaceWidget,
        ]


class InputOptions(Base):
    def load_conversion_widgets(self) -> None:
        self.conversion_widgets = []
        for plugin in input_format_plugins():
            pw = config_widget_for_input_plugin(plugin)
            if pw is not None:
                pw.conv_plugin = plugin
                self.conversion_widgets.append(pw)


class OutputOptions(Base):
    def load_conversion_widgets(self) -> None:
        self.conversion_widgets = []
        for plugin in output_format_plugins():
            name = plugin.name.lower().replace(' ', '_')
            try:
                output_widget = importlib.import_module('calibre.gui2.convert.' + name)
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
