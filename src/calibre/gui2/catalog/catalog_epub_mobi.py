#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, sys

from functools import partial

from calibre.ebooks.conversion.config import load_defaults
from calibre.gui2 import gprefs, info_dialog, open_url, question_dialog
from calibre.utils.icu import sort_key

from catalog_epub_mobi_ui import Ui_Form
from PyQt4.Qt import (Qt, QAbstractItemView, QCheckBox, QComboBox,
        QDoubleSpinBox, QIcon, QLineEdit, QObject, QRadioButton, QSize, QSizePolicy,
        QTableWidget, QTableWidgetItem, QTextEdit, QToolButton, QUrl,
        QVBoxLayout, QWidget,
        SIGNAL)

class PluginWidget(QWidget,Ui_Form):

    TITLE = _('E-book options')
    HELP  = _('Options specific to')+' AZW3/EPUB/MOBI '+_('output')
    DEBUG = False

    # Output synced to the connected device?
    sync_enabled = True

    # Formats supported by this plugin
    formats = set(['azw3','epub','mobi'])

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)
        self._initControlArrays()

    def _initControlArrays(self):
        # Default values for controls
        CheckBoxControls = []
        ComboBoxControls = []
        DoubleSpinBoxControls = []
        LineEditControls = []
        RadioButtonControls = []
        TableWidgetControls = []
        TextEditControls = []

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
            elif type(self.__dict__[item]) is QTextEdit:
                TextEditControls.append(str(self.__dict__[item].objectName()))

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

        # TextEditControls
        #option_fields += zip(['exclude_genre_results'],['excluded genres will appear here'],['text_edit'])

        # SpinBoxControls
        option_fields += zip(['thumb_width'],[1.00],['spin_box'])

        # Exclusion rules
        option_fields += zip(['exclusion_rules_tw'],
                             [{'ordinal':0,
                               'enabled':True,
                               'name':'Catalogs',
                               'field':'Tags',
                               'pattern':'Catalog'},],
                             ['table_widget'])

        # Prefix rules
        option_fields += zip(['prefix_rules_tw','prefix_rules_tw'],
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
                               'prefix':u'\u00d7'},],
                             ['table_widget','table_widget'])

        self.OPTION_FIELDS = option_fields

    def construct_tw_opts_object(self, c_name, opt_value, opts_dict):
        '''
        Build an opts object from the UI settings to pass to the catalog builder
        Handles two types of rules sets, with and without ['prefix'] field
        Store processed opts object to opt_dict
        '''
        rule_set = []
        for stored_rule in opt_value:
            rule = stored_rule.copy()
            # Skip disabled and incomplete rules
            if not rule['enabled']:
                continue
            elif not rule['field'] or not rule['pattern']:
                continue
            elif 'prefix' in rule and rule['prefix'] is None:
                continue
            else:
                if rule['field'] != 'Tags':
                    # Look up custom column friendly name
                    rule['field'] = self.eligible_custom_fields[rule['field']]['field']
                    if rule['pattern'] in [_('any value'),_('any date')]:
                        rule_pattern = '.*'
                    elif rule['pattern'] == _('unspecified'):
                        rule['pattern'] = 'None'
            if 'prefix' in rule:
                pr = (rule['name'],rule['field'],rule['pattern'],rule['prefix'])
            else:
                pr = (rule['name'],rule['field'],rule['pattern'])
            rule_set.append(pr)
        opt_value = tuple(rule_set)
        # Strip off the trailing '_tw'
        opts_dict[c_name[:-3]] = opt_value

    def exclude_genre_changed(self, regex):
        """ Dynamically compute excluded genres.

        Run exclude_genre regex against db.all_tags() to show excluded tags.
        PROVISIONAL CODE, NEEDS TESTING

        Args:
         regex (QLineEdit.text()): regex to compile, compute

        Output:
         self.exclude_genre_results (QLabel): updated to show tags to be excluded as genres
        """
        if not regex:
            self.exclude_genre_results.clear()
            self.exclude_genre_results.setText(_('No genres will be excluded'))
            return

        results = _('Regex does not match any tags in database')
        try:
            pattern = re.compile((str(regex)))
        except:
            results = _("regex error: %s") % sys.exc_info()[1]
        else:
            excluded_tags = []
            for tag in self.all_tags:
                hit = pattern.search(tag)
                if hit:
                    excluded_tags.append(hit.string)
            if excluded_tags:
                if set(excluded_tags) == set(self.all_tags):
                    results = _("All genres will be excluded")
                else:
                    results = ', '.join(sorted(excluded_tags))
        finally:
            if self.DEBUG:
                print(results)
            self.exclude_genre_results.clear()
            self.exclude_genre_results.setText(results)

    def exclude_genre_reset(self):
        for default in self.OPTION_FIELDS:
            if default[0] == 'exclude_genre':
                self.exclude_genre.setText(default[1])
                break

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

    def initialize(self, name, db):
        '''

        CheckBoxControls (c_type: check_box):
            ['generate_titles','generate_series','generate_genres',
             'generate_recently_added','generate_descriptions','include_hr']
        ComboBoxControls (c_type: combo_box):
            ['exclude_source_field','header_note_source_field',
             'merge_source_field']
        LineEditControls (c_type: line_edit):
            ['exclude_genre']
        RadioButtonControls (c_type: radio_button):
            ['merge_before','merge_after','generate_new_cover', 'use_existing_cover']
        SpinBoxControls (c_type: spin_box):
            ['thumb_width']
        TableWidgetControls (c_type: table_widget):
            ['exclusion_rules_tw','prefix_rules_tw']
        TextEditControls (c_type: text_edit):
            ['exclude_genre_results']

        '''
        self.name = name
        self.db = db
        self.all_tags = db.all_tags()
        self.fetchEligibleCustomFields()
        self.populate_combo_boxes()

        # Update dialog fields from stored options
        exclusion_rules = []
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
            if c_type == 'table_widget':
                if c_name == 'exclusion_rules_tw':
                    if opt_value not in exclusion_rules:
                        exclusion_rules.append(opt_value)
                if c_name == 'prefix_rules_tw':
                    if opt_value not in prefix_rules:
                        prefix_rules.append(opt_value)

        # Add icon to the reset button, hook textChanged signal
        self.reset_exclude_genres_tb.setIcon(QIcon(I('trash.png')))
        self.reset_exclude_genres_tb.clicked.connect(self.exclude_genre_reset)

        # Hook textChanged event for exclude_genre QLineEdit
        self.exclude_genre.textChanged.connect(self.exclude_genre_changed)

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

        # Initialize exclusion rules
        self.exclusion_rules_table = ExclusionRules(self.exclusion_rules_gb,
            "exclusion_rules_tw",exclusion_rules, self.eligible_custom_fields,self.db)

        # Initialize prefix rules
        self.prefix_rules_table = PrefixRules(self.prefix_rules_gb,
            "prefix_rules_tw",prefix_rules, self.eligible_custom_fields,self.db)

        # Initialize excluded genres preview
        self.exclude_genre_changed(unicode(getattr(self, 'exclude_genre').text()).strip())

    def options(self):
        # Save/return the current options
        # exclude_genre stores literally
        # Section switches store as True/False
        # others store as lists

        opts_dict = {}
        prefix_rules_processed = False
        exclusion_rules_processed = False

        for opt in self.OPTION_FIELDS:
            c_name, c_def, c_type = opt
            if c_name == 'exclusion_rules_tw' and exclusion_rules_processed:
                continue
            if c_name == 'prefix_rules_tw' and prefix_rules_processed:
                continue

            if c_type in ['check_box', 'radio_button']:
                opt_value = getattr(self, c_name).isChecked()
            elif c_type in ['combo_box']:
                opt_value = unicode(getattr(self,c_name).currentText()).strip()
            elif c_type in ['line_edit']:
                opt_value = unicode(getattr(self, c_name).text()).strip()
            elif c_type in ['spin_box']:
                opt_value = unicode(getattr(self, c_name).value())
            elif c_type in ['table_widget']:
                if c_name == 'prefix_rules_tw':
                    opt_value = self.prefix_rules_table.get_data()
                    prefix_rules_processed = True
                if c_name == 'exclusion_rules_tw':
                    opt_value = self.exclusion_rules_table.get_data()
                    exclusion_rules_processed = True

            # Store UI values to gui.json in config dir
            gprefs.set(self.name + '_' + c_name, opt_value)

            # Construct opts object for catalog builder
            if c_name in ['exclusion_rules_tw','prefix_rules_tw']:
                self.construct_tw_opts_object(c_name, opt_value, opts_dict)
            else:
                opts_dict[c_name] = opt_value

        # Generate specs for merge_comments, header_note_source_field
        checked = ''
        if self.merge_before.isChecked():
            checked = 'before'
        elif self.merge_after.isChecked():
            checked = 'after'
        include_hr = self.include_hr.isChecked()
        opts_dict['merge_comments_rule'] = "%s:%s:%s" % \
            (self.merge_source_field_name, checked, include_hr)

        opts_dict['header_note_source_field'] = self.header_note_source_field_name

        # Fix up exclude_genre regex if blank. Assume blank = no exclusions
        if opts_dict['exclude_genre'] == '':
            opts_dict['exclude_genre'] = 'a^'

        # Append the output profile
        try:
            opts_dict['output_profile'] = [load_defaults('page_setup')['output_profile']]
        except:
            opts_dict['output_profile'] = ['default']

        if self.DEBUG:
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

    def show_help(self):
        '''
        Display help file
        '''
        url = 'file:///' + P('catalog/help_epub_mobi.html')
        open_url(QUrl(url))

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

class ComboBox(NoWheelComboBox):
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

class GenericRulesTable(QTableWidget):
    '''
    Generic methods for managing rows in a QTableWidget
    '''
    DEBUG = False
    MAXIMUM_TABLE_HEIGHT = 113
    NAME_FIELD_WIDTH = 225

    def __init__(self, parent_gb, object_name, rules, eligible_custom_fields, db):
        self.rules = rules
        self.eligible_custom_fields = eligible_custom_fields
        self.db = db
        QTableWidget.__init__(self)
        self.setObjectName(object_name)
        self.layout = parent_gb.layout()

        # Add ourselves to the layout
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        #sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)
        self.setMaximumSize(QSize(16777215, self.MAXIMUM_TABLE_HEIGHT))

        self.setColumnCount(0)
        self.setRowCount(0)
        self.layout.addWidget(self)

        self.last_row_selected = self.currentRow()
        self.last_rows_selected = self.selectionModel().selectedRows()

        self._init_controls()

        # Hook check_box changes
        QObject.connect(self, SIGNAL('cellChanged(int,int)'), self.enabled_state_changed)

    def _init_controls(self):
        # Add the control set
        vbl = QVBoxLayout()
        self.move_rule_up_tb = QToolButton()
        self.move_rule_up_tb.setObjectName("move_rule_up_tb")
        self.move_rule_up_tb.setToolTip('Move rule up')
        self.move_rule_up_tb.setIcon(QIcon(I('arrow-up.png')))
        self.move_rule_up_tb.clicked.connect(self.move_row_up)
        vbl.addWidget(self.move_rule_up_tb)

        self.add_rule_tb = QToolButton()
        self.add_rule_tb.setObjectName("add_rule_tb")
        self.add_rule_tb.setToolTip('Add a new rule')
        self.add_rule_tb.setIcon(QIcon(I('plus.png')))
        self.add_rule_tb.clicked.connect(self.add_row)
        vbl.addWidget(self.add_rule_tb)

        self.delete_rule_tb = QToolButton()
        self.delete_rule_tb.setObjectName("delete_rule_tb")
        self.delete_rule_tb.setToolTip('Delete selected rule')
        self.delete_rule_tb.setIcon(QIcon(I('list_remove.png')))
        self.delete_rule_tb.clicked.connect(self.delete_row)
        vbl.addWidget(self.delete_rule_tb)

        self.move_rule_down_tb = QToolButton()
        self.move_rule_down_tb.setObjectName("move_rule_down_tb")
        self.move_rule_down_tb.setToolTip('Move rule down')
        self.move_rule_down_tb.setIcon(QIcon(I('arrow-down.png')))
        self.move_rule_down_tb.clicked.connect(self.move_row_down)
        vbl.addWidget(self.move_rule_down_tb)

        self.layout.addLayout(vbl)

    def add_row(self):
        self.setFocus()
        row = self.last_row_selected + 1
        if self.DEBUG:
            print("%s:add_row(): at row: %d" % (self.objectName(), row))
        self.insertRow(row)
        self.populate_table_row(row, self.create_blank_row_data())
        self.select_and_scroll_to_row(row)
        self.resizeColumnsToContents()
        # In case table was empty
        self.horizontalHeader().setStretchLastSection(True)

    def delete_row(self):
        if self.DEBUG:
            print("%s:delete_row()" % self.objectName())

        self.setFocus()
        rows = self.last_rows_selected
        if len(rows) == 0:
            return

        first = rows[0].row() + 1
        last = rows[-1].row() + 1

        first_rule_name = unicode(self.cellWidget(first-1,self.COLUMNS['NAME']['ordinal']).text()).strip()
        message = _("Are you sure you want to delete '%s'?") % (first_rule_name)
        if len(rows) > 1:
            message = _('Are you sure you want to delete rules #%d-%d?') % (first, last)
        if not question_dialog(self, _('Delete Rule'), message, show_copy_button=False):
            return
        first_sel_row = self.currentRow()
        for selrow in reversed(rows):
            self.removeRow(selrow.row())
        if first_sel_row < self.rowCount():
            self.select_and_scroll_to_row(first_sel_row)
        elif self.rowCount() > 0:
            self.select_and_scroll_to_row(first_sel_row - 1)

    def enabled_state_changed(self, row, col):
        if col in [self.COLUMNS['ENABLED']['ordinal']]:
            self.select_and_scroll_to_row(row)
            if self.DEBUG:
                print("%s:enabled_state_changed(): row %d col %d" %
                      (self.objectName(), row, col))

    def focusInEvent(self,e):
        if self.DEBUG:
            print("%s:focusInEvent()" % self.objectName())

    def focusOutEvent(self,e):
        # Override of QTableWidget method - clear selection when table loses focus
        self.last_row_selected = self.currentRow()
        self.last_rows_selected = self.selectionModel().selectedRows()
        self.clearSelection()
        if self.DEBUG:
            print("%s:focusOutEvent(): self.last_row_selected: %d" % (self.objectName(),self.last_row_selected))

    def move_row_down(self):
        self.setFocus()
        rows = self.last_rows_selected
        if len(rows) == 0:
            return
        last_sel_row = rows[-1].row()
        if last_sel_row == self.rowCount() - 1:
            return

        self.blockSignals(True)
        for selrow in reversed(rows):
            dest_row = selrow.row() + 1
            src_row = selrow.row()
            if self.DEBUG:
                print("%s:move_row_down() %d -> %d" % (self.objectName(),src_row, dest_row))

            # Save the contents of the destination row
            saved_data = self.convert_row_to_data(dest_row)

            # Remove the destination row
            self.removeRow(dest_row)

            # Insert a new row at the original location
            self.insertRow(src_row)

            # Populate it with the saved data
            self.populate_table_row(src_row, saved_data)

        scroll_to_row = last_sel_row + 1
        self.select_and_scroll_to_row(scroll_to_row)
        self.blockSignals(False)

    def move_row_up(self):
        self.setFocus()
        rows = self.last_rows_selected
        if len(rows) == 0:
            return
        first_sel_row = rows[0].row()
        if first_sel_row <= 0:
            return
        self.blockSignals(True)

        for selrow in rows:
            if self.DEBUG:
                print("%s:move_row_up() %d -> %d" % (self.objectName(),selrow.row(), selrow.row()-1))

            # Save the row above
            saved_data = self.convert_row_to_data(selrow.row() - 1)

            # Add a row below us with the source data
            self.insertRow(selrow.row() + 1)
            self.populate_table_row(selrow.row() + 1, saved_data)

            # Delete the row above
            self.removeRow(selrow.row() - 1)

        scroll_to_row = first_sel_row
        if scroll_to_row > 0:
            scroll_to_row = scroll_to_row - 1
        self.select_and_scroll_to_row(scroll_to_row)
        self.blockSignals(False)

    def populate_table(self):
        # Format of rules list is different if default values vs retrieved JSON
        # Hack to normalize list style
        rules = self.rules
        if rules and type(rules[0]) is list:
            rules = rules[0]
        self.setFocus()
        rules = sorted(rules, key=lambda k: k['ordinal'])
        for row, rule in enumerate(rules):
            self.insertRow(row)
            self.select_and_scroll_to_row(row)
            self.populate_table_row(row, rule)
        self.selectRow(0)

    def resize_name(self):
        self.setColumnWidth(1, self.NAME_FIELD_WIDTH)

    def rule_name_edited(self):
        if self.DEBUG:
            print("%s:rule_name_edited()" % self.objectName())

        current_row = self.currentRow()
        self.cellWidget(current_row,1).home(False)
        self.select_and_scroll_to_row(current_row)

    def select_and_scroll_to_row(self, row):
        self.setFocus()
        self.selectRow(row)
        self.scrollToItem(self.currentItem())
        self.last_row_selected = self.currentRow()
        self.last_rows_selected = self.selectionModel().selectedRows()

    def _source_index_changed(self, combo):
        # Figure out which row we're in
        for row in range(self.rowCount()):
            if self.cellWidget(row, self.COLUMNS['FIELD']['ordinal']) is combo:
                break

        if self.DEBUG:
            print("%s:_source_index_changed(): calling source_index_changed with row: %d " %
                  (self.objectName(), row))

        self.source_index_changed(combo, row)

    def source_index_changed(self, combo, row, pattern=''):
        # Populate the Pattern field based upon the Source field

        source_field = str(combo.currentText())
        if source_field == '':
            values = []
        elif source_field == 'Tags':
            values = sorted(self.db.all_tags(), key=sort_key)
        else:
            if self.eligible_custom_fields[unicode(source_field)]['datatype'] in ['enumeration', 'text']:
                values = self.db.all_custom(self.db.field_metadata.key_to_label(
                                            self.eligible_custom_fields[unicode(source_field)]['field']))
                values = sorted(values, key=sort_key)
            elif self.eligible_custom_fields[unicode(source_field)]['datatype'] in ['bool']:
                values = [_('True'),_('False'),_('unspecified')]
            elif self.eligible_custom_fields[unicode(source_field)]['datatype'] in ['composite']:
                values = [_('any value'),_('unspecified')]
            elif self.eligible_custom_fields[unicode(source_field)]['datatype'] in ['datetime']:
                values = [_('any date'),_('unspecified')]

        values_combo = ComboBox(self, values, pattern)
        values_combo.currentIndexChanged.connect(partial(self.values_index_changed, values_combo))
        self.setCellWidget(row, self.COLUMNS['PATTERN']['ordinal'], values_combo)
        self.select_and_scroll_to_row(row)

    def values_index_changed(self, combo):
        # After edit, select row
        for row in range(self.rowCount()):
            if self.cellWidget(row, self.COLUMNS['PATTERN']['ordinal']) is combo:
                self.select_and_scroll_to_row(row)
                break

        if self.DEBUG:
            print("%s:values_index_changed(): row %d " %
                  (self.objectName(), row))

class ExclusionRules(GenericRulesTable):

    COLUMNS = { 'ENABLED':{'ordinal': 0, 'name': ''},
                'NAME':   {'ordinal': 1, 'name': _('Name')},
                'FIELD':  {'ordinal': 2, 'name': _('Field')},
                'PATTERN':  {'ordinal': 3, 'name': _('Value')},}

    def __init__(self, parent_gb_hl, object_name, rules, eligible_custom_fields, db):
        super(ExclusionRules, self).__init__(parent_gb_hl, object_name, rules, eligible_custom_fields, db)
        self.setObjectName("exclusion_rules_table")
        self._init_table_widget()
        self._initialize()

    def _init_table_widget(self):
        header_labels = [self.COLUMNS[index]['name'] \
            for index in sorted(self.COLUMNS.keys(), key=lambda c: self.COLUMNS[c]['ordinal'])]
        self.setColumnCount(len(header_labels))
        self.setHorizontalHeaderLabels(header_labels)
        self.setSortingEnabled(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)

    def _initialize(self):
        self.populate_table()
        self.resizeColumnsToContents()
        self.resize_name()
        self.horizontalHeader().setStretchLastSection(True)
        self.clearSelection()

    def convert_row_to_data(self, row):
        data = self.create_blank_row_data()
        data['ordinal'] = row
        data['enabled'] = self.item(row,self.COLUMNS['ENABLED']['ordinal']).checkState() == Qt.Checked
        data['name'] = unicode(self.cellWidget(row,self.COLUMNS['NAME']['ordinal']).text()).strip()
        data['field'] = unicode(self.cellWidget(row,self.COLUMNS['FIELD']['ordinal']).currentText()).strip()
        data['pattern'] = unicode(self.cellWidget(row,self.COLUMNS['PATTERN']['ordinal']).currentText()).strip()
        return data

    def create_blank_row_data(self):
        data = {}
        data['ordinal'] = -1
        data['enabled'] = True
        data['name'] = 'New rule'
        data['field'] = ''
        data['pattern'] = ''
        return data

    def get_data(self):
        data_items = []
        for row in range(self.rowCount()):
            data = self.convert_row_to_data(row)
            data_items.append(
                               {'ordinal':data['ordinal'],
                                'enabled':data['enabled'],
                                'name':data['name'],
                                'field':data['field'],
                                'pattern':data['pattern']})
        return data_items

    def populate_table_row(self, row, data):

        def set_rule_name_in_row(row, col, name=''):
            rule_name = QLineEdit(name)
            rule_name.home(False)
            rule_name.editingFinished.connect(self.rule_name_edited)
            self.setCellWidget(row, col, rule_name)

        def set_source_field_in_row(row, col, field=''):
            source_combo = ComboBox(self, sorted(self.eligible_custom_fields.keys(), key=sort_key), field)
            source_combo.currentIndexChanged.connect(partial(self._source_index_changed, source_combo))
            self.setCellWidget(row, col, source_combo)
            return source_combo

        # Entry point
        self.blockSignals(True)

        # Enabled
        check_box = CheckableTableWidgetItem(data['enabled'])
        self.setItem(row, self.COLUMNS['ENABLED']['ordinal'], check_box)

        # Rule name
        set_rule_name_in_row(row, self.COLUMNS['NAME']['ordinal'], name=data['name'])

        # Source field
        source_combo = set_source_field_in_row(row, self.COLUMNS['FIELD']['ordinal'], field=data['field'])

        # Pattern
        # The contents of the Pattern field is driven by the Source field
        self.source_index_changed(source_combo, row, pattern=data['pattern'])

        self.blockSignals(False)

class PrefixRules(GenericRulesTable):

    COLUMNS = { 'ENABLED':{'ordinal': 0, 'name': ''},
                'NAME':   {'ordinal': 1, 'name': _('Name')},
                'PREFIX': {'ordinal': 2, 'name': _('Prefix')},
                'FIELD':  {'ordinal': 3, 'name': _('Field')},
                'PATTERN':{'ordinal': 4, 'name': _('Value')},}

    def __init__(self, parent_gb_hl, object_name, rules, eligible_custom_fields, db):
        super(PrefixRules, self).__init__(parent_gb_hl, object_name, rules, eligible_custom_fields, db)
        self.setObjectName("prefix_rules_table")
        self._init_table_widget()
        self._initialize()

    def _init_table_widget(self):
        header_labels = [self.COLUMNS[index]['name'] \
            for index in sorted(self.COLUMNS.keys(), key=lambda c: self.COLUMNS[c]['ordinal'])]
        self.setColumnCount(len(header_labels))
        self.setHorizontalHeaderLabels(header_labels)
        self.setSortingEnabled(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)

    def _initialize(self):
        self.generate_prefix_list()
        self.populate_table()
        self.resizeColumnsToContents()
        self.resize_name()
        self.horizontalHeader().setStretchLastSection(True)
        self.clearSelection()

    def convert_row_to_data(self, row):
        data = self.create_blank_row_data()
        data['ordinal'] = row
        data['enabled'] = self.item(row,self.COLUMNS['ENABLED']['ordinal']).checkState() == Qt.Checked
        data['name'] = unicode(self.cellWidget(row,self.COLUMNS['NAME']['ordinal']).text()).strip()
        data['prefix'] = unicode(self.cellWidget(row,self.COLUMNS['PREFIX']['ordinal']).currentText()).strip()
        data['field'] = unicode(self.cellWidget(row,self.COLUMNS['FIELD']['ordinal']).currentText()).strip()
        data['pattern'] = unicode(self.cellWidget(row,self.COLUMNS['PATTERN']['ordinal']).currentText()).strip()
        return data

    def create_blank_row_data(self):
        data = {}
        data['ordinal'] = -1
        data['enabled'] = True
        data['name'] = 'New rule'
        data['field'] = ''
        data['pattern'] = ''
        data['prefix'] = ''
        return data

    def generate_prefix_list(self):
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
            ('Arrow carriage return',u'\u21b5'),
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
            ('Cards clubs',u'\u2663'),
            ('Cards diamonds',u'\u2666'),
            ('Cards hearts',u'\u2665'),
            ('Cards spades',u'\u2660'),
            ('Caret',u'^'),
            ('Checkmark',u'\u2713'),
            ('Copyright circle c',u'\u00a9'),
            ('Copyright circle r',u'\u00ae'),
            ('Copyright trademark',u'\u2122'),
            ('Currency cent',u'\u00a2'),
            ('Currency dollar',u'$'),
            ('Currency euro',u'\u20ac'),
            ('Currency pound',u'\u00a3'),
            ('Currency yen',u'\u00a5'),
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
            ('Paragraph',u'\u00b6'),
            ('Percent',u'%'),
            ('Plus-or-minus',u'\u00b1'),
            ('Plus',u'+'),
            ('Punctuation colon',u':'),
            ('Punctuation colon-semi',u';'),
            ('Punctuation exclamation',u'!'),
            ('Punctuation question',u'?'),
            ('Punctuation period',u'.'),
            ('Punctuation slash back',u'\\'),
            ('Punctuation slash forward',u'/'),
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
        raw_prefix_list = sorted(raw_prefix_list, key=prefix_sorter)
        self.prefix_list = [x[1] for x in raw_prefix_list]

    def get_data(self):
        data_items = []
        for row in range(self.rowCount()):
            data = self.convert_row_to_data(row)
            data_items.append(
                               {'ordinal':data['ordinal'],
                                'enabled':data['enabled'],
                                'name':data['name'],
                                'field':data['field'],
                                'pattern':data['pattern'],
                                'prefix':data['prefix']})
        return data_items

    def populate_table_row(self, row, data):

        def set_prefix_field_in_row(row, col, field=''):
            prefix_combo = ComboBox(self, self.prefix_list, field)
            self.setCellWidget(row, col, prefix_combo)

        def set_rule_name_in_row(row, col, name=''):
            rule_name = QLineEdit(name)
            rule_name.home(False)
            rule_name.editingFinished.connect(self.rule_name_edited)
            self.setCellWidget(row, col, rule_name)

        def set_source_field_in_row(row, col, field=''):
            source_combo = ComboBox(self, sorted(self.eligible_custom_fields.keys(), key=sort_key), field)
            source_combo.currentIndexChanged.connect(partial(self._source_index_changed, source_combo))
            self.setCellWidget(row, col, source_combo)
            return source_combo

        # Entry point
        self.blockSignals(True)

        # Enabled
        self.setItem(row, self.COLUMNS['ENABLED']['ordinal'], CheckableTableWidgetItem(data['enabled']))

        # Rule name
        set_rule_name_in_row(row, self.COLUMNS['NAME']['ordinal'], name=data['name'])

        # Prefix
        set_prefix_field_in_row(row, self.COLUMNS['PREFIX']['ordinal'], field=data['prefix'])

        # Source field
        source_combo = set_source_field_in_row(row, self.COLUMNS['FIELD']['ordinal'], field=data['field'])

        # Pattern
        # The contents of the Pattern field is driven by the Source field
        self.source_index_changed(source_combo, row, pattern=data['pattern'])

        self.blockSignals(False)

