#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QWidget, pyqtSignal

from calibre.customize.ui import preferences_plugins

class ConfigWidgetInterface(object):

    changed_signal = None

    def genesis(self, gui):
        raise NotImplementedError()

    def restore_defaults(self):
        pass

    def commit(self):
        pass


class ConfigWidgetBase(QWidget, ConfigWidgetInterface):

    changed_signal = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        if hasattr(self, 'setupUi'):
            self.setupUi(self)

def get_plugin(category, name):
    for plugin in preferences_plugins():
        if plugin.category == category and plugin.name == name:
            return plugin
    raise ValueError(
            'No Preferences PLugin with category: %s and name: %s found' %
            (category, name))

def test_widget(category, name, gui=None): # {{{
    from PyQt4.Qt import QDialog, QVBoxLayout, QDialogButtonBox
    pl = get_plugin(category, name)
    d = QDialog()
    d.resize(750, 550)
    bb = QDialogButtonBox(d)
    bb.setStandardButtons(bb.Apply|bb.Cancel|bb.RestoreDefaults)
    bb.accepted.connect(d.accept)
    bb.rejected.connect(d.reject)
    w = pl.create_widget(d)
    bb.button(bb.RestoreDefaults).clicked.connect(w.restore_defaults)
    bb.button(bb.Apply).setEnabled(False)
    w.changed_signal.connect(lambda : bb.button(bb.Apply).setEnable(True))
    l = QVBoxLayout()
    pl.setLayout(l)
    l.addWidget(w)
    if gui is None:
        from calibre.gui2.ui import Main
        from calibre.gui2.main import option_parser
        from calibre.library.db import db
        parser = option_parser()
        opts, args = parser.parse_args([])
        actions = tuple(Main.create_application_menubar())
        db = db()
        gui = Main(opts)
        gui.initialize(db.library_path, db, None, actions)
    w.genesis(gui)
    if d.exec_() == QDialog.Accepted:
        w.commit()
# }}}

