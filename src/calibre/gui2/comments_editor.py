#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, os, json, weakref

from lxml import html
import sip

from PyQt5.Qt import (QApplication, QFontInfo, QSize, QWidget, QPlainTextEdit,
    QToolBar, QVBoxLayout, QAction, QIcon, Qt, QTabWidget, QUrl, QFormLayout,
    QSyntaxHighlighter, QColor, QColorDialog, QMenu, QDialog, QLabel,
    QHBoxLayout, QKeySequence, QLineEdit, QDialogButtonBox, QPushButton,
    QCheckBox)
from PyQt5.QtWebKitWidgets import QWebView, QWebPage

from calibre.ebooks.chardet import xml_to_unicode
from calibre import xml_replace_entities, prepare_string_for_xml
from calibre.gui2 import open_url, error_dialog, choose_files, gprefs, NO_URL_FORMATTING, secure_web_page
from calibre.utils.soupparser import fromstring
from calibre.utils.config import tweaks
from calibre.utils.imghdr import what


class PageAction(QAction):  # {{{

    def __init__(self, wac, icon, text, checkable, view):
        QAction.__init__(self, QIcon(I(icon+'.png')), text, view)
        self._page_action = getattr(QWebPage, wac)
        self.setCheckable(checkable)
        self.triggered.connect(self.trigger_page_action)
        view.selectionChanged.connect(self.update_state,
                type=Qt.QueuedConnection)
        self.page_action.changed.connect(self.update_state,
                type=Qt.QueuedConnection)
        self.update_state()

    @property
    def page_action(self):
        return self.parent().pageAction(self._page_action)

    def trigger_page_action(self, *args):
        self.page_action.trigger()

    def update_state(self, *args):
        if sip.isdeleted(self) or sip.isdeleted(self.page_action):
            return
        if self.isCheckable():
            self.setChecked(self.page_action.isChecked())
        self.setEnabled(self.page_action.isEnabled())

# }}}


class BlockStyleAction(QAction):  # {{{

    def __init__(self, text, name, view):
        QAction.__init__(self, text, view)
        self._name = name
        self.triggered.connect(self.apply_style)

    def apply_style(self, *args):
        self.parent().exec_command('formatBlock', self._name)

# }}}


class EditorWidget(QWebView):  # {{{

    def __init__(self, parent=None):
        QWebView.__init__(self, parent)
        self._parent = weakref.ref(parent)
        self.readonly = False

        self.comments_pat = re.compile(r'<!--.*?-->', re.DOTALL)

        extra_shortcuts = {
                'ToggleBold': 'Bold',
                'ToggleItalic': 'Italic',
                'ToggleUnderline': 'Underline',
        }

        for wac, name, icon, text, checkable in [
                ('ToggleBold', 'bold', 'format-text-bold', _('Bold'), True),
                ('ToggleItalic', 'italic', 'format-text-italic', _('Italic'),
                    True),
                ('ToggleUnderline', 'underline', 'format-text-underline',
                    _('Underline'), True),
                ('ToggleStrikethrough', 'strikethrough', 'format-text-strikethrough',
                    _('Strikethrough'), True),
                ('ToggleSuperscript', 'superscript', 'format-text-superscript',
                    _('Superscript'), True),
                ('ToggleSubscript', 'subscript', 'format-text-subscript',
                    _('Subscript'), True),
                ('InsertOrderedList', 'ordered_list', 'format-list-ordered',
                    _('Ordered list'), True),
                ('InsertUnorderedList', 'unordered_list', 'format-list-unordered',
                    _('Unordered list'), True),

                ('AlignLeft', 'align_left', 'format-justify-left',
                    _('Align left'), False),
                ('AlignCenter', 'align_center', 'format-justify-center',
                    _('Align center'), False),
                ('AlignRight', 'align_right', 'format-justify-right',
                    _('Align right'), False),
                ('AlignJustified', 'align_justified', 'format-justify-fill',
                    _('Align justified'), False),
                ('Undo', 'undo', 'edit-undo', _('Undo'), False),
                ('Redo', 'redo', 'edit-redo', _('Redo'), False),
                ('RemoveFormat', 'remove_format', 'edit-clear', _('Remove formatting'), False),
                ('Copy', 'copy', 'edit-copy', _('Copy'), False),
                ('Paste', 'paste', 'edit-paste', _('Paste'), False),
                ('Cut', 'cut', 'edit-cut', _('Cut'), False),
                ('Indent', 'indent', 'format-indent-more',
                    _('Increase indentation'), False),
                ('Outdent', 'outdent', 'format-indent-less',
                    _('Decrease indentation'), False),
                ('SelectAll', 'select_all', 'edit-select-all',
                    _('Select all'), False),
            ]:
            ac = PageAction(wac, icon, text, checkable, self)
            setattr(self, 'action_'+name, ac)
            ss = extra_shortcuts.get(wac, None)
            if ss:
                ac.setShortcut(QKeySequence(getattr(QKeySequence, ss)))
            if wac == 'RemoveFormat':
                ac.triggered.connect(self.remove_format_cleanup,
                        type=Qt.QueuedConnection)

        self.action_color = QAction(QIcon(I('format-text-color.png')), _('Foreground color'),
                self)
        self.action_color.triggered.connect(self.foreground_color)

        self.action_background = QAction(QIcon(I('format-fill-color.png')),
                _('Background color'), self)
        self.action_background.triggered.connect(self.background_color)

        self.action_block_style = QAction(QIcon(I('format-text-heading.png')),
                _('Style text block'), self)
        self.action_block_style.setToolTip(
                _('Style the selected text block'))
        self.block_style_menu = QMenu(self)
        self.action_block_style.setMenu(self.block_style_menu)
        self.block_style_actions = []
        for text, name in [
                (_('Normal'), 'p'),
                (_('Heading') +' 1', 'h1'),
                (_('Heading') +' 2', 'h2'),
                (_('Heading') +' 3', 'h3'),
                (_('Heading') +' 4', 'h4'),
                (_('Heading') +' 5', 'h5'),
                (_('Heading') +' 6', 'h6'),
                (_('Pre-formatted'), 'pre'),
                (_('Blockquote'), 'blockquote'),
                (_('Address'), 'address'),
                ]:
            ac = BlockStyleAction(text, name, self)
            self.block_style_menu.addAction(ac)
            self.block_style_actions.append(ac)

        self.action_insert_link = QAction(QIcon(I('insert-link.png')),
                _('Insert link or image'), self)
        self.action_insert_link.triggered.connect(self.insert_link)
        self.pageAction(QWebPage.ToggleBold).changed.connect(self.update_link_action)
        self.action_insert_link.setEnabled(False)
        self.action_clear = QAction(QIcon(I('trash.png')), _('Clear'), self)
        self.action_clear.triggered.connect(self.clear_text)

        self.page().setLinkDelegationPolicy(QWebPage.DelegateAllLinks)
        self.page().linkClicked.connect(self.link_clicked)
        secure_web_page(self.page().settings())

        self.setHtml('')
        self.set_readonly(False)

    def update_link_action(self):
        wac = self.pageAction(QWebPage.ToggleBold)
        self.action_insert_link.setEnabled(wac.isEnabled())

    def set_readonly(self, what):
        self.readonly = what
        self.page().setContentEditable(not self.readonly)

    def clear_text(self, *args):
        us = self.page().undoStack()
        us.beginMacro('clear all text')
        self.action_select_all.trigger()
        self.action_remove_format.trigger()
        self.exec_command('delete')
        us.endMacro()
        self.set_font_style()
        self.setFocus(Qt.OtherFocusReason)

    def link_clicked(self, url):
        open_url(url)

    def foreground_color(self):
        col = QColorDialog.getColor(Qt.black, self,
                _('Choose foreground color'), QColorDialog.ShowAlphaChannel)
        if col.isValid():
            self.exec_command('foreColor', unicode(col.name()))

    def background_color(self):
        col = QColorDialog.getColor(Qt.white, self,
                _('Choose background color'), QColorDialog.ShowAlphaChannel)
        if col.isValid():
            self.exec_command('hiliteColor', unicode(col.name()))

    def insert_link(self, *args):
        link, name, is_image = self.ask_link()
        if not link:
            return
        url = self.parse_link(link)
        if url.isValid():
            url = unicode(url.toString(NO_URL_FORMATTING))
            self.setFocus(Qt.OtherFocusReason)
            if is_image:
                self.exec_command('insertHTML',
                        '<img src="%s" alt="%s"></img>'%(prepare_string_for_xml(url, True),
                            prepare_string_for_xml(name or _('Image'), True)))
            elif name:
                self.exec_command('insertHTML',
                        '<a href="%s">%s</a>'%(prepare_string_for_xml(url, True),
                            prepare_string_for_xml(name)))
            else:
                self.exec_command('createLink', url)
        else:
            error_dialog(self, _('Invalid URL'),
                         _('The url %r is invalid') % link, show=True)

    def ask_link(self):
        d = QDialog(self)
        d.setWindowTitle(_('Create link'))
        l = QFormLayout()
        l.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        d.setLayout(l)
        d.url = QLineEdit(d)
        d.name = QLineEdit(d)
        d.treat_as_image = QCheckBox(d)
        d.setMinimumWidth(600)
        d.bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        d.br = b = QPushButton(_('&Browse'))
        b.setIcon(QIcon(I('document_open.png')))

        def cf():
            files = choose_files(d, 'select link file', _('Choose file'), select_only_single_file=True)
            if files:
                path = files[0]
                d.url.setText(path)
                if path and os.path.exists(path):
                    with lopen(path, 'rb') as f:
                        q = what(f)
                    is_image = q in {'jpeg', 'png', 'gif'}
                    d.treat_as_image.setChecked(is_image)

        b.clicked.connect(cf)
        d.la = la = QLabel(_(
            'Enter a URL. If you check the "Treat the URL as an image" box '
            'then the URL will be added as an image reference instead of as '
            'a link. You can also choose to create a link to a file on '
            'your computer. '
            'Note that if you create a link to a file on your computer, it '
            'will stop working if the file is moved.'))
        la.setWordWrap(True)
        la.setStyleSheet('QLabel { margin-bottom: 1.5ex }')
        l.setWidget(0, l.SpanningRole, la)
        l.addRow(_('Enter &URL:'), d.url)
        l.addRow(_('Treat the URL as an &image'), d.treat_as_image)
        l.addRow(_('Enter &name (optional):'), d.name)
        l.addRow(_('Choose a file on your computer:'), d.br)
        l.addRow(d.bb)
        d.bb.accepted.connect(d.accept)
        d.bb.rejected.connect(d.reject)
        d.resize(d.sizeHint())
        link, name, is_image = None, None, False
        if d.exec_() == d.Accepted:
            link, name = unicode(d.url.text()).strip(), unicode(d.name.text()).strip()
            is_image = d.treat_as_image.isChecked()
        return link, name, is_image

    def parse_link(self, link):
        link = link.strip()
        if link and os.path.exists(link):
            return QUrl.fromLocalFile(link)
        has_schema = re.match(r'^[a-zA-Z]+:', link)
        if has_schema is not None:
            url = QUrl(link, QUrl.TolerantMode)
            if url.isValid():
                return url
        if os.path.exists(link):
            return QUrl.fromLocalFile(link)

        if has_schema is None:
            first, _, rest = link.partition('.')
            prefix = 'http'
            if first == 'ftp':
                prefix = 'ftp'
            url = QUrl(prefix +'://'+link, QUrl.TolerantMode)
            if url.isValid():
                return url

        return QUrl(link, QUrl.TolerantMode)

    def sizeHint(self):
        return QSize(150, 150)

    def exec_command(self, cmd, arg=None):
        frame = self.page().mainFrame()
        if arg is not None:
            js = 'document.execCommand("%s", false, %s);' % (cmd,
                    json.dumps(unicode(arg)))
        else:
            js = 'document.execCommand("%s", false, null);' % cmd
        frame.evaluateJavaScript(js)

    def remove_format_cleanup(self):
        self.html = self.html

    @dynamic_property
    def html(self):

        def fget(self):
            ans = u''
            try:
                if not self.page().mainFrame().documentElement().findFirst('meta[name="calibre-dont-sanitize"]').isNull():
                    # Bypass cleanup if special meta tag exists
                    return unicode(self.page().mainFrame().toHtml())
                check = unicode(self.page().mainFrame().toPlainText()).strip()
                raw = unicode(self.page().mainFrame().toHtml())
                raw = xml_to_unicode(raw, strip_encoding_pats=True,
                                    resolve_entities=True)[0]
                raw = self.comments_pat.sub('', raw)
                if not check and '<img' not in raw.lower():
                    return ans

                try:
                    root = html.fromstring(raw)
                except:
                    root = fromstring(raw)

                elems = []
                for body in root.xpath('//body'):
                    if body.text:
                        elems.append(body.text)
                    elems += [html.tostring(x, encoding=unicode) for x in body if
                        x.tag not in ('script', 'style')]

                if len(elems) > 1:
                    ans = u'<div>%s</div>'%(u''.join(elems))
                else:
                    ans = u''.join(elems)
                    if not ans.startswith('<'):
                        ans = '<p>%s</p>'%ans
                ans = xml_replace_entities(ans)
            except:
                import traceback
                traceback.print_exc()

            return ans

        def fset(self, val):
            self.setHtml(val)
            self.set_font_style()
        return property(fget=fget, fset=fset)

    def set_html(self, val, allow_undo=True):
        if not allow_undo or self.readonly:
            self.html = val
            return
        mf = self.page().mainFrame()
        mf.evaluateJavaScript('document.execCommand("selectAll", false, null)')
        mf.evaluateJavaScript('document.execCommand("insertHTML", false, %s)' % json.dumps(unicode(val)))
        self.set_font_style()

    def set_font_style(self):
        fi = QFontInfo(QApplication.font(self))
        f  = fi.pixelSize() + 1 + int(tweaks['change_book_details_font_size_by'])
        fam = unicode(fi.family()).strip().replace('"', '')
        if not fam:
            fam = 'sans-serif'
        style = 'font-size: %fpx; font-family:"%s",sans-serif;' % (f, fam)

        # toList() is needed because PyQt on Debian is old/broken
        for body in self.page().mainFrame().documentElement().findAll('body').toList():
            body.setAttribute('style', style)
        self.page().setContentEditable(not self.readonly)

    def event(self, ev):
        if ev.type() in (ev.KeyPress, ev.KeyRelease, ev.ShortcutOverride) and ev.key() in (
                Qt.Key_Tab, Qt.Key_Escape, Qt.Key_Backtab):
            if (ev.key() == Qt.Key_Tab and ev.modifiers() & Qt.ControlModifier and ev.type() == ev.KeyPress):
                self.exec_command('insertHTML', '<span style="white-space:pre">\t</span>')
                ev.accept()
                return True
            ev.ignore()
            return False
        return QWebView.event(self, ev)

    def contextMenuEvent(self, ev):
        menu = self.page().createStandardContextMenu()
        paste = self.pageAction(QWebPage.Paste)
        for action in menu.actions():
            if action == paste:
                menu.insertAction(action, self.pageAction(QWebPage.PasteAndMatchStyle))
        parent = self._parent()
        if hasattr(parent, 'toolbars_visible'):
            vis = parent.toolbars_visible
            menu.addAction(_('%s toolbars') % (_('Hide') if vis else _('Show')), parent.toggle_toolbars)
        menu.exec_(ev.globalPos())

# }}}

# Highlighter {{{


State_Text = -1
State_DocType = 0
State_Comment = 1
State_TagStart = 2
State_TagName = 3
State_InsideTag = 4
State_AttributeName = 5
State_SingleQuote = 6
State_DoubleQuote = 7
State_AttributeValue = 8


class Highlighter(QSyntaxHighlighter):

    def __init__(self, doc):
        QSyntaxHighlighter.__init__(self, doc)
        self.colors = {}
        self.colors['doctype']        = QColor(192, 192, 192)
        self.colors['entity']         = QColor(128, 128, 128)
        self.colors['tag']            = QColor(136,  18, 128)
        self.colors['comment']        = QColor(35, 110,  37)
        self.colors['attrname']       = QColor(153,  69,   0)
        self.colors['attrval']        = QColor(36,  36, 170)

    def highlightBlock(self, text):
        state = self.previousBlockState()
        len_ = len(text)
        start = 0
        pos = 0

        while pos < len_:

            if state == State_Comment:
                start = pos
                while pos < len_:
                    if text[pos:pos+3] == u"-->":
                        pos += 3
                        state = State_Text
                        break
                    else:
                        pos += 1
                self.setFormat(start, pos - start, self.colors['comment'])

            elif state == State_DocType:
                start = pos
                while pos < len_:
                    ch = text[pos]
                    pos += 1
                    if ch == u'>':
                        state = State_Text
                        break
                self.setFormat(start, pos - start, self.colors['doctype'])

            # at '<' in e.g. "<span>foo</span>"
            elif state == State_TagStart:
                start = pos + 1
                while pos < len_:
                    ch = text[pos]
                    pos += 1
                    if ch == u'>':
                        state = State_Text
                        break
                    if not ch.isspace():
                        pos -= 1
                        state = State_TagName
                        break

            # at 'b' in e.g "<blockquote>foo</blockquote>"
            elif state == State_TagName:
                start = pos
                while pos < len_:
                    ch = text[pos]
                    pos += 1
                    if ch.isspace():
                        pos -= 1
                        state = State_InsideTag
                        break
                    if ch == u'>':
                        state = State_Text
                        break
                self.setFormat(start, pos - start, self.colors['tag'])

            # anywhere after tag name and before tag closing ('>')
            elif state == State_InsideTag:
                start = pos

                while pos < len_:
                    ch = text[pos]
                    pos += 1

                    if ch == u'/':
                        continue

                    if ch == u'>':
                        state = State_Text
                        break

                    if not ch.isspace():
                        pos -= 1
                        state = State_AttributeName
                        break

            # at 's' in e.g. <img src=bla.png/>
            elif state == State_AttributeName:
                start = pos

                while pos < len_:
                    ch = text[pos]
                    pos += 1

                    if ch == u'=':
                        state = State_AttributeValue
                        break

                    if ch in (u'>', u'/'):
                        state = State_InsideTag
                        break

                self.setFormat(start, pos - start, self.colors['attrname'])

            # after '=' in e.g. <img src=bla.png/>
            elif state == State_AttributeValue:
                start = pos

                # find first non-space character
                while pos < len_:
                    ch = text[pos]
                    pos += 1

                    # handle opening single quote
                    if ch == u"'":
                        state = State_SingleQuote
                        break

                    # handle opening double quote
                    if ch == u'"':
                        state = State_DoubleQuote
                        break

                    if not ch.isspace():
                        break

                if state == State_AttributeValue:
                    # attribute value without quote
                    # just stop at non-space or tag delimiter
                    start = pos
                    while pos < len_:
                        ch = text[pos]
                        if ch.isspace():
                            break
                        if ch in (u'>', u'/'):
                            break
                        pos += 1
                    state = State_InsideTag
                    self.setFormat(start, pos - start, self.colors['attrval'])

            # after the opening single quote in an attribute value
            elif state == State_SingleQuote:
                start = pos

                while pos < len_:
                    ch = text[pos]
                    pos += 1
                    if ch == u"'":
                        break

                state = State_InsideTag

                self.setFormat(start, pos - start, self.colors['attrval'])

            # after the opening double quote in an attribute value
            elif state == State_DoubleQuote:
                start = pos

                while pos < len_:
                    ch = text[pos]
                    pos += 1
                    if ch == u'"':
                        break

                state = State_InsideTag

                self.setFormat(start, pos - start, self.colors['attrval'])

            else:
                # State_Text and default
                while pos < len_:
                    ch = text[pos]
                    if ch == u'<':
                        if text[pos:pos+4] == u"<!--":
                            state = State_Comment
                        else:
                            if text[pos:pos+9].upper() == u"<!DOCTYPE":
                                state = State_DocType
                            else:
                                state = State_TagStart
                        break
                    elif ch == u'&':
                        start = pos
                        while pos < len_ and text[pos] != u';':
                            self.setFormat(start, pos - start,
                                    self.colors['entity'])
                            pos += 1

                    else:
                        pos += 1

        self.setCurrentBlockState(state)

# }}}


class Editor(QWidget):  # {{{

    toolbar_prefs_name = None

    def __init__(self, parent=None, one_line_toolbar=False, toolbar_prefs_name=None):
        QWidget.__init__(self, parent)
        self.toolbar_prefs_name = toolbar_prefs_name or self.toolbar_prefs_name
        self.toolbar1 = QToolBar(self)
        self.toolbar2 = QToolBar(self)
        self.toolbar3 = QToolBar(self)
        for i in range(1, 4):
            t = getattr(self, 'toolbar%d'%i)
            t.setIconSize(QSize(18, 18))
        self.editor = EditorWidget(self)
        self.set_html = self.editor.set_html
        self.tabs = QTabWidget(self)
        self.tabs.setTabPosition(self.tabs.South)
        self.wyswyg = QWidget(self.tabs)
        self.code_edit = QPlainTextEdit(self.tabs)
        self.source_dirty = False
        self.wyswyg_dirty = True

        self._layout = QVBoxLayout(self)
        self.wyswyg.layout = l = QVBoxLayout(self.wyswyg)
        self.setLayout(self._layout)
        l.setContentsMargins(0, 0, 0, 0)
        if one_line_toolbar:
            tb = QHBoxLayout()
            l.addLayout(tb)
        else:
            tb = l
        tb.addWidget(self.toolbar1)
        tb.addWidget(self.toolbar2)
        tb.addWidget(self.toolbar3)
        l.addWidget(self.editor)
        self._layout.addWidget(self.tabs)
        self.tabs.addTab(self.wyswyg, _('N&ormal view'))
        self.tabs.addTab(self.code_edit, _('&HTML source'))
        self.tabs.currentChanged[int].connect(self.change_tab)
        self.highlighter = Highlighter(self.code_edit.document())
        self.layout().setContentsMargins(0, 0, 0, 0)
        if self.toolbar_prefs_name is not None:
            hidden = gprefs.get(self.toolbar_prefs_name)
            if hidden:
                self.hide_toolbars()

        # toolbar1 {{{
        self.toolbar1.addAction(self.editor.action_undo)
        self.toolbar1.addAction(self.editor.action_redo)
        self.toolbar1.addAction(self.editor.action_select_all)
        self.toolbar1.addAction(self.editor.action_remove_format)
        self.toolbar1.addAction(self.editor.action_clear)
        self.toolbar1.addSeparator()

        for x in ('copy', 'cut', 'paste'):
            ac = getattr(self.editor, 'action_'+x)
            self.toolbar1.addAction(ac)

        self.toolbar1.addSeparator()
        self.toolbar1.addAction(self.editor.action_background)
        # }}}

        # toolbar2 {{{
        for x in ('', 'un'):
            ac = getattr(self.editor, 'action_%sordered_list'%x)
            self.toolbar2.addAction(ac)
        self.toolbar2.addSeparator()
        for x in ('superscript', 'subscript', 'indent', 'outdent'):
            self.toolbar2.addAction(getattr(self.editor, 'action_' + x))
            if x in ('subscript', 'outdent'):
                self.toolbar2.addSeparator()

        self.toolbar2.addAction(self.editor.action_block_style)
        w = self.toolbar2.widgetForAction(self.editor.action_block_style)
        if hasattr(w, 'setPopupMode'):
            w.setPopupMode(w.InstantPopup)
        self.toolbar2.addAction(self.editor.action_insert_link)
        # }}}

        # toolbar3 {{{
        for x in ('bold', 'italic', 'underline', 'strikethrough'):
            ac = getattr(self.editor, 'action_'+x)
            self.toolbar3.addAction(ac)
        self.toolbar3.addSeparator()

        for x in ('left', 'center', 'right', 'justified'):
            ac = getattr(self.editor, 'action_align_'+x)
            self.toolbar3.addAction(ac)
        self.toolbar3.addSeparator()
        self.toolbar3.addAction(self.editor.action_color)
        # }}}

        self.code_edit.textChanged.connect(self.code_dirtied)
        self.editor.page().contentsChanged.connect(self.wyswyg_dirtied)

    def set_minimum_height_for_editor(self, val):
        self.editor.setMinimumHeight(val)

    @dynamic_property
    def html(self):
        def fset(self, v):
            self.editor.html = v

        def fget(self):
            self.tabs.setCurrentIndex(0)
            return self.editor.html
        return property(fget=fget, fset=fset)

    def change_tab(self, index):
        # print 'reloading:', (index and self.wyswyg_dirty) or (not index and
        #        self.source_dirty)
        if index == 1:  # changing to code view
            if self.wyswyg_dirty:
                self.code_edit.setPlainText(self.editor.html)
                self.wyswyg_dirty = False
        elif index == 0:  # changing to wyswyg
            if self.source_dirty:
                self.editor.html = unicode(self.code_edit.toPlainText())
                self.source_dirty = False

    @dynamic_property
    def tab(self):
        def fget(self):
            return 'code' if self.tabs.currentWidget() is self.code_edit else 'wyswyg'

        def fset(self, val):
            self.tabs.setCurrentWidget(self.code_edit if val == 'code' else self.wyswyg)
        return property(fget=fget, fset=fset)

    def wyswyg_dirtied(self, *args):
        self.wyswyg_dirty = True

    def code_dirtied(self, *args):
        self.source_dirty = True

    def hide_toolbars(self):
        self.toolbar1.setVisible(False)
        self.toolbar2.setVisible(False)
        self.toolbar3.setVisible(False)

    def show_toolbars(self):
        self.toolbar1.setVisible(True)
        self.toolbar2.setVisible(True)
        self.toolbar3.setVisible(True)

    def toggle_toolbars(self):
        visible = self.toolbars_visible
        getattr(self, ('hide' if visible else 'show') + '_toolbars')()
        if self.toolbar_prefs_name is not None:
            gprefs.set(self.toolbar_prefs_name, visible)

    @dynamic_property
    def toolbars_visible(self):
        def fget(self):
            return self.toolbar1.isVisible() or self.toolbar2.isVisible() or self.toolbar3.isVisible()

        def fset(self, val):
            getattr(self, ('show' if val else 'hide') + '_toolbars')()
        return property(fget=fget, fset=fset)

    def set_readonly(self, what):
        self.editor.set_readonly(what)

    def hide_tabs(self):
        self.tabs.tabBar().setVisible(False)

# }}}


if __name__ == '__main__':
    app = QApplication([])
    w = Editor()
    w.resize(800, 600)
    w.show()
    w.html = '''<span style="background-color: rgb(0, 255, 255); ">He hadn't
    set out to have an <em>affair</em>, <span style="font-style:italic; background-color:red">much</span> less a long-term, devoted one.</span>'''
    app.exec_()
    # print w.html
