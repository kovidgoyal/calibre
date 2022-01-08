#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json

from qt.core import Qt, QDialog

from calibre.gui2.convert.look_and_feel_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.ebooks.conversion.config import OPTIONS
from polyglot.builtins import iteritems


class LookAndFeelWidget(Widget, Ui_Form):

    TITLE = _('Look & feel')
    ICON  = 'lookfeel.png'
    HELP  = _('Control the look and feel of the output.')
    COMMIT_NAME = 'look_and_feel'

    FILTER_CSS = {
            'fonts': {'font-family'},
            'margins': {'margin', 'margin-left', 'margin-right', 'margin-top',
                'margin-bottom'},
            'padding':  {'padding', 'padding-left', 'padding-right', 'padding-top',
                'padding-bottom'},
            'floats': {'float'},
            'colors': {'color', 'background', 'background-color'},
    }

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['pipe']['look_and_feel'])
        for val, text in [
                ('original', _('Original')),
                ('left', _('Left align')),
                ('justify', _('Justify text'))
                ]:
            self.opt_change_justification.addItem(text, (val))
        self.db, self.book_id = db, book_id
        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_disable_font_rescaling.toggle()
        self.opt_disable_font_rescaling.toggle()
        self.button_font_key.clicked.connect(self.font_key_wizard)
        self.opt_remove_paragraph_spacing.toggle()
        self.opt_remove_paragraph_spacing.toggle()
        connect_lambda(self.opt_smarten_punctuation.stateChanged, self, lambda self, state:
                state != Qt.CheckState.Unchecked and self.opt_unsmarten_punctuation.setCheckState(Qt.CheckState.Unchecked))
        connect_lambda(self.opt_unsmarten_punctuation.stateChanged, self, lambda self, state:
                state != Qt.CheckState.Unchecked and self.opt_smarten_punctuation.setCheckState(Qt.CheckState.Unchecked))

    def get_value_handler(self, g):
        if g is self.opt_change_justification:
            ans = str(g.itemData(g.currentIndex()) or '')
            return ans
        if g is self.opt_filter_css:
            ans = set()
            for key, item in iteritems(self.FILTER_CSS):
                w = getattr(self, 'filter_css_%s'%key)
                if w.isChecked():
                    ans = ans.union(item)
            ans = ans.union({x.strip().lower() for x in
                str(self.filter_css_others.text()).split(',')})
            return ','.join(ans) if ans else None
        if g is self.opt_font_size_mapping:
            val = str(g.text()).strip()
            val = [x.strip() for x in val.split(',' if ',' in val else ' ') if x.strip()]
            return ', '.join(val) or None
        if g is self.opt_transform_css_rules or g is self.opt_transform_html_rules:
            return json.dumps(g.rules)
        return Widget.get_value_handler(self, g)

    def set_value_handler(self, g, val):
        if g is self.opt_change_justification:
            for i in range(g.count()):
                c = str(g.itemData(i) or '')
                if val == c:
                    g.setCurrentIndex(i)
                    break
            return True
        if g is self.opt_filter_css:
            if not val:
                val = ''
            items = frozenset(x.strip().lower() for x in val.split(','))
            for key, vals in iteritems(self.FILTER_CSS):
                w = getattr(self, 'filter_css_%s'%key)
                if not vals - items:
                    items = items - vals
                    w.setChecked(True)
                else:
                    w.setChecked(False)
            self.filter_css_others.setText(', '.join(items))
            return True
        if g is self.opt_transform_css_rules or g is self.opt_transform_html_rules:
            g.rules = json.loads(val) if val else []
            return True

    def connect_gui_obj_handler(self, gui_obj, slot):
        if gui_obj is self.opt_filter_css:
            for key in self.FILTER_CSS:
                w = getattr(self, 'filter_css_%s'%key)
                w.stateChanged.connect(slot)
            self.filter_css_others.textChanged.connect(slot)
            return
        if gui_obj is self.opt_transform_css_rules or gui_obj is self.opt_transform_html_rules:
            gui_obj.changed.connect(slot)
            return
        raise NotImplementedError()

    def font_key_wizard(self):
        from calibre.gui2.convert.font_key import FontKeyChooser
        d = FontKeyChooser(self, self.opt_base_font_size.value(),
                str(self.opt_font_size_mapping.text()).strip())
        if d.exec() == QDialog.DialogCode.Accepted:
            self.opt_font_size_mapping.setText(', '.join(['%.1f'%x for x in
                d.fsizes]))
            self.opt_base_font_size.setValue(d.dbase)
