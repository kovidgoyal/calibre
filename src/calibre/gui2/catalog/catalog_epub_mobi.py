#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from calibre.ebooks.conversion.config import load_defaults
from calibre.gui2 import gprefs, question_dialog
from calibre.utils.icu import sort_key

from catalog_epub_mobi_ui import Ui_Form
from PyQt4 import QtGui
from PyQt4.Qt import (Qt, QAbstractItemView, QCheckBox, QComboBox, QDialog,
                      QDialogButtonBox, QDoubleSpinBox,
                      QHBoxLayout, QIcon, QLabel, QLineEdit,
                      QPlainTextEdit, QRadioButton, QSize, QTableWidget, QTableWidgetItem,
                      QVBoxLayout, QWidget)

class PluginWidget(QWidget,Ui_Form):

    TITLE = _('E-book options')
    HELP  = _('Options specific to')+' EPUB/MOBI '+_('output')

    # Output synced to the connected device?
    sync_enabled = True

    # Formats supported by this plugin
    formats = set(['epub','mobi'])

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)
        self._initControlArrays()

    def _initControlArrays(self):

        CheckBoxControls = []
        ComboBoxControls = []
        DoubleSpinBoxControls = []
        LineEditControls = []
        RadioButtonControls = []
        TableWidgetControls = []

        for item in self.__dict__:
            if type(self.__dict__[item]) is QCheckBox:
                CheckBoxControls.append(str(self.__dict__[item].objectName()))
            elif type(self.__dict__[item]) is QComboBox:
                ComboBoxControls.append(str(self.__dict__[item].objectName()))
            elif type(self.__dict__[item]) is QDoubleSpinBox:
                DoubleSpinBoxControls.append(str(self.__dict__[item].objectName()))
            elif type(self.__dict__[item]) is QLineEdit:
                LineEditControls.append(str(self.__dict__[item].objectName()))
            elif type(self.__dict__[item]) is QRadioButton:
                RadioButtonControls.append(str(self.__dict__[item].objectName()))
            elif type(self.__dict__[item]) is QTableWidget:
                TableWidgetControls.append(str(self.__dict__[item].objectName()))

        option_fields = zip(CheckBoxControls,
                            [True for i in CheckBoxControls],
                            ['check_box' for i in CheckBoxControls])
        option_fields += zip(ComboBoxControls,
                            [None for i in ComboBoxControls],
                            ['combo_box' for i in ComboBoxControls])
        option_fields += zip(RadioButtonControls,
                            [None for i in RadioButtonControls],
                            ['radio_button' for i in RadioButtonControls])

        # LineEditControls
        option_fields += zip(['exclude_genre'],['\[.+\]|\+'],['line_edit'])
        option_fields += zip(['exclude_pattern'],[None],['line_edit'])
        option_fields += zip(['exclude_tags'],['~,'+_('Catalog')],['line_edit'])

        # SpinBoxControls
        option_fields += zip(['thumb_width'],[1.00],['spin_box'])

        # Prefix rules TableWidget
        option_fields += zip(['prefix_rules_tw','prefix_rules_tw','prefix_rules_tw'],
                             [{'ordinal':0,
                               'enabled':True,
                               'name':'Read book',
                               'field':'Tags',
                               'pattern':'+',
                               'prefix':u'\u2713'},
                              {'ordinal':1,
                               'enabled':True,
                               'name':'Wishlist item',
                               'field':'Tags',
                               'pattern':'Wishlist',
                               'prefix':u'\u00d7'},
                              {'ordinal':2,
                               'enabled':False,
                               'name':'New rule',
                               'field':'',
                               'pattern':'',
                               'prefix':''}],
                             ['table_widget','table_widget','table_widget'])

        self.OPTION_FIELDS = option_fields

    def fetchEligibleCustomFields(self):
        self.all_custom_fields = self.db.custom_field_keys()
        custom_fields = {}
        custom_fields['Tags'] = {'field':'tag', 'datatype':u'text'}
        for custom_field in self.all_custom_fields:
            field_md = self.db.metadata_for_field(custom_field)
            if field_md['datatype'] in ['bool','composite','datetime','enumeration','text']:
                custom_fields[field_md['name']] = {'field':custom_field,
                                                   'datatype':field_md['datatype']}
        self.eligible_custom_fields = custom_fields

    def generatePrefixList(self):
        def prefix_sorter(item):
            key = item
            if item[0] == "_":
                key = 'zzz' + item
            return key


        # Create a list of prefixes for user selection
        raw_prefix_list = [
            ('Ampersand',u'&'),
            ('Angle left double',u'\u00ab'),
            ('Angle left',u'\u2039'),
            ('Angle right double',u'\u00bb'),
            ('Angle right',u'\u203a'),
            ('Arrow double',u'\u2194'),
            ('Arrow down',u'\u2193'),
            ('Arrow left',u'\u2190'),
            ('Arrow right',u'\u2192'),
            ('Arrow up',u'\u2191'),
            ('Asterisk',u'*'),
            ('At sign',u'@'),
            ('Bullet smallest',u'\u22c5'),
            ('Bullet small',u'\u00b7'),
            ('Bullet',u'\u2022'),
            ('Caret',u'^'),
            ('Checkmark',u'\u2713'),
            ('Copyright',u'\u00a9'),
            ('Currency dollar',u'$'),
            ('Currency euro',u'\u20ac'),
            ('Dagger double',u'\u2021'),
            ('Dagger',u'\u2020'),
            ('Degree',u'\u00b0'),
            ('Dots3',u'\u2234'),
            ('Hash',u'#'),
            ('Infinity',u'\u221e'),
            ('Lozenge',u'\u25ca'),
            ('Math divide',u'\u00f7'),
            ('Math empty',u'\u2205'),
            ('Math equals',u'='),
            ('Math minus',u'\u2212'),
            ('Math plus circled',u'\u2295'),
            ('Math times circled',u'\u2297'),
            ('Math times',u'\u00d7'),
            ('O slash',u'\u00d8'),
            ('Paragraph',u'\u00b6'),
            ('Percent',u'%'),
            ('Plus-or-minus',u'\u00b1'),
            ('Plus',u'+'),
            ('Punctuation colon',u':'),
            ('Punctuation colon-semi',u';'),
            ('Punctuation exclamation',u'!'),
            ('Punctuation question',u'?'),
            ('Registered trademark',u'\u00ae'),
            ('Section',u'\u00a7'),
            ('Tilde',u'~'),
            ('Vertical bar',u'|'),
            ('Vertical bar broken',u'\u00a6'),
            ('_0',u'0'),
            ('_1',u'1'),
            ('_2',u'2'),
            ('_3',u'3'),
            ('_4',u'4'),
            ('_5',u'5'),
            ('_6',u'6'),
            ('_7',u'7'),
            ('_8',u'8'),
            ('_9',u'9'),
            ('_A',u'A'),
            ('_B',u'B'),
            ('_C',u'C'),
            ('_D',u'D'),
            ('_E',u'E'),
            ('_F',u'F'),
            ('_G',u'G'),
            ('_H',u'H'),
            ('_I',u'I'),
            ('_J',u'J'),
            ('_K',u'K'),
            ('_L',u'L'),
            ('_M',u'M'),
            ('_N',u'N'),
            ('_O',u'O'),
            ('_P',u'P'),
            ('_Q',u'Q'),
            ('_R',u'R'),
            ('_S',u'S'),
            ('_T',u'T'),
            ('_U',u'U'),
            ('_V',u'V'),
            ('_W',u'W'),
            ('_X',u'X'),
            ('_Y',u'Y'),
            ('_Z',u'Z'),
            ('_a',u'a'),
            ('_b',u'b'),
            ('_c',u'c'),
            ('_d',u'd'),
            ('_e',u'e'),
            ('_f',u'f'),
            ('_g',u'g'),
            ('_h',u'h'),
            ('_i',u'i'),
            ('_j',u'j'),
            ('_k',u'k'),
            ('_l',u'l'),
            ('_m',u'm'),
            ('_n',u'n'),
            ('_o',u'o'),
            ('_p',u'p'),
            ('_q',u'q'),
            ('_r',u'r'),
            ('_s',u's'),
            ('_t',u't'),
            ('_u',u'u'),
            ('_v',u'v'),
            ('_w',u'w'),
            ('_x',u'x'),
            ('_y',u'y'),
            ('_z',u'z'),
            ]
        #raw_prefix_list = sorted(raw_prefix_list, key=lambda k: sort_key(k[0]))
        raw_prefix_list = sorted(raw_prefix_list, key=prefix_sorter)
        self.prefixes = [x[1] for x in raw_prefix_list]

    def initialize(self, name, db):
        '''

        CheckBoxControls (c_type: check_box):
            ['generate_titles','generate_series','generate_genres',
                            'generate_recently_added','generate_descriptions','include_hr']
        ComboBoxControls (c_type: combo_box):
            ['exclude_source_field','header_note_source_field',
                            'merge_source_field']
        LineEditControls (c_type: line_edit):
            ['exclude_genre','exclude_pattern','exclude_tags']
        RadioButtonControls (c_type: radio_button):
            ['merge_before','merge_after']
        SpinBoxControls (c_type: spin_box):
            ['thumb_width']
        TableWidgetControls (c_type: table_widget):
            ['prefix_rules_tw']

        '''
        self.name = name
        self.db = db
        self.fetchEligibleCustomFields()
        self.generatePrefixList()
        self.populate_combo_boxes()


        # Update dialog fields from stored options
        prefix_rules = []
        for opt in self.OPTION_FIELDS:
            c_name, c_def, c_type = opt
            opt_value = gprefs.get(self.name + '_' + c_name, c_def)
            if c_type in ['check_box']:
                getattr(self, c_name).setChecked(eval(str(opt_value)))
            elif c_type in ['combo_box'] and opt_value is not None:
                # *** Test this code with combo boxes ***
                #index = self.read_source_field.findText(opt_value)
                index = getattr(self,c_name).findText(opt_value)
                if index == -1 and c_name == 'read_source_field':
                    index = self.read_source_field.findText('Tag')
                #self.read_source_field.setCurrentIndex(index)
                getattr(self,c_name).setCurrentIndex(index)
            elif c_type in ['line_edit']:
                getattr(self, c_name).setText(opt_value if opt_value else '')
            elif c_type in ['radio_button'] and opt_value is not None:
                getattr(self, c_name).setChecked(opt_value)
            elif c_type in ['spin_box']:
                getattr(self, c_name).setValue(float(opt_value))
            elif c_type in ['table_widget'] and c_name == 'prefix_rules_tw':
                if opt_value not in prefix_rules:
                    prefix_rules.append(opt_value)

        # Init self.exclude_source_field_name
        self.exclude_source_field_name = ''
        cs = unicode(self.exclude_source_field.currentText())
        if cs > '':
            exclude_source_spec = self.exclude_source_fields[cs]
            self.exclude_source_field_name = exclude_source_spec['field']

        # Init self.merge_source_field_name
        self.merge_source_field_name = ''
        cs = unicode(self.merge_source_field.currentText())
        if cs > '':
            merge_source_spec = self.merge_source_fields[cs]
            self.merge_source_field_name = merge_source_spec['field']

        # Init self.header_note_source_field_name
        self.header_note_source_field_name = ''
        cs = unicode(self.header_note_source_field.currentText())
        if cs > '':
            header_note_source_spec = self.header_note_source_fields[cs]
            self.header_note_source_field_name = header_note_source_spec['field']

        # Hook changes to thumb_width
        self.thumb_width.valueChanged.connect(self.thumb_width_changed)

        # Hook changes to Description section
        self.generate_descriptions.stateChanged.connect(self.generate_descriptions_changed)

        # Neaten up the prefix rules
        self.prefix_rules_initialize()
        self.populate_prefix_rules(prefix_rules)
        self.prefix_rules_tw.resizeColumnsToContents()
        self.prefix_rules_resize_name(1.5)
        self.prefix_rules_tw.horizontalHeader().setStretchLastSection(True)

    def prefix_rules_initialize(self):
        # Assign icons to buttons, hook clicks
        self.move_rule_up_tb.setToolTip('Move rule up')
        self.move_rule_up_tb.setIcon(QIcon(I('arrow-up.png')))
        self.move_rule_up_tb.clicked.connect(self.prefix_rules_move_row_up)

        self.add_rule_tb.setToolTip('Add a new rule')
        self.add_rule_tb.setIcon(QIcon(I('plus.png')))
        self.add_rule_tb.clicked.connect(self.prefix_rules_add_row)

        self.delete_rule_tb.setToolTip('Delete selected rule')
        self.delete_rule_tb.setIcon(QIcon(I('list_remove.png')))
        self.delete_rule_tb.clicked.connect(self.prefix_rules_delete_row)

        self.move_rule_down_tb.setToolTip('Move rule down')
        self.move_rule_down_tb.setIcon(QIcon(I('arrow-down.png')))
        self.move_rule_down_tb.clicked.connect(self.prefix_rules_move_row_down)

        # Configure the QTableWidget
        # enabled/rule name/source field/pattern/prefix
        self.prefix_rules_tw.clear()
        header_labels = ['','Name','Prefix','Source','Pattern']
        self.prefix_rules_tw.setColumnCount(len(header_labels))
        self.prefix_rules_tw.setHorizontalHeaderLabels(header_labels)
        self.prefix_rules_tw.setSortingEnabled(False)
        self.prefix_rules_tw.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.prefix_rules_tw.cellDoubleClicked.connect(self.prefix_rules_cell_double_clicked)

    def options(self):
        # Save/return the current options
        # exclude_genre stores literally
        # generate_titles, generate_recently_added store as True/False
        # others store as lists

        opts_dict = {}
        # Save values to gprefs
        prefix_rules_processed = False
        for opt in self.OPTION_FIELDS:
            c_name, c_def, c_type = opt
            if c_type in ['check_box', 'radio_button']:
                opt_value = getattr(self, c_name).isChecked()
            elif c_type in ['combo_box']:
                opt_value = unicode(getattr(self,c_name).currentText()).strip()
            elif c_type in ['line_edit']:
                opt_value = unicode(getattr(self, c_name).text()).strip()
            elif c_type in ['spin_box']:
                opt_value = unicode(getattr(self, c_name).value())
            elif c_type in ['table_widget']:
                opt_value = self.prefix_rules_get_data()

            gprefs.set(self.name + '_' + c_name, opt_value)

            # Construct opts object for catalog builder
            if c_name == 'exclude_tags':
                # store as list
                opts_dict[c_name] = opt_value.split(',')
            elif c_name == 'prefix_rules_tw':
                if prefix_rules_processed:
                    continue
                rule_set = []
                for rule in opt_value:
                    # Test for empty name/field/pattern/prefix, continue
                    # If pattern = any or unspecified, convert to regex
                    if not rule['enabled']:
                        continue
                    elif not rule['field'] or not rule['pattern'] or not rule['prefix']:
                        continue
                    else:
                        if rule['field'] != 'Tags':
                            # Look up custom column name
                            #print(self.eligible_custom_fields[rule['field']]['field'])
                            rule['field'] = self.eligible_custom_fields[rule['field']]['field']
                        if rule['pattern'].startswith('any'):
                            rule['pattern'] = '.*'
                        elif rule['pattern'] == 'unspecified':
                            rule['pattern'] = 'None'

                        pr = (rule['name'],rule['field'],rule['pattern'],rule['prefix'])
                        rule_set.append(pr)

                opt_value = tuple(rule_set)
                opts_dict['prefix_rules'] = opt_value
                prefix_rules_processed = True

            else:
                opts_dict[c_name] = opt_value

        # Generate markers for hybrids
        #opts_dict['read_book_marker'] = "%s:%s" % (self.read_source_field_name,
        #                                           self.read_pattern.text())
        opts_dict['exclude_book_marker'] = "%s:%s" % (self.exclude_source_field_name,
                                                       self.exclude_pattern.text())

        # Generate specs for merge_comments, header_note_source_field
        checked = ''
        if self.merge_before.isChecked():
            checked = 'before'
        elif self.merge_after.isChecked():
            checked = 'after'
        include_hr = self.include_hr.isChecked()
        opts_dict['merge_comments'] = "%s:%s:%s" % \
            (self.merge_source_field_name, checked, include_hr)

        opts_dict['header_note_source_field'] = self.header_note_source_field_name

        # Append the output profile
        try:
            opts_dict['output_profile'] = [load_defaults('page_setup')['output_profile']]
        except:
            opts_dict['output_profile'] = ['default']
        if False:
            print "opts_dict"
            for opt in sorted(opts_dict.keys(), key=sort_key):
                print " %s: %s" % (opt, repr(opts_dict[opt]))
        return opts_dict

    def populate_combo_boxes(self):
        # Custom column types declared in
        #  gui2.preferences.create_custom_column:CreateCustomColumn()
        # As of 0.7.34:
        #  bool         Yes/No
        #  comments     Long text, like comments, not shown in tag browser
        #  composite    Column built from other columns
        #  datetime     Date
        #  enumeration  Text, but with a fixed set of permitted values
        #  float        Floating point numbers
        #  int          Integers
        #  rating       Ratings, shown with stars
        #  series       Text column for keeping series-like information
        #  text         Column shown in the tag browser
        #  *text        Comma-separated text, like tags, shown in tag browser

        # Populate the 'Excluded books' hybrid
        custom_fields = {}
        for custom_field in self.all_custom_fields:
            field_md = self.db.metadata_for_field(custom_field)
            if field_md['datatype'] in ['bool','composite','datetime','enumeration','text']:
                custom_fields[field_md['name']] = {'field':custom_field,
                                                   'datatype':field_md['datatype']}
        # Blank field first
        self.exclude_source_field.addItem('')
        # Add the sorted eligible fields to the combo box
        for cf in sorted(custom_fields, key=sort_key):
            self.exclude_source_field.addItem(cf)
        self.exclude_source_fields = custom_fields
        self.exclude_source_field.currentIndexChanged.connect(self.exclude_source_field_changed)


        # Populate the 'Header note' combo box
        custom_fields = {}
        for custom_field in self.all_custom_fields:
            field_md = self.db.metadata_for_field(custom_field)
            if field_md['datatype'] in ['bool','composite','datetime','enumeration','text']:
                custom_fields[field_md['name']] = {'field':custom_field,
                                                   'datatype':field_md['datatype']}
        # Blank field first
        self.header_note_source_field.addItem('')
        # Add the sorted eligible fields to the combo box
        for cf in sorted(custom_fields, key=sort_key):
            self.header_note_source_field.addItem(cf)
        self.header_note_source_fields = custom_fields
        self.header_note_source_field.currentIndexChanged.connect(self.header_note_source_field_changed)


        # Populate the 'Merge with Comments' combo box
        custom_fields = {}
        for custom_field in self.all_custom_fields:
            field_md = self.db.metadata_for_field(custom_field)
            if field_md['datatype'] in ['text','comments','composite']:
                custom_fields[field_md['name']] = {'field':custom_field,
                                                   'datatype':field_md['datatype']}
        # Blank field first
        self.merge_source_field.addItem('')
        # Add the sorted eligible fields to the combo box
        for cf in sorted(custom_fields, key=sort_key):
            self.merge_source_field.addItem(cf)
        self.merge_source_fields = custom_fields
        self.merge_source_field.currentIndexChanged.connect(self.merge_source_field_changed)
        self.merge_before.setEnabled(False)
        self.merge_after.setEnabled(False)
        self.include_hr.setEnabled(False)

    def populate_prefix_rules(self,rules):
        # Format of rules list is different if default values vs retrieved JSON
        # Hack to normalize list style
        if type(rules[0]) is list:
            rules = rules[0]
        self.prefix_rules_tw.setFocus()
        for row, rule in enumerate(rules):
            self.prefix_rules_tw.insertRow(row)
            self.prefix_rules_select_and_scroll_to_row(row)
            self.populate_prefix_rules_table_row(row, rule)
        self.prefix_rules_tw.selectRow(0)

    def populate_prefix_rules_table_row(self, row, data):

        def set_prefix_field_in_row(row, col, field=''):
            prefix_combo = PrefixRulesComboBox(self, self.prefixes, field)
            self.prefix_rules_tw.setCellWidget(row, col, prefix_combo)

        def set_rule_name_in_row(row, col, name=''):
            rule_name = QLineEdit(name)
            rule_name.home(False)
            rule_name.editingFinished.connect(self.prefix_rules_rule_name_edited)
            self.prefix_rules_tw.setCellWidget(row, col, rule_name)

        def set_source_field_in_row(row, col, field=''):
            source_combo = PrefixRulesComboBox(self, sorted(self.eligible_custom_fields.keys(), key=sort_key), field)
            source_combo.currentIndexChanged.connect(partial(self.prefix_rules_source_index_changed, source_combo, row))
            #source_combo.currentIndexChanged.connect(self.prefix_rules_source_index_changed, source_combo, row)
            self.prefix_rules_tw.setCellWidget(row, col, source_combo)
            return source_combo


        # Entry point
        self.prefix_rules_tw.blockSignals(True)
        #print("populate_prefix_rules_table_row processing rule:\n%s\n" % data)

        # Column 0: Enabled
        self.prefix_rules_tw.setItem(row, 0, CheckableTableWidgetItem(data['enabled']))

        # Column 1: Rule name
        #rule_name = QTableWidgetItem(data['name'])
        #self.prefix_rules_tw.setItem(row, 1, rule_name)
        set_rule_name_in_row(row, 1, name=data['name'])

        # Column 2: Prefix
        set_prefix_field_in_row(row, 2, field=data['prefix'])

        # Column 3: Source field
        source_combo = set_source_field_in_row(row, 3, field=data['field'])

        # Column 4: Pattern
        # The contents of the Pattern field is driven by the Source field
        self.prefix_rules_source_index_changed(source_combo, row, 4, pattern=data['pattern'])

        self.prefix_rules_tw.blockSignals(False)

    def prefix_rules_add_row(self):
        # Called when '+' clicked
        self.prefix_rules_tw.setFocus()
        row = self.prefix_rules_tw.currentRow() + 1
        self.prefix_rules_tw.insertRow(row)
        self.populate_prefix_rules_table_row(row, self.prefix_rules_create_blank_row_data())
        self.prefix_rules_select_and_scroll_to_row(row)
        self.prefix_rules_tw.resizeColumnsToContents()
        self.prefix_rules_tw.horizontalHeader().setStretchLastSection(True)

    def prefix_rules_cell_double_clicked(self, row, col):
        print("prefix_rules_cell_double_clicked: row:%d col:%d" % (row, col))

    def prefix_rules_convert_row_to_data(self, row):
        data = self.prefix_rules_create_blank_row_data()
        data['ordinal'] = row
        data['enabled'] = self.prefix_rules_tw.item(row,0).checkState() == Qt.Checked
        data['name'] = unicode(self.prefix_rules_tw.cellWidget(row,1).text()).strip()
        data['prefix'] = unicode(self.prefix_rules_tw.cellWidget(row,2).currentText()).strip()
        data['field'] = unicode(self.prefix_rules_tw.cellWidget(row,3).currentText()).strip()
        data['pattern'] = unicode(self.prefix_rules_tw.cellWidget(row,4).currentText()).strip()
        return data

    def prefix_rules_create_blank_row_data(self):
        data = {}
        data['ordinal'] = -1
        data['enabled'] = False
        data['name'] = 'New rule'
        data['field'] = ''
        data['pattern'] = ''
        data['prefix'] = ''
        return data

    def prefix_rules_delete_row(self):
        self.prefix_rules_tw.setFocus()
        rows = self.prefix_rules_tw.selectionModel().selectedRows()
        if len(rows) == 0:
            return
        message = '<p>Are you sure you want to delete this rule?'
        if len(rows) > 1:
            message = '<p>Are you sure you want to delete the %d selected rules?'%len(rows)
        if not question_dialog(self, _('Are you sure?'), message, show_copy_button=False):
            return
        first_sel_row = self.prefix_rules_tw.currentRow()
        for selrow in reversed(rows):
            self.prefix_rules_tw.removeRow(selrow.row())
        if first_sel_row < self.prefix_rules_tw.rowCount():
            self.prefix_rules_select_and_scroll_to_row(first_sel_row)
        elif self.prefix_rules_tw.rowCount() > 0:
            self.prefix_rules_select_and_scroll_to_row(first_sel_row - 1)

    def prefix_rules_get_data(self):
        data_items = []
        for row in range(self.prefix_rules_tw.rowCount()):
            data = self.prefix_rules_convert_row_to_data(row)
            data_items.append(
                               {'ordinal':data['ordinal'],
                                'enabled':data['enabled'],
                                'name':data['name'],
                                'field':data['field'],
                                'pattern':data['pattern'],
                                'prefix':data['prefix']})
        return data_items

    def prefix_rules_move_row_down(self):
        self.prefix_rules_tw.setFocus()
        rows = self.prefix_rules_tw.selectionModel().selectedRows()
        if len(rows) == 0:
            return
        last_sel_row = rows[-1].row()
        if last_sel_row == self.prefix_rules_tw.rowCount() - 1:
            return

        self.prefix_rules_tw.blockSignals(True)
        for selrow in reversed(rows):
            dest_row = selrow.row() + 1
            src_row = selrow.row()

            # Save the contents of the destination row
            saved_data = self.prefix_rules_convert_row_to_data(dest_row)

            # Remove the destination row
            self.prefix_rules_tw.removeRow(dest_row)

            # Insert a new row at the original location
            self.prefix_rules_tw.insertRow(src_row)

            # Populate it with the saved data
            self.populate_prefix_rules_table_row(src_row, saved_data)
        self.blockSignals(False)
        scroll_to_row = last_sel_row + 1
        if scroll_to_row < self.prefix_rules_tw.rowCount() - 1:
            scroll_to_row = scroll_to_row + 1
        self.prefix_rules_tw.scrollToItem(self.prefix_rules_tw.item(scroll_to_row, 0))

    def prefix_rules_move_row_up(self):
        self.prefix_rules_tw.setFocus()
        rows = self.prefix_rules_tw.selectionModel().selectedRows()
        if len(rows) == 0:
            return
        first_sel_row = rows[0].row()
        if first_sel_row <= 0:
            return
        self.prefix_rules_tw.blockSignals(True)
        for selrow in rows:
            # Save the row above
            saved_data = self.prefix_rules_convert_row_to_data(selrow.row() - 1)

            # Add a row below us with the source data
            self.prefix_rules_tw.insertRow(selrow.row() + 1)
            self.populate_prefix_rules_table_row(selrow.row() + 1, saved_data)

            # Delete the row above
            self.prefix_rules_tw.removeRow(selrow.row() - 1)
        self.blockSignals(False)

        scroll_to_row = first_sel_row - 1
        if scroll_to_row > 0:
            scroll_to_row = scroll_to_row - 1
        self.prefix_rules_tw.scrollToItem(self.prefix_rules_tw.item(scroll_to_row, 0))

    def prefix_rules_resize_name(self, scale):
        current_width = self.prefix_rules_tw.columnWidth(1)
        self.prefix_rules_tw.setColumnWidth(1, min(225,int(current_width * scale)))

    def prefix_rules_rule_name_edited(self):
        current_row = self.prefix_rules_tw.currentRow()
        self.prefix_rules_tw.cellWidget(current_row,1).home(False)
        self.prefix_rules_tw.setFocus()
        self.prefix_rules_select_and_scroll_to_row(current_row)

    def prefix_rules_select_and_scroll_to_row(self, row):
        self.prefix_rules_tw.selectRow(row)
        self.prefix_rules_tw.scrollToItem(self.prefix_rules_tw.currentItem())

    def prefix_rules_source_index_changed(self, combo, row, col, pattern=''):
        # Populate the Pattern field based upon the Source field

        source_field = str(combo.currentText())
        if source_field == '':
            values = []
        elif source_field == 'Tags':
            values = sorted(self.db.all_tags(), key=sort_key)
        else:
            if self.eligible_custom_fields[source_field]['datatype'] in ['enumeration', 'text']:
                values = self.db.all_custom(self.db.field_metadata.key_to_label(
                                            self.eligible_custom_fields[source_field]['field']))
                values = sorted(values, key=sort_key)
            elif self.eligible_custom_fields[source_field]['datatype'] in ['bool']:
                values = ['True','False','unspecified']
            elif self.eligible_custom_fields[source_field]['datatype'] in ['datetime']:
                values = ['any date','unspecified']
            elif self.eligible_custom_fields[source_field]['datatype'] in ['composite']:
                values = ['any value','unspecified']

        values_combo = PrefixRulesComboBox(self, values, pattern)
        self.prefix_rules_tw.setCellWidget(row, 4, values_combo)

    def read_source_field_changed(self,new_index):
        '''
        Process changes in the read_source_field combo box
        Currently using QLineEdit for all field types
        Possible to modify to switch QWidget type
        '''
        new_source = unicode(self.read_source_field.currentText())
        read_source_spec = self.read_source_fields[new_source]
        self.read_source_field_name = read_source_spec['field']

        # Change pattern input widget to match the source field datatype
        if read_source_spec['datatype'] in ['bool','composite','datetime','text']:
            if not isinstance(self.read_pattern, QLineEdit):
                self.read_spec_hl.removeWidget(self.read_pattern)
                dw = QLineEdit(self)
                dw.setObjectName('read_pattern')
                dw.setToolTip('Pattern for read book')
                self.read_pattern = dw
                self.read_spec_hl.addWidget(dw)

    def exclude_source_field_changed(self,new_index):
        '''
        Process changes in the exclude_source_field combo box
        Currently using QLineEdit for all field types
        Possible to modify to switch QWidget type
        '''
        new_source = str(self.exclude_source_field.currentText())
        self.exclude_source_field_name = new_source
        if new_source > '':
            exclude_source_spec = self.exclude_source_fields[unicode(new_source)]
            self.exclude_source_field_name = exclude_source_spec['field']
            self.exclude_pattern.setEnabled(True)

            # Change pattern input widget to match the source field datatype
            if exclude_source_spec['datatype'] in ['bool','composite','datetime','text']:
                if not isinstance(self.exclude_pattern, QLineEdit):
                    self.exclude_spec_hl.removeWidget(self.exclude_pattern)
                    dw = QLineEdit(self)
                    dw.setObjectName('exclude_pattern')
                    dw.setToolTip('Exclusion pattern')
                    self.exclude_pattern = dw
                    self.exclude_spec_hl.addWidget(dw)
        else:
            self.exclude_pattern.setEnabled(False)

    def generate_descriptions_changed(self,new_state):
        '''
        Process changes to Descriptions section
        0: unchecked
        2: checked
        '''

        return
        '''
        if new_state == 0:
            # unchecked
            self.merge_source_field.setEnabled(False)
            self.merge_before.setEnabled(False)
            self.merge_after.setEnabled(False)
            self.include_hr.setEnabled(False)
        elif new_state == 2:
            # checked
            self.merge_source_field.setEnabled(True)
            self.merge_before.setEnabled(True)
            self.merge_after.setEnabled(True)
            self.include_hr.setEnabled(True)
        '''

    def header_note_source_field_changed(self,new_index):
        '''
        Process changes in the header_note_source_field combo box
        '''
        new_source = str(self.header_note_source_field.currentText())
        self.header_note_source_field_name = new_source
        if new_source > '':
            header_note_source_spec = self.header_note_source_fields[unicode(new_source)]
            self.header_note_source_field_name = header_note_source_spec['field']

    def merge_source_field_changed(self,new_index):
        '''
        Process changes in the merge_source_field combo box
        '''
        new_source = str(self.merge_source_field.currentText())
        self.merge_source_field_name = new_source
        if new_source > '':
            merge_source_spec = self.merge_source_fields[unicode(new_source)]
            self.merge_source_field_name = merge_source_spec['field']
            if not self.merge_before.isChecked() and not self.merge_after.isChecked():
                self.merge_after.setChecked(True)
            self.merge_before.setEnabled(True)
            self.merge_after.setEnabled(True)
            self.include_hr.setEnabled(True)

        else:
            self.merge_before.setEnabled(False)
            self.merge_after.setEnabled(False)
            self.include_hr.setEnabled(False)

    def thumb_width_changed(self,new_value):
        '''
        Process changes in the thumb_width spin box
        '''
        pass


class CheckableTableWidgetItem(QTableWidgetItem):
    '''
    Borrowed from kiwidude
    '''

    def __init__(self, checked=False, is_tristate=False):
        QTableWidgetItem.__init__(self, '')
        self.setFlags(Qt.ItemFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled ))
        if is_tristate:
            self.setFlags(self.flags() | Qt.ItemIsTristate)
        if checked:
            self.setCheckState(Qt.Checked)
        else:
            if is_tristate and checked is None:
                self.setCheckState(Qt.PartiallyChecked)
            else:
                self.setCheckState(Qt.Unchecked)

    def get_boolean_value(self):
        '''
        Return a boolean value indicating whether checkbox is checked
        If this is a tristate checkbox, a partially checked value is returned as None
        '''
        if self.checkState() == Qt.PartiallyChecked:
            return None
        else:
            return self.checkState() == Qt.Checked

class NoWheelComboBox(QComboBox):

    def wheelEvent (self, event):
        # Disable the mouse wheel on top of the combo box changing selection as plays havoc in a grid
        event.ignore()

class PrefixRulesComboBox(NoWheelComboBox):
    # Caller is responsible for providing the list in the preferred order
    def __init__(self, parent, items, selected_text,insert_blank=True):
        NoWheelComboBox.__init__(self, parent)
        self.populate_combo(items, selected_text, insert_blank)

    def populate_combo(self, items, selected_text, insert_blank):
        if insert_blank:
            self.addItems([''])
        self.addItems(items)
        if selected_text:
            idx = self.findText(selected_text)
            self.setCurrentIndex(idx)
        else:
            self.setCurrentIndex(0)


