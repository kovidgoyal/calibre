#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from qt.core import QKeySequence, QListWidgetItem, Qt

from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.look_feel_ui import Ui_Form


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui

        self.tabWidget.setCurrentIndex(0)
        self.tabWidget.tabBar().setVisible(False)
        keys = [QKeySequence('F11', QKeySequence.SequenceFormat.PortableText), QKeySequence(
            'Ctrl+Shift+F', QKeySequence.SequenceFormat.PortableText)]
        keys = [str(x.toString(QKeySequence.SequenceFormat.NativeText)) for x in keys]

        for i in range(self.tabWidget.count()):
            self.sections_view.addItem(QListWidgetItem(self.tabWidget.tabIcon(i), self.tabWidget.tabText(i).replace('&', '')))
        self.sections_view.setCurrentRow(self.tabWidget.currentIndex())
        self.sections_view.currentRowChanged.connect(self.tabWidget.setCurrentIndex)
        self.sections_view.setMaximumWidth(self.sections_view.sizeHintForColumn(0) + 16)
        self.sections_view.setSpacing(4)
        self.sections_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tabWidget.currentWidget().setFocus(Qt.FocusReason.OtherFocusReason)

    def initial_tab_changed(self):
        self.sections_view.setCurrentRow(self.tabWidget.currentIndex())

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        for w in self.tabWidget.all_widgets:
            if hasattr(w, 'restore_defaults'):
                w.restore_defaults()
        self.changed_signal.emit()

    def refresh_gui(self, gui):
        m = gui.library_view.model()
        m.update_db_prefs_cache()
        m.beginResetModel(), m.endResetModel()
        gui.tags_view.model().reset_tag_browser()


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    test_widget('Interface', 'Look & Feel')
