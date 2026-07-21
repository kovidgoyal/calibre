from typing import Any

class Token:
    is_container: bool
    type: str
    _as_css: str
    value: Any
    unit: str | None
    line: int
    column: int
    def __init__(self, type: str, as_css: str, value: Any, unit: str | None, line: int, column: int) -> None:
        "Token"
        pass
    def as_css(self) -> str:
        "as_css() -> Return the CSS representation of this token"
        pass

def tokenize_flat(css_source: str, ignore_comments: bool) -> list[Token]:
    "tokenize_flat(css_source, ignore_comments)\n\n Convert CSS source into a flat list of tokens"
    pass

def init(
    compiled_token_regexps: Any,
    unicode_unescape: Any,
    newline_unescape: Any,
    simple_unescape: Any,
    find_newlines: Any,
    token_dispatch: Any,
    compiled_token_indexes: dict[str, int],
    colon: str,
    scolon: str,
    lpar: str,
    rpar: str,
    lbrace: str,
    rbrace: str,
    lbox: str,
    rbox: str,
    delim_tok: str,
    integer: str,
    string_tok: str,
) -> None:
    "init()\n\nInitialize the module."
    pass

def cleanup() -> None:
    "cleanup()\n\nRelease resources allocated by init(). Safe to call multiple times."
    pass
