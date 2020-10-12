#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, sys

from functools import partial

from calibre.ebooks.conversion.config import load_defaults
from calibre.gui2 import gprefs, open_url, question_dialog, error_dialog
from calibre.utils.config import JSONConfig
from calibre.utils.icu import sort_key
from calibre.utils.localization import localize_user_manual_link
from polyglot.builtins import native_string_type, unicode_type, zip, range

from .catalog_epub_mobi_ui import Ui_Form
from PyQt5.Qt import (Qt, QAbstractItemView, QCheckBox, QComboBox,
        QDoubleSpinBox, QIcon, QInputDialog, QLineEdit, QRadioButton,
        QSize, QSizePolicy, QTableWidget, QTableWidgetItem, QTextEdit, QToolButton,
        QUrl, QVBoxLayout, QWidget)
try:
    from PyQt5 import sip
except ImportError:
    import sip


class PluginWidget(QWidget,Ui_Form):

    TITLE = _('E-book options')
    HELP  = _('Options specific to')+' AZW3/EPUB/MOBI '+_('output')
    DEBUG = False
    handles_scrolling = True

    # Output synced to the connected device?
    sync_enabled = True

    # Formats supported by this plugin
    formats = {'azw3','epub','mobi'}

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)
        self._initControlArrays()
        self.blocking_all_signals = None
        self.parent_ref = lambda: None

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
                CheckBoxControls.append(self.__dict__[item].objectName())
            elif type(self.__dict__[item]) is QComboBox:
                ComboBoxControls.append(self.__dict__[item].objectName())
            elif type(self.__dict__[item]) is QDoubleSpinBox:
                DoubleSpinBoxControls.append(self.__dict__[item].objectName())
            elif type(self.__dict__[item]) is QLineEdit:
                LineEditControls.append(self.__dict__[item].objectName())
            elif type(self.__dict__[item]) is QRadioButton:
                RadioButtonControls.append(self.__dict__[item].objectName())
            elif type(self.__dict__[item]) is QTableWidget:
                TableWidgetControls.append(self.__dict__[item].objectName())
            elif type(self.__dict__[item]) is QTextEdit:
                TextEditControls.append(self.__dict__[item].objectName())

        option_fields = list(zip(CheckBoxControls,
                            [True for i in CheckBoxControls],
                            ['check_box' for i in CheckBoxControls]))
        option_fields += list(zip(ComboBoxControls,
                            [None for i in ComboBoxControls],
                            ['combo_box' for i in ComboBoxControls]))
        option_fields += list(zip(RadioButtonControls,
                            [None for i in RadioButtonControls],
                            ['radio_button' for i in RadioButtonControls]))

        # LineEditControls
        option_fields += list(zip(['exclude_genre'],[r'\[.+\]|^\+$'],['line_edit']))

        # TextEditControls
        # option_fields += list(zip(['exclude_genre_results'],['excluded genres will appear here'],['text_edit']))

        # SpinBoxControls
        option_fields += list(zip(['thumb_width'],[1.00],['spin_box']))

        # Exclusion rules
        option_fields += list(zip(['exclusion_rules_tw'],
                             [{'ordinal':0,
                               'enabled':True,
                               'name':_('Catalogs'),
                               'field':_('Tags'),
                               'pattern':'Catalog'},],
                             ['table_widget']))

        # Prefix rules
        option_fields += list(zip(['prefix_rules_tw','prefix_rules_tw'],
                             [{'ordinal':0,
                               'enabled':True,
                               'name':_('Read book'),
                               'field':_('Tags'),
                               'pattern':'+',
                               'prefix':u'\u2713'},
                              {'ordinal':1,
                               'enabled':True,
                               'name':_('Wishlist item'),
                               'field':_('Tags'),
                               'pattern':'Wishlist',
                               'prefix':'\u00d7'},],
                             ['table_widget','table_widget']))

        self.OPTION_FIELDS = option_fields

    def block_all_signals(self, bool):
        if self.DEBUG:
            print("block_all_signals: %s" % bool)
        self.blocking_all_signals = bool
        for opt in self.OPTION_FIELDS:
            c_name, c_def, c_type = opt
            if c_name in ['exclusion_rules_tw', 'prefix_rules_tw']:
                continue
            getattr(self, c_name).blockSignals(bool)

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
            if not rule['field'] or not rule['pattern']:
                continue
            if 'prefix' in rule and rule['prefix'] is None:
                continue
            if rule['field'] != _('Tags'):
                # Look up custom column friendly name
                rule['field'] = self.eligible_custom_fields[rule['field']]['field']
                if rule['pattern'] in [_('any value'),_('any date')]:
                    rule['pattern'] = '.*'
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

    def exclude_genre_changed(self):
        """ Dynamically compute excluded genres.

        Run exclude_genre regex against selected genre_source_field to show excluded tags.

        Inputs:
            current regex
            genre_source_field

        Output:
         self.exclude_genre_results (QLabel): updated to show tags to be excluded as genres
        """
        def _truncated_results(excluded_tags, limit=180):
            '''
            Limit number of genres displayed to avoid dialog explosion
            '''
            start = []
            end = []
            lower = 0
            upper = len(excluded_tags) -1
            excluded_tags.sort()
            while True:
                if lower > upper:
                    break
                elif lower == upper:
                    start.append(excluded_tags[lower])
                    break
                start.append(excluded_tags[lower])
                end.insert(0,excluded_tags[upper])
                if len(', '.join(start)) + len(', '.join(end)) > limit:
                    break
                lower += 1
                upper -= 1
            if excluded_tags == start + end:
                return ', '.join(excluded_tags)
            else:
                return "%s  ...  %s" % (', '.join(start), ', '.join(end))

        results = _('No genres will be excluded')

        regex = unicode_type(getattr(self, 'exclude_genre').text()).strip()
        if not regex:
            self.exclude_genre_results.clear()
            self.exclude_genre_results.setText(results)
            return

        # Populate all_genre_tags from currently source
        if self.genre_source_field_name == _('Tags'):
            all_genre_tags = self.db.all_tags()
        else:
            all_genre_tags = list(self.db.all_custom(self.db.field_metadata.key_to_label(self.genre_source_field_name)))

        try:
            pattern = re.compile(regex)
        except:
            results = _("regex error: %s") % sys.exc_info()[1]
        else:
            excluded_tags = []
            for tag in all_genre_tags:
                hit = pattern.search(tag)
                if hit:
                    excluded_tags.append(hit.string)
            if excluded_tags:
                if set(excluded_tags) == set(all_genre_tags):
                    results = _("All genres will be excluded")
                else:
                    results = _truncated_results(excluded_tags)
        finally:
            if False and self.DEBUG:
                print("exclude_genre_changed(): %s" % results)
            self.exclude_genre_results.clear()
            self.exclude_genre_results.setText(results)

    def exclude_genre_reset(self):
        for default in self.OPTION_FIELDS:
            if default[0] == 'exclude_genre':
                self.exclude_genre.setText(default[1])
                break

    def fetch_eligible_custom_fields(self):
        self.all_custom_fields = self.db.custom_field_keys()
        custom_fields = {}
        custom_fields[_('Tags')] = {'field':'tag', 'datatype':u'text'}
        for custom_field in self.all_custom_fields:
            field_md = self.db.metadata_for_field(custom_field)
            if field_md['datatype'] in ['bool','composite','datetime','enumeration','text']:
                custom_fields[field_md['name']] = {'field':custom_field,
                                                   'datatype':field_md['datatype']}
        self.eligible_custom_fields = custom_fields

    def generate_descriptions_changed(self, enabled):
        '''
        Toggle Description-related controls
        '''
        self.header_note_source_field.setEnabled(enabled)
        self.include_hr.setEnabled(enabled)
        self.merge_after.setEnabled(enabled)
        self.merge_before.setEnabled(enabled)
        self.merge_source_field.setEnabled(enabled)
        self.thumb_width.setEnabled(enabled)

    def generate_genres_changed(self, enabled):
        '''
        Toggle Genres-related controls
        '''
        self.genre_source_field.setEnabled(enabled)

    def genre_source_field_changed(self,new_index):
        '''
        Process changes in the genre_source_field combo box
        Update Excluded genres preview
        '''
        new_source = self.genre_source_field.currentText()
        self.genre_source_field_name = new_source
        if new_source != _('Tags'):
            genre_source_spec = self.genre_source_fields[unicode_type(new_source)]
            self.genre_source_field_name = genre_source_spec['field']
        self.exclude_genre_changed()

    def get_format_and_title(self):
        current_format = None
        current_title = None
        parent = self.parent_ref()
        if parent is not None:
            current_title = parent.title.text().strip()
            current_format = parent.format.currentText().strip()
        return current_format, current_title

    def header_note_source_field_changed(self,new_index):
        '''
        Process changes in the header_note_source_field combo box
        '''
        new_source = self.header_note_source_field.currentText()
        self.header_note_source_field_name = new_source
        if new_source:
            header_note_source_spec = self.header_note_source_fields[unicode_type(new_source)]
            self.header_note_source_field_name = header_note_source_spec['field']

    def initialize(self, name, db):
        '''
        CheckBoxControls (c_type: check_box):
            ['cross_reference_authors',
             'generate_titles','generate_series','generate_genres',
             'generate_recently_added','generate_descriptions',
             'include_hr']
        ComboBoxControls (c_type: combo_box):
            ['exclude_source_field','genre_source_field',
             'header_note_source_field','merge_source_field']
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
        self.all_genre_tags = []
        self.fetch_eligible_custom_fields()
        self.populate_combo_boxes()

        # Update dialog fields from stored options, validating options for combo boxes
        # Hook all change events to self.settings_changed

        self.blocking_all_signals = True
        exclusion_rules = []
        prefix_rules = []
        for opt in self.OPTION_FIELDS:
            c_name, c_def, c_type = opt
            opt_value = gprefs.get(self.name + '_' + c_name, c_def)
            if c_type in ['check_box']:
                getattr(self, c_name).setChecked(eval(unicode_type(opt_value)))
                getattr(self, c_name).clicked.connect(partial(self.settings_changed, c_name))
            elif c_type in ['combo_box']:
                if opt_value is None:
                    index = 0
                    if c_name == 'genre_source_field':
                        index = self.genre_source_field.findText(_('Tags'))
                else:
                    index = getattr(self,c_name).findText(opt_value)
                    if index == -1:
                        if c_name == 'read_source_field':
                            index = self.read_source_field.findText(_('Tags'))
                        elif c_name == 'genre_source_field':
                            index = self.genre_source_field.findText(_('Tags'))
                getattr(self,c_name).setCurrentIndex(index)
                if c_name != 'preset_field':
                    getattr(self, c_name).currentIndexChanged.connect(partial(self.settings_changed, c_name))
            elif c_type in ['line_edit']:
                getattr(self, c_name).setText(opt_value if opt_value else '')
                getattr(self, c_name).editingFinished.connect(partial(self.settings_changed, c_name))
            elif c_type in ['radio_button'] and opt_value is not None:
                getattr(self, c_name).setChecked(opt_value)
                getattr(self, c_name).clicked.connect(partial(self.settings_changed, c_name))
            elif c_type in ['spin_box']:
                getattr(self, c_name).setValue(float(opt_value))
                getattr(self, c_name).valueChanged.connect(partial(self.settings_changed, c_name))
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

        # Hook Descriptions checkbox for related options, init
        self.generate_descriptions.clicked.connect(self.generate_descriptions_changed)
        self.generate_descriptions_changed(self.generate_descriptions.isChecked())

        # Init self.merge_source_field_name
        self.merge_source_field_name = ''
        cs = unicode_type(self.merge_source_field.currentText())
        if cs:
            merge_source_spec = self.merge_source_fields[cs]
            self.merge_source_field_name = merge_source_spec['field']

        # Init self.header_note_source_field_name
        self.header_note_source_field_name = ''
        cs = unicode_type(self.header_note_source_field.currentText())
        if cs:
            header_note_source_spec = self.header_note_source_fields[cs]
            self.header_note_source_field_name = header_note_source_spec['field']

        # Init self.genre_source_field_name
        self.genre_source_field_name = _('Tags')
        cs = unicode_type(self.genre_source_field.currentText())
        if cs != _('Tags'):
            genre_source_spec = self.genre_source_fields[cs]
            self.genre_source_field_name = genre_source_spec['field']

        # Hook Genres checkbox
        self.generate_genres.clicked.connect(self.generate_genres_changed)
        self.generate_genres_changed(self.generate_genres.isChecked())

        # Initialize exclusion rules
        self.exclusion_rules_table = ExclusionRules(self, self.exclusion_rules_gb,
            "exclusion_rules_tw", exclusion_rules)

        # Initialize prefix rules
        self.prefix_rules_table = PrefixRules(self, self.prefix_rules_gb,
            "prefix_rules_tw", prefix_rules)

        # Initialize excluded genres preview
        self.exclude_genre_changed()

        # Hook Preset signals
        self.preset_delete_pb.clicked.connect(self.preset_remove)
        self.preset_save_pb.clicked.connect(self.preset_save)
        self.preset_field.currentIndexChanged[native_string_type].connect(self.preset_change)

        self.blocking_all_signals = False

    def merge_source_field_changed(self,new_index):
        '''
        Process changes in the merge_source_field combo box
        '''
        new_source = self.merge_source_field.currentText()
        self.merge_source_field_name = new_source
        if new_source:
            merge_source_spec = self.merge_source_fields[unicode_type(new_source)]
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

    def options(self):
        '''
        Return, optionally save current options
        exclude_genre stores literally
        Section switches store as True/False
        others store as lists
        '''

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
                opt_value = unicode_type(getattr(self,c_name).currentText()).strip()
            elif c_type in ['line_edit']:
                opt_value = unicode_type(getattr(self, c_name).text()).strip()
            elif c_type in ['spin_box']:
                opt_value = unicode_type(getattr(self, c_name).value())
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

        # Generate specs for merge_comments, header_note_source_field, genre_source_field
        checked = ''
        if self.merge_before.isChecked():
            checked = 'before'
        elif self.merge_after.isChecked():
            checked = 'after'
        include_hr = self.include_hr.isChecked()

        # Init self.merge_source_field_name
        self.merge_source_field_name = ''
        cs = unicode_type(self.merge_source_field.currentText())
        if cs and cs in self.merge_source_fields:
            merge_source_spec = self.merge_source_fields[cs]
            self.merge_source_field_name = merge_source_spec['field']

        # Init self.header_note_source_field_name
        self.header_note_source_field_name = ''
        cs = unicode_type(self.header_note_source_field.currentText())
        if cs and cs in self.header_note_source_fields:
            header_note_source_spec = self.header_note_source_fields[cs]
            self.header_note_source_field_name = header_note_source_spec['field']

        # Init self.genre_source_field_name
        self.genre_source_field_name = _('Tags')
        cs = unicode_type(self.genre_source_field.currentText())
        if cs != _('Tags') and cs and cs in self.genre_source_fields:
            genre_source_spec = self.genre_source_fields[cs]
            self.genre_source_field_name = genre_source_spec['field']

        opts_dict['merge_comments_rule'] = "%s:%s:%s" % \
            (self.merge_source_field_name, checked, include_hr)

        opts_dict['header_note_source_field'] = self.header_note_source_field_name

        opts_dict['genre_source_field'] = self.genre_source_field_name

        # Fix up exclude_genre regex if blank. Assume blank = no exclusions
        if opts_dict['exclude_genre'] == '':
            opts_dict['exclude_genre'] = 'a^'

        # Append the output profile
        try:
            opts_dict['output_profile'] = [load_defaults('page_setup')['output_profile']]
        except:
            opts_dict['output_profile'] = ['default']

        if False and self.DEBUG:
            print("opts_dict")
            for opt in sorted(opts_dict.keys(), key=sort_key):
                print(" %s: %s" % (opt, repr(opts_dict[opt])))
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

        # Populate the 'Genres' combo box
        custom_fields = {_('Tags'):{'field':None,'datatype':None}}
        for custom_field in self.all_custom_fields:
            field_md = self.db.metadata_for_field(custom_field)
            if field_md['datatype'] in ['text','enumeration']:
                custom_fields[field_md['name']] = {'field':custom_field,
                                                   'datatype':field_md['datatype']}
        # Add the sorted eligible fields to the combo box
        for cf in sorted(custom_fields, key=sort_key):
            self.genre_source_field.addItem(cf)
        self.genre_source_fields = custom_fields
        self.genre_source_field.currentIndexChanged.connect(self.genre_source_field_changed)

        # Populate the Presets combo box
        self.presets = JSONConfig("catalog_presets")
        self.preset_field.addItem("")
        self.preset_field_values = sorted(self.presets, key=sort_key)
        self.preset_field.addItems(self.preset_field_values)

    def preset_change(self, item_name):
        '''
        Update catalog options from current preset
        '''
        if not item_name:
            return

        current_preset = self.preset_field.currentText()
        options = self.presets[current_preset]

        exclusion_rules = []
        prefix_rules = []

        self.block_all_signals(True)
        for opt in self.OPTION_FIELDS:
            c_name, c_def, c_type = opt
            if c_name == 'preset_field':
                continue
            # Ignore extra entries in options for cli invocation
            if c_name in options:
                opt_value = options[c_name]
            else:
                continue
            if c_type in ['check_box']:
                getattr(self, c_name).setChecked(eval(unicode_type(opt_value)))
                if c_name == 'generate_genres':
                    self.genre_source_field.setEnabled(eval(unicode_type(opt_value)))
            elif c_type in ['combo_box']:
                if opt_value is None:
                    index = 0
                    if c_name == 'genre_source_field':
                        index = self.genre_source_field.findText(_('Tags'))
                else:
                    index = getattr(self,c_name).findText(opt_value)
                    if index == -1:
                        if c_name == 'read_source_field':
                            index = self.read_source_field.findText(_('Tags'))
                        elif c_name == 'genre_source_field':
                            index = self.genre_source_field.findText(_('Tags'))
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

        # Reset exclusion rules
        self.exclusion_rules_table.clearLayout()
        self.exclusion_rules_table = ExclusionRules(self, self.exclusion_rules_gb,
            "exclusion_rules_tw", exclusion_rules)

        # Reset prefix rules
        self.prefix_rules_table.clearLayout()
        self.prefix_rules_table = PrefixRules(self, self.prefix_rules_gb,
            "prefix_rules_tw", prefix_rules)

        # Reset excluded genres preview
        self.exclude_genre_changed()

        # Reset format and title
        format = options['format']
        title = options['catalog_title']
        self.set_format_and_title(format, title)

        # Reset Descriptions-related enable/disable switches
        self.generate_descriptions_changed(self.generate_descriptions.isChecked())

        self.block_all_signals(False)

    def preset_remove(self):
        if self.preset_field.currentIndex() == 0:
            return

        if not question_dialog(self, _("Delete saved catalog preset"),
                _("The selected saved catalog preset will be deleted. "
                    "Are you sure?")):
            return

        item_id = self.preset_field.currentIndex()
        item_name = unicode_type(self.preset_field.currentText())

        self.preset_field.blockSignals(True)
        self.preset_field.removeItem(item_id)
        self.preset_field.blockSignals(False)
        self.preset_field.setCurrentIndex(0)

        if item_name in self.presets.keys():
            del(self.presets[item_name])
            self.presets.commit()

    def preset_save(self):
        names = ['']
        names.extend(self.preset_field_values)
        try:
            dex = names.index(self.preset_search_name)
        except:
            dex = 0
        name = ''
        while not name:
            name, ok =  QInputDialog.getItem(self, _('Save catalog preset'),
                    _('Preset name:'), names, dex, True)
            if not ok:
                return
            if not name:
                error_dialog(self, _("Save catalog preset"),
                        _("You must provide a name."), show=True)
        new = True
        name = unicode_type(name)
        if name in self.presets.keys():
            if not question_dialog(self, _("Save catalog preset"),
                    _("That saved preset already exists and will be overwritten. "
                        "Are you sure?")):
                return
            new = False

        preset = {}
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
                if c_name == 'preset_field':
                    continue
                opt_value = unicode_type(getattr(self,c_name).currentText()).strip()
            elif c_type in ['line_edit']:
                opt_value = unicode_type(getattr(self, c_name).text()).strip()
            elif c_type in ['spin_box']:
                opt_value = unicode_type(getattr(self, c_name).value())
            elif c_type in ['table_widget']:
                if c_name == 'prefix_rules_tw':
                    opt_value = self.prefix_rules_table.get_data()
                    prefix_rules_processed = True
                if c_name == 'exclusion_rules_tw':
                    opt_value = self.exclusion_rules_table.get_data()
                    exclusion_rules_processed = True

            preset[c_name] = opt_value
            # Construct cli version of table rules
            if c_name in ['exclusion_rules_tw','prefix_rules_tw']:
                self.construct_tw_opts_object(c_name, opt_value, preset)

        format, title = self.get_format_and_title()
        preset['format'] = format
        preset['catalog_title'] = title

        # Additional items needed for cli invocation
        # Generate specs for merge_comments, header_note_source_field, genre_source_field
        checked = ''
        if self.merge_before.isChecked():
            checked = 'before'
        elif self.merge_after.isChecked():
            checked = 'after'
        include_hr = self.include_hr.isChecked()
        preset['merge_comments_rule'] = "%s:%s:%s" % \
            (self.merge_source_field_name, checked, include_hr)

        preset['header_note_source_field'] = unicode_type(self.header_note_source_field.currentText())
        preset['genre_source_field'] = unicode_type(self.genre_source_field.currentText())

        # Append the current output profile
        try:
            preset['output_profile'] = load_defaults('page_setup')['output_profile']
        except:
            preset['output_profile'] = 'default'

        self.presets[name] = preset
        self.presets.commit()

        if new:
            self.preset_field.blockSignals(True)
            self.preset_field.clear()
            self.preset_field.addItem('')
            self.preset_field_values = sorted(self.presets, key=sort_key)
            self.preset_field.addItems(self.preset_field_values)
            self.preset_field.blockSignals(False)
        self.preset_field.setCurrentIndex(self.preset_field.findText(name))

    def set_format_and_title(self, format, title):
        parent = self.parent_ref()
        if parent is not None:
            if format:
                index = parent.format.findText(format)
                parent.format.blockSignals(True)
                parent.format.setCurrentIndex(index)
                parent.format.blockSignals(False)
            if title:
                parent.title.setText(title)

    def settings_changed(self, source):
        '''
        When anything changes, clear Preset combobox
        '''
        if self.DEBUG:
            print("settings_changed: %s" % source)
        self.preset_field.setCurrentIndex(0)

    def show_help(self):
        '''
        Display help file
        '''
        open_url(QUrl(localize_user_manual_link('https://manual.calibre-ebook.com/catalogs.html')))


class CheckableTableWidgetItem(QTableWidgetItem):

    '''
    Borrowed from kiwidude
    '''

    def __init__(self, checked=False, is_tristate=False):
        QTableWidgetItem.__init__(self, '')
        self.setFlags(Qt.ItemFlags(Qt.ItemIsSelectable | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled))
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

    def wheelEvent(self, event):
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

    def __init__(self, parent, parent_gb, object_name, rules):
        self.parent = parent
        self.rules = rules
        self.eligible_custom_fields = parent.eligible_custom_fields
        self.db = parent.db
        QTableWidget.__init__(self)
        self.setObjectName(object_name)
        self.layout = parent_gb.layout()

        # Add ourselves to the layout
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        # sizePolicy.setHeightForWidth(self.sizePolicy().hasHeightForWidth())
        self.setSizePolicy(sizePolicy)
        self.setMaximumSize(QSize(16777215, self.MAXIMUM_TABLE_HEIGHT))

        self.setColumnCount(0)
        self.setRowCount(0)
        self.layout.addWidget(self)

        self.last_row_selected = self.currentRow()
        self.last_rows_selected = self.selectionModel().selectedRows()

        # Add the controls
        self._init_controls()

        # Hook check_box changes
        self.cellChanged.connect(self.enabled_state_changed)

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

    def clearLayout(self):
        if self.layout is not None:
            old_layout = self.layout

            for child in old_layout.children():
                for i in reversed(range(child.count())):
                    if child.itemAt(i).widget() is not None:
                        child.itemAt(i).widget().setParent(None)
                sip.delete(child)

            for i in reversed(range(old_layout.count())):
                if old_layout.itemAt(i).widget() is not None:
                    old_layout.itemAt(i).widget().setParent(None)

    def delete_row(self):
        if self.DEBUG:
            print("%s:delete_row()" % self.objectName())

        self.setFocus()
        rows = self.last_rows_selected
        if len(rows) == 0:
            return

        first = rows[0].row() + 1
        last = rows[-1].row() + 1

        first_rule_name = unicode_type(self.cellWidget(first-1,self.COLUMNS['NAME']['ordinal']).text()).strip()
        message = _("Are you sure you want to delete '%s'?") % (first_rule_name)
        if len(rows) > 1:
            message = _('Are you sure you want to delete rules #%(first)d-%(last)d?') % dict(first=first, last=last)
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
            self.settings_changed("enabled_state_changed")
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
        self.settings_changed("rule_name_edited")

    def select_and_scroll_to_row(self, row):
        self.setFocus()
        self.selectRow(row)
        self.scrollToItem(self.currentItem())
        self.last_row_selected = self.currentRow()
        self.last_rows_selected = self.selectionModel().selectedRows()

    def settings_changed(self, source):
        if not self.parent.blocking_all_signals:
            self.parent.settings_changed(source)

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

        source_field = combo.currentText()

        if source_field == '':
            values = []
        elif source_field == _('Tags'):
            values = sorted(self.db.all_tags(), key=sort_key)
        else:
            if self.eligible_custom_fields[unicode_type(source_field)]['datatype'] in ['enumeration', 'text']:
                values = self.db.all_custom(self.db.field_metadata.key_to_label(
                                            self.eligible_custom_fields[unicode_type(source_field)]['field']))
                values = sorted(values, key=sort_key)
            elif self.eligible_custom_fields[unicode_type(source_field)]['datatype'] in ['bool']:
                values = [_('True'),_('False'),_('unspecified')]
            elif self.eligible_custom_fields[unicode_type(source_field)]['datatype'] in ['composite']:
                values = [_('any value'),_('unspecified')]
            elif self.eligible_custom_fields[unicode_type(source_field)]['datatype'] in ['datetime']:
                values = [_('any date'),_('unspecified')]

        values_combo = ComboBox(self, values, pattern)
        values_combo.currentIndexChanged.connect(partial(self.values_index_changed, values_combo))
        self.setCellWidget(row, self.COLUMNS['PATTERN']['ordinal'], values_combo)
        self.select_and_scroll_to_row(row)
        self.settings_changed("source_index_changed")

    def values_index_changed(self, combo):
        # After edit, select row
        for row in range(self.rowCount()):
            if self.cellWidget(row, self.COLUMNS['PATTERN']['ordinal']) is combo:
                self.select_and_scroll_to_row(row)
                self.settings_changed("values_index_changed")
                break

        if self.DEBUG:
            print("%s:values_index_changed(): row %d " %
                  (self.objectName(), row))


class ExclusionRules(GenericRulesTable):

    COLUMNS = {'ENABLED':{'ordinal': 0, 'name': ''},
                'NAME':   {'ordinal': 1, 'name': _('Name')},
                'FIELD':  {'ordinal': 2, 'name': _('Field')},
                'PATTERN':  {'ordinal': 3, 'name': _('Value')},}

    def __init__(self, parent, parent_gb_hl, object_name, rules):
        super(ExclusionRules, self).__init__(parent, parent_gb_hl, object_name, rules)
        self.setObjectName("exclusion_rules_table")
        self._init_table_widget()
        self._initialize()

    def _init_table_widget(self):
        header_labels = [self.COLUMNS[index]['name']
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
        data['name'] = unicode_type(self.cellWidget(row,self.COLUMNS['NAME']['ordinal']).text()).strip()
        data['field'] = unicode_type(self.cellWidget(row,self.COLUMNS['FIELD']['ordinal']).currentText()).strip()
        data['pattern'] = unicode_type(self.cellWidget(row,self.COLUMNS['PATTERN']['ordinal']).currentText()).strip()
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

    COLUMNS = {'ENABLED':{'ordinal': 0, 'name': ''},
                'NAME':   {'ordinal': 1, 'name': _('Name')},
                'PREFIX': {'ordinal': 2, 'name': _('Prefix')},
                'FIELD':  {'ordinal': 3, 'name': _('Field')},
                'PATTERN':{'ordinal': 4, 'name': _('Value')},}

    def __init__(self, parent, parent_gb_hl, object_name, rules):
        super(PrefixRules, self).__init__(parent, parent_gb_hl, object_name, rules)
        self.setObjectName("prefix_rules_table")
        self._init_table_widget()
        self._initialize()

    def _init_table_widget(self):
        header_labels = [self.COLUMNS[index]['name']
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
        data['name'] = unicode_type(self.cellWidget(row,self.COLUMNS['NAME']['ordinal']).text()).strip()
        data['prefix'] = unicode_type(self.cellWidget(row,self.COLUMNS['PREFIX']['ordinal']).currentText()).strip()
        data['field'] = unicode_type(self.cellWidget(row,self.COLUMNS['FIELD']['ordinal']).currentText()).strip()
        data['pattern'] = unicode_type(self.cellWidget(row,self.COLUMNS['PATTERN']['ordinal']).currentText()).strip()
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
            ('Ampersand', '&'),
            ('Angle left double', '\u00ab'),
            ('Angle left', '\u2039'),
            ('Angle right double', '\u00bb'),
            ('Angle right', '\u203a'),
            ('Arrow carriage return', '\u21b5'),
            ('Arrow double', '\u2194'),
            ('Arrow down', '\u2193'),
            ('Arrow left', '\u2190'),
            ('Arrow right', '\u2192'),
            ('Arrow up', '\u2191'),
            ('Asterisk', '*'),
            ('At sign', '@'),
            ('Bullet smallest', '\u22c5'),
            ('Bullet small', '\u00b7'),
            ('Bullet', '\u2022'),
            ('Cards clubs', '\u2663'),
            ('Cards diamonds', '\u2666'),
            ('Cards hearts', '\u2665'),
            ('Cards spades', '\u2660'),
            ('Caret', '^'),
            ('Checkmark', '\u2713'),
            ('Copyright circle c', '\u00a9'),
            ('Copyright circle r', '\u00ae'),
            ('Copyright trademark', '\u2122'),
            ('Currency cent', '\u00a2'),
            ('Currency dollar', '$'),
            ('Currency euro', '\u20ac'),
            ('Currency pound', '\u00a3'),
            ('Currency yen', '\u00a5'),
            ('Dagger double', '\u2021'),
            ('Dagger', '\u2020'),
            ('Degree', '\u00b0'),
            ('Dots3', '\u2234'),
            ('Hash', '#'),
            ('Infinity', '\u221e'),
            ('Lozenge', '\u25ca'),
            ('Math divide', '\u00f7'),
            ('Math empty', '\u2205'),
            ('Math equals', '='),
            ('Math minus', '\u2212'),
            ('Math plus circled', '\u2295'),
            ('Math times circled', '\u2297'),
            ('Math times', '\u00d7'),
            ('Paragraph', '\u00b6'),
            ('Percent', '%'),
            ('Plus-or-minus', '\u00b1'),
            ('Plus', '+'),
            ('Punctuation colon', ':'),
            ('Punctuation colon-semi', ';'),
            ('Punctuation exclamation', '!'),
            ('Punctuation question', '?'),
            ('Punctuation period', '.'),
            ('Punctuation slash back', '\\'),
            ('Punctuation slash forward', '/'),
            ('Section', '\u00a7'),
            ('Tilde', '~'),
            ('Vertical bar', '|'),
            ('Vertical bar broken', '\u00a6'),
            ('_0', '0'),
            ('_1', '1'),
            ('_2', '2'),
            ('_3', '3'),
            ('_4', '4'),
            ('_5', '5'),
            ('_6', '6'),
            ('_7', '7'),
            ('_8', '8'),
            ('_9', '9'),
            ('_A', 'A'),
            ('_B', 'B'),
            ('_C', 'C'),
            ('_D', 'D'),
            ('_E', 'E'),
            ('_F', 'F'),
            ('_G', 'G'),
            ('_H', 'H'),
            ('_I', 'I'),
            ('_J', 'J'),
            ('_K', 'K'),
            ('_L', 'L'),
            ('_M', 'M'),
            ('_N', 'N'),
            ('_O', 'O'),
            ('_P', 'P'),
            ('_Q', 'Q'),
            ('_R', 'R'),
            ('_S', 'S'),
            ('_T', 'T'),
            ('_U', 'U'),
            ('_V', 'V'),
            ('_W', 'W'),
            ('_X', 'X'),
            ('_Y', 'Y'),
            ('_Z', 'Z'),
            ('_a', 'a'),
            ('_b', 'b'),
            ('_c', 'c'),
            ('_d', 'd'),
            ('_e', 'e'),
            ('_f', 'f'),
            ('_g', 'g'),
            ('_h', 'h'),
            ('_i', 'i'),
            ('_j', 'j'),
            ('_k', 'k'),
            ('_l', 'l'),
            ('_m', 'm'),
            ('_n', 'n'),
            ('_o', 'o'),
            ('_p', 'p'),
            ('_q', 'q'),
            ('_r', 'r'),
            ('_s', 's'),
            ('_t', 't'),
            ('_u', 'u'),
            ('_v', 'v'),
            ('_w', 'w'),
            ('_x', 'x'),
            ('_y', 'y'),
            ('_z', 'z'),
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
            prefix_combo.currentIndexChanged.connect(partial(self.settings_changed, 'set_prefix_field_in_row'))
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
