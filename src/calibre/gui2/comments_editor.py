#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid at kovidgoyal.net>


import os
import re
import weakref
from collections import defaultdict
from contextlib import contextmanager

from html5_parser import parse
from lxml import html
from PyQt5.Qt import (
    QAction, QApplication, QBrush, QByteArray, QCheckBox, QColor, QColorDialog,
    QDialog, QDialogButtonBox, QFont, QFontInfo, QFontMetrics, QFormLayout,
    QHBoxLayout, QIcon, QKeySequence, QLabel, QLineEdit, QMenu, QPalette,
    QPlainTextEdit, QPushButton, QSize, QSyntaxHighlighter, Qt, QTabWidget,
    QTextBlockFormat, QTextCharFormat, QTextCursor, QTextEdit, QTextListFormat,
    QToolBar, QUrl, QVBoxLayout, QWidget, pyqtSignal, pyqtSlot
)

from calibre import xml_replace_entities
from calibre.ebooks.chardet import xml_to_unicode
from calibre.gui2 import NO_URL_FORMATTING, choose_files, error_dialog, gprefs, is_dark_theme
from calibre.gui2.book_details import css
from calibre.gui2.widgets import LineEditECM
from calibre.gui2.widgets2 import to_plain_text
from calibre.utils.config import tweaks
from calibre.utils.imghdr import what
from polyglot.builtins import filter, iteritems, itervalues, unicode_type

# Cleanup Qt markup {{{


def parse_style(style):
    props = filter(None, (x.strip() for x in style.split(';')))
    ans = {}
    for prop in props:
        try:
            k, v = prop.split(':', 1)
        except Exception:
            continue
        ans[k.strip().lower()] = v.strip()
    return ans


liftable_props = ('font-style', 'font-weight', 'font-family', 'font-size')


def lift_styles(tag, style_map):
    common_props = None
    has_text = bool(tag.text)
    child_styles = []
    for child in tag.iterchildren('*'):
        if child.tail:
            has_text = True
        style = style_map[child]
        child_styles.append(style)
        if common_props is None:
            common_props = style.copy()
        else:
            for k, v in tuple(iteritems(common_props)):
                if style.get(k) != v:
                    del common_props[k]
    if not has_text and common_props:
        lifted_props = []
        tag_style = style_map[tag]
        for k in liftable_props:
            if k in common_props:
                lifted_props.append(k)
                tag_style[k] = common_props[k]
        if lifted_props:
            for style in child_styles:
                for k in lifted_props:
                    del style[k]


def filter_qt_styles(style):
    for k in tuple(style):
        # -qt-paragraph-type is a hack used by Qt for empty paragraphs
        if k.startswith('-qt-'):
            del style[k]


def remove_margins(tag, style):
    ml, mr, mt, mb = (style.pop('margin-' + k, None) for k in 'left right top bottom'.split())
    is_blockquote = ml == mr and ml and ml != '0px' and (ml != mt or ml != mb)
    if is_blockquote:
        tag.tag = 'blockquote'


def remove_zero_indents(style):
    ti = style.get('text-indent')
    if ti == '0px':
        del style['text-indent']


def remove_heading_font_styles(tag, style):
    lvl = int(tag.tag[1:])
    expected_size = (None, 'xx-large', 'x-large', 'large', None, 'small', 'x-small')[lvl]
    if style.get('font-size', 1) == expected_size:
        del style['font-size']
    if style.get('font-weight') == '600':
        del style['font-weight']


def use_implicit_styling_for_span(span, style):
    is_italic = style.get('font-style') == 'italic'
    is_bold = style.get('font-weight') == '600'
    if is_italic and not is_bold:
        del style['font-style']
        span.tag = 'em'
    elif is_bold and not is_italic:
        del style['font-weight']
        span.tag = 'strong'
    if span.tag == 'span' and style.get('text-decoration') == 'underline':
        span.tag = 'u'
        del style['text-decoration']
    if span.tag == 'span' and style.get('text-decoration') == 'line-through':
        span.tag = 's'
        del style['text-decoration']
    if span.tag == 'span' and style.get('vertical-align') in ('sub', 'super'):
        span.tag = 'sub' if style.pop('vertical-align') == 'sub' else 'sup'


def use_implicit_styling_for_a(a, style_map):
    for span in a.iterchildren('span'):
        style = style_map[span]
        if style.get('text-decoration') == 'underline':
            del style['text-decoration']
        if style.get('color') == '#0000ff':
            del style['color']
        break


def merge_contiguous_links(root):
    all_hrefs = set(root.xpath('//a/@href'))
    for href in all_hrefs:
        tags = root.xpath('//a[@href="{}"]'.format(href))
        processed = set()

        def insert_tag(parent, child):
            parent.tail = child.tail
            if child.text:
                children = parent.getchildren()
                if children:
                    children[-1].tail = (children[-1].tail or '') + child.text
                else:
                    parent.text = (parent.text or '') + child.text
            for gc in child.iterchildren('*'):
                parent.append(gc)

        for a in tags:
            if a in processed or a.tail:
                continue
            processed.add(a)
            n = a
            remove = []
            while not n.tail and n.getnext() is not None and getattr(n.getnext(), 'tag', None) == 'a' and n.getnext().get('href') == href:
                n = n.getnext()
                processed.add(n)
                remove.append(n)
            for n in remove:
                insert_tag(a, n)
                n.getparent().remove(n)


def convert_anchors_to_ids(root):
    anchors = root.xpath('//a[@name]')
    for a in anchors:
        p = a.getparent()
        if len(a.attrib) == 1 and not p.text and a is p[0] and not a.text and not p.get('id') and a.get('name') and len(a) == 0:
            p.text = a.tail
            p.set('id', a.get('name'))
            p.remove(a)


def cleanup_qt_markup(root):
    from calibre.ebooks.docx.cleanup import lift
    style_map = defaultdict(dict)
    for tag in root.xpath('//*[@style]'):
        style_map[tag] = parse_style(tag.get('style'))
    block_tags = root.xpath('//body/*')
    for tag in block_tags:
        lift_styles(tag, style_map)
        tag_style = style_map[tag]
        remove_margins(tag, tag_style)
        remove_zero_indents(tag_style)
        if tag.tag.startswith('h') and tag.tag[1:] in '123456':
            remove_heading_font_styles(tag, tag_style)
        for child in tag.iterdescendants('a'):
            use_implicit_styling_for_a(child, style_map)
        for child in tag.iterdescendants('span'):
            use_implicit_styling_for_span(child, style_map[child])
        if tag.tag == 'p' and style_map[tag].get('-qt-paragraph-type') == 'empty':
            del tag[:]
            tag.text = '\xa0'
        if tag.tag in ('ol', 'ul'):
            for li in tag.iterdescendants('li'):
                ts = style_map.get(li)
                if ts:
                    remove_margins(li, ts)
                    remove_zero_indents(ts)
    for style in itervalues(style_map):
        filter_qt_styles(style)
    for tag, style in iteritems(style_map):
        if style:
            tag.set('style', '; '.join('{}: {}'.format(k, v) for k, v in iteritems(style)))
        else:
            tag.attrib.pop('style', None)
    for span in root.xpath('//span[not(@style)]'):
        lift(span)

    merge_contiguous_links(root)
    convert_anchors_to_ids(root)
# }}}


class EditorWidget(QTextEdit, LineEditECM):  # {{{

    data_changed = pyqtSignal()

    @property
    def readonly(self):
        return self.isReadOnly()

    @readonly.setter
    def readonly(self, val):
        self.setReadOnly(bool(val))

    @contextmanager
    def editing_cursor(self, set_cursor=True):
        c = self.textCursor()
        c.beginEditBlock()
        yield c
        c.endEditBlock()
        if set_cursor:
            self.setTextCursor(c)
        self.focus_self()

    def __init__(self, parent=None):
        QTextEdit.__init__(self, parent)
        self.setTabChangesFocus(True)
        self.document().setDefaultStyleSheet(css() + '\n\nli { margin-top: 0.5ex; margin-bottom: 0.5ex; }')
        font = self.font()
        f = QFontInfo(font)
        delta = tweaks['change_book_details_font_size_by'] + 1
        if delta:
            font.setPixelSize(f.pixelSize() + delta)
            self.setFont(font)
        f = QFontMetrics(self.font())
        self.em_size = f.horizontalAdvance('m')
        self.base_url = None
        self._parent = weakref.ref(parent)
        self.comments_pat = re.compile(r'<!--.*?-->', re.DOTALL)

        for rec in (
            ('bold', 'format-text-bold', _('Bold'), True),
            ('italic', 'format-text-italic', _('Italic'), True),
            ('underline', 'format-text-underline', _('Underline'), True),
            ('strikethrough', 'format-text-strikethrough', _('Strikethrough'), True),
            ('superscript', 'format-text-superscript', _('Superscript'), True),
            ('subscript', 'format-text-subscript', _('Subscript'), True),
            ('ordered_list', 'format-list-ordered', _('Ordered list'), True),
            ('unordered_list', 'format-list-unordered', _('Unordered list'), True),

            ('align_left', 'format-justify-left', _('Align left'), True),
            ('align_center', 'format-justify-center', _('Align center'), True),
            ('align_right', 'format-justify-right', _('Align right'), True),
            ('align_justified', 'format-justify-fill', _('Align justified'), True),
            ('undo', 'edit-undo', _('Undo'), ),
            ('redo', 'edit-redo', _('Redo'), ),
            ('remove_format', 'edit-clear', _('Remove formatting'), ),
            ('copy', 'edit-copy', _('Copy'), ),
            ('paste', 'edit-paste', _('Paste'), ),
            ('paste_and_match_style', 'edit-paste', _('Paste and match style'), ),
            ('cut', 'edit-cut', _('Cut'), ),
            ('indent', 'format-indent-more', _('Increase indentation'), ),
            ('outdent', 'format-indent-less', _('Decrease indentation'), ),
            ('select_all', 'edit-select-all', _('Select all'), ),

            ('color', 'format-text-color', _('Foreground color')),
            ('background', 'format-fill-color', _('Background color')),
            ('insert_link', 'insert-link', _('Insert link or image'),),
            ('insert_hr', 'format-text-hr', _('Insert separator'),),
            ('clear', 'trash', _('Clear')),
        ):
            name, icon, text = rec[:3]
            checkable = len(rec) == 4
            ac = QAction(QIcon(I(icon + '.png')), text, self)
            if checkable:
                ac.setCheckable(checkable)
            setattr(self, 'action_'+name, ac)
            ac.triggered.connect(getattr(self, 'do_' + name))

        self.action_block_style = QAction(QIcon(I('format-text-heading.png')),
                _('Style text block'), self)
        self.action_block_style.setToolTip(
                _('Style the selected text block'))
        self.block_style_menu = QMenu(self)
        self.action_block_style.setMenu(self.block_style_menu)
        self.block_style_actions = []
        h = _('Heading {0}')
        for text, name in (
            (_('Normal'), 'p'),
            (h.format(1), 'h1'),
            (h.format(2), 'h2'),
            (h.format(3), 'h3'),
            (h.format(4), 'h4'),
            (h.format(5), 'h5'),
            (h.format(6), 'h6'),
            (_('Blockquote'), 'blockquote'),
        ):
            ac = QAction(text, self)
            self.block_style_menu.addAction(ac)
            ac.block_name = name
            ac.setCheckable(True)
            self.block_style_actions.append(ac)
            ac.triggered.connect(self.do_format_block)

        self.setHtml('')
        self.copyAvailable.connect(self.update_clipboard_actions)
        self.update_clipboard_actions(False)
        self.selectionChanged.connect(self.update_selection_based_actions)
        self.update_selection_based_actions()
        connect_lambda(self.undoAvailable, self, lambda self, yes: self.action_undo.setEnabled(yes))
        connect_lambda(self.redoAvailable, self, lambda self, yes: self.action_redo.setEnabled(yes))
        self.action_undo.setEnabled(False), self.action_redo.setEnabled(False)
        self.textChanged.connect(self.update_cursor_position_actions)
        self.cursorPositionChanged.connect(self.update_cursor_position_actions)
        self.textChanged.connect(self.data_changed)
        self.update_cursor_position_actions()

    def keyPressEvent(self, ev):
        if ev.matches(QKeySequence.Bold):
            ev.accept()
            self.action_bold.toggle(), self.action_bold.trigger()
            return
        if ev.matches(QKeySequence.Italic):
            ev.accept()
            self.action_italic.toggle(), self.action_italic.trigger()
            return
        if ev.matches(QKeySequence.Underline):
            ev.accept()
            self.action_underline.toggle(), self.action_underline.trigger()
            return
        return QTextEdit.keyPressEvent(self, ev)

    def update_clipboard_actions(self, copy_available):
        self.action_copy.setEnabled(copy_available)
        self.action_cut.setEnabled(copy_available)

    def update_selection_based_actions(self):
        pass

    def update_cursor_position_actions(self):
        c = self.textCursor()
        ls = c.currentList()
        self.action_ordered_list.setChecked(ls is not None and ls.format().style() == QTextListFormat.ListDecimal)
        self.action_unordered_list.setChecked(ls is not None and ls.format().style() == QTextListFormat.ListDisc)
        tcf = c.charFormat()
        vert = tcf.verticalAlignment()
        self.action_superscript.setChecked(vert == QTextCharFormat.AlignSuperScript)
        self.action_subscript.setChecked(vert == QTextCharFormat.AlignSubScript)
        self.action_bold.setChecked(tcf.fontWeight() == QFont.Bold)
        self.action_italic.setChecked(tcf.fontItalic())
        self.action_underline.setChecked(tcf.fontUnderline())
        self.action_strikethrough.setChecked(tcf.fontStrikeOut())
        bf = c.blockFormat()
        a = bf.alignment()
        self.action_align_left.setChecked(a == Qt.AlignLeft)
        self.action_align_right.setChecked(a == Qt.AlignRight)
        self.action_align_center.setChecked(a == Qt.AlignHCenter)
        self.action_align_justified.setChecked(a == Qt.AlignJustify)
        lvl = bf.headingLevel()
        name = 'p'
        if lvl == 0:
            if bf.leftMargin() == bf.rightMargin() and bf.leftMargin() > 0:
                name = 'blockquote'
        else:
            name = 'h{}'.format(lvl)
        for ac in self.block_style_actions:
            ac.setChecked(ac.block_name == name)

    def set_readonly(self, what):
        self.readonly = what

    def focus_self(self):
        self.setFocus(Qt.TabFocusReason)

    def do_clear(self, *args):
        c = self.textCursor()
        c.beginEditBlock()
        c.movePosition(QTextCursor.Start, QTextCursor.MoveAnchor)
        c.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        c.removeSelectedText()
        c.endEditBlock()
        self.focus_self()
    clear_text = do_clear

    def do_bold(self):
        with self.editing_cursor() as c:
            fmt = QTextCharFormat()
            fmt.setFontWeight(
                QFont.Bold if c.charFormat().fontWeight() != QFont.Bold else QFont.Normal)
            c.mergeCharFormat(fmt)

    def do_italic(self):
        with self.editing_cursor() as c:
            fmt = QTextCharFormat()
            fmt.setFontItalic(not c.charFormat().fontItalic())
            c.mergeCharFormat(fmt)

    def do_underline(self):
        with self.editing_cursor() as c:
            fmt = QTextCharFormat()
            fmt.setFontUnderline(not c.charFormat().fontUnderline())
            c.mergeCharFormat(fmt)

    def do_strikethrough(self):
        with self.editing_cursor() as c:
            fmt = QTextCharFormat()
            fmt.setFontStrikeOut(not c.charFormat().fontStrikeOut())
            c.mergeCharFormat(fmt)

    def do_vertical_align(self, which):
        with self.editing_cursor() as c:
            fmt = QTextCharFormat()
            fmt.setVerticalAlignment(which)
            c.mergeCharFormat(fmt)

    def do_superscript(self):
        self.do_vertical_align(QTextCharFormat.AlignSuperScript)

    def do_subscript(self):
        self.do_vertical_align(QTextCharFormat.AlignSubScript)

    def do_list(self, fmt):
        with self.editing_cursor() as c:
            ls = c.currentList()
            if ls is not None:
                lf = ls.format()
                if lf.style() == fmt:
                    c.setBlockFormat(QTextBlockFormat())
                else:
                    lf.setStyle(fmt)
                    ls.setFormat(lf)
            else:
                ls = c.createList(fmt)

    def do_ordered_list(self):
        self.do_list(QTextListFormat.ListDecimal)

    def do_unordered_list(self):
        self.do_list(QTextListFormat.ListDisc)

    def do_alignment(self, which):
        with self.editing_cursor() as c:
            fmt = QTextBlockFormat()
            fmt.setAlignment(which)
            c.setBlockFormat(fmt)

    def do_align_left(self):
        self.do_alignment(Qt.AlignLeft)

    def do_align_center(self):
        self.do_alignment(Qt.AlignHCenter)

    def do_align_right(self):
        self.do_alignment(Qt.AlignRight)

    def do_align_justified(self):
        self.do_alignment(Qt.AlignJustify)

    def do_undo(self):
        self.undo()
        self.focus_self()

    def do_redo(self):
        self.redo()
        self.focus_self()

    def do_remove_format(self):
        with self.editing_cursor() as c:
            c.setBlockFormat(QTextBlockFormat())
            c.setCharFormat(QTextCharFormat())

    def do_copy(self):
        self.copy()
        self.focus_self()

    def do_paste(self):
        self.paste()
        self.focus_self()

    def do_paste_and_match_style(self):
        text = QApplication.instance().clipboard().text()
        if text:
            self.setText(text)

    def do_cut(self):
        self.cut()
        self.focus_self()

    def indent_block(self, mult=1):
        with self.editing_cursor() as c:
            bf = c.blockFormat()
            bf.setTextIndent(bf.textIndent() + 2 * self.em_size * mult)
            c.setBlockFormat(bf)

    def do_indent(self):
        self.indent_block()

    def do_outdent(self):
        self.indent_block(-1)

    def do_select_all(self):
        with self.editing_cursor() as c:
            c.movePosition(QTextCursor.Start, QTextCursor.MoveAnchor)
            c.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)

    def level_for_block_type(self, name):
        if name == 'blockquote':
            return 0
        return {q: i for i, q in enumerate('p h1 h2 h3 h4 h5 h6'.split())}[name]

    def do_format_block(self):
        name = self.sender().block_name
        with self.editing_cursor() as c:
            bf = QTextBlockFormat()
            cf = QTextCharFormat()
            bcf = c.blockCharFormat()
            lvl = self.level_for_block_type(name)
            wt = QFont.Bold if lvl else None
            adjust = (0, 3, 2, 1, 0, -1, -1)[lvl]
            pos = None
            if not c.hasSelection():
                pos = c.position()
                c.movePosition(QTextCursor.StartOfBlock, QTextCursor.MoveAnchor)
                c.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
            # margin values are taken from qtexthtmlparser.cpp
            hmargin = 0
            if name == 'blockquote':
                hmargin = 40
            tmargin = bmargin = 12
            if name == 'h1':
                tmargin, bmargin = 18, 12
            elif name == 'h2':
                tmargin, bmargin = 16, 12
            elif name == 'h3':
                tmargin, bmargin = 14, 12
            elif name == 'h4':
                tmargin, bmargin = 12, 12
            elif name == 'h5':
                tmargin, bmargin = 12, 4
            bf.setLeftMargin(hmargin), bf.setRightMargin(hmargin)
            bf.setTopMargin(tmargin), bf.setBottomMargin(bmargin)
            bf.setHeadingLevel(lvl)
            if adjust:
                bcf.setProperty(QTextCharFormat.FontSizeAdjustment, adjust)
                cf.setProperty(QTextCharFormat.FontSizeAdjustment, adjust)
            if wt:
                bcf.setProperty(QTextCharFormat.FontWeight, wt)
                cf.setProperty(QTextCharFormat.FontWeight, wt)
            c.setBlockCharFormat(bcf)
            c.mergeCharFormat(cf)
            c.mergeBlockFormat(bf)
            if pos is not None:
                c.setPosition(pos)

    def do_color(self):
        col = QColorDialog.getColor(Qt.black, self,
                _('Choose foreground color'), QColorDialog.ShowAlphaChannel)
        if col.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(QBrush(col))
            with self.editing_cursor() as c:
                c.mergeCharFormat(fmt)

    def do_background(self):
        col = QColorDialog.getColor(Qt.white, self,
                _('Choose background color'), QColorDialog.ShowAlphaChannel)
        if col.isValid():
            fmt = QTextCharFormat()
            fmt.setBackground(QBrush(col))
            with self.editing_cursor() as c:
                c.mergeCharFormat(fmt)

    def do_insert_hr(self, *args):
        with self.editing_cursor() as c:
            c.movePosition(c.EndOfBlock, c.MoveAnchor)
            c.insertHtml('<hr>')

    def do_insert_link(self, *args):
        link, name, is_image = self.ask_link()
        if not link:
            return
        url = self.parse_link(link)
        if url.isValid():
            url = unicode_type(url.toString(NO_URL_FORMATTING))
            self.focus_self()
            with self.editing_cursor() as c:
                if is_image:
                    c.insertImage(url)
                else:
                    oldfmt = QTextCharFormat(c.charFormat())
                    fmt = QTextCharFormat()
                    fmt.setAnchor(True)
                    fmt.setAnchorHref(url)
                    fmt.setForeground(QBrush(self.palette().color(QPalette.Link)))
                    if name or not c.hasSelection():
                        c.mergeCharFormat(fmt)
                        c.insertText(name or url)
                    else:
                        pos, anchor = c.position(), c.anchor()
                        start, end = min(pos, anchor), max(pos, anchor)
                        for i in range(start, end):
                            cur = self.textCursor()
                            cur.setPosition(i), cur.setPosition(i + 1, c.KeepAnchor)
                            cur.mergeCharFormat(fmt)
                    c.setPosition(c.position())
                    c.setCharFormat(oldfmt)

        else:
            error_dialog(self, _('Invalid URL'),
                         _('The url %r is invalid') % link, show=True)

    def ask_link(self):

        class Ask(QDialog):

            def accept(self):
                if self.treat_as_image.isChecked():
                    url = self.url.text()
                    if url.lower().split(':', 1)[0] in ('http', 'https'):
                        error_dialog(self, _('Remote images not supported'), _(
                            'You must download the image to your computer, URLs pointing'
                            ' to remote images are not supported.'), show=True)
                        return
                QDialog.accept(self)

        d = Ask(self)
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
            filetypes = []
            if d.treat_as_image.isChecked():
                filetypes = [(_('Images'), 'png jpeg jpg gif'.split())]
            files = choose_files(d, 'select link file', _('Choose file'), filetypes, select_only_single_file=True)
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
            link, name = unicode_type(d.url.text()).strip(), unicode_type(d.name.text()).strip()
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

    @property
    def html(self):
        raw = original_html = self.toHtml()
        check = self.toPlainText().strip()
        raw = xml_to_unicode(raw, strip_encoding_pats=True, resolve_entities=True)[0]
        raw = self.comments_pat.sub('', raw)
        if not check and '<img' not in raw.lower():
            return ''

        root = parse(raw, maybe_xhtml=False, sanitize_names=True)
        if root.xpath('//meta[@name="calibre-dont-sanitize"]'):
            # Bypass cleanup if special meta tag exists
            return original_html

        try:
            cleanup_qt_markup(root)
        except Exception:
            import traceback
            traceback.print_exc()
        elems = []
        for body in root.xpath('//body'):
            if body.text:
                elems.append(body.text)
            elems += [html.tostring(x, encoding='unicode') for x in body if
                x.tag not in ('script', 'style')]

        if len(elems) > 1:
            ans = '<div>%s</div>'%(u''.join(elems))
        else:
            ans = ''.join(elems)
            if not ans.startswith('<'):
                ans = '<p>%s</p>'%ans
        return xml_replace_entities(ans)

    @html.setter
    def html(self, val):
        self.setHtml(val)

    def set_base_url(self, qurl):
        self.base_url = qurl

    @pyqtSlot(int, 'QUrl', result='QVariant')
    def loadResource(self, rtype, qurl):
        if self.base_url:
            if qurl.isRelative():
                qurl = self.base_url.resolved(qurl)
            if qurl.isLocalFile():
                path = qurl.toLocalFile()
                try:
                    with lopen(path, 'rb') as f:
                        data = f.read()
                except EnvironmentError:
                    if path.rpartition('.')[-1].lower() in {'jpg', 'jpeg', 'gif', 'png', 'bmp', 'webp'}:
                        return QByteArray(bytearray.fromhex(
                                    '89504e470d0a1a0a0000000d49484452'
                                    '000000010000000108060000001f15c4'
                                    '890000000a49444154789c6300010000'
                                    '0500010d0a2db40000000049454e44ae'
                                    '426082'))
                else:
                    return QByteArray(data)

    def set_html(self, val, allow_undo=True):
        if not allow_undo or self.readonly:
            self.html = val
            return
        with self.editing_cursor() as c:
            c.movePosition(QTextCursor.Start, QTextCursor.MoveAnchor)
            c.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            c.removeSelectedText()
            c.insertHtml(val)

    def text(self):
        return self.textCursor().selectedText()

    def setText(self, text):
        with self.editing_cursor() as c:
            c.insertText(text)

    def contextMenuEvent(self, ev):
        menu = self.createStandardContextMenu()
        for action in menu.actions():
            parts = action.text().split('\t')
            if len(parts) == 2 and QKeySequence(QKeySequence.Paste).toString(QKeySequence.NativeText) in parts[-1]:
                menu.insertAction(action, self.action_paste_and_match_style)
                break
        else:
            menu.addAction(self.action_paste_and_match_style)
        st = self.text()
        m = QMenu(_('Fonts'))
        m.addAction(self.action_bold), m.addAction(self.action_italic), m.addAction(self.action_underline)
        menu.addMenu(m)

        if st and st.strip():
            self.create_change_case_menu(menu)
        parent = self._parent()
        if hasattr(parent, 'toolbars_visible'):
            vis = parent.toolbars_visible
            menu.addAction(_('%s toolbars') % (_('Hide') if vis else _('Show')), parent.toggle_toolbars)
        menu.addSeparator()
        menu.addAction(_('Smarten punctuation'), parent.smarten_punctuation)
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
        self.colors['comment']        = QColor(35, 110,  37)
        if is_dark_theme():
            from calibre.gui2.palette import dark_link_color
            self.colors['tag']            = QColor(186,  78, 188)
            self.colors['attrname']       = QColor(193,  119, 60)
            self.colors['attrval']        = dark_link_color
        else:
            self.colors['tag']            = QColor(136,  18, 128)
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
                    if text[pos:pos+3] == "-->":
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
                    if ch == '>':
                        state = State_Text
                        break
                self.setFormat(start, pos - start, self.colors['doctype'])

            # at '<' in e.g. "<span>foo</span>"
            elif state == State_TagStart:
                start = pos + 1
                while pos < len_:
                    ch = text[pos]
                    pos += 1
                    if ch == '>':
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
                    if ch == '>':
                        state = State_Text
                        break
                self.setFormat(start, pos - start, self.colors['tag'])

            # anywhere after tag name and before tag closing ('>')
            elif state == State_InsideTag:
                start = pos

                while pos < len_:
                    ch = text[pos]
                    pos += 1

                    if ch == '/':
                        continue

                    if ch == '>':
                        state = State_Text
                        self.setFormat(pos-1, 1, self.colors['tag'])
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

                    if ch == '=':
                        state = State_AttributeValue
                        break

                    if ch in ('>', '/'):
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
                    if ch == "'":
                        state = State_SingleQuote
                        self.setFormat(pos - 1, 1, self.colors['attrval'])
                        break

                    # handle opening double quote
                    if ch == '"':
                        state = State_DoubleQuote
                        self.setFormat(pos - 1, 1, self.colors['attrval'])
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
                        if ch in ('>', '/'):
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
                    if ch == "'":
                        break

                state = State_InsideTag

                self.setFormat(start, pos - start, self.colors['attrval'])

            # after the opening double quote in an attribute value
            elif state == State_DoubleQuote:
                start = pos

                while pos < len_:
                    ch = text[pos]
                    pos += 1
                    if ch == '"':
                        break

                state = State_InsideTag

                self.setFormat(start, pos - start, self.colors['attrval'])

            else:
                # State_Text and default
                while pos < len_:
                    ch = text[pos]
                    if ch == '<':
                        if text[pos:pos+4] == "<!--":
                            state = State_Comment
                        else:
                            if text[pos:pos+9].upper() == "<!DOCTYPE":
                                state = State_DocType
                            else:
                                state = State_TagStart
                        break
                    elif ch == '&':
                        start = pos
                        while pos < len_ and text[pos] != ';':
                            self.setFormat(start, pos - start,
                                    self.colors['entity'])
                            pos += 1

                    else:
                        pos += 1

        self.setCurrentBlockState(state)

# }}}


class Editor(QWidget):  # {{{

    toolbar_prefs_name = None
    data_changed = pyqtSignal()

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
        self.editor.data_changed.connect(self.data_changed)
        self.set_base_url = self.editor.set_base_url
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
        self.tabs.addTab(self.wyswyg, _('&Normal view'))
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
        self.toolbar2.addAction(self.editor.action_insert_hr)
        # }}}

        # toolbar3 {{{
        for x in ('bold', 'italic', 'underline', 'strikethrough'):
            ac = getattr(self.editor, 'action_'+x)
            self.toolbar3.addAction(ac)
            self.addAction(ac)
        self.toolbar3.addSeparator()

        for x in ('left', 'center', 'right', 'justified'):
            ac = getattr(self.editor, 'action_align_'+x)
            self.toolbar3.addAction(ac)
        self.toolbar3.addSeparator()
        self.toolbar3.addAction(self.editor.action_color)
        # }}}

        self.code_edit.textChanged.connect(self.code_dirtied)
        self.editor.data_changed.connect(self.wyswyg_dirtied)

    def set_minimum_height_for_editor(self, val):
        self.editor.setMinimumHeight(val)

    @property
    def html(self):
        self.tabs.setCurrentIndex(0)
        return self.editor.html

    @html.setter
    def html(self, v):
        self.editor.html = v

    def change_tab(self, index):
        # print 'reloading:', (index and self.wyswyg_dirty) or (not index and
        #        self.source_dirty)
        if index == 1:  # changing to code view
            if self.wyswyg_dirty:
                self.code_edit.setPlainText(self.editor.html)
                self.wyswyg_dirty = False
        elif index == 0:  # changing to wyswyg
            if self.source_dirty:
                self.editor.html = to_plain_text(self.code_edit)
                self.source_dirty = False

    @property
    def tab(self):
        return 'code' if self.tabs.currentWidget() is self.code_edit else 'wyswyg'

    @tab.setter
    def tab(self, val):
        self.tabs.setCurrentWidget(self.code_edit if val == 'code' else self.wyswyg)

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

    @property
    def toolbars_visible(self):
        return self.toolbar1.isVisible() or self.toolbar2.isVisible() or self.toolbar3.isVisible()

    @toolbars_visible.setter
    def toolbars_visible(self, val):
        getattr(self, ('show' if val else 'hide') + '_toolbars')()

    def set_readonly(self, what):
        self.editor.set_readonly(what)

    def hide_tabs(self):
        self.tabs.tabBar().setVisible(False)

    def smarten_punctuation(self):
        from calibre.ebooks.conversion.preprocess import smarten_punctuation
        html = self.html
        newhtml = smarten_punctuation(html)
        if html != newhtml:
            self.html = newhtml

# }}}


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    w = Editor()
    w.resize(800, 600)
    w.show()
    w.html = '''<h1>Test Heading</h1><blockquote>Test blockquote</blockquote><p><span style="background-color: rgb(0, 255, 255); ">He hadn't
    set <u>out</u> to have an <em>affair</em>, <span style="font-style:italic; background-color:red">
    much</span> less a <s>long-term</s>, <b>devoted</b> one.</span><p>hello'''
    w.html = '<div><p id="moo">Testing <em>a</em> link.</p><p>\xa0</p><p>ss</p></div>'
    app.exec_()
    # print w.html
