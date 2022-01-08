#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import re
import textwrap
from bisect import bisect
from functools import partial
from qt.core import (
    QAbstractItemModel, QAbstractListModel, QApplication, QCheckBox, QGridLayout,
    QHBoxLayout, QIcon, QInputMethodEvent, QLabel, QListView, QMenu, QMimeData,
    QModelIndex, QPen, QPushButton, QSize, QSizePolicy, QSplitter,
    QStyledItemDelegate, Qt, QToolButton, QTreeView, pyqtSignal, QAbstractItemView, QDialogButtonBox
)

from calibre.gui2.tweak_book import tprefs
from calibre.gui2.tweak_book.widgets import BusyCursor, Dialog
from calibre.gui2.widgets2 import HistoryLineEdit2
from calibre.utils.icu import safe_chr as codepoint_to_chr
from calibre.utils.unicode_names import character_name_from_code, points_for_word
from calibre_extensions.progress_indicator import set_no_activate_on_click

ROOT = QModelIndex()

non_printing = {
    0xa0: 'nbsp', 0x2000: 'nqsp', 0x2001: 'mqsp', 0x2002: 'ensp', 0x2003: 'emsp', 0x2004: '3/msp', 0x2005: '4/msp', 0x2006: '6/msp',
    0x2007: 'fsp', 0x2008: 'psp', 0x2009: 'thsp', 0x200A: 'hsp', 0x200b: 'zwsp', 0x200c: 'zwnj', 0x200d: 'zwj', 0x200e: 'lrm', 0x200f: 'rlm',
    0x2028: 'lsep', 0x2029: 'psep', 0x202a: 'rle', 0x202b: 'lre', 0x202c: 'pdp', 0x202d: 'lro', 0x202e: 'rlo', 0x202f: 'nnbsp',
    0x205f: 'mmsp', 0x2060: 'wj', 0x2061: 'fa', 0x2062: 'x', 0x2063: ',', 0x2064: '+', 0x206A: 'iss', 0x206b: 'ass', 0x206c: 'iafs', 0x206d: 'aafs',
    0x206e: 'nads', 0x206f: 'nods', 0x20: 'sp', 0x7f: 'del', 0x2e3a: '2m', 0x2e3b: '3m', 0xad: 'shy',
}


# Searching {{{
def search_for_chars(query, and_tokens=False):
    ans = set()
    for i, token in enumerate(query.split()):
        token = token.lower()
        m = re.match(r'(?:[u]\+)([a-f0-9]+)', token)
        if m is not None:
            chars = {int(m.group(1), 16)}
        else:
            chars = points_for_word(token)
        if chars is not None:
            if and_tokens:
                ans = chars if i == 0 else (ans & chars)
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
    (_('Cypriot syllabary'), (0x10800, 0x1083F)),
    (_('Cyrillic'), (0x400, 0x4FF)),
    (_('Cyrillic supplement'), (0x500, 0x52F)),
    (_('Cyrillic extended A'), (0x2DE0, 0x2DFF)),
    (_('Cyrillic extended B'), (0xA640, 0xA69F)),
    (_('Georgian'), (0x10A0, 0x10FF)),
    (_('Georgian supplement'), (0x2D00, 0x2D2F)),
    (_('Glagolitic'), (0x2C00, 0x2C5F)),
    (_('Gothic'), (0x10330, 0x1034F)),
    (_('Greek and Coptic'), (0x370, 0x3FF)),
    (_('Greek extended'), (0x1F00, 0x1FFF)),
    (_('Latin, Basic & Latin-1 supplement'), (0x20, 0xFF)),
    (_('Latin extended A'), (0x100, 0x17F)),
    (_('Latin extended B'), (0x180, 0x24F)),
    (_('Latin extended C'), (0x2C60, 0x2C7F)),
    (_('Latin extended D'), (0xA720, 0xA7FF)),
    (_('Latin extended additional'), (0x1E00, 0x1EFF)),
    (_('Latin ligatures'), (0xFB00, 0xFB06)),
    (_('Fullwidth Latin letters'), (0xFF00, 0xFF5E)),
    (_('Linear B syllabary'), (0x10000, 0x1007F)),
    (_('Linear B ideograms'), (0x10080, 0x100FF)),
    (_('Ogham'), (0x1680, 0x169F)),
    (_('Old italic'), (0x10300, 0x1032F)),
    (_('Phaistos disc'), (0x101D0, 0x101FF)),
    (_('Runic'), (0x16A0, 0x16FF)),
    (_('Shavian'), (0x10450, 0x1047F)),
)),

(_('Phonetic symbols'), (
    (_('IPA extensions'), (0x250, 0x2AF)),
    (_('Phonetic extensions'), (0x1D00, 0x1D7F)),
    (_('Phonetic extensions supplement'), (0x1D80, 0x1DBF)),
    (_('Modifier tone letters'), (0xA700, 0xA71F)),
    (_('Spacing modifier letters'), (0x2B0, 0x2FF)),
    (_('Superscripts and subscripts'), (0x2070, 0x209F)),
)),

(_('Combining diacritics'), (
    (_('Combining diacritical marks'), (0x300, 0x36F)),
    (_('Combining diacritical marks for symbols'), (0x20D0, 0x20FF)),
    (_('Combining diacritical marks supplement'), (0x1DC0, 0x1DFF)),
    (_('Combining half marks'), (0xFE20, 0xFE2F)),
)),

(_('African scripts'), (
    (_('Bamum'), (0xA6A0, 0xA6FF)),
    (_('Bamum supplement'), (0x16800, 0x16A3F)),
    (_('Egyptian hieroglyphs'), (0x13000, 0x1342F)),
    (_('Ethiopic'), (0x1200, 0x137F)),
    (_('Ethiopic supplement'), (0x1380, 0x139F)),
    (_('Ethiopic extended'), (0x2D80, 0x2DDF)),
    (_('Ethiopic extended A'), (0xAB00, 0xAB2F)),
    (_('Meroitic cursive'), (0x109A0, 0x109FF)),
    (_('Meroitic hieroglyphs'), (0x10980, 0x1099F)),
    (_('N\'Ko'), (0x7C0, 0x7FF)),
    (_('Osmanya'), (0x10480, 0x104AF)),
    (_('Tifinagh'), (0x2D30, 0x2D7F)),
    (_('Vai'), (0xA500, 0xA63F)),
)),

(_('Middle Eastern scripts'), (
    (_('Arabic'), (0x600, 0x6FF)),
    (_('Arabic supplement'), (0x750, 0x77F)),
    (_('Arabic extended A'), (0x8A0, 0x8FF)),
    (_('Arabic presentation forms A'), (0xFB50, 0xFDFF)),
    (_('Arabic presentation forms B'), (0xFE70, 0xFEFF)),
    (_('Avestan'), (0x10B00, 0x10B3F)),
    (_('Carian'), (0x102A0, 0x102DF)),
    (_('Cuneiform'), (0x12000, 0x123FF)),
    (_('Cuneiform numbers and punctuation'), (0x12400, 0x1247F)),
    (_('Hebrew'), (0x590, 0x5FF)),
    (_('Hebrew presentation forms'), (0xFB1D, 0xFB4F)),
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

(_('Central Asian scripts'), (
    (_('Mongolian'), (0x1800, 0x18AF)),
    (_('Old Turkic'), (0x10C00, 0x10C4F)),
    (_('Phags-pa'), (0xA840, 0xA87F)),
    (_('Tibetan'), (0xF00, 0xFFF)),
)),

(_('South Asian scripts'), (
    (_('Bengali'), (0x980, 0x9FF)),
    (_('Brahmi'), (0x11000, 0x1107F)),
    (_('Chakma'), (0x11100, 0x1114F)),
    (_('Devanagari'), (0x900, 0x97F)),
    (_('Devanagari extended'), (0xA8E0, 0xA8FF)),
    (_('Gujarati'), (0xA80, 0xAFF)),
    (_('Gurmukhi'), (0xA00, 0xA7F)),
    (_('Kaithi'), (0x11080, 0x110CF)),
    (_('Kannada'), (0xC80, 0xCFF)),
    (_('Kharoshthi'), (0x10A00, 0x10A5F)),
    (_('Lepcha'), (0x1C00, 0x1C4F)),
    (_('Limbu'), (0x1900, 0x194F)),
    (_('Malayalam'), (0xD00, 0xD7F)),
    (_('Meetei Mayek'), (0xABC0, 0xABFF)),
    (_('Meetei Mayek extensions'), (0xAAE0, 0xAAEF)),
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
    (_('Vedic extensions'), (0x1CD0, 0x1CFF)),
)),

(_('Southeast Asian scripts'), (
    (_('Balinese'), (0x1B00, 0x1B7F)),
    (_('Batak'), (0x1BC0, 0x1BFF)),
    (_('Buginese'), (0x1A00, 0x1A1F)),
    (_('Cham'), (0xAA00, 0xAA5F)),
    (_('Javanese'), (0xA980, 0xA9DF)),
    (_('Kayah Li'), (0xA900, 0xA92F)),
    (_('Khmer'), (0x1780, 0x17FF)),
    (_('Khmer symbols'), (0x19E0, 0x19FF)),
    (_('Lao'), (0xE80, 0xEFF)),
    (_('Myanmar'), (0x1000, 0x109F)),
    (_('Myanmar extended A'), (0xAA60, 0xAA7F)),
    (_('New Tai Lue'), (0x1980, 0x19DF)),
    (_('Rejang'), (0xA930, 0xA95F)),
    (_('Sundanese'), (0x1B80, 0x1BBF)),
    (_('Sundanese supplement'), (0x1CC0, 0x1CCF)),
    (_('Tai Le'), (0x1950, 0x197F)),
    (_('Tai Tham'), (0x1A20, 0x1AAF)),
    (_('Tai Viet'), (0xAA80, 0xAADF)),
    (_('Thai'), (0xE00, 0xE7F)),
)),

(_('Philippine scripts'), (
    (_('Buhid'), (0x1740, 0x175F)),
    (_('Hanunoo'), (0x1720, 0x173F)),
    (_('Tagalog'), (0x1700, 0x171F)),
    (_('Tagbanwa'), (0x1760, 0x177F)),
)),

(_('East Asian scripts'), (
    (_('Bopomofo'), (0x3100, 0x312F)),
    (_('Bopomofo extended'), (0x31A0, 0x31BF)),
    (_('CJK Unified ideographs'), (0x4E00, 0x9FFF)),
    (_('CJK Unified ideographs extension A'), (0x3400, 0x4DBF)),
    (_('CJK Unified ideographs extension B'), (0x20000, 0x2A6DF)),
    (_('CJK Unified ideographs extension C'), (0x2A700, 0x2B73F)),
    (_('CJK Unified ideographs extension D'), (0x2B740, 0x2B81F)),
    (_('CJK compatibility ideographs'), (0xF900, 0xFAFF)),
    (_('CJK compatibility ideographs supplement'), (0x2F800, 0x2FA1F)),
    (_('Kangxi radicals'), (0x2F00, 0x2FDF)),
    (_('CJK radicals supplement'), (0x2E80, 0x2EFF)),
    (_('CJK strokes'), (0x31C0, 0x31EF)),
    (_('Ideographic description characters'), (0x2FF0, 0x2FFF)),
    (_('Hiragana'), (0x3040, 0x309F)),
    (_('Katakana'), (0x30A0, 0x30FF)),
    (_('Katakana phonetic extensions'), (0x31F0, 0x31FF)),
    (_('Kana supplement'), (0x1B000, 0x1B0FF)),
    (_('Halfwidth Katakana'), (0xFF65, 0xFF9F)),
    (_('Kanbun'), (0x3190, 0x319F)),
    (_('Hangul syllables'), (0xAC00, 0xD7AF)),
    (_('Hangul Jamo'), (0x1100, 0x11FF)),
    (_('Hangul Jamo extended A'), (0xA960, 0xA97F)),
    (_('Hangul Jamo extended B'), (0xD7B0, 0xD7FF)),
    (_('Hangul compatibility Jamo'), (0x3130, 0x318F)),
    (_('Halfwidth Jamo'), (0xFFA0, 0xFFDC)),
    (_('Lisu'), (0xA4D0, 0xA4FF)),
    (_('Miao'), (0x16F00, 0x16F9F)),
    (_('Yi syllables'), (0xA000, 0xA48F)),
    (_('Yi radicals'), (0xA490, 0xA4CF)),
)),

(_('American scripts'), (
    (_('Cherokee'), (0x13A0, 0x13FF)),
    (_('Deseret'), (0x10400, 0x1044F)),
    (_('Unified Canadian aboriginal syllabics'), (0x1400, 0x167F)),
    (_('UCAS extended'), (0x18B0, 0x18FF)),
)),

(_('Other'), (
    (_('Alphabetic presentation forms'), (0xFB00, 0xFB4F)),
    (_('Halfwidth and Fullwidth forms'), (0xFF00, 0xFFEF)),
)),

(_('Punctuation'), (
    (_('General punctuation'), (0x2000, 0x206F)),
    (_('ASCII punctuation'), (0x21, 0x7F)),
    (_('Cuneiform numbers and punctuation'), (0x12400, 0x1247F)),
    (_('Latin-1 punctuation'), (0xA1, 0xBF)),
    (_('Small form variants'), (0xFE50, 0xFE6F)),
    (_('Supplemental punctuation'), (0x2E00, 0x2E7F)),
    (_('CJK symbols and punctuation'), (0x3000, 0x303F)),
    (_('CJK compatibility forms'), (0xFE30, 0xFE4F)),
    (_('Fullwidth ASCII punctuation'), (0xFF01, 0xFF60)),
    (_('Vertical forms'), (0xFE10, 0xFE1F)),
)),

(_('Alphanumeric symbols'), (
    (_('Arabic mathematical alphabetic symbols'), (0x1EE00, 0x1EEFF)),
    (_('Letterlike symbols'), (0x2100, 0x214F)),
    (_('Roman symbols'), (0x10190, 0x101CF)),
    (_('Mathematical alphanumeric symbols'), (0x1D400, 0x1D7FF)),
    (_('Enclosed alphanumerics'), (0x2460, 0x24FF)),
    (_('Enclosed alphanumeric supplement'), (0x1F100, 0x1F1FF)),
    (_('Enclosed CJK letters and months'), (0x3200, 0x32FF)),
    (_('Enclosed ideographic supplement'), (0x1F200, 0x1F2FF)),
    (_('CJK compatibility'), (0x3300, 0x33FF)),
)),

(_('Technical symbols'), (
    (_('Miscellaneous technical'), (0x2300, 0x23FF)),
    (_('Control pictures'), (0x2400, 0x243F)),
    (_('Optical character recognition'), (0x2440, 0x245F)),
)),

(_('Numbers and digits'), (
    (_('Aegean numbers'), (0x10100, 0x1013F)),
    (_('Ancient Greek numbers'), (0x10140, 0x1018F)),
    (_('Common Indic number forms'), (0xA830, 0xA83F)),
    (_('Counting rod numerals'), (0x1D360, 0x1D37F)),
    (_('Cuneiform numbers and punctuation'), (0x12400, 0x1247F)),
    (_('Fullwidth ASCII digits'), (0xFF10, 0xFF19)),
    (_('Number forms'), (0x2150, 0x218F)),
    (_('Rumi numeral symbols'), (0x10E60, 0x10E7F)),
    (_('Superscripts and subscripts'), (0x2070, 0x209F)),
)),

(_('Mathematical symbols'), (
    (_('Arrows'), (0x2190, 0x21FF)),
    (_('Supplemental arrows A'), (0x27F0, 0x27FF)),
    (_('Supplemental arrows B'), (0x2900, 0x297F)),
    (_('Miscellaneous symbols and arrows'), (0x2B00, 0x2BFF)),
    (_('Mathematical alphanumeric symbols'), (0x1D400, 0x1D7FF)),
    (_('Letterlike symbols'), (0x2100, 0x214F)),
    (_('Mathematical operators'), (0x2200, 0x22FF)),
    (_('Miscellaneous mathematical symbols A'), (0x27C0, 0x27EF)),
    (_('Miscellaneous mathematical symbols B'), (0x2980, 0x29FF)),
    (_('Supplemental mathematical operators'), (0x2A00, 0x2AFF)),
    (_('Ceilings and floors'), (0x2308, 0x230B)),
    (_('Geometric shapes'), (0x25A0, 0x25FF)),
    (_('Box drawing'), (0x2500, 0x257F)),
    (_('Block elements'), (0x2580, 0x259F)),
)),

(_('Musical symbols'), (
    (_('Musical symbols'), (0x1D100, 0x1D1FF)),
    (_('More musical symbols'), (0x2669, 0x266F)),
    (_('Ancient Greek musical notation'), (0x1D200, 0x1D24F)),
    (_('Byzantine musical symbols'), (0x1D000, 0x1D0FF)),
)),

(_('Game symbols'), (
    (_('Chess'), (0x2654, 0x265F)),
    (_('Domino tiles'), (0x1F030, 0x1F09F)),
    (_('Draughts'), (0x26C0, 0x26C3)),
    (_('Japanese chess'), (0x2616, 0x2617)),
    (_('Mahjong tiles'), (0x1F000, 0x1F02F)),
    (_('Playing cards'), (0x1F0A0, 0x1F0FF)),
    (_('Playing card suits'), (0x2660, 0x2667)),
)),

(_('Other symbols'), (
    (_('Alchemical symbols'), (0x1F700, 0x1F77F)),
    (_('Ancient symbols'), (0x10190, 0x101CF)),
    (_('Braille patterns'), (0x2800, 0x28FF)),
    (_('Currency symbols'), (0x20A0, 0x20CF)),
    (_('Combining diacritical marks for symbols'), (0x20D0, 0x20FF)),
    (_('Dingbats'), (0x2700, 0x27BF)),
    (_('Emoticons'), (0x1F600, 0x1F64F)),
    (_('Miscellaneous symbols'), (0x2600, 0x26FF)),
    (_('Miscellaneous symbols and arrows'), (0x2B00, 0x2BFF)),
    (_('Miscellaneous symbols and pictographs'), (0x1F300, 0x1F5FF)),
    (_('Yijing hexagram symbols'), (0x4DC0, 0x4DFF)),
    (_('Yijing mono and digrams'), (0x268A, 0x268F)),
    (_('Yijing trigrams'), (0x2630, 0x2637)),
    (_('Tai Xuan Jing symbols'), (0x1D300, 0x1D35F)),
    (_('Transport and map symbols'), (0x1F680, 0x1F6FF)),
)),

(_('Other'), (
    (_('Specials'), (0xFFF0, 0xFFFF)),
    (_('Tags'), (0xE0000, 0xE007F)),
    (_('Variation selectors'), (0xFE00, 0xFE0F)),
    (_('Variation selectors supplement'), (0xE0100, 0xE01EF)),
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
        self.fav_icon = QIcon.ic('rating.png')

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

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        pid = index.internalId()
        if pid == 0:
            if role == Qt.ItemDataRole.DisplayRole:
                return self.categories[index.row()][0]
            if role == Qt.ItemDataRole.FontRole:
                return self.bold_font
            if role == Qt.ItemDataRole.DecorationRole and index.row() == 0:
                return self.fav_icon
        else:
            if role == Qt.ItemDataRole.DisplayRole:
                item = self.categories[pid - 1][1][index.row()]
                return item[0]
        return None

    def get_range(self, index):
        if index.isValid():
            pid = index.internalId()
            if pid == 0:
                if index.row() == 0:
                    return (_('Favorites'), list(tprefs['charmap_favorites']))
            else:
                item = self.categories[pid - 1][1][index.row()]
                return (item[0], list(range(item[1][0], item[1][1] + 1)))

    def get_char_info(self, char_code):
        ipos = bisect(self.starts, char_code) - 1
        try:
            category, subcategory = self.category_map[self.starts[ipos]]
        except IndexError:
            category = subcategory = _('Unknown')
        return category, subcategory, character_name_from_code(char_code)


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
        set_no_activate_on_click(self)
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
        if role == Qt.ItemDataRole.UserRole and -1 < index.row() < len(self.chars):
            return self.chars[index.row()]
        return None

    def flags(self, index):
        ans = Qt.ItemFlag.ItemIsEnabled
        if self.allow_dnd:
            ans |= Qt.ItemFlag.ItemIsSelectable
            ans |= Qt.ItemFlag.ItemIsDragEnabled if index.isValid() else Qt.ItemFlag.ItemIsDropEnabled
        return ans

    def supportedDropActions(self):
        return Qt.DropAction.MoveAction

    def mimeTypes(self):
        return ['application/calibre_charcode_indices']

    def mimeData(self, indexes):
        data = ','.join(str(i.row()) for i in indexes)
        md = QMimeData()
        md.setData('application/calibre_charcode_indices', data.encode('utf-8'))
        return md

    def dropMimeData(self, md, action, row, column, parent):
        if action != Qt.DropAction.MoveAction or not md.hasFormat('application/calibre_charcode_indices') or row < 0 or column != 0:
            return False
        indices = list(map(int, bytes(md.data('application/calibre_charcode_indices')).decode('ascii').split(',')))
        codes = [self.chars[x] for x in indices]
        for x in indices:
            self.chars[x] = None
        for x in reversed(codes):
            self.chars.insert(row, x)
        self.beginResetModel()
        self.chars = [x for x in self.chars if x is not None]
        self.endResetModel()
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
        try:
            charcode = int(index.data(Qt.ItemDataRole.UserRole))
        except (TypeError, ValueError):
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
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom | Qt.TextFlag.TextSingleLine, codepoint_to_chr(charcode))

    def paint_non_printing(self, painter, option, charcode):
        text = self.np_pat.sub(r'\n\1', non_printing[charcode])
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap | Qt.TextFlag.TextWrapAnywhere, text)
        painter.setPen(QPen(Qt.PenStyle.DashLine))
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
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setItemDelegate(self.delegate)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setMouseTracking(True)
        self.setSpacing(2)
        self.setUniformItemSizes(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)
        self.showing_favorites = False
        set_no_activate_on_click(self)
        self.activated.connect(self.item_activated)
        self.clicked.connect(self.item_activated)

    def item_activated(self, index):
        try:
            char_code = int(self.model().data(index, Qt.ItemDataRole.UserRole))
        except (TypeError, ValueError):
            pass
        else:
            self.char_selected.emit(codepoint_to_chr(char_code))

    def set_allow_drag_and_drop(self, enabled):
        if not enabled:
            self.setDragEnabled(False)
            self.viewport().setAcceptDrops(False)
            self.setDropIndicatorShown(True)
            self._model.allow_dnd = False
        else:
            self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            self.viewport().setAcceptDrops(True)
            self.setDragEnabled(True)
            self.setAcceptDrops(True)
            self.setDropIndicatorShown(False)
            self._model.allow_dnd = True

    def show_chars(self, name, codes):
        self.showing_favorites = name == _('Favorites')
        self._model.beginResetModel()
        self._model.chars = codes
        self._model.endResetModel()
        self.scrollToTop()

    def mouseMoveEvent(self, ev):
        index = self.indexAt(ev.pos())
        if index.isValid():
            row = index.row()
            if row != self.last_mouse_idx:
                self.last_mouse_idx = row
                try:
                    char_code = int(self.model().data(index, Qt.ItemDataRole.UserRole))
                except (TypeError, ValueError):
                    pass
                else:
                    self.show_name.emit(char_code)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.show_name.emit(-1)
            self.last_mouse_idx = -1
        return QListView.mouseMoveEvent(self, ev)

    def context_menu(self, pos):
        index = self.indexAt(pos)
        if index.isValid():
            try:
                char_code = int(self.model().data(index, Qt.ItemDataRole.UserRole))
            except (TypeError, ValueError):
                pass
            else:
                m = QMenu(self)
                m.addAction(QIcon.ic('edit-copy.png'), _('Copy %s to clipboard') % codepoint_to_chr(char_code), partial(self.copy_to_clipboard, char_code))
                m.addAction(QIcon.ic('rating.png'),
                            (_('Remove %s from favorites') if self.showing_favorites else _('Add %s to favorites')) % codepoint_to_chr(char_code),
                            partial(self.remove_from_favorites, char_code))
                if self.showing_favorites:
                    m.addAction(_('Restore favorites to defaults'), self.restore_defaults)
                m.exec(self.mapToGlobal(pos))

    def restore_defaults(self):
        del tprefs['charmap_favorites']
        self.model().beginResetModel()
        self.model().chars = list(tprefs['charmap_favorites'])
        self.model().endResetModel()

    def copy_to_clipboard(self, char_code):
        c = QApplication.clipboard()
        c.setText(codepoint_to_chr(char_code))

    def remove_from_favorites(self, char_code):
        existing = tprefs['charmap_favorites']
        if not self.showing_favorites:
            if char_code not in existing:
                tprefs['charmap_favorites'] = [char_code] + existing
        elif char_code in existing:
            existing.remove(char_code)
            tprefs['charmap_favorites'] = existing
            self.model().beginResetModel()
            self.model().chars.remove(char_code)
            self.model().endResetModel()


class CharSelect(Dialog):

    def __init__(self, parent=None):
        self.initialized = False
        Dialog.__init__(self, _('Insert character'), 'charmap_dialog', parent)
        self.setWindowIcon(QIcon.ic('character-set.png'))
        self.setFocusProxy(parent)

    def setup_ui(self):
        self.l = l = QGridLayout(self)
        self.setLayout(l)

        self.bb.setStandardButtons(QDialogButtonBox.StandardButton.Close)
        self.rearrange_button = b = self.bb.addButton(_('Re-arrange favorites'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setCheckable(True)
        b.setChecked(False)
        b.setVisible(False)
        b.setDefault(True)

        self.splitter = s = QSplitter(self)
        s.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        s.setChildrenCollapsible(False)

        self.search = h = HistoryLineEdit2(self)
        h.setToolTip(textwrap.fill(_(
            'Search for Unicode characters by using the English names or nicknames.'
            ' You can also search directly using a character code. For example, the following'
            ' searches will all yield the no-break space character: U+A0, nbsp, no-break')))
        h.initialize('charmap_search')
        h.setPlaceholderText(_('Search by name, nickname or character code'))
        self.search_button = b = QPushButton(_('&Search'))
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        h.returnPressed.connect(self.do_search)
        b.clicked.connect(self.do_search)
        self.clear_button = cb = QToolButton(self)
        cb.setIcon(QIcon.ic('clear_left.png'))
        cb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        cb.setText(_('Clear search'))
        cb.clicked.connect(self.clear_search)
        l.addWidget(h), l.addWidget(b, 0, 1), l.addWidget(cb, 0, 2)

        self.category_view = CategoryView(self)
        self.category_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.category_view.clicked.connect(self.category_view_clicked)
        l.addWidget(s, 1, 0, 1, 3)
        self.char_view = CharView(self)
        self.char_view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.rearrange_button.toggled[bool].connect(self.set_allow_drag_and_drop)
        self.category_view.category_selected.connect(self.show_chars)
        self.char_view.show_name.connect(self.show_char_info)
        self.char_view.char_selected.connect(self.char_selected)
        s.addWidget(self.category_view), s.addWidget(self.char_view)

        self.char_info = la = QLabel('\xa0')
        la.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        l.addWidget(la, 2, 0, 1, 3)

        self.rearrange_msg = la = QLabel(_(
            'Drag and drop characters to re-arrange them. Click the "Re-arrange" button again when you are done.'))
        la.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        la.setVisible(False)
        l.addWidget(la, 3, 0, 1, 3)
        self.h = h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        self.match_any = mm = QCheckBox(_('Match any word'))
        mm.setToolTip(_('When searching return characters whose names match any of the specified words'))
        mm.setChecked(tprefs.get('char_select_match_any', True))
        connect_lambda(mm.stateChanged, self, lambda self: tprefs.set('char_select_match_any', self.match_any.isChecked()))
        h.addWidget(mm), h.addStretch(), h.addWidget(self.bb)
        l.addLayout(h, 4, 0, 1, 3)
        self.char_view.setFocus(Qt.FocusReason.OtherFocusReason)

    def category_view_clicked(self):
        p = self.parent()
        if p is not None and p.focusWidget() is not None:
            p.activateWindow()

    def do_search(self):
        text = str(self.search.text()).strip()
        if not text:
            return self.clear_search()
        with BusyCursor():
            chars = search_for_chars(text, and_tokens=not self.match_any.isChecked())
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
        text = '\xa0'
        if char_code > 0:
            category_name, subcategory_name, character_name = self.category_view.model().get_char_info(char_code)
            text = _('{character_name} (U+{char_code:04X}) in {category_name} - {subcategory_name}').format(**locals())
        self.char_info.setText(text)

    def show(self):
        self.initialize()
        Dialog.show(self)
        self.raise_()

    def char_selected(self, c):
        if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier:
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
    from calibre.gui2 import Application
    app = Application([])
    w = CharSelect()
    w.initialize()
    w.show()
    app.exec()
