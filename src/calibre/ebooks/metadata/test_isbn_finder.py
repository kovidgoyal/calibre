#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import unittest

from calibre.ebooks.metadata.isbn_finder import MIN_PART_LENGTH, find_isbn

PRINT, EBOOK, OTHER, ISBN10 = '9780306406157', '9783161484100', '9781861978769', '0306406152'


class TestISBNFinder(unittest.TestCase):
    def test_find_isbn(self):
        filler = 'Some text of the book. ' * (MIN_PART_LENGTH // 10)
        for text, expected in (
            ('Copyright 2020\nISBN 978-0-306-40615-7 (hardcover)\nISBN 978-3-16-148410-0 (ebook)\n', EBOOK),
            ('ISBN: 978-0-306-40615-7\nISBN: 978-3-16-148410-0\n', PRINT),
            ('ISBN-10: 0-306-40615-2\n', ISBN10),
            ('isbn 0 306 40615 2\n', ISBN10),
            # No-break space and non-breaking hyphens
            ('ISBN' + chr(0xA0) + chr(0x2011).join(('978', '0', '306', '40615', '7')) + '\n', PRINT),
            ('e-ISBN 9783161484100, print ISBN 9780306406157\n', EBOOK),
            # Invalid check digits and numbers that are not labeled as ISBNs
            ('ISBN 978-0-306-40615-8\nCall 0306406152 for details.\n', None),
            ('Printed in 2020. 978-0-306-40615-7\n', PRINT),
            # The front of the book is preferred over the rest
            ('ISBN 978-0-306-40615-7\n' + filler + '\nAlso by the author, ISBN 978-1-86197-876-9\n', PRINT),
            ('Title page\n' + filler + filler + '\nAlso available: ISBN 978-1-86197-876-9\n' + filler + filler + filler, None),
            (filler + '\nCopyright page\nISBN 978-1-86197-876-9\n', OTHER),
            # Labeled ISBNs are preferred over unlabeled ones
            ('978-0-306-40615-7\nISBN 978-3-16-148410-0\n', EBOOK),
            ('', None),
        ):
            with self.subTest(text=text[:60]):
                self.assertEqual(find_isbn(text), expected)


def find_tests():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestISBNFinder)


if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(find_tests())
