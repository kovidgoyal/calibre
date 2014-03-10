#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import unicodedata, re, os, cPickle, textwrap
from bisect import bisect
from functools import partial
from collections import defaultdict

from PyQt4.Qt import (
    QAbstractItemModel, QModelIndex, Qt, QVariant, pyqtSignal, QApplication,
    QTreeView, QSize, QGridLayout, QAbstractListModel, QListView, QPen, QMenu,
    QStyledItemDelegate, QSplitter, QLabel, QSizePolicy, QIcon, QMimeData,
    QPushButton, QToolButton, QInputMethodEvent)

from calibre.constants import plugins, cache_dir
from calibre.gui2 import NONE
from calibre.gui2.widgets2 import HistoryLineEdit2
from calibre.gui2.tweak_book import tprefs
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.utils.icu import safe_chr as chr, icu_unicode_version, character_name_from_code

ROOT = QModelIndex()

non_printing = {
    0xa0: 'nbsp', 0x2000: 'nqsp', 0x2001: 'mqsp', 0x2002: 'ensp', 0x2003: 'emsp', 0x2004: '3/msp', 0x2005: '4/msp', 0x2006: '6/msp',
    0x2007: 'fsp', 0x2008: 'psp', 0x2009: 'thsp', 0x200A: 'hsp', 0x200b: 'zwsp', 0x200c: 'zwnj', 0x200d: 'zwj', 0x200e: 'lrm', 0x200f: 'rlm',
    0x2028: 'lsep', 0x2029: 'psep', 0x202a: 'rle', 0x202b: 'lre', 0x202c: 'pdp', 0x202d: 'lro', 0x202e: 'rlo', 0x202f: 'nnbsp',
    0x205f: 'mmsp', 0x2060: 'wj', 0x2061: 'fa', 0x2062: 'x', 0x2063: ',', 0x2064: '+', 0x206A: 'iss', 0x206b: 'ass', 0x206c: 'iafs', 0x206d: 'aafs',
    0x206e: 'nads', 0x206f: 'nods', 0x20: 'sp', 0x7f: 'del', 0x2e3a: '2m', 0x2e3b: '3m', 0xad: 'shy',
}

# Searching {{{

def load_search_index():
    topchar = 0x10ffff
    ver = (1, topchar, icu_unicode_version or unicodedata.unidata_version)  # Increment this when you make any changes to the index
    name_map = {}
    path = os.path.join(cache_dir(), 'unicode-name-index.pickle')
    if os.path.exists(path):
        with open(path, 'rb') as f:
            name_map = cPickle.load(f)
        if name_map.pop('calibre-nm-version:', None) != ver:
            name_map = {}
    if not name_map:
        name_map = defaultdict(set)
        for x in xrange(1, topchar + 1):
            for word in character_name_from_code(x).split():
                name_map[word.lower()].add(x)
        from calibre.ebooks.html_entities import html5_entities
        for name, char in html5_entities.iteritems():
            try:
                name_map[name.lower()].add(ord(char))
            except TypeError:
                continue
        name_map['nnbsp'].add(0x202F)
        name_map['calibre-nm-version:'] = ver
        cPickle.dump(dict(name_map), open(path, 'wb'), -1)
        del name_map['calibre-nm-version:']
    return name_map

_index = None

def search_for_chars(query, and_tokens=False):
    global _index
    if _index is None:
        _index = load_search_index()
    ans = set()
    for token in query.split():
        token = token.lower()
        m = re.match(r'(?:[u]\+)([a-f0-9]+)', token)
        if m is not None:
            chars = {int(m.group(1), 16)}
        else:
            chars = _index.get(token, None)
        if chars is not None:
            if and_tokens:
                ans &= chars
            else:
                ans |= chars
    return sorted(ans)
# }}}

class CategoryModel(QAbstractItemModel):

    def __init__(self, parent=None):
        QAbstractItemModel.__init__(self, parent)
        self.categories = ((_('Favorites'), ()),  # {{{
(_('European scripts'), (
    (_('Armenian'), (0x530, 0x58F)),
    (_('Armenian ligatures'), (0xFB13, 0xFB17)),
    (_('Coptic'), (0x2C80, 0x2CFF)),
    (_('Coptic in Greek block'), (0x3E2, 0x3EF)),
    (_('Cypriot Syllabary'), (0x10800, 0x1083F)),
    (_('Cyrillic'), (0x400, 0x4FF)),
    (_('Cyrillic Supplement'), (0x500, 0x52F)),
    (_('Cyrillic Extended-A'), (0x2DE0, 0x2DFF)),
    (_('Cyrillic Extended-B'), (0xA640, 0xA69F)),
    (_('Georgian'), (0x10A0, 0x10FF)),
    (_('Georgian Supplement'), (0x2D00, 0x2D2F)),
    (_('Glagolitic'), (0x2C00, 0x2C5F)),
    (_('Gothic'), (0x10330, 0x1034F)),
    (_('Greek and Coptic'), (0x370, 0x3FF)),
    (_('Greek Extended'), (0x1F00, 0x1FFF)),
    (_('Latin, Basic & Latin-1 Supplement'), (0x20, 0xFF)),
    (_('Latin Extended-A'), (0x100, 0x17F)),
    (_('Latin Extended-B'), (0x180, 0x24F)),
    (_('Latin Extended-C'), (0x2C60, 0x2C7F)),
    (_('Latin Extended-D'), (0xA720, 0xA7FF)),
    (_('Latin Extended Additional'), (0x1E00, 0x1EFF)),
    (_('Latin ligatures'), (0xFB00, 0xFB06)),
    (_('Fullwidth Latin letters'), (0xFF00, 0xFF5E)),
    (_('Linear B Syllabary'), (0x10000, 0x1007F)),
    (_('Linear B Ideograms'), (0x10080, 0x100FF)),
    (_('Ogham'), (0x1680, 0x169F)),
    (_('Old Italic'), (0x10300, 0x1032F)),
    (_('Phaistos Disc'), (0x101D0, 0x101FF)),
    (_('Runic'), (0x16A0, 0x16FF)),
    (_('Shavian'), (0x10450, 0x1047F)),
)),

(_('Phonetic Symbols'), (
    (_('IPA Extensions'), (0x250, 0x2AF)),
    (_('Phonetic Extensions'), (0x1D00, 0x1D7F)),
    (_('Phonetic Extensions Supplement'), (0x1D80, 0x1DBF)),
    (_('Modifier Tone Letters'), (0xA700, 0xA71F)),
    (_('Spacing Modifier Letters'), (0x2B0, 0x2FF)),
    (_('Superscripts and Subscripts'), (0x2070, 0x209F)),
)),

(_('Combining Diacritics'), (
    (_('Combining Diacritical Marks'), (0x300, 0x36F)),
    (_('Combining Diacritical Marks for Symbols'), (0x20D0, 0x20FF)),
    (_('Combining Diacritical Marks Supplement'), (0x1DC0, 0x1DFF)),
    (_('Combining Half Marks'), (0xFE20, 0xFE2F)),
)),

(_('African Scripts'), (
    (_('Bamum'), (0xA6A0, 0xA6FF)),
    (_('Bamum Supplement'), (0x16800, 0x16A3F)),
    (_('Egyptian Hieroglyphs'), (0x13000, 0x1342F)),
    (_('Ethiopic'), (0x1200, 0x137F)),
    (_('Ethiopic Supplement'), (0x1380, 0x139F)),
    (_('Ethiopic Extended'), (0x2D80, 0x2DDF)),
    (_('Ethiopic Extended-A'), (0xAB00, 0xAB2F)),
    (_('Meroitic Cursive'), (0x109A0, 0x109FF)),
    (_('Meroitic Hieroglyphs*'), (0x10980, 0x1099F)),
    (_('N\'Ko'), (0x7C0, 0x7FF)),
    (_('Osmanya'), (0x10480, 0x104AF)),
    (_('Tifinagh'), (0x2D30, 0x2D7F)),
    (_('Vai'), (0xA500, 0xA63F)),
)),

(_('Middle Eastern Scripts'), (
    (_('Arabic'), (0x600, 0x6FF)),
    (_('Arabic Supplement'), (0x750, 0x77F)),
    (_('Arabic Extended-A'), (0x8A0, 0x8FF)),
    (_('Arabic Presentation Forms-A'), (0xFB50, 0xFDFF)),
    (_('Arabic Presentation Forms-B'), (0xFE70, 0xFEFF)),
    (_('Avestan'), (0x10B00, 0x10B3F)),
    (_('Carian'), (0x102A0, 0x102DF)),
    (_('Cuneiform'), (0x12000, 0x123FF)),
    (_('Cuneiform Numbers and Punctuation'), (0x12400, 0x1247F)),
    (_('Hebrew'), (0x590, 0x5FF)),
    (_('Hebrew Presentation Forms'), (0xFB1D, 0xFB4F)),
    (_('Imperial Aramaic'), (0x10840, 0x1085F)),
    (_('Inscriptional Pahlavi'), (0x10B60, 0x10B7F)),
    (_('Inscriptional Parthian'), (0x10B40, 0x10B5F)),
    (_('Lycian'), (0x10280, 0x1029F)),
    (_('Lydian'), (0x10920, 0x1093F)),
    (_('Mandaic'), (0x840, 0x85F)),
    (_('Old Persian'), (0x103A0, 0x103DF)),
    (_('Old South Arabian'), (0x10A60, 0x10A7F)),
    (_('Phoenician'), (0x10900, 0x1091F)),
    (_('Samaritan'), (0x800, 0x83F)),
    (_('Syriac'), (0x700, 0x74F)),
    (_('Ugaritic'), (0x10380, 0x1039F)),
)),

(_('Central Asian Scripts'), (
    (_('Mongolian'), (0x1800, 0x18AF)),
    (_('Old Turkic'), (0x10C00, 0x10C4F)),
    (_('Phags-pa'), (0xA840, 0xA87F)),
    (_('Tibetan'), (0xF00, 0xFFF)),
)),

(_('South Asian Scripts'), (
    (_('Bengali'), (0x980, 0x9FF)),
    (_('Brahmi'), (0x11000, 0x1107F)),
    (_('Chakma'), (0x11100, 0x1114F)),
    (_('Devanagari'), (0x900, 0x97F)),
    (_('Devanagari Extended'), (0xA8E0, 0xA8FF)),
    (_('Gujarati'), (0xA80, 0xAFF)),
    (_('Gurmukhi'), (0xA00, 0xA7F)),
    (_('Kaithi'), (0x11080, 0x110CF)),
    (_('Kannada'), (0xC80, 0xCFF)),
    (_('Kharoshthi'), (0x10A00, 0x10A5F)),
    (_('Lepcha'), (0x1C00, 0x1C4F)),
    (_('Limbu'), (0x1900, 0x194F)),
    (_('Malayalam'), (0xD00, 0xD7F)),
    (_('Meetei Mayek'), (0xABC0, 0xABFF)),
    (_('Meetei Mayek Extensions*'), (0xAAE0, 0xAAEF)),
    (_('Ol Chiki'), (0x1C50, 0x1C7F)),
    (_('Oriya'), (0xB00, 0xB7F)),
    (_('Saurashtra'), (0xA880, 0xA8DF)),
    (_('Sinhala'), (0xD80, 0xDFF)),
    (_('Sharada'), (0x11180, 0x111DF)),
    (_('Sora Sompeng'), (0x110D0, 0x110FF)),
    (_('Syloti Nagri'), (0xA800, 0xA82F)),
    (_('Takri'), (0x11680, 0x116CF)),
    (_('Tamil'), (0xB80, 0xBFF)),
    (_('Telugu'), (0xC00, 0xC7F)),
    (_('Thaana'), (0x780, 0x7BF)),
    (_('Vedic Extensions'), (0x1CD0, 0x1CFF)),
)),

(_('Southeast Asian Scripts'), (
    (_('Balinese'), (0x1B00, 0x1B7F)),
    (_('Batak'), (0x1BC0, 0x1BFF)),
    (_('Buginese'), (0x1A00, 0x1A1F)),
    (_('Cham'), (0xAA00, 0xAA5F)),
    (_('Javanese'), (0xA980, 0xA9DF)),
    (_('Kayah Li'), (0xA900, 0xA92F)),
    (_('Khmer'), (0x1780, 0x17FF)),
    (_('Khmer Symbols'), (0x19E0, 0x19FF)),
    (_('Lao'), (0xE80, 0xEFF)),
    (_('Myanmar'), (0x1000, 0x109F)),
    (_('Myanmar Extended-A'), (0xAA60, 0xAA7F)),
    (_('New Tai Lue'), (0x1980, 0x19DF)),
    (_('Rejang'), (0xA930, 0xA95F)),
    (_('Sundanese'), (0x1B80, 0x1BBF)),
    (_('Sundanese Supplement'), (0x1CC0, 0x1CCF)),
    (_('Tai Le'), (0x1950, 0x197F)),
    (_('Tai Tham'), (0x1A20, 0x1AAF)),
    (_('Tai Viet'), (0xAA80, 0xAADF)),
    (_('Thai'), (0xE00, 0xE7F)),
)),

(_('Philippine Scripts'), (
    (_('Buhid'), (0x1740, 0x175F)),
    (_('Hanunoo'), (0x1720, 0x173F)),
    (_('Tagalog'), (0x1700, 0x171F)),
    (_('Tagbanwa'), (0x1760, 0x177F)),
)),

(_('East Asian Scripts'), (
    (_('Bopomofo'), (0x3100, 0x312F)),
    (_('Bopomofo Extended'), (0x31A0, 0x31BF)),
    (_('CJK Unified Ideographs'), (0x4E00, 0x9FFF)),
    (_('CJK Unified Ideographs Extension-A'), (0x3400, 0x4DBF)),
    (_('CJK Unified Ideographs Extension B'), (0x20000, 0x2A6DF)),
    (_('CJK Unified Ideographs Extension C'), (0x2A700, 0x2B73F)),
    (_('CJK Unified Ideographs Extension D'), (0x2B740, 0x2B81F)),
    (_('CJK Compatibility Ideographs'), (0xF900, 0xFAFF)),
    (_('CJK Compatibility Ideographs Supplement'), (0x2F800, 0x2FA1F)),
    (_('Kangxi Radicals'), (0x2F00, 0x2FDF)),
    (_('CJK Radicals Supplement'), (0x2E80, 0x2EFF)),
    (_('CJK Strokes'), (0x31C0, 0x31EF)),
    (_('Ideographic Description Characters'), (0x2FF0, 0x2FFF)),
    (_('Hiragana'), (0x3040, 0x309F)),
    (_('Katakana'), (0x30A0, 0x30FF)),
    (_('Katakana Phonetic Extensions'), (0x31F0, 0x31FF)),
    (_('Kana Supplement'), (0x1B000, 0x1B0FF)),
    (_('Halfwidth Katakana'), (0xFF65, 0xFF9F)),
    (_('Kanbun'), (0x3190, 0x319F)),
    (_('Hangul Syllables'), (0xAC00, 0xD7AF)),
    (_('Hangul Jamo'), (0x1100, 0x11FF)),
    (_('Hangul Jamo Extended-A'), (0xA960, 0xA97F)),
    (_('Hangul Jamo Extended-B'), (0xD7B0, 0xD7FF)),
    (_('Hangul Compatibility Jamo'), (0x3130, 0x318F)),
    (_('Halfwidth Jamo'), (0xFFA0, 0xFFDC)),
    (_('Lisu'), (0xA4D0, 0xA4FF)),
    (_('Miao'), (0x16F00, 0x16F9F)),
    (_('Yi Syllables'), (0xA000, 0xA48F)),
    (_('Yi Radicals'), (0xA490, 0xA4CF)),
)),

(_('American Scripts'), (
    (_('Cherokee'), (0x13A0, 0x13FF)),
    (_('Deseret'), (0x10400, 0x1044F)),
    (_('Unified Canadian Aboriginal Syllabics'), (0x1400, 0x167F)),
    (_('UCAS Extended'), (0x18B0, 0x18FF)),
)),

(_('Other'), (
    (_('Alphabetic Presentation Forms'), (0xFB00, 0xFB4F)),
    (_('Halfwidth and Fullwidth Forms'), (0xFF00, 0xFFEF)),
)),

(_('Punctuation'), (
    (_('General Punctuation'), (0x2000, 0x206F)),
    (_('ASCII Punctuation'), (0x21, 0x7F)),
    (_('Cuneiform Numbers and Punctuation'), (0x12400, 0x1247F)),
    (_('Latin-1 Punctuation'), (0xA1, 0xBF)),
    (_('Small Form Variants'), (0xFE50, 0xFE6F)),
    (_('Supplemental Punctuation'), (0x2E00, 0x2E7F)),
    (_('CJK Symbols and Punctuation'), (0x3000, 0x303F)),
    (_('CJK Compatibility Forms'), (0xFE30, 0xFE4F)),
    (_('Fullwidth ASCII Punctuation'), (0xFF01, 0xFF60)),
    (_('Vertical Forms'), (0xFE10, 0xFE1F)),
)),

(_('Alphanumeric Symbols'), (
    (_('Arabic Mathematical Alphabetic Symbols'), (0x1EE00, 0x1EEFF)),
    (_('Letterlike Symbols'), (0x2100, 0x214F)),
    (_('Roman Symbols'), (0x10190, 0x101CF)),
    (_('Mathematical Alphanumeric Symbols'), (0x1D400, 0x1D7FF)),
    (_('Enclosed Alphanumerics'), (0x2460, 0x24FF)),
    (_('Enclosed Alphanumeric Supplement'), (0x1F100, 0x1F1FF)),
    (_('Enclosed CJK Letters and Months'), (0x3200, 0x32FF)),
    (_('Enclosed Ideographic Supplement'), (0x1F200, 0x1F2FF)),
    (_('CJK Compatibility'), (0x3300, 0x33FF)),
)),

(_('Technical Symbols'), (
    (_('Miscellaneous Technical'), (0x2300, 0x23FF)),
    (_('Control Pictures'), (0x2400, 0x243F)),
    (_('Optical Character Recognition'), (0x2440, 0x245F)),
)),

(_('Numbers and Digits'), (
    (_('Aegean Numbers'), (0x10100, 0x1013F)),
    (_('Ancient Greek Numbers'), (0x10140, 0x1018F)),
    (_('Common Indic Number Forms'), (0xA830, 0xA83F)),
    (_('Counting Rod Numerals'), (0x1D360, 0x1D37F)),
    (_('Cuneiform Numbers and Punctuation'), (0x12400, 0x1247F)),
    (_('Fullwidth ASCII Digits'), (0xFF10, 0xFF19)),
    (_('Number Forms'), (0x2150, 0x218F)),
    (_('Rumi Numeral Symbols'), (0x10E60, 0x10E7F)),
    (_('Superscripts and Subscripts'), (0x2070, 0x209F)),
)),

(_('Mathematical Symbols'), (
    (_('Arrows'), (0x2190, 0x21FF)),
    (_('Supplemental Arrows-A'), (0x27F0, 0x27FF)),
    (_('Supplemental Arrows-B'), (0x2900, 0x297F)),
    (_('Miscellaneous Symbols and Arrows'), (0x2B00, 0x2BFF)),
    (_('Mathematical Alphanumeric Symbols'), (0x1D400, 0x1D7FF)),
    (_('Letterlike Symbols'), (0x2100, 0x214F)),
    (_('Mathematical Operators'), (0x2200, 0x22FF)),
    (_('Miscellaneous Mathematical Symbols-A'), (0x27C0, 0x27EF)),
    (_('Miscellaneous Mathematical Symbols-B'), (0x2980, 0x29FF)),
    (_('Supplemental Mathematical Operators'), (0x2A00, 0x2AFF)),
    (_('Ceilings and Floors'), (0x2308, 0x230B)),
    (_('Geometric Shapes'), (0x25A0, 0x25FF)),
    (_('Box Drawing'), (0x2500, 0x257F)),
    (_('Block Elements'), (0x2580, 0x259F)),
)),

(_('Musical Symbols'), (
    (_('Musical Symbols'), (0x1D100, 0x1D1FF)),
    (_('More Musical Symbols'), (0x2669, 0x266F)),
    (_('Ancient Greek Musical Notation'), (0x1D200, 0x1D24F)),
    (_('Byzantine Musical Symbols'), (0x1D000, 0x1D0FF)),
)),

(_('Game Symbols'), (
    (_('Chess'), (0x2654, 0x265F)),
    (_('Domino Tiles'), (0x1F030, 0x1F09F)),
    (_('Draughts'), (0x26C0, 0x26C3)),
    (_('Japanese Chess'), (0x2616, 0x2617)),
    (_('Mahjong Tiles'), (0x1F000, 0x1F02F)),
    (_('Playing Cards'), (0x1F0A0, 0x1F0FF)),
    (_('Playing Card Suits'), (0x2660, 0x2667)),
)),

(_('Other Symbols'), (
    (_('Alchemical Symbols'), (0x1F700, 0x1F77F)),
    (_('Ancient Symbols'), (0x10190, 0x101CF)),
    (_('Braille Patterns'), (0x2800, 0x28FF)),
    (_('Currency Symbols'), (0x20A0, 0x20CF)),
    (_('Combining Diacritical Marks for Symbols'), (0x20D0, 0x20FF)),
    (_('Dingbats'), (0x2700, 0x27BF)),
    (_('Emoticons'), (0x1F600, 0x1F64F)),
    (_('Miscellaneous Symbols'), (0x2600, 0x26FF)),
    (_('Miscellaneous Symbols and Arrows'), (0x2B00, 0x2BFF)),
    (_('Miscellaneous Symbols And Pictographs'), (0x1F300, 0x1F5FF)),
    (_('Yijing Hexagram Symbols'), (0x4DC0, 0x4DFF)),
    (_('Yijing Mono and Digrams'), (0x268A, 0x268F)),
    (_('Yijing Trigrams'), (0x2630, 0x2637)),
    (_('Tai Xuan Jing Symbols'), (0x1D300, 0x1D35F)),
    (_('Transport And Map Symbols'), (0x1F680, 0x1F6FF)),
)),

(_('Other'), (
    (_('Specials'), (0xFFF0, 0xFFFF)),
    (_('Tags'), (0xE0000, 0xE007F)),
    (_('Variation Selectors'), (0xFE00, 0xFE0F)),
    (_('Variation Selectors Supplement'), (0xE0100, 0xE01EF)),
)),
)  # }}}

        self.category_map = {}
        self.starts = []
        for tlname, items in self.categories[1:]:
            for name, (start, end) in items:
                self.category_map[start] = (tlname, name)
                self.starts.append(start)
        self.starts.sort()
        self.bold_font = f = QApplication.font()
        f.setBold(True)
        self.fav_icon = QIcon(I('rating.png'))

    def columnCount(self, parent=ROOT):
        return 1

    def rowCount(self, parent=ROOT):
        if not parent.isValid():
            return len(self.categories)
        r = parent.row()
        pid = parent.internalId()
        if pid == 0 and -1 < r < len(self.categories):
            return len(self.categories[r][1])
        return 0

    def index(self, row, column, parent=ROOT):
        if not parent.isValid():
            return self.createIndex(row, column) if -1 < row < len(self.categories) else ROOT
        try:
            return self.createIndex(row, column, parent.row() + 1) if -1 < row < len(self.categories[parent.row()][1]) else ROOT
        except IndexError:
            return ROOT

    def parent(self, index):
        if not index.isValid():
            return ROOT
        pid = index.internalId()
        if pid == 0:
            return ROOT
        return self.index(pid - 1, 0)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return NONE
        pid = index.internalId()
        if pid == 0:
            if role == Qt.DisplayRole:
                return QVariant(self.categories[index.row()][0])
            if role == Qt.FontRole:
                return QVariant(self.bold_font)
            if role == Qt.DecorationRole and index.row() == 0:
                return QVariant(self.fav_icon)
        else:
            if role == Qt.DisplayRole:
                item = self.categories[pid - 1][1][index.row()]
                return QVariant(item[0])
        return NONE

    def get_range(self, index):
        if index.isValid():
            pid = index.internalId()
            if pid == 0:
                if index.row() == 0:
                    return (_('Favorites'), list(tprefs['charmap_favorites']))
            else:
                item = self.categories[pid - 1][1][index.row()]
                return (item[0], list(xrange(item[1][0], item[1][1] + 1)))

    def get_char_info(self, char_code):
        ipos = bisect(self.starts, char_code) - 1
        try:
            category, subcategory = self.category_map[self.starts[ipos]]
        except IndexError:
            category = subcategory = _('Unknown')
        return category, subcategory, (character_name_from_code(char_code) or _('Unknown'))

class CategoryDelegate(QStyledItemDelegate):

    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)

    def sizeHint(self, option, index):
        ans = QStyledItemDelegate.sizeHint(self, option, index)
        if not index.parent().isValid():
            ans += QSize(0, 6)
        return ans

class CategoryView(QTreeView):

    category_selected = pyqtSignal(object, object)

    def __init__(self, parent=None):
        QTreeView.__init__(self, parent)
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.activated.connect(self.item_activated)
        self.clicked.connect(self.item_activated)
        pi = plugins['progress_indicator'][0]
        if hasattr(pi, 'set_no_activate_on_click'):
            pi.set_no_activate_on_click(self)
        self.initialized = False
        self.setExpandsOnDoubleClick(False)

    def item_activated(self, index):
        ans = self._model.get_range(index)
        if ans is not None:
            self.category_selected.emit(*ans)
        else:
            if self.isExpanded(index):
                self.collapse(index)
            else:
                self.expand(index)

    def get_chars(self):
        ans = self._model.get_range(self.currentIndex())
        if ans is not None:
            self.category_selected.emit(*ans)

    def initialize(self):
        if not self.initialized:
            self._model = m = CategoryModel(self)
            self.setModel(m)
            self.setCurrentIndex(m.index(0, 0))
            self.item_activated(m.index(0, 0))
            self._delegate = CategoryDelegate(self)
            self.setItemDelegate(self._delegate)
            self.initialized = True

class CharModel(QAbstractListModel):

    def __init__(self, parent=None):
        QAbstractListModel.__init__(self, parent)
        self.chars = []
        self.allow_dnd = False

    def rowCount(self, parent=ROOT):
        return len(self.chars)

    def data(self, index, role):
        if role == Qt.UserRole and -1 < index.row() < len(self.chars):
            return QVariant(self.chars[index.row()])
        return NONE

    def flags(self, index):
        ans = Qt.ItemIsEnabled
        if self.allow_dnd:
            ans |= Qt.ItemIsSelectable
            ans |= Qt.ItemIsDragEnabled if index.isValid() else Qt.ItemIsDropEnabled
        return ans

    def supportedDropActions(self):
        return Qt.MoveAction

    def mimeTypes(self):
        return ['application/calibre_charcode_indices']

    def mimeData(self, indexes):
        data = ','.join(str(i.row()) for i in indexes)
        md = QMimeData()
        md.setData('application/calibre_charcode_indices', data.encode('utf-8'))
        return md

    def dropMimeData(self, md, action, row, column, parent):
        if action != Qt.MoveAction or not md.hasFormat('application/calibre_charcode_indices') or row < 0 or column != 0:
            return False
        indices = map(int, bytes(md.data('application/calibre_charcode_indices')).split(','))
        codes = [self.chars[x] for x in indices]
        for x in indices:
            self.chars[x] = None
        for x in reversed(codes):
            self.chars.insert(row, x)
        self.chars = [x for x in self.chars if x is not None]
        self.reset()
        tprefs['charmap_favorites'] = list(self.chars)
        return True

class CharDelegate(QStyledItemDelegate):

    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)
        self.item_size = QSize(32, 32)
        self.np_pat = re.compile(r'(sp|j|nj|ss|fs|ds)$')

    def sizeHint(self, option, index):
        return self.item_size

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, index)
        charcode, ok = index.data(Qt.UserRole).toInt()
        if not ok:
            return
        painter.save()
        try:
            if charcode in non_printing:
                self.paint_non_printing(painter, option, charcode)
            else:
                self.paint_normal(painter, option, charcode)
        finally:
            painter.restore()

    def paint_normal(self, painter, option, charcode):
        f = option.font
        f.setPixelSize(option.rect.height() - 8)
        painter.setFont(f)
        painter.drawText(option.rect, Qt.AlignHCenter | Qt.AlignBottom | Qt.TextSingleLine, chr(charcode))

    def paint_non_printing(self, painter, option, charcode):
        text = self.np_pat.sub(r'\n\1', non_printing[charcode])
        painter.drawText(option.rect, Qt.AlignCenter | Qt.TextWordWrap | Qt.TextWrapAnywhere, text)
        painter.setPen(QPen(Qt.DashLine))
        painter.drawRect(option.rect.adjusted(1, 1, -1, -1))

class CharView(QListView):

    show_name = pyqtSignal(object)
    char_selected = pyqtSignal(object)

    def __init__(self, parent=None):
        self.last_mouse_idx = -1
        QListView.__init__(self, parent)
        self._model = CharModel(self)
        self.setModel(self._model)
        self.delegate = CharDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setFlow(self.LeftToRight)
        self.setWrapping(True)
        self.setMouseTracking(True)
        self.setSpacing(2)
        self.setUniformItemSizes(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)
        self.showing_favorites = False
        pi = plugins['progress_indicator'][0]
        if hasattr(pi, 'set_no_activate_on_click'):
            pi.set_no_activate_on_click(self)
        self.activated.connect(self.item_activated)
        self.clicked.connect(self.item_activated)

    def item_activated(self, index):
        char_code, ok = self.model().data(index, Qt.UserRole).toInt()
        if ok:
            self.char_selected.emit(chr(char_code))

    def set_allow_drag_and_drop(self, enabled):
        if not enabled:
            self.setDragEnabled(False)
            self.viewport().setAcceptDrops(False)
            self.setDropIndicatorShown(True)
            self._model.allow_dnd = False
        else:
            self.setSelectionMode(self.ExtendedSelection)
            self.viewport().setAcceptDrops(True)
            self.setDragEnabled(True)
            self.setAcceptDrops(True)
            self.setDropIndicatorShown(False)
            self._model.allow_dnd = True

    def show_chars(self, name, codes):
        self.showing_favorites = name == _('Favorites')
        self._model.chars = codes
        self._model.reset()
        self.scrollToTop()

    def mouseMoveEvent(self, ev):
        index = self.indexAt(ev.pos())
        if index.isValid():
            row = index.row()
            if row != self.last_mouse_idx:
                self.last_mouse_idx = row
                char_code, ok = self.model().data(index, Qt.UserRole).toInt()
                if ok:
                    self.show_name.emit(char_code)
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
            self.show_name.emit(-1)
            self.last_mouse_idx = -1
        return QListView.mouseMoveEvent(self, ev)

    def context_menu(self, pos):
        index = self.indexAt(pos)
        if index.isValid():
            char_code, ok = self.model().data(index, Qt.UserRole).toInt()
            if ok:
                m = QMenu(self)
                m.addAction(QIcon(I('edit-copy.png')), _('Copy %s to clipboard') % chr(char_code), partial(self.copy_to_clipboard, char_code))
                m.addAction(QIcon(I('rating.png')),
                            (_('Remove %s from favorites') if self.showing_favorites else _('Add %s to favorites')) % chr(char_code),
                            partial(self.remove_from_favorites, char_code))
                if self.showing_favorites:
                    m.addAction(_('Restore favorites to defaults'), self.restore_defaults)
                m.exec_(self.mapToGlobal(pos))

    def restore_defaults(self):
        del tprefs['charmap_favorites']
        self.model().chars = list(tprefs['charmap_favorites'])
        self.model().reset()

    def copy_to_clipboard(self, char_code):
        c = QApplication.clipboard()
        c.setText(chr(char_code))

    def remove_from_favorites(self, char_code):
        existing = tprefs['charmap_favorites']
        if not self.showing_favorites:
            if char_code not in existing:
                tprefs['charmap_favorites'] = [char_code] + existing
        elif char_code in existing:
            existing.remove(char_code)
            tprefs['charmap_favorites'] = existing
            self.model().chars.remove(char_code)
            self.model().reset()

class CharSelect(Dialog):

    def __init__(self, parent=None):
        self.initialized = False
        Dialog.__init__(self, _('Insert character'), 'charmap_dialog', parent)
        self.setWindowIcon(QIcon(I('character-set.png')))
        self.focus_widget = None

    def setup_ui(self):
        self.l = l = QGridLayout(self)
        self.setLayout(l)

        self.bb.setStandardButtons(self.bb.Close)
        self.rearrange_button = b = self.bb.addButton(_('Re-arrange favorites'), self.bb.ActionRole)
        b.setCheckable(True)
        b.setChecked(False)
        b.setVisible(False)
        b.setDefault(True)

        self.splitter = s = QSplitter(self)
        s.setChildrenCollapsible(False)

        self.search = h = HistoryLineEdit2(self)
        h.setToolTip(textwrap.fill(_(
            'Search for unicode characters by using the English names or nicknames.'
            ' You can also search directly using a character code. For example, the following'
            ' searches will all yield the no-break space character: U+A0, nbsp, no-break')))
        h.initialize('charmap_search')
        h.setPlaceholderText(_('Search by name, nickname or character code'))
        self.search_button = b = QPushButton(_('&Search'))
        h.returnPressed.connect(self.do_search)
        b.clicked.connect(self.do_search)
        self.clear_button = cb = QToolButton(self)
        cb.setIcon(QIcon(I('clear_left.png')))
        cb.setText(_('Clear search'))
        cb.clicked.connect(self.clear_search)
        l.addWidget(h), l.addWidget(b, 0, 1), l.addWidget(cb, 0, 2)

        self.category_view = CategoryView(self)
        l.addWidget(s, 1, 0, 1, 3)
        self.char_view = CharView(self)
        self.rearrange_button.toggled[bool].connect(self.set_allow_drag_and_drop)
        self.category_view.category_selected.connect(self.show_chars)
        self.char_view.show_name.connect(self.show_char_info)
        self.char_view.char_selected.connect(self.char_selected)
        s.addWidget(self.category_view), s.addWidget(self.char_view)

        self.char_info = la = QLabel('\xa0')
        la.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        l.addWidget(la, 2, 0, 1, 3)

        self.rearrange_msg = la = QLabel(_(
            'Drag and drop characters to re-arrange them. Click the re-arrange button again when you are done.'))
        la.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        la.setVisible(False)
        l.addWidget(la, 3, 0, 1, 3)
        l.addWidget(self.bb, 4, 0, 1, 3)
        self.char_view.setFocus(Qt.OtherFocusReason)

    def do_search(self):
        from calibre.gui2.tweak_book.boss import BusyCursor
        text = unicode(self.search.text()).strip()
        if not text:
            return self.clear_search()
        with BusyCursor():
            chars = search_for_chars(text)
        self.show_chars(_('Search'), chars)

    def clear_search(self):
        self.search.clear()
        self.category_view.get_chars()

    def set_allow_drag_and_drop(self, on):
        self.char_view.set_allow_drag_and_drop(on)
        self.rearrange_msg.setVisible(on)

    def show_chars(self, name, codes):
        b = self.rearrange_button
        b.setVisible(name == _('Favorites'))
        b.blockSignals(True)
        b.setChecked(False)
        b.blockSignals(False)
        self.char_view.show_chars(name, codes)
        self.char_view.set_allow_drag_and_drop(False)

    def initialize(self):
        if not self.initialized:
            self.category_view.initialize()

    def sizeHint(self):
        return QSize(800, 600)

    def show_char_info(self, char_code):
        if char_code > 0:
            category_name, subcategory_name, character_name = self.category_view.model().get_char_info(char_code)
            self.char_info.setText('%s - %s - %s (U+%04X)' % (category_name, subcategory_name, character_name, char_code))
        else:
            self.char_info.clear()

    def show(self):
        self.initialize()
        Dialog.show(self)
        self.raise_()

    def char_selected(self, c):
        if QApplication.keyboardModifiers() & Qt.CTRL:
            self.hide()
        if self.parent() is None or self.parent().focusWidget() is None:
            QApplication.clipboard().setText(c)
            return
        self.parent().activateWindow()
        w = self.parent().focusWidget()
        e = QInputMethodEvent('', [])
        e.setCommitString(c)
        if hasattr(w, 'no_popup'):
            oval = w.no_popup
            w.no_popup = True
        QApplication.sendEvent(w, e)
        if hasattr(w, 'no_popup'):
            w.no_popup = oval

if __name__ == '__main__':
    app = QApplication([])
    w = CharSelect()
    w.initialize()
    w.show()
    app.exec_()
