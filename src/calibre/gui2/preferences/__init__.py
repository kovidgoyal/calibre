#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QWidget, pyqtSignal, QCheckBox, QAbstractSpinBox, \
    QLineEdit, QComboBox, QVariant

from calibre.customize.ui import preferences_plugins

class ConfigWidgetInterface(object):

    changed_signal = None

    def genesis(self, gui):
        raise NotImplementedError()

    def restore_defaults(self):
        pass

    def commit(self):
        pass

class Setting(object):

    def __init__(self, name, config_obj, widget, gui_name=None,
            empty_string_is_None=True, choices=None):
        self.name, self.gui_name = name, gui_name
        self.empty_string_is_None = empty_string_is_None
        self.choices = choices
        if gui_name is None:
            self.gui_name = 'opt_'+name
        self.config_obj = config_obj
        self.gui_obj = getattr(widget, self.gui_name)

        if isinstance(self.gui_obj, QCheckBox):
            self.datatype = 'bool'
            self.gui_obj.stateChanged.connect(lambda x:
                    widget.changed_signal.emit())
        elif isinstance(self.gui_obj, QAbstractSpinBox):
            self.datatype = 'number'
            self.gui_obj.valueChanged.connect(lambda x:
                    widget.changed_signal.emit())
        elif isinstance(self.gui_obj, QLineEdit):
            self.datatype = 'string'
            self.gui_obj.textChanged.connect(lambda x:
                    widget.changed_signal.emit())
        elif isinstance(self.gui_obj, QComboBox):
            self.datatype = 'choice'
            self.gui_obj.editTextChanged.connect(lambda x:
                    widget.changed_signal.emit())
            self.gui_obj.currentIndexChanged.connect(lambda x:
                    widget.changed_signal.emit())
        else:
            raise ValueError('Unknown data type')

    def initialize(self):
        self.gui_obj.blockSignals(True)
        if self.datatype == 'choices':
            self.gui_obj.clear()
            for x in self.choices:
                if isinstance(x, basestring):
                    x = (x, x)
                self.gui_obj.addItem(x[0], QVariant(x[1]))
        self.set_gui_val(self.get_config_val(default=False))
        self.gui_obj.blockSignals(False)

    def commit(self):
        self.set_config_val(self.get_gui_val())

    def restore_defaults(self):
        self.set_gui_val(self.get_config_val(default=True))

    def get_config_val(self, default=False):
        if default:
            val = self.config_obj.defaults[self.name]
        else:
            val = self.config_obj[self.name]
        return val

    def set_config_val(self, val):
        self.config_obj[self.name] = val

    def set_gui_val(self, val):
        if self.datatype == 'bool':
            self.gui_obj.setChecked(bool(val))
        elif self.datatype == 'number':
            self.gui_obj.setValue(val)
        elif self.datatype == 'string':
            self.gui_obj.setText(val if val else '')
        elif self.datatype == 'choices':
            idx = self.gui_obj.findData(QVariant(val))
            if idx == -1:
                idx = 0
            self.gui_obj.setCurrentIndex(idx)

    def get_gui_val(self):
        if self.datatype == 'bool':
            val = bool(self.gui_obj.isChecked())
        elif self.datatype == 'number':
            val = self.gui_obj.value(val)
        elif self.datatype == 'string':
            val = unicode(self.gui_name.text()).strip()
            if self.empty_string_is_None and not val:
                val = None
        elif self.datatype == 'choices':
            idx = self.gui_obj.currentIndex()
            val = unicode(self.gui_obj.itemData(idx).toString())
        return val


class ConfigWidgetBase(QWidget, ConfigWidgetInterface):

    changed_signal = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        if hasattr(self, 'setupUi'):
            self.setupUi(self)
        self.settings = {}

    def register(self, name, config_obj, widget, gui_name=None):
        setting = Setting(name, config_obj, widget, gui_name=gui_name)
        self.register_setting(setting)

    def register_setting(self, setting):
        self.settings[setting.name] = setting
        return setting

    def initialize(self):
        for setting in self.settings.values():
            setting.initialize()

    def commit(self):
        for setting in self.settings.values():
            setting.commit()

    def restore_defaults(self, *args):
        for setting in self.settings.values():
            setting.restore_defaults()



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

