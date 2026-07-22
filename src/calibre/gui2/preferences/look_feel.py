#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid@kovidgoyal.net>

from qt.core import QListWidgetItem, QMenu, QPoint, Qt, QTabWidget

from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.look_feel_ui import Ui_Form
from calibre.utils.localization import _


class ConfigWidget(ConfigWidgetBase, Ui_Form):
    def genesis(self, gui):
        self.gui = gui

        self.tabWidget.setCurrentIndex(0)
        if tab_bar := self.tabWidget.tabBar():
            tab_bar.setVisible(False)

        for i in range(self.tabWidget.count()):
            self.sections_view.addItem(QListWidgetItem(self.tabWidget.tabIcon(i), self.tabWidget.tabText(i).replace('&', '')))
        self.sections_view.setCurrentRow(self.tabWidget.currentIndex())
        self.sections_view.currentRowChanged.connect(self.tabWidget.setCurrentIndex)
        self.sections_view.setMaximumWidth(self.sections_view.sizeHintForColumn(0) + 16)
        self.sections_view.setSpacing(4)
        self.sections_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sections_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sections_view.customContextMenuRequested.connect(self.show_context_menu_for_section)

        self.tabWidget.currentWidget().setFocus(Qt.FocusReason.OtherFocusReason)

    def initial_tab_changed(self):
        self.sections_view.setCurrentRow(self.tabWidget.currentIndex())

    def _restore_widget_defaults(self, widget):
        if hasattr(widget, 'restore_defaults'):
            widget.restore_defaults()
        elif isinstance(widget, QTabWidget):
            for i in range(widget.count()):
                sw = widget.widget(i)
                if sw is not None and hasattr(sw, 'restore_defaults'):
                    sw.restore_defaults()

    def restore_defaults(self, *args):
        ConfigWidgetBase.restore_defaults(self)
        for w in self.tabWidget.all_widgets:
            self._restore_widget_defaults(w)
        self.changed_signal.emit()

    def refresh_gui(self, gui):
        m = gui.library_view.model()
        m.update_db_prefs_cache()
        m.beginResetModel(), m.endResetModel()
        gui.tags_view.model().reset_tag_browser()

    def show_context_menu_for_section(self, pos: QPoint) -> None:
        if item := self.sections_view.itemAt(pos):
            menu = QMenu(self.sections_view)
            menu.addAction(_('Restore defaults for {}').format(item.data(Qt.ItemDataRole.DisplayRole)))
            num = self.sections_view.indexFromItem(item).row()
            widget = tuple(self.tabWidget.all_widgets)[num]
            pos = self.sections_view.mapToGlobal(pos)
            can_restore = hasattr(widget, 'restore_defaults') or isinstance(widget, QTabWidget)
            if can_restore and menu.exec(pos):  # type: ignore
                self._restore_widget_defaults(widget)
                self.changed_signal.emit()


if __name__ == '__main__':
    from calibre.gui2 import Application

    app = Application([])
    test_widget('Interface', 'Look & Feel')
