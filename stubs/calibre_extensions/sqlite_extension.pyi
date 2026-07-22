FTS5_TOKENIZE_QUERY: int
FTS5_TOKENIZE_DOCUMENT: int
FTS5_TOKENIZE_PREFIX: int
FTS5_TOKENIZE_AUX: int
FTS5_TOKEN_COLOCATED: int

def get_locales_for_break_iteration() -> list[str]:
    "Get list of available locales for break iteration"
    pass

def set_ui_language(val: str) -> None:
    "Set the current UI language"
    pass

def tokenize(text: str, remove_diacritics: bool = True, flags: int = 4) -> list[dict[str, str | int]]:
    "Tokenize a string, useful for testing"
    pass

def stem(text: str, lang: str = 'en') -> str:
    "Stem a word in the specified language, defaulting to English"
    pass
