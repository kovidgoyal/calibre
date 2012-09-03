# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import textwrap

from PyQt4.Qt import QWidget, QListWidgetItem, Qt, QVariant, SIGNAL, \
                     QLabel, QLineEdit, QCheckBox

from calibre.gui2 import error_dialog, question_dialog
from calibre.gui2.device_drivers.configwidget_ui import Ui_ConfigWidget
from calibre.utils.formatter import validation_formatter
from calibre.ebooks import BOOK_EXTENSIONS

class ConfigWidget(QWidget, Ui_ConfigWidget):

    def __init__(self, settings, all_formats, supports_subdirs,
        must_read_metadata, supports_use_author_sort,
        extra_customization_message, device):

        QWidget.__init__(self)
        Ui_ConfigWidget.__init__(self)
        self.setupUi(self)

        self.settings = settings

        all_formats = set(all_formats)
        self.calibre_known_formats = device.FORMATS
        self.device_name = device.get_gui_name()
        if device.USER_CAN_ADD_NEW_FORMATS:
            all_formats = set(all_formats) | set(BOOK_EXTENSIONS)

        format_map = settings.format_map
        disabled_formats = list(set(all_formats).difference(format_map))
        for format in format_map + list(sorted(disabled_formats)):
            item = QListWidgetItem(format, self.columns)
            item.setData(Qt.UserRole, QVariant(format))
            item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable|Qt.ItemIsSelectable)
            item.setCheckState(Qt.Checked if format in format_map else Qt.Unchecked)

        self.connect(self.column_up, SIGNAL('clicked()'), self.up_column)
        self.connect(self.column_down, SIGNAL('clicked()'), self.down_column)

        if device.HIDE_FORMATS_CONFIG_BOX:
            self.groupBox.hide()

        if supports_subdirs:
            self.opt_use_subdirs.setChecked(self.settings.use_subdirs)
        else:
            self.opt_use_subdirs.hide()
        if not must_read_metadata:
            self.opt_read_metadata.setChecked(self.settings.read_metadata)
        else:
            self.opt_read_metadata.hide()
        if supports_use_author_sort:
            self.opt_use_author_sort.setChecked(self.settings.use_author_sort)
        else:
            self.opt_use_author_sort.hide()
        if extra_customization_message:
            def parse_msg(m):
                msg, _, tt = m.partition(':::') if m else ('', '', '')
                return msg.strip(), textwrap.fill(tt.strip(), 100)

            if isinstance(extra_customization_message, list):
                self.opt_extra_customization = []
                if len(extra_customization_message) > 6:
                    row_func = lambda x, y: ((x/2) * 2) + y
                    col_func = lambda x: x%2
                else:
                    row_func = lambda x, y: x*2 + y
                    col_func = lambda x: 0

                for i, m in enumerate(extra_customization_message):
                    label_text, tt = parse_msg(m)
                    if not label_text:
                        self.opt_extra_customization.append(None)
                        continue
                    if isinstance(settings.extra_customization[i], bool):
                        self.opt_extra_customization.append(QCheckBox(label_text))
                        self.opt_extra_customization[-1].setToolTip(tt)
                        self.opt_extra_customization[i].setChecked(bool(settings.extra_customization[i]))
                    else:
                        self.opt_extra_customization.append(QLineEdit(self))
                        l = QLabel(label_text)
                        l.setToolTip(tt)
                        self.opt_extra_customization[i].setToolTip(tt)
                        l.setBuddy(self.opt_extra_customization[i])
                        l.setWordWrap(True)
                        self.opt_extra_customization[i].setText(settings.extra_customization[i])
                        self.opt_extra_customization[i].setCursorPosition(0)
                        self.extra_layout.addWidget(l, row_func(i, 0), col_func(i))
                    self.extra_layout.addWidget(self.opt_extra_customization[i],
                                                row_func(i, 1), col_func(i))
            else:
                self.opt_extra_customization = QLineEdit()
                label_text, tt = parse_msg(extra_customization_message)
                l = QLabel(label_text)
                l.setToolTip(tt)
                l.setBuddy(self.opt_extra_customization)
                l.setWordWrap(True)
                if settings.extra_customization:
                    self.opt_extra_customization.setText(settings.extra_customization)
                    self.opt_extra_customization.setCursorPosition(0)
                self.opt_extra_customization.setCursorPosition(0)
                self.extra_layout.addWidget(l, 0, 0)
                self.extra_layout.addWidget(self.opt_extra_customization, 1, 0)
        self.opt_save_template.setText(settings.save_template)


    def up_column(self):
        idx = self.columns.currentRow()
        if idx > 0:
            self.columns.insertItem(idx-1, self.columns.takeItem(idx))
            self.columns.setCurrentRow(idx-1)

    def down_column(self):
        idx = self.columns.currentRow()
        if idx < self.columns.count()-1:
            self.columns.insertItem(idx+1, self.columns.takeItem(idx))
            self.columns.setCurrentRow(idx+1)

    def format_map(self):
        formats = [unicode(self.columns.item(i).data(Qt.UserRole).toString()) for i in range(self.columns.count()) if self.columns.item(i).checkState()==Qt.Checked]
        return formats

    def use_subdirs(self):
        return self.opt_use_subdirs.isChecked()

    def read_metadata(self):
        return self.opt_read_metadata.isChecked()

    def use_author_sort(self):
        return self.opt_use_author_sort.isChecked()

    def validate(self):
        formats = set(self.format_map())
        extra = formats - set(self.calibre_known_formats)
        if extra:
            fmts = sorted([x.upper() for x in extra])
            if not question_dialog(self, _('Unknown formats'),
                    _('You have enabled the <b>{0}</b> formats for'
                        ' your {1}. The {1} may not support them.'
                        ' If you send these formats to your {1} they '
                        'may not work. Are you sure?').format(
                            (', '.join(fmts)), self.device_name)):
                return False

        tmpl = unicode(self.opt_save_template.text())
        try:
            validation_formatter.validate(tmpl)
            return True
        except Exception as err:
            error_dialog(self, _('Invalid template'),
                    '<p>'+_('The template %s is invalid:')%tmpl + \
                    '<br>'+unicode(err), show=True)

            return False
