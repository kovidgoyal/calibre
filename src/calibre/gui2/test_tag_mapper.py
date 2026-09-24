#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, calibre contributors

import unittest

from calibre.gui2 import Application
from calibre.gui2.tag_mapper import DATA_ROLE, Rules


class RuleSearchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Application.instance() or Application([])

    def setUp(self):
        self.widget = Rules()
        self.rules = [
            {'action': 'remove', 'match_type': 'one_of', 'query': 'fiction', 'replace': ''},
            {'action': 'replace', 'match_type': 'has', 'query': 'science', 'replace': 'Sci-Fi'},
            {'action': 'replace', 'match_type': 'has', 'query': 'sci-fi books', 'replace': 'books'},
        ]
        self.widget.rules = self.rules

    def tearDown(self):
        self.widget.close()

    def test_searches_stored_fields_and_wraps_without_changing_rules(self):
        widget = self.widget
        widget.search_edit.setText('SCI-FI')
        self.assertEqual(widget.rule_list.currentRow(), 1)
        self.assertEqual(widget.search_status.text(), '2 matching rules')
        widget.next_button.click()
        self.assertEqual(widget.rule_list.currentRow(), 2)
        widget.next_button.click()
        self.assertEqual(widget.rule_list.currentRow(), 1)
        widget.previous_button.click()
        self.assertEqual(widget.rule_list.currentRow(), 2)
        self.assertEqual(widget.rules, self.rules)

    def test_no_match_leaves_selection_and_order_unchanged(self):
        widget = self.widget
        widget.rule_list.setCurrentRow(1)
        widget.search_edit.setText('absent term')
        self.assertEqual(widget.search_status.text(), 'No matching rules')
        self.assertEqual(widget.rule_list.currentRow(), 1)
        self.assertFalse(widget.next_button.isEnabled())
        self.assertEqual(widget.rules, self.rules)

    def test_matches_nested_string_values_after_rule_change(self):
        widget = self.widget
        widget.search_edit.setText('new class')
        self.assertEqual(widget.search_status.text(), 'No matching rules')
        rule = dict(self.rules[0], actions=[{'type': 'add', 'data': 'New Class'}])
        widget.rule_list.item(0).setData(DATA_ROLE, rule)
        widget.changed.emit()
        self.assertEqual(widget.search_status.text(), '1 matching rule')
        widget.next_button.click()
        self.assertEqual(widget.rule_list.currentRow(), 0)
        self.assertEqual(widget.rules[0]['actions'][0]['data'], 'New Class')

    def test_reload_and_remove_refresh_match_count(self):
        widget = self.widget
        widget.search_edit.setText('sci-fi')
        widget.rules = self.rules[:1]
        self.assertEqual(widget.search_status.text(), 'No matching rules')
        widget.rules = self.rules
        self.assertEqual(widget.search_status.text(), '2 matching rules')
        widget.rule_list.setCurrentRow(1)
        widget.remove_rules()
        self.assertEqual(widget.search_status.text(), '1 matching rule')
        self.assertEqual(widget.rules, [self.rules[0], self.rules[2]])


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(RuleSearchTest)
