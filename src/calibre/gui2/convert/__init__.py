#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap

from PyQt4.Qt import QWidget, QSpinBox, QDoubleSpinBox, QLineEdit, QTextEdit, \
    QCheckBox, QComboBox, Qt, QIcon, SIGNAL

from calibre.customize.conversion import OptionRecommendation
from calibre.ebooks.conversion.config import load_defaults, \
        save_defaults as save_defaults_, \
    load_specifics, GuiRecommendations

class Widget(QWidget):

    TITLE = _('Unknown')
    ICON  = I('config.svg')
    HELP  = ''

    def __init__(self, parent, name, options):
        QWidget.__init__(self, parent)
        self.setupUi(self)
        self._options = options
        self._name = name
        self._icon = QIcon(self.ICON)
        for name in self._options:
            if not hasattr(self, 'opt_'+name):
                raise Exception('Option %s missing in %s'%(name,
                    self.__class__.__name__))

    def initialize_options(self, get_option, get_help, db=None, book_id=None):
        '''
        :param get_option: A callable that takes one argument: the option name
        and returns the corresponding OptionRecommendation.
        :param get_help: A callable that takes the option name and return a help
        string.
        '''
        defaults = load_defaults(self._name)
        defaults.merge_recommendations(get_option, OptionRecommendation.LOW,
                self._options)

        if db is not None:
            specifics = load_specifics(db, book_id)
            specifics.merge_recommendations(get_option, OptionRecommendation.HIGH,
                    self._options, only_existing=True)
            defaults.update(specifics)


        self.apply_recommendations(defaults)
        self.setup_help(get_help)

    def commit_options(self, save_defaults=False):
        recs = self.create_recommendations()
        if save_defaults:
            save_defaults_(self._name, recs)
        return recs

    def create_recommendations(self):
        recs = GuiRecommendations()
        for name in self._options:
            gui_opt = getattr(self, 'opt_'+name, None)
            if gui_opt is None: continue
            recs[name] = self.get_value(gui_opt)
        return recs

    def apply_recommendations(self, recs):
        for name, val in recs.items():
            gui_opt = getattr(self, 'opt_'+name, None)
            if gui_opt is None: continue
            self.set_value(gui_opt, val)
            if name in getattr(recs, 'disabled_options', []):
                gui_opt.setDisabled(True)


    def get_value(self, g):
        from calibre.gui2.convert.xpath_wizard import XPathEdit
        from calibre.gui2.convert.regex_builder import RegexEdit
        ret = self.get_value_handler(g)
        if ret != 'this is a dummy return value, xcswx1avcx4x':
            return ret
        if isinstance(g, (QSpinBox, QDoubleSpinBox)):
            return g.value()
        elif isinstance(g, (QLineEdit, QTextEdit)):
            func = getattr(g, 'toPlainText', getattr(g, 'text', None))()
            ans = unicode(func).strip()
            if not ans:
                ans = None
            return ans
        elif isinstance(g, QComboBox):
            return unicode(g.currentText())
        elif isinstance(g, QCheckBox):
            return bool(g.isChecked())
        elif isinstance(g, XPathEdit):
            return g.xpath if g.xpath else None
        elif isinstance(g, RegexEdit):
            return g.regex if g.regex else None
        else:
            raise Exception('Can\'t get value from %s'%type(g))


    def set_value(self, g, val):
        from calibre.gui2.convert.xpath_wizard import XPathEdit
        from calibre.gui2.convert.regex_builder import RegexEdit
        if self.set_value_handler(g, val):
            return
        if isinstance(g, (QSpinBox, QDoubleSpinBox)):
            g.setValue(val)
        elif isinstance(g, (QLineEdit, QTextEdit)):
            if not val: val = ''
            getattr(g, 'setPlainText', g.setText)(val)
            getattr(g, 'setCursorPosition', lambda x: x)(0)
        elif isinstance(g, QComboBox) and val:
            idx = g.findText(val, Qt.MatchFixedString)
            if idx < 0:
                g.addItem(val)
                idx = g.findText(val, Qt.MatchFixedString)
            g.setCurrentIndex(idx)
        elif isinstance(g, QCheckBox):
            g.setCheckState(Qt.Checked if bool(val) else Qt.Unchecked)
        elif isinstance(g, (XPathEdit, RegexEdit)):
            g.edit.setText(val if val else '')
        else:
            raise Exception('Can\'t set value %s in %s'%(repr(val),
                unicode(g.objectName())))
        self.post_set_value(g, val)

    def set_help(self, msg):
        if msg and getattr(msg, 'strip', lambda:True)():
            try:
                self.emit(SIGNAL('set_help(PyQt_PyObject)'), msg)
            except:
                pass

    def setup_help(self, help_provider):
        w = textwrap.TextWrapper(80)
        for name in self._options:
            g = getattr(self, 'opt_'+name, None)
            if g is None:
                continue
            help = help_provider(name)
            if not help: continue
            g._help = help
            g.setToolTip('\n'.join(w.wrap(help.replace('<', '&lt;').replace('>',
                '&gt;'))))
            g.setWhatsThis('\n'.join(w.wrap(help.replace('<', '&lt;').replace('>',
                '&gt;'))))
            g.__class__.enterEvent = lambda obj, event: self.set_help(getattr(obj, '_help', obj.toolTip()))


    def set_value_handler(self, g, val):
        return False

    def post_set_value(self, g, val):
        pass

    def get_value_handler(self, g):
        return 'this is a dummy return value, xcswx1avcx4x'

    def post_get_value(self, g):
        pass

    def pre_commit_check(self):
        return True

    def commit(self, save_defaults=False):
        return self.commit_options(save_defaults)

    def config_title(self):
        return self.TITLE

    def config_icon(self):
        return self._icon

