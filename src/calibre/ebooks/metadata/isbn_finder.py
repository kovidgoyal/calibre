#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

# Find the ISBN of a book in its text, usually on its copyright page

import re
from collections.abc import Callable, Iterator

from calibre.ebooks.metadata import check_isbn

ISBN_NUMBER = r'(97[89](?:[- ]?\d){10}|\d(?:[- ]?\d){8}[- ]?[\dXx])(?![\dXx])'
LABELED_ISBN = re.compile(r'\bISBN(?:-?1[03])?\b[^\w\n]{0,12}' + ISBN_NUMBER, re.IGNORECASE)
# Only 13 digit numbers starting with the ISBN prefixes are considered without
# an ISBN label, as many other numbers would pass the ISBN-10 check
UNLABELED_ISBN = re.compile(r'(?<![\d-])(97[89](?:[- ]?\d){10})(?!\d)')
EBOOK_WORDS = re.compile(r'e-?books?|e-?pub|electronic|digital|kindle|e-?isbn|online|pdf', re.IGNORECASE)
# Unicode hyphens, dashes and minus
DASHES = re.compile('[' + ''.join(map(chr, (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2212))) + ']')
# No-break and thin spaces
SPACES = re.compile('[' + ''.join(map(chr, (0xA0, 0x2007, 0x202F, 0x2009))) + ']')
# The parts of the book to look at: the copyright page is usually near the
# start, sometimes at the end. The rest of the text often has the ISBNs of
# other books.
FRONT_FRACTION, BACK_FRACTION, MIN_PART_LENGTH = 0.1, 0.05, 20000


def isbns_in(text: str, pat: re.Pattern) -> Iterator[tuple[str, bool]]:
    "Yield valid ISBNs in text along with whether they are marked as being for an ebook"
    for m in pat.finditer(text):
        isbn = check_isbn(m.group(1))
        if isbn:
            line_start = text.rfind('\n', 0, m.start()) + 1
            line_end = text.find('\n', m.end())
            line = text[line_start : line_end if line_end > -1 else len(text)]
            yield isbn, EBOOK_WORDS.search(line) is not None


def best_isbn(found: list[tuple[str, bool]]) -> str | None:
    for isbn, is_ebook in found:
        if is_ebook:
            return isbn
    return found[0][0] if found else None


def find_isbn(text: str) -> str | None:
    """
    Find the ISBN of a book in its text. ISBNs labeled as such near the start
    of the book are preferred, and if there are several, the one for the
    ebook edition is preferred.
    """
    text = SPACES.sub(' ', DASHES.sub('-', text))
    front_len = max(int(len(text) * FRONT_FRACTION), MIN_PART_LENGTH)
    back_len = max(int(len(text) * BACK_FRACTION), MIN_PART_LENGTH)
    front, back = text[:front_len], text[max(front_len, len(text) - back_len) :]
    for pat in (LABELED_ISBN, UNLABELED_ISBN):
        for part in (front, back):
            if ans := best_isbn(list(isbns_in(part, pat))):
                return ans
    return None


def find_isbn_in_book(path: str) -> str | None:
    from calibre.db.fts.text import extract_text

    return find_isbn(extract_text(path))


def find_isbns(books: list[tuple[int, str]], notification: Callable[[float, str], object] = lambda x, y: y) -> dict[int, str]:
    """
    Find the ISBNs of the specified books, a list of (book_id, path to book
    file). Used in a worker process. Returns a mapping of book_id to the ISBN
    or to an empty string if no ISBN was found or the book could not be read.
    """
    import traceback

    ans = {}
    for i, (book_id, path) in enumerate(books):
        try:
            ans[book_id] = find_isbn_in_book(path) or ''
        except Exception:
            traceback.print_exc()
            ans[book_id] = ''
        notification((i + 1) / len(books), '')
    return ans
