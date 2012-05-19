#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.conversion.config import load_defaults
from calibre.gui2 import gprefs

from catalog_epub_mobi_ui import Ui_Form
from PyQt4.Qt import QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit, \
                     QRadioButton, QWidget

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
        option_fields += zip(['exclude_genre'],['\[.+\]'],['line_edit'])
        option_fields += zip(['exclude_pattern'],[None],['line_edit'])
        option_fields += zip(['exclude_tags'],['~,'+_('Catalog')],['line_edit'])
        option_fields += zip(['read_pattern'],['+'],['line_edit'])
        option_fields += zip(['wishlist_tag'],['Wishlist'],['line_edit'])

        # SpinBoxControls
        option_fields += zip(['thumb_width'],[1.00],['spin_box'])

        self.OPTION_FIELDS = option_fields

    def initialize(self, name, db):
        '''

        CheckBoxControls (c_type: check_box):
            ['generate_titles','generate_series','generate_genres',
                            'generate_recently_added','generate_descriptions','include_hr']
        ComboBoxControls (c_type: combo_box):
            ['read_source_field','exclude_source_field','header_note_source_field',
                            'merge_source_field']
        LineEditControls (c_type: line_edit):
            ['exclude_genre','exclude_pattern','exclude_tags','read_pattern',
                            'wishlist_tag']
        RadioButtonControls (c_type: radio_button):
            ['merge_before','merge_after']
        SpinBoxControls (c_type: spin_box):
            ['thumb_width']

        '''

        self.name = name
        self.db = db
        self.populateComboBoxes()

        # Update dialog fields from stored options
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

        # Init self.read_source_field_name
        cs = unicode(self.read_source_field.currentText())
        read_source_spec = self.read_source_fields[cs]
        self.read_source_field_name = read_source_spec['field']

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

    def options(self):
        # Save/return the current options
        # exclude_genre stores literally
        # generate_titles, generate_recently_added store as True/False
        # others store as lists

        opts_dict = {}
        # Save values to gprefs
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
            gprefs.set(self.name + '_' + c_name, opt_value)

            # Construct opts object
            if c_name == 'exclude_tags':
                # store as list
                opts_dict[c_name] = opt_value.split(',')
            else:
                opts_dict[c_name] = opt_value

        # Generate markers for hybrids
        opts_dict['read_book_marker'] = "%s:%s" % (self.read_source_field_name,
                                                   self.read_pattern.text())
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
            for opt in sorted(opts_dict.keys()):
                print " %s: %s" % (opt, repr(opts_dict[opt]))
        return opts_dict

    def populateComboBoxes(self):
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

        all_custom_fields = self.db.custom_field_keys()
        # Populate the 'Read book' hybrid
        custom_fields = {}
        custom_fields['Tag'] = {'field':'tag', 'datatype':u'text'}
        for custom_field in all_custom_fields:
            field_md = self.db.metadata_for_field(custom_field)
            if field_md['datatype'] in ['bool','composite','datetime','enumeration','text']:
                custom_fields[field_md['name']] = {'field':custom_field,
                                                   'datatype':field_md['datatype']}
        # Add the sorted eligible fields to the combo box
        for cf in sorted(custom_fields):
            self.read_source_field.addItem(cf)
        self.read_source_fields = custom_fields
        self.read_source_field.currentIndexChanged.connect(self.read_source_field_changed)


        # Populate the 'Excluded books' hybrid
        custom_fields = {}
        for custom_field in all_custom_fields:
            field_md = self.db.metadata_for_field(custom_field)
            if field_md['datatype'] in ['bool','composite','datetime','enumeration','text']:
                custom_fields[field_md['name']] = {'field':custom_field,
                                                   'datatype':field_md['datatype']}
        # Blank field first
        self.exclude_source_field.addItem('')
        # Add the sorted eligible fields to the combo box
        for cf in sorted(custom_fields):
            self.exclude_source_field.addItem(cf)
        self.exclude_source_fields = custom_fields
        self.exclude_source_field.currentIndexChanged.connect(self.exclude_source_field_changed)


        # Populate the 'Header note' combo box
        custom_fields = {}
        for custom_field in all_custom_fields:
            field_md = self.db.metadata_for_field(custom_field)
            if field_md['datatype'] in ['bool','composite','datetime','enumeration','text']:
                custom_fields[field_md['name']] = {'field':custom_field,
                                                   'datatype':field_md['datatype']}
        # Blank field first
        self.header_note_source_field.addItem('')
        # Add the sorted eligible fields to the combo box
        for cf in sorted(custom_fields):
            self.header_note_source_field.addItem(cf)
        self.header_note_source_fields = custom_fields
        self.header_note_source_field.currentIndexChanged.connect(self.header_note_source_field_changed)


        # Populate the 'Merge with Comments' combo box
        custom_fields = {}
        for custom_field in all_custom_fields:
            field_md = self.db.metadata_for_field(custom_field)
            if field_md['datatype'] in ['text','comments','composite']:
                custom_fields[field_md['name']] = {'field':custom_field,
                                                   'datatype':field_md['datatype']}
        # Blank field first
        self.merge_source_field.addItem('')
        # Add the sorted eligible fields to the combo box
        for cf in sorted(custom_fields):
            self.merge_source_field.addItem(cf)
        self.merge_source_fields = custom_fields
        self.merge_source_field.currentIndexChanged.connect(self.merge_source_field_changed)
        self.merge_before.setEnabled(False)
        self.merge_after.setEnabled(False)
        self.include_hr.setEnabled(False)

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
        Process changes in the header_note_source_field combo box
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
