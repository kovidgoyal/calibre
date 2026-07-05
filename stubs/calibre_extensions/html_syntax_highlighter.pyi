from collections.abc import Callable
from typing import Any

class Tag:
    name: str
    bold: bool
    italic: bool
    lang: str | None

    def __init__(self, name: str, bold: bool | None = None, italic: bool | None = None, lang: str | None = None) -> None:
        'Tag'
        pass

    def copy(self) -> Tag:
        'copy() -> Return a copy of this Tag'
        pass

class State:
    tag_being_defined: Tag | None
    tags: list[Tag]
    is_bold: bool
    is_italic: bool
    current_lang: str | None
    parse: int
    css_formats: Any
    sub_parser_state: Any
    default_lang: str | None
    attribute_name: str | None

    def __init__(self, tag_being_defined: Tag | None = None, tags: list[Tag] | None = None, is_bold: bool = False, is_italic: bool = False, current_lang: str | None = None, parse: int = 0, css_formats: Any = None, sub_parser_state: Any = None, default_lang: str | None = None, attribute_name: str | None = None) -> None:
        'State'
        pass

    def copy(self) -> State:
        'copy() -> Return a copy of this Tag'
        pass

bold_tags: frozenset[str]
italic_tags: frozenset[str]

def init(spell_property: Callable[..., Any], recognized: Callable[..., Any], split: Callable[..., Any]) -> None:
    'init()\n\n Initialize this module'
    pass

def check_spelling(text: str, text_len: int, fmt: Any, locale: Any, sfmt: Any, store_locale: bool) -> tuple[tuple[int, Any], ...]:
    'html_check_spelling()\n\n Speedup inner loop for spell check'
    pass
