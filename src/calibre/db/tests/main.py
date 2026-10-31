#!/usr/bin/env python
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

from calibre.utils.run_tests import find_tests_in_package, run_tests

if TYPE_CHECKING:
    import unittest


def find_tests() -> unittest.TestSuite:

    return find_tests_in_package('calibre.db.tests')


if __name__ == '__main__':
    try:
        import init_calibre  # ruff: ignore[unused-import]
    except ImportError:
        pass
    run_tests(find_tests)
