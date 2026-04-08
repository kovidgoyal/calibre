#!/usr/bin/env python
# License: GPL v3 Copyright: 2026, calibre contributors

import unittest
from datetime import UTC
from unittest.mock import MagicMock

from calibre.gui2.library.annotations import get_group_key, get_group_keys_list
from calibre.utils.icu import primary_sort_key


def _make_result(book_id=1, annot_id=1, **extra):
    return {
        'book_id': book_id,
        'id': annot_id,
        'format': 'EPUB',
        'user_type': 'local',
        'user': 'viewer',
        'annotation': {},
        **extra,
    }


def _make_mock_db(field_for_map=None, field_metadata=None):
    '''
    Build a lightweight mock that satisfies grouping_key's db access:
      - db.field_for(field, bid): returns values from field_for_map
      - db.field_metadata: plain dict
    '''
    db = MagicMock()
    d = field_for_map or {}

    def _field_for(field, bid):
        if (field, bid) in d:
            return d[(field, bid)]
        return d.get(field)

    db.field_for.side_effect = _field_for
    db.field_metadata = field_metadata or {}
    return db


class GroupKeyTest(unittest.TestCase):

    def test_pubdate_year_buckets_without_day_in_format(self):
        from datetime import datetime

        from qt.core import QDateTime

        pub_dt = datetime(2005, 3, 1, 0, 0, 0, tzinfo=UTC)
        db = _make_mock_db(
            field_for_map={'pubdate': pub_dt},
            field_metadata={
                'pubdate': {
                    'datatype': 'datetime',
                    'display': {'date_format': 'MMM yyyy'},
                }
            },
        )
        (sort_key, label) = get_group_key(_make_result(), 'pubdate', db)

        expected_year = pub_dt.year
        current_year = QDateTime.currentDateTime().date().year()

        self.assertEqual(label, str(expected_year), 'Expected label to be the year string')
        self.assertEqual(sort_key, (current_year - expected_year, label), 'Expected sort key to be (years_past, label)')

    def test_pubdate_unknown_year_when_no_pubdate(self):
        from calibre.utils.iso8601 import UNDEFINED_DATE
        db = _make_mock_db(
            field_for_map={'pubdate': None},
            field_metadata={
                'pubdate': {
                    'datatype': 'datetime',
                    'display': {'date_format': 'MMM yyyy'},
                }
            },
        )
        (_, label) = get_group_key(_make_result(), 'pubdate', db)

        # When pubdate is None the code falls back to UNDEFINED_QDATETIME whose
        # year equals UNDEFINED_DATE.year; the label should be that year as a string.
        self.assertEqual(label, str(UNDEFINED_DATE.year), 'Expected label to be the undefined-date year string')

    def test_arbitrary_text_field_sorts_case_insensitively(self):
        db = _make_mock_db(
            field_for_map={'publisher': 'Tor Books'},
            field_metadata={'publisher': {'datatype': 'text'}},
        )
        (sort_key, label) = get_group_key(_make_result(), 'publisher', db)

        self.assertEqual(label, 'Tor Books')
        self.assertEqual(sort_key, (primary_sort_key('Tor Books'), 'Tor Books'))

    def test_arbitrary_float_field_uses_raw_value_as_sort_key(self):
        db = _make_mock_db(
            field_for_map={'series_index': 4.5},
            field_metadata={'series_index': {'datatype': 'float'}},
        )
        (sort_key, label) = get_group_key(_make_result(), 'series_index', db)

        self.assertEqual(label, '4.5')
        self.assertEqual(sort_key, (4.5, '4.5'))

    def test_missing_value_returns_unknown_sentinel(self):
        db = _make_mock_db(
            field_for_map={'publisher': None},
            field_metadata={'publisher': {'datatype': 'text'}},
        )
        (sort_key, _) = get_group_key(_make_result(), 'publisher', db)

        self.assertEqual(sort_key, (primary_sort_key(''),), 'Expected sort key to be the unknown sentinel')

    def test_annotation_level_field_read_from_result_dict(self):
        db = _make_mock_db(field_metadata={'format': {'datatype': 'text'}})
        result = _make_result(format='PDF')
        (_, label) = get_group_key(result, 'format', db)

        db.field_for.assert_not_called()
        self.assertEqual(label, 'PDF')

    def test_group_by_book_id_title(self):
        db = _make_mock_db(
            field_for_map={'title': 'The Great Gatsby'},
            field_metadata={},
        )
        result = _make_result(book_id=42)
        (sort_key, label) = get_group_key(result, 'title', db)

        self.assertEqual(label, 'The Great Gatsby')
        self.assertEqual(sort_key, (primary_sort_key('The Great Gatsby'), 42))

    def test_group_by_authors(self):
        db = _make_mock_db(
            field_for_map={'authors': ('F. Scott Fitzgerald',)},
            field_metadata={},
        )
        (sort_key, label) = get_group_key(_make_result(), 'authors', db)

        self.assertEqual(label, 'F. Scott Fitzgerald')
        self.assertIsInstance(sort_key[0], bytes)  # Don't test the implementation of authors_to_sort_string

    def test_group_by_authors_unknown_when_empty(self):
        db = _make_mock_db(
            field_for_map={'authors': ()},
            field_metadata={},
        )
        (_, label) = get_group_key(_make_result(), 'authors', db)

        self.assertEqual(label, 'Unknown author')

    def test_group_by_user(self):
        db = _make_mock_db(field_metadata={})
        result = _make_result(user_type='local', user='reader')
        (sort_key, label) = get_group_key(result, 'user', db)

        self.assertIsInstance(label, str)
        self.assertEqual(sort_key[0], primary_sort_key(label))

    def test_group_by_annot_timestamp_day_bucketing(self):
        from qt.core import QDateTime, Qt

        # Use an ISO timestamp from the annotation
        ts_iso = '2024-12-25T10:30:00.000Z'
        db = _make_mock_db(field_metadata={})
        result = _make_result(annotation={'timestamp': ts_iso})
        (sort_key, label) = get_group_key(result, 'annot_timestamp', db)

        # Parse the timestamp to verify sort key
        qdt = QDateTime.fromString(ts_iso, Qt.DateFormat.ISODate)
        self.assertTrue(qdt.isValid(), 'Test setup: timestamp should be valid')
        qdt = qdt.toLocalTime()
        qdate = qdt.date()
        today = QDateTime.currentDateTime().toLocalTime().date()
        expected_days_past = today.toJulianDay() - qdate.toJulianDay()

        # sort_key[0] is days_past, sort_key[1] is the formatted date label
        self.assertEqual(sort_key[0], expected_days_past)
        # Not asserting a particular label due to locale variations
        self.assertIsInstance(label, str)

    def test_group_by_annot_timestamp_with_invalid_date(self):
        db = _make_mock_db(field_metadata={})
        result = _make_result(annotation={'timestamp': 'invalid-timestamp'})
        (sort_key, _) = get_group_key(result, 'annot_timestamp', db)

        # Should use current date when parse fails
        self.assertIsInstance(sort_key[0], int)
        self.assertIsInstance(sort_key[1], str)

    def test_group_by_book_timestamp_uses_db_field(self):
        from datetime import datetime

        from qt.core import QDateTime, Qt
        ts_iso = '2023-06-15T08:00:00.000Z'
        ts_dt = datetime(2023, 6, 15, 8, 0, 0, tzinfo=UTC)
        db = _make_mock_db(
            field_for_map={'timestamp': ts_dt},
            field_metadata={
                'timestamp': {
                    'datatype': 'datetime',
                    'display': {'date_format': 'dd MMM yyyy'},
                }
            },
        )
        # Even if the annotation has its own timestamp, grouping by 'timestamp'
        # must use the book's Date Added value from the DB.
        result = _make_result(annotation={'timestamp': '2000-01-01T00:00:00.000Z'})
        (sort_key, label) = get_group_key(result, 'timestamp', db)

        qdt = QDateTime.fromString(ts_iso, Qt.DateFormat.ISODate).toLocalTime()
        qdate = qdt.date()
        today = QDateTime.currentDateTime().toLocalTime().date()
        expected_days_past = today.toJulianDay() - qdate.toJulianDay()

        self.assertEqual(sort_key[0], expected_days_past)
        self.assertIsInstance(label, str)


class GroupKeysListTest(unittest.TestCase):

    def test_single_valued_field_returns_one_entry(self):
        db = _make_mock_db(
            field_for_map={'publisher': 'Tor Books'},
            field_metadata={'publisher': {'datatype': 'text', 'is_multiple': {}}},
        )
        entries = get_group_keys_list(_make_result(), 'publisher', db)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1], 'Tor Books')

    def test_multi_valued_field_returns_one_entry_per_value(self):
        db = _make_mock_db(
            field_for_map={'tags': ('sci-fi', 'fantasy')},
            field_metadata={'tags': {'datatype': 'text', 'is_multiple': {'cache_to_list': ','}}},
        )
        entries = get_group_keys_list(_make_result(), 'tags', db)
        labels = [label for _, label in entries]
        self.assertEqual(sorted(labels), ['fantasy', 'sci-fi'])

    def test_multi_valued_field_empty_returns_ungrouped(self):
        from calibre.gui2.library.bookshelf_view import all_groupings
        db = _make_mock_db(
            field_for_map={'tags': ()},
            field_metadata={'tags': {'datatype': 'text', 'is_multiple': {'cache_to_list': ','}}},
        )
        entries = get_group_keys_list(_make_result(), 'tags', db)
        self.assertEqual(len(entries), 1)
        expected_label = all_groupings()['tags']
        self.assertEqual(entries[0][1], expected_label)

    def test_title_returns_one_entry(self):
        db = _make_mock_db(
            field_for_map={'title': 'Dune'},
            field_metadata={},
        )
        entries = get_group_keys_list(_make_result(), 'title', db)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1], 'Dune')

    def test_annot_timestamp_returns_one_entry(self):
        db = _make_mock_db(field_metadata={})
        result = _make_result(annotation={'timestamp': '2024-01-01T00:00:00.000Z'})
        entries = get_group_keys_list(result, 'annot_timestamp', db)
        self.assertEqual(len(entries), 1)

    def test_authors_multi_valued_returns_one_per_author(self):
        db = _make_mock_db(
            field_for_map={'authors': ('Alice', 'Bob')},
            field_metadata={'authors': {'datatype': 'text', 'is_multiple': {'cache_to_list': ','}}},
        )
        entries = get_group_keys_list(_make_result(), 'authors', db)
        labels = [label for _, label in entries]
        self.assertEqual(sorted(labels), ['Alice', 'Bob'])


def find_tests():
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(GroupKeyTest))
    suite.addTests(loader.loadTestsFromTestCase(GroupKeysListTest))
    return suite
