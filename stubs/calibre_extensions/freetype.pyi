from collections.abc import Sequence

class FreeTypeError(Exception):
    pass

class FreeType:
    def __init__(self) -> None:
        'FreeType'
        pass

    def load_font(self, data: bytes) -> Face:
        'load_font(bytestring) -> Load a font from font data.'
        pass

class Face:
    def __init__(self, freetype: FreeType, data: bytes) -> None:
        'Face'
        pass

    @property
    def family_name(self) -> str:
        'The family name of this font.'
        pass

    @property
    def style_name(self) -> str:
        'The style name of this font.'
        pass

    def supports_text(self, char_codes: Sequence[int]) -> bool:
        'supports_text(sequence of unicode character codes) -> Return True iff this font has glyphs for all the specified characters.'
        pass

    def glyph_id(self, code: int) -> int:
        'glyph_id(character code) -> Returns the glyph id for the specified character code.'
        pass
