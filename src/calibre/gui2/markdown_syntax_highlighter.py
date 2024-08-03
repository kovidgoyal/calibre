#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>


import re

from qt.core import QApplication, QBrush, QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor, QTextLayout

from calibre.gui2.palette import dark_link_color, light_link_color


class MarkdownHighlighter(QSyntaxHighlighter):

    MARKDOWN_KEYS_REGEX = {
        'Bold': re.compile(r'(?<!\\)(?P<delim>\*\*)(?P<text>.+?)(?P=delim)'),
        'Italic': re.compile(r'(?<![\*\\])(?P<delim>\*)(?!\*)(?P<text>([^\*]{2,}?|[^\*]))(?<![\*\\])(?P=delim)'),
        'BoldItalic': re.compile(r'(?<!\\)(?P<delim>\*\*\*)(?P<text>([^\*]{2,}?|[^\*]))(?<!\\)(?P=delim)'),
        'uBold': re.compile(r'(?<!\\)(?P<delim>__)(?P<text>.+?)(?P=delim)'),
        'uItalic': re.compile(r'(?<![_\\])(?P<delim>_)(?!_)(?P<text>([^_]{2,}?|[^_]))(?<![_\\])(?P=delim)'),
        'uBoldItalic': re.compile(r'(?<!\\)(?P<delim>___)(?P<text>([^_]{2,}?|[^_]))(?<!\\)(?P=delim)'),
        'Link': re.compile(r'(?<![!\\]])\[.*?(?<!\\)\](\[.+?(?<!\\)\]|\(.+?(?<!\\)\))'),
        'Image': re.compile(r'(?<!\\)!\[.*?(?<!\\)\](\[.+?(?<!\\)\]|\(.+?(?<!\\)\))'),
        'LinkRef': re.compile(r'(?u)^\s*\[.*?\]:\s*[^\s].*'),
        'Header': re.compile(r'^#{1,6}.*'),
        'UnorderedList': re.compile(r'(?u)^\s*(\*|\+|-)[ \t]\s*'),
        'UnorderedListStar': re.compile(r'(?u)^\s*\*[ \t]\s*'),
        'OrderedList': re.compile(r'(?u)^\s*\d+\.[ \t]\s*'),
        'BlockQuote': re.compile(r'^[ ]{0,3}>+[ \t]?'),
        'CodeBlock': re.compile(r'^([ ]{4,}|[ ]*\t).*'),
        'CodeSpan': re.compile(r'(?<!\\)(?P<delim>`+).+?(?P=delim)'),
        'HeaderLine': re.compile(r'(?u)^(-|=)+\s*$'),
        'HR': re.compile(r'(?u)^(\s*(\*|-|_)\s*){3,}$'),
        'Html': re.compile(r'(?u)</?[^/\s].*?(?<!\\)>'),
        'Entity': re.compile(r'&([A-z]{2,7}|#\d{1,7}|#x[\dA-Fa-f]{1,6});'),
    }

    key_theme_maps = {
        'Bold': "bold",
        'Italic': "emphasis",
        'BoldItalic': "boldemphasis",
        'uBold': "bold",
        'uItalic': "emphasis",
        'uBoldItalic': "boldemphasis",
        'Link': "link",
        'Image': "image",
        'LinkRef': "link",
        'Header': "header",
        'HeaderLine': "header",
        'CodeBlock': "codeblock",
        'UnorderedList': "unorderedlist",
        'UnorderedListStar': "unorderedlist",
        'OrderedList': "orderedlist",
        'BlockQuote': "blockquote",
        'CodeSpan': "codespan",
        'HR': "line",
        'Html': "html",
        'Entity': "entity",
    }

    light_theme =  {
        "bold": {"font-weight":"bold"},
        "emphasis": {"font-style":"italic"},
        "boldemphasis": {"font-weight":"bold", "font-style":"italic"},
        "link": {"color":light_link_color.name(), "font-weight":"normal", "font-style":"normal"},
        "image": {"color":"#cb4b16", "font-weight":"normal", "font-style":"normal"},
        "header": {"color":"#2aa198", "font-weight":"bold", "font-style":"normal"},
        "unorderedlist": {"color":"red", "font-weight":"normal", "font-style":"normal"},
        "orderedlist": {"color":"red", "font-weight":"normal", "font-style":"normal"},
        "blockquote": {"color":"red", "font-weight":"bold", "font-style":"normal"},
        "codespan": {"color":"#ff5800", "font-weight":"normal", "font-style":"normal"},
        "codeblock": {"color":"#ff5800", "font-weight":"normal", "font-style":"normal"},
        "line": {"color":"#2aa198", "font-weight":"normal", "font-style":"normal"},
        "html": {"color":"#c000c0", "font-weight":"normal", "font-style":"normal"},
        "entity": {"color":"#006496"},
    }

    dark_theme =  {
        "bold": {"font-weight":"bold"},
        "emphasis": {"font-style":"italic"},
        "boldemphasis": {"font-weight":"bold", "font-style":"italic"},
        "link": {"color":dark_link_color.name(), "font-weight":"normal", "font-style":"normal"},
        "image": {"color":"#cb4b16", "font-weight":"normal", "font-style":"normal"},
        "header": {"color":"#2aa198", "font-weight":"bold", "font-style":"normal"},
        "unorderedlist": {"color":"yellow", "font-weight":"normal", "font-style":"normal"},
        "orderedlist": {"color":"yellow", "font-weight":"normal", "font-style":"normal"},
        "blockquote": {"color":"yellow", "font-weight":"bold", "font-style":"normal"},
        "codespan": {"color":"#90ee90", "font-weight":"normal", "font-style":"normal"},
        "codeblock": {"color":"#ff9900", "font-weight":"normal", "font-style":"normal"},
        "line": {"color":"#2aa198", "font-weight":"normal", "font-style":"normal"},
        "html": {"color":"#f653a6", "font-weight":"normal", "font-style":"normal"},
        "entity": {"color":"#ff82ac"},
    }

    def __init__(self, parent):
        super().__init__(parent)
        theme = self.dark_theme if QApplication.instance().is_dark_theme else self.light_theme
        self.setTheme(theme)

    def setTheme(self, theme):
        self.theme = theme
        self.MARKDOWN_KWS_FORMAT = {}

        for k in ['Bold', 'Italic','BoldItalic']:
            # generate dynamically keys and theme for EntityBold, EntityItalic, EntityBoldItalic
            t = self.key_theme_maps[k]
            newtheme = theme['entity'].copy()
            newtheme.update(theme[t])
            newthemekey = 'entity'+t
            newmapkey = 'Entity'+k
            theme[newthemekey] = newtheme
            self.key_theme_maps[newmapkey] = newthemekey

        for k,t in self.key_theme_maps.items():
            subtheme = theme[t]
            format = QTextCharFormat()
            if 'color' in subtheme:
                format.setForeground(QBrush(QColor(subtheme['color'])))
            format.setFontWeight(QFont.Weight.Bold if subtheme.get('font-weight') == 'bold' else QFont.Weight.Normal)
            format.setFontItalic(subtheme.get('font-style') == 'italic')
            self.MARKDOWN_KWS_FORMAT[k] = format

        self.rehighlight()

    def highlightBlock(self, text):
        self.offset = 0
        self.highlightMarkdown(text)
        self.highlightHtml(text)

    def highlightMarkdown(self, text):
        cursor = QTextCursor(self.document())
        bf = cursor.blockFormat()

        #Block quotes can contain all elements so process it first, internally process recursively and return
        if self.highlightBlockQuote(text, cursor, bf):
            return

        #If empty line no need to check for below elements just return
        if self.highlightEmptyLine(text, cursor, bf):
            return

        #If horizontal line, look at pevious line to see if its a header, process and return
        if self.highlightHorizontalLine(text, cursor, bf):
            return

        if self.highlightHeader(text, cursor, bf):
            return

        self.highlightList(text, cursor, bf)

        self.highlightBoldEmphasis(text, cursor, bf)

        self.highlightLink(text, cursor, bf)

        self.highlightImage(text, cursor, bf)

        self.highlightEntity(text, cursor, bf)

        self.highlightCodeSpan(text, cursor, bf)

        self.highlightCodeBlock(text, cursor, bf)

    def highlightBlockQuote(self, text, cursor, bf):
        found = False
        mo = re.match(self.MARKDOWN_KEYS_REGEX['BlockQuote'],text)
        if mo:
            self.setFormat(self.offset+ mo.start(), mo.end() - mo.start(), self.MARKDOWN_KWS_FORMAT['BlockQuote'])
            self.offset += mo.end()
            unquote = text[mo.end():]
            self.highlightMarkdown(unquote)
            found = True
        return found

    def highlightEmptyLine(self, text, cursor, bf):
        textAscii = str(text.replace('\u2029','\n'))
        if textAscii.strip():
            return False
        else:
            return True

    def highlightHorizontalLine(self, text, cursor, bf):
        found = False

        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['HeaderLine'],text):
            prevBlock = self.currentBlock().previous()
            prevCursor = QTextCursor(prevBlock)
            prev = prevBlock.text()
            prevAscii = str(prev.replace('\u2029','\n'))
            if self.offset == 0 and prevAscii.strip():
                #print "Its a header"
                prevCursor.select(QTextCursor.SelectionType.LineUnderCursor)
                #prevCursor.setCharFormat(self.MARKDOWN_KWS_FORMAT['Header'])
                formatRange = QTextLayout.FormatRange()
                formatRange.format = self.MARKDOWN_KWS_FORMAT['Header']
                formatRange.length = prevCursor.block().length()
                formatRange.start = 0
                prevCursor.block().layout().setFormats([formatRange])
                self.setFormat(self.offset+ mo.start(), mo.end() - mo.start(), self.MARKDOWN_KWS_FORMAT['HeaderLine'])
                return True

        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['HR'],text):
            self.setFormat(self.offset+ mo.start(), mo.end() - mo.start(), self.MARKDOWN_KWS_FORMAT['HR'])
            found = True
        return found

    def highlightHeader(self, text, cursor, bf):
        found = False
        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['Header'],text):
            #bf.setBackground(QBrush(QColor(7,54,65)))
            #cursor.movePosition(QTextCursor.End)
            #cursor.mergeBlockFormat(bf)
            self.setFormat(self.offset+ mo.start(), mo.end() - mo.start(), self.MARKDOWN_KWS_FORMAT['Header'])
            found = True
        return found

    def highlightList(self, text, cursor, bf):
        found = False
        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['UnorderedList'],text):
            self.setFormat(self.offset+ mo.start(), mo.end() - mo.start(), self.MARKDOWN_KWS_FORMAT['UnorderedList'])
            found = True

        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['OrderedList'],text):
            self.setFormat(self.offset+ mo.start(), mo.end() - mo.start(), self.MARKDOWN_KWS_FORMAT['OrderedList'])
            found = True
        return found

    def highlightLink(self, text, cursor, bf):
        found = False
        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['Link'],text):
            self.setFormat(self.offset+ mo.start(), mo.end() - mo.start(), self.MARKDOWN_KWS_FORMAT['Link'])
            found = True

        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['LinkRef'],text):
            self.setFormat(self.offset+ mo.start(), mo.end() - mo.start(), self.MARKDOWN_KWS_FORMAT['LinkRef'])
            found = True
        return found

    def highlightImage(self, text, cursor, bf):
        found = False
        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['Image'],text):
            self.setFormat(self.offset+ mo.start(), mo.end() - mo.start(), self.MARKDOWN_KWS_FORMAT['Image'])
            found = True
        return found

    def highlightCodeSpan(self, text, cursor, bf):
        found = False
        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['CodeSpan'],text):
            self.setFormat(self.offset+ mo.start(), mo.end() - mo.start(), self.MARKDOWN_KWS_FORMAT['CodeSpan'])
            found = True
        return found

    def highlightBoldEmphasis(self, text, cursor, bf):
        mo = re.match(self.MARKDOWN_KEYS_REGEX['UnorderedListStar'], text)
        if mo:
            offset = mo.end()
        else:
            offset = 0
        return self._highlightBoldEmphasis(text[offset:], cursor, bf, offset, False, False)

    def _highlightBoldEmphasis(self, text, cursor, bf, offset, bold, emphasis):
        #detect and apply imbricated Bold/Emphasis
        found = False

        def apply(match, bold, emphasis):
            if bold and emphasis:
                self.setFormat(self.offset+offset+ match.start(), match.end() - match.start(), self.MARKDOWN_KWS_FORMAT['BoldItalic'])
            elif bold:
                self.setFormat(self.offset+offset+ match.start(), match.end() - match.start(), self.MARKDOWN_KWS_FORMAT['Bold'])
            elif emphasis:
                self.setFormat(self.offset+offset+ match.start(), match.end() - match.start(), self.MARKDOWN_KWS_FORMAT['Italic'])

        def recusive(match, extra_offset, bold, emphasis):
            apply(match, bold, emphasis)
            if bold and emphasis:
                return  # max deep => return, do not process extra Bold/Italic

            sub_txt = text[match.start()+extra_offset : match.end()-extra_offset]
            sub_offset = offset + extra_offset + mo.start()
            self._highlightBoldEmphasis(sub_txt, cursor, bf, sub_offset, bold, emphasis)

        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['Italic'],text):
            recusive(mo, 1, bold, True)
            found = True
        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['uItalic'],text):
            recusive(mo, 1, bold, True)
            found = True

        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['Bold'],text):
            recusive(mo, 2, True, emphasis)
            found = True
        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['uBold'],text):
            recusive(mo, 2, True, emphasis)
            found = True

        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['BoldItalic'],text):
            apply(mo, True, True)
            found = True
        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['uBoldItalic'],text):
            apply(mo, True, True)
            found = True

        return found

    def highlightCodeBlock(self, text, cursor, bf):
        found = False
        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['CodeBlock'],text):
            stripped = text.lstrip()
            if stripped[0] not in ('*','-','+') and not re.match(self.MARKDOWN_KEYS_REGEX['OrderedList'], stripped):
                self.setFormat(self.offset+ mo.start(), mo.end() - mo.start(), self.MARKDOWN_KWS_FORMAT['CodeBlock'])
                found = True
        return found

    def highlightEntity(self, text, cursor, bf):
        found = False
        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['Entity'],text):
            charformat = self.format(self.offset+ mo.start())
            charbold = charformat.fontWeight() == QFont.Weight.Bold
            charitalic = charformat.fontItalic()
            if charbold and charitalic:
                format = self.MARKDOWN_KWS_FORMAT['EntityBoldItalic']
            elif charbold and not charitalic:
                format = self.MARKDOWN_KWS_FORMAT['EntityBold']
            elif not charbold and charitalic:
                format = self.MARKDOWN_KWS_FORMAT['EntityItalic']
            else:
                format = self.MARKDOWN_KWS_FORMAT['Entity']
            self.setFormat(self.offset+ mo.start(), mo.end() - mo.start(), format)
            found = True
        return found

    def highlightHtml(self, text):
        for mo in re.finditer(self.MARKDOWN_KEYS_REGEX['Html'], text):
            self.setFormat(mo.start(), mo.end() - mo.start(), self.MARKDOWN_KWS_FORMAT['Html'])
