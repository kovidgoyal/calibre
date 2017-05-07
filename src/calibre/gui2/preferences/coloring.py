#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, textwrap, json
from functools import partial

from PyQt5.Qt import (QWidget, QDialog, QLabel, QGridLayout, QComboBox, QSize,
        QLineEdit, QIntValidator, QDoubleValidator, QFrame, Qt, QIcon, QHBoxLayout,
        QScrollArea, QPushButton, QVBoxLayout, QDialogButtonBox, QToolButton,
        QListView, QAbstractListModel, pyqtSignal, QSizePolicy, QSpacerItem,
        QApplication, QStandardItem, QStandardItemModel, QCheckBox, QMenu)

from calibre import prepare_string_for_xml, sanitize_file_name_unicode, as_unicode
from calibre.constants import config_dir
from calibre.utils.icu import sort_key
from calibre.gui2 import error_dialog, choose_files, pixmap_to_data, gprefs, choose_save_file
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.metadata.single_download import RichTextDelegate
from calibre.gui2.widgets2 import ColorButton
from calibre.library.coloring import (Rule, conditionable_columns,
    displayable_columns, rule_from_template, color_row_key)
from calibre.utils.localization import lang_map
from calibre.utils.icu import lower

all_columns_string = _('All Columns')

icon_rule_kinds = [(_('icon with text'), 'icon'),
                   (_('icon with no text'), 'icon_only'),
                   (_('composed icons w/text'), 'icon_composed'),
                   (_('composed icons w/no text'), 'icon_only_composed'),]


class ConditionEditor(QWidget):  # {{{

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
            'datetime' : (
                (_('is equal to'), 'eq'),
                (_('is less than'), 'lt'),
                (_('is greater than'), 'gt'),
                (_('is set'), 'is set'),
                (_('is not set'), 'is not set'),
                (_('is more days ago than'), 'older count days'),
                (_('is fewer days ago than'), 'count_days'),
                (_('is more days from now than'), 'newer future days'),
                (_('is fewer days from now than'), 'older future days')
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

    for x in ('float', 'rating'):
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
                key=lambda(key): sort_key(fm[key]['name'])):
            self.column_box.addItem(fm[key]['name'], key)
        self.column_box.setCurrentIndex(0)

        self.column_box.currentIndexChanged.connect(self.init_action_box)
        self.action_box.currentIndexChanged.connect(self.init_value_box)

        for b in (self.column_box, self.action_box):
            b.setSizeAdjustPolicy(b.AdjustToMinimumContentsLengthWithIcon)
            b.setMinimumContentsLength(20)

    @dynamic_property
    def current_col(self):
        def fget(self):
            idx = self.column_box.currentIndex()
            return unicode(self.column_box.itemData(idx) or '')

        def fset(self, val):
            for idx in range(self.column_box.count()):
                c = unicode(self.column_box.itemData(idx) or '')
                if c == val:
                    self.column_box.setCurrentIndex(idx)
                    return
            raise ValueError('Column %r not found'%val)
        return property(fget=fget, fset=fset)

    @dynamic_property
    def current_action(self):
        def fget(self):
            idx = self.action_box.currentIndex()
            return unicode(self.action_box.itemData(idx) or '')

        def fset(self, val):
            for idx in range(self.action_box.count()):
                c = unicode(self.action_box.itemData(idx) or '')
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
                    ' or deu for German or eng for English. You can also use'
                    ' the full language name, in which case calibre will try to'
                    ' automatically convert it to the language code.')
        elif dt in ('int', 'float', 'rating'):
            tt = _('Enter a number')
            v = QIntValidator if dt == 'int' else QDoubleValidator
            self.value_box.setValidator(v(self.value_box))
        elif dt == 'datetime':
            if action == 'count_days':
                self.value_box.setValidator(QIntValidator(self.value_box))
                tt = _('Enter the maximum days old the item can be. Zero is today. '
                       'Dates in the future always match')
            elif action == 'older count days':
                self.value_box.setValidator(QIntValidator(self.value_box))
                tt = _('Enter the minimum days old the item can be. Zero is today. '
                       'Dates in the future never match')
            elif action == 'older future days':
                self.value_box.setValidator(QIntValidator(self.value_box))
                tt = _('Enter the maximum days in the future the item can be. '
                       'Zero is today. Dates in the past always match')
            elif action == 'newer future days':
                self.value_box.setValidator(QIntValidator(self.value_box))
                tt = _('Enter the minimum days in the future the item can be. '
                       'Zero is today. Dates in the past never match')
            else:
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


class RuleEditor(QDialog):  # {{{

    @property
    def doing_multiple(self):
        return hasattr(self, 'multiple_icon_cb') and self.multiple_icon_cb.isChecked()

    def __init__(self, fm, pref_name, parent=None):
        QDialog.__init__(self, parent)
        self.fm = fm

        if pref_name == 'column_color_rules':
            self.rule_kind = 'color'
            rule_text = _('column coloring')
        elif pref_name == 'column_icon_rules':
            self.rule_kind = 'icon'
            rule_text = _('column icon')
        elif pref_name == 'cover_grid_icon_rules':
            self.rule_kind = 'emblem'
            rule_text = _('Cover grid emblem')

        self.setWindowIcon(QIcon(I('format-fill-color.png')))
        self.setWindowTitle(_('Create/edit a {0} rule').format(rule_text))

        self.l = l = QGridLayout(self)
        self.setLayout(l)

        self.l1 = l1 = QLabel(_('Create a {0} rule by'
            ' filling in the boxes below').format(rule_text))
        l.addWidget(l1, 0, 0, 1, 8)

        self.f1 = QFrame(self)
        self.f1.setFrameShape(QFrame.HLine)
        l.addWidget(self.f1, 1, 0, 1, 8)

        self.l2 = l2 = QLabel(_('Add the emblem:') if self.rule_kind == 'emblem' else _('Set the'))
        l.addWidget(l2, 2, 0)

        if self.rule_kind == 'color':
            l.addWidget(QLabel(_('color')))
        elif self.rule_kind == 'icon':
            self.kind_box = QComboBox(self)
            for tt, t in icon_rule_kinds:
                self.kind_box.addItem(tt, t)
            l.addWidget(self.kind_box, 2, 1)
            self.kind_box.setToolTip(textwrap.fill(_(
                'If you choose composed icons and multiple rules match, then all the'
                ' matching icons will be combined, otherwise the icon from the'
                ' first rule to match will be used.')))
        else:
            pass

        self.l3 = l3 = QLabel(_('of the column:'))
        l.addWidget(l3, 2, 2)

        self.column_box = QComboBox(self)
        l.addWidget(self.column_box, 2, 3)

        self.l4 = l4 = QLabel(_('to'))
        l.addWidget(l4, 2, 4)
        if self.rule_kind == 'emblem':
            l3.setVisible(False), self.column_box.setVisible(False), l4.setVisible(False)

        def create_filename_box():
            self.filename_box = f = QComboBox()
            self.filenamebox_view = v = QListView()
            v.setIconSize(QSize(32, 32))
            self.filename_box.setView(v)
            self.orig_filenamebox_view = f.view()
            f.setMinimumContentsLength(20), f.setSizeAdjustPolicy(f.AdjustToMinimumContentsLengthWithIcon)
            self.populate_icon_filenames()

        if self.rule_kind == 'color':
            self.color_box = ColorButton(parent=self)
            self.color_label = QLabel('Sample text Sample text')
            self.color_label.setTextFormat(Qt.RichText)
            l.addWidget(self.color_box, 2, 5)
            l.addWidget(self.color_label, 2, 6)
            l.addItem(QSpacerItem(10, 10, QSizePolicy.Expanding), 2, 7)
        elif self.rule_kind == 'emblem':
            create_filename_box()
            self.update_filename_box()
            self.filename_button = QPushButton(QIcon(I('document_open.png')),
                                               _('&Add new image'))
            l.addWidget(self.filename_box)
            l.addWidget(self.filename_button, 2, 6)
            l.addWidget(QLabel(_('(Images should be square-ish)')), 2, 7)
            l.setColumnStretch(7, 10)
        else:
            create_filename_box()

            vb = QVBoxLayout()
            self.multiple_icon_cb = QCheckBox(_('Choose more than one icon'))
            vb.addWidget(self.multiple_icon_cb)
            self.update_filename_box()
            self.multiple_icon_cb.clicked.connect(self.multiple_box_clicked)
            vb.addWidget(self.filename_box)
            l.addLayout(vb, 2, 5)

            self.filename_button = QPushButton(QIcon(I('document_open.png')),
                                               _('&Add icon'))
            l.addWidget(self.filename_button, 2, 6)
            l.addWidget(QLabel(_('Icons should be square or landscape')), 2, 7)
            l.setColumnStretch(7, 10)

        self.l5 = l5 = QLabel(
            _('Only if the following conditions are all satisfied:'))
        l.addWidget(l5, 3, 0, 1, 7)

        self.scroll_area = sa = QScrollArea(self)
        sa.setMinimumHeight(300)
        sa.setMinimumWidth(950)
        sa.setWidgetResizable(True)
        l.addWidget(sa, 4, 0, 1, 8)

        self.add_button = b = QPushButton(QIcon(I('plus.png')),
                _('Add another condition'))
        l.addWidget(b, 5, 0, 1, 8)
        b.clicked.connect(self.add_blank_condition)

        self.l6 = l6 = QLabel(_('You can disable a condition by'
            ' blanking all of its boxes'))
        l.addWidget(l6, 6, 0, 1, 8)

        self.bb = bb = QDialogButtonBox(
                QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb, 7, 0, 1, 8)
        if self.rule_kind != 'color':
            self.remove_button = b = bb.addButton(_('Remove image'), bb.ActionRole)
            b.setIcon(QIcon(I('minus.png')))
            b.setMenu(QMenu())
            self.update_remove_button()

        self.conditions_widget = QWidget(self)
        sa.setWidget(self.conditions_widget)
        self.conditions_widget.setLayout(QVBoxLayout())
        self.conditions_widget.layout().setAlignment(Qt.AlignTop)
        self.conditions = []

        if self.rule_kind == 'color':
            for b in (self.column_box, ):
                b.setSizeAdjustPolicy(b.AdjustToMinimumContentsLengthWithIcon)
                b.setMinimumContentsLength(15)

        for key in sorted(displayable_columns(fm),
                          key=lambda(k): sort_key(fm[k]['name']) if k != color_row_key else 0):
            if key == color_row_key and self.rule_kind != 'color':
                continue
            name = all_columns_string if key == color_row_key else fm[key]['name']
            if name:
                self.column_box.addItem(name, key)
        self.column_box.setCurrentIndex(0)

        if self.rule_kind == 'color':
            self.color_box.color = '#000'
            self.update_color_label()
            self.color_box.color_changed.connect(self.update_color_label)
        else:
            self.rule_icon_files = []
            self.filename_button.clicked.connect(self.filename_button_clicked)

        self.resize(self.sizeHint())

    def multiple_box_clicked(self):
        self.update_filename_box()
        self.update_icon_filenames_in_box()

    @property
    def icon_folder(self):
        return os.path.join(config_dir, 'cc_icons')

    def populate_icon_filenames(self):
        d = self.icon_folder
        self.icon_file_names = []
        if os.path.exists(d):
            for icon_file in os.listdir(d):
                icon_file = lower(icon_file)
                if os.path.exists(os.path.join(d, icon_file)) and icon_file.endswith('.png'):
                    self.icon_file_names.append(icon_file)
        self.icon_file_names.sort(key=sort_key)

    def update_filename_box(self):
        doing_multiple = self.doing_multiple

        model = QStandardItemModel()
        self.filename_box.setModel(model)
        self.icon_file_names.sort(key=sort_key)
        if doing_multiple:
            item = QStandardItem(_('Open to see checkboxes'))
            item.setIcon(QIcon(I('blank.png')))
        else:
            item = QStandardItem('')
        item.setFlags(Qt.ItemFlag(0))
        model.appendRow(item)

        for i,filename in enumerate(self.icon_file_names):
            item = QStandardItem(filename)
            if doing_multiple:
                item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                item.setData(Qt.Unchecked, Qt.CheckStateRole)
            else:
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            icon = QIcon(os.path.join(self.icon_folder, filename))
            item.setIcon(icon)
            model.appendRow(item)

    def update_color_label(self):
        pal = QApplication.palette()
        bg1 = unicode(pal.color(pal.Base).name())
        bg2 = unicode(pal.color(pal.AlternateBase).name())
        c = self.color_box.color
        self.color_label.setText('''
            <span style="color: {c}; background-color: {bg1}">&nbsp;{st}&nbsp;</span>
            <span style="color: {c}; background-color: {bg2}">&nbsp;{st}&nbsp;</span>
            '''.format(c=c, bg1=bg1, bg2=bg2, st=_('Sample text')))

    def sanitize_icon_file_name(self, icon_path):
        n = lower(sanitize_file_name_unicode(
                             os.path.splitext(
                                   os.path.basename(icon_path))[0]+'.png'))
        return n.replace("'", '_')

    def filename_button_clicked(self):
        try:
            path = choose_files(self, 'choose_category_icon',
                        _('Select Icon'), filters=[
                        (_('Images'), ['png', 'gif', 'jpg', 'jpeg'])],
                    all_files=False, select_only_single_file=True)
            if path:
                icon_path = path[0]
                icon_name = self.sanitize_icon_file_name(icon_path)
                if icon_name not in self.icon_file_names:
                    self.icon_file_names.append(icon_name)
                    try:
                        p = QIcon(icon_path).pixmap(QSize(128, 128))
                        d = self.icon_folder
                        if not os.path.exists(os.path.join(d, icon_name)):
                            if not os.path.exists(d):
                                os.makedirs(d)
                            with open(os.path.join(d, icon_name), 'wb') as f:
                                f.write(pixmap_to_data(p, format='PNG'))
                    except:
                        import traceback
                        traceback.print_exc()
                    self.update_filename_box()
                    self.update_remove_button()
                if self.doing_multiple:
                    if icon_name not in self.rule_icon_files:
                        self.rule_icon_files.append(icon_name)
                    self.update_icon_filenames_in_box()
                else:
                    self.filename_box.setCurrentIndex(self.filename_box.findText(icon_name))
                self.filename_box.adjustSize()
        except:
            import traceback
            traceback.print_exc()
        return

    def get_filenames_from_box(self):
        if self.doing_multiple:
            model = self.filename_box.model()
            fnames = []
            for i in range(1, model.rowCount()):
                item = model.item(i, 0)
                if item.checkState() == Qt.Checked:
                    fnames.append(lower(unicode(item.text())))
            fname = ' : '.join(fnames)
        else:
            fname = lower(unicode(self.filename_box.currentText()))
        return fname

    def update_icon_filenames_in_box(self):
        if self.rule_icon_files:
            if not self.doing_multiple:
                idx = self.filename_box.findText(self.rule_icon_files[0])
                if idx >= 0:
                    self.filename_box.setCurrentIndex(idx)
                else:
                    self.filename_box.setCurrentIndex(0)
            else:
                model = self.filename_box.model()
                for icon in self.rule_icon_files:
                    idx = self.filename_box.findText(icon)
                    if idx >= 0:
                        item = model.item(idx)
                        item.setCheckState(Qt.Checked)

    def update_remove_button(self):
        m = self.remove_button.menu()
        m.clear()
        for name in self.icon_file_names:
            m.addAction(QIcon(os.path.join(self.icon_folder, name)), name).triggered.connect(partial(
                self.remove_image, name))

    def remove_image(self, name):
        try:
            os.remove(os.path.join(self.icon_folder, name))
        except EnvironmentError:
            pass
        else:
            self.populate_icon_filenames()
            self.update_remove_button()
            self.update_filename_box()
            self.update_icon_filenames_in_box()

    def add_blank_condition(self):
        c = ConditionEditor(self.fm, parent=self.conditions_widget)
        self.conditions.append(c)
        self.conditions_widget.layout().addWidget(c)

    def apply_rule(self, kind, col, rule):
        if kind == 'color':
            if rule.color:
                self.color_box.color = rule.color
        else:
            if self.rule_kind == 'icon':
                for i, tup in enumerate(icon_rule_kinds):
                    if kind == tup[1]:
                        self.kind_box.setCurrentIndex(i)
                        break
            self.rule_icon_files = [ic.strip() for ic in rule.color.split(':')]
            if len(self.rule_icon_files) > 1:
                self.multiple_icon_cb.setChecked(True)
            self.update_filename_box()
            self.update_icon_filenames_in_box()

        for i in range(self.column_box.count()):
            c = unicode(self.column_box.itemData(i) or '')
            if col == c:
                self.column_box.setCurrentIndex(i)
                break

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
        if self.rule_kind != 'color':
            fname = self.get_filenames_from_box()
            if not fname:
                error_dialog(self, _('No icon selected'),
                        _('You must choose an icon for this rule'), show=True)
                return
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
        if self.rule_kind != 'color':
            r.color = self.get_filenames_from_box()
        else:
            r.color = self.color_box.color
        idx = self.column_box.currentIndex()
        col = unicode(self.column_box.itemData(idx) or '')
        for c in self.conditions:
            condition = c.condition
            if condition is not None:
                r.add_condition(*condition)
        if self.rule_kind == 'icon':
            kind = unicode(self.kind_box.itemData(
                                    self.kind_box.currentIndex()) or '')
        else:
            kind = self.rule_kind

        return kind, col, r
# }}}


class RulesModel(QAbstractListModel):  # {{{

    EXIM_VERSION = 1

    def load_rule(self, col, template):
        if col not in self.fm and col != color_row_key:
            return
        try:
            rule = rule_from_template(self.fm, template)
        except:
            rule = template
        return rule

    def __init__(self, prefs, fm, pref_name, parent=None):
        QAbstractListModel.__init__(self, parent)

        self.fm = fm
        self.pref_name = pref_name
        if pref_name == 'column_color_rules':
            self.rule_kind = 'color'
            rules = list(prefs[pref_name])
            self.rules = []
            for col, template in rules:
                rule = self.load_rule(col, template)
                if rule is not None:
                    self.rules.append(('color', col, rule))
        else:
            self.rule_kind = 'icon' if pref_name == 'column_icon_rules' else 'emblem'
            rules = list(prefs[pref_name])
            self.rules = []
            for kind, col, template in rules:
                rule = self.load_rule(col, template)
                if rule is not None:
                    self.rules.append((kind, col, rule))

    def rowCount(self, *args):
        return len(self.rules)

    def data(self, index, role):
        row = index.row()
        try:
            kind, col, rule = self.rules[row]
        except:
            return None
        if role == Qt.DisplayRole:
            if col == color_row_key:
                col = all_columns_string
            else:
                col = self.fm[col]['name']
            return self.rule_to_html(kind, col, rule)
        if role == Qt.UserRole:
            return (kind, col, rule)

    def add_rule(self, kind, col, rule):
        self.beginResetModel()
        self.rules.append((kind, col, rule))
        self.endResetModel()
        return self.index(len(self.rules)-1)

    def replace_rule(self, index, kind, col, r):
        self.rules[index.row()] = (kind, col, r)
        self.dataChanged.emit(index, index)

    def remove_rule(self, index):
        self.beginResetModel()
        self.rules.remove(self.rules[index.row()])
        self.endResetModel()

    def rules_as_list(self, for_export=False):
        rules = []
        for kind, col, r in self.rules:
            if isinstance(r, Rule):
                r = r.template
            if r is not None:
                if not for_export and kind == 'color':
                    rules.append((col, r))
                else:
                    rules.append((kind, col, r))
        return rules

    def import_rules(self, rules):
        self.beginResetModel()
        for kind, col, template in rules:
            if self.pref_name == 'column_color_rules':
                kind = 'color'
            rule = self.load_rule(col, template)
            if rule is not None:
                self.rules.append((kind, col, rule))
        self.endResetModel()

    def commit(self, prefs):
        prefs[self.pref_name] = self.rules_as_list()

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
        self.beginResetModel()
        self.endResetModel()

    def rule_to_html(self, kind, col, rule):
        trans_kind = 'not found'
        if kind == 'color':
            trans_kind = _('color')
        else:
            for tt, t in icon_rule_kinds:
                if kind == t:
                    trans_kind = tt
                    break

        if not isinstance(rule, Rule):
            if kind == 'color':
                return _('''
                <p>Advanced rule for column <b>%(col)s</b>:
                <pre>%(rule)s</pre>
                ''')%dict(col=col, rule=prepare_string_for_xml(rule))
            elif self.rule_kind == 'emblem':
                return _('''
                <p>Advanced rule:
                <pre>%(rule)s</pre>
                ''')%dict(rule=prepare_string_for_xml(rule))
            else:
                return _('''
                <p>Advanced rule: set <b>%(typ)s</b> for column <b>%(col)s</b>:
                <pre>%(rule)s</pre>
                ''')%dict(col=col,
                          typ=trans_kind,
                          rule=prepare_string_for_xml(rule))

        conditions = [self.condition_to_html(c) for c in rule.conditions]

        sample = '' if kind != 'color' else (
                     _('(<span style="color: %s;">sample</span>)') % rule.color)

        if kind == 'emblem':
            return _('<p>Add the emblem <b>{0}</b> to the cover if the following conditions are met:</p>'
                    '\n<ul>{1}</ul>').format(rule.color, ''.join(conditions))
        return _('''\
            <p>Set the <b>%(kind)s</b> of <b>%(col)s</b> to <b>%(color)s</b> %(sample)s
            if the following conditions are met:</p>
            <ul>%(rule)s</ul>
            ''') % dict(kind=trans_kind, col=col, color=rule.color,
                        sample=sample, rule=''.join(conditions))

    def condition_to_html(self, condition):
        col, a, v = condition
        dt = self.fm[col]['datatype']
        c = self.fm[col]['name']
        action_name = a
        if col in ConditionEditor.ACTION_MAP:
            # look for a column-name-specific label
            for trans, ac in ConditionEditor.ACTION_MAP[col]:
                if ac == a:
                    action_name = trans
                    break
        elif dt in ConditionEditor.ACTION_MAP:
            # Look for a type-specific label
            for trans, ac in ConditionEditor.ACTION_MAP[dt]:
                if ac == a:
                    action_name = trans
                    break
        else:
            # Wasn't a type-specific or column-specific label. Look for a text-type
            for dt in ['single', 'multiple']:
                for trans, ac in ConditionEditor.ACTION_MAP[dt]:
                    if ac == a:
                        action_name = trans
                        break
                else:
                    continue
                break
        if action_name == Rule.INVALID_CONDITION:
            return (
                _('<li>The condition using column <b>%(col)s</b> is <b>invalid</b>')
                % dict(col=c))
        return (
            _('<li>If the <b>%(col)s</b> column <b>%(action)s</b> value: <b>%(val)s</b>') % dict(
                col=c, action=action_name, val=prepare_string_for_xml(v)))

# }}}


class EditRules(QWidget):  # {{{

    changed = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        self.l = l = QGridLayout(self)
        self.setLayout(l)

        self.enabled = c = QCheckBox(self)
        l.addWidget(c, l.rowCount(), 0, 1, 2)
        c.setVisible(False)
        c.stateChanged.connect(self.changed)

        self.l1 = l1 = QLabel('')
        l1.setWordWrap(True)
        l.addWidget(l1, l.rowCount(), 0, 1, 2)

        self.add_button = QPushButton(QIcon(I('plus.png')), _('&Add rule'),
                self)
        self.remove_button = QPushButton(QIcon(I('minus.png')),
                _('&Remove rule(s)'), self)
        self.add_button.clicked.connect(self.add_rule)
        self.remove_button.clicked.connect(self.remove_rule)
        l.addWidget(self.add_button, l.rowCount(), 0)
        l.addWidget(self.remove_button, l.rowCount() - 1, 1)

        self.g = g = QGridLayout()
        self.rules_view = QListView(self)
        self.rules_view.doubleClicked.connect(self.edit_rule)
        self.rules_view.setSelectionMode(self.rules_view.ExtendedSelection)
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

        l.addLayout(g, l.rowCount(), 0, 1, 2)
        l.setRowStretch(l.rowCount() - 1, 10)

        self.add_advanced_button = b = QPushButton(QIcon(I('plus.png')),
                _('Add advanced rule'), self)
        b.clicked.connect(self.add_advanced)
        self.hb = hb = QHBoxLayout()
        l.addLayout(hb, l.rowCount(), 0, 1, 2)
        hb.addWidget(b)
        hb.addStretch(10)
        self.export_button = b = QPushButton(_('E&xport'), self)
        b.clicked.connect(self.export_rules)
        b.setToolTip(_('Export these rules to a file'))
        hb.addWidget(b)
        self.import_button = b = QPushButton(_('&Import'), self)
        b.setToolTip(_('Import rules from a file'))
        b.clicked.connect(self.import_rules)
        hb.addWidget(b)

    def initialize(self, fm, prefs, mi, pref_name):
        self.pref_name = pref_name
        self.model = RulesModel(prefs, fm, self.pref_name)
        self.rules_view.setModel(self.model)
        self.fm = fm
        self.mi = mi
        if pref_name == 'column_color_rules':
            text = _(
                'You can control the color of columns in the'
                ' book list by creating "rules" that tell calibre'
                ' what color to use. Click the "Add rule" button below'
                ' to get started.<p>You can <b>change an existing rule</b> by'
                ' double clicking it.')
        elif pref_name == 'column_icon_rules':
            text = _(
                'You can add icons to columns in the'
                ' book list by creating "rules" that tell calibre'
                ' what icon to use. Click the "Add rule" button below'
                ' to get started.<p>You can <b>change an existing rule</b> by'
                ' double clicking it.')
        elif pref_name == 'cover_grid_icon_rules':
            text = _('You can add emblems (small icons) that are displayed on the side of covers'
                     ' in the Cover grid by creating "rules" that tell calibre'
                ' what image to use. Click the "Add rule" button below'
                ' to get started.<p>You can <b>change an existing rule</b> by'
                ' double clicking it.')
            self.enabled.setVisible(True)
            self.enabled.setChecked(gprefs['show_emblems'])
            self.enabled.setText(_('Show &emblems next to the covers'))
            self.enabled.stateChanged.connect(self.enabled_toggled)
            self.enabled.setToolTip(_(
                'If checked, you can tell calibre to display icons of your choosing'
                ' next to the covers shown in the Cover grid, controlled by the'
                ' metadata of the book.'))
            self.enabled_toggled()
        self.l1.setText('<p>'+ text)

    def enabled_toggled(self):
        enabled = self.enabled.isChecked()
        for x in ('add_advanced_button', 'rules_view', 'up_button', 'down_button', 'add_button', 'remove_button'):
            getattr(self, x).setEnabled(enabled)

    def add_rule(self):
        d = RuleEditor(self.model.fm, self.pref_name)
        d.add_blank_condition()
        if d.exec_() == d.Accepted:
            kind, col, r = d.rule
            if kind and r and col:
                idx = self.model.add_rule(kind, col, r)
                self.rules_view.scrollTo(idx)
                self.changed.emit()

    def add_advanced(self):
        if self.pref_name == 'column_color_rules':
            td = TemplateDialog(self, '', mi=self.mi, fm=self.fm, color_field='')
            if td.exec_() == td.Accepted:
                col, r = td.rule
                if r and col:
                    idx = self.model.add_rule('color', col, r)
                    self.rules_view.scrollTo(idx)
                    self.changed.emit()
        else:
            if self.pref_name == 'cover_grid_icon_rules':
                td = TemplateDialog(self, '', mi=self.mi, fm=self.fm, doing_emblem=True)
            else:
                td = TemplateDialog(self, '', mi=self.mi, fm=self.fm, icon_field_key='')
            if td.exec_() == td.Accepted:
                typ, col, r = td.rule
                if typ and r and col:
                    idx = self.model.add_rule(typ, col, r)
                    self.rules_view.scrollTo(idx)
                    self.changed.emit()

    def edit_rule(self, index):
        try:
            kind, col, rule = self.model.data(index, Qt.UserRole)
        except:
            return
        if isinstance(rule, Rule):
            d = RuleEditor(self.model.fm, self.pref_name)
            d.apply_rule(kind, col, rule)
        elif self.pref_name == 'column_color_rules':
            d = TemplateDialog(self, rule, mi=self.mi, fm=self.fm, color_field=col)
        elif self.pref_name == 'cover_grid_icon_rules':
            d = TemplateDialog(self, rule, mi=self.mi, fm=self.fm, doing_emblem=True)
        else:
            d = TemplateDialog(self, rule, mi=self.mi, fm=self.fm, icon_field_key=col,
                               icon_rule_kind=kind)

        if d.exec_() == d.Accepted:
            if len(d.rule) == 2:  # Convert template dialog rules to a triple
                d.rule = ('color', d.rule[0], d.rule[1])
            kind, col, r = d.rule
            if kind and r is not None and col:
                self.model.replace_rule(index, kind, col, r)
                self.rules_view.scrollTo(index)
                self.changed.emit()

    def get_selected_row(self, txt):
        sm = self.rules_view.selectionModel()
        rows = list(sm.selectedRows())
        if not rows:
            error_dialog(self, _('No rule selected'),
                    _('No rule selected for %s.')%txt, show=True)
            return None
        return sorted(rows, reverse=True)

    def remove_rule(self):
        rows = self.get_selected_row(_('removal'))
        if rows is not None:
            for row in rows:
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
        if self.pref_name == 'cover_grid_icon_rules':
            gprefs['show_emblems'] = self.enabled.isChecked()

    def export_rules(self):
        path = choose_save_file(self, 'export-coloring-rules', _('Choose file to export to'),
                                filters=[(_('Rules'), ['rules'])], all_files=False, initial_filename=self.pref_name + '.rules')
        if path:
            rules = {
                'version': self.model.EXIM_VERSION,
                'type': self.model.pref_name,
                'rules': self.model.rules_as_list(for_export=True)
            }
            with lopen(path, 'wb') as f:
                f.write(json.dumps(rules, indent=2))

    def import_rules(self):
        files = choose_files(self, 'import-coloring-rules', _('Choose file to import from'),
                                filters=[(_('Rules'), ['rules'])], all_files=False, select_only_single_file=True)
        if files:
            with lopen(files[0], 'rb') as f:
                raw = f.read()
            try:
                rules = json.loads(raw)
                if rules['version'] != self.model.EXIM_VERSION:
                    raise ValueError('Unsupported rules version: {}'.format(rules['version']))
                if rules['type'] != self.pref_name:
                    raise ValueError('Rules are not of the correct type')
                rules = list(rules['rules'])
            except Exception as e:
                return error_dialog(self, _('No valid rules found'), _(
                    'No valid rules were found in {}.').format(files[0]), det_msg=as_unicode(e), show=True)
            self.model.import_rules(rules)
            self.changed.emit()
# }}}


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])

    from calibre.library import db

    db = db()

    if False:
        d = RuleEditor(db.field_metadata, 'column_icon_rules')
        d.add_blank_condition()
        d.exec_()

        kind, col, r = d.rule

        print ('Column to be colored:', col)
        print ('Template:')
        print (r.template)
    else:
        d = EditRules()
        d.resize(QSize(800, 600))
        d.initialize(db.field_metadata, db.prefs, None, 'column_color_rules')
        d.show()
        app.exec_()
        d.commit(db.prefs)
