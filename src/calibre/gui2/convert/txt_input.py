# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from PyQt5.Qt import QListWidgetItem, Qt

from calibre.gui2.convert.txt_input_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.ebooks.conversion.plugins.txt_input import MD_EXTENSIONS
from calibre.ebooks.conversion.config import OPTIONS


class PluginWidget(Widget, Ui_Form):

    TITLE = _('TXT input')
    HELP = _('Options specific to')+' TXT '+_('input')
    COMMIT_NAME = 'txt_input'
    ICON = I('mimetypes/txt.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['input']['txt'])
        self.db, self.book_id = db, book_id
        for x in get_option('paragraph_type').option.choices:
            self.opt_paragraph_type.addItem(x)
        for x in get_option('formatting_type').option.choices:
            self.opt_formatting_type.addItem(x)
        self.md_map = {}
        for name, text in MD_EXTENSIONS.iteritems():
            i = QListWidgetItem('%s - %s' % (name, text), self.opt_markdown_extensions)
            i.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            i.setData(Qt.UserRole, name)
            self.md_map[name] = i

        self.initialize_options(get_option, get_help, db, book_id)

    def set_value_handler(self, g, val):
        if g is self.opt_markdown_extensions:
            for i in self.md_map.itervalues():
                i.setCheckState(Qt.Unchecked)
            for x in val.split(','):
                x = x.strip()
                if x in self.md_map:
                    self.md_map[x].setCheckState(Qt.Checked)
            return True

    def get_value_handler(self, g):
        if g is not self.opt_markdown_extensions:
            return Widget.get_value_handler(self, g)
        return ', '.join(unicode(i.data(Qt.UserRole) or '') for i in self.md_map.itervalues() if i.checkState())

    def connect_gui_obj_handler(self, g, f):
        if g is not self.opt_markdown_extensions:
            raise NotImplementedError()
        g.itemChanged.connect(lambda item: f())
