#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import (QWidget, QDialog, QLabel, QGridLayout, QComboBox, QSize,
        QLineEdit, QIntValidator, QDoubleValidator, QFrame, QColor, Qt, QIcon,
        QScrollArea, QPushButton, QVBoxLayout, QDialogButtonBox, QToolButton,
        QListView, QAbstractListModel, pyqtSignal, QSizePolicy, QSpacerItem,
        QApplication)

from calibre import prepare_string_for_xml
from calibre.utils.icu import sort_key
from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.metadata.single_download import RichTextDelegate
from calibre.library.coloring import (Rule, conditionable_columns,
    displayable_columns, rule_from_template)
from calibre.utils.localization import lang_map
from calibre.utils.icu import lower

class ConditionEditor(QWidget): # {{{

    ACTION_MAP = {
            'bool' : (
                    (_('is true'), 'is true',),
                    (_('is false'), 'is false'),
                    (_('is undefined'), 'is undefined')
            ),
            'ondevice' : (
                    (_('is true'), 'is set',),
                    (_('is false'), 'is not set'),
            ),
            'identifiers' : (
                (_('has id'), 'has id'),
                (_('does not have id'), 'does not have id'),
            ),
            'int' : (
                (_('is equal to'), 'eq'),
                (_('is less than'), 'lt'),
                (_('is greater than'), 'gt')
            ),
            'multiple' : (
                (_('has'), 'has'),
                (_('does not have'), 'does not have'),
                (_('has pattern'), 'has pattern'),
                (_('does not have pattern'), 'does not have pattern'),
                (_('is set'), 'is set'),
                (_('is not set'), 'is not set'),
            ),
            'single'   : (
                (_('is'), 'is'),
                (_('is not'), 'is not'),
                (_('matches pattern'), 'matches pattern'),
                (_('does not match pattern'), 'does not match pattern'),
                (_('is set'), 'is set'),
                (_('is not set'), 'is not set'),
            ),
    }

    for x in ('float', 'rating', 'datetime'):
        ACTION_MAP[x] = ACTION_MAP['int']


    def __init__(self, fm, parent=None):
        QWidget.__init__(self, parent)
        self.fm = fm

        self.action_map = self.ACTION_MAP

        self.l = l = QGridLayout(self)
        self.setLayout(l)

        texts = _('If the ___ column ___ values')
        try:
            one, two, three = texts.split('___')
        except:
            one, two, three = 'If the ', ' column ', ' value '

        self.l1 = l1 = QLabel(one)
        l.addWidget(l1, 0, 0)

        self.column_box = QComboBox(self)
        l.addWidget(self.column_box, 0, 1)



        self.l2 = l2 = QLabel(two)
        l.addWidget(l2, 0, 2)

        self.action_box = QComboBox(self)
        l.addWidget(self.action_box, 0, 3)

        self.l3 = l3 = QLabel(three)
        l.addWidget(l3, 0, 4)

        self.value_box = QLineEdit(self)
        l.addWidget(self.value_box, 0, 5)

        self.column_box.addItem('', '')
        for key in sorted(
                conditionable_columns(fm),
                key=sort_key):
            self.column_box.addItem(key, key)
        self.column_box.setCurrentIndex(0)

        self.column_box.currentIndexChanged.connect(self.init_action_box)
        self.action_box.currentIndexChanged.connect(self.init_value_box)

        for b in (self.column_box, self.action_box):
            b.setSizeAdjustPolicy(b.AdjustToMinimumContentsLengthWithIcon)
            b.setMinimumContentsLength(15)

    @dynamic_property
    def current_col(self):
        def fget(self):
            idx = self.column_box.currentIndex()
            return unicode(self.column_box.itemData(idx).toString())
        def fset(self, val):
            for idx in range(self.column_box.count()):
                c = unicode(self.column_box.itemData(idx).toString())
                if c == val:
                    self.column_box.setCurrentIndex(idx)
                    return
            raise ValueError('Column %r not found'%val)
        return property(fget=fget, fset=fset)

    @dynamic_property
    def current_action(self):
        def fget(self):
            idx = self.action_box.currentIndex()
            return unicode(self.action_box.itemData(idx).toString())
        def fset(self, val):
            for idx in range(self.action_box.count()):
                c = unicode(self.action_box.itemData(idx).toString())
                if c == val:
                    self.action_box.setCurrentIndex(idx)
                    return
            raise ValueError('Action %r not valid for current column'%val)
        return property(fget=fget, fset=fset)

    @property
    def current_val(self):
        ans = unicode(self.value_box.text()).strip()
        if self.current_col == 'languages':
            rmap = {lower(v):k for k, v in lang_map().iteritems()}
            ans = rmap.get(lower(ans), ans)
        return ans

    @dynamic_property
    def condition(self):

        def fget(self):
            c, a, v = (self.current_col, self.current_action,
                    self.current_val)
            if not c or not a:
                return None
            return (c, a, v)

        def fset(self, condition):
            c, a, v = condition
            if not v:
                v = ''
            v = v.strip()
            self.current_col = c
            self.current_action = a
            self.value_box.setText(v)

        return property(fget=fget, fset=fset)

    def init_action_box(self):
        self.action_box.blockSignals(True)
        self.action_box.clear()
        self.action_box.addItem('', '')
        col = self.current_col
        if col:
            m = self.fm[col]
            dt = m['datatype']
            if dt in self.action_map:
                actions = self.action_map[dt]
            else:
                if col == 'ondevice':
                    k = 'ondevice'
                elif col == 'identifiers':
                    k = 'identifiers'
                else:
                    k = 'multiple' if m['is_multiple'] else 'single'
                actions = self.action_map[k]

            for text, key in actions:
                self.action_box.addItem(text, key)
        self.action_box.setCurrentIndex(0)
        self.action_box.blockSignals(False)
        self.init_value_box()

    def init_value_box(self):
        self.value_box.setEnabled(True)
        self.value_box.setText('')
        self.value_box.setInputMask('')
        self.value_box.setValidator(None)
        col = self.current_col
        if not col:
            return
        m = self.fm[col]
        dt = m['datatype']
        action = self.current_action
        if not action:
            return
        m = self.fm[col]
        dt = m['datatype']
        tt = ''
        if col == 'identifiers':
            tt = _('Enter either an identifier type or an '
                    'identifier type and value of the form identifier:value')
        elif col == 'languages':
            tt = _('Enter a 3 letter ISO language code, like fra for French'
                    ' or deu for German or eng for English')
        elif dt in ('int', 'float', 'rating'):
            tt = _('Enter a number')
            v = QIntValidator if dt == 'int' else QDoubleValidator
            self.value_box.setValidator(v(self.value_box))
        elif dt == 'datetime':
            self.value_box.setInputMask('9999-99-99')
            tt = _('Enter a date in the format YYYY-MM-DD')
        else:
            tt = _('Enter a string.')
            if 'pattern' in action:
                tt = _('Enter a regular expression')
            elif m.get('is_multiple', False):
                tt += '\n' + _('You can match multiple values by separating'
                        ' them with %s')%m['is_multiple']['ui_to_list']
        self.value_box.setToolTip(tt)
        if action in ('is set', 'is not set', 'is true', 'is false',
                'is undefined'):
            self.value_box.setEnabled(False)
# }}}

class RuleEditor(QDialog): # {{{

    def __init__(self, fm, parent=None):
        QDialog.__init__(self, parent)
        self.fm = fm

        self.setWindowIcon(QIcon(I('format-fill-color.png')))
        self.setWindowTitle(_('Create/edit a column coloring rule'))

        self.l = l = QGridLayout(self)
        self.setLayout(l)

        self.l1 = l1 = QLabel(_('Create a coloring rule by'
            ' filling in the boxes below'))
        l.addWidget(l1, 0, 0, 1, 5)

        self.f1 = QFrame(self)
        self.f1.setFrameShape(QFrame.HLine)
        l.addWidget(self.f1, 1, 0, 1, 5)

        self.l2 = l2 = QLabel(_('Set the color of the column:'))
        l.addWidget(l2, 2, 0)

        self.column_box = QComboBox(self)
        l.addWidget(self.column_box, 2, 1)

        self.l3 = l3 = QLabel(_('to'))
        l.addWidget(l3, 2, 2)

        self.color_box = QComboBox(self)
        self.color_label = QLabel('Sample text Sample text')
        self.color_label.setTextFormat(Qt.RichText)
        l.addWidget(self.color_box, 2, 3)
        l.addWidget(self.color_label, 2, 4)
        l.addItem(QSpacerItem(10, 10, QSizePolicy.Expanding), 2, 5)

        self.l4 = l4 = QLabel(
            _('Only if the following conditions are all satisfied:'))
        l.addWidget(l4, 3, 0, 1, 6)

        self.scroll_area = sa = QScrollArea(self)
        sa.setMinimumHeight(300)
        sa.setMinimumWidth(950)
        sa.setWidgetResizable(True)
        l.addWidget(sa, 4, 0, 1, 6)

        self.add_button = b = QPushButton(QIcon(I('plus.png')),
                _('Add another condition'))
        l.addWidget(b, 5, 0, 1, 6)
        b.clicked.connect(self.add_blank_condition)

        self.l5 = l5 = QLabel(_('You can disable a condition by'
            ' blanking all of its boxes'))
        l.addWidget(l5, 6, 0, 1, 6)

        self.bb = bb = QDialogButtonBox(
                QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb, 7, 0, 1, 6)

        self.conditions_widget = QWidget(self)
        sa.setWidget(self.conditions_widget)
        self.conditions_widget.setLayout(QVBoxLayout())
        self.conditions_widget.layout().setAlignment(Qt.AlignTop)
        self.conditions = []

        for b in (self.column_box, self.color_box):
            b.setSizeAdjustPolicy(b.AdjustToMinimumContentsLengthWithIcon)
            b.setMinimumContentsLength(15)

        for key in sorted(
                displayable_columns(fm),
                key=sort_key):
            name = fm[key]['name']
            if name:
                self.column_box.addItem(key, key)
        self.column_box.setCurrentIndex(0)

        self.color_box.addItems(QColor.colorNames())
        self.color_box.setCurrentIndex(0)

        self.update_color_label()
        self.color_box.currentIndexChanged.connect(self.update_color_label)
        self.resize(self.sizeHint())

    def update_color_label(self):
        pal = QApplication.palette()
        bg1 = unicode(pal.color(pal.Base).name())
        bg2 = unicode(pal.color(pal.AlternateBase).name())
        c = unicode(self.color_box.currentText())
        self.color_label.setText('''
            <span style="color: {c}; background-color: {bg1}">&nbsp;{st}&nbsp;</span>
            <span style="color: {c}; background-color: {bg2}">&nbsp;{st}&nbsp;</span>
            '''.format(c=c, bg1=bg1, bg2=bg2, st=_('Sample Text')))


    def add_blank_condition(self):
        c = ConditionEditor(self.fm, parent=self.conditions_widget)
        self.conditions.append(c)
        self.conditions_widget.layout().addWidget(c)

    def apply_rule(self, col, rule):
        for i in range(self.column_box.count()):
            c = unicode(self.column_box.itemData(i).toString())
            if col == c:
                self.column_box.setCurrentIndex(i)
                break
        if rule.color:
            idx = self.color_box.findText(rule.color)
            if idx >= 0:
                self.color_box.setCurrentIndex(idx)
        for c in rule.conditions:
            ce = ConditionEditor(self.fm, parent=self.conditions_widget)
            self.conditions.append(ce)
            self.conditions_widget.layout().addWidget(ce)
            try:
                ce.condition = c
            except:
                import traceback
                traceback.print_exc()


    def accept(self):
        if self.validate():
            QDialog.accept(self)

    def validate(self):
        r = Rule(self.fm)
        for c in self.conditions:
            condition = c.condition
            if condition is not None:
                try:
                    r.add_condition(*condition)
                except Exception as e:
                    import traceback
                    error_dialog(self, _('Invalid condition'),
                            _('One of the conditions for this rule is'
                                ' invalid: <b>%s</b>')%e,
                            det_msg=traceback.format_exc(), show=True)
                    return False
        if len(r.conditions) < 1:
            error_dialog(self, _('No conditions'),
                    _('You must specify at least one non-empty condition'
                        ' for this rule'), show=True)
            return False
        return True

    @property
    def rule(self):
        r = Rule(self.fm)
        r.color = unicode(self.color_box.currentText())
        idx = self.column_box.currentIndex()
        col = unicode(self.column_box.itemData(idx).toString())
        for c in self.conditions:
            condition = c.condition
            if condition is not None:
                r.add_condition(*condition)

        return col, r
# }}}

class RulesModel(QAbstractListModel): # {{{

    def __init__(self, prefs, fm, parent=None):
        QAbstractListModel.__init__(self, parent)

        self.fm = fm
        rules = list(prefs['column_color_rules'])
        self.rules = []
        for col, template in rules:
            try:
                rule = rule_from_template(self.fm, template)
            except:
                rule = template
            self.rules.append((col, rule))

    def rowCount(self, *args):
        return len(self.rules)

    def data(self, index, role):
        row = index.row()
        try:
            col, rule = self.rules[row]
        except:
            return None

        if role == Qt.DisplayRole:
            return self.rule_to_html(col, rule)
        if role == Qt.UserRole:
            return (col, rule)

    def add_rule(self, col, rule):
        self.rules.append((col, rule))
        self.reset()
        return self.index(len(self.rules)-1)

    def replace_rule(self, index, col, r):
        self.rules[index.row()] = (col, r)
        self.dataChanged.emit(index, index)

    def remove_rule(self, index):
        self.rules.remove(self.rules[index.row()])
        self.reset()

    def commit(self, prefs):
        rules = []
        for col, r in self.rules:
            if isinstance(r, Rule):
                r = r.template
            if r is not None:
                rules.append((col, r))
        prefs['column_color_rules'] = rules

    def move(self, idx, delta):
        row = idx.row() + delta
        if row >= 0 and row < len(self.rules):
            t = self.rules[row]
            self.rules[row] = self.rules[row-delta]
            self.rules[row-delta] = t
            self.dataChanged.emit(idx, idx)
            idx = self.index(row)
            self.dataChanged.emit(idx, idx)
            return idx

    def clear(self):
        self.rules = []
        self.reset()

    def rule_to_html(self, col, rule):
        if not isinstance(rule, Rule):
            return _('''
            <p>Advanced Rule for column <b>%(col)s</b>:
            <pre>%(rule)s</pre>
            ''')%dict(col=col, rule=prepare_string_for_xml(rule))
        conditions = [self.condition_to_html(c) for c in rule.conditions]
        return _('''\
            <p>Set the color of <b>%(col)s</b> to <b>%(color)s</b> if the following
            conditions are met:</p>
            <ul>%(rule)s</ul>
            ''') % dict(col=col, color=rule.color, rule=''.join(conditions))

    def condition_to_html(self, condition):
        c, a, v = condition
        action_name = a
        for actions in ConditionEditor.ACTION_MAP.itervalues():
            for trans, ac in actions:
                if ac == a:
                    action_name = trans

        return (
            _('<li>If the <b>%(col)s</b> column <b>%(action)s</b> value: <b>%(val)s</b>') %
                dict(col=c, action=action_name, val=prepare_string_for_xml(v)))

# }}}

class EditRules(QWidget): # {{{

    changed = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        self.l = l = QGridLayout(self)
        self.setLayout(l)

        self.l1 = l1 = QLabel('<p>'+_(
            'You can control the color of columns in the'
            ' book list by creating "rules" that tell calibre'
            ' what color to use. Click the Add Rule button below'
            ' to get started.<p>You can <b>change an existing rule</b> by double'
            ' clicking it.'))
        l1.setWordWrap(True)
        l.addWidget(l1, 0, 0, 1, 2)

        self.add_button = QPushButton(QIcon(I('plus.png')), _('Add Rule'),
                self)
        self.remove_button = QPushButton(QIcon(I('minus.png')),
                _('Remove Rule'), self)
        self.add_button.clicked.connect(self.add_rule)
        self.remove_button.clicked.connect(self.remove_rule)
        l.addWidget(self.add_button, 1, 0)
        l.addWidget(self.remove_button, 1, 1)

        self.g = g = QGridLayout()
        self.rules_view = QListView(self)
        self.rules_view.doubleClicked.connect(self.edit_rule)
        self.rules_view.setSelectionMode(self.rules_view.SingleSelection)
        self.rules_view.setAlternatingRowColors(True)
        self.rtfd = RichTextDelegate(parent=self.rules_view, max_width=400)
        self.rules_view.setItemDelegate(self.rtfd)
        g.addWidget(self.rules_view, 0, 0, 2, 1)

        self.up_button = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-up.png')))
        b.setToolTip(_('Move the selected rule up'))
        b.clicked.connect(self.move_up)
        g.addWidget(b, 0, 1, 1, 1, Qt.AlignTop)
        self.down_button = b = QToolButton(self)
        b.setIcon(QIcon(I('arrow-down.png')))
        b.setToolTip(_('Move the selected rule down'))
        b.clicked.connect(self.move_down)
        g.addWidget(b, 1, 1, 1, 1, Qt.AlignBottom)

        l.addLayout(g, 2, 0, 1, 2)
        l.setRowStretch(2, 10)

        self.add_advanced_button = b = QPushButton(QIcon(I('plus.png')),
                _('Add Advanced Rule'), self)
        b.clicked.connect(self.add_advanced)
        l.addWidget(b, 3, 0, 1, 2)

    def initialize(self, fm, prefs, mi):
        self.model = RulesModel(prefs, fm)
        self.rules_view.setModel(self.model)
        self.fm = fm
        self.mi = mi

    def _add_rule(self, dlg):
        if dlg.exec_() == dlg.Accepted:
            col, r = dlg.rule
            if r and col:
                idx = self.model.add_rule(col, r)
                self.rules_view.scrollTo(idx)
                self.changed.emit()

    def add_rule(self):
            d = RuleEditor(self.model.fm)
            d.add_blank_condition()
            self._add_rule(d)

    def add_advanced(self):
        td = TemplateDialog(self, '', mi=self.mi, fm=self.fm, color_field='')
        self._add_rule(td)

    def edit_rule(self, index):
        try:
            col, rule = self.model.data(index, Qt.UserRole)
        except:
            return
        if isinstance(rule, Rule):
            d = RuleEditor(self.model.fm)
            d.apply_rule(col, rule)
        else:
            d = TemplateDialog(self, rule, mi=self.mi, fm=self.fm, color_field=col)
        if d.exec_() == d.Accepted:
            col, r = d.rule
            if r is not None and col:
                self.model.replace_rule(index, col, r)
                self.rules_view.scrollTo(index)
                self.changed.emit()

    def get_selected_row(self, txt):
        sm = self.rules_view.selectionModel()
        rows = list(sm.selectedRows())
        if not rows:
            error_dialog(self, _('No rule selected'),
                    _('No rule selected for %s.')%txt, show=True)
            return None
        return rows[0]

    def remove_rule(self):
        row = self.get_selected_row(_('removal'))
        if row is not None:
            self.model.remove_rule(row)
            self.changed.emit()

    def move_up(self):
        idx = self.rules_view.currentIndex()
        if idx.isValid():
            idx = self.model.move(idx, -1)
            if idx is not None:
                sm = self.rules_view.selectionModel()
                sm.select(idx, sm.ClearAndSelect)
                self.rules_view.setCurrentIndex(idx)
                self.changed.emit()

    def move_down(self):
        idx = self.rules_view.currentIndex()
        if idx.isValid():
            idx = self.model.move(idx, 1)
            if idx is not None:
                sm = self.rules_view.selectionModel()
                sm.select(idx, sm.ClearAndSelect)
                self.rules_view.setCurrentIndex(idx)
                self.changed.emit()

    def clear(self):
        self.model.clear()
        self.changed.emit()

    def commit(self, prefs):
        self.model.commit(prefs)

# }}}

if __name__ == '__main__':
    app = QApplication([])

    from calibre.library import db

    db = db()

    if True:
        d = RuleEditor(db.field_metadata)
        d.add_blank_condition()
        d.exec_()

        col, r = d.rule

        print ('Column to be colored:', col)
        print ('Template:')
        print (r.template)
    else:
        d = EditRules()
        d.resize(QSize(800, 600))
        d.initialize(db.field_metadata, db.prefs, None)
        d.show()
        app.exec_()
        d.commit(db.prefs)


