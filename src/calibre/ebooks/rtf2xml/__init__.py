from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from io import TextIOWrapper


def open_for_read(path: str) -> TextIOWrapper:
    return open(path, encoding='utf-8', errors='replace')


def open_for_write(path: str, append: bool = False) -> TextIOWrapper:
    mode = 'a' if append else 'w'
    return open(path, mode, encoding='utf-8', errors='replace', newline='')
