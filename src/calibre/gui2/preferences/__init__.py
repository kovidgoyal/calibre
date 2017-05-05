#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap

from PyQt5.Qt import (QWidget, pyqtSignal, QCheckBox, QAbstractSpinBox,
    QLineEdit, QComboBox, Qt, QIcon, QDialog, QVBoxLayout,
    QDialogButtonBox)

from calibre.customize.ui import preferences_plugins
from calibre.utils.config import ConfigProxy
from calibre.gui2.complete2 import EditWithComplete


class AbortCommit(Exception):
    pass


class ConfigWidgetInterface(object):

    '''
    This class defines the interface that all widgets displayed in the
    Preferences dialog must implement. See :class:`ConfigWidgetBase` for
    a base class that implements this interface and defines various convenience
    methods as well.
    '''

    #: This signal must be emitted whenever the user changes a value in this
    #: widget
    changed_signal = None

    #: Set to True iff the :meth:`restore_to_defaults` method is implemented.
    supports_restoring_to_defaults = True

    #: The tooltip for the "Restore defaults" button
    restore_defaults_desc = _('Restore settings to default values. '
            'You have to click Apply to actually save the default settings.')

    #: If True the Preferences dialog will not allow the user to set any more
    #: preferences. Only has effect if :meth:`commit` returns True.
    restart_critical = False

    def genesis(self, gui):
        '''
        Called once before the widget is displayed, should perform any
        necessary setup.

        :param gui: The main calibre graphical user interface
        '''
        raise NotImplementedError()

    def initialize(self):
        '''
        Should set all config values to their initial values (the values
        stored in the config files).
        '''
        raise NotImplementedError()

    def restore_defaults(self):
        '''
        Should set all config values to their defaults.
        '''
        pass

    def commit(self):
        '''
        Save any changed settings. Return True if the changes require a
        restart, False otherwise. Raise an :class:`AbortCommit` exception
        to indicate that an error occurred. You are responsible for giving the
        user feedback about what the error is and how to correct it.
        '''
        return False

    def refresh_gui(self, gui):
        '''
        Called once after this widget is committed. Responsible for causing the
        gui to reread any changed settings. Note that by default the GUI
        re-initializes various elements anyway, so most widgets won't need to
        use this method.
        '''
        pass


class Setting(object):

    CHOICES_SEARCH_FLAGS = Qt.MatchExactly | Qt.MatchCaseSensitive

    def __init__(self, name, config_obj, widget, gui_name=None,
            empty_string_is_None=True, choices=None, restart_required=False):
        self.name, self.gui_name = name, gui_name
        self.empty_string_is_None = empty_string_is_None
        self.restart_required = restart_required
        self.choices = choices
        if gui_name is None:
            self.gui_name = 'opt_'+name
        self.config_obj = config_obj
        self.gui_obj = getattr(widget, self.gui_name)
        self.widget = widget

        if isinstance(self.gui_obj, QCheckBox):
            self.datatype = 'bool'
            self.gui_obj.stateChanged.connect(self.changed)
        elif isinstance(self.gui_obj, QAbstractSpinBox):
            self.datatype = 'number'
            self.gui_obj.valueChanged.connect(self.changed)
        elif isinstance(self.gui_obj, QLineEdit):
            self.datatype = 'string'
            self.gui_obj.textChanged.connect(self.changed)
        elif isinstance(self.gui_obj, QComboBox):
            self.datatype = 'choice'
            self.gui_obj.editTextChanged.connect(self.changed)
            self.gui_obj.currentIndexChanged.connect(self.changed)
        else:
            raise ValueError('Unknown data type %s' % self.gui_obj.__class__)

        if isinstance(self.config_obj, ConfigProxy) and \
                not unicode(self.gui_obj.toolTip()):
            h = self.config_obj.help(self.name)
            if h:
                self.gui_obj.setToolTip(h)
        tt = unicode(self.gui_obj.toolTip())
        if tt:
            if not unicode(self.gui_obj.whatsThis()):
                self.gui_obj.setWhatsThis(tt)
            if not unicode(self.gui_obj.statusTip()):
                self.gui_obj.setStatusTip(tt)
            tt = '\n'.join(textwrap.wrap(tt, 70))
            self.gui_obj.setToolTip(tt)

    def changed(self, *args):
        self.widget.changed_signal.emit()

    def initialize(self):
        self.gui_obj.blockSignals(True)
        if self.datatype == 'choice':
            choices = self.choices or []
            if isinstance(self.gui_obj, EditWithComplete):
                self.gui_obj.all_items = choices
            else:
                self.gui_obj.clear()
                for x in choices:
                    if isinstance(x, basestring):
                        x = (x, x)
                    self.gui_obj.addItem(x[0], (x[1]))
        self.set_gui_val(self.get_config_val(default=False))
        self.gui_obj.blockSignals(False)
        self.initial_value = self.get_gui_val()

    def commit(self):
        val = self.get_gui_val()
        oldval = self.get_config_val()
        changed = val != oldval
        if changed:
            self.set_config_val(self.get_gui_val())
        return changed and self.restart_required

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
        elif self.datatype == 'choice':
            if isinstance(self.gui_obj, EditWithComplete):
                self.gui_obj.setText(val)
            else:
                idx = self.gui_obj.findData((val), role=Qt.UserRole,
                        flags=self.CHOICES_SEARCH_FLAGS)
                if idx == -1:
                    idx = 0
                self.gui_obj.setCurrentIndex(idx)

    def get_gui_val(self):
        if self.datatype == 'bool':
            val = bool(self.gui_obj.isChecked())
        elif self.datatype == 'number':
            val = self.gui_obj.value()
        elif self.datatype == 'string':
            val = unicode(self.gui_obj.text()).strip()
            if self.empty_string_is_None and not val:
                val = None
        elif self.datatype == 'choice':
            if isinstance(self.gui_obj, EditWithComplete):
                val = unicode(self.gui_obj.text())
            else:
                idx = self.gui_obj.currentIndex()
                if idx < 0:
                    idx = 0
                val = unicode(self.gui_obj.itemData(idx) or '')
        return val


class CommaSeparatedList(Setting):

    def set_gui_val(self, val):
        x = ''
        if val:
            x = u', '.join(val)
        self.gui_obj.setText(x)

    def get_gui_val(self):
        val = unicode(self.gui_obj.text()).strip()
        ans = []
        if val:
            ans = [x.strip() for x in val.split(',')]
            ans = [x for x in ans if x]
        return ans


class ConfigWidgetBase(QWidget, ConfigWidgetInterface):

    '''
    Base class that contains code to easily add standard config widgets like
    checkboxes, combo boxes, text fields and so on. See the :meth:`register`
    method.

    This class automatically handles change notification, resetting to default,
    translation between gui objects and config objects, etc. for registered
    settings.

    If your config widget inherits from this class but includes setting that
    are not registered, you should override the :class:`ConfigWidgetInterface` methods
    and call the base class methods inside the overrides.
    '''

    changed_signal = pyqtSignal()
    restart_now = pyqtSignal()
    supports_restoring_to_defaults = True
    restart_critical = False

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        if hasattr(self, 'setupUi'):
            self.setupUi(self)
        self.settings = {}

    def register(self, name, config_obj, gui_name=None, choices=None,
            restart_required=False, empty_string_is_None=True, setting=Setting):
        '''
        Register a setting.

        :param name: The setting name
        :param config: The config object that reads/writes the setting
        :param gui_name: The name of the GUI object that presents an interface
                         to change the setting. By default it is assumed to be
                         ``'opt_' + name``.
        :param choices: If this setting is a multiple choice (combobox) based
                        setting, the list of choices. The list is a list of two
                        element tuples of the form: ``[(gui name, value), ...]``
        :param setting: The class responsible for managing this setting. The
                        default class handles almost all cases, so this param
                        is rarely used.
        '''
        setting = setting(name, config_obj, self, gui_name=gui_name,
                choices=choices, restart_required=restart_required,
                empty_string_is_None=empty_string_is_None)
        return self.register_setting(setting)

    def register_setting(self, setting):
        self.settings[setting.name] = setting
        return setting

    def initialize(self):
        for setting in self.settings.values():
            setting.initialize()

    def commit(self, *args):
        restart_required = False
        for setting in self.settings.values():
            rr = setting.commit()
            if rr:
                restart_required = True
        return restart_required

    def restore_defaults(self, *args):
        for setting in self.settings.values():
            setting.restore_defaults()


def get_plugin(category, name):
    for plugin in preferences_plugins():
        if plugin.category == category and plugin.name == name:
            return plugin
    raise ValueError(
            'No Preferences Plugin with category: %s and name: %s found' %
            (category, name))


class ConfigDialog(QDialog):

    def set_widget(self, w):
        self.w = w

    def accept(self):
        try:
            self.restart_required = self.w.commit()
        except AbortCommit:
            return
        QDialog.accept(self)


def init_gui():
    from calibre.gui2.ui import Main
    from calibre.gui2.main import option_parser
    from calibre.library import db
    parser = option_parser()
    opts, args = parser.parse_args([])
    actions = tuple(Main.create_application_menubar())
    db = db()
    gui = Main(opts)
    gui.initialize(db.library_path, db, None, actions, show_gui=False)
    return gui


def show_config_widget(category, name, gui=None, show_restart_msg=False,
        parent=None, never_shutdown=False):
    '''
    Show the preferences plugin identified by category and name

    :param gui: gui instance, if None a hidden gui is created
    :param show_restart_msg: If True and the preferences plugin indicates a
    restart is required, show a message box telling the user to restart
    :param parent: The parent of the displayed dialog

    :return: True iff a restart is required for the changes made by the user to
    take effect
    '''
    from calibre.gui2 import gprefs
    pl = get_plugin(category, name)
    d = ConfigDialog(parent)
    d.resize(750, 550)
    conf_name = 'config_widget_dialog_geometry_%s_%s'%(category, name)
    geom = gprefs.get(conf_name, None)
    d.setWindowTitle(_('Configure ') + name)
    d.setWindowIcon(QIcon(I('config.png')))
    bb = QDialogButtonBox(d)
    bb.setStandardButtons(bb.Apply|bb.Cancel|bb.RestoreDefaults)
    bb.accepted.connect(d.accept)
    bb.rejected.connect(d.reject)
    w = pl.create_widget(d)
    d.set_widget(w)
    bb.button(bb.RestoreDefaults).clicked.connect(w.restore_defaults)
    bb.button(bb.RestoreDefaults).setEnabled(w.supports_restoring_to_defaults)
    bb.button(bb.Apply).setEnabled(False)
    bb.button(bb.Apply).clicked.connect(d.accept)

    def onchange():
        b = bb.button(bb.Apply)
        b.setEnabled(True)
        b.setDefault(True)
        b.setAutoDefault(True)
    w.changed_signal.connect(onchange)
    bb.button(bb.Cancel).setFocus(True)
    l = QVBoxLayout()
    d.setLayout(l)
    l.addWidget(w)
    l.addWidget(bb)
    mygui = gui is None
    if gui is None:
        gui = init_gui()
        mygui = True
    w.genesis(gui)
    w.initialize()
    if geom is not None:
        d.restoreGeometry(geom)
    d.exec_()
    geom = bytearray(d.saveGeometry())
    gprefs[conf_name] = geom
    rr = getattr(d, 'restart_required', False)
    if show_restart_msg and rr:
        from calibre.gui2 import warning_dialog
        warning_dialog(gui, 'Restart required', 'Restart required', show=True)
    if mygui and not never_shutdown:
        gui.shutdown()
    return rr

# Testing {{{


def test_widget(category, name, gui=None):
    show_config_widget(category, name, gui=gui, show_restart_msg=True)


def test_all():
    from PyQt5.Qt import QApplication
    app = QApplication([])
    app
    gui = init_gui()
    for plugin in preferences_plugins():
        test_widget(plugin.category, plugin.name, gui=gui)
    gui.shutdown()


if __name__ == '__main__':
    test_all()
# }}}
