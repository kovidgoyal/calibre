__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid at kovidgoyal.net>'

'''Dialog to create a new custom column'''

import re
from functools import partial

from PyQt4.Qt import QDialog, Qt, QListWidgetItem, QVariant, QColor, QIcon

from calibre.gui2.preferences.create_custom_column_ui import Ui_QCreateCustomColumn
from calibre.gui2 import error_dialog

class CreateCustomColumn(QDialog, Ui_QCreateCustomColumn):

    # Note: in this class, we are treating is_multiple as the boolean that
    # custom_columns expects to find in its structure. It does not use the dict

    column_types = {
                    0:{'datatype':'text',
                        'text':_('Text, column shown in the tag browser'),
                        'is_multiple':False},
                    1:{'datatype':'*text',
                        'text':_('Comma separated text, like tags, shown in the tag browser'),
                        'is_multiple':True},
                    2:{'datatype':'comments',
                        'text':_('Long text, like comments, not shown in the tag browser'),
                        'is_multiple':False},
                    3:{'datatype':'series',
                        'text':_('Text column for keeping series-like information'),
                        'is_multiple':False},
                    4:{'datatype':'enumeration',
                        'text':_('Text, but with a fixed set of permitted values'), 'is_multiple':False},
                    5:{'datatype':'datetime',
                        'text':_('Date'), 'is_multiple':False},
                    6:{'datatype':'float',
                        'text':_('Floating point numbers'), 'is_multiple':False},
                    7:{'datatype':'int',
                        'text':_('Integers'), 'is_multiple':False},
                    8:{'datatype':'rating',
                        'text':_('Ratings, shown with stars'),
                        'is_multiple':False},
                    9:{'datatype':'bool',
                        'text':_('Yes/No'), 'is_multiple':False},
                    10:{'datatype':'composite',
                        'text':_('Column built from other columns'), 'is_multiple':False},
                    11:{'datatype':'*composite',
                        'text':_('Column built from other columns, behaves like tags'), 'is_multiple':True},
                }

    def __init__(self, parent, editing, standard_colheads, standard_colnames):
        QDialog.__init__(self, parent)
        Ui_QCreateCustomColumn.__init__(self)
        self.setupUi(self)
        self.setWindowTitle(_('Create a custom column'))
        self.heading_label.setText(_('Create a custom column'))
        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.simple_error = partial(error_dialog, self, show=True,
            show_copy_button=False)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.shortcuts.linkActivated.connect(self.shortcut_activated)
        text = '<p>'+_('Quick create:')
        for col, name in [('isbn', _('ISBN')), ('formats', _('Formats')),
                ('yesno', _('Yes/No')),
                ('tags', _('Tags')), ('series', _('Series')), ('rating',
                    _('Rating')), ('people', _("People's names"))]:
            text += ' <a href="col:%s">%s</a>,'%(col, name)
        text = text[:-1]
        self.shortcuts.setText(text)

        for sort_by in [_('Text'), _('Number'), _('Date'), _('Yes/No')]:
            self.composite_sort_by.addItem(sort_by)

        self.parent = parent
        self.editing_col = editing
        self.standard_colheads = standard_colheads
        self.standard_colnames = standard_colnames
        self.column_type_box.setMaxVisibleItems(len(self.column_types))
        for t in self.column_types:
            self.column_type_box.addItem(self.column_types[t]['text'])
        self.column_type_box.currentIndexChanged.connect(self.datatype_changed)
        if not self.editing_col:
            self.datatype_changed()
            self.exec_()
            return
        self.setWindowTitle(_('Edit a custom column'))
        self.heading_label.setText(_('Edit a custom column'))
        self.shortcuts.setVisible(False)
        idx = parent.opt_columns.currentRow()
        if idx < 0:
            self.simple_error(_('No column selected'),
                    _('No column has been selected'))
            return
        col = unicode(parent.opt_columns.item(idx).data(Qt.UserRole).toString())
        if col not in parent.custcols:
            self.simple_error('', _('Selected column is not a user-defined column'))
            return

        c = parent.custcols[col]
        self.column_name_box.setText(c['label'])
        self.column_heading_box.setText(c['name'])
        ct = c['datatype']
        if c['is_multiple']:
            ct = '*' + ct
        self.orig_column_number = c['colnum']
        self.orig_column_name = col
        column_numbers = dict(map(lambda x:(self.column_types[x]['datatype'], x),
                                  self.column_types))
        self.column_type_box.setCurrentIndex(column_numbers[ct])
        self.column_type_box.setEnabled(False)
        if ct == 'datetime':
            if c['display'].get('date_format', None):
                self.date_format_box.setText(c['display'].get('date_format', ''))
        elif ct in ['composite', '*composite']:
            self.composite_box.setText(c['display'].get('composite_template', ''))
            sb = c['display'].get('composite_sort', 'text')
            vals = ['text', 'number', 'date', 'bool']
            if sb in vals:
                sb = vals.index(sb)
            else:
                sb = 0
            self.composite_sort_by.setCurrentIndex(sb)
            self.composite_make_category.setChecked(
                                c['display'].get('make_category', False))
            self.composite_contains_html.setChecked(
                                c['display'].get('contains_html', False))
        elif ct == 'enumeration':
            self.enum_box.setText(','.join(c['display'].get('enum_values', [])))
            self.enum_colors.setText(','.join(c['display'].get('enum_colors', [])))
        elif ct in ['int', 'float']:
            if c['display'].get('number_format', None):
                self.number_format_box.setText(c['display'].get('number_format', ''))
        self.datatype_changed()
        if ct in ['text', 'composite', 'enumeration']:
            self.use_decorations.setChecked(c['display'].get('use_decorations', False))
        elif ct == '*text':
            self.is_names.setChecked(c['display'].get('is_names', False))

        all_colors = [unicode(s) for s in list(QColor.colorNames())]
        self.enum_colors_label.setToolTip('<p>' + ', '.join(all_colors) + '</p>')

        self.composite_contains_html.setToolTip('<p>' +
                _('If checked, this column will be displayed as HTML in '
                  'book details and the content server. This can be used to '
                  'construct links with the template language. For example, '
                  'the template '
                  '<pre>&lt;big&gt;&lt;b&gt;{title}&lt;/b&gt;&lt;/big&gt;'
                  '{series:| [|}{series_index:| [|]]}</pre>'
                  'will create a field displaying the title in bold large '
                  'characters, along with the series, for example <br>"<big><b>'
                  'An Oblique Approach</b></big> [Belisarius [1]]". The template '
                  '<pre>&lt;a href="http://www.beam-ebooks.de/ebook/{identifiers'
                  ':select(beam)}"&gt;Beam book&lt;/a&gt;</pre> '
                  'will generate a link to the book on the Beam ebooks site.')
                        + '</p>')
        self.exec_()

    def shortcut_activated(self, url):
        which = unicode(url).split(':')[-1]
        self.column_type_box.setCurrentIndex({
            'yesno': 9,
            'tags' : 1,
            'series': 3,
            'rating': 8,
            'people': 1,
            }.get(which, 10))
        self.column_name_box.setText(which)
        self.column_heading_box.setText({
            'isbn':'ISBN',
            'formats':_('Formats'),
            'yesno':_('Yes/No'),
            'tags': _('My Tags'),
            'series': _('My Series'),
            'rating': _('My Rating'),
            'people': _('People')}[which])
        self.is_names.setChecked(which == 'people')
        if self.composite_box.isVisible():
            self.composite_box.setText(
                {
                    'isbn': '{identifiers:select(isbn)}',
                    'formats': '{formats}',
                    }[which])
            self.composite_sort_by.setCurrentIndex(0)

    def datatype_changed(self, *args):
        try:
            col_type = self.column_types[self.column_type_box.currentIndex()]['datatype']
        except:
            col_type = None
        for x in ('box', 'default_label', 'label'):
            getattr(self, 'date_format_'+x).setVisible(col_type == 'datetime')
            getattr(self, 'number_format_'+x).setVisible(col_type in ['int', 'float'])
        for x in ('box', 'default_label', 'label', 'sort_by', 'sort_by_label',
                  'make_category', 'contains_html'):
            getattr(self, 'composite_'+x).setVisible(col_type in ['composite', '*composite'])
        for x in ('box', 'default_label', 'label', 'colors', 'colors_label'):
            getattr(self, 'enum_'+x).setVisible(col_type == 'enumeration')
        self.use_decorations.setVisible(col_type in ['text', 'composite', 'enumeration'])
        self.is_names.setVisible(col_type == '*text')
        if col_type == 'int':
            self.number_format_box.setToolTip('<p>' +
                _('Examples: The format <code>{0:0>4d}</code> '
                  'gives a 4-digit number with leading zeros. The format '
                  '<code>{0:d}&nbsp;days</code> prints the number then the word "days"')+ '</p>')
        elif col_type == 'float':
            self.number_format_box.setToolTip('<p>' +
                _('Examples: The format <code>{0:.1f}</code> gives a floating '
                  'point number with 1 digit after the decimal point. The format '
                  '<code>Price:&nbsp;$&nbsp;{0:,.2f}</code> prints '
                  '"Price&nbsp;$&nbsp;" then displays the number with 2 digits '
                  'after the decimal point and thousands separated by commas.') + '</p>')

    def accept(self):
        col = unicode(self.column_name_box.text()).strip()
        if not col:
            return self.simple_error('', _('No lookup name was provided'))
        if col.startswith('#'):
            col = col[1:]
        if re.match('^\w*$', col) is None or not col[0].isalpha() or col.lower() != col:
            return self.simple_error('', _('The lookup name must contain only '
                    'lower case letters, digits and underscores, and start with a letter'))
        if col.endswith('_index'):
            return self.simple_error('', _('Lookup names cannot end with _index, '
                    'because these names are reserved for the index of a series column.'))
        col_heading = unicode(self.column_heading_box.text()).strip()
        col_type = self.column_types[self.column_type_box.currentIndex()]['datatype']
        if col_type[0] == '*':
            col_type = col_type[1:]
            is_multiple = True
        else:
            is_multiple = False
        if not col_heading:
            return self.simple_error('', _('No column heading was provided'))

        db = self.parent.gui.library_view.model().db
        key = db.field_metadata.custom_field_prefix+col
        bad_col = False
        if key in self.parent.custcols:
            if not self.editing_col or \
                    self.parent.custcols[key]['colnum'] != self.orig_column_number:
                bad_col = True
        if bad_col:
            return self.simple_error('', _('The lookup name %s is already used')%col)

        bad_head = False
        for t in self.parent.custcols:
            if self.parent.custcols[t]['name'] == col_heading:
                if not self.editing_col or \
                        self.parent.custcols[t]['colnum'] != self.orig_column_number:
                    bad_head = True
        for t in self.standard_colheads:
            if self.standard_colheads[t] == col_heading:
                bad_head = True
        if bad_head:
            return self.simple_error('', _('The heading %s is already used')%col_heading)

        display_dict = {}

        if col_type == 'datetime':
            if unicode(self.date_format_box.text()).strip():
                display_dict = {'date_format':unicode(self.date_format_box.text()).strip()}
            else:
                display_dict = {'date_format': None}
        elif col_type == 'composite':
            if not unicode(self.composite_box.text()).strip():
                return self.simple_error('', _('You must enter a template for'
                    ' composite columns'))
            display_dict = {'composite_template':unicode(self.composite_box.text()).strip(),
                            'composite_sort': ['text', 'number', 'date', 'bool']
                                        [self.composite_sort_by.currentIndex()],
                            'make_category': self.composite_make_category.isChecked(),
                            'contains_html': self.composite_contains_html.isChecked(),
                        }
        elif col_type == 'enumeration':
            if not unicode(self.enum_box.text()).strip():
                return self.simple_error('', _('You must enter at least one'
                    ' value for enumeration columns'))
            l = [v.strip() for v in unicode(self.enum_box.text()).split(',') if v.strip()]
            l_lower = [v.lower() for v in l]
            for i,v in enumerate(l_lower):
                if v in l_lower[i+1:]:
                    return self.simple_error('', _('The value "{0}" is in the '
                    'list more than once, perhaps with different case').format(l[i]))
            c = unicode(self.enum_colors.text())
            if c:
                c = [v.strip() for v in unicode(self.enum_colors.text()).split(',')]
            else:
                c = []
            if len(c) != 0 and len(c) != len(l):
                return self.simple_error('', _('The colors box must be empty or '
                'contain the same number of items as the value box'))
            for tc in c:
                if tc not in QColor.colorNames():
                    return self.simple_error('',
                            _('The color {0} is unknown').format(tc))

            display_dict = {'enum_values': l, 'enum_colors': c}
        elif col_type == 'text' and is_multiple:
            display_dict = {'is_names': self.is_names.isChecked()}
        elif col_type in ['int', 'float']:
            if unicode(self.number_format_box.text()).strip():
                display_dict = {'number_format':unicode(self.number_format_box.text()).strip()}
            else:
                display_dict = {'number_format': None}

        if col_type in ['text', 'composite', 'enumeration'] and not is_multiple:
            display_dict['use_decorations'] = self.use_decorations.checkState()

        if not self.editing_col:
            self.parent.custcols[key] = {
                    'label':col,
                    'name':col_heading,
                    'datatype':col_type,
                    'display':display_dict,
                    'normalized':None,
                    'colnum':None,
                    'is_multiple':is_multiple,
                }
            item = QListWidgetItem(col_heading, self.parent.opt_columns)
            item.setData(Qt.UserRole, QVariant(key))
            item.setData(Qt.DecorationRole, QVariant(QIcon(I('column.png'))))
            item.setFlags(Qt.ItemIsEnabled|Qt.ItemIsUserCheckable|Qt.ItemIsSelectable)
            item.setCheckState(Qt.Checked)
        else:
            idx = self.parent.opt_columns.currentRow()
            item = self.parent.opt_columns.item(idx)
            item.setText(col_heading)
            self.parent.custcols[self.orig_column_name]['label'] = col
            self.parent.custcols[self.orig_column_name]['name'] = col_heading
            self.parent.custcols[self.orig_column_name]['display'].update(display_dict)
            self.parent.custcols[self.orig_column_name]['*edited'] = True
            self.parent.custcols[self.orig_column_name]['*must_restart'] = True
        QDialog.accept(self)

    def reject(self):
        QDialog.reject(self)
