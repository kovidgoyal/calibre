# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid@kovidgoyal.net>

"""
Type definitions shared by multiple modules that have no natural home module.
Types that belong to a specific module should be defined there instead.
This module must only be imported inside TYPE_CHECKING blocks.
"""

from collections.abc import Callable, Iterator
from typing import IO, Protocol, TextIO, TypedDict


class PrintKwargs(TypedDict, total=False):
    sep: str | None
    end: str | None
    file: TextIO | None
    flush: bool


class PopenKwargs(TypedDict, total=False):
    stdin: int | IO[bytes] | None
    stdout: int | IO[bytes] | None
    stderr: int | IO[bytes] | None
    cwd: str | None
    creationflags: int


class RegexMatch(Protocol):
    "The subset of a match object from the regex module that is used in calibre"

    def span(self) -> tuple[int, int]: ...
    def group(self) -> str: ...
    def expand(self, template: str, /) -> str: ...


class RegexPattern(Protocol):
    "The subset of a compiled pattern from the regex module that is used in calibre"

    @property
    def flags(self) -> int: ...
    def search(self, string: str, /) -> RegexMatch | None: ...
    def fullmatch(self, string: str, /) -> RegexMatch | None: ...
    def subn(self, repl: str | Callable[[RegexMatch], str], string: str, /) -> tuple[str, int]: ...
    def findall(self, string: str, /) -> list[object]: ...
    def finditer(self, string: str, /) -> Iterator[RegexMatch]: ...
