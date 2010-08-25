#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QWidget, pyqtSignal, QCheckBox

from calibre.customize.ui import preferences_plugins
from calibre.utils.config import DynamicConfig, XMLConfig

class ConfigWidgetInterface(object):

    changed_signal = None

    def genesis(self, gui):
        raise NotImplementedError()

    def restore_defaults(self):
        pass

    def commit(self):
        pass

class Setting(object):

    def __init__(self, name, config_obj, widget, gui_name=None):
        self.name, self.gui_name = name, gui_name
        if gui_name is None:
            self.gui_name = 'opt_'+name
        self.config_obj = config_obj
        self.gui_obj = getattr(widget, self.gui_name)

        if isinstance(self.gui_obj, QCheckBox):
            self.datatype = 'bool'
            self.gui_obj.stateChanged.connect(lambda x:
                    widget.changed_signal.emit())
        else:
            raise ValueError('Unknown data type')

        if isinstance(config_obj, (DynamicConfig, XMLConfig)):
            self.config_type = 'dict'
        else:
            raise ValueError('Unknown config type')

    def initialize(self):
        self.set_gui_val()

    def commit(self):
        self.set_config_val()

    def restore_defaults(self):
        self.set_gui_val(to_default=True)

    def set_gui_val(self, to_default=False):
        if self.config_type == 'dict':
            if to_default:
                val = self.config_obj.defaults[self.name]
            else:
                val = self.config_obj[self.name]
        if self.datatype == 'bool':
            self.gui_obj.setChecked(bool(val))

    def set_config_val(self):
        if self.datatype == 'bool':
            val = bool(self.gui_obj.isChecked())
        if self.config_type == 'dict':
            self.config_obj[self.name] = val


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

