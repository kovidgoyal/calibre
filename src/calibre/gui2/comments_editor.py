#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re, os

from lxml import html

from PyQt4.Qt import (QApplication, QFontInfo, QSize, QWidget, QPlainTextEdit,
    QToolBar, QVBoxLayout, QAction, QIcon, Qt, QTabWidget, QUrl,
    QSyntaxHighlighter, QColor, QChar, QColorDialog, QMenu, QInputDialog,
    QHBoxLayout, QKeySequence)
from PyQt4.QtWebKit import QWebView, QWebPage

from calibre.ebooks.chardet import xml_to_unicode
from calibre import xml_replace_entities
from calibre.gui2 import open_url
from calibre.utils.soupparser import fromstring
from calibre.utils.config import tweaks

class PageAction(QAction): # {{{

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
        if self.isCheckable():
            self.setChecked(self.page_action.isChecked())
        self.setEnabled(self.page_action.isEnabled())

# }}}

class BlockStyleAction(QAction): # {{{

    def __init__(self, text, name, view):
        QAction.__init__(self, text, view)
        self._name = name
        self.triggered.connect(self.apply_style)

    def apply_style(self, *args):
        self.parent().exec_command('formatBlock', self._name)

# }}}

class EditorWidget(QWebView): # {{{

    def __init__(self, parent=None):
        QWebView.__init__(self, parent)

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
                ('RemoveFormat', 'remove_format', 'trash', _('Remove formatting'), False),
                ('Copy', 'copy', 'edit-copy', _('Copy'), False),
                ('Paste', 'paste', 'edit-paste', _('Paste'), False),
                ('Cut', 'cut', 'edit-cut', _('Cut'), False),
                ('Indent', 'indent', 'format-indent-more',
                    _('Increase Indentation'), False),
                ('Outdent', 'outdent', 'format-indent-less',
                    _('Decrease Indentation'), False),
                ('SelectAll', 'select_all', 'edit-select-all',
                    _('Select all'), False),
            ]:
            ac = PageAction(wac, icon, text, checkable, self)
            setattr(self, 'action_'+name, ac)
            ss = extra_shortcuts.get(wac, None)
            if ss:
                ac.setShortcut(QKeySequence(getattr(QKeySequence, ss)))

        self.action_color = QAction(QIcon(I('format-text-color')), _('Foreground color'),
                self)
        self.action_color.triggered.connect(self.foreground_color)

        self.action_background = QAction(QIcon(I('format-fill-color')),
                _('Background color'), self)
        self.action_background.triggered.connect(self.background_color)

        self.action_block_style = QAction(QIcon(I('format-text-heading')),
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
                _('Insert link'), self)
        self.action_insert_link.triggered.connect(self.insert_link)
        self.action_clear = QAction(QIcon(I('edit-clear')), _('Clear'), self)
        self.action_clear.triggered.connect(self.clear_text)

        self.page().setLinkDelegationPolicy(QWebPage.DelegateAllLinks)
        self.page().linkClicked.connect(self.link_clicked)

        self.setHtml('')
        self.page().setContentEditable(True)

    def clear_text(self, *args):
        self.action_select_all.trigger()
        self.action_cut.trigger()

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
        link, ok = QInputDialog.getText(self, _('Create link'),
            _('Enter URL'))
        if not ok:
            return
        url = self.parse_link(unicode(link))
        if url.isValid():
            url = unicode(url.toString())
            self.exec_command('createLink', url)

    def parse_link(self, link):
        link = link.strip()
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
            js = 'document.execCommand("%s", false, "%s");' % (cmd, arg)
        else:
            js = 'document.execCommand("%s", false, null);' % cmd
        frame.evaluateJavaScript(js)

    @dynamic_property
    def html(self):

        def fget(self):
            ans = u''
            check = unicode(self.page().mainFrame().toPlainText()).strip()
            if not check:
                return ans
            try:
                raw = unicode(self.page().mainFrame().toHtml())
                raw = xml_to_unicode(raw, strip_encoding_pats=True,
                                    resolve_entities=True)[0]
                raw = self.comments_pat.sub('', raw)

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
            fi = QFontInfo(QApplication.font(self))
            f  = fi.pixelSize() + 1 + int(tweaks['change_book_details_font_size_by'])
            fam = unicode(fi.family()).strip().replace('"', '')
            if not fam:
                fam = 'sans-serif'
            style = 'font-size: %fpx; font-family:"%s",sans-serif;' % (f, fam)

            # toList() is needed because PyQt on Debian is old/broken
            for body in self.page().mainFrame().documentElement().findAll('body').toList():
                body.setAttribute('style', style)
            self.page().setContentEditable(True)

        return property(fget=fget, fset=fset)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Tab, Qt.Key_Escape, Qt.Key_Backtab):
            ev.ignore()
        else:
            return QWebView.keyPressEvent(self, ev)

    def keyReleaseEvent(self, ev):
        if ev.key() in (Qt.Key_Tab, Qt.Key_Escape, Qt.Key_Backtab):
            ev.ignore()
        else:
            return QWebView.keyReleaseEvent(self, ev)


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
        self.colors['comment']        = QColor( 35, 110,  37)
        self.colors['attrname']       = QColor(153,  69,   0)
        self.colors['attrval']        = QColor( 36,  36, 170)

    def highlightBlock(self, text):
        state = self.previousBlockState()
        len_ = text.length()
        start = 0
        pos = 0

        while pos < len_:

            if state == State_Comment:
                start = pos
                while pos < len_:
                    if text.mid(pos, 3) == "-->":
                        pos += 3;
                        state = State_Text;
                        break
                    else:
                        pos += 1
                self.setFormat(start, pos - start, self.colors['comment'])

            elif state == State_DocType:
                start = pos
                while pos < len_:
                    ch = text.at(pos)
                    pos += 1
                    if ch == QChar('>'):
                        state = State_Text
                        break
                self.setFormat(start, pos - start, self.colors['doctype'])

            # at '<' in e.g. "<span>foo</span>"
            elif state == State_TagStart:
                start = pos + 1
                while pos < len_:
                    ch = text.at(pos)
                    pos += 1
                    if ch == QChar('>'):
                        state = State_Text
                        break
                    if not ch.isSpace():
                        pos -= 1
                        state = State_TagName
                        break

            # at 'b' in e.g "<blockquote>foo</blockquote>"
            elif state == State_TagName:
                start = pos
                while pos < len_:
                    ch = text.at(pos)
                    pos += 1
                    if ch.isSpace():
                        pos -= 1
                        state = State_InsideTag
                        break
                    if ch == QChar('>'):
                        state = State_Text
                        break
                self.setFormat(start, pos - start, self.colors['tag']);

            # anywhere after tag name and before tag closing ('>')
            elif state == State_InsideTag:
                start = pos

                while pos < len_:
                    ch = text.at(pos)
                    pos += 1

                    if ch == QChar('/'):
                        continue

                    if ch == QChar('>'):
                        state = State_Text
                        break

                    if not ch.isSpace():
                        pos -= 1
                        state = State_AttributeName
                        break

            # at 's' in e.g. <img src=bla.png/>
            elif state == State_AttributeName:
                start = pos

                while pos < len_:
                    ch = text.at(pos)
                    pos += 1

                    if ch == QChar('='):
                        state = State_AttributeValue
                        break

                    if ch in (QChar('>'), QChar('/')):
                        state = State_InsideTag
                        break

                self.setFormat(start, pos - start, self.colors['attrname'])

            # after '=' in e.g. <img src=bla.png/>
            elif state == State_AttributeValue:
                start = pos

                # find first non-space character
                while pos < len_:
                    ch = text.at(pos)
                    pos += 1

                    # handle opening single quote
                    if ch == QChar("'"):
                        state = State_SingleQuote
                        break

                    # handle opening double quote
                    if ch == QChar('"'):
                        state = State_DoubleQuote
                        break

                    if not ch.isSpace():
                        break

                if state == State_AttributeValue:
                    # attribute value without quote
                    # just stop at non-space or tag delimiter
                    start = pos
                    while pos < len_:
                        ch = text.at(pos);
                        if ch.isSpace():
                            break
                        if ch in (QChar('>'), QChar('/')):
                            break
                        pos += 1
                    state = State_InsideTag
                    self.setFormat(start, pos - start, self.colors['attrval'])

            # after the opening single quote in an attribute value
            elif state == State_SingleQuote:
                start = pos

                while pos < len_:
                    ch = text.at(pos)
                    pos += 1
                    if ch == QChar("'"):
                        break

                state = State_InsideTag

                self.setFormat(start, pos - start, self.colors['attrval'])

            # after the opening double quote in an attribute value
            elif state == State_DoubleQuote:
                start = pos

                while pos < len_:
                    ch = text.at(pos)
                    pos += 1
                    if ch == QChar('"'):
                        break

                state = State_InsideTag

                self.setFormat(start, pos - start, self.colors['attrval'])

            else:
                # State_Text and default
                while pos < len_:
                    ch = text.at(pos)
                    if ch == QChar('<'):
                        if text.mid(pos, 4) == "<!--":
                            state = State_Comment
                        else:
                            if text.mid(pos, 9).toUpper() == "<!DOCTYPE":
                                state = State_DocType
                            else:
                                state = State_TagStart
                        break;
                    elif ch == QChar('&'):
                        start = pos
                        while pos < len_ and text.at(pos) != QChar(';'):
                            self.setFormat(start, pos - start,
                                    self.colors['entity'])
                            pos += 1

                    else:
                        pos += 1


        self.setCurrentBlockState(state)

# }}}

class Editor(QWidget): # {{{

    def __init__(self, parent=None, one_line_toolbar=False):
        QWidget.__init__(self, parent)
        self.toolbar1 = QToolBar(self)
        self.toolbar2 = QToolBar(self)
        self.toolbar3 = QToolBar(self)
        for i in range(1, 4):
            t = getattr(self, 'toolbar%d'%i)
            t.setIconSize(QSize(18, 18))
        self.editor = EditorWidget(self)
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
        self.tabs.addTab(self.wyswyg, _('Normal view'))
        self.tabs.addTab(self.code_edit, _('HTML Source'))
        self.tabs.currentChanged[int].connect(self.change_tab)
        self.highlighter = Highlighter(self.code_edit.document())

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

    @dynamic_property
    def html(self):
        def fset(self, v):
            self.editor.html = v
        def fget(self):
            self.tabs.setCurrentIndex(0)
            return self.editor.html
        return property(fget=fget, fset=fset)

    def change_tab(self, index):
        #print 'reloading:', (index and self.wyswyg_dirty) or (not index and
        #        self.source_dirty)
        if index == 1: # changing to code view
            if self.wyswyg_dirty:
                self.code_edit.setPlainText(self.editor.html)
                self.wyswyg_dirty = False
        elif index == 0: #changing to wyswyg
            if self.source_dirty:
                self.editor.html = unicode(self.code_edit.toPlainText())
                self.source_dirty = False

    def wyswyg_dirtied(self, *args):
        self.wyswyg_dirty = True

    def code_dirtied(self, *args):
        self.source_dirty = True

    def hide_toolbars(self):
        self.toolbar1.setVisible(False)
        self.toolbar2.setVisible(False)
        self.toolbar3.setVisible(False)

# }}}

if __name__ == '__main__':
    app = QApplication([])
    w = Editor()
    w.resize(800, 600)
    w.show()
# testing {{{

    w.html = '''
<div>

 <h3>From Publishers Weekly</h3>
 <div>
 Starred Review. Paul Dirac (1902–1984) shared the Nobel Prize for physics with Erwin Schrödinger in 1933, but whereas physicists regard Dirac as one of the giants of the 20th century, he isn't as well known outside the profession. This may be due to the lack of humorous quips attributed to Dirac, as compared with an Einstein or a Feynman. If he spoke at all, it was with one-word answers that made Calvin Coolidge look loquacious . Dirac adhered to Keats's admonition that Beauty is truth, truth beauty: if an equation was beautiful, it was probably correct, and vice versa. His most famous equation predicted the positron (now used in PET scans), which is the antiparticle of the electron, and antimatter in general. In 1955, Dirac came up with a primitive version of string theory, which today is the rock star branch of physics. Physicist Farmelo (<i>It Must Be Beautiful</i>) speculates that Dirac suffered from undiagnosed autism because his character quirks resembled autism's symptoms. Farmelo proves himself a wizard at explaining the arcane aspects of particle physics. His great affection for his odd but brilliant subject shows on every page, giving Dirac the biography any great scientist deserves. <i>(Sept.)</i> <br>Copyright © Reed Business Information, a division of Reed Elsevier Inc. All rights reserved.

 </div>
 <h3>Review</h3>
 <div>
 <div><b><i>Kirkus</i> *Starred Review*</b><br> “Paul Dirac was a giant of 20th-century physics, and this rich, satisfying biography does him justice…. [A] nuanced portrayal of an introverted eccentric who held his own in a small clique of revolutionary scientific geniuses.”<br><p><b>Peter Higgs, <i>Times (UK)</i></b><br> “Fascinating reading… Graham Farmelo has done a splendid job of portraying Dirac and his world. The biography is a major achievement.”</p> <p><b><i>Telegraph</i></b><br> “If Newton was the Shakespeare of British physics, Dirac was its Milton, the most fascinating and enigmatic of all our great scientists. And he now has a biography to match his talents: a wonderful book by Graham Farmelo. The story it tells is moving, sometimes comic, sometimes infinitely sad, and goes to the roots of what we mean by truth in science.”</p> <p><b><i>New Statesman</i></b><br> “A marvelously rich and intimate study.”</p> <p><b><i>Sunday Herald</i></b><br> “Farmelo’s splendid biography has enough scientific exposition for the biggest science fan and enough human interest for the rest of us. It creates a picture of a man who was a great theoretical scientist but also an awkward but oddly endearing human being…. This is a fine book: a fitting tribute to a significant and intriguing scientific figure.”</p> <p><b><i>The Economist</i></b><br> “[A] sympathetic portrait….Of the small group of young men who developed quantum mechanics and revolutionized physics almost a century ago, he truly stands out. Paul Dirac was a strange man in a strange world. This biography, long overdue, is most welcome.”</p> <p><b><i>Times Higher Education Supplement (UK)</i></b><br> “A page-turner about Dirac and quantum physics seems a contradiction in terms, but Graham Farmelo's new book, <i>The Strangest Man</i>, is an eminently readable account of the developments in physics throughout the 1920s, 1930s and 1940s and the life of one of the discipline's key scientists.”</p> <p><b><i>New Scientist</i></b><br> “Enthralling… Regardless of whether Dirac was autistic or simply unpleasant, he is an icon of modern thought and Farmelo's book gives us a genuine insight into his life and times.”</p> <p><b>John Gribbin, <i>Literary Review</i></b><br> “Fascinating …[A] suberb book.”</p> <p><b>Tom Stoppard</b><br> “In the group portrait of genius in 20th century physics, Paul Dirac is the stick figure. Who was he, and what did he do? For all non-physicists who have followed the greatest intellectual adventure of modern times, this is the missing book.”</p> <p><b>Michael Frayn</b><br> “Graham Farmelo has found the subject he was born to write about, and brought it off triumphantly. Dirac was one of the great founding fathers of modern physics, a theoretician who explored the sub-atomic world through the power of pure mathematics. He was also a most extraordinary man - an extreme introvert, and perhaps autistic. Farmelo traces the outward events as authoritatively as the inward. His book is a monumental achievement – one of the great scientific biographies.”</p> <p><b>Roger Highfield, Editor,<i>New Scientist</i></b><br> “A must-read for anyone interested in the extraordinary power of pure thought. With this revelatory, moving and definitive biography, Graham Farmelo provides the first real glimpse inside the bizarre mind of Paul Dirac.”</p> <p><b>Martin Rees, President of the Royal Society, Master of Trinity College, Professor of Cosmology and Astrophysics at the University of Cambridge and Astronomer Royal</b><br> “Paul Dirac, though a quiet and withdrawn character, made towering contributions to the greatest scientific revolution of the 20th century. In this sensitive and meticulously researched biography, Graham Farmelo does Dirac proud, and offers a wonderful insight into the European academic environment in which his creativity flourished."</p> <p><b><i>Barnes &amp; Noble Review</i></b><br> “Farmelo explains all the science relevant to understanding Dirac, and does it well; equally good is his careful and copious account of a personal life that was dogged by a sense of tragedy…. [I]f [Dirac] could read Farmelo’s absorbing and accessible account of his life he would see that it had magic in it, and triumph: the magic of revelations about the deep nature of reality, and the triumph of having moved human understanding several steps further towards the light.”</p> <p><b><i>Newark Star-Ledger</i></b><br> “[An] excellently researched biography…. [T]his book is a major step toward making a staggeringly brilliant, remote man seem likeable.”</p> <p><b><i>Los Angeles Times</i></b><br> “Graham Farmelo has managed to haul Dirac onstage in an affectionate and meticulously researched book that illuminates both his era and his science…. Farmelo is very good at portraying this locked-in, asocial creature, often with an eerie use of the future-perfect tense…, which has the virtue of putting the reader in the same room with people who are long gone.”</p> <p><b>SeedMagazine.com</b><br> “[A] tour de force filled with insight and revelation. <i>The Strangest Man</i> offers an unprecedented and gripping view of Dirac not only as a scientist, but also as a human being.”</p> <p><b><i>New York Times Book Review</i></b><br> “This biography is a gift. It is both wonderfully written (certainly not a given in the category Accessible Biographies of Mathematical Physicists) and a thought-provoking meditation on human achievement, limitations and the relations between the two…. [T]he most satisfying and memorable biography I have read in years.”</p> <p><b><i>Time Magazine</i></b><br> “Paul Dirac won a Nobel Prize for Physics at 31. He was one of quantum mechanics’ founding fathers, an Einstein-level genius. He was also virtually incapable of having normal social interactions. Graham Farmelo’s biography explains Dirac’s mysterious life and work.”<br><br><b><i>Library Journal</i></b><br> “Farmelo did not pick the easiest biography to write – its subject lived a largely solitary life in deep thought. But Dirac was also beset with tragedy… and in that respect, the author proposes some novel insights into what shaped the man. This would be a strong addition to a bibliography of magnificent 20th-century physicist biographies, including Walter Issacson’s Einstein, Kai Bird and Martin J. Sherwin’s <i>American Prometheus: The Triumph and Tragedy of J. Robert Oppenheimer</i>, and James Gleick’s <i>Genius: The Life and Science of Richard Feynman</i>.”<br><br><b><i>American Journal of Physics</i></b><br> “[A] very moving biography…. It would have been easy to simply fill the biography with Dirac stories of which there is a cornucopia, many of which are actually true. But Farmelo does much more than that. He has met and spoken with people who knew Dirac including the surviving members of his family. He has been to where Dirac lived and worked and he understands the physics. What has emerged is a 558 page biography, which is a model of the genre. Dirac was so private and emotionally self-contained that one wonders if anyone really knew him. Farmelo’s book is as close as we are likely to come."<br><br><b><i>American Scientist</i></b><br> “[A] highly readable and sympathetic biography of the taciturn British physicist who can be said, with little exaggeration, to have invented modern theoretical physics. The book is a real achievement, alternately gripping and illuminating.”<br><br><b><i>Natural History</i></b><br> “Farmelo’s eloquent and empathetic examination of Dirac’s life raises this book above the level of workmanlike popularization. Using personal interviews, scientific archives, and newly released documents and letters, he’s managed – as much as anyone could – to dispel the impression of the physicist as a real-life Mr. Spock, the half Vulcan of Star Trek.”<br><br><b><i>Science</i></b><br> “[A] consummate and seamless biography…. Farmelo has succeeded masterfully in the difficult genre of writing a great scientist’s life for a general audience.”<br><br><b><i>Physics Today</i></b><br> “[An] excellent biography of a hero of physics…. [I]n <i>The Strangest Man</i>, we are treated to a fascinating, thoroughly researched, and well-written account of one of the most important figures of modern physics.”<br><br><b><i>Nature</i></b><br> “As this excellent biography by Graham Farmelo shows, Dirac’s contributions to science were profound and far-ranging; modern ideas that have their origins in quantum electrodynamics are inspired by his insight…. The effortless writing style shows that it is possible to describe profound ideas without compromising scientific integrity or readability."<br><br><b>Freeman Dyson, <i>New York Review of Books</i></b><br> “In Farmelo’s book we see Dirac as a character in a human drama, carrying his full share of tragedy as well as triumph.”<b><i><br></i></b> <br><b><i>American Journal of Physics</i></b><br> “Farmelo’s exhaustively researched biography…not only traces the life of its title figure but portrays the unfolding of quantum mechanics with cinematic scope…. He repeatedly zooms his storyteller’s lens in and out between intimate close-ups and grand scenes, all the while attempting to make the physics comprehensible to the general readership without trivializing it. In his telling, the front-line scientists are a competitive troupe of explorers, jockeying for renown – only the uncharted territory is in the mind and the map is mathematical…. We read works like Farmelo’s for enlightenment, for inspiration, and for the reminder that science is a quintessentially human endeavor, with all...</p></div>

 </div>
</div>
<div>

 <h3>From Publishers Weekly</h3>
 <div>
 Starred Review. Paul Dirac (1902–1984) shared the Nobel Prize for physics with Erwin Schrödinger in 1933, but whereas physicists regard Dirac as one of the giants of the 20th century, he isn't as well known outside the profession. This may be due to the lack of humorous quips attributed to Dirac, as compared with an Einstein or a Feynman. If he spoke at all, it was with one-word answers that made Calvin Coolidge look loquacious . Dirac adhered to Keats's admonition that Beauty is truth, truth beauty: if an equation was beautiful, it was probably correct, and vice versa. His most famous equation predicted the positron (now used in PET scans), which is the antiparticle of the electron, and antimatter in general. In 1955, Dirac came up with a primitive version of string theory, which today is the rock star branch of physics. Physicist Farmelo (<i>It Must Be Beautiful</i>) speculates that Dirac suffered from undiagnosed autism because his character quirks resembled autism's symptoms. Farmelo proves himself a wizard at explaining the arcane aspects of particle physics. His great affection for his odd but brilliant subject shows on every page, giving Dirac the biography any great scientist deserves. <i>(Sept.)</i> <br>Copyright © Reed Business Information, a division of Reed Elsevier Inc. All rights reserved.

 </div>
 <h3>Review</h3>
 <div>
 <div><b><i>Kirkus</i> *Starred Review*</b><br> “Paul Dirac was a giant of 20th-century physics, and this rich, satisfying biography does him justice…. [A] nuanced portrayal of an introverted eccentric who held his own in a small clique of revolutionary scientific geniuses.”<br><p><b>Peter Higgs, <i>Times (UK)</i></b><br> “Fascinating reading… Graham Farmelo has done a splendid job of portraying Dirac and his world. The biography is a major achievement.”</p> <p><b><i>Telegraph</i></b><br> “If Newton was the Shakespeare of British physics, Dirac was its Milton, the most fascinating and enigmatic of all our great scientists. And he now has a biography to match his talents: a wonderful book by Graham Farmelo. The story it tells is moving, sometimes comic, sometimes infinitely sad, and goes to the roots of what we mean by truth in science.”</p> <p><b><i>New Statesman</i></b><br> “A marvelously rich and intimate study.”</p> <p><b><i>Sunday Herald</i></b><br> “Farmelo’s splendid biography has enough scientific exposition for the biggest science fan and enough human interest for the rest of us. It creates a picture of a man who was a great theoretical scientist but also an awkward but oddly endearing human being…. This is a fine book: a fitting tribute to a significant and intriguing scientific figure.”</p> <p><b><i>The Economist</i></b><br> “[A] sympathetic portrait….Of the small group of young men who developed quantum mechanics and revolutionized physics almost a century ago, he truly stands out. Paul Dirac was a strange man in a strange world. This biography, long overdue, is most welcome.”</p> <p><b><i>Times Higher Education Supplement (UK)</i></b><br> “A page-turner about Dirac and quantum physics seems a contradiction in terms, but Graham Farmelo's new book, <i>The Strangest Man</i>, is an eminently readable account of the developments in physics throughout the 1920s, 1930s and 1940s and the life of one of the discipline's key scientists.”</p> <p><b><i>New Scientist</i></b><br> “Enthralling… Regardless of whether Dirac was autistic or simply unpleasant, he is an icon of modern thought and Farmelo's book gives us a genuine insight into his life and times.”</p> <p><b>John Gribbin, <i>Literary Review</i></b><br> “Fascinating …[A] suberb book.”</p> <p><b>Tom Stoppard</b><br> “In the group portrait of genius in 20th century physics, Paul Dirac is the stick figure. Who was he, and what did he do? For all non-physicists who have followed the greatest intellectual adventure of modern times, this is the missing book.”</p> <p><b>Michael Frayn</b><br> “Graham Farmelo has found the subject he was born to write about, and brought it off triumphantly. Dirac was one of the great founding fathers of modern physics, a theoretician who explored the sub-atomic world through the power of pure mathematics. He was also a most extraordinary man - an extreme introvert, and perhaps autistic. Farmelo traces the outward events as authoritatively as the inward. His book is a monumental achievement – one of the great scientific biographies.”</p> <p><b>Roger Highfield, Editor,<i>New Scientist</i></b><br> “A must-read for anyone interested in the extraordinary power of pure thought. With this revelatory, moving and definitive biography, Graham Farmelo provides the first real glimpse inside the bizarre mind of Paul Dirac.”</p> <p><b>Martin Rees, President of the Royal Society, Master of Trinity College, Professor of Cosmology and Astrophysics at the University of Cambridge and Astronomer Royal</b><br> “Paul Dirac, though a quiet and withdrawn character, made towering contributions to the greatest scientific revolution of the 20th century. In this sensitive and meticulously researched biography, Graham Farmelo does Dirac proud, and offers a wonderful insight into the European academic environment in which his creativity flourished."</p> <p><b><i>Barnes &amp; Noble Review</i></b><br> “Farmelo explains all the science relevant to understanding Dirac, and does it well; equally good is his careful and copious account of a personal life that was dogged by a sense of tragedy…. [I]f [Dirac] could read Farmelo’s absorbing and accessible account of his life he would see that it had magic in it, and triumph: the magic of revelations about the deep nature of reality, and the triumph of having moved human understanding several steps further towards the light.”</p> <p><b><i>Newark Star-Ledger</i></b><br> “[An] excellently researched biography…. [T]his book is a major step toward making a staggeringly brilliant, remote man seem likeable.”</p> <p><b><i>Los Angeles Times</i></b><br> “Graham Farmelo has managed to haul Dirac onstage in an affectionate and meticulously researched book that illuminates both his era and his science…. Farmelo is very good at portraying this locked-in, asocial creature, often with an eerie use of the future-perfect tense…, which has the virtue of putting the reader in the same room with people who are long gone.”</p> <p><b>SeedMagazine.com</b><br> “[A] tour de force filled with insight and revelation. <i>The Strangest Man</i> offers an unprecedented and gripping view of Dirac not only as a scientist, but also as a human being.”</p> <p><b><i>New York Times Book Review</i></b><br> “This biography is a gift. It is both wonderfully written (certainly not a given in the category Accessible Biographies of Mathematical Physicists) and a thought-provoking meditation on human achievement, limitations and the relations between the two…. [T]he most satisfying and memorable biography I have read in years.”</p> <p><b><i>Time Magazine</i></b><br> “Paul Dirac won a Nobel Prize for Physics at 31. He was one of quantum mechanics’ founding fathers, an Einstein-level genius. He was also virtually incapable of having normal social interactions. Graham Farmelo’s biography explains Dirac’s mysterious life and work.”<br><br><b><i>Library Journal</i></b><br> “Farmelo did not pick the easiest biography to write – its subject lived a largely solitary life in deep thought. But Dirac was also beset with tragedy… and in that respect, the author proposes some novel insights into what shaped the man. This would be a strong addition to a bibliography of magnificent 20th-century physicist biographies, including Walter Issacson’s Einstein, Kai Bird and Martin J. Sherwin’s <i>American Prometheus: The Triumph and Tragedy of J. Robert Oppenheimer</i>, and James Gleick’s <i>Genius: The Life and Science of Richard Feynman</i>.”<br><br><b><i>American Journal of Physics</i></b><br> “[A] very moving biography…. It would have been easy to simply fill the biography with Dirac stories of which there is a cornucopia, many of which are actually true. But Farmelo does much more than that. He has met and spoken with people who knew Dirac including the surviving members of his family. He has been to where Dirac lived and worked and he understands the physics. What has emerged is a 558 page biography, which is a model of the genre. Dirac was so private and emotionally self-contained that one wonders if anyone really knew him. Farmelo’s book is as close as we are likely to come."<br><br><b><i>American Scientist</i></b><br> “[A] highly readable and sympathetic biography of the taciturn British physicist who can be said, with little exaggeration, to have invented modern theoretical physics. The book is a real achievement, alternately gripping and illuminating.”<br><br><b><i>Natural History</i></b><br> “Farmelo’s eloquent and empathetic examination of Dirac’s life raises this book above the level of workmanlike popularization. Using personal interviews, scientific archives, and newly released documents and letters, he’s managed – as much as anyone could – to dispel the impression of the physicist as a real-life Mr. Spock, the half Vulcan of Star Trek.”<br><br><b><i>Science</i></b><br> “[A] consummate and seamless biography…. Farmelo has succeeded masterfully in the difficult genre of writing a great scientist’s life for a general audience.”<br><br><b><i>Physics Today</i></b><br> “[An] excellent biography of a hero of physics…. [I]n <i>The Strangest Man</i>, we are treated to a fascinating, thoroughly researched, and well-written account of one of the most important figures of modern physics.”<br><br><b><i>Nature</i></b><br> “As this excellent biography by Graham Farmelo shows, Dirac’s contributions to science were profound and far-ranging; modern ideas that have their origins in quantum electrodynamics are inspired by his insight…. The effortless writing style shows that it is possible to describe profound ideas without compromising scientific integrity or readability."<br><br><b>Freeman Dyson, <i>New York Review of Books</i></b><br> “In Farmelo’s book we see Dirac as a character in a human drama, carrying his full share of tragedy as well as triumph.”<b><i><br></i></b> <br><b><i>American Journal of Physics</i></b><br> “Farmelo’s exhaustively researched biography…not only traces the life of its title figure but portrays the unfolding of quantum mechanics with cinematic scope…. He repeatedly zooms his storyteller’s lens in and out between intimate close-ups and grand scenes, all the while attempting to make the physics comprehensible to the general readership without trivializing it. In his telling, the front-line scientists are a competitive troupe of explorers, jockeying for renown – only the uncharted territory is in the mind and the map is mathematical…. We read works like Farmelo’s for enlightenment, for inspiration, and for the reminder that science is a quintessentially human endeavor, with all...</p></div>

 </div>
</div>
    '''.decode('utf-8')
    app.exec_()
    #print w.html.encode('utf-8')

# }}}
    #print w.html
