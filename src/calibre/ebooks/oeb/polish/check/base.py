#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TYPE_CHECKING, Self

from calibre import detect_ncpus as cpu_count

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from calibre.ebooks.oeb.polish.container import Container

DEBUG, INFO, WARN, ERROR, CRITICAL = range(5)

#: A location of an error of the form: (name, lnum, col)
type ErrorLocation = tuple[str, int | None, int | None]


class BaseError:
    HELP = ''
    INDIVIDUAL_FIX = ''
    # A human readable name for the type of this error, used when displaying
    # the list of skipped rules. Defaults to the error message.
    RULE_NAME = ''
    level = ERROR
    has_multiple_locations = False
    # Set by the GUI to the index into all_locations the user activated
    current_location_index: int | None = None
    is_parsing_error = False
    # True for problems found by the optional accessibility checks
    is_accessibility_problem = False

    def __init__(self, msg: str, name: str, line: int | None = None, col: int | None = None) -> None:
        self.msg, self.line, self.col = msg, line, col
        self.name = name
        # A list with entries of the form: (name, lnum, col)
        self.all_locations: list[ErrorLocation] | None = None

    # Error types whose fix touches the whole book set this to True and
    # implement fix_batch() so that many errors can be fixed in a single pass
    has_batch_fix = False

    # Error types whose fix renames a file set this to True. They are fixed
    # after all other errors, as the other errors refer to files by name.
    renames_file = False

    if TYPE_CHECKING:
        # Errors that have INDIVIDUAL_FIX set implement this to fix the error,
        # returning False if nothing was changed
        def __call__(self, container: Container) -> bool | None: ...

    @classmethod
    def fix_batch(cls, container: Container, errors: Sequence[Self]) -> bool:
        """Fix all the specified errors, which must be instances of this
        class, with the same result as fixing them one by one, in order.
        Returns False if nothing was changed. Only called if has_batch_fix is
        True."""
        raise NotImplementedError(f'{cls.__name__} does not support fixing in batches')

    @property
    def rule_id(self) -> str:
        """A stable identifier for the type of this error, used to skip it"""
        return self.__class__.__name__

    @property
    def rule_name(self) -> str:
        return self.RULE_NAME or self.msg

    @property
    def can_be_skipped(self) -> bool:
        return not self.is_parsing_error

    def __str__(self) -> str:
        return f'{self.__class__.__name__}:{self.name} ({self.line}, {self.col}):{self.msg}'

    __repr__ = __str__


def worker[T](func: Callable[..., T], args: Sequence[object]) -> tuple[T | None, str | None]:
    try:
        result = func(*args)
        tb = None
    except Exception:
        result = None
        import traceback

        tb = traceback.format_exc()
    return result, tb


def run_checkers[T](func: Callable[..., Iterable[T]], args_list: Iterable[Sequence[object]]) -> list[T]:
    # Use concurrent.futures rather than multiprocessing.pool.ThreadPool as the
    # latter needs the multiprocessing resource tracker process for its
    # semaphores, which breaks if that process is not running
    ans: list[T] = []
    with ThreadPoolExecutor(max_workers=cpu_count()) as pool:
        for result, tb in pool.map(partial(worker, func), args_list):
            if tb is not None:
                raise Exception(f'Failed to run worker: \n{tb}')
            assert result is not None  # tb is None so result is the return value of func
            ans.extend(result)
    return ans
