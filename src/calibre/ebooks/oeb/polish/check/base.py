#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from contextlib import closing
from functools import partial
from multiprocessing.pool import ThreadPool

from calibre import detect_ncpus as cpu_count

DEBUG, INFO, WARN, ERROR, CRITICAL = range(5)


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

    def __init__(self, msg, name, line=None, col=None):
        self.msg, self.line, self.col = msg, line, col
        self.name = name
        # A list with entries of the form: (name, lnum, col)
        self.all_locations = None

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

    def __str__(self):
        return f'{self.__class__.__name__}:{self.name} ({self.line}, {self.col}):{self.msg}'

    __repr__ = __str__


def worker(func, args):
    try:
        result = func(*args)
        tb = None
    except Exception:
        result = None
        import traceback

        tb = traceback.format_exc()
    return result, tb


def run_checkers(func, args_list):
    num = cpu_count()
    pool = ThreadPool(num)
    ans = []
    with closing(pool):
        for result, tb in pool.map(partial(worker, func), args_list):
            if tb is not None:
                raise Exception(f'Failed to run worker: \n{tb}')
            ans.extend(result)
    return ans
