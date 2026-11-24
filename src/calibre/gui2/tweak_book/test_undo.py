#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from calibre.gui2.tweak_book import undo
from calibre.gui2.tweak_book.undo import GlobalUndoHistory


class FakeContainer:
    "Stands in for a Container, the undo history only uses the root folder of its containers"

    def __init__(self, parent_dir: str) -> None:
        self.root = tempfile.mkdtemp(dir=parent_dir)


class UndoHistoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tdir = tempfile.mkdtemp()
        self.history = GlobalUndoHistory()

    def tearDown(self) -> None:
        shutil.rmtree(self.tdir, ignore_errors=True)

    def new_container(self) -> FakeContainer:
        return FakeContainer(self.tdir)

    def open_book_with_savepoints(self, num: int) -> list[FakeContainer]:
        containers = [self.new_container()]
        self.history.open_book(containers[0])
        for i in range(num):
            containers.append(self.new_container())
            self.history.add_savepoint(containers[-1], f'savepoint {i}')
        return containers

    def assert_exists(self, *containers: FakeContainer) -> None:
        for c in containers:
            self.assertTrue(os.path.isdir(c.root), f'Checkpoint folder was wrongly deleted: {c.root}')

    def assert_deleted(self, *containers: FakeContainer) -> None:
        for c in containers:
            self.assertFalse(os.path.exists(c.root), f'Checkpoint folder was not deleted: {c.root}')

    def test_new_savepoint_after_undo_deletes_redo_checkpoints(self) -> None:
        c = self.open_book_with_savepoints(3)
        self.assertIs(self.history.undo(), c[2])
        self.assertIs(self.history.undo(), c[1])
        new = self.new_container()
        self.history.add_savepoint(new, 'new')
        self.assertEqual([s.container for s in self.history.states], [c[0], c[1], new])
        self.assert_deleted(c[2], c[3])
        self.assert_exists(c[0], c[1], new)

    def test_exceeding_max_savepoints_deletes_oldest_checkpoints(self) -> None:
        with patch.object(undo, 'MAX_SAVEPOINTS', 3):
            c = self.open_book_with_savepoints(4)
        self.assertEqual([s.container for s in self.history.states], c[2:])
        self.assertEqual(self.history.pos, 2)
        self.assert_deleted(c[0], c[1])
        self.assert_exists(*c[2:])

    def test_rewind_savepoint_deletes_rewound_checkpoint(self) -> None:
        c = self.open_book_with_savepoints(2)
        self.assertIs(self.history.rewind_savepoint(), c[1])
        self.assert_deleted(c[2])
        self.assert_exists(c[0], c[1])

    def test_undo_and_redo_keep_checkpoints(self) -> None:
        c = self.open_book_with_savepoints(2)
        self.history.undo()
        self.history.undo()
        self.history.redo()
        self.assert_exists(*c)


def find_tests() -> unittest.TestSuite:
    return unittest.defaultTestLoader.loadTestsFromTestCase(UndoHistoryTest)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_cli

    run_cli(find_tests())
