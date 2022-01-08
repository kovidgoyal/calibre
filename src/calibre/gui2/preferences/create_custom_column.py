#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid at kovidgoyal.net>'

'''Dialog to create a new custom column'''

import copy, re
from enum import Enum
from functools import partial

from qt.core import (
    QDialog, Qt, QColor, QIcon, QVBoxLayout, QLabel, QGridLayout,
    QDialogButtonBox, QWidget, QLineEdit, QHBoxLayout, QComboBox,
    QCheckBox, QSpinBox, QRadioButton, QGroupBox
)

from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.template_line_editor import TemplateLineEditor
from calibre.utils.date import parse_date, UNDEFINED_DATE
from polyglot.builtins import iteritems


class CreateCustomColumn(QDialog):

    # Note: in this class, we are treating is_multiple as the boolean that
    # custom_columns expects to find in its structure. It does not use the dict

    column_types = dict(enumerate((
        {
            'datatype':'text',
            'text':_('Text, column shown in the Tag browser'),
            'is_multiple':False
        },
        {
            'datatype':'*text',
            'text':_('Comma separated text, like tags, shown in the Tag browser'),
            'is_multiple':True
        },
        {
            'datatype':'comments',
            'text':_('Long text, like comments, not shown in the Tag browser'),
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
    column_types_map = {k['datatype']:idx for idx, k in iteritems(column_types)}

    def __init__(self, gui, caller, current_key, standard_colheads, freeze_lookup_name=False):
        QDialog.__init__(self, gui)
        self.gui = gui
        self.setup_ui()
        self.setWindowTitle(_('Create a custom column'))
        self.heading_label.setText('<b>' + _('Create a custom column'))
        # Remove help icon on title bar
        icon = self.windowIcon()
        self.setWindowFlags(self.windowFlags()&(~Qt.WindowType.WindowContextHelpButtonHint))
        self.setWindowIcon(icon)

        self.simple_error = partial(error_dialog, self, show=True,
            show_copy_button=False)
        for sort_by in [_('Text'), _('Number'), _('Date'), _('Yes/No')]:
            self.composite_sort_by.addItem(sort_by)

        self.caller = caller
        self.caller.cc_column_key = None
        self.editing_col = current_key is not None
        self.standard_colheads = standard_colheads
        self.column_type_box.setMaxVisibleItems(len(self.column_types))
        for t in self.column_types:
            self.column_type_box.addItem(self.column_types[t]['text'])
        self.column_type_box.currentIndexChanged.connect(self.datatype_changed)

        if not self.editing_col:
            self.datatype_changed()
            self.exec()
            return

        self.setWindowTitle(_('Edit custom column'))
        self.heading_label.setText('<b>' + _('Edit custom column'))
        self.shortcuts.setVisible(False)
        col = current_key
        if col not in caller.custcols:
            self.simple_error('', _('The selected column is not a user-defined column'))
            return

        c = caller.custcols[col]
        self.column_name_box.setText(c['label'])
        if freeze_lookup_name:
            self.column_name_box.setEnabled(False)
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
        elif ct == 'bool':
            icon = bool(c['display'].get('bools_show_icons', True))
            txt = bool(c['display'].get('bools_show_text', False))
            if icon and txt:
                self.bool_show_both_button.click()
            elif icon:
                self.bool_show_icon_button.click()
            else:
                self.bool_show_text_button.click()

        # Default values
        dv = c['display'].get('default_value', None)
        if dv is not None:
            if ct == 'bool':
                self.default_value.setText(_('Yes') if dv else _('No'))
            elif ct == 'datetime':
                self.default_value.setText(_('Now') if dv == 'now' else dv)
            elif ct == 'rating':
                if self.allow_half_stars.isChecked():
                    self.default_value.setText(str(dv/2))
                else:
                    self.default_value.setText(str(dv//2))
            elif ct in ('int', 'float'):
                self.default_value.setText(str(dv))
            elif ct not in ('composite', '*composite'):
                self.default_value.setText(dv)

        self.datatype_changed()
        if ct in ['text', 'composite', 'enumeration']:
            self.use_decorations.setChecked(c['display'].get('use_decorations', False))
        elif ct == '*text':
            self.is_names.setChecked(c['display'].get('is_names', False))
        self.description_box.setText(c['display'].get('description', ''))
        self.decimals_box.setValue(min(9, max(1, int(c['display'].get('decimals', 2)))))

        all_colors = [str(s) for s in list(QColor.colorNames())]
        self.enum_colors_label.setToolTip('<p>' + ', '.join(all_colors) + '</p>')
        self.exec()

    def shortcut_activated(self, url):  # {{{
        which = str(url).split(':')[-1]
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
                    'formats': "{:'re(approximate_formats(), ',', ', ')'}",
                    }[which])
            self.composite_sort_by.setCurrentIndex(0)
        if which == 'text':
            self.comments_heading_position.setCurrentIndex(self.comments_heading_position.findData('side'))
            self.comments_type.setCurrentIndex(self.comments_type.findData('short-text'))
    # }}}

    def setup_ui(self):  # {{{
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowIcon(QIcon.ic('column.png'))
        self.vl = l = QVBoxLayout(self)
        self.heading_label = la = QLabel('')
        l.addWidget(la)
        self.shortcuts = s = QLabel('')
        s.setWordWrap(True)
        s.linkActivated.connect(self.shortcut_activated)
        text = '<p>'+_('Quick create:')
        for col, name in [('isbn', _('ISBN')), ('formats', _('Formats')),
                ('yesno', _('Yes/No')),
                ('tags', _('Tags')), ('series', ngettext('Series', 'Series', 1)), ('rating',
                    _('Rating')), ('people', _("Names")), ('text', _('Short text'))]:
            text += ' <a href="col:%s">%s</a>,'%(col, name)
        text = text[:-1]
        s.setText(text)
        l.addWidget(s)
        self.g = g = QGridLayout()
        l.addLayout(g)
        l.addStretch(10)
        self.button_box = bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
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
        add_row(_("&Lookup name:"), cnb)

        # Heading
        self.column_heading_box = chb = QLineEdit(self)
        chb.setToolTip(_("Column heading in the library view and category name in the Tag browser"))
        add_row(_("Column &heading:"), chb)

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
        add_row(_("&Column type:"), h)

        # Description
        self.description_box = d = QLineEdit(self)
        d.setToolTip(_("Optional text describing what this column is for"))
        add_row(_("D&escription:"), d)

        # bool formatting
        h1 = QHBoxLayout()

        def add_bool_radio_button(txt):
            b = QRadioButton(txt)
            b.clicked.connect(partial(self.bool_radio_button_clicked, b))
            h1.addWidget(b)
            return b
        self.bool_show_icon_button = add_bool_radio_button(_('&Icon'))
        self.bool_show_text_button = add_bool_radio_button(_('&Text'))
        self.bool_show_both_button = add_bool_radio_button(_('&Both'))
        self.bool_button_group = QGroupBox()
        self.bool_button_group.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.bool_button_group.setLayout(h1)
        h = QHBoxLayout()
        h.addWidget(self.bool_button_group)
        self.bool_button_group_label = la = QLabel(_('Choose whether an icon, text, or both is shown in the book list'))
        la.setWordWrap(True)
        h.addWidget(la)
        h.setStretch(1, 10)
        self.bool_show_label = add_row(_('&Show:'), h)

        # Date/number formatting
        h = QHBoxLayout()
        self.format_box = fb = QLineEdit(self)
        h.addWidget(fb)
        self.format_default_label = la = QLabel('')
        la.setOpenExternalLinks(True), la.setWordWrap(True)
        h.addWidget(la)
        self.format_label = add_row('', h)

        # Float number of decimal digits
        h = QHBoxLayout()
        self.decimals_box = fb = QSpinBox(self)
        fb.setRange(1, 9)
        fb.setValue(2)
        h.addWidget(fb)
        self.decimals_default_label = la = QLabel(_(
            'Control the number of decimal digits you can enter when editing this column'))
        la.setWordWrap(True)
        h.addWidget(la)
        self.decimals_label = add_row(_('Decimals when &editing:'), h)

        # Template
        self.composite_box = cb = TemplateLineEditor(self)
        self.composite_default_label = cdl = QLabel(_("Default: (nothing)"))
        cb.setToolTip(_("Field template. Uses the same syntax as save templates."))
        cdl.setToolTip(_("Similar to save templates. For example, %s") % "{title} {isbn}")
        h = QHBoxLayout()
        h.addWidget(cb), h.addWidget(cdl)
        self.composite_label = add_row(_("&Template:"), h)

        # Comments properties
        self.comments_heading_position = ct = QComboBox(self)
        for k, text in (
                ('hide', _('No heading')),
                ('above', _('Show heading above the text')),
                ('side', _('Show heading to the side of the text'))
        ):
            ct.addItem(text, k)
        ct.setToolTip(_('Choose whether or not the column heading is shown in the Book\n'
                        'details panel and, if shown, where'))
        self.comments_heading_position_label = add_row(_('Column heading:'), ct)

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
        self.enum_box = eb = QLineEdit(self)
        eb.setToolTip(_(
            "A comma-separated list of permitted values. The empty value is always\n"
            "included, and is the default. For example, the list 'one,two,three' has\n"
            "four values, the first of them being the empty value."))
        self.enum_default_label = add_row(_("&Values:"), eb)
        self.enum_colors = ec = QLineEdit(self)
        ec.setToolTip(_("A list of color names to use when displaying an item. The\n"
            "list must be empty or contain a color for each value."))
        self.enum_colors_label = add_row(_('Colors:'), ec)

        # Rating allow half stars
        self.allow_half_stars = ahs = QCheckBox(_('Allow half stars'))
        ahs.setToolTip(_('Allow half star ratings, for example: ') + '★★★⯨')
        add_row(None, ahs)

        # Composite display properties
        l = QHBoxLayout()
        self.composite_sort_by_label = la = QLabel(_("&Sort/search column by"))
        self.composite_sort_by = csb = QComboBox(self)
        la.setBuddy(csb), csb.setToolTip(_("How this column should handled in the GUI when sorting and searching"))
        l.addWidget(la), l.addWidget(csb)
        self.composite_make_category = cmc = QCheckBox(_("Show in Tag browser"))
        cmc.setToolTip(_("If checked, this column will appear in the Tag browser as a category"))
        l.addWidget(cmc)
        self.composite_contains_html = cch = QCheckBox(_("Show as HTML in Book details"))
        cch.setToolTip('<p>' + _(
            'If checked, this column will be displayed as HTML in '
            'Book details and the Content server. This can be used to '
            'construct links with the template language. For example, '
            'the template '
            '<pre>&lt;big&gt;&lt;b&gt;{title}&lt;/b&gt;&lt;/big&gt;'
            '{series:| [|}{series_index:| [|]]}</pre>'
            'will create a field displaying the title in bold large '
            'characters, along with the series, for example <br>"<big><b>'
            'An Oblique Approach</b></big> [Belisarius [1]]". The template '
            '<pre>&lt;a href="https://www.beam-ebooks.de/ebook/{identifiers'
            ':select(beam)}"&gt;Beam book&lt;/a&gt;</pre> '
            'will generate a link to the book on the Beam e-books site.') + '</p>')
        l.addWidget(cch)
        add_row(None, l)

        # Default value
        self.default_value = dv = QLineEdit(self)
        dv.setToolTip('<p>' + _('Default value when a new book is added to the '
            'library. For Date columns enter the word "Now", or the date as '
            'yyyy-mm-dd. For Yes/No columns enter "Yes" or "No". For Text with '
            'a fixed set of values enter one of the permitted values. For '
            'Rating columns enter a number between 0 and 5.') + '</p>')
        self.default_value_label = add_row(_('&Default value:'), dv)

        self.resize(self.sizeHint())
    # }}}

    def bool_radio_button_clicked(self, button, clicked):
        if clicked:
            self.bool_button_group.setFocusProxy(button)

    def datatype_changed(self, *args):
        try:
            col_type = self.column_types[self.column_type_box.currentIndex()]['datatype']
        except:
            col_type = None
        needs_format = col_type in ('datetime', 'int', 'float')
        for x in ('box', 'default_label', 'label'):
            getattr(self, 'format_'+x).setVisible(needs_format)
            getattr(self, 'decimals_'+x).setVisible(col_type == 'float')
        if needs_format:
            if col_type == 'datetime':
                l, dl = _('&Format for dates:'), _('Default: dd MMM yyyy.')
                self.format_box.setToolTip(_(
                    '<p>Date format.</p>'
                    '<p>The formatting codes are:'
                    '<ul>'
                    '<li>d    : the day as number without a leading zero (1 to 31)</li>'
                    '<li>dd   : the day as number with a leading zero (01 to 31)</li>'
                    '<li>ddd  : the abbreviated localized day name (e.g. "Mon" to "Sun").</li>'
                    '<li>dddd : the long localized day name (e.g. "Monday" to "Sunday").</li>'
                    '<li>M    : the <b>month</b> as number without a leading zero (1 to 12).</li>'
                    '<li>MM   : the <b>month</b> as number with a leading zero (01 to 12)</li>'
                    '<li>MMM  : the abbreviated localized <b>month</b> name (e.g. "Jan" to "Dec").</li>'
                    '<li>MMMM : the long localized <b>month</b> name (e.g. "January" to "December").</li>'
                    '<li>yy   : the year as two digit number (00 to 99).</li>'
                    '<li>yyyy : the year as four digit number.</li>'
                    '<li>h    : the hours without a leading 0 (0 to 11 or 0 to 23, depending on am/pm)</li>'
                    '<li>hh   : the hours with a leading 0 (00 to 11 or 00 to 23, depending on am/pm)</li>'
                    '<li>m    : the <b>minutes</b> without a leading 0 (0 to 59)</li>'
                    '<li>mm   : the <b>minutes</b> with a leading 0 (00 to 59)</li>'
                    '<li>s    : the seconds without a leading 0 (0 to 59)</li>'
                    '<li>ss   : the seconds with a leading 0 (00 to 59)</li>'
                    '<li>ap   : use a 12-hour clock instead of a 24-hour clock, with "ap" replaced by the localized string for am or pm</li>'
                    '<li>AP   : use a 12-hour clock instead of a 24-hour clock, with "AP" replaced by the localized string for AM or PM</li>'
                    '<li>iso  : the date with time and timezone. Must be the only format present</li>'
                    '</ul></p>'
                    "<p>For example:\n"
                    "<ul>\n"
                    "<li>ddd, d MMM yyyy gives Mon, 5 Jan 2010</li>\n"
                    "<li>dd MMMM yy gives 05 January 10</li>\n"
                    "</ul> "))
            else:
                l, dl = _('&Format for numbers:'), (
                    '<p>' + _('Default: Not formatted. For format language details see'
                    ' <a href="https://docs.python.org/library/string.html#format-string-syntax">the Python documentation</a>'))
                if col_type == 'int':
                    self.format_box.setToolTip('<p>' + _(
                        'Examples: The format <code>{0:0>4d}</code> '
                        'gives a 4-digit number with leading zeros. The format '
                        '<code>{0:d}&nbsp;days</code> prints the number then the word "days"')+ '</p>')
                else:
                    self.format_box.setToolTip('<p>' + _(
                        'Examples: The format <code>{0:.1f}</code> gives a floating '
                        'point number with 1 digit after the decimal point. The format '
                        '<code>Price:&nbsp;$&nbsp;{0:,.2f}</code> prints '
                        '"Price&nbsp;$&nbsp;" then displays the number with 2 digits '
                        'after the decimal point and thousands separated by commas.') + '</p>'
                    )
            self.format_label.setText(l), self.format_default_label.setText(dl)
        for x in ('box', 'default_label', 'label', 'sort_by', 'sort_by_label',
                  'make_category', 'contains_html'):
            getattr(self, 'composite_'+x).setVisible(col_type in ['composite', '*composite'])
        for x in ('box', 'default_label',  'colors', 'colors_label'):
            getattr(self, 'enum_'+x).setVisible(col_type == 'enumeration')
        for x in ('value_label', 'value'):
            getattr(self, 'default_'+x).setVisible(col_type not in ['composite', '*composite'])
        self.use_decorations.setVisible(col_type in ['text', 'composite', 'enumeration'])
        self.is_names.setVisible(col_type == '*text')

        is_comments = col_type == 'comments'
        self.comments_heading_position.setVisible(is_comments)
        self.comments_heading_position_label.setVisible(is_comments)
        self.comments_type.setVisible(is_comments)
        self.comments_type_label.setVisible(is_comments)
        self.allow_half_stars.setVisible(col_type == 'rating')

        is_bool = col_type == 'bool'
        self.bool_button_group.setVisible(is_bool)
        self.bool_button_group_label.setVisible(is_bool)
        self.bool_show_label.setVisible(is_bool)

    def accept(self):
        col = str(self.column_name_box.text()).strip()
        if not col:
            return self.simple_error('', _('No lookup name was provided'))
        if col.startswith('#'):
            col = col[1:]
        if re.match(r'^\w*$', col) is None or not col[0].isalpha() or col.lower() != col:
            return self.simple_error('', _('The lookup name must contain only '
                    'lower case letters, digits and underscores, and start with a letter'))
        if col.endswith('_index'):
            return self.simple_error('', _('Lookup names cannot end with _index, '
                    'because these names are reserved for the index of a series column.'))
        col_heading = str(self.column_heading_box.text()).strip()
        coldef = self.column_types[self.column_type_box.currentIndex()]
        col_type = coldef['datatype']
        if col_type[0] == '*':
            col_type = col_type[1:]
            is_multiple = True
        else:
            is_multiple = False
        if not col_heading:
            return self.simple_error('', _('No column heading was provided'))

        db = self.gui.library_view.model().db
        key = db.field_metadata.custom_field_prefix+col
        cc = self.caller.custcols
        if key in cc and (not self.editing_col or cc[key]['colnum'] != self.orig_column_number):
            return self.simple_error('', _('The lookup name %s is already used')%col)
        bad_head = False
        for cc in self.caller.custcols.values():
            if cc['name'] == col_heading and cc['colnum'] != self.orig_column_number:
                bad_head = True
                break
        for t in self.standard_colheads:
            if self.standard_colheads[t] == col_heading:
                bad_head = True
        if bad_head:
            return self.simple_error('', _('The heading %s is already used')%col_heading)

        display_dict = {}

        default_val = (str(self.default_value.text()).strip()
                        if col_type != 'composite' else None)

        if col_type == 'datetime':
            if str(self.format_box.text()).strip():
                display_dict = {'date_format':str(self.format_box.text()).strip()}
            else:
                display_dict = {'date_format': None}
            if default_val:
                if default_val == _('Now'):
                    display_dict['default_value'] = 'now'
                else:
                    try:
                        tv = parse_date(default_val)
                    except:
                        tv = UNDEFINED_DATE
                    if tv == UNDEFINED_DATE:
                        return self.simple_error(_('Invalid default value'),
                                 _('The default value must be "Now" or a date'))
                    display_dict['default_value'] = default_val
        elif col_type == 'composite':
            if not str(self.composite_box.text()).strip():
                return self.simple_error('', _('You must enter a template for '
                           'composite columns'))
            display_dict = {'composite_template':str(self.composite_box.text()).strip(),
                            'composite_sort': ['text', 'number', 'date', 'bool']
                                        [self.composite_sort_by.currentIndex()],
                            'make_category': self.composite_make_category.isChecked(),
                            'contains_html': self.composite_contains_html.isChecked(),
                        }
        elif col_type == 'enumeration':
            if not str(self.enum_box.text()).strip():
                return self.simple_error('', _('You must enter at least one '
                            'value for enumeration columns'))
            l = [v.strip() for v in str(self.enum_box.text()).split(',') if v.strip()]
            l_lower = [v.lower() for v in l]
            for i,v in enumerate(l_lower):
                if v in l_lower[i+1:]:
                    return self.simple_error('', _('The value "{0}" is in the '
                    'list more than once, perhaps with different case').format(l[i]))
            c = str(self.enum_colors.text())
            if c:
                c = [v.strip() for v in str(self.enum_colors.text()).split(',')]
            else:
                c = []
            if len(c) != 0 and len(c) != len(l):
                return self.simple_error('', _('The colors box must be empty or '
                           'contain the same number of items as the value box'))
            for tc in c:
                if tc not in QColor.colorNames() and not re.match("#(?:[0-9a-f]{3}){1,4}",tc,re.I):
                    return self.simple_error('', _('The color {0} is unknown').format(tc))
            display_dict = {'enum_values': l, 'enum_colors': c}
            if default_val:
                if default_val not in l:
                    return self.simple_error(_('Invalid default value'),
                             _('The default value must be one of the permitted values'))
                display_dict['default_value'] = default_val
        elif col_type == 'text' and is_multiple:
            display_dict = {'is_names': self.is_names.isChecked()}
        elif col_type in ['int', 'float']:
            if str(self.format_box.text()).strip():
                display_dict = {'number_format':str(self.format_box.text()).strip()}
            else:
                display_dict = {'number_format': None}
            if col_type == 'float':
                display_dict['decimals'] = int(self.decimals_box.value())
            if default_val:
                try:
                    if col_type == 'int':
                        msg = _('The default value must be an integer')
                        tv = int(default_val)
                        display_dict['default_value'] = tv
                    else:
                        msg = _('The default value must be a real number')
                        tv = float(default_val)
                        display_dict['default_value'] = tv
                except:
                    return self.simple_error(_('Invalid default value'), msg)
        elif col_type == 'comments':
            display_dict['heading_position'] = str(self.comments_heading_position.currentData())
            display_dict['interpret_as'] = str(self.comments_type.currentData())
        elif col_type == 'rating':
            half_stars = bool(self.allow_half_stars.isChecked())
            display_dict['allow_half_stars'] = half_stars
            if default_val:
                try:
                    tv = int((float(default_val) if half_stars else int(default_val)) * 2)
                except:
                    tv = -1
                if tv < 0 or tv > 10:
                    if half_stars:
                        return self.simple_error(_('Invalid default value'),
                             _('The default value must be a real number between 0 and 5.0'))
                    else:
                        return self.simple_error(_('Invalid default value'),
                             _('The default value must be an integer between 0 and 5'))
                display_dict['default_value'] = tv
        elif col_type == 'bool':
            if default_val:
                tv = {_('Yes'): True, _('No'): False}.get(default_val, None)
                if tv is None:
                    return self.simple_error(_('Invalid default value'),
                             _('The default value must be "Yes" or "No"'))
                display_dict['default_value'] = tv
            show_icon = bool(self.bool_show_icon_button.isChecked()) or bool(self.bool_show_both_button.isChecked())
            show_text = bool(self.bool_show_text_button.isChecked()) or bool(self.bool_show_both_button.isChecked())
            display_dict['bools_show_text'] = show_text
            display_dict['bools_show_icons'] = show_icon

        if col_type in ['text', 'composite', 'enumeration'] and not is_multiple:
            display_dict['use_decorations'] = self.use_decorations.checkState() == Qt.CheckState.Checked

        if default_val and 'default_value' not in display_dict:
            display_dict['default_value'] = default_val

        display_dict['description'] = self.description_box.text().strip()

        if not self.editing_col:
            self.caller.custcols[key] = {
                    'label':col,
                    'name':col_heading,
                    'datatype':col_type,
                    'display':display_dict,
                    'normalized':None,
                    'colnum':None,
                    'is_multiple':is_multiple,
                }
            self.caller.cc_column_key = key
        else:
            cc = self.caller.custcols[self.orig_column_name]
            cc['label'] = col
            cc['name'] = col_heading
            # Remove any previous default value
            cc['display'].pop('default_value', None)
            cc['display'].update(display_dict)
            cc['*edited'] = True
            cc['*must_restart'] = True
            self.caller.cc_column_key = key
        QDialog.accept(self)

    def reject(self):
        QDialog.reject(self)


class CreateNewCustomColumn:
    """
    Provide an API to create new custom columns.

    Usage:
        from calibre.gui2.preferences.create_custom_column import CreateNewCustomColumn
        creator = CreateNewCustomColumn(gui)
        if creator.must_restart():
                ...
        else:
            result = creator.create_column(....)
            if result[0] == creator.Result.COLUMN_ADDED:

    The parameter 'gui' passed when creating a class instance is the main
    calibre gui (calibre.gui2.ui.get_gui())

    Use the create_column(...) method to open a dialog to create a new custom
    column with given lookup_name, column_heading, datatype, and is_multiple.
    You can create as many columns as you wish with a single instance of the
    CreateNewCustomColumn class. Subsequent class instances will refuse to
    create columns until calibre is restarted, as will calibre Preferences.

    The lookup name must begin with a '#'. All remaining characters must be
    lower case letters, digits or underscores. The character after the '#' must
    be a letter. The lookup name must not end with the suffix '_index'.

    The datatype must be one of calibre's custom column types: 'bool',
    'comments', 'composite', 'datetime', 'enumeration', 'float', 'int',
    'rating', 'series', or 'text'. The datatype can't be changed in the dialog.

    is_multiple tells calibre that the column contains multiple values -- is
    tags-like. The value True is allowed only for 'composite' and 'text' types.

    If generate_unused_lookup_name is False then the provided lookup_name and
    column_heading must not already exist. If generate_unused_lookup_name is
    True then if necessary the method will add the suffix '_n' to the provided
    lookup_name to allocate an unused lookup_name, where 'n' is an integer.
    The same processing is applied to column_heading to make it is unique, using
    the same suffix used for the lookup name if possible. In either case the
    user can change the column heading in the dialog.

    Set freeze_lookup_name to False if you want to allow the user choose a
    different lookup name. The user will not be allowed to choose the lookup
    name of an existing column. The provided lookup_name and column_heading
    either must not exist or generate_unused_lookup_name must be True,
    regardless of the value of freeze_lookup_name.

    The 'display' parameter is used to pass item- and type-specific information
    for the column. It is a dict. The easiest way to see the current values for
    'display' for a particular column is to create a column like you want then
    look for the lookup name in the file metadata_db_prefs_backup.json. You must
    restart calibre twice after creating a new column before its information
    will appear in that file.

    The key:value pairs for each type are as follows. Note that this
    list might be incorrect. As said above, the best way to get current values
    is to create a similar column and look at the values in 'display'.
      all types:
        'default_value': a string representation of the default value for the
                         column. Permitted values are type specific
        'description': a string containing the column's description
      comments columns:
        'heading_position': a string specifying where a comment heading goes:
                            hide, above, side
        'interpret_as': a string specifying the comment's purpose:
                        html, short-text, long-text, markdown
      composite columns:
        'composite_template': a string containing the template for the composite column
        'composite_sort': a string specifying how the composite is to be sorted
        'make_category': True or False -- whether the column is shown in the tag browser
        'contains_html': True or False -- whether the column is interpreted as HTML
        'use_decorations': True or False -- should check marks be displayed
      datetime columns:
        'date_format': a string specifying the display format
      enumerated columns
        'enum_values': a string containing comma-separated valid values for an enumeration
        'enum_colors': a string containing comma-separated colors for an enumeration
        'use_decorations': True or False -- should check marks be displayed
      float columns:
        'decimals': the number of decimal digits to allow when editing (int). Range: 1 - 9
      float and int columns:
        'number_format': the format to apply when displaying the column
      rating columns:
        'allow_half_stars': True or False -- are half-stars allowed
      text columns:
        'is_names': True or False -- whether the items are comma or ampersand separated
        'use_decorations': True or False -- should check marks be displayed

    This method returns a tuple (Result.enum_value, message). If tuple[0] is
    Result.COLUMN_ADDED then the message is the lookup name including the '#'.
    Otherwise it is a potentially localized error message.

    You or the user must restart calibre for the column(s) to be actually added.

    Result.EXCEPTION_RAISED is returned if the create dialog raises an exception.
    This can happen if the display contains illegal values, for example a string
    where a boolean is required. The string is the exception text. Run calibre
    in debug mode to see the entire traceback.

    The method returns Result.MUST_RESTART if further calibre configuration has
    been blocked. You can check for this situation in advance by calling
    must_restart().
    """

    class Result(Enum):
        COLUMN_ADDED = 0
        CANCELED = 1
        INVALID_KEY = 2
        DUPLICATE_KEY = 3
        DUPLICATE_HEADING = 4
        INVALID_TYPE = 5
        INVALID_IS_MULTIPLE = 6
        INVALID_DISPLAY = 7
        EXCEPTION_RAISED = 8
        MUST_RESTART = 9

    def __init__(self, gui):
        self.gui = gui
        self.restart_required = gui.must_restart_before_config
        self.db = db = self.gui.library_view.model().db
        self.custcols = copy.deepcopy(db.field_metadata.custom_field_metadata())
        # Get the largest internal column number so we can be sure that we can
        # detect duplicates.
        self.created_count = max((x['colnum'] for x in self.custcols.values()),
                                         default=0) + 1

    def create_column(self, lookup_name, column_heading, datatype, is_multiple,
                      display={}, generate_unused_lookup_name=False, freeze_lookup_name=True):
        """ See the class documentation for more information."""
        if self.restart_required:
            return (self.Result.MUST_RESTART, _("You must restart calibre before making any more changes"))
        if not lookup_name.startswith('#'):
            return (self.Result.INVALID_KEY, _("The lookup name must begin with a '#'"))
        suffix_number = 1
        if lookup_name in self.custcols:
            if not generate_unused_lookup_name:
                return(self.Result.DUPLICATE_KEY, _("The custom column %s already exists") % lookup_name)
            for suffix_number in range(suffix_number, 100000):
                nk = '%s_%d'%(lookup_name, suffix_number)
                if nk not in self.custcols:
                    lookup_name = nk
                    break
        if column_heading:
            headings = {v['name'] for v in self.custcols.values()}
            if column_heading in headings:
                if not generate_unused_lookup_name:
                    return(self.Result.DUPLICATE_HEADING,
                           _("The column heading %s already exists") % column_heading)
                for i in range(suffix_number, 100000):
                    nh = '%s_%d'%(column_heading, i)
                    if nh not in headings:
                        column_heading = nh
                        break
        else:
            column_heading = lookup_name
        if datatype not in CreateCustomColumn.column_types_map:
            return(self.Result.INVALID_TYPE,
                   _("The custom column type %s doesn't exist") % datatype)
        if is_multiple and '*' + datatype not in CreateCustomColumn.column_types_map:
            return(self.Result.INVALID_IS_MULTIPLE,
                   _("You cannot specify is_multiple for the datatype %s") % datatype)
        if not isinstance(display, dict):
            return(self.Result.INVALID_DISPLAY,
                   _("The display parameter must be a Python dict"))
        self.created_count += 1
        self.custcols[lookup_name] = {
                'label': lookup_name,
                'name': column_heading,
                'datatype': datatype,
                'display': display,
                'normalized': None,
                'colnum': self.created_count,
                'is_multiple': is_multiple,
            }
        try:
            dialog = CreateCustomColumn(self.gui, self, lookup_name,
                                        self.gui.library_view.model().orig_headers,
                                        freeze_lookup_name=freeze_lookup_name)
            if dialog.result() == QDialog.DialogCode.Accepted and self.cc_column_key is not None:
                cc = self.custcols[lookup_name]
                self.db.create_custom_column(
                                label=cc['label'],
                                name=cc['name'],
                                datatype=cc['datatype'],
                                is_multiple=cc['is_multiple'],
                                display=cc['display'])
                self.gui.must_restart_before_config = True
                return (self.Result.COLUMN_ADDED, self.cc_column_key)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.custcols.pop(lookup_name, None)
            return (self.Result.EXCEPTION_RAISED, str(e))
        self.custcols.pop(lookup_name, None)
        return (self.Result.CANCELED, _('Canceled'))

    def current_columns(self):
        """
        Return the currently defined custom columns

        Return the currently defined custom columns including the ones that haven't
        yet been created. It is a dict of dicts defined as follows:
            custcols[lookup_name] = {
                    'label': lookup_name,
                    'name': column_heading,
                    'datatype': datatype,
                    'display': display,
                    'normalized': None,
                    'colnum': an integer used internally,
                    'is_multiple': is_multiple,
                }
        Columns that already exist will have additional attributes that this class
        doesn't use. See calibre.library.field_metadata.add_custom_field() for the
        complete list.
        """
        # deepcopy to prevent users from changing it. The new MappingProxyType
        # isn't enough because only the top-level dict is immutable, not the
        # items in the dict.
        return copy.deepcopy(self.custcols)

    def current_headings(self):
        """
        Return the currently defined column headings

        Return the column headings including the ones that haven't yet been
        created. It is a dict. The key is the heading, the value is the lookup
        name having that heading.
        """
        return {v['name']:('#' + v['label']) for v in self.custcols.values()}

    def must_restart(self):
        """Return true if calibre must be restarted before new columns can be added."""
        return self.restart_required
