#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import SIGNAL, QVariant

from calibre.gui2.convert.look_and_feel_ui import Ui_Form
from calibre.gui2.convert import Widget

class LookAndFeelWidget(Widget, Ui_Form):

    TITLE = _('Look & Feel')
    ICON  = I('lookfeel.png')
    HELP  = _('Control the look and feel of the output')
    COMMIT_NAME = 'look_and_feel'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
                ['change_justification', 'extra_css', 'base_font_size',
                    'font_size_mapping', 'line_height',
                    'linearize_tables', 'smarten_punctuation',
                    'disable_font_rescaling', 'insert_blank_line',
                    'remove_paragraph_spacing', 'remove_paragraph_spacing_indent_size','input_encoding',
                    'asciiize', 'keep_ligatures']
                )
        for val, text in [
                ('original', _('Original')),
                ('left', _('Left align')),
                ('justify', _('Justify text'))
                ]:
            self.opt_change_justification.addItem(text, QVariant(val))
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_disable_font_rescaling.toggle()
        self.opt_disable_font_rescaling.toggle()
        self.connect(self.button_font_key, SIGNAL('clicked()'),
                self.font_key_wizard)
        self.opt_remove_paragraph_spacing.toggle()
        self.opt_remove_paragraph_spacing.toggle()

    def get_value_handler(self, g):
        if g is self.opt_change_justification:
            ans = unicode(g.itemData(g.currentIndex()).toString())
            return ans
        return Widget.get_value_handler(self, g)

    def set_value_handler(self, g, val):
        if g is self.opt_change_justification:
            for i in range(g.count()):
                c = unicode(g.itemData(i).toString())
                if val == c:
                    g.setCurrentIndex(i)
                    break
            return True

    def font_key_wizard(self):
        from calibre.gui2.convert.font_key import FontKeyChooser
        d = FontKeyChooser(self, self.opt_base_font_size.value(),
                unicode(self.opt_font_size_mapping.text()).strip())
        if d.exec_() == d.Accepted:
            self.opt_font_size_mapping.setText(', '.join(['%.1f'%x for x in
                d.fsizes]))
            self.opt_base_font_size.setValue(d.dbase)


