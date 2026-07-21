from collections.abc import Callable, Iterator

ok: int
icu_version: str
unicode_version: str

USET_SPAN_NOT_CONTAINED: int
USET_SPAN_CONTAINED: int
USET_SPAN_SIMPLE: int
UCOL_DEFAULT: int
UCOL_PRIMARY: int
UCOL_SECONDARY: int
UCOL_TERTIARY: int
UCOL_DEFAULT_STRENGTH: int
UCOL_QUATERNARY: int
UCOL_IDENTICAL: int
UCOL_OFF: int
UCOL_ON: int
UCOL_SHIFTED: int
UCOL_NON_IGNORABLE: int
UCOL_LOWER_FIRST: int
UCOL_UPPER_FIRST: int
UCOL_FRENCH_COLLATION: int
UCOL_ALTERNATE_HANDLING: int
UCOL_CASE_FIRST: int
UCOL_CASE_LEVEL: int
UCOL_NORMALIZATION_MODE: int
UCOL_DECOMPOSITION_MODE: int
UCOL_STRENGTH: int
UCOL_NUMERIC_COLLATION: int
UCOL_REORDER_CODE_SPACE: int
UCOL_REORDER_CODE_PUNCTUATION: int
UCOL_REORDER_CODE_SYMBOL: int
UCOL_REORDER_CODE_CURRENCY: int
UCOL_REORDER_CODE_DEFAULT: int

NFD: int
NFKD: int
NFC: int
NFKC: int

UPPER_CASE: int
LOWER_CASE: int
TITLE_CASE: int

UBRK_CHARACTER: int
UBRK_WORD: int
UBRK_LINE: int
UBRK_SENTENCE: int

class Collator:
    "Collator"

    def __init__(self, locale: str) -> None:
        "Create a Collator for the specified locale."
        pass

    def sort_key(self, unicode_object: str) -> bytes:
        (
            "sort_key(unicode object) -> Return a sort key for the given object as a bytestring. The idea is that these bytestring will sort using the builtin"
            " cmp function, just like the original unicode strings would sort in the current locale with ICU."
        )
        pass

    def get_attribute(self, key: int) -> int:
        "get_attribute(key) -> get the specified attribute on this collator."
        pass

    def set_attribute(self, key: int, val: int) -> None:
        "set_attribute(key, val) -> set the specified attribute on this collator."
        pass

    def strcmp(self, a: str, b: str) -> int:
        "strcmp(unicode object, unicode object) -> strcmp(a, b) <=> cmp(sorty_key(a), sort_key(b)), but faster."
        pass

    def find_all(self, pattern: str, source: str, callback: Callable[[int, int], object], whole_words: bool = False) -> None:
        (
            "find(pattern, source, callback) -> reports the position and length of all occurrences of pattern in source to callback. Aborts if callback returns"
            " anything other than None."
        )
        pass

    def find(self, pattern: str, source: str, whole_words: bool = False) -> tuple[int, int]:
        "find(pattern, source) -> returns the position and length of the first occurrence of pattern in source. Returns (-1, -1) if not found."
        pass

    def contains(self, pattern: str, source: str) -> bool:
        "contains(pattern, source) -> return True iff the pattern was found in the source."
        pass

    def contractions(self) -> tuple[str | None, ...]:
        "contractions() -> returns the contractions defined for this collator."
        pass

    def clone(self) -> Collator:
        "clone() -> returns a clone of this collator."
        pass

    def startswith(self, a: str, b: str, offset: int = 0) -> bool:
        "startswith(a, b, offset=0) -> returns True iff a startswith b at the given codepoint offset, following the current collation rules."
        pass

    def collation_order(self, string: str) -> tuple[int, int]:
        (
            "collation_order(string) -> returns (order, length) where order is an integer that gives the position of string in a list. length gives the number"
            " of characters used for order."
        )
        pass

    @property
    def actual_locale(self) -> str:
        "Actual locale used by this collator."
        pass

    @property
    def capsule(self) -> object:
        "A capsule enclosing the pointer to the ICU collator struct"
        pass

    @property
    def display_name(self) -> str:
        "Display name of this collator in English. The name reflects the actual data source used."
        pass

    @property
    def strength(self) -> int:
        "The strength of this collator."
        pass

    @strength.setter
    def strength(self, val: int) -> None:
        pass

    @property
    def upper_first(self) -> bool | None:
        (
            "Whether this collator should always put upper case letters before lower case. Values are: None - means use the tertiary strength of the letters."
            " True - Always sort upper case before lower case. False - Always sort lower case before upper case."
        )
        pass

    @upper_first.setter
    def upper_first(self, val: bool | None) -> None:
        pass

    @property
    def numeric(self) -> bool:
        "If True the collator sorts contiguous digits as numbers rather than strings, so 2 will sort before 10."
        pass

    @numeric.setter
    def numeric(self, val: bool) -> None:
        pass

    @property
    def max_variable(self) -> int:
        "The highest sorting character affected by alternate handling"
        pass

    @max_variable.setter
    def max_variable(self, val: int) -> None:
        pass

class Transliterator:
    "Transliterator"

    def __init__(self, id: str, rules: str, forward: bool = True) -> None:
        "Create a Transliterator with the specified id compiled from the specified rules."
        pass

    def transliterate(self, text: str) -> str:
        "transliterate(text) -> Run the transliterator on the specified text"
        pass

class BreakIterator:
    (
        "BreakIterator(type, locale[, extra_word_break_chars]) -> Create a break iterator.\nFor UBRK_WORD iterators, extra_word_break_chars is an optional"
        " string of characters\nthat act as additional word-break points beyond the ICU defaults."
    )

    def __init__(self, type: int, locale: str, extra_word_break_chars: str | None = None) -> None:
        "Create a break iterator of the specified type (one of UBRK_CHARACTER, UBRK_WORD, UBRK_LINE, UBRK_SENTENCE) for the specified locale."
        pass

    def set_text(self, unicode_object: str) -> None:
        "set_text(unicode object) -> Set the text this iterator will operate on"
        pass

    def split2(self) -> list[tuple[int, int]]:
        (
            "split2() -> Split the current text into tokens, returning a list of 2-tuples of the form (position of token, length of token). The numbers are"
            " suitable for indexing python strings regardless of narrow/wide builds."
        )
        pass

    def iter_breaks(self) -> Iterator[tuple[int, int]]:
        (
            "iter_breaks() -> Split the current text into tokens, returning an iterator that yields 2-tuples of the form (position of token, length of token)."
            " The numbers are suitable for indexing python strings regardless of narrow/wide builds."
        )
        pass

    def iter_positions(self) -> Iterator[int]:
        (
            "iter_positions() -> Split the current text into tokens, returning an iterator that yields the position of each token as an integer. The numbers"
            " are suitable for indexing python strings regardless of narrow/wide builds."
        )
        pass

    def count_words(self) -> int:
        "count_words() -> Split the current text into tokens as in split2() and count the number of tokens."
        pass

    def index(self, token: str) -> int:
        (
            "index(token) -> Find the index of the first match for token. Useful to find, for example, words that could also be a part of a larger word. For"
            " example, index('i') in 'string i' will be 7 not 3. Returns -1 if not found."
        )
        pass

def change_case(unicode_object: str, which: int, locale: str | bytes | None) -> str:
    "change_case(unicode object, which, locale) -> change case to one of UPPER_CASE, LOWER_CASE, TITLE_CASE"
    pass

def swap_case(unicode_object: str) -> str:
    "swap_case(unicode object) -> swaps the case using the simple, locale independent unicode algorithm"
    pass

def set_default_encoding(encoding: object = None) -> None:
    "set_default_encoding(encoding) -> Set the default encoding for the python unicode implementation. In Py3, this operation is a no-op"
    pass

def set_filesystem_encoding(encoding: str | bytes) -> None:
    "set_filesystem_encoding(encoding) -> Set the filesystem encoding for python."
    pass

def get_available_transliterators() -> list[str]:
    "get_available_transliterators() -> Return list of available transliterators. This list is rather limited on OS X."
    pass

def character_name(char: str, alias: bool = False) -> str:
    "character_name(char, alias=False) -> Return name for the first character in char, which must be a unicode string."
    pass

def character_name_from_code(code: int, alias: bool = False) -> str:
    "character_name_from_code(code, alias=False) -> Return the name for the specified unicode code point"
    pass

def chr(code: int) -> str:
    (
        "chr(code) -> Return a python unicode string corresponding to the specified character code. The string can have length 1 or 2 (for non BMP codes on"
        " narrow python builds)."
    )
    pass

def ord_string(code: str) -> tuple[int, ...]:
    "ord_string(code) -> Convert a python unicode string to a tuple of unicode codepoints."
    pass

def normalize(mode: int, unicode_text: str) -> str:
    "normalize(mode, unicode_text) -> Return a python unicode string which is normalized in the specified mode."
    pass

def roundtrip(string: str) -> str:
    "roundtrip(string) -> Roundtrip a unicode object from python to ICU back to python (useful for testing)"
    pass

def available_locales_for_break_iterator() -> tuple[bytes, ...]:
    "available_locales_for_break_iterator() -> Return tuple of all available locales for the BreakIterator"
    pass

def string_length(string: str) -> int:
    (
        "string_length(string) -> Return the length of a string (number of unicode code points in the string). Useful on narrow python builds where len()"
        " returns an incorrect answer if the string contains surrogate pairs."
    )
    pass

def utf16_length(string: str) -> int:
    (
        "utf16_length(string) -> Return the length of a string (number of UTF-16 code points in the string). Useful on wide python builds where len() returns"
        " an incorrect answer if the string contains surrogate pairs."
    )
    pass

def word_prefix_find(collator: Collator, break_iterator: BreakIterator, string: str, prefix: str) -> int:
    (
        "word_prefix_find(collator, break_iterator, string, prefix) -> Return the codepoint offset of the first word in string that starts with prefix"
        " according to collator, or -1 if none."
    )
    pass
