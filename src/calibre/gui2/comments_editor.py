#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid at kovidgoyal.net>


import os
import re
import sys
import weakref
from collections import defaultdict
from contextlib import contextmanager
from functools import partial
from html5_parser import parse
from lxml import html
from qt.core import (
    QAction, QApplication, QBrush, QByteArray, QCheckBox, QColor, QColorDialog, QDialog,
    QDialogButtonBox, QFont, QFontInfo, QFontMetrics, QFormLayout, QHBoxLayout, QIcon,
    QKeySequence, QLabel, QLineEdit, QMenu, QPalette, QPlainTextEdit, QPointF,
    QPushButton, QSize, QSpinBox, QSyntaxHighlighter, Qt, QTabWidget, QTextBlockFormat,
    QTextCharFormat, QTextCursor, QTextDocument, QTextEdit, QTextFormat,
    QTextFrameFormat, QTextImageFormat, QTextListFormat, QTimer, QToolButton, QUrl,
    QVBoxLayout, QWidget, pyqtSignal, pyqtSlot,
)
from threading import Thread

from calibre import browser, fit_image, xml_replace_entities
from calibre.db.constants import DATA_DIR_NAME
from calibre.ebooks.chardet import xml_to_unicode
from calibre.gui2 import (
    NO_URL_FORMATTING, FunctionDispatcher, choose_dir, choose_files, error_dialog,
    gprefs, is_dark_theme, local_path_for_resource, question_dialog, safe_open_url,
)
from calibre.gui2.book_details import resolved_css
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.gui2.flow_toolbar import create_flow_toolbar
from calibre.gui2.widgets import LineEditECM
from calibre.gui2.widgets2 import to_plain_text
from calibre.startup import connect_lambda
from calibre.utils.cleantext import clean_xml_chars
from calibre.utils.config import tweaks
from calibre.utils.filenames import make_long_path_useable
from calibre.utils.imghdr import what
from polyglot.builtins import iteritems, itervalues

# Cleanup Qt markup {{{

OBJECT_REPLACEMENT_CHAR = '\ufffc'


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
        if child.tail and child.tail.strip():
            has_text = True
        style = style_map[child]
        child_styles.append(style)
        if not child.text and len(child) == 0:
            continue
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
                    style.pop(k, None)


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
    if style.get('font-weight') in ('0', '600', '700', 'bold'):
        del style['font-weight']


def use_implicit_styling_for_span(span, style):
    is_italic = style.get('font-style') == 'italic'
    is_bold = style.get('font-weight') in ('600', '700', 'bold')
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
        tags = root.xpath(f'//a[@href="{href}"]')
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
    convert_anchors_to_ids(root)
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
    for img in root.xpath('//img[@style]'):
        s = style_map.get(img)
        if s:
            if s == {'float': 'left'}:
                s['margin-right'] = '0.5em'
            elif s == {'float': 'right'}:
                s['margin-left'] = '0.5em'
    for style in itervalues(style_map):
        filter_qt_styles(style)
        fw = style.get('font-weight')
        if fw in ('600', '700'):
            style['font-weight'] = 'bold'
    for tag, style in iteritems(style_map):
        if style:
            tag.set('style', '; '.join(f'{k}: {v}' for k, v in iteritems(style)))
        else:
            tag.attrib.pop('style', None)
    for span in root.xpath('//span[not(@style)]'):
        lift(span)

    merge_contiguous_links(root)
# }}}


def fix_html(original_html, original_txt, remove_comments=True, callback=None):
    raw = original_html
    raw = xml_to_unicode(raw, strip_encoding_pats=True, resolve_entities=True)[0]
    if remove_comments:
        comments_pat = re.compile(r'<!--.*?-->', re.DOTALL)
        raw = comments_pat.sub('', raw)
    if not original_txt and '<img' not in raw.lower():
        return ''

    try:
        root = parse(raw, maybe_xhtml=False, sanitize_names=True)
    except Exception:
        root = parse(clean_xml_chars(raw), maybe_xhtml=False, sanitize_names=True)
    if root.xpath('//meta[@name="calibre-dont-sanitize"]'):
        # Bypass cleanup if special meta tag exists
        return original_html

    try:
        cleanup_qt_markup(root)
    except Exception:
        import traceback
        traceback.print_exc()
    if callback is not None:
        callback(root, original_txt)
    elems = []
    for body in root.xpath('//body'):
        if body.text:
            elems.append(body.text)
        elems += [html.tostring(x, encoding='unicode') for x in body if
            x.tag not in ('script', 'style')]

    if len(elems) > 1:
        ans = '<div>%s</div>'%(''.join(elems))
    else:
        ans = ''.join(elems)
        if not ans.startswith('<'):
            ans = '<p>%s</p>'%ans
    return xml_replace_entities(ans)

class EditorWidget(QTextEdit, LineEditECM):  # {{{

    data_changed = pyqtSignal()
    insert_images_separately = False
    can_store_images = False

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
        self.document().setDefaultStyleSheet(resolved_css() + '\n\nli { margin-top: 0.5ex; margin-bottom: 0.5ex; }')
        font = self.font()
        f = QFontInfo(font)
        delta = tweaks['change_book_details_font_size_by'] + 1
        if delta:
            font.setPixelSize(int(f.pixelSize() + delta))
            self.setFont(font)
        f = QFontMetrics(self.font())
        self.em_size = f.horizontalAdvance('m')
        self.base_url = None
        self._parent = weakref.ref(parent)
        self.shortcut_map = {}

        def r(name, icon, text, checkable=False, shortcut=None):
            ac = QAction(QIcon.ic(icon + '.png'), text, self)
            ac.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            if checkable:
                ac.setCheckable(checkable)
            setattr(self, 'action_'+name, ac)
            ac.triggered.connect(getattr(self, 'do_' + name))
            if shortcut is not None:
                self.shortcut_map[shortcut] = ac
                sc = shortcut if isinstance(shortcut, QKeySequence) else QKeySequence(shortcut)
                ac.setShortcut(sc)
                ac.setToolTip(text + f' [{sc.toString(QKeySequence.SequenceFormat.NativeText)}]')
            self.addAction(ac)

        r('bold', 'format-text-bold', _('Bold'), True, QKeySequence.StandardKey.Bold)
        r('italic', 'format-text-italic', _('Italic'), True, QKeySequence.StandardKey.Italic)
        r('underline', 'format-text-underline', _('Underline'), True, QKeySequence.StandardKey.Underline)
        r('strikethrough', 'format-text-strikethrough', _('Strikethrough'), True)
        r('superscript', 'format-text-superscript', _('Superscript'), True)
        r('subscript', 'format-text-subscript', _('Subscript'), True)
        r('ordered_list', 'format-list-ordered', _('Ordered list'), True)
        r('unordered_list', 'format-list-unordered', _('Unordered list'), True)

        r('align_left', 'format-justify-left', _('Align left'), True)
        r('align_center', 'format-justify-center', _('Align center'), True)
        r('align_right', 'format-justify-right', _('Align right'), True)
        r('align_justified', 'format-justify-fill', _('Align justified'), True)
        r('undo', 'edit-undo', _('Undo'), shortcut=QKeySequence.StandardKey.Undo)
        r('redo', 'edit-redo', _('Redo'), shortcut=QKeySequence.StandardKey.Redo)
        r('remove_format', 'edit-clear', _('Remove formatting'))
        r('copy', 'edit-copy', _('Copy'), shortcut=QKeySequence.StandardKey.Copy)
        r('paste', 'edit-paste', _('Paste'), shortcut=QKeySequence.StandardKey.Paste)
        r('paste_and_match_style', 'edit-paste', _('Paste and match style'), shortcut=QKeySequence('ctrl+shift+v', QKeySequence.SequenceFormat.PortableText))
        r('cut', 'edit-cut', _('Cut'), shortcut=QKeySequence.StandardKey.Cut)
        r('indent', 'format-indent-more', _('Increase indentation'))
        r('outdent', 'format-indent-less', _('Decrease indentation'))
        r('select_all', 'edit-select-all', _('Select all'), shortcut=QKeySequence.StandardKey.SelectAll)

        r('color', 'format-text-color', _('Foreground color'))
        r('background', 'format-fill-color', _('Background color'))
        r('insert_link', 'insert-link', _('Insert link') if self.insert_images_separately else _('Insert link or image'),
          shortcut=QKeySequence('Ctrl+l', QKeySequence.SequenceFormat.PortableText))
        r('insert_image', 'view-image', _('Insert image'), shortcut=QKeySequence('Ctrl+p', QKeySequence.SequenceFormat.PortableText))
        r('insert_hr', 'format-text-hr', _('Insert separator'),)
        r('clear', 'trash', _('Clear'))

        self.action_block_style = QAction(QIcon.ic('format-text-heading.png'),
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

    def update_clipboard_actions(self, copy_available):
        self.action_copy.setEnabled(copy_available)
        self.action_cut.setEnabled(copy_available)

    def update_selection_based_actions(self):
        pass

    def update_cursor_position_actions(self):
        c = self.textCursor()
        tcf = c.charFormat()
        ls = c.currentList()
        self.action_ordered_list.setChecked(ls is not None and ls.format().style() == QTextListFormat.Style.ListDecimal)
        self.action_unordered_list.setChecked(ls is not None and ls.format().style() == QTextListFormat.Style.ListDisc)
        vert = tcf.verticalAlignment()
        self.action_superscript.setChecked(vert == QTextCharFormat.VerticalAlignment.AlignSuperScript)
        self.action_subscript.setChecked(vert == QTextCharFormat.VerticalAlignment.AlignSubScript)
        self.action_bold.setChecked(tcf.fontWeight() == QFont.Weight.Bold)
        self.action_italic.setChecked(tcf.fontItalic())
        self.action_underline.setChecked(tcf.fontUnderline())
        self.action_strikethrough.setChecked(tcf.fontStrikeOut())
        bf = c.blockFormat()
        a = bf.alignment()
        self.action_align_left.setChecked(a == Qt.AlignmentFlag.AlignLeft)
        self.action_align_right.setChecked(a == Qt.AlignmentFlag.AlignRight)
        self.action_align_center.setChecked(a == Qt.AlignmentFlag.AlignHCenter)
        self.action_align_justified.setChecked(a == Qt.AlignmentFlag.AlignJustify)
        lvl = bf.headingLevel()
        name = 'p'
        if lvl == 0:
            if bf.leftMargin() == bf.rightMargin() and bf.leftMargin() > 0:
                name = 'blockquote'
        else:
            name = f'h{lvl}'
        for ac in self.block_style_actions:
            ac.setChecked(ac.block_name == name)

    def set_readonly(self, what):
        self.readonly = what

    def focus_self(self):
        self.setFocus(Qt.FocusReason.TabFocusReason)

    def do_clear(self, *args):
        c = self.textCursor()
        c.beginEditBlock()
        c.movePosition(QTextCursor.MoveOperation.Start, QTextCursor.MoveMode.MoveAnchor)
        c.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        c.removeSelectedText()
        c.endEditBlock()
        self.focus_self()
    clear_text = do_clear

    def do_bold(self):
        with self.editing_cursor() as c:
            fmt = QTextCharFormat()
            fmt.setFontWeight(
                QFont.Weight.Bold if c.charFormat().fontWeight() != QFont.Weight.Bold else QFont.Weight.Normal)
            c.mergeCharFormat(fmt)
        self.update_cursor_position_actions()

    def do_italic(self):
        with self.editing_cursor() as c:
            fmt = QTextCharFormat()
            fmt.setFontItalic(not c.charFormat().fontItalic())
            c.mergeCharFormat(fmt)
        self.update_cursor_position_actions()

    def do_underline(self):
        with self.editing_cursor() as c:
            fmt = QTextCharFormat()
            fmt.setFontUnderline(not c.charFormat().fontUnderline())
            c.mergeCharFormat(fmt)
        self.update_cursor_position_actions()

    def do_strikethrough(self):
        with self.editing_cursor() as c:
            fmt = QTextCharFormat()
            fmt.setFontStrikeOut(not c.charFormat().fontStrikeOut())
            c.mergeCharFormat(fmt)
        self.update_cursor_position_actions()

    def do_vertical_align(self, which):
        with self.editing_cursor() as c:
            fmt = QTextCharFormat()
            fmt.setVerticalAlignment(which)
            c.mergeCharFormat(fmt)
        self.update_cursor_position_actions()

    def do_superscript(self):
        self.do_vertical_align(QTextCharFormat.VerticalAlignment.AlignSuperScript)

    def do_subscript(self):
        self.do_vertical_align(QTextCharFormat.VerticalAlignment.AlignSubScript)

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
        self.update_cursor_position_actions()

    def do_ordered_list(self):
        self.do_list(QTextListFormat.Style.ListDecimal)

    def do_unordered_list(self):
        self.do_list(QTextListFormat.Style.ListDisc)

    def do_alignment(self, which):
        with self.editing_cursor() as c:
            c = self.textCursor()
            fmt = QTextBlockFormat()
            fmt.setAlignment(which)
            c.mergeBlockFormat(fmt)
        self.update_cursor_position_actions()

    def do_align_left(self):
        self.do_alignment(Qt.AlignmentFlag.AlignLeft)

    def do_align_center(self):
        self.do_alignment(Qt.AlignmentFlag.AlignHCenter)

    def do_align_right(self):
        self.do_alignment(Qt.AlignmentFlag.AlignRight)

    def do_align_justified(self):
        self.do_alignment(Qt.AlignmentFlag.AlignJustify)

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
        self.update_cursor_position_actions()

    def keyPressEvent(self, ev):
        for sc, ac in self.shortcut_map.items():
            if isinstance(sc, QKeySequence.StandardKey) and ev.matches(sc):
                ac.trigger()
                return
        return super().keyPressEvent(ev)

    def do_copy(self):
        self.copy()
        self.focus_self()

    def do_paste(self):
        images_before = set()
        for fmt in self.document().allFormats():
            if fmt.isImageFormat():
                images_before.add(fmt.toImageFormat().name())
        self.paste()
        if self.can_store_images:
            added = set()
            for fmt in self.document().allFormats():
                if fmt.isImageFormat():
                    name = fmt.toImageFormat().name()
                    if name not in images_before and name.partition(':')[0] in ('https', 'http'):
                        added.add(name)
            if added and question_dialog(
                self, _('Download images'), _(
                    'Download all remote images in the pasted content?')):
                self.download_images(added)
        self.focus_self()

    def download_images(self, urls):
        from calibre.web import get_download_filename_from_response
        br = browser()
        d = self.document()
        c = self.textCursor()
        c.setPosition(0)
        pos_map = {}
        while True:
            c = d.find(OBJECT_REPLACEMENT_CHAR, c, QTextDocument.FindFlag.FindCaseSensitively)
            if c.isNull():
                break
            fmt = c.charFormat()
            if fmt.isImageFormat():
                name = fmt.toImageFormat().name()
                if name in urls:
                    pos_map[name] = c.position()

        pd = ProgressDialog(title=_('Downloading images...'), min=0, max=0, parent=self)
        pd.canceled_signal.connect(pd.accept)
        data_map = {}
        error_map = {}
        set_msg = FunctionDispatcher(pd.set_msg, parent=pd)
        accept = FunctionDispatcher(pd.accept, parent=pd)

        def do_download():
            for url, pos in pos_map.items():
                if pd.canceled:
                    return
                set_msg(_('Downloading {}...').format(url))
                try:
                    res = br.open_novisit(url, timeout=30)
                    fname = get_download_filename_from_response(res)
                    data = res.read()
                except Exception as err:
                    error_map[url] = err
                else:
                    data_map[url] = fname, data
            accept()
        Thread(target=do_download, daemon=True).start()
        pd.exec()
        if pd.canceled:
            return

        for url, pos in pos_map.items():
            fname, data = data_map[url]
            newname = self.commit_downloaded_image(data, fname)
            c = self.textCursor()
            c.setPosition(pos)
            alignment = QTextFrameFormat.Position.InFlow
            f = self.frame_for_cursor(c)
            if f is not None:
                alignment = f.frameFormat().position()
            fmt = c.charFormat()
            i = fmt.toImageFormat()
            i.setName(newname)
            c.deletePreviousChar()
            c.insertImage(i, alignment)
        if error_map:
            m = '\n'.join(
                _('Could not download {0} with error:').format(url) + '\n\t' + str(err) + '\n\n' for url, err in error_map.items())
            error_dialog(self, _('Failed to download some images'), _(
                'Some images could not be downloaded, click "Show details" to see which ones'), det_msg=m, show=True)

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
        self.update_cursor_position_actions()

    def do_indent(self):
        self.indent_block()

    def do_outdent(self):
        self.indent_block(-1)

    def do_select_all(self):
        with self.editing_cursor() as c:
            c.movePosition(QTextCursor.MoveOperation.Start, QTextCursor.MoveMode.MoveAnchor)
            c.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)

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
            wt = QFont.Weight.Bold if lvl else QFont.Weight.Normal
            adjust = (0, 3, 2, 1, 0, -1, -1)[lvl]
            pos = None
            if not c.hasSelection():
                pos = c.position()
                c.movePosition(QTextCursor.MoveOperation.StartOfBlock, QTextCursor.MoveMode.MoveAnchor)
                c.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
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
            bcf.setProperty(QTextFormat.Property.FontSizeAdjustment, adjust)
            cf.setProperty(QTextFormat.Property.FontSizeAdjustment, adjust)
            bcf.setFontWeight(wt)
            cf.setFontWeight(wt)
            c.setBlockCharFormat(bcf)
            c.mergeCharFormat(cf)
            c.mergeBlockFormat(bf)
            if pos is not None:
                c.setPosition(pos)
        self.update_cursor_position_actions()

    def do_color(self):
        col = QColorDialog.getColor(Qt.GlobalColor.black, self,
                _('Choose foreground color'), QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if col.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(QBrush(col))
            with self.editing_cursor() as c:
                c.mergeCharFormat(fmt)

    def do_background(self):
        col = QColorDialog.getColor(Qt.GlobalColor.white, self,
                _('Choose background color'), QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if col.isValid():
            fmt = QTextCharFormat()
            fmt.setBackground(QBrush(col))
            with self.editing_cursor() as c:
                c.mergeCharFormat(fmt)

    def do_insert_hr(self, *args):
        with self.editing_cursor() as c:
            c.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.MoveAnchor)
            c.insertHtml('<hr>')

    def do_insert_image(self):
        from calibre.gui2 import choose_images
        files = choose_images(self, 'choose-image-for-comments-editor', _('Choose image'), formats='png jpeg jpg gif svg webp'.split())
        if files:
            self.focus_self()
            with self.editing_cursor() as c:
                c.insertImage(files[0])

    def do_insert_link(self, *args):
        link, name, is_image = self.ask_link()
        if not link:
            return
        url = self.parse_link(link)
        if url.isValid():
            if url.isLocalFile() and not os.path.isabs(url.toLocalFile()):
                url = url.toLocalFile()
            else:
                url = url.toString(NO_URL_FORMATTING)
            self.focus_self()
            with self.editing_cursor() as c:
                if is_image:
                    c.insertImage(url)
                else:
                    oldfmt = QTextCharFormat(c.charFormat())
                    fmt = QTextCharFormat()
                    fmt.setAnchor(True)
                    fmt.setAnchorHref(url)
                    fmt.setForeground(QBrush(self.palette().color(QPalette.ColorRole.Link)))
                    if name or not c.hasSelection():
                        c.mergeCharFormat(fmt)
                        c.insertText(name or url)
                    else:
                        pos, anchor = c.position(), c.anchor()
                        start, end = min(pos, anchor), max(pos, anchor)
                        for i in range(start, end):
                            cur = self.textCursor()
                            cur.setPosition(i), cur.setPosition(i + 1, QTextCursor.MoveMode.KeepAnchor)
                            cur.mergeCharFormat(fmt)
                    c.setPosition(c.position())
                    c.setCharFormat(oldfmt)

        else:
            error_dialog(self, _('Invalid URL'),
                         _('The URL %r is invalid') % link, show=True)

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
        l.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        d.setLayout(l)
        d.url = QLineEdit(d)
        d.name = QLineEdit(d)
        d.treat_as_image = QCheckBox(d)
        d.setMinimumWidth(600)
        d.bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        d.br = b = QPushButton(_('&File'))
        base = os.path.dirname(self.base_url.toLocalFile()) if self.base_url else os.getcwd()
        data_path = os.path.join(base, DATA_DIR_NAME)
        if self.base_url:
            os.makedirs(data_path, exist_ok=True)

        def cf(data_dir=False):
            filetypes = []
            if d.treat_as_image.isChecked():
                filetypes = [(_('Images'), 'png jpeg jpg gif'.split())]
            if data_dir:
                files = choose_files(
                    d, 'select link file', _('Choose file'), filetypes, select_only_single_file=True, no_save_dir=True,
                    default_dir=data_path)
            else:
                files = choose_files(d, 'select link file', _('Choose file'), filetypes, select_only_single_file=True)
            if files:
                path = files[0]
                d.url.setText(path)
                if path and os.path.exists(path):
                    with open(path, 'rb') as f:
                        q = what(f)
                    is_image = q in {'jpeg', 'png', 'gif', 'webp'}
                    d.treat_as_image.setChecked(is_image)
                if data_dir:
                    path = os.path.relpath(path, base).replace(os.sep, '/')
                    d.url.setText(path)
        b.clicked.connect(lambda: cf())
        d.brdf = b = QPushButton(_('&Data file'))
        b.clicked.connect(lambda: cf(True))
        b.setToolTip(_('A relative link to a data file associated with this book'))
        if not os.path.exists(data_path):
            b.setVisible(False)
        d.brd = b = QPushButton(_('F&older'))
        def cd():
            path = choose_dir(d, 'select link folder', _('Choose folder'))
            if path:
                d.url.setText(path)
        b.clicked.connect(cd)

        d.la = la = QLabel(_(
            'Enter a URL. If you check the "Treat the URL as an image" box '
            'then the URL will be added as an image reference instead of as '
            'a link. You can also choose to create a link to a file on '
            'your computer. '
            'Note that if you create a link to a file on your computer, it '
            'will stop working if the file is moved.'))
        la.setWordWrap(True)
        la.setStyleSheet('QLabel { margin-bottom: 1.5ex }')
        l.setWidget(0, QFormLayout.ItemRole.SpanningRole, la)
        l.addRow(_('Enter &URL:'), d.url)
        l.addRow(_('Treat the URL as an &image'), d.treat_as_image)
        l.addRow(_('Enter &name (optional):'), d.name)
        h = QHBoxLayout()
        h.addWidget(d.br), h.addWidget(d.brdf), h.addWidget(d.brd)
        l.addRow(_('Choose a file on your computer:'), h)
        l.addRow(d.bb)
        d.bb.accepted.connect(d.accept)
        d.bb.rejected.connect(d.reject)
        d.resize(d.sizeHint())
        link, name, is_image = None, None, False
        if d.exec() == QDialog.DialogCode.Accepted:
            link, name = str(d.url.text()).strip(), str(d.name.text()).strip()
            is_image = d.treat_as_image.isChecked()
        return link, name, is_image

    def parse_link(self, link):
        link = link.strip()
        if link and os.path.exists(link):
            return QUrl.fromLocalFile(link)
        has_schema = re.match(r'^[a-zA-Z]+:', link)
        if has_schema is not None:
            url = QUrl(link, QUrl.ParsingMode.TolerantMode)
            if url.isValid():
                return url
        else:
            if self.base_url:
                base = os.path.dirname(self.base_url.toLocalFile())
            else:
                base = os.getcwd()
            candidate = os.path.join(base, link)
            if os.path.exists(candidate):
                return QUrl.fromLocalFile(link)
        if os.path.exists(link):
            return QUrl.fromLocalFile(link)

        if has_schema is None:
            first, _, rest = link.partition('.')
            prefix = 'http'
            if first == 'ftp':
                prefix = 'ftp'
            url = QUrl(prefix +'://'+link, QUrl.ParsingMode.TolerantMode)
            if url.isValid():
                return url

        return QUrl(link, QUrl.ParsingMode.TolerantMode)

    def sizeHint(self):
        return QSize(150, 150)

    @property
    def html(self):
        return fix_html(self.toHtml(), self.toPlainText().strip(), callback=self.get_html_callback)

    def get_html_callback(self, root, text):
        pass

    @html.setter
    def html(self, val):
        self.setHtml(val)

    def set_base_url(self, qurl):
        self.base_url = qurl

    @pyqtSlot(int, 'QUrl', result='QVariant')
    def loadResource(self, rtype, qurl):
        path = local_path_for_resource(qurl, base_qurl=self.base_url)
        if path:
            data = None
            try:
                with open(make_long_path_useable(path), 'rb') as f:
                    data = f.read()
            except OSError:
                if path.rpartition('.')[-1].lower() in {'jpg', 'jpeg', 'gif', 'png', 'bmp', 'webp'}:
                    data = bytearray.fromhex(
                                '89504e470d0a1a0a0000000d49484452'
                                '000000010000000108060000001f15c4'
                                '890000000a49444154789c6300010000'
                                '0500010d0a2db40000000049454e44ae'
                                '426082')
            if data is not None:
                r = QByteArray(data)
                self.document().addResource(rtype, qurl, r)
                return r

    def set_html(self, val, allow_undo=True):
        if not allow_undo or self.readonly:
            self.html = val
            return
        with self.editing_cursor() as c:
            c.movePosition(QTextCursor.MoveOperation.Start, QTextCursor.MoveMode.MoveAnchor)
            c.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
            c.removeSelectedText()
            c.insertHtml(val)

    def text(self):
        return self.textCursor().selectedText()
    selectedText = text

    def setText(self, text):
        with self.editing_cursor() as c:
            c.insertText(text)
    insert = setText

    def hasSelectedText(self):
        c = self.textCursor()
        return c.hasSelection()

    def createMimeDataFromSelection(self):
        ans = super().createMimeDataFromSelection()
        html, txt = ans.html(), ans.text()
        html = fix_html(html, txt, remove_comments=False)
        # Qt has a bug where copying from the start of a paragraph does not
        # include the paragraph definition in the fragment. Try to fix that
        # by moving the StartFragment comment to before the paragraph when
        # the selection starts at the start of a block
        c = self.textCursor()
        c2 = QTextCursor(c)
        c2.setPosition(c.selectionStart())
        if c2.atBlockStart():
            html = re.sub(r'(<p.*?>)(<!--StartFragment-->)', r'\2\1', html, count=1)
        ans.setHtml(html)
        return ans

    def remove_image_at(self, cursor_pos):
        c = self.textCursor()
        c.clearSelection()
        c.setPosition(cursor_pos)
        fmt = c.charFormat()
        if fmt.isImageFormat():
            c.deletePreviousChar()

    def resize_image_at(self, cursor_pos):
        c = self.textCursor()
        c.clearSelection()
        c.setPosition(cursor_pos)
        c.movePosition(QTextCursor.MoveOperation.PreviousCharacter, QTextCursor.MoveMode.KeepAnchor)
        fmt = c.charFormat()
        if not fmt.isImageFormat():
            return
        fmt = fmt.toImageFormat()
        from calibre.utils.img import image_from_data
        img = image_from_data(self.loadResource(QTextDocument.ResourceType.ImageResource, QUrl(fmt.name())))
        w, h = int(fmt.width()), int(fmt.height())
        d = QDialog(self)
        l = QVBoxLayout(d)
        la = QLabel(_('Shrink image to fit within:'))
        h = QHBoxLayout()
        l.addLayout(h)
        la = QLabel(_('&Width:'))
        h.addWidget(la)
        d.width = w = QSpinBox(self)
        w.setRange(0, 10000), w.setSuffix(' px')
        w.setValue(int(fmt.width()))
        h.addWidget(w), la.setBuddy(w)
        w.setSpecialValueText(' ')
        la = QLabel(_('&Height:'))
        h.addWidget(la)
        d.height = w = QSpinBox(self)
        w.setRange(0, 10000), w.setSuffix(' px')
        w.setValue(int(fmt.height()))
        h.addWidget(w), la.setBuddy(w)
        w.setSpecialValueText(' ')
        h.addStretch(10)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(d.accept), bb.rejected.connect(d.reject)
        d.setWindowTitle(_('Enter new size for image'))
        l.addWidget(bb)
        d.resize(d.sizeHint())

        if d.exec() == QDialog.DialogCode.Accepted:
            page_width, page_height = (d.width.value() or sys.maxsize), (d.height.value() or sys.maxsize)
            w, h = int(img.width()), int(img.height())
            resized, nw, nh = fit_image(w, h, page_width, page_height)
            if resized:
                fmt.setWidth(nw), fmt.setHeight(nh)
            else:
                f = QTextImageFormat()
                f.setName(fmt.name())
                fmt = f
            c.setCharFormat(fmt)

    def align_image_at(self, cursor_pos, alignment):
        c = self.textCursor()
        c.clearSelection()
        c.setPosition(cursor_pos)
        fmt = c.charFormat()
        if fmt.isImageFormat() and c.currentFrame():
            f = self.frame_for_cursor(c)
            if f is not None:
                ff = f.frameFormat()
                ff.setPosition(alignment)
                f.setFrameFormat(ff)
                self.document().markContentsDirty(cursor_pos-2, 5)
            else:
                c.deleteChar()
                c.insertImage(fmt.toImageFormat(), alignment)

    def first_image_replacement_char_position_for(self, image_name):
        d = self.document()
        c = self.textCursor()
        c.setPosition(0)
        while True:
            c = d.find(OBJECT_REPLACEMENT_CHAR, c, QTextDocument.FindFlag.FindCaseSensitively)
            if c.isNull():
                break
            fmt = c.charFormat()
            if fmt.isImageFormat() and fmt.toImageFormat().name() == image_name:
                return c.position()
        return -1

    def frame_for_cursor(self, c):
        q = c.position()
        for cf in c.currentFrame().childFrames():
            a, b = cf.firstPosition(), cf.lastPosition()
            a, b = min(a, b), max(a, b)
            if a <= q <= b:
                return cf

    def open_link(self, link: str) -> None:
        qurl = QUrl(link, QUrl.ParsingMode.TolerantMode)
        if qurl.isRelative() and self.base_url:
            qurl = QUrl.fromLocalFile(os.path.join(os.path.dirname(self.base_url.toLocalFile()), qurl.path()))
        safe_open_url(qurl)

    def contextMenuEvent(self, ev):
        menu = QMenu(self)
        img_name = self.document().documentLayout().imageAt(QPointF(ev.pos()))
        if img_name:
            pos = self.first_image_replacement_char_position_for(img_name)
            if pos > -1:
                c = self.textCursor()
                c.clearSelection()
                c.setPosition(pos)
                pos = QTextFrameFormat.Position.InFlow
                ff = self.frame_for_cursor(c)
                if ff is not None:
                    pos = ff.frameFormat().position()
                align_menu = menu.addMenu(QIcon.ic('view-image.png'), _('Image...'))
                def a(text, epos):
                    ac = align_menu.addAction(text)
                    ac.setCheckable(True)
                    ac.triggered.connect(partial(self.align_image_at, c.position(), epos))
                    if pos == epos:
                        ac.setChecked(True)
                cs = align_menu.addAction(QIcon.ic('resize.png'), _('Change size'))
                cs.triggered.connect(partial(self.resize_image_at, c.position()))
                align_menu.addSeparator()
                a(_('Float to the left'), QTextFrameFormat.Position.FloatLeft)
                a(_('Inline with text'), QTextFrameFormat.Position.InFlow)
                a(_('Float to the right'), QTextFrameFormat.Position.FloatRight)
                align_menu.addSeparator()
                align_menu.addAction(QIcon.ic('trash.png'), _('Remove this image')).triggered.connect(partial(self.remove_image_at, c.position()))
        link_name = self.document().documentLayout().anchorAt(QPointF(ev.pos()))
        if link_name:
            menu.addAction(QIcon.ic('insert-link.png'), _('Open link'), partial(self.open_link, link_name))
        for ac in 'undo redo -- cut copy paste paste_and_match_style -- select_all'.split():
            if ac == '--':
                menu.addSeparator()
            else:
                ac = getattr(self, 'action_' + ac)
                menu.addAction(ac)
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
        am = QMenu(_('Advanced'))
        menu.addMenu(am)
        am.addAction(self.action_block_style)
        am.addAction(self.action_insert_link)
        if self.insert_images_separately:
            am.addAction(self.action_insert_image)
        am.addAction(self.action_background)
        am.addAction(self.action_color)
        menu.addAction(_('Smarten punctuation'), parent.smarten_punctuation)
        menu.exec(ev.globalPos())

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
    editor_class = EditorWidget

    def __init__(self, parent=None, one_line_toolbar=False, toolbar_prefs_name=None):
        QWidget.__init__(self, parent)
        self.toolbar_prefs_name = toolbar_prefs_name or self.toolbar_prefs_name
        self.toolbar = create_flow_toolbar(self, restrict_to_single_line=one_line_toolbar, icon_size=18)
        self.editor = self.editor_class(self)
        self.editor.data_changed.connect(self.data_changed)
        self.set_base_url = self.editor.set_base_url
        self.set_html = self.editor.set_html
        self.tabs = QTabWidget(self)
        self.tabs.setTabPosition(QTabWidget.TabPosition.South)
        self.wyswyg = QWidget(self.tabs)
        self.code_edit = QPlainTextEdit(self.tabs)
        self.code_edit.setTabChangesFocus(True)
        self.source_dirty = False
        self.wyswyg_dirty = True

        self._layout = QVBoxLayout(self)
        self.wyswyg.layout = l = QVBoxLayout(self.wyswyg)
        self.setLayout(self._layout)
        l.setContentsMargins(0, 0, 0, 0)

        l.addWidget(self.toolbar)
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

        self.toolbar.add_action(self.editor.action_undo)
        self.toolbar.add_action(self.editor.action_redo)
        self.toolbar.add_action(self.editor.action_select_all)
        self.toolbar.add_action(self.editor.action_remove_format)
        self.toolbar.add_action(self.editor.action_clear)
        self.toolbar.add_separator()

        for x in ('copy', 'cut', 'paste'):
            ac = getattr(self.editor, 'action_'+x)
            self.toolbar.add_action(ac)

        self.toolbar.add_separator()
        self.toolbar.add_action(self.editor.action_background)
        self.toolbar.add_action(self.editor.action_color)
        self.toolbar.add_separator()

        for x in ('', 'un'):
            ac = getattr(self.editor, 'action_%sordered_list'%x)
            self.toolbar.add_action(ac)
        self.toolbar.add_separator()
        for x in ('superscript', 'subscript', 'indent', 'outdent'):
            self.toolbar.add_action(getattr(self.editor, 'action_' + x))
            if x in ('subscript', 'outdent'):
                self.toolbar.add_separator()

        self.toolbar.add_action(self.editor.action_block_style, popup_mode=QToolButton.ToolButtonPopupMode.InstantPopup)
        self.toolbar.add_action(self.editor.action_insert_link)
        if self.editor.insert_images_separately:
            self.toolbar.add_action(self.editor.action_insert_image)
        self.toolbar.add_action(self.editor.action_insert_hr)
        self.toolbar.add_separator()

        for x in ('bold', 'italic', 'underline', 'strikethrough'):
            ac = getattr(self.editor, 'action_'+x)
            self.toolbar.add_action(ac)
            self.addAction(ac)
        self.toolbar.add_separator()

        for x in ('left', 'center', 'right', 'justified'):
            ac = getattr(self.editor, 'action_align_'+x)
            self.toolbar.add_action(ac)
        self.toolbar.add_separator()
        QTimer.singleShot(0, self.toolbar.updateGeometry)

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
        self.toolbar.setVisible(False)

    def show_toolbars(self):
        self.toolbar.setVisible(True)
        QTimer.singleShot(0, self.toolbar.updateGeometry)

    def toggle_toolbars(self):
        visible = self.toolbars_visible
        getattr(self, ('hide' if visible else 'show') + '_toolbars')()
        if self.toolbar_prefs_name is not None:
            gprefs.set(self.toolbar_prefs_name, visible)

    @property
    def toolbars_visible(self):
        return self.toolbar.isVisible()

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
    w = Editor(one_line_toolbar=False)
    w.set_base_url(QUrl.fromLocalFile(os.getcwd()))
    w.resize(800, 600)
    w.setWindowFlag(Qt.WindowType.Dialog)
    w.show()
    w.html = '''<h1>Test Heading</h1><blockquote>Test blockquote</blockquote><p><span style="background-color: rgb(0, 255, 255); ">He hadn't
    set <u>out</u> to have an <em>affair</em>, <span style="font-style:italic; background-color:red">
    much</span> less a <s>long-term</s>, <b>devoted</b> one.</span><p>hello'''
    w.html = '<div><p id="moo" align="justify">Testing <em>a</em> link.</p><p align="justify">\xa0</p><p align="justify">ss</p></div>'
    i = 'file:///home/kovid/work/calibre/resources/images/'
    w.html = f'<p>Testing <img src="{i}/donate.png"> img and another <img src="{i}/lt.png">file</p>'
    app.exec()
    # print w.html
