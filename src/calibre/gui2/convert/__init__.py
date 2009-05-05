#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from PyQt4.Qt import QWidget, QSpinBox, QDoubleSpinBox, QLineEdit, QTextEdit, \
    QCheckBox, QComboBox, Qt, QIcon, SIGNAL

from calibre.customize.conversion import OptionRecommendation
from calibre.utils.config import config_dir
from calibre.utils.lock import ExclusiveFile
from calibre import sanitize_file_name

config_dir = os.path.join(config_dir, 'conversion')
if not os.path.exists(config_dir):
    os.makedirs(config_dir)

def name_to_path(name):
    return os.path.join(config_dir, sanitize_file_name(name)+'.py')

def save_defaults(name, recs):
    path = name_to_path(name)
    raw = str(recs)
    with open(path, 'wb'):
        pass
    with ExclusiveFile(path) as f:
        f.write(raw)
save_defaults_ = save_defaults

def load_defaults(name):
    path = name_to_path(name)
    if not os.path.exists(path):
        open(path, 'wb').close()
    with ExclusiveFile(path) as f:
        raw = f.read()
    r = GuiRecommendations()
    if raw:
        r.from_string(raw)
    return r

def save_specifics(db, book_id, recs):
    raw = str(recs)
    db.set_conversion_options(book_id, 'PIPE', raw)

def load_specifics(db, book_id):
    raw = db.conversion_options(book_id, 'PIPE')
    r = GuiRecommendations()
    if raw:
        r.from_string(raw)
    return r

class GuiRecommendations(dict):

    def __new__(cls, *args):
        dict.__new__(cls)
        obj = super(GuiRecommendations, cls).__new__(cls, *args)
        obj.disabled_options = set([])
        return obj

    def to_recommendations(self, level=OptionRecommendation.LOW):
        ans = []
        for key, val in self.items():
            ans.append((key, val, level))
        return ans

    def __str__(self):
        ans = ['{']
        for key, val in self.items():
            ans.append('\t'+repr(key)+' : '+repr(val)+',')
        ans.append('}')
        return '\n'.join(ans)

    def from_string(self, raw):
        try:
            d = eval(raw)
        except SyntaxError:
            d = None
        if d:
            self.update(d)

    def merge_recommendations(self, get_option, level, options):
        for name in options:
            opt = get_option(name)
            if opt is None: continue
            if opt.level == OptionRecommendation.HIGH:
                self[name] = opt.recommended_value
                self.disabled_options.add(name)
            elif opt.level > level or name not in self:
                self[name] = opt.recommended_value


class Widget(QWidget):

    TITLE = _('Unknown')
    ICON  = ':/images/config.svg'
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
        and returns the correspoing OptionRecommendation.
        :param get_help: A callable that takes the option name and return a help
        string.
        '''
        defaults = load_defaults(self._name)
        defaults.merge_recommendations(get_option, OptionRecommendation.LOW,
                self._options)

        if db is not None:
            specifics = load_specifics(db, book_id)
            specifics.merge_recommendations(get_option, OptionRecommendation.HIGH,
                    self._options)
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
        else:
            raise Exception('Can\'t get value from %s'%type(g))


    def set_value(self, g, val):
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
        else:
            raise Exception('Can\'t set value %s in %s'%(repr(val), type(g)))
        self.post_set_value(g, val)

    def set_help(self, msg):
        if msg and getattr(msg, 'strip', lambda:True)():
            self.emit(SIGNAL('set_help(PyQt_PyObject)'), msg)

    def setup_help(self, help_provider):
        for name in self._options:
            g = getattr(self, 'opt_'+name, None)
            if g is None:
                continue
            help = help_provider(name)
            if not help: continue
            g._help = help
            g.setToolTip(help.replace('<', '&lt;').replace('>', '&gt;'))
            g.setWhatsThis(help.replace('<', '&lt;').replace('>', '&gt;'))
            g.__class__.enterEvent = lambda obj, event: self.set_help(getattr(obj, '_help', obj.toolTip()))


    def set_value_handler(self, g, val):
        return False

    def post_set_value(self, g, val):
        pass

    def get_value_handler(self, g):
        return 'this is a dummy return value, xcswx1avcx4x'

    def post_get_value(self, g):
        pass

    def commit(self, save_defaults=False):
        return self.commit_options(save_defaults)

    def config_title(self):
        return self.TITLE

    def config_icon(self):
        return self._icon

