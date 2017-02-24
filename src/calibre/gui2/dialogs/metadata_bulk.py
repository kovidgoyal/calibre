__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''Dialog to edit metadata in bulk'''

import re, os
from collections import namedtuple, defaultdict
from threading import Thread

from PyQt5.Qt import Qt, QDialog, QGridLayout, QVBoxLayout, QFont, QLabel, \
                     pyqtSignal, QDialogButtonBox, QInputDialog, QLineEdit, \
                     QDateTime, QCompleter, QCoreApplication, QSize

from calibre.gui2.dialogs.metadata_bulk_ui import Ui_MetadataBulkDialog
from calibre.gui2.dialogs.tag_editor import TagEditor
from calibre.ebooks.metadata import string_to_authors, authors_to_string, title_sort
from calibre.ebooks.metadata.book.formatter import SafeFormat
from calibre.gui2.custom_column_widgets import populate_metadata_page
from calibre.gui2 import error_dialog, UNDEFINED_QDATETIME, \
    gprefs, question_dialog, FunctionDispatcher
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.metadata.basic_widgets import CalendarWidget
from calibre.utils.config import dynamic, JSONConfig
from calibre.utils.titlecase import titlecase
from calibre.utils.icu import sort_key, capitalize
from calibre.utils.config import prefs, tweaks
from calibre.utils.imghdr import identify
from calibre.utils.date import qt_to_dt
from calibre.db import _get_next_series_num_for_list


def get_cover_data(stream, ext):  # {{{
    from calibre.ebooks.metadata.meta import get_metadata
    old = prefs['read_file_metadata']
    if not old:
        prefs['read_file_metadata'] = True
    cdata = area = None

    try:
        with stream:
            mi = get_metadata(stream, ext)
        if mi.cover and os.access(mi.cover, os.R_OK):
            cdata = open(mi.cover).read()
        elif mi.cover_data[1] is not None:
            cdata = mi.cover_data[1]
        if cdata:
            fmt, width, height = identify(cdata)
            area = width*height
    except:
        cdata = area = None

    if old != prefs['read_file_metadata']:
        prefs['read_file_metadata'] = old

    return cdata, area
# }}}


Settings = namedtuple('Settings',
    'remove_all remove add au aus do_aus rating pub do_series do_autonumber '
    'do_swap_ta do_remove_conv do_auto_author series do_series_restart series_start_value series_increment '
    'do_title_case cover_action clear_series clear_pub pubdate adddate do_title_sort languages clear_languages '
    'restore_original comments generate_cover_settings')

null = object()


class MyBlockingBusy(QDialog):  # {{{

    all_done = pyqtSignal()

    def __init__(self, args, ids, db, refresh_books, cc_widgets, s_r_func, do_sr, sr_calls, parent=None, window_title=_('Working')):
        QDialog.__init__(self, parent)

        self._layout =  l = QVBoxLayout()
        self.setLayout(l)

        self.msg = QLabel(_('Processing %d books, please wait...') % len(ids))
        self.font = QFont()
        self.font.setPointSize(self.font.pointSize() + 8)
        self.msg.setFont(self.font)
        self.pi = ProgressIndicator(self)
        self.pi.setDisplaySize(100)
        self._layout.addWidget(self.pi, 0, Qt.AlignHCenter)
        self._layout.addSpacing(15)
        self._layout.addWidget(self.msg, 0, Qt.AlignHCenter)
        self.setWindowTitle(window_title + '...')
        self.setMinimumWidth(200)
        self.resize(self.sizeHint())
        self.error = None
        self.all_done.connect(self.on_all_done, type=Qt.QueuedConnection)
        self.args, self.ids = args, ids
        self.db, self.cc_widgets = db, cc_widgets
        self.s_r_func = FunctionDispatcher(s_r_func)
        self.do_sr = do_sr
        self.sr_calls = sr_calls
        self.refresh_books = refresh_books

    def accept(self):
        pass

    def reject(self):
        pass

    def on_all_done(self):
        if not self.error:
            # The cc widgets can only be accessed in the GUI thread
            try:
                for w in self.cc_widgets:
                    w.commit(self.ids)
            except Exception as err:
                import traceback
                self.error = (err, traceback.format_exc())
        self.pi.stopAnimation()
        QDialog.accept(self)

    def exec_(self):
        self.thread = Thread(target=self.do_it)
        self.thread.start()
        self.pi.startAnimation()
        return QDialog.exec_(self)

    def do_it(self):
        try:
            self.do_all()
        except Exception as err:
            import traceback
            try:
                err = unicode(err)
            except:
                err = repr(err)
            self.error = (err, traceback.format_exc())

        self.all_done.emit()

    def do_all(self):
        cache = self.db.new_api
        args = self.args

        # Title and authors
        if args.do_swap_ta:
            title_map = cache.all_field_for('title', self.ids)
            authors_map = cache.all_field_for('authors', self.ids)

            def new_title(authors):
                ans = authors_to_string(authors)
                return titlecase(ans) if args.do_title_case else ans
            new_title_map = {bid:new_title(authors) for bid, authors in authors_map.iteritems()}
            new_authors_map = {bid:string_to_authors(title) for bid, title in title_map.iteritems()}
            cache.set_field('authors', new_authors_map)
            cache.set_field('title', new_title_map)

        if args.do_title_case and not args.do_swap_ta:
            title_map = cache.all_field_for('title', self.ids)
            cache.set_field('title', {bid:titlecase(title) for bid, title in title_map.iteritems()})

        if args.do_title_sort:
            lang_map = cache.all_field_for('languages', self.ids)
            title_map = cache.all_field_for('title', self.ids)

            def get_sort(book_id):
                if args.languages:
                    lang = args.languages[0]
                else:
                    try:
                        lang = lang_map[book_id][0]
                    except (KeyError, IndexError, TypeError, AttributeError):
                        lang = 'eng'
                return title_sort(title_map[book_id], lang=lang)
            cache.set_field('sort', {bid:get_sort(bid) for bid in self.ids})

        if args.au:
            authors = string_to_authors(args.au)
            cache.set_field('authors', {bid:authors for bid in self.ids})

        if args.do_auto_author:
            aus_map = cache.author_sort_strings_for_books(self.ids)
            cache.set_field('author_sort', {book_id:' & '.join(aus_map[book_id]) for book_id in aus_map})

        if args.aus and args.do_aus:
            cache.set_field('author_sort', {bid:args.aus for bid in self.ids})

        # Covers
        if args.cover_action == 'remove':
            cache.set_cover({bid:None for bid in self.ids})
        elif args.cover_action == 'generate':
            from calibre.ebooks.covers import generate_cover
            for book_id in self.ids:
                mi = self.db.get_metadata(book_id, index_is_id=True)
                cdata = generate_cover(mi, prefs=args.generate_cover_settings)
                cache.set_cover({book_id:cdata})
        elif args.cover_action == 'fromfmt':
            for book_id in self.ids:
                fmts = cache.formats(book_id, verify_formats=False)
                if fmts:
                    covers = []
                    for fmt in fmts:
                        fmtf = cache.format(book_id, fmt, as_file=True)
                        if fmtf is None:
                            continue
                        cdata, area = get_cover_data(fmtf, fmt)
                        if cdata:
                            covers.append((cdata, area))
                    covers.sort(key=lambda x: x[1])
                    if covers:
                        cache.set_cover({book_id:covers[-1][0]})
        elif args.cover_action == 'trim':
            from calibre.utils.img import remove_borders_from_image, image_to_data, image_from_data
            for book_id in self.ids:
                cdata = cache.cover(book_id)
                if cdata:
                    img = image_from_data(cdata)
                    nimg = remove_borders_from_image(img)
                    if nimg is not img:
                        cdata = image_to_data(nimg)
                        cache.set_cover({book_id:cdata})
        elif args.cover_action == 'clone':
            cdata = None
            for book_id in self.ids:
                cdata = cache.cover(book_id)
                if cdata:
                    break
            if cdata:
                cache.set_cover({bid:cdata for bid in self.ids if bid != book_id})

        if args.restore_original:
            for book_id in self.ids:
                formats = cache.formats(book_id)
                originals = tuple(x.upper() for x in formats if x.upper().startswith('ORIGINAL_'))
                for ofmt in originals:
                    cache.restore_original_format(book_id, ofmt)

        # Various fields
        if args.rating != -1:
            cache.set_field('rating', {bid:args.rating for bid in self.ids})

        if args.clear_pub:
            cache.set_field('publisher', {bid:'' for bid in self.ids})

        if args.pub:
            cache.set_field('publisher', {bid:args.pub for bid in self.ids})

        if args.clear_series:
            cache.set_field('series', {bid:'' for bid in self.ids})

        if args.pubdate is not None:
            cache.set_field('pubdate', {bid:args.pubdate for bid in self.ids})

        if args.adddate is not None:
            cache.set_field('timestamp', {bid:args.adddate for bid in self.ids})

        if args.do_series:
            sval = args.series_start_value if args.do_series_restart else cache.get_next_series_num_for(args.series, current_indices=True)
            cache.set_field('series', {bid:args.series for bid in self.ids})
            if not args.series:
                cache.set_field('series_index', {bid:1.0 for bid in self.ids})
            else:
                def next_series_num(bid, i):
                    if args.do_series_restart:
                        return sval + (i * args.series_increment)
                    next_num = _get_next_series_num_for_list(sorted(sval.itervalues()), unwrap=False)
                    sval[bid] = next_num
                    return next_num

                smap = {bid:next_series_num(bid, i) for i, bid in enumerate(self.ids)}
                if args.do_autonumber:
                    cache.set_field('series_index', smap)
                elif tweaks['series_index_auto_increment'] != 'no_change':
                    cache.set_field('series_index', {bid:1.0 for bid in self.ids})

        if args.comments is not null:
            cache.set_field('comments', {bid:args.comments for bid in self.ids})

        if args.do_remove_conv:
            cache.delete_conversion_options(self.ids)

        if args.clear_languages:
            cache.set_field('languages', {bid:() for bid in self.ids})
        elif args.languages:
            cache.set_field('languages', {bid:args.languages for bid in self.ids})

        if args.remove_all:
            cache.set_field('tags', {bid:() for bid in self.ids})
        if args.add or args.remove:
            self.db.bulk_modify_tags(self.ids, add=args.add, remove=args.remove)

        if self.do_sr:
            for book_id in self.ids:
                self.s_r_func(book_id)
            if self.sr_calls:
                for field, book_id_val_map in self.sr_calls.iteritems():
                    self.refresh_books.update(self.db.new_api.set_field(field, book_id_val_map))

# }}}


class MetadataBulkDialog(QDialog, Ui_MetadataBulkDialog):

    s_r_functions = {''              : lambda x: x,
                            _('Lower Case') : lambda x: icu_lower(x),
                            _('Upper Case') : lambda x: icu_upper(x),
                            _('Title Case') : lambda x: titlecase(x),
                            _('Capitalize') : lambda x: capitalize(x),
                    }

    s_r_match_modes = [_('Character match'),
                            _('Regular Expression'),
                      ]

    s_r_replace_modes = [_('Replace field'),
                            _('Prepend to field'),
                            _('Append to field'),
                        ]

    def __init__(self, window, rows, model, tab, refresh_books):
        QDialog.__init__(self, window)
        self.setupUi(self)
        self.model = model
        self.db = model.db
        self.refresh_book_list.setChecked(gprefs['refresh_book_list_on_bulk_edit'])
        self.refresh_book_list.toggled.connect(self.save_refresh_booklist)
        self.ids = [self.db.id(r) for r in rows]
        self.first_title = self.db.title(self.ids[0], index_is_id=True)
        self.cover_clone.setToolTip(unicode(self.cover_clone.toolTip()) + ' (%s)' % self.first_title)
        self.box_title.setText('<p>' +
                _('Editing meta information for <b>%d books</b>') %
                len(rows))
        self.write_series = False
        self.changed = False
        self.refresh_books = refresh_books
        self.comments = null
        self.comments_button.clicked.connect(self.set_comments)

        all_tags = self.db.all_tags()
        self.tags.update_items_cache(all_tags)
        self.remove_tags.update_items_cache(all_tags)

        self.initialize_combos()

        self.series.currentIndexChanged[int].connect(self.series_changed)
        self.rating.currentIndexChanged.connect(lambda:self.apply_rating.setChecked(True))
        self.series.editTextChanged.connect(self.series_changed)
        self.tag_editor_button.clicked.connect(self.tag_editor)
        self.autonumber_series.stateChanged[int].connect(self.auto_number_changed)
        self.pubdate.setMinimumDateTime(UNDEFINED_QDATETIME)
        self.pubdate_cw = CalendarWidget(self.pubdate)
        self.pubdate.setCalendarWidget(self.pubdate_cw)
        pubdate_format = tweaks['gui_pubdate_display_format']
        if pubdate_format is not None:
            self.pubdate.setDisplayFormat(pubdate_format)
        self.pubdate.setSpecialValueText(_('Undefined'))
        self.clear_pubdate_button.clicked.connect(self.clear_pubdate)
        self.pubdate.dateTimeChanged.connect(self.do_apply_pubdate)
        self.adddate.setDateTime(QDateTime.currentDateTime())
        self.adddate.setMinimumDateTime(UNDEFINED_QDATETIME)
        self.adddate_cw = CalendarWidget(self.adddate)
        self.adddate.setCalendarWidget(self.adddate_cw)
        adddate_format = tweaks['gui_timestamp_display_format']
        if adddate_format is not None:
            self.adddate.setDisplayFormat(adddate_format)
        self.adddate.setSpecialValueText(_('Undefined'))
        self.clear_adddate_button.clicked.connect(self.clear_adddate)
        self.adddate.dateTimeChanged.connect(self.do_apply_adddate)

        if len(self.db.custom_field_keys(include_composites=False)) == 0:
            self.central_widget.removeTab(1)
        else:
            self.create_custom_column_editors()

        self.prepare_search_and_replace()

        self.button_box.clicked.connect(self.button_clicked)
        self.button_box.button(QDialogButtonBox.Apply).setToolTip(_(
            'Immediately make all changes without closing the dialog. '
            'This operation cannot be canceled or undone'))
        self.do_again = False
        self.central_widget.setCurrentIndex(tab)
        geom = gprefs.get('bulk_metadata_window_geometry', None)
        if geom is not None:
            self.restoreGeometry(bytes(geom))
        else:
            self.resize(self.sizeHint())
        ct = gprefs.get('bulk_metadata_window_tab', 0)
        self.central_widget.setCurrentIndex(ct)
        self.languages.init_langs(self.db)
        self.languages.setEditText('')
        self.authors.setFocus(Qt.OtherFocusReason)
        self.generate_cover_settings = None
        self.button_config_cover_gen.setVisible(False)
        self.button_config_cover_gen.clicked.connect(self.customize_cover_generation)
        self.exec_()

    def sizeHint(self):
        desktop = QCoreApplication.instance().desktop()
        geom = desktop.availableGeometry(self)
        nh, nw = max(300, geom.height()-50), max(400, geom.width()-70)
        return QSize(nw, nh)

    def customize_cover_generation(self):
        from calibre.gui2.covers import CoverSettingsDialog
        d = CoverSettingsDialog(parent=self)
        if d.exec_() == d.Accepted:
            self.generate_cover_settings = d.prefs_for_rendering

    def set_comments(self):
        from calibre.gui2.dialogs.comments_dialog import CommentsDialog
        d = CommentsDialog(self, '' if self.comments is null else (self.comments or ''), _('Comments'))
        if d.exec_() == d.Accepted:
            self.comments = d.textbox.html
            b = self.comments_button
            b.setStyleSheet('QPushButton { font-weight: bold }')
            if unicode(b.text())[-1] != '*':
                b.setText(unicode(b.text()) + ' *')

    def save_refresh_booklist(self, *args):
        gprefs['refresh_book_list_on_bulk_edit'] = bool(self.refresh_book_list.isChecked())

    def save_state(self, *args):
        gprefs['bulk_metadata_window_geometry'] = \
            bytearray(self.saveGeometry())
        gprefs['bulk_metadata_window_tab'] = self.central_widget.currentIndex()

    def do_apply_pubdate(self, *args):
        self.apply_pubdate.setChecked(True)

    def clear_pubdate(self, *args):
        self.pubdate.setDateTime(UNDEFINED_QDATETIME)

    def do_apply_adddate(self, *args):
        self.apply_adddate.setChecked(True)

    def clear_adddate(self, *args):
        self.adddate.setDateTime(UNDEFINED_QDATETIME)

    def button_clicked(self, which):
        if which == self.button_box.button(QDialogButtonBox.Apply):
            self.do_again = True
            self.accept()

    # S&R {{{
    def prepare_search_and_replace(self):
        self.search_for.initialize('bulk_edit_search_for')
        self.replace_with.initialize('bulk_edit_replace_with')
        self.s_r_template.initialize('bulk_edit_template')
        self.test_text.initialize('bulk_edit_test_test')
        self.all_fields = ['']
        self.writable_fields = ['']
        fm = self.db.field_metadata
        for f in fm:
            if (f in ['author_sort'] or
                    (fm[f]['datatype'] in ['text', 'series', 'enumeration', 'comments', 'rating'] and
                     fm[f].get('search_terms', None) and
                     f not in ['formats', 'ondevice', 'series_sort']) or
                    (fm[f]['datatype'] in ['int', 'float', 'bool', 'datetime'] and
                     f not in ['id', 'timestamp'])):
                self.all_fields.append(f)
                self.writable_fields.append(f)
            if fm[f]['datatype'] == 'composite':
                self.all_fields.append(f)
        self.all_fields.sort()
        self.all_fields.insert(1, '{template}')
        self.writable_fields.sort()
        self.search_field.setMaxVisibleItems(25)
        self.destination_field.setMaxVisibleItems(25)
        self.testgrid.setColumnStretch(1, 1)
        self.testgrid.setColumnStretch(2, 1)
        offset = 10
        self.s_r_number_of_books = min(10, len(self.ids))
        for i in range(1,self.s_r_number_of_books+1):
            w = QLabel(self.tabWidgetPage3)
            w.setText(_('Book %d:')%i)
            self.testgrid.addWidget(w, i+offset, 0, 1, 1)
            w = QLineEdit(self.tabWidgetPage3)
            w.setReadOnly(True)
            name = 'book_%d_text'%i
            setattr(self, name, w)
            self.book_1_text.setObjectName(name)
            self.testgrid.addWidget(w, i+offset, 1, 1, 1)
            w = QLineEdit(self.tabWidgetPage3)
            w.setReadOnly(True)
            name = 'book_%d_result'%i
            setattr(self, name, w)
            self.book_1_text.setObjectName(name)
            self.testgrid.addWidget(w, i+offset, 2, 1, 1)

        ident_types = sorted(self.db.get_all_identifier_types(), key=sort_key)
        self.s_r_dst_ident.setCompleter(QCompleter(ident_types))
        try:
            self.s_r_dst_ident.setPlaceholderText(_('Enter an identifier type'))
        except:
            pass
        self.s_r_src_ident.addItems(ident_types)

        self.main_heading = _(
                 '<b>You can destroy your library using this feature.</b> '
                 'Changes are permanent. There is no undo function. '
                 'You are strongly encouraged to back up your library '
                 'before proceeding.<p>'
                 'Search and replace in text fields using character matching '
                 'or regular expressions. ')

        self.character_heading = _(
                 'In character mode, the field is searched for the entered '
                 'search text. The text is replaced by the specified replacement '
                 'text everywhere it is found in the specified field. After '
                 'replacement is finished, the text can be changed to '
                 'upper-case, lower-case, or title-case. If the case-sensitive '
                 'check box is checked, the search text must match exactly. If '
                 'it is unchecked, the search text will match both upper- and '
                 'lower-case letters'
                 )

        self.regexp_heading = _(
                 'In regular expression mode, the search text is an '
                 'arbitrary python-compatible regular expression. The '
                 'replacement text can contain backreferences to parenthesized '
                 'expressions in the pattern. The search is not anchored, '
                 'and can match and replace multiple times on the same string. '
                 'The modification functions (lower-case etc) are applied to the '
                 'matched text, not to the field as a whole. '
                 'The destination box specifies the field where the result after '
                 'matching and replacement is to be assigned. You can replace '
                 'the text in the field, or prepend or append the matched text. '
                 'See <a href="https://docs.python.org/library/re.html"> '
                 'this reference</a> for more information on python\'s regular '
                 'expressions, and in particular the \'sub\' function.'
                 )

        self.search_mode.addItems(self.s_r_match_modes)
        self.search_mode.setCurrentIndex(dynamic.get('s_r_search_mode', 0))
        self.replace_mode.addItems(self.s_r_replace_modes)
        self.replace_mode.setCurrentIndex(0)

        self.s_r_search_mode = 0
        self.s_r_error = None
        self.s_r_obj = None

        self.replace_func.addItems(sorted(self.s_r_functions.keys()))
        self.search_mode.currentIndexChanged[int].connect(self.s_r_search_mode_changed)
        self.search_field.currentIndexChanged[int].connect(self.s_r_search_field_changed)
        self.destination_field.currentIndexChanged[int].connect(self.s_r_destination_field_changed)

        self.replace_mode.currentIndexChanged[int].connect(self.s_r_paint_results)
        self.replace_func.currentIndexChanged[str].connect(self.s_r_paint_results)
        self.search_for.editTextChanged[str].connect(self.s_r_paint_results)
        self.replace_with.editTextChanged[str].connect(self.s_r_paint_results)
        self.test_text.editTextChanged[str].connect(self.s_r_paint_results)
        self.comma_separated.stateChanged.connect(self.s_r_paint_results)
        self.case_sensitive.stateChanged.connect(self.s_r_paint_results)
        self.s_r_src_ident.currentIndexChanged[int].connect(self.s_r_identifier_type_changed)
        self.s_r_dst_ident.textChanged.connect(self.s_r_paint_results)
        self.s_r_template.lost_focus.connect(self.s_r_template_changed)
        self.central_widget.setCurrentIndex(0)

        self.search_for.completer().setCaseSensitivity(Qt.CaseSensitive)
        self.replace_with.completer().setCaseSensitivity(Qt.CaseSensitive)
        self.s_r_template.completer().setCaseSensitivity(Qt.CaseSensitive)

        self.s_r_search_mode_changed(self.search_mode.currentIndex())
        self.multiple_separator.setFixedWidth(30)
        self.multiple_separator.setText(' ::: ')
        self.multiple_separator.textChanged.connect(self.s_r_separator_changed)
        self.results_count.valueChanged[int].connect(self.s_r_display_bounds_changed)
        self.starting_from.valueChanged[int].connect(self.s_r_display_bounds_changed)

        self.save_button.clicked.connect(self.s_r_save_query)
        self.remove_button.clicked.connect(self.s_r_remove_query)

        self.queries = JSONConfig("search_replace_queries")
        self.saved_search_name = ''
        self.query_field.addItem("")
        self.query_field_values = sorted([q for q in self.queries], key=sort_key)
        self.query_field.addItems(self.query_field_values)
        self.query_field.currentIndexChanged[str].connect(self.s_r_query_change)
        self.query_field.setCurrentIndex(0)
        self.search_field.setCurrentIndex(0)
        self.s_r_search_field_changed(0)

    def s_r_sf_itemdata(self, idx):
        if idx is None:
            idx = self.search_field.currentIndex()
        return unicode(self.search_field.itemData(idx) or '')

    def s_r_df_itemdata(self, idx):
        if idx is None:
            idx = self.destination_field.currentIndex()
        return unicode(self.destination_field.itemData(idx) or '')

    def s_r_get_field(self, mi, field):
        if field:
            if field == '{template}':
                v = SafeFormat().safe_format(
                    unicode(self.s_r_template.text()), mi, _('S/R TEMPLATE ERROR'), mi)
                return [v]
            fm = self.db.metadata_for_field(field)
            if field == 'sort':
                val = mi.get('title_sort', None)
            elif fm['datatype'] == 'datetime':
                val = mi.format_field(field)[1]
            else:
                val = mi.get(field, None)
            if isinstance(val, (int, float, bool)):
                val = str(val)
            elif fm['is_csp']:
                # convert the csp dict into a list
                id_type = unicode(self.s_r_src_ident.currentText())
                if id_type:
                    val = [val.get(id_type, '')]
                else:
                    val = [u'%s:%s'%(t[0], t[1]) for t in val.iteritems()]
            if val is None:
                val = [] if fm['is_multiple'] else ['']
            elif not fm['is_multiple']:
                val = [val]
            elif fm['datatype'] == 'composite':
                val = [v2.strip() for v2 in val.split(fm['is_multiple']['ui_to_list'])]
            elif field == 'authors':
                val = [v2.replace('|', ',') for v2 in val]
        else:
            val = []
        if not val:
            val = ['']
        return val

    def s_r_display_bounds_changed(self, i):
        self.s_r_search_field_changed(self.search_field.currentIndex())

    def s_r_template_changed(self):
        self.s_r_search_field_changed(self.search_field.currentIndex())

    def s_r_identifier_type_changed(self, idx):
        self.s_r_search_field_changed(self.search_field.currentIndex())
        self.s_r_paint_results(idx)

    def s_r_search_field_changed(self, idx):
        self.s_r_template.setVisible(False)
        self.template_label.setVisible(False)
        self.s_r_src_ident_label.setVisible(False)
        self.s_r_src_ident.setVisible(False)
        if idx == 1:  # Template
            self.s_r_template.setVisible(True)
            self.template_label.setVisible(True)
        elif self.s_r_sf_itemdata(idx) == 'identifiers':
            self.s_r_src_ident_label.setVisible(True)
            self.s_r_src_ident.setVisible(True)

        for i in range(0, self.s_r_number_of_books):
            w = getattr(self, 'book_%d_text'%(i+1))
            mi = self.db.get_metadata(self.ids[i], index_is_id=True)
            src = self.s_r_sf_itemdata(idx)
            t = self.s_r_get_field(mi, src)
            if len(t) > 1:
                t = t[self.starting_from.value()-1:
                      self.starting_from.value()-1 + self.results_count.value()]
            w.setText(unicode(self.multiple_separator.text()).join(t))

        if self.search_mode.currentIndex() == 0:
            self.destination_field.setCurrentIndex(idx)
        else:
            self.s_r_destination_field_changed(self.destination_field.currentIndex())
            self.s_r_paint_results(None)

    def s_r_destination_field_changed(self, idx):
        self.s_r_dst_ident_label.setVisible(False)
        self.s_r_dst_ident.setVisible(False)
        txt = self.s_r_df_itemdata(idx)
        if not txt:
            txt = self.s_r_sf_itemdata(None)
        if txt and txt in self.writable_fields:
            if txt == 'identifiers':
                self.s_r_dst_ident_label.setVisible(True)
                self.s_r_dst_ident.setVisible(True)
            self.destination_field_fm = self.db.metadata_for_field(txt)
        self.s_r_paint_results(None)

    def s_r_search_mode_changed(self, val):
        self.search_field.clear()
        self.destination_field.clear()
        if val == 0:
            for f in self.writable_fields:
                self.search_field.addItem(f if f != 'sort' else 'title_sort', f)
                self.destination_field.addItem(f if f != 'sort' else 'title_sort', f)
            self.destination_field.setCurrentIndex(0)
            self.destination_field.setVisible(False)
            self.destination_field_label.setVisible(False)
            self.replace_mode.setCurrentIndex(0)
            self.replace_mode.setVisible(False)
            self.replace_mode_label.setVisible(False)
            self.comma_separated.setVisible(False)
            self.s_r_heading.setText('<p>'+self.main_heading + self.character_heading)
        else:
            self.search_field.blockSignals(True)
            self.destination_field.blockSignals(True)
            for f in self.all_fields:
                self.search_field.addItem(f if f != 'sort' else 'title_sort', f)
            for f in self.writable_fields:
                self.destination_field.addItem(f if f != 'sort' else 'title_sort', f)
            self.search_field.blockSignals(False)
            self.destination_field.blockSignals(False)
            self.destination_field.setVisible(True)
            self.destination_field_label.setVisible(True)
            self.replace_mode.setVisible(True)
            self.replace_mode_label.setVisible(True)
            self.comma_separated.setVisible(True)
            self.s_r_heading.setText('<p>'+self.main_heading + self.regexp_heading)
        self.s_r_paint_results(None)

    def s_r_separator_changed(self, txt):
        self.s_r_search_field_changed(self.search_field.currentIndex())

    def s_r_set_colors(self):
        if self.s_r_error is not None:
            col = 'rgb(255, 0, 0, 20%)'
            self.test_result.setText(self.s_r_error.message)
        else:
            col = 'rgb(0, 255, 0, 20%)'
        self.test_result.setStyleSheet('QLineEdit { color: black; '
                                       'background-color: %s; }'%col)
        for i in range(0,self.s_r_number_of_books):
            getattr(self, 'book_%d_result'%(i+1)).setText('')

    def s_r_func(self, match):
        rfunc = self.s_r_functions[unicode(self.replace_func.currentText())]
        rtext = unicode(self.replace_with.text())
        rtext = match.expand(rtext)
        return rfunc(rtext)

    def s_r_do_regexp(self, mi):
        src_field = self.s_r_sf_itemdata(None)
        src = self.s_r_get_field(mi, src_field)
        result = []
        rfunc = self.s_r_functions[unicode(self.replace_func.currentText())]
        for s in src:
            t = self.s_r_obj.sub(self.s_r_func, s)
            if self.search_mode.currentIndex() == 0:
                t = rfunc(t)
            result.append(t)
        return result

    def s_r_do_destination(self, mi, val):
        src = self.s_r_sf_itemdata(None)
        if src == '':
            return ''
        dest = self.s_r_df_itemdata(None)
        if dest == '':
            if (src == '{template}' or
                        self.db.metadata_for_field(src)['datatype'] == 'composite'):
                raise Exception(_('You must specify a destination when source is '
                                  'a composite field or a template'))
            dest = src

        if self.destination_field_fm['datatype'] == 'rating' and val[0]:
            ok = True
            try:
                v = int(val[0])
                if v < 0 or v > 10:
                    ok = False
            except:
                ok = False
            if not ok:
                raise Exception(_('The replacement value for a rating column must '
                                  'be empty or an integer between 0 and 10'))
        dest_mode = self.replace_mode.currentIndex()

        if self.destination_field_fm['is_csp']:
            dest_ident = unicode(self.s_r_dst_ident.text())
            if not dest_ident or (src == 'identifiers' and dest_ident == '*'):
                raise Exception(_('You must specify a destination identifier type'))

        if self.destination_field_fm['is_multiple']:
            if self.comma_separated.isChecked():
                splitter = self.destination_field_fm['is_multiple']['ui_to_list']
                res = []
                for v in val:
                    res.extend([x.strip() for x in v.split(splitter) if x.strip()])
                val = res
            else:
                val = [v.replace(',', '') for v in val]

        if dest_mode != 0:
            dest_val = mi.get(dest, '')
            if self.db.metadata_for_field(dest)['is_csp']:
                dst_id_type = unicode(self.s_r_dst_ident.text())
                if dst_id_type:
                    dest_val = [dest_val.get(dst_id_type, '')]
                else:
                    # convert the csp dict into a list
                    dest_val = [u'%s:%s'%(t[0], t[1]) for t in dest_val.iteritems()]
            if dest_val is None:
                dest_val = []
            elif not isinstance(dest_val, list):
                dest_val = [dest_val]
        else:
            dest_val = []

        if dest_mode == 1:
            val.extend(dest_val)
        elif dest_mode == 2:
            val[0:0] = dest_val
        return val

    def s_r_replace_mode_separator(self):
        if self.comma_separated.isChecked():
            return ','
        return ''

    def s_r_paint_results(self, txt):
        self.s_r_error = None
        self.s_r_set_colors()

        if self.case_sensitive.isChecked():
            flags = 0
        else:
            flags = re.I

        flags |= re.UNICODE

        try:
            stext = unicode(self.search_for.text())
            if not stext:
                raise Exception(_('You must specify a search expression in the "Search for" field'))
            if self.search_mode.currentIndex() == 0:
                self.s_r_obj = re.compile(re.escape(stext), flags)
            else:
                self.s_r_obj = re.compile(stext, flags)
        except Exception as e:
            self.s_r_obj = None
            self.s_r_error = e
            self.s_r_set_colors()
            return

        try:
            self.test_result.setText(self.s_r_obj.sub(self.s_r_func,
                                     unicode(self.test_text.text())))
        except Exception as e:
            self.s_r_error = e
            self.s_r_set_colors()
            return

        for i in range(0,self.s_r_number_of_books):
            mi = self.db.get_metadata(self.ids[i], index_is_id=True)
            wr = getattr(self, 'book_%d_result'%(i+1))
            try:
                result = self.s_r_do_regexp(mi)
                t = self.s_r_do_destination(mi, result)
                if len(t) > 1 and self.destination_field_fm['is_multiple']:
                    t = t[self.starting_from.value()-1:
                          self.starting_from.value()-1 + self.results_count.value()]
                    t = unicode(self.multiple_separator.text()).join(t)
                else:
                    t = self.s_r_replace_mode_separator().join(t)
                wr.setText(t)
            except Exception as e:
                self.s_r_error = e
                self.s_r_set_colors()
                break

    def do_search_replace(self, book_id):
        source = self.s_r_sf_itemdata(None)
        if not source or not self.s_r_obj:
            return
        dest = self.s_r_df_itemdata(None)
        if not dest:
            dest = source
        dfm = self.db.field_metadata[dest]
        mi = self.db.new_api.get_proxy_metadata(book_id)
        val = self.s_r_do_regexp(mi)
        val = self.s_r_do_destination(mi, val)
        if dfm['is_multiple']:
            if dfm['is_csp']:
                # convert the colon-separated pair strings back into a dict,
                # which is what set_identifiers wants
                dst_id_type = unicode(self.s_r_dst_ident.text())
                if dst_id_type and dst_id_type != '*':
                    v = ''.join(val)
                    ids = mi.get(dest)
                    ids[dst_id_type] = v
                    val = ids
                else:
                    try:
                        val = dict([(t.split(':')) for t in val])
                    except:
                        raise Exception(_('Invalid identifier string. It must be a '
                                          'comma-separated list of pairs of '
                                          'strings separated by a colon'))
        else:
            val = self.s_r_replace_mode_separator().join(val)
            if dest == 'title' and len(val) == 0:
                val = _('Unknown')

        if not val and dfm['datatype'] == 'datetime':
            val = None
        if dfm['datatype'] == 'rating':
            if (not val or int(val) == 0):
                val = None
            if dest == 'rating' and val:
                val = (int(val) // 2) * 2
        self.set_field_calls[dest][book_id] = val
    # }}}

    def create_custom_column_editors(self):
        w = self.central_widget.widget(1)
        layout = QGridLayout()
        self.custom_column_widgets, self.__cc_spacers = \
            populate_metadata_page(layout, self.db, self.ids, parent=w,
                                   two_column=False, bulk=True)
        w.setLayout(layout)
        self.__custom_col_layouts = [layout]
        ans = self.custom_column_widgets
        for i in range(len(ans)-1):
            w.setTabOrder(ans[i].widgets[-1], ans[i+1].widgets[1])
            for c in range(2, len(ans[i].widgets), 2):
                w.setTabOrder(ans[i].widgets[c-1], ans[i].widgets[c+1])

    def initialize_combos(self):
        self.initalize_authors()
        self.initialize_series()
        self.initialize_publisher()
        for x in ('authors', 'publisher', 'series'):
            x = getattr(self, x)
            x.setSizeAdjustPolicy(x.AdjustToMinimumContentsLengthWithIcon)
            x.setMinimumContentsLength(25)

    def initalize_authors(self):
        all_authors = self.db.all_authors()
        all_authors.sort(key=lambda x : sort_key(x[1]))

        self.authors.set_separator('&')
        self.authors.set_space_before_sep(True)
        self.authors.set_add_separator(tweaks['authors_completer_append_separator'])
        self.authors.update_items_cache(self.db.all_author_names())
        self.authors.show_initial_value('')

    def initialize_series(self):
        all_series = self.db.all_series()
        all_series.sort(key=lambda x : sort_key(x[1]))
        self.series.set_separator(None)
        self.series.update_items_cache([x[1] for x in all_series])
        self.series.show_initial_value('')

    def initialize_publisher(self):
        all_publishers = self.db.all_publishers()
        all_publishers.sort(key=lambda x : sort_key(x[1]))
        self.publisher.set_separator(None)
        self.publisher.update_items_cache([x[1] for x in all_publishers])
        self.publisher.show_initial_value('')

    def tag_editor(self, *args):
        d = TagEditor(self, self.db, None)
        d.exec_()
        if d.result() == QDialog.Accepted:
            tag_string = ', '.join(d.tags)
            self.tags.setText(tag_string)
            self.tags.update_items_cache(self.db.all_tags())
            self.remove_tags.update_items_cache(self.db.all_tags())

    def auto_number_changed(self, state):
        self.series_start_number.setEnabled(bool(state))
        self.series_increment.setEnabled(bool(state))
        if state:
            self.series_numbering_restarts.setEnabled(True)
        else:
            self.series_numbering_restarts.setEnabled(False)
            self.series_numbering_restarts.setChecked(False)
            self.series_start_number.setValue(1.0)
            self.series_increment.setValue(1.0)

    def reject(self):
        self.save_state()
        QDialog.reject(self)

    def accept(self):
        self.save_state()
        if len(self.ids) < 1:
            return QDialog.accept(self)
        try:
            source = self.s_r_sf_itemdata(None)
        except:
            source = ''
        do_sr = source and self.s_r_obj

        if self.s_r_error is not None and do_sr:
            error_dialog(self, _('Search/replace invalid'),
                    _('Search/replace is invalid: %s')%self.s_r_error.message,
                    show=True)
            return False
        self.changed = bool(self.ids)
        # Cache values from GUI so that Qt widgets are not used in
        # non GUI thread
        for w in getattr(self, 'custom_column_widgets', []):
            w.gui_val

        remove_all = self.remove_all_tags.isChecked()
        remove = []
        if not remove_all:
            remove = unicode(self.remove_tags.text()).strip().split(',')
        add = unicode(self.tags.text()).strip().split(',')
        au = unicode(self.authors.text())
        aus = unicode(self.author_sort.text())
        do_aus = self.author_sort.isEnabled()
        rating = self.rating.rating_value
        if not self.apply_rating.isChecked():
            rating = -1
        pub = unicode(self.publisher.text())
        do_series = self.write_series
        clear_series = self.clear_series.isChecked()
        clear_pub = self.clear_pub.isChecked()
        series = unicode(self.series.currentText()).strip()
        do_autonumber = self.autonumber_series.isChecked()
        do_series_restart = self.series_numbering_restarts.isChecked()
        series_start_value = self.series_start_number.value()
        series_increment = self.series_increment.value()
        do_swap_ta = self.swap_title_and_author.isChecked()
        do_remove_conv = self.remove_conversion_settings.isChecked()
        do_auto_author = self.auto_author_sort.isChecked()
        do_title_case = self.change_title_to_title_case.isChecked()
        do_title_sort = self.update_title_sort.isChecked()
        clear_languages = self.clear_languages.isChecked()
        restore_original = self.restore_original.isChecked()
        languages = self.languages.lang_codes
        pubdate = adddate = None
        if self.apply_pubdate.isChecked():
            pubdate = qt_to_dt(self.pubdate.dateTime())
        if self.apply_adddate.isChecked():
            adddate = qt_to_dt(self.adddate.dateTime())

        cover_action = None
        if self.cover_remove.isChecked():
            cover_action = 'remove'
        elif self.cover_generate.isChecked():
            cover_action = 'generate'
        elif self.cover_from_fmt.isChecked():
            cover_action = 'fromfmt'
        elif self.cover_trim.isChecked():
            cover_action = 'trim'
        elif self.cover_clone.isChecked():
            cover_action = 'clone'

        args = Settings(remove_all, remove, add, au, aus, do_aus, rating, pub, do_series,
                do_autonumber, do_swap_ta,
                do_remove_conv, do_auto_author, series, do_series_restart,
                series_start_value, series_increment, do_title_case, cover_action, clear_series, clear_pub,
                pubdate, adddate, do_title_sort, languages, clear_languages,
                restore_original, self.comments, self.generate_cover_settings)

        self.set_field_calls = defaultdict(dict)
        bb = MyBlockingBusy(args, self.ids, self.db, self.refresh_books,
            getattr(self, 'custom_column_widgets', []),
            self.do_search_replace, do_sr, self.set_field_calls, parent=self)

        # The metadata backup thread causes database commits
        # which can slow down bulk editing of large numbers of books
        self.model.stop_metadata_backup()
        try:
            bb.exec_()
        finally:
            self.model.start_metadata_backup()

        bb.thread = bb.db = bb.cc_widgets = None

        if bb.error is not None:
            return error_dialog(self, _('Failed'),
                    bb.error[0], det_msg=bb.error[1],
                    show=True)

        dynamic['s_r_search_mode'] = self.search_mode.currentIndex()
        self.db.clean()
        return QDialog.accept(self)

    def series_changed(self, *args):
        self.write_series = bool(unicode(self.series.currentText()).strip())
        self.autonumber_series.setEnabled(True)

    def s_r_remove_query(self, *args):
        if self.query_field.currentIndex() == 0:
            return

        if not question_dialog(self, _("Delete saved search/replace"),
                _("The selected saved search/replace will be deleted. "
                    "Are you sure?")):
            return

        item_id = self.query_field.currentIndex()
        item_name = unicode(self.query_field.currentText())

        self.query_field.blockSignals(True)
        self.query_field.removeItem(item_id)
        self.query_field.blockSignals(False)
        self.query_field.setCurrentIndex(0)

        if item_name in self.queries.keys():
            del(self.queries[item_name])
            self.queries.commit()

    def s_r_save_query(self, *args):
        names = ['']
        names.extend(self.query_field_values)
        try:
            dex = names.index(self.saved_search_name)
        except:
            dex = 0
        name = ''
        while not name:
            name, ok =  QInputDialog.getItem(self, _('Save search/replace'),
                    _('Search/replace name:'), names, dex, True)
            if not ok:
                return
            if not name:
                error_dialog(self, _("Save search/replace"),
                        _("You must provide a name."), show=True)
        new = True
        name = unicode(name)
        if name in self.queries.keys():
            if not question_dialog(self, _("Save search/replace"),
                    _("That saved search/replace already exists and will be overwritten. "
                        "Are you sure?")):
                return
            new = False

        query = {}
        query['name'] = name
        query['search_field'] = unicode(self.search_field.currentText())
        query['search_mode'] = unicode(self.search_mode.currentText())
        query['s_r_template'] = unicode(self.s_r_template.text())
        query['s_r_src_ident'] = unicode(self.s_r_src_ident.currentText())
        query['search_for'] = unicode(self.search_for.text())
        query['case_sensitive'] = self.case_sensitive.isChecked()
        query['replace_with'] = unicode(self.replace_with.text())
        query['replace_func'] = unicode(self.replace_func.currentText())
        query['destination_field'] = unicode(self.destination_field.currentText())
        query['s_r_dst_ident'] = unicode(self.s_r_dst_ident.text())
        query['replace_mode'] = unicode(self.replace_mode.currentText())
        query['comma_separated'] = self.comma_separated.isChecked()
        query['results_count'] = self.results_count.value()
        query['starting_from'] = self.starting_from.value()
        query['multiple_separator'] = unicode(self.multiple_separator.text())

        self.queries[name] = query
        self.queries.commit()

        if new:
            self.query_field.blockSignals(True)
            self.query_field.clear()
            self.query_field.addItem('')
            self.query_field_values = sorted([q for q in self.queries], key=sort_key)
            self.query_field.addItems(self.query_field_values)
            self.query_field.blockSignals(False)
        self.query_field.setCurrentIndex(self.query_field.findText(name))

    def s_r_query_change(self, item_name):
        if not item_name:
            self.s_r_reset_query_fields()
            self.saved_search_name = ''
            return
        item = self.queries.get(unicode(item_name), None)
        if item is None:
            self.s_r_reset_query_fields()
            return
        self.saved_search_name = item_name

        def set_text(attr, key):
            try:
                attr.setText(item[key])
            except:
                pass

        def set_checked(attr, key):
            try:
                attr.setChecked(item[key])
            except:
                attr.setChecked(False)

        def set_value(attr, key):
            try:
                attr.setValue(int(item[key]))
            except:
                attr.setValue(0)

        def set_index(attr, key):
            try:
                attr.setCurrentIndex(attr.findText(item[key]))
            except:
                attr.setCurrentIndex(0)

        set_index(self.search_mode, 'search_mode')
        set_index(self.search_field, 'search_field')
        set_text(self.s_r_template, 's_r_template')

        self.s_r_template_changed()  # simulate gain/loss of focus

        set_index(self.s_r_src_ident, 's_r_src_ident')
        set_text(self.s_r_dst_ident, 's_r_dst_ident')
        set_text(self.search_for, 'search_for')
        set_checked(self.case_sensitive, 'case_sensitive')
        set_text(self.replace_with, 'replace_with')
        set_index(self.replace_func, 'replace_func')
        set_index(self.destination_field, 'destination_field')
        set_index(self.replace_mode, 'replace_mode')
        set_checked(self.comma_separated, 'comma_separated')
        set_value(self.results_count, 'results_count')
        set_value(self.starting_from, 'starting_from')
        set_text(self.multiple_separator, 'multiple_separator')

    def s_r_reset_query_fields(self):
        # Don't reset the search mode. The user will probably want to use it
        # as it was
        self.search_field.setCurrentIndex(0)
        self.s_r_src_ident.setCurrentIndex(0)
        self.s_r_template.setText("")
        self.search_for.setText("")
        self.case_sensitive.setChecked(False)
        self.replace_with.setText("")
        self.replace_func.setCurrentIndex(0)
        self.destination_field.setCurrentIndex(0)
        self.s_r_dst_ident.setText('')
        self.replace_mode.setCurrentIndex(0)
        self.comma_separated.setChecked(True)
        self.results_count.setValue(999)
        self.starting_from.setValue(1)
        self.multiple_separator.setText(" ::: ")
