#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import json
import os
import textwrap
from functools import partial
from qt.core import (
    QAbstractItemView, QAbstractListModel, QApplication, QCheckBox, QComboBox,
    QDialog, QDialogButtonBox, QDoubleValidator, QFrame, QGridLayout, QIcon,
    QIntValidator, QItemSelectionModel, QLabel, QLineEdit, QListView,
    QPalette, QPushButton, QScrollArea, QSize, QSizePolicy, QSpacerItem,
    QStandardItem, QStandardItemModel, Qt, QToolButton, QVBoxLayout, QWidget,
    QItemSelection, QListWidget, QListWidgetItem, pyqtSignal
)

from calibre import as_unicode, prepare_string_for_xml, sanitize_file_name
from calibre.constants import config_dir
from calibre.gui2 import (
    choose_files, choose_save_file, error_dialog, gprefs, open_local_file,
    pixmap_to_data, question_dialog
)
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.metadata.single_download import RichTextDelegate
from calibre.gui2.widgets2 import ColorButton, FlowLayout, Separator
from calibre.library.coloring import (
    Rule, color_row_key, conditionable_columns, displayable_columns,
    rule_from_template
)
from calibre.utils.icu import lower, sort_key
from calibre.utils.localization import lang_map
from polyglot.builtins import iteritems

all_columns_string = _('All columns')

icon_rule_kinds = [(_('icon with text'), 'icon'),
                   (_('icon with no text'), 'icon_only'),
                   (_('composed icons w/text'), 'icon_composed'),
                   (_('composed icons w/no text'), 'icon_only_composed'),]


class ConditionEditor(QWidget):  # {{{

    ACTION_MAP = {
            'bool2' : (
                    (_('is true'), 'is true',),
                    (_('is false'), 'is not true'),
            ),
            'bool' : (
                    (_('is true'), 'is true',),
                    (_('is not true'), 'is not true'),
                    (_('is false'), 'is false'),
                    (_('is not false'), 'is not false'),
                    (_('is undefined'), 'is undefined'),
                    (_('is defined'), 'is defined'),
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
                (_('is greater than'), 'gt'),
                (_('is set'), 'is set'),
                (_('is not set'), 'is not set')
            ),
            'datetime' : (
                (_('is equal to'), 'eq'),
                (_('is earlier than'), 'lt'),
                (_('is later than'), 'gt'),
                (_('is today'), 'is today'),
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
            'multiple_no_isset' : (
                (_('has'), 'has'),
                (_('does not have'), 'does not have'),
                (_('has pattern'), 'has pattern'),
                (_('does not have pattern'), 'does not have pattern'),
            ),
            'single'   : (
                (_('is'), 'is'),
                (_('is not'), 'is not'),
                (_('contains'), 'contains'),
                (_('does not contain'), 'does not contain'),
                (_('matches pattern'), 'matches pattern'),
                (_('does not match pattern'), 'does not match pattern'),
                (_('is set'), 'is set'),
                (_('is not set'), 'is not set'),
            ),
            'single_no_isset'   : (
                (_('is'), 'is'),
                (_('is not'), 'is not'),
                (_('contains'), 'contains'),
                (_('does not contain'), 'does not contain'),
                (_('matches pattern'), 'matches pattern'),
                (_('does not match pattern'), 'does not match pattern'),
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

        texts = _('If the ___ column ___ value')
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
                key=lambda key: sort_key(fm[key]['name'])):
            self.column_box.addItem('{} ({})'.format(fm[key]['name'], key), key)
        self.column_box.setCurrentIndex(0)

        self.column_box.currentIndexChanged.connect(self.init_action_box)
        self.action_box.currentIndexChanged.connect(self.init_value_box)

        for b in (self.column_box, self.action_box):
            b.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            b.setMinimumContentsLength(20)

    @property
    def current_col(self):
        idx = self.column_box.currentIndex()
        return str(self.column_box.itemData(idx) or '')

    @current_col.setter
    def current_col(self, val):
        for idx in range(self.column_box.count()):
            c = str(self.column_box.itemData(idx) or '')
            if c == val:
                self.column_box.setCurrentIndex(idx)
                return
        raise ValueError('Column %r not found'%val)

    @property
    def current_action(self):
        idx = self.action_box.currentIndex()
        return str(self.action_box.itemData(idx) or '')

    @current_action.setter
    def current_action(self, val):
        for idx in range(self.action_box.count()):
            c = str(self.action_box.itemData(idx) or '')
            if c == val:
                self.action_box.setCurrentIndex(idx)
                return
        raise ValueError('Action %r not valid for current column'%val)

    @property
    def current_val(self):
        ans = str(self.value_box.text()).strip()
        if not self.value_box.isEnabled():
            ans = ''
        if self.current_col == 'languages':
            rmap = {lower(v):k for k, v in iteritems(lang_map())}
            ans = rmap.get(lower(ans), ans)
        return ans

    @property
    def condition(self):

        c, a, v = (self.current_col, self.current_action,
                self.current_val)
        if not c or not a:
            return None
        return (c, a, v)

    @condition.setter
    def condition(self, condition):
        c, a, v = condition
        if not v:
            v = ''
        v = v.strip()
        self.current_col = c
        self.current_action = a
        self.value_box.setText(v)

    def init_action_box(self):
        self.action_box.blockSignals(True)
        self.action_box.clear()
        self.action_box.addItem('', '')
        col = self.current_col
        if col:
            m = self.fm[col]
            dt = m['datatype']
            if dt == 'bool':
                from calibre.gui2.ui import get_gui
                if not get_gui().current_db.new_api.pref('bools_are_tristate'):
                    dt = 'bool2'
            if dt in self.action_map:
                actions = self.action_map[dt]
            else:
                if col == 'ondevice':
                    k = 'ondevice'
                elif col == 'identifiers':
                    k = 'identifiers'
                elif col == 'authors':
                    k = 'multiple_no_isset'
                elif col == 'title':
                    k = 'single_no_isset'
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
        if action in ('is set', 'is not set', 'is true', 'is false', 'is undefined', 'is today'):
            self.value_box.setEnabled(False)
# }}}


class RemoveIconFileDialog(QDialog):  # {{{
    def __init__(self, parent, icon_file_names, icon_folder):
        self.files_to_remove = []
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Remove icons'))
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowType.WindowContextHelpButtonHint))
        l = QVBoxLayout(self)
        t = QLabel('<p>' + _('Select the icons you wish to remove. The icon files will be '
                             'removed when you press OK. There is no undo.') + '</p>')
        t.setWordWrap(True)
        t.setTextFormat(Qt.TextFormat.RichText)
        l.addWidget(t)
        self.listbox = lw = QListWidget(parent)
        lw.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        for fn in icon_file_names:
            item = QListWidgetItem(fn)
            item.setIcon(QIcon(os.path.join(icon_folder, fn)))
            lw.addItem(item)
        l.addWidget(lw)
        self.bb = bb = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb)

    def sizeHint(self):
        return QSize(700, 600)

    def accept(self):
        self.files_to_remove = [item.text() for item in self.listbox.selectedItems()]
        if not self.files_to_remove:
            return error_dialog(self, _('No icons selected'), _(
                'You must select at least one icon to remove'), show=True)
        if question_dialog(self,
            _('Remove icons'),
            ngettext('One icon will be removed.', '{} icons will be removed.', len(self.files_to_remove)
                        ).format(len(self.files_to_remove)) + ' ' + _('This will prevent any rules that use this icon from working. Are you sure?'),
            yes_text=_('Yes'),
            no_text=_('No'),
            det_msg='\n'.join(self.files_to_remove),
            skip_dialog_name='remove_icon_confirmation_dialog'
        ):
            QDialog.accept(self)
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

        self.setWindowIcon(QIcon.ic('format-fill-color.png'))
        self.setWindowTitle(_('Create/edit a {0} rule').format(rule_text))

        self.l = l = QGridLayout(self)
        self.setLayout(l)

        self.l1 = l1 = QLabel(_('Create a {0} rule by'
            ' filling in the boxes below').format(rule_text))
        l.addWidget(l1, 0, 0, 1, 8)

        self.f1 = QFrame(self)
        self.f1.setFrameShape(QFrame.Shape.HLine)
        l.addWidget(self.f1, 1, 0, 1, 8)

        # self.l2 = l2 = QLabel(_('Add the emblem:') if self.rule_kind == 'emblem' else _('Set the'))
        # l.addWidget(l2, 2, 0)

        if self.rule_kind == 'emblem':
            self.l2 = l2 = QLabel(_('Add the emblem:'))
            l.addWidget(l2, 2, 0)
        elif self.rule_kind == 'color':
            l.addWidget(QLabel(_('Set the color of the column:')), 2, 0)
        elif self.rule_kind == 'icon':
            l.addWidget(QLabel(_('Set the:')), 2, 0)
            self.kind_box = QComboBox(self)
            for tt, t in icon_rule_kinds:
                self.kind_box.addItem(tt, t)
            l.addWidget(self.kind_box, 3, 0)
            self.kind_box.setToolTip(textwrap.fill(_(
                'Choosing icon with text will add an icon to the left of the'
                ' column content, choosing icon with no text will hide'
                ' the column content and leave only the icon.'
                ' If you choose composed icons and multiple rules match, then all the'
                ' matching icons will be combined, otherwise the icon from the'
                ' first rule to match will be used.')))
            self.l3 = l3 = QLabel(_('of the column:'))
            l.addWidget(l3, 2, 2)
        else:
            pass

        self.column_box = QComboBox(self)
        l.addWidget(self.column_box, 3, 0 if self.rule_kind == 'color' else 2)

        self.l4 = l4 = QLabel(_('to:'))
        l.addWidget(l4, 2, 5)
        if self.rule_kind == 'emblem':
            self.column_box.setVisible(False), l4.setVisible(False)

        def create_filename_box():
            self.filename_box = f = QComboBox()
            self.filenamebox_view = v = QListView()
            v.setIconSize(QSize(32, 32))
            self.filename_box.setView(v)
            self.orig_filenamebox_view = f.view()
            f.setMinimumContentsLength(20), f.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            self.populate_icon_filenames()

        if self.rule_kind == 'color':
            self.color_box = ColorButton(parent=self)
            self.color_label = QLabel('Sample text Sample text')
            self.color_label.setTextFormat(Qt.TextFormat.RichText)
            l.addWidget(self.color_box, 3, 5)
            l.addWidget(self.color_label, 3, 6)
            l.addItem(QSpacerItem(10, 10, QSizePolicy.Policy.Expanding), 2, 7)
        elif self.rule_kind == 'emblem':
            create_filename_box()
            self.update_filename_box()
            self.filename_button = QPushButton(QIcon.ic('document_open.png'),
                                               _('&Add new image'))
            l.addWidget(self.filename_box, 3, 0)
            l.addWidget(self.filename_button, 3, 2)
            l.addWidget(QLabel(_('(Images should be square-ish)')), 3, 4)
            l.setColumnStretch(7, 10)
        else:
            create_filename_box()
            self.multiple_icon_cb = QCheckBox(_('Choose &more than one icon'))
            l.addWidget(self.multiple_icon_cb, 4, 5)
            self.update_filename_box()
            self.multiple_icon_cb.clicked.connect(self.multiple_box_clicked)
            l.addWidget(self.filename_box, 3, 5)

            self.filename_button = QPushButton(QIcon.ic('document_open.png'),
                                               _('&Add icon'))
            l.addWidget(self.filename_button, 3, 6)
            l.addWidget(QLabel(_('(Icons should be square or landscape)')), 4, 6)
            l.setColumnStretch(7, 10)

        self.l5 = l5 = QLabel(
            _('Only if the following conditions are all satisfied:'))
        l.addWidget(l5, 5, 0, 1, 7)

        self.scroll_area = sa = QScrollArea(self)
        sa.setMinimumHeight(300)
        sa.setMinimumWidth(700)
        sa.setWidgetResizable(True)
        l.addWidget(sa, 6, 0, 1, 8)

        self.add_button = b = QPushButton(QIcon.ic('plus.png'),
                _('Add &another condition'))
        l.addWidget(b, 7, 0, 1, 8)
        b.clicked.connect(self.add_blank_condition)

        self.l6 = l6 = QLabel(_('You can disable a condition by'
            ' blanking all of its boxes'))
        l.addWidget(l6, 8, 0, 1, 8)

        self.bb = bb = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb, 9, 0, 1, 8)
        if self.rule_kind != 'color':
            self.remove_button = b = bb.addButton(_('&Remove icons'), QDialogButtonBox.ButtonRole.ActionRole)
            b.setIcon(QIcon.ic('minus.png'))
            b.clicked.connect(self.remove_icon_file_dialog)
            b.setToolTip('<p>' + _('Remove previously added icons. Note that removing an '
                                   'icon will cause rules that use it to stop working.') + '</p>')

        self.conditions_widget = QWidget(self)
        sa.setWidget(self.conditions_widget)
        self.conditions_widget.setLayout(QVBoxLayout())
        self.conditions_widget.layout().setAlignment(Qt.AlignmentFlag.AlignTop)
        self.conditions = []

        if self.rule_kind == 'color':
            for b in (self.column_box, ):
                b.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                b.setMinimumContentsLength(15)

        for key in sorted(displayable_columns(fm),
                          key=lambda k: sort_key(fm[k]['name']) if k != color_row_key else b''):
            if key == color_row_key and self.rule_kind != 'color':
                continue
            name = all_columns_string if key == color_row_key else fm[key]['name']
            if name:
                self.column_box.addItem(name +
                        (' (' + key + ')' if key != color_row_key else ''), key)
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
            item.setIcon(QIcon.ic('blank.png'))
        else:
            item = QStandardItem('')
        item.setFlags(Qt.ItemFlag(0))
        model.appendRow(item)

        for i,filename in enumerate(self.icon_file_names):
            item = QStandardItem(filename)
            if doing_multiple:
                item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                item.setData(Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
            else:
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            icon = QIcon(os.path.join(self.icon_folder, filename))
            item.setIcon(icon)
            model.appendRow(item)

    def update_color_label(self):
        pal = QApplication.palette()
        bg1 = str(pal.color(QPalette.ColorRole.Base).name())
        bg2 = str(pal.color(QPalette.ColorRole.AlternateBase).name())
        c = self.color_box.color
        self.color_label.setText('''
            <span style="color: {c}; background-color: {bg1}">&nbsp;{st}&nbsp;</span>
            <span style="color: {c}; background-color: {bg2}">&nbsp;{st}&nbsp;</span>
            '''.format(c=c, bg1=bg1, bg2=bg2, st=_('Sample text')))

    def sanitize_icon_file_name(self, icon_path):
        n = lower(sanitize_file_name(
                             os.path.splitext(
                                   os.path.basename(icon_path))[0]+'.png'))
        return n.replace("'", '_')

    def filename_button_clicked(self):
        try:
            path = choose_files(self, 'choose_category_icon',
                        _('Select icon'), filters=[
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
                if item.checkState() == Qt.CheckState.Checked:
                    fnames.append(lower(str(item.text())))
            fname = ' : '.join(fnames)
        else:
            fname = lower(str(self.filename_box.currentText()))
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
                        item.setCheckState(Qt.CheckState.Checked)

    def remove_icon_file_dialog(self):
        d = RemoveIconFileDialog(self, self.icon_file_names, self.icon_folder)
        if d.exec() == QDialog.DialogCode.Accepted:
            if len(d.files_to_remove) > 0:
                for name in d.files_to_remove:
                    try:
                        os.remove(os.path.join(self.icon_folder, name))
                    except OSError:
                        pass
                self.populate_icon_filenames()
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
            c = str(self.column_box.itemData(i) or '')
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
        col = str(self.column_box.itemData(idx) or '')
        for c in self.conditions:
            condition = c.condition
            if condition is not None:
                r.add_condition(*condition)
        if self.rule_kind == 'icon':
            kind = str(self.kind_box.itemData(
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
        if role == Qt.ItemDataRole.DisplayRole:
            if col == color_row_key:
                col = all_columns_string
            else:
                col = self.fm[col]['name']
            return self.rule_to_html(kind, col, rule)
        if role == Qt.ItemDataRole.UserRole:
            return (kind, col, rule)

    def add_rule(self, kind, col, rule, selected_row=None):
        self.beginResetModel()
        if selected_row:
            self.rules.insert(selected_row.row(), (kind, col, rule))
        else:
            self.rules.append((kind, col, rule))
        self.endResetModel()
        if selected_row:
            return self.index(selected_row.row())
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
            self.beginResetModel()
            t = self.rules.pop(row-delta)
            self.rules.insert(row, t)  # does append if row >= len(rules)
            self.endResetModel()
            idx = self.index(row)
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
            _('<li>If the <b>%(col)s</b> column <b>%(action)s</b> %(val_label)s<b>%(val)s</b>') % dict(
                col=c, action=action_name, val=prepare_string_for_xml(v),
                val_label=_('value: ') if v else ''))

# }}}


class RulesView(QListView):  # {{{

    def __init__(self, parent, enable_convert_buttons_function):
        QListView.__init__(self, parent)
        self.enable_convert_buttons_function = enable_convert_buttons_function

    def currentChanged(self, new, prev):
        if self.model() and new.isValid():
            _, _, rule = self.model().data(new, Qt.ItemDataRole.UserRole)
            self.enable_convert_buttons_function(isinstance(rule, Rule))
        return super().currentChanged(new, prev)
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

        self.add_button = QPushButton(QIcon.ic('plus.png'), _('&Add rule'),
                self)
        self.remove_button = QPushButton(QIcon.ic('minus.png'),
                _('&Remove rule(s)'), self)
        self.add_button.clicked.connect(self.add_rule)
        self.remove_button.clicked.connect(self.remove_rule)
        l.addWidget(self.add_button, l.rowCount(), 0)
        l.addWidget(self.remove_button, l.rowCount() - 1, 1)

        self.g = g = QGridLayout()
        self.rules_view = RulesView(self, self.do_enable_convert_buttons)
        self.rules_view.doubleClicked.connect(self.edit_rule)
        self.rules_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.rules_view.setAlternatingRowColors(True)
        self.rtfd = RichTextDelegate(parent=self.rules_view, max_width=400)
        self.rules_view.setItemDelegate(self.rtfd)
        g.addWidget(self.rules_view, 0, 0, 2, 1)

        self.up_button = b = QToolButton(self)
        b.setIcon(QIcon.ic('arrow-up.png'))
        b.setToolTip(_('Move the selected rule up'))
        b.clicked.connect(partial(self.move_rows, moving_up=True))
        g.addWidget(b, 0, 1, 1, 1, Qt.AlignmentFlag.AlignTop)
        self.down_button = b = QToolButton(self)
        b.setIcon(QIcon.ic('arrow-down.png'))
        b.setToolTip(_('Move the selected rule down'))
        b.clicked.connect(partial(self.move_rows, moving_up=False))
        g.addWidget(b, 1, 1, 1, 1, Qt.AlignmentFlag.AlignBottom)

        l.addLayout(g, l.rowCount(), 0, 1, 2)
        l.setRowStretch(l.rowCount() - 1, 10)

        self.add_advanced_button = b = QPushButton(QIcon.ic('plus.png'),
                _('Add ad&vanced rule'), self)
        b.clicked.connect(self.add_advanced)
        self.hb = hb = FlowLayout()
        l.addLayout(hb, l.rowCount(), 0, 1, 2)
        hb.addWidget(b)
        self.duplicate_rule_button = b = QPushButton(QIcon.ic('edit-copy.png'),
                _('Du&plicate rule'), self)
        b.clicked.connect(self.duplicate_rule)
        b.setEnabled(False)
        hb.addWidget(b)
        self.convert_to_advanced_button = b = QPushButton(QIcon.ic('modified.png'),
                _('Convert to advanced r&ule'), self)
        b.clicked.connect(self.convert_to_advanced)
        b.setEnabled(False)
        hb.addWidget(b)
        sep = Separator(self, b)
        hb.addWidget(sep)

        self.open_icon_folder_button = b = QPushButton(QIcon.ic('icon_choose.png'),
                _('Open icon folder'), self)
        b.clicked.connect(self.open_icon_folder)
        hb.addWidget(b)
        sep = Separator(self, b)
        hb.addWidget(sep)
        self.export_button = b = QPushButton(_('E&xport'), self)
        b.clicked.connect(self.export_rules)
        b.setToolTip(_('Export these rules to a file'))
        hb.addWidget(b)
        self.import_button = b = QPushButton(_('&Import'), self)
        b.setToolTip(_('Import rules from a file'))
        b.clicked.connect(self.import_rules)
        hb.addWidget(b)

    def open_icon_folder(self):
        path = os.path.join(config_dir, 'cc_icons')
        os.makedirs(path, exist_ok=True)
        open_local_file(path)

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

    def do_enable_convert_buttons(self, to_what):
        self.convert_to_advanced_button.setEnabled(to_what)
        self.duplicate_rule_button.setEnabled(True)

    def convert_to_advanced(self):
        sm = self.rules_view.selectionModel()
        rows = list(sm.selectedRows())
        if not rows or len(rows) != 1:
            error_dialog(self, _('Select one rule'),
                _('You must select only one rule.'), show=True)
            return
        idx = self.rules_view.currentIndex()
        if idx.isValid():
            kind, col, rule = self.model.data(idx, Qt.ItemDataRole.UserRole)
            if isinstance(rule, Rule):
                template = '\n'.join(
                     [l for l in rule.template.splitlines() if not l.startswith(Rule.SIGNATURE)])
                orig_row = idx.row()
                self.model.remove_rule(idx)
                new_idx = self.model.add_rule(kind, col, template)
                new_idx = self.model.move(new_idx, -(self.model.rowCount() - orig_row - 1))
                self.rules_view.setCurrentIndex(new_idx)
                self.changed.emit()

    def duplicate_rule(self):
        sm = self.rules_view.selectionModel()
        rows = list(sm.selectedRows())
        if not rows or len(rows) != 1:
            error_dialog(self, _('Select one rule'),
                _('You must select only one rule.'), show=True)
            return
        idx = self.rules_view.currentIndex()
        if idx.isValid():
            kind, col, rule = self.model.data(idx, Qt.ItemDataRole.UserRole)
            orig_row = idx.row() + 1
            new_idx = self.model.add_rule(kind, col, rule)
            new_idx = self.model.move(new_idx, -(self.model.rowCount() - orig_row - 1))
            self.rules_view.setCurrentIndex(new_idx)
            self.changed.emit()

    def add_rule(self):
        d = RuleEditor(self.model.fm, self.pref_name)
        d.add_blank_condition()
        if d.exec() == QDialog.DialogCode.Accepted:
            kind, col, r = d.rule
            if kind and r and col:
                selected_row = self.get_first_selected_row()
                idx = self.model.add_rule(kind, col, r, selected_row=selected_row)
                self.rules_view.scrollTo(idx)
                self.changed.emit()

    def add_advanced(self):
        selected_row = self.get_first_selected_row()
        if self.pref_name == 'column_color_rules':
            td = TemplateDialog(self, '', mi=self.mi, fm=self.fm, color_field='')
            if td.exec() == QDialog.DialogCode.Accepted:
                col, r = td.rule
                if r and col:
                    idx = self.model.add_rule('color', col, r, selected_row=selected_row)
                    self.rules_view.scrollTo(idx)
                    self.changed.emit()
        else:
            if self.pref_name == 'cover_grid_icon_rules':
                td = TemplateDialog(self, '', mi=self.mi, fm=self.fm, doing_emblem=True)
            else:
                td = TemplateDialog(self, '', mi=self.mi, fm=self.fm, icon_field_key='')
            if td.exec() == QDialog.DialogCode.Accepted:
                typ, col, r = td.rule
                if typ and r and col:
                    idx = self.model.add_rule(typ, col, r, selected_row=selected_row)
                    self.rules_view.scrollTo(idx)
                    self.changed.emit()

    def edit_rule(self, index):
        try:
            kind, col, rule = self.model.data(index, Qt.ItemDataRole.UserRole)
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

        if d.exec() == QDialog.DialogCode.Accepted:
            if len(d.rule) == 2:  # Convert template dialog rules to a triple
                d.rule = ('color', d.rule[0], d.rule[1])
            kind, col, r = d.rule
            if kind and r is not None and col:
                self.model.replace_rule(index, kind, col, r)
                self.rules_view.scrollTo(index)
                self.changed.emit()

    def get_first_selected_row(self):
        r = self.get_selected_row('', show_error=False)
        if r:
            return r[-1]
        return None

    def get_selected_row(self, txt, show_error=True):
        sm = self.rules_view.selectionModel()
        rows = list(sm.selectedRows())
        if not rows:
            if show_error:
                error_dialog(self, _('No rule selected'), _('No rule selected for %s.')%txt, show=True)
            return None
        return sorted(rows, reverse=True)

    def remove_rule(self):
        rows = self.get_selected_row(_('removal'))
        if rows is not None:
            for row in rows:
                self.model.remove_rule(row)
            self.changed.emit()

    def move_rows(self, moving_up=True):
        sm = self.rules_view.selectionModel()
        rows = sorted(list(sm.selectedRows()), reverse=not moving_up)
        if rows:
            if rows[0].row() == (0 if moving_up else self.model.rowCount() - 1):
                return
            sm.clear()
            indices_to_select = []
            for idx in rows:
                if idx.isValid():
                    idx = self.model.move(idx, -1 if moving_up else 1)
                    if idx is not None:
                        indices_to_select.append(idx)
            if indices_to_select:
                new_selections = QItemSelection()
                for idx in indices_to_select:
                    new_selections.merge(QItemSelection(idx, idx),
                                         QItemSelectionModel.SelectionFlag.Select)
                sm.select(new_selections, QItemSelectionModel.SelectionFlag.Select)
                self.rules_view.scrollTo(indices_to_select[0])
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
            data = json.dumps(rules, indent=2)
            if not isinstance(data, bytes):
                data = data.encode('utf-8')
            with lopen(path, 'wb') as f:
                f.write(data)

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
        d.exec()

        kind, col, r = d.rule

        print('Column to be colored:', col)
        print('Template:')
        print(r.template)
    else:
        d = EditRules()
        d.resize(QSize(800, 600))
        d.initialize(db.field_metadata, db.prefs, None, 'column_color_rules')
        d.show()
        app.exec()
        d.commit(db.prefs)
