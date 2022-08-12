#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import math
import unicodedata
from functools import partial
from qt.core import (
    QAction, QApplication, QColor, QIcon, QImage, QInputDialog, QMainWindow, QMenu,
    QPainter, QPixmap, QSize, Qt, QTextCursor, QToolButton, pyqtSignal,
    qDrawShadeRect
)

from calibre import prints
from calibre.constants import DEBUG
from calibre.ebooks.chardet import replace_encoding_declarations
from calibre.gui2 import error_dialog, open_url
from calibre.gui2.tweak_book import (
    actions, current_container, dictionaries, editor_name, editor_toolbar_actions,
    editors, tprefs, update_mark_text_action
)
from calibre.gui2.tweak_book.editor import (
    CLASS_ATTRIBUTE_PROPERTY, CSS_PROPERTY, LINK_PROPERTY, SPELL_PROPERTY,
    TAG_NAME_PROPERTY
)
from calibre.gui2.tweak_book.editor.help import help_url
from calibre.gui2.tweak_book.editor.text import TextEdit
from calibre.utils.icu import utf16_length
from polyglot.builtins import itervalues, string_or_bytes


def create_icon(text, palette=None, sz=None, divider=2, fill='white'):
    if isinstance(fill, string_or_bytes):
        fill = QColor(fill)
    sz = sz or int(math.ceil(tprefs['toolbar_icon_size'] * QApplication.instance().devicePixelRatio()))
    if palette is None:
        palette = QApplication.palette()
    img = QImage(sz, sz, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHints(QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.Antialiasing)
    if fill is not None:
        qDrawShadeRect(p, img.rect(), palette, fill=fill, lineWidth=1, midLineWidth=1)
    f = p.font()
    f.setFamily('Liberation Sans'), f.setPixelSize(int(sz // divider)), f.setBold(True)
    p.setFont(f), p.setPen(QColor('#2271d5'))
    p.drawText(img.rect().adjusted(2, 2, -2, -2), Qt.AlignmentFlag.AlignCenter, text)
    p.end()
    return QIcon(QPixmap.fromImage(img))


def register_text_editor_actions(_reg, palette):
    def reg(*args, **kw):
        ac = _reg(*args)
        for s in kw.get('syntaxes', ('format',)):
            editor_toolbar_actions[s][args[3]] = ac
        return ac

    ac = reg('format-text-bold.png', _('&Bold'), ('format_text', 'bold'), 'format-text-bold', 'Ctrl+B', _('Make the selected text bold'))
    ac.setToolTip(_('<h3>Bold</h3>Make the selected text bold'))
    ac = reg('format-text-italic.png', _('&Italic'), ('format_text', 'italic'), 'format-text-italic', 'Ctrl+I', _('Make the selected text italic'))
    ac.setToolTip(_('<h3>Italic</h3>Make the selected text italic'))
    ac = reg('format-text-underline.png', _('&Underline'), ('format_text', 'underline'), 'format-text-underline', (), _('Underline the selected text'))
    ac.setToolTip(_('<h3>Underline</h3>Underline the selected text'))
    ac = reg('format-text-strikethrough.png', _('&Strikethrough'), ('format_text', 'strikethrough'),
             'format-text-strikethrough', (), _('Draw a line through the selected text'))
    ac.setToolTip(_('<h3>Strikethrough</h3>Draw a line through the selected text'))
    ac = reg('format-text-superscript.png', _('&Superscript'), ('format_text', 'superscript'),
             'format-text-superscript', (), _('Make the selected text a superscript'))
    ac.setToolTip(_('<h3>Superscript</h3>Set the selected text slightly smaller and above the normal line'))
    ac = reg('format-text-subscript.png', _('&Subscript'), ('format_text', 'subscript'),
             'format-text-subscript', (), _('Make the selected text a subscript'))
    ac.setToolTip(_('<h3>Subscript</h3>Set the selected text slightly smaller and below the normal line'))
    ac = reg('format-text-color.png', _('&Color'), ('format_text', 'color'), 'format-text-color', (), _('Change text color'))
    ac.setToolTip(_('<h3>Color</h3>Change the color of the selected text'))
    ac = reg('format-fill-color.png', _('&Background color'), ('format_text', 'background-color'),
             'format-text-background-color', (), _('Change background color of text'))
    ac.setToolTip(_('<h3>Background color</h3>Change the background color of the selected text'))
    ac = reg('format-justify-left.png', _('Align &left'), ('format_text', 'justify_left'), 'format-text-justify-left', (), _('Align left'))
    ac.setToolTip(_('<h3>Align left</h3>Align the paragraph to the left'))
    ac = reg('format-justify-center.png', _('&Center'), ('format_text', 'justify_center'), 'format-text-justify-center', (), _('Center'))
    ac.setToolTip(_('<h3>Center</h3>Center the paragraph'))
    ac = reg('format-justify-right.png', _('Align &right'), ('format_text', 'justify_right'), 'format-text-justify-right', (), _('Align right'))
    ac.setToolTip(_('<h3>Align right</h3>Align the paragraph to the right'))
    ac = reg('format-justify-fill.png', _('&Justify'), ('format_text', 'justify_justify'), 'format-text-justify-fill', (), _('Justify'))
    ac.setToolTip(_('<h3>Justify</h3>Align the paragraph to both the left and right margins'))

    ac = reg('sort.png', _('&Sort style rules'), ('sort_css',), 'editor-sort-css', (),
             _('Sort the style rules'), syntaxes=('css',))
    ac = reg('view-image.png', _('&Insert image'), ('insert_resource', 'image'), 'insert-image', (),
             _('Insert an image into the text'), syntaxes=('html', 'css'))
    ac.setToolTip(_('<h3>Insert image</h3>Insert an image into the text'))

    ac = reg('insert-link.png', _('Insert &hyperlink'), ('insert_hyperlink',), 'insert-hyperlink', (), _('Insert hyperlink'), syntaxes=('html',))
    ac.setToolTip(_('<h3>Insert hyperlink</h3>Insert a hyperlink into the text'))

    ac = reg(create_icon('/*', divider=1, fill=None), _('Smart &comment'), ('smart_comment',), 'editor-smart-comment', ('Ctrl+`',), _(
        'Smart comment (toggle block comments)'), syntaxes=())
    ac.setToolTip(_('<h3>Smart comment</h3>Comment or uncomment text<br><br>'
                    'If the cursor is inside an existing block comment, uncomment it, otherwise comment out the selected text.'))

    for i, name in enumerate(('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p')):
        text = ('&' + name) if name == 'p' else (name[0] + '&' + name[1])
        desc = _('Convert the paragraph to &lt;%s&gt;') % name
        ac = reg(create_icon(name), text, ('rename_block_tag', name), 'rename-block-tag-' + name, 'Ctrl+%d' % (i + 1), desc, syntaxes=())
        ac.setToolTip(desc)

    for transform, text in [
            ('upper', _('&Upper case')), ('lower', _('&Lower case')), ('swap', _('&Swap case')),
            ('title', _('&Title case')), ('capitalize', _('&Capitalize'))]:
        desc = _('Change the case of the selected text: %s') % text
        ac = reg(None, text, ('change_case', transform), 'transform-case-' + transform, (), desc, syntaxes=())
        ac.setToolTip(desc)

    ac = reg('code.png', _('Insert &tag'), ('insert_tag',), 'insert-tag', ('Ctrl+<'), _('Insert tag'), syntaxes=('html', 'xml'))
    ac.setToolTip(_('<h3>Insert tag</h3>Insert a tag, if some text is selected the tag will be inserted around the selected text'))

    ac = reg('trash.png', _('Remove &tag'), ('remove_tag',), 'remove-tag', ('Ctrl+>'), _('Remove tag'), syntaxes=('html', 'xml'))
    ac.setToolTip(_('<h3>Remove tag</h3>Remove the currently highlighted tag'))

    ac = reg('split.png', _('&Split tag'), ('split_tag',), 'split-tag', ('Ctrl+Alt+>'), _('Split current tag'), syntaxes=('html', 'xml'))
    ac.setToolTip(_('<h3>Split tag</h3>Split the current tag at the cursor position'))

    editor_toolbar_actions['html']['fix-html-current'] = actions['fix-html-current']
    for s in ('xml', 'html', 'css'):
        editor_toolbar_actions[s]['pretty-current'] = actions['pretty-current']
    editor_toolbar_actions['html']['change-paragraph'] = actions['change-paragraph'] = QAction(
        QIcon.ic('format-text-heading.png'), _('Change paragraph to heading'), ac.parent())


class Editor(QMainWindow):

    has_line_numbers = True

    modification_state_changed = pyqtSignal(object)
    undo_redo_state_changed = pyqtSignal(object, object)
    copy_available_state_changed = pyqtSignal(object)
    data_changed = pyqtSignal(object)
    cursor_position_changed = pyqtSignal()
    word_ignored = pyqtSignal(object, object)
    link_clicked = pyqtSignal(object)
    class_clicked = pyqtSignal(object)
    rename_class = pyqtSignal(object)
    smart_highlighting_updated = pyqtSignal()

    def __init__(self, syntax, parent=None):
        QMainWindow.__init__(self, parent)
        if parent is None:
            self.setWindowFlags(Qt.WindowType.Widget)
        self.is_synced_to_container = False
        self.syntax = syntax
        self.editor = TextEdit(self)
        self.editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self.show_context_menu)
        self.setCentralWidget(self.editor)
        self.create_toolbars()
        self.undo_available = False
        self.redo_available = False
        self.copy_available = self.cut_available = False
        self.editor.modificationChanged.connect(self._modification_state_changed)
        self.editor.undoAvailable.connect(self._undo_available)
        self.editor.redoAvailable.connect(self._redo_available)
        self.editor.textChanged.connect(self._data_changed)
        self.editor.copyAvailable.connect(self._copy_available)
        self.editor.cursorPositionChanged.connect(self._cursor_position_changed)
        self.editor.link_clicked.connect(self.link_clicked)
        self.editor.class_clicked.connect(self.class_clicked)
        self.editor.smart_highlighting_updated.connect(self.smart_highlighting_updated)

    @property
    def current_line(self):
        return self.editor.textCursor().blockNumber()

    @current_line.setter
    def current_line(self, val):
        self.editor.go_to_line(val)

    @property
    def current_editing_state(self):
        c = self.editor.textCursor()
        return {'cursor':(c.anchor(), c.position())}

    @current_editing_state.setter
    def current_editing_state(self, val):
        anchor, position = val.get('cursor', (None, None))
        if anchor is not None and position is not None:
            c = self.editor.textCursor()
            c.setPosition(anchor), c.setPosition(position, QTextCursor.MoveMode.KeepAnchor)
            self.editor.setTextCursor(c)

    def current_tag(self, for_position_sync=True):
        return self.editor.current_tag(for_position_sync=for_position_sync)

    @property
    def highlighter(self):
        return self.editor.highlighter

    @property
    def number_of_lines(self):
        return self.editor.blockCount()

    @property
    def data(self):
        ans = self.get_raw_data()
        ans, changed = replace_encoding_declarations(ans, enc='utf-8', limit=4*1024)
        if changed:
            self.data = ans
        return ans.encode('utf-8')

    @data.setter
    def data(self, val):
        self.editor.load_text(val, syntax=self.syntax, doc_name=editor_name(self))

    def init_from_template(self, template):
        self.editor.load_text(template, syntax=self.syntax, process_template=True, doc_name=editor_name(self))

    def change_document_name(self, newname):
        self.editor.change_document_name(newname)
        self.editor.completion_doc_name = newname

    def get_raw_data(self):
        # The EPUB spec requires NFC normalization, see section 1.3.6 of
        # http://www.idpf.org/epub/20/spec/OPS_2.0.1_draft.htm
        return unicodedata.normalize('NFC', str(self.editor.toPlainText()).rstrip('\0'))

    def replace_data(self, raw, only_if_different=True):
        if isinstance(raw, bytes):
            raw = raw.decode('utf-8')
        current = self.get_raw_data() if only_if_different else False
        if current != raw:
            self.editor.replace_text(raw)

    def apply_settings(self, prefs=None, dictionaries_changed=False):
        self.editor.apply_settings(prefs=None, dictionaries_changed=dictionaries_changed)

    def set_focus(self):
        self.editor.setFocus(Qt.FocusReason.OtherFocusReason)

    def action_triggered(self, action):
        action, args = action[0], action[1:]
        func = getattr(self.editor, action)
        func(*args)

    def insert_image(self, href, fullpage=False, preserve_aspect_ratio=False, width=-1, height=-1):
        self.editor.insert_image(href, fullpage=fullpage, preserve_aspect_ratio=preserve_aspect_ratio, width=width, height=height)

    def insert_hyperlink(self, href, text, template=None):
        self.editor.insert_hyperlink(href, text, template=template)

    def _build_insert_tag_button_menu(self):
        m = self.insert_tag_menu
        m.clear()
        names = tprefs['insert_tag_mru']
        for name in names:
            m.addAction(name, partial(self.insert_tag, name))
        m.addSeparator()
        m.addAction(_('Add a tag to this menu'), self.add_insert_tag)
        if names:
            m = m.addMenu(_('Remove from this menu'))
            for name in names:
                m.addAction(name, partial(self.remove_insert_tag, name))

    def insert_tag(self, name):
        self.editor.insert_tag(name)
        mru = tprefs['insert_tag_mru']
        try:
            mru.remove(name)
        except ValueError:
            pass
        mru.insert(0, name)
        tprefs['insert_tag_mru'] = mru
        self._build_insert_tag_button_menu()

    def add_insert_tag(self):
        name, ok = QInputDialog.getText(self, _('Name of tag to add'), _(
            'Enter the name of the tag'))
        if ok:
            mru = tprefs['insert_tag_mru']
            mru.insert(0, name)
            tprefs['insert_tag_mru'] = mru
            self._build_insert_tag_button_menu()

    def remove_insert_tag(self, name):
        mru = tprefs['insert_tag_mru']
        try:
            mru.remove(name)
        except ValueError:
            pass
        tprefs['insert_tag_mru'] = mru
        self._build_insert_tag_button_menu()

    def set_request_completion(self, callback=None, doc_name=None):
        self.editor.request_completion = callback
        self.editor.completion_doc_name = doc_name

    def handle_completion_result(self, result):
        return self.editor.handle_completion_result(result)

    def undo(self):
        self.editor.undo()

    def redo(self):
        self.editor.redo()

    @property
    def selected_text(self):
        return self.editor.selected_text

    def get_smart_selection(self, update=True):
        return self.editor.smarts.get_smart_selection(self.editor, update=update)

    # Search and replace {{{
    def mark_selected_text(self):
        self.editor.mark_selected_text()

    def find(self, *args, **kwargs):
        return self.editor.find(*args, **kwargs)

    def find_text(self, *args, **kwargs):
        return self.editor.find_text(*args, **kwargs)

    def find_spell_word(self, *args, **kwargs):
        return self.editor.find_spell_word(*args, **kwargs)

    def replace(self, *args, **kwargs):
        return self.editor.replace(*args, **kwargs)

    def all_in_marked(self, *args, **kwargs):
        return self.editor.all_in_marked(*args, **kwargs)

    def go_to_anchor(self, *args, **kwargs):
        return self.editor.go_to_anchor(*args, **kwargs)
    # }}}

    @property
    def has_marked_text(self):
        return self.editor.current_search_mark is not None

    @property
    def is_modified(self):
        return self.editor.is_modified

    @is_modified.setter
    def is_modified(self, val):
        self.editor.is_modified = val

    def create_toolbars(self):
        self.action_bar = b = self.addToolBar(_('Edit actions tool bar'))
        b.setObjectName('action_bar')  # Needed for saveState
        self.tools_bar = b = self.addToolBar(_('Editor tools'))
        b.setObjectName('tools_bar')
        self.bars = [self.action_bar, self.tools_bar]
        if self.syntax == 'html':
            self.format_bar = b = self.addToolBar(_('Format text'))
            b.setObjectName('html_format_bar')
            self.bars.append(self.format_bar)
        self.insert_tag_menu = QMenu(self)
        self.populate_toolbars()
        for x in self.bars:
            x.setFloatable(False)
            x.topLevelChanged.connect(self.toolbar_floated)
            x.setIconSize(QSize(tprefs['toolbar_icon_size'], tprefs['toolbar_icon_size']))

    def toolbar_floated(self, floating):
        if not floating:
            self.save_state()
            for ed in itervalues(editors):
                if ed is not self:
                    ed.restore_state()

    def save_state(self):
        for bar in self.bars:
            if bar.isFloating():
                return
        tprefs['%s-editor-state' % self.syntax] = bytearray(self.saveState())

    def restore_state(self):
        state = tprefs.get('%s-editor-state' % self.syntax, None)
        if state is not None:
            self.restoreState(state)
        for bar in self.bars:
            bar.setVisible(len(bar.actions()) > 0)

    def populate_toolbars(self):
        self.action_bar.clear(), self.tools_bar.clear()

        def add_action(name, bar):
            if name is None:
                bar.addSeparator()
                return
            try:
                ac = actions[name]
            except KeyError:
                if DEBUG:
                    prints('Unknown editor tool: %r' % name)
                return
            bar.addAction(ac)
            if name == 'insert-tag':
                w = bar.widgetForAction(ac)
                if hasattr(w, 'setPopupMode'):
                    # For some unknown reason this button is occasionally a
                    # QPushButton instead of a QToolButton
                    w.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
                w.setMenu(self.insert_tag_menu)
                w.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                w.customContextMenuRequested.connect(w.showMenu)
                self._build_insert_tag_button_menu()
            elif name == 'change-paragraph':
                m = ac.m = QMenu()
                ac.setMenu(m)
                ch = bar.widgetForAction(ac)
                if hasattr(ch, 'setPopupMode'):
                    # For some unknown reason this button is occasionally a
                    # QPushButton instead of a QToolButton
                    ch.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                for name in tuple('h%d' % d for d in range(1, 7)) + ('p',):
                    m.addAction(actions['rename-block-tag-%s' % name])

        for name in tprefs.get('editor_common_toolbar', ()):
            add_action(name, self.action_bar)

        for name in tprefs.get('editor_%s_toolbar' % self.syntax, ()):
            add_action(name, self.tools_bar)

        if self.syntax == 'html':
            self.format_bar.clear()
            for name in tprefs['editor_format_toolbar']:
                add_action(name, self.format_bar)
        self.restore_state()

    def break_cycles(self):
        for x in ('modification_state_changed', 'word_ignored', 'link_clicked', 'class_clicked', 'smart_highlighting_updated'):
            try:
                getattr(self, x).disconnect()
            except TypeError:
                pass  # in case this signal was never connected
        self.undo_redo_state_changed.disconnect()
        self.copy_available_state_changed.disconnect()
        self.cursor_position_changed.disconnect()
        self.data_changed.disconnect()
        self.editor.undoAvailable.disconnect()
        self.editor.redoAvailable.disconnect()
        self.editor.modificationChanged.disconnect()
        self.editor.textChanged.disconnect()
        self.editor.copyAvailable.disconnect()
        self.editor.cursorPositionChanged.disconnect()
        self.editor.link_clicked.disconnect()
        self.editor.class_clicked.disconnect()
        self.editor.smart_highlighting_updated.disconnect()
        self.editor.setPlainText('')
        self.editor.smarts = None
        self.editor.request_completion = None

    def _modification_state_changed(self):
        self.is_synced_to_container = self.is_modified
        self.modification_state_changed.emit(self.is_modified)

    def _data_changed(self):
        self.is_synced_to_container = False
        self.data_changed.emit(self)

    def _undo_available(self, available):
        self.undo_available = available
        self.undo_redo_state_changed.emit(self.undo_available, self.redo_available)

    def _redo_available(self, available):
        self.redo_available = available
        self.undo_redo_state_changed.emit(self.undo_available, self.redo_available)

    def _copy_available(self, available):
        self.copy_available = self.cut_available = available
        self.copy_available_state_changed.emit(available)

    def _cursor_position_changed(self, *args):
        self.cursor_position_changed.emit()

    @property
    def cursor_position(self):
        c = self.editor.textCursor()
        char = ''
        col = c.positionInBlock()
        if not c.atStart():
            c.clearSelection()
            c.movePosition(QTextCursor.MoveOperation.PreviousCharacter, QTextCursor.MoveMode.KeepAnchor)
            char = str(c.selectedText()).rstrip('\0')
        return (c.blockNumber() + 1, col, char)

    def cut(self):
        self.editor.cut()

    def copy(self):
        self.editor.copy()

    def go_to_line(self, line, col=None):
        self.editor.go_to_line(line, col=col)

    def paste(self):
        if not self.editor.canPaste():
            return error_dialog(self, _('No text'), _(
                'There is no suitable text in the clipboard to paste.'), show=True)
        self.editor.paste()

    def contextMenuEvent(self, ev):
        ev.ignore()

    def fix_html(self):
        if self.syntax == 'html':
            from calibre.ebooks.oeb.polish.pretty import fix_html
            self.editor.replace_text(fix_html(current_container(), str(self.editor.toPlainText())).decode('utf-8'))
            return True
        return False

    def pretty_print(self, name):
        from calibre.ebooks.oeb.polish.pretty import (
            pretty_css, pretty_html, pretty_xml
        )
        if self.syntax in {'css', 'html', 'xml'}:
            func = {'css':pretty_css, 'xml':pretty_xml}.get(self.syntax, pretty_html)
            original_text = str(self.editor.toPlainText())
            prettied_text = func(current_container(), name, original_text).decode('utf-8')
            if original_text != prettied_text:
                self.editor.replace_text(prettied_text)
            return True
        return False

    def show_context_menu(self, pos):
        m = QMenu(self)
        a = m.addAction
        c = self.editor.cursorForPosition(pos)
        origc = QTextCursor(c)
        current_cursor = self.editor.textCursor()
        r = origr = self.editor.syntax_range_for_cursor(c)
        if (r is None or not r.format.property(SPELL_PROPERTY)) and c.positionInBlock() > 0 and not current_cursor.hasSelection():
            c.setPosition(c.position() - 1)
            r = self.editor.syntax_range_for_cursor(c)

        if r is not None and r.format.property(SPELL_PROPERTY):
            word = self.editor.text_for_range(c.block(), r)
            locale = self.editor.spellcheck_locale_for_cursor(c)
            orig_pos = c.position()
            c.setPosition(orig_pos - utf16_length(word))
            found = False
            self.editor.setTextCursor(c)
            if locale and self.editor.find_spell_word([word], locale.langcode, center_on_cursor=False):
                found = True
                fc = self.editor.textCursor()
                if fc.position() < c.position():
                    self.editor.find_spell_word([word], locale.langcode, center_on_cursor=False)
            spell_cursor = self.editor.textCursor()
            if current_cursor.hasSelection():
                # Restore the current cursor so that any selection is preserved
                # for the change case actions
                self.editor.setTextCursor(current_cursor)
            if found:
                suggestions = dictionaries.suggestions(word, locale)[:7]
                if suggestions:
                    for suggestion in suggestions:
                        ac = m.addAction(suggestion, partial(self.editor.simple_replace, suggestion, cursor=spell_cursor))
                        f = ac.font()
                        f.setBold(True), ac.setFont(f)
                    m.addSeparator()
                m.addAction(actions['spell-next'])
                m.addAction(_('Ignore this word'), partial(self._nuke_word, None, word, locale))
                dics = dictionaries.active_user_dictionaries
                if len(dics) > 0:
                    if len(dics) == 1:
                        m.addAction(_('Add this word to the dictionary: {0}').format(dics[0].name), partial(
                            self._nuke_word, dics[0].name, word, locale))
                    else:
                        ac = m.addAction(_('Add this word to the dictionary'))
                        dmenu = QMenu(m)
                        ac.setMenu(dmenu)
                        for dic in dics:
                            dmenu.addAction(dic.name, partial(self._nuke_word, dic.name, word, locale))
                m.addSeparator()

        if origr is not None and origr.format.property(LINK_PROPERTY):
            href = self.editor.text_for_range(origc.block(), origr)
            m.addAction(_('Open %s') % href, partial(self.link_clicked.emit, href))

        if origr is not None and origr.format.property(CLASS_ATTRIBUTE_PROPERTY):
            cls = self.editor.class_for_position(pos)
            if cls:
                class_name = cls['class']
                m.addAction(_('Rename the class {}').format(class_name), partial(self.rename_class.emit, class_name))

        if origr is not None and (origr.format.property(TAG_NAME_PROPERTY) or origr.format.property(CSS_PROPERTY)):
            word = self.editor.text_for_range(origc.block(), origr)
            item_type = 'tag_name' if origr.format.property(TAG_NAME_PROPERTY) else 'css_property'
            url = help_url(word, item_type, self.editor.highlighter.doc_name, extra_data=current_container().opf_version)
            if url is not None:
                m.addAction(_('Show help for: %s') % word, partial(open_url, url))

        for x in ('undo', 'redo'):
            ac = actions['editor-%s' % x]
            if ac.isEnabled():
                a(ac)
        m.addSeparator()
        for x in ('cut', 'copy', 'paste'):
            ac = actions['editor-' + x]
            if ac.isEnabled():
                a(ac)
        m.addSeparator()
        m.addAction(_('&Select all'), self.editor.select_all)
        if self.selected_text or self.has_marked_text:
            update_mark_text_action(self)
            m.addAction(actions['mark-selected-text'])
        if self.syntax != 'css' and actions['editor-cut'].isEnabled():
            cm = QMenu(_('C&hange case'), m)
            for ac in 'upper lower swap title capitalize'.split():
                cm.addAction(actions['transform-case-' + ac])
            m.addMenu(cm)
        if self.syntax == 'html':
            m.addAction(actions['multisplit'])
        m.exec(self.editor.viewport().mapToGlobal(pos))

    def goto_sourceline(self, *args, **kwargs):
        return self.editor.goto_sourceline(*args, **kwargs)

    def goto_css_rule(self, *args, **kwargs):
        return self.editor.goto_css_rule(*args, **kwargs)

    def get_tag_contents(self, *args, **kwargs):
        return self.editor.get_tag_contents(*args, **kwargs)

    def _nuke_word(self, dic, word, locale):
        if dic is None:
            dictionaries.ignore_word(word, locale)
        else:
            dictionaries.add_to_user_dictionary(dic, word, locale)
        self.word_ignored.emit(word, locale)


def launch_editor(path_to_edit, path_is_raw=False, syntax='html', callback=None):
    from calibre.gui2 import Application
    from calibre.gui2.tweak_book import dictionaries
    from calibre.gui2.tweak_book.editor.syntax.html import refresh_spell_check_status
    from calibre.gui2.tweak_book.main import option_parser
    from calibre.gui2.tweak_book.ui import Main
    dictionaries.initialize()
    refresh_spell_check_status()
    opts = option_parser().parse_args([])
    app = Application([])
    # Create the actions that are placed into the editors toolbars
    main = Main(opts)  # noqa
    if path_is_raw:
        raw = path_to_edit
    else:
        with open(path_to_edit, 'rb') as f:
            raw = f.read().decode('utf-8')
        ext = path_to_edit.rpartition('.')[-1].lower()
        if ext in ('html', 'htm', 'xhtml', 'xhtm'):
            syntax = 'html'
        elif ext in ('css',):
            syntax = 'css'
    t = Editor(syntax)
    t.data = raw
    if callback is not None:
        callback(t)
    t.show()
    app.exec()
