# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid@kovidgoyal.net>

from collections.abc import Callable, Iterator
from typing import Protocol, TextIO, TypedDict


class PrintKwargs(TypedDict, total=False):
    sep: str | None
    end: str | None
    file: TextIO | None
    flush: bool


class RegexMatch(Protocol):
    "The subset of a match object from the regex module that is used by the editor"

    def span(self) -> tuple[int, int]: ...
    def group(self) -> str: ...
    def expand(self, template: str, /) -> str: ...


class RegexPattern(Protocol):
    "The subset of a compiled pattern from the regex module that is used by the editor"

    @property
    def flags(self) -> int: ...
    def search(self, string: str, /) -> RegexMatch | None: ...
    def fullmatch(self, string: str, /) -> RegexMatch | None: ...
    def subn(self, repl: str | Callable[[RegexMatch], str], string: str, /) -> tuple[str, int]: ...
    def findall(self, string: str, /) -> list[object]: ...
    def finditer(self, string: str, /) -> Iterator[RegexMatch]: ...
