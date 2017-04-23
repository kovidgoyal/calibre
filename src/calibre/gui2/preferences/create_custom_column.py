#!/usr/bin/env python2
# vim:fileencoding=UTF-8

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid at kovidgoyal.net>'

'''Dialog to create a new custom column'''

import re
from functools import partial

from PyQt5.Qt import (
    QDialog, Qt, QColor, QIcon, QVBoxLayout, QLabel, QGridLayout,
    QDialogButtonBox, QWidget, QLineEdit, QHBoxLayout, QComboBox,
    QCheckBox
)

from calibre.gui2 import error_dialog


class CreateCustomColumn(QDialog):

    # Note: in this class, we are treating is_multiple as the boolean that
    # custom_columns expects to find in its structure. It does not use the dict

    column_types = dict(enumerate((
        {
            'datatype':'text',
            'text':_('Text, column shown in the tag browser'),
            'is_multiple':False
        },
        {
            'datatype':'*text',
            'text':_('Comma separated text, like tags, shown in the tag browser'),
            'is_multiple':True
        },
        {
            'datatype':'comments',
            'text':_('Long text, like comments, not shown in the tag browser'),
            'is_multiple':False
        },
        {
            'datatype':'series',
            'text':_('Text column for keeping series-like information'),
            'is_multiple':False
        },
        {
            'datatype':'enumeration',
            'text':_('Text, but with a fixed set of permitted values'),
            'is_multiple':False
        },
        {
            'datatype':'datetime',
            'text':_('Date'),
            'is_multiple':False
        },
        {
            'datatype':'float',
            'text':_('Floating point numbers'),
            'is_multiple':False
        },
        {
            'datatype':'int',
            'text':_('Integers'),
            'is_multiple':False
        },
        {
            'datatype':'rating',
            'text':_('Ratings, shown with stars'),
            'is_multiple':False
        },
        {
            'datatype':'bool',
            'text':_('Yes/No'),
            'is_multiple':False
        },
        {
            'datatype':'composite',
            'text':_('Column built from other columns'),
            'is_multiple':False
        },
        {
            'datatype':'*composite',
            'text':_('Column built from other columns, behaves like tags'),
            'is_multiple':True
        },
    )))
    column_types_map = {k['datatype']:idx for idx, k in column_types.iteritems()}

    def __init__(self, parent, current_row, current_key, standard_colheads, standard_colnames):
        QDialog.__init__(self, parent)
        self.setup_ui()
        self.setWindowTitle(_('Create a custom column'))
        self.heading_label.setText('<b>' + _('Create a custom column'))
        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.simple_error = partial(error_dialog, self, show=True,
            show_copy_button=False)
        for sort_by in [_('Text'), _('Number'), _('Date'), _('Yes/No')]:
            self.composite_sort_by.addItem(sort_by)

        self.parent = parent
        self.parent.cc_column_key = None
        self.editing_col = current_row is not None
        self.standard_colheads = standard_colheads
        self.standard_colnames = standard_colnames
        self.column_type_box.setMaxVisibleItems(len(self.column_types))
        for t in self.column_types:
            self.column_type_box.addItem(self.column_types[t]['text'])
        self.column_type_box.currentIndexChanged.connect(self.datatype_changed)

        all_colors = [unicode(s) for s in list(QColor.colorNames())]
        self.enum_colors_label.setToolTip('<p>' + ', '.join(all_colors) + '</p>')

        if not self.editing_col:
            self.datatype_changed()
            self.exec_()
            return

        self.setWindowTitle(_('Edit a custom column'))
        self.heading_label.setText('<b>' + _('Edit a custom column'))
        self.shortcuts.setVisible(False)
        idx = current_row
        if idx < 0:
            self.simple_error(_('No column selected'),
                    _('No column has been selected'))
            return
        col = current_key
        if col not in parent.custcols:
            self.simple_error('', _('Selected column is not a user-defined column'))
            return

        c = parent.custcols[col]
        self.column_name_box.setText(c['label'])
        self.column_heading_box.setText(c['name'])
        self.column_heading_box.setFocus()
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
                self.format_box.setText(c['display'].get('date_format', ''))
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
                self.format_box.setText(c['display'].get('number_format', ''))
        elif ct == 'comments':
            idx = max(0, self.comments_heading_position.findData(c['display'].get('heading_position', 'hide')))
            self.comments_heading_position.setCurrentIndex(idx)
            idx = max(0, self.comments_type.findData(c['display'].get('interpret_as', 'html')))
            self.comments_type.setCurrentIndex(idx)
        elif ct == 'rating':
            self.allow_half_stars.setChecked(bool(c['display'].get('allow_half_stars', False)))
        self.datatype_changed()
        if ct in ['text', 'composite', 'enumeration']:
            self.use_decorations.setChecked(c['display'].get('use_decorations', False))
        elif ct == '*text':
            self.is_names.setChecked(c['display'].get('is_names', False))
        self.description_box.setText(c['display'].get('description', ''))

        self.exec_()

    def shortcut_activated(self, url):  # {{{
        which = unicode(url).split(':')[-1]
        self.column_type_box.setCurrentIndex({
            'yesno': self.column_types_map['bool'],
            'tags' : self.column_types_map['*text'],
            'series': self.column_types_map['series'],
            'rating': self.column_types_map['rating'],
            'people': self.column_types_map['*text'],
            'text': self.column_types_map['comments'],
            }.get(which, self.column_types_map['composite']))
        self.column_name_box.setText(which)
        self.column_heading_box.setText({
            'isbn':'ISBN',
            'formats':_('Formats'),
            'yesno':_('Yes/No'),
            'tags': _('My Tags'),
            'series': _('My Series'),
            'rating': _('My Rating'),
            'people': _('People'),
            'text': _('My Title'),
        }[which])
        self.is_names.setChecked(which == 'people')
        if self.composite_box.isVisible():
            self.composite_box.setText(
                {
                    'isbn': '{identifiers:select(isbn)}',
                    'formats': "{:'approximate_formats()'}",
                    }[which])
            self.composite_sort_by.setCurrentIndex(0)
        if which == 'text':
            self.comments_heading_position.setCurrentIndex(self.comments_heading_position.findData('side'))
            self.comments_type.setCurrentIndex(self.comments_type.findData('short-text'))
    # }}}

    def setup_ui(self):  # {{{
        self.setWindowModality(Qt.ApplicationModal)
        self.setWindowIcon(QIcon(I('column.png')))
        self.vl = l = QVBoxLayout(self)
        self.heading_label = la = QLabel('')
        l.addWidget(la)
        self.shortcuts = s = QLabel('')
        s.setWordWrap(True)
        s.linkActivated.connect(self.shortcut_activated)
        text = '<p>'+_('Quick create:')
        for col, name in [('isbn', _('ISBN')), ('formats', _('Formats')),
                ('yesno', _('Yes/No')),
                ('tags', _('Tags')), ('series', _('Series')), ('rating',
                    _('Rating')), ('people', _("Names")), ('text', _('Short text'))]:
            text += ' <a href="col:%s">%s</a>,'%(col, name)
        text = text[:-1]
        s.setText(text)
        l.addWidget(s)
        self.g = g = QGridLayout()
        l.addLayout(g)
        l.addStretch(10)
        self.button_box = bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        bb.accepted.connect(self.accept), bb.rejected.connect(self.reject)
        l.addWidget(bb)

        def add_row(text, widget):
            if text is None:
                f = g.addWidget if isinstance(widget, QWidget) else g.addLayout
                f(widget, g.rowCount(), 0, 1, -1)
                return

            row = g.rowCount()
            la = QLabel(text)
            g.addWidget(la, row, 0, 1, 1)
            if isinstance(widget, QWidget):
                la.setBuddy(widget)
                g.addWidget(widget, row, 1, 1, 1)
            else:
                widget.setContentsMargins(0, 0, 0, 0)
                g.addLayout(widget, row, 1, 1, 1)
                for i in range(widget.count()):
                    w = widget.itemAt(i).widget()
                    if isinstance(w, QWidget):
                        la.setBuddy(w)
                        break
            return la

        # Lookup name
        self.column_name_box = cnb = QLineEdit(self)
        cnb.setToolTip(_("Used for searching the column. Must contain only digits and lower case letters."))
        add_row(_("&Lookup name"), cnb)

        # Heading
        self.column_heading_box = chb = QLineEdit(self)
        chb.setToolTip(_("Column heading in the library view and category name in the tag browser"))
        add_row(_("Column &heading"), chb)

        # Column Type
        h = QHBoxLayout()
        self.column_type_box = ctb = QComboBox(self)
        ctb.setMinimumWidth(70)
        ctb.setToolTip(_("What kind of information will be kept in the column."))
        h.addWidget(ctb)
        self.use_decorations = ud = QCheckBox(_("Show &checkmarks"), self)
        ud.setToolTip(_("Show check marks in the GUI. Values of 'yes', 'checked', and 'true'\n"
            "will show a green check. Values of 'no', 'unchecked', and 'false' will show a red X.\n"
            "Everything else will show nothing."))
        h.addWidget(ud)
        self.is_names = ins = QCheckBox(_("Contains names"), self)
        ins.setToolTip(_("Check this box if this column contains names, like the authors column."))
        h.addWidget(ins)
        add_row(_("&Column type"), h)

        # Description
        self.description_box = d = QLineEdit(self)
        d.setToolTip(_("Optional text describing what this column is for"))
        add_row(_("D&escription"), d)

        # Date/number formatting
        h = QHBoxLayout()
        self.format_box = fb = QLineEdit(self)
        h.addWidget(fb)
        self.format_default_label = la = QLabel('')
        la.setOpenExternalLinks(True)
        h.addWidget(la)
        self.format_label = add_row('', h)

        # Template
        self.composite_box = cb = QLineEdit(self)
        self.composite_default_label = cdl = QLabel(_("Default: (nothing)"))
        cb.setToolTip(_("Field template. Uses the same syntax as save templates."))
        cdl.setToolTip(_("Similar to save templates. For example, %s") % "{title} {isbn}")
        h = QHBoxLayout()
        h.addWidget(cb), h.addWidget(cdl)
        self.composite_label = add_row(_("&Template"), h)

        # Comments properties
        self.comments_heading_position = ct = QComboBox(self)
        for k, text in (
                ('hide', _('No heading')),
                ('above', _('Show heading above the text')),
                ('side', _('Show heading to the side of the text'))
        ):
            ct.addItem(text, k)
        ct.setToolTip(_('Choose whether or not the column heading is shown in the Book\n'
                        'Details panel and, if shown, where'))
        self.comments_heading_position_label = add_row(_('Column heading'), ct)

        self.comments_type = ct = QComboBox(self)
        for k, text in (
                ('html', 'HTML'),
                ('short-text', _('Short text, like a title')),
                ('long-text', _('Plain text')),
                ('markdown', _('Plain text formatted using markdown'))
        ):
            ct.addItem(text, k)
        ct.setToolTip(_('Choose how the data in this column is interpreted.\n'
                        'This controls how the data is displayed in the Book details panel\n'
                        'and how it is edited.'))
        self.comments_type_label = add_row(_('Interpret this column as:') + ' ', ct)

        # Values for enum type
        l = QGridLayout()
        self.enum_box = eb = QLineEdit(self)
        eb.setToolTip(_(
            "A comma-separated list of permitted values. The empty value is always\n"
            "included, and is the default. For example, the list 'one,two,three' has\n"
            "four values, the first of them being the empty value."))
        self.enum_default_label = la = QLabel(_("Values"))
        la.setBuddy(eb)
        l.addWidget(eb), l.addWidget(la, 0, 1)
        self.enum_colors = ec = QLineEdit(self)
        ec.setToolTip(_("A list of color names to use when displaying an item. The\n"
            "list must be empty or contain a color for each value."))
        self.enum_colors_label = la = QLabel(_('Colors'))
        la.setBuddy(ec)
        l.addWidget(ec), l.addWidget(la, 1, 1)
        self.enum_label = add_row(_('&Values'), l)

        # Rating allow half stars
        self.allow_half_stars = ahs = QCheckBox(_('Allow half stars'))
        ahs.setToolTip(_('Allow half star ratings, for example: ') + '<span style="font-family:calibre Symbols">★★★½</span>')
        add_row(None, ahs)

        # Composite display properties
        l = QHBoxLayout()
        self.composite_sort_by_label = la = QLabel(_("&Sort/search column by"))
        self.composite_sort_by = csb = QComboBox(self)
        la.setBuddy(csb), csb.setToolTip(_("How this column should handled in the GUI when sorting and searching"))
        l.addWidget(la), l.addWidget(csb)
        self.composite_make_category = cmc = QCheckBox(_("Show in tags browser"))
        cmc.setToolTip(_("If checked, this column will appear in the tags browser as a category"))
        l.addWidget(cmc)
        self.composite_contains_html = cch = QCheckBox(_("Show as HTML in book details"))
        cch.setToolTip('<p>' +
                _('If checked, this column will be displayed as HTML in '
                  'book details and the content server. This can be used to '
                  'construct links with the template language. For example, '
                  'the template '
                  '<pre>&lt;big&gt;&lt;b&gt;{title}&lt;/b&gt;&lt;/big&gt;'
                  '{series:| [|}{series_index:| [|]]}</pre>'
                  'will create a field displaying the title in bold large '
                  'characters, along with the series, for example <br>"<big><b>'
                  'An Oblique Approach</b></big> [Belisarius [1]]". The template '
                  '<pre>&lt;a href="https://www.beam-ebooks.de/ebook/{identifiers'
                  ':select(beam)}"&gt;Beam book&lt;/a&gt;</pre> '
                  'will generate a link to the book on the Beam ebooks site.') + '</p>')
        l.addWidget(cch)
        add_row(None, l)

        self.resize(self.sizeHint())
    # }}}

    def datatype_changed(self, *args):
        try:
            col_type = self.column_types[self.column_type_box.currentIndex()]['datatype']
        except:
            col_type = None
        needs_format = col_type in ('datetime', 'int', 'float')
        for x in ('box', 'default_label', 'label'):
            getattr(self, 'format_'+x).setVisible(needs_format)
        if needs_format:
            if col_type == 'datetime':
                l, dl = _('&Format for dates'), _('Default: dd MMM yyyy.')
                self.format_box.setToolTip(_(
                    "<p>Date format. Use 1-4 \'d\'s for day, 1-4 \'M\'s for month, and 2 or 4 \'y\'s for year.</p>\n"
                    "<p>For example:\n"
                    "<ul>\n"
                    "<li>ddd, d MMM yyyy gives Mon, 5 Jan 2010<li>\n"
                    "<li>dd MMMM yy gives 05 January 10</li>\n"
                    "</ul> "))
            else:
                l, dl = _('&Format for numbers'), (
                    '<p>' + _('Default: Not formatted. For format language details see'
                    ' <a href="https://docs.python.org/library/string.html#format-string-syntax">the python documentation</a>'))
                if col_type == 'int':
                    self.format_box.setToolTip('<p>' +
                        _('Examples: The format <code>{0:0>4d}</code> '
                        'gives a 4-digit number with leading zeros. The format '
                        '<code>{0:d}&nbsp;days</code> prints the number then the word "days"')+ '</p>')
                else:
                    self.format_box.setToolTip('<p>' +
                        _('Examples: The format <code>{0:.1f}</code> gives a floating '
                        'point number with 1 digit after the decimal point. The format '
                        '<code>Price:&nbsp;$&nbsp;{0:,.2f}</code> prints '
                        '"Price&nbsp;$&nbsp;" then displays the number with 2 digits '
                        'after the decimal point and thousands separated by commas.') + '</p>'
                    )
            self.format_label.setText(l), self.format_default_label.setText(dl)
        for x in ('box', 'default_label', 'label', 'sort_by', 'sort_by_label',
                  'make_category', 'contains_html'):
            getattr(self, 'composite_'+x).setVisible(col_type in ['composite', '*composite'])
        for x in ('box', 'default_label', 'label', 'colors', 'colors_label'):
            getattr(self, 'enum_'+x).setVisible(col_type == 'enumeration')
        self.use_decorations.setVisible(col_type in ['text', 'composite', 'enumeration'])
        self.is_names.setVisible(col_type == '*text')
        is_comments = col_type == 'comments'
        self.comments_heading_position.setVisible(is_comments)
        self.comments_heading_position_label.setVisible(is_comments)
        self.comments_type.setVisible(is_comments)
        self.comments_type_label.setVisible(is_comments)
        self.allow_half_stars.setVisible(col_type == 'rating')

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
        coldef = self.column_types[self.column_type_box.currentIndex()]
        col_type = coldef['datatype']
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
            if unicode(self.format_box.text()).strip():
                display_dict = {'date_format':unicode(self.format_box.text()).strip()}
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
                if tc not in QColor.colorNames() and not re.match("#(?:[0-9a-f]{3}){1,4}",tc,re.I):
                    return self.simple_error('',
                            _('The color {0} is unknown').format(tc))

            display_dict = {'enum_values': l, 'enum_colors': c}
        elif col_type == 'text' and is_multiple:
            display_dict = {'is_names': self.is_names.isChecked()}
        elif col_type in ['int', 'float']:
            if unicode(self.format_box.text()).strip():
                display_dict = {'number_format':unicode(self.format_box.text()).strip()}
            else:
                display_dict = {'number_format': None}
        elif col_type == 'comments':
            display_dict['heading_position'] = type(u'')(self.comments_heading_position.currentData())
            display_dict['interpret_as'] = type(u'')(self.comments_type.currentData())
        elif col_type == 'rating':
            display_dict['allow_half_stars'] = bool(self.allow_half_stars.isChecked())

        if col_type in ['text', 'composite', 'enumeration'] and not is_multiple:
            display_dict['use_decorations'] = self.use_decorations.checkState()
        display_dict['description'] = self.description_box.text().strip()

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
            self.parent.cc_column_key = key
        else:
            self.parent.custcols[self.orig_column_name]['label'] = col
            self.parent.custcols[self.orig_column_name]['name'] = col_heading
            self.parent.custcols[self.orig_column_name]['display'].update(display_dict)
            self.parent.custcols[self.orig_column_name]['*edited'] = True
            self.parent.custcols[self.orig_column_name]['*must_restart'] = True
            self.parent.cc_column_key = key
        QDialog.accept(self)

    def reject(self):
        QDialog.reject(self)
