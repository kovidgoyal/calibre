#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os, re
from collections import namedtuple

from calibre.ebooks.docx.block_styles import binary_property, inherit
from calibre.utils.filenames import ascii_filename
from calibre.utils.fonts.scanner import font_scanner, NoFonts
from calibre.utils.fonts.utils import panose_to_css_generic_family, is_truetype_font
from calibre.utils.icu import ord_string
from polyglot.builtins import codepoint_to_chr, iteritems

Embed = namedtuple('Embed', 'name key subsetted')


def has_system_fonts(name):
    try:
        return bool(font_scanner.fonts_for_family(name))
    except NoFonts:
        return False


def get_variant(bold=False, italic=False):
    return {(False, False):'Regular', (False, True):'Italic',
            (True, False):'Bold', (True, True):'BoldItalic'}[(bold, italic)]


def find_fonts_matching(fonts, style='normal', stretch='normal'):
    for font in fonts:
        if font['font-style'] == style and font['font-stretch'] == stretch:
            yield font


def weight_key(font):
    w = font['font-weight']
    try:
        return abs(int(w) - 400)
    except Exception:
        return abs({'normal': 400, 'bold': 700}.get(w, 1000000) - 400)


def get_best_font(fonts, style, stretch):
    try:
        return sorted(find_fonts_matching(fonts, style, stretch), key=weight_key)[0]
    except Exception:
        pass


class Family:

    def __init__(self, elem, embed_relationships, XPath, get):
        self.name = self.family_name = get(elem, 'w:name')
        self.alt_names = tuple(get(x, 'w:val') for x in XPath('./w:altName')(elem))
        if self.alt_names and not has_system_fonts(self.name):
            for x in self.alt_names:
                if has_system_fonts(x):
                    self.family_name = x
                    break

        self.embedded = {}
        for x in ('Regular', 'Bold', 'Italic', 'BoldItalic'):
            for y in XPath('./w:embed%s[@r:id]' % x)(elem):
                rid = get(y, 'r:id')
                key = get(y, 'w:fontKey')
                subsetted = get(y, 'w:subsetted') in {'1', 'true', 'on'}
                if rid in embed_relationships:
                    self.embedded[x] = Embed(embed_relationships[rid], key, subsetted)

        self.generic_family = 'auto'
        for x in XPath('./w:family[@w:val]')(elem):
            self.generic_family = get(x, 'w:val', 'auto')

        ntt = binary_property(elem, 'notTrueType', XPath, get)
        self.is_ttf = ntt is inherit or not ntt

        self.panose1 = None
        self.panose_name = None
        for x in XPath('./w:panose1[@w:val]')(elem):
            try:
                v = get(x, 'w:val')
                v = tuple(int(v[i:i+2], 16) for i in range(0, len(v), 2))
            except (TypeError, ValueError, IndexError):
                pass
            else:
                self.panose1 = v
                self.panose_name = panose_to_css_generic_family(v)

        self.css_generic_family = {'roman':'serif', 'swiss':'sans-serif', 'modern':'monospace',
                                   'decorative':'fantasy', 'script':'cursive'}.get(self.generic_family, None)
        self.css_generic_family = self.css_generic_family or self.panose_name or 'serif'


SYMBOL_MAPS = {  # {{{
    'Wingdings': (' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', '🖉', '✂', '✁', '👓', '🕭', '🕮', '🕯', '🕿', '✆', '🖂', '🖃', '📪', '📫', '📬', '📭', '🗀', '🗁', '🗎', '🗏', '🗐', '🗄', '⏳', '🖮', '🖰', '🖲', '🖳', '🖴', '🖫', '🖬', '✇', '✍', '🖎', '✌', '🖏', '👍', '👎', '☜', '☞', '☜', '🖗', '🖐', '☺', '😐', '☹', '💣', '🕱', '🏳', '🏱', '✈', '☼', '🌢', '❄', '🕆', '✞', '🕈', '✠', '✡', '☪', '☯', '🕉', '☸', '♈', '♉', '♊', '♋', '♌', '♍', '♎', '♏', '♐', '♑', '♒', '♓', '🙰', '🙵', '⚫', '🔾', '◼', '🞏', '🞐', '❑', '❒', '🞟', '⧫', '◆', '❖', '🞙', '⌧', '⮹', '⌘', '🏵', '🏶', '🙶', '🙷', ' ', '🄋', '➀', '➁', '➂', '➃', '➄', '➅', '➆', '➇', '➈', '➉', '🄌', '➊', '➋', '➌', '➍', '➎', '➏', '➐', '➑', '➒', '➓', '🙢', '🙠', '🙡', '🙣', '🙦', '🙤', '🙥', '🙧', '∙', '•', '⬝', '⭘', '🞆', '🞈', '🞊', '🞋', '🔿', '▪', '🞎', '🟀', '🟁', '★', '🟋', '🟏', '🟓', '🟑', '⯐', '⌖', '⯎', '⯏', '⯑', '✪', '✰', '🕐', '🕑', '🕒', '🕓', '🕔', '🕕', '🕖', '🕗', '🕘', '🕙', '🕚', '🕛', '⮰', '⮱', '⮲', '⮳', '⮴', '⮵', '⮶', '⮷', '🙪', '🙫', '🙕', '🙔', '🙗', '🙖', '🙐', '🙑', '🙒', '🙓', '⌫', '⌦', '⮘', '⮚', '⮙', '⮛', '⮈', '⮊', '⮉', '⮋', '🡨', '🡪', '🡩', '🡫', '🡬', '🡭', '🡯', '🡮', '🡸', '🡺', '🡹', '🡻', '🡼', '🡽', '🡿', '🡾', '⇦', '⇨', '⇧', '⇩', '⬄', '⇳', '⬁', '⬀', '⬃', '⬂', '🢬', '🢭', '🗶', '✓', '🗷', '🗹', ' '),  # noqa

    'Wingdings 2': (' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', '🖊', '🖋', '🖌', '🖍', '✄', '✀', '🕾', '🕽', '🗅', '🗆', '🗇', '🗈', '🗉', '🗊', '🗋', '🗌', '🗍', '📋', '🗑', '🗔', '🖵', '🖶', '🖷', '🖸', '🖭', '🖯', '🖱', '🖒', '🖓', '🖘', '🖙', '🖚', '🖛', '👈', '👉', '🖜', '🖝', '🖞', '🖟', '🖠', '🖡', '👆', '👇', '🖢', '🖣', '🖑', '🗴', '🗸', '🗵', '☑', '⮽', '☒', '⮾', '⮿', '🛇', '⦸', '🙱', '🙴', '🙲', '🙳', '‽', '🙹', '🙺', '🙻', '🙦', '🙤', '🙥', '🙧', '🙚', '🙘', '🙙', '🙛', '⓪', '①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩', '⓿', '❶', '❷', '❸', '❹', '❺', '❻', '❼', '❽', '❾', '❿', ' ', '☉', '🌕', '☽', '☾', '⸿', '✝', '🕇', '🕜', '🕝', '🕞', '🕟', '🕠', '🕡', '🕢', '🕣', '🕤', '🕥', '🕦', '🕧', '🙨', '🙩', '⋅', '🞄', '⦁', '●', '●', '🞅', '🞇', '🞉', '⊙', '⦿', '🞌', '🞍', '◾', '■', '□', '🞑', '🞒', '🞓', '🞔', '▣', '🞕', '🞖', '🞗', '🞘', '⬩', '⬥', '◇', '🞚', '◈', '🞛', '🞜', '🞝', '🞞', '⬪', '⬧', '◊', '🞠', '◖', '◗', '⯊', '⯋', '⯀', '⯁', '⬟', '⯂', '⬣', '⬢', '⯃', '⯄', '🞡', '🞢', '🞣', '🞤', '🞥', '🞦', '🞧', '🞨', '🞩', '🞪', '🞫', '🞬', '🞭', '🞮', '🞯', '🞰', '🞱', '🞲', '🞳', '🞴', '🞵', '🞶', '🞷', '🞸', '🞹', '🞺', '🞻', '🞼', '🞽', '🞾', '🞿', '🟀', '🟂', '🟄', '🟆', '🟉', '🟊', '✶', '🟌', '🟎', '🟐', '🟒', '✹', '🟃', '🟇', '✯', '🟍', '🟔', '⯌', '⯍', '※', '⁂', ' ', ' ', ' ', ' ', ' ', ' ',),  # noqa

    'Wingdings 3': (' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', '⭠', '⭢', '⭡', '⭣', '⭤', '⭥', '⭧', '⭦', '⭰', '⭲', '⭱', '⭳', '⭶', '⭸', '⭻', '⭽', '⭤', '⭥', '⭪', '⭬', '⭫', '⭭', '⭍', '⮠', '⮡', '⮢', '⮣', '⮤', '⮥', '⮦', '⮧', '⮐', '⮑', '⮒', '⮓', '⮀', '⮃', '⭾', '⭿', '⮄', '⮆', '⮅', '⮇', '⮏', '⮍', '⮎', '⮌', '⭮', '⭯', '⎋', '⌤', '⌃', '⌥', '␣', '⍽', '⇪', '⮸', '🢠', '🢡', '🢢', '🢣', '🢤', '🢥', '🢦', '🢧', '🢨', '🢩', '🢪', '🢫', '🡐', '🡒', '🡑', '🡓', '🡔', '🡕', '🡗', '🡖', '🡘', '🡙', '▲', '▼', '△', '▽', '◀', '▶', '◁', '▷', '◣', '◢', '◤', '◥', '🞀', '🞂', '🞁', ' ', '🞃', '⯅', '⯆', '⯇', '⯈', '⮜', '⮞', '⮝', '⮟', '🠐', '🠒', '🠑', '🠓', '🠔', '🠖', '🠕', '🠗', '🠘', '🠚', '🠙', '🠛', '🠜', '🠞', '🠝', '🠟', '🠀', '🠂', '🠁', '🠃', '🠄', '🠆', '🠅', '🠇', '🠈', '🠊', '🠉', '🠋', '🠠', '🠢', '🠤', '🠦', '🠨', '🠪', '🠬', '🢜', '🢝', '🢞', '🢟', '🠮', '🠰', '🠲', '🠴', '🠶', '🠸', '🠺', '🠹', '🠻', '🢘', '🢚', '🢙', '🢛', '🠼', '🠾', '🠽', '🠿', '🡀', '🡂', '🡁', '🡃', '🡄', '🡆', '🡅', '🡇', '⮨', '⮩', '⮪', '⮫', '⮬', '⮭', '⮮', '⮯', '🡠', '🡢', '🡡', '🡣', '🡤', '🡥', '🡧', '🡦', '🡰', '🡲', '🡱', '🡳', '🡴', '🡵', '🡷', '🡶', '🢀', '🢂', '🢁', '🢃', '🢄', '🢅', '🢇', '🢆', '🢐', '🢒', '🢑', '🢓', '🢔', '🢕', '🢗', '🢖', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ',),  # noqa

    'Webdings': (' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', '🕷', '🕸', '🕲', '🕶', '🏆', '🎖', '🖇', '🗨', '🗩', '🗰', '🗱', '🌶', '🎗', '🙾', '🙼', '🗕', '🗖', '🗗', '⏴', '⏵', '⏶', '⏷', '⏪', '⏩', '⏮', '⏭', '⏸', '⏹', '⏺', '🗚', '🗳', '🛠', '🏗', '🏘', '🏙', '🏚', '🏜', '🏭', '🏛', '🏠', '🏖', '🏝', '🛣', '🔍', '🏔', '👁', '👂', '🏞', '🏕', '🛤', '🏟', '🛳', '🕬', '🕫', '🕨', '🔈', '🎔', '🎕', '🗬', '🙽', '🗭', '🗪', '🗫', '⮔', '✔', '🚲', '⬜', '🛡', '📦', '🛱', '⬛', '🚑', '🛈', '🛩', '🛰', '🟈', '🕴', '⬤', '🛥', '🚔', '🗘', '🗙', '❓', '🛲', '🚇', '🚍', '⛳', '⦸', '⊖', '🚭', '🗮', '⏐', '🗯', '🗲', ' ', '🚹', '🚺', '🛉', '🛊', '🚼', '👽', '🏋', '⛷', '🏂', '🏌', '🏊', '🏄', '🏍', '🏎', '🚘', '🗠', '🛢', '📠', '🏷', '📣', '👪', '🗡', '🗢', '🗣', '✯', '🖄', '🖅', '🖃', '🖆', '🖹', '🖺', '🖻', '🕵', '🕰', '🖽', '🖾', '📋', '🗒', '🗓', '🕮', '📚', '🗞', '🗟', '🗃', '🗂', '🖼', '🎭', '🎜', '🎘', '🎙', '🎧', '💿', '🎞', '📷', '🎟', '🎬', '📽', '📹', '📾', '📻', '🎚', '🎛', '📺', '💻', '🖥', '🖦', '🖧', '🍹', '🎮', '🎮', '🕻', '🕼', '🖁', '🖀', '🖨', '🖩', '🖿', '🖪', '🗜', '🔒', '🔓', '🗝', '📥', '📤', '🕳', '🌣', '🌤', '🌥', '🌦', '☁', '🌨', '🌧', '🌩', '🌪', '🌬', '🌫', '🌜', '🌡', '🛋', '🛏', '🍽', '🍸', '🛎', '🛍', 'Ⓟ', '♿', '🛆', '🖈', '🎓', '🗤', '🗥', '🗦', '🗧', '🛪', '🐿', '🐦', '🐟', '🐕', '🐈', '🙬', '🙮', '🙭', '🙯', '🗺', '🌍', '🌏', '🌎', '🕊',),  # noqa

    'Symbol': (' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', '!', '∀', '#', '∃', '%', '&', '∍', '(', ')', '*', '+', ',', '−', '.', '/', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', ':', ';', '<', '=', '>', '?', '≅', 'Α', 'Β', 'Χ', 'Δ', 'Ε', 'Φ', 'Γ', 'Η', 'Ι', 'ϑ', 'Λ', 'Μ', 'Ν', 'Ξ', 'Ο', 'Π', 'Θ', 'Ρ', 'Σ', 'Τ', 'Υ', 'ς', 'Ω', 'Ξ', 'Ψ', 'Ζ', '[', '∴', ']', '⊥', '_', '', 'α', 'β', 'χ', 'δ', 'ε', 'φ', 'γ', 'η', 'ι', 'ϕ', 'λ', 'μ', 'ν', 'ξ', 'ο', 'π', 'θ', 'ρ', 'σ', 'τ', 'υ', 'ϖ', 'ω', 'ξ', 'ψ', 'ζ', '{', '|', '}', '~', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', ' ', '€', 'ϒ', '′', '≤', '⁄', '∞', 'ƒ', '♣', '♥', '♦', '♠', '↔', '←', '↑', '→', '↓', '°', '±', '″', '≥', '×', '∝', '∂', '•', '÷', '≠', '≡', '≈', '…', '⏐', '⎯', '↲', 'ℵ', 'ℑ', 'ℜ', '℘', '⊗', '⊕', '∅', '∩', '∪', '⊃', '⊇', '⊄', '⊂', '⊆', '∈', '∉', '∠', '∂', '®', '©', '™', '∏', '√', '⋅', '¬', '∦', '∧', '⇔', '⇐', '⇑', '⇒', '⇓', '◊', '〈', '®', '©', '™', '∑', '⎛', '⎜', '⎝', '⎡', '⎢', '⎣', '⎧', '⎨', '⎩', '⎪', ' ', '〉', '∫', '⌠', '⎮', '⌡', '⎞', '⎟', '⎠', '⎤', '⎥', '⎦', '⎪', '⎫', '⎬', ' ',),  # noqa
}  # }}}

SYMBOL_FONT_NAMES = frozenset(n.lower() for n in SYMBOL_MAPS)


def is_symbol_font(family):
    try:
        return family.lower() in SYMBOL_FONT_NAMES
    except AttributeError:
        return False


def do_map(m, points):
    base = 0xf000
    limit = len(m) + base
    for p in points:
        if base < p < limit:
            yield m[p - base]
        else:
            yield codepoint_to_chr(p)


def map_symbol_text(text, font):
    m = SYMBOL_MAPS[font]
    if isinstance(text, bytes):
        text = text.decode('utf-8')
    return ''.join(do_map(m, ord_string(text)))


class Fonts:

    def __init__(self, namespace):
        self.namespace = namespace
        self.fonts = {}
        self.used = set()

    def __call__(self, root, embed_relationships, docx, dest_dir):
        for elem in self.namespace.XPath('//w:font[@w:name]')(root):
            self.fonts[self.namespace.get(elem, 'w:name')] = Family(elem, embed_relationships, self.namespace.XPath, self.namespace.get)

    def family_for(self, name, bold=False, italic=False):
        f = self.fonts.get(name, None)
        if f is None:
            return 'serif'
        variant = get_variant(bold, italic)
        self.used.add((name, variant))
        name = f.name if variant in f.embedded else f.family_name
        if is_symbol_font(name):
            return name
        return '"{}", {}'.format(name.replace('"', ''), f.css_generic_family)

    def embed_fonts(self, dest_dir, docx):
        defs = []
        dest_dir = os.path.join(dest_dir, 'fonts')
        for name, variant in self.used:
            f = self.fonts[name]
            if variant in f.embedded:
                if not os.path.exists(dest_dir):
                    os.mkdir(dest_dir)
                fname = self.write(name, dest_dir, docx, variant)
                if fname is not None:
                    d = {'font-family':'"%s"' % name.replace('"', ''), 'src': 'url("fonts/%s")' % fname}
                    if 'Bold' in variant:
                        d['font-weight'] = 'bold'
                    if 'Italic' in variant:
                        d['font-style'] = 'italic'
                    d = [f'{k}: {v}' for k, v in iteritems(d)]
                    d = ';\n\t'.join(d)
                    defs.append('@font-face {\n\t%s\n}\n' % d)
        return '\n'.join(defs)

    def write(self, name, dest_dir, docx, variant):
        f = self.fonts[name]
        ef = f.embedded[variant]
        raw = docx.read(ef.name)
        prefix = raw[:32]
        if ef.key:
            key = re.sub(r'[^A-Fa-f0-9]', '', ef.key)
            key = bytearray(reversed(tuple(int(key[i:i+2], 16) for i in range(0, len(key), 2))))
            prefix = bytearray(prefix)
            prefix = bytes(bytearray(prefix[i]^key[i % len(key)] for i in range(len(prefix))))
        if not is_truetype_font(prefix):
            return None
        ext = 'otf' if prefix.startswith(b'OTTO') else 'ttf'
        fname = ascii_filename(f'{name} - {variant}.{ext}').replace(' ', '_').replace('&', '_')
        with open(os.path.join(dest_dir, fname), 'wb') as dest:
            dest.write(prefix)
            dest.write(raw[32:])

        return fname
