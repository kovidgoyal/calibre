#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>


import io

from calibre.db.tests.base import BaseTest


class PageCountTest(BaseTest):

    ae = BaseTest.assertEqual

    def test_page_count_in_db(self):
        test_page_count_in_db(self)

    def test_page_count(self):
        from calibre.library.page_count import test_page_count
        test_page_count()


def test_page_count_in_db(self: BaseTest) -> None:
    from calibre.db.constants import Pages
    from calibre.library.page_count import CHARS_PER_PAGE
    from calibre.utils.podofo import sample_pdf_data
    txt_data = ('a ' * (2*CHARS_PER_PAGE + 10)).encode()
    db = self.init_cache()
    # test schema upgrade marked all books as needing scan
    def status():
        return set(db.backend.execute('SELECT pages,needs_scan FROM books_pages_link'))
    self.ae(status(), {(0,1)})
    self.ae(db.pages_needs_scan((1,2,19)), {1,2})
    counted = []
    db.maintain_page_counts.count_callback = counted.append
    db.maintain_page_counts.tick_event.clear()
    db.queue_pages_scan()
    db.maintain_page_counts.tick_event.wait()
    self.assertFalse(counted)
    self.ae(status(), {(-1,0)})
    self.ae(db.field_for('pages', 1), -1)
    # test that adding a format queues
    def add_format(fmt, data):
        db.maintain_page_counts.tick_event.clear()
        db.add_format(1, fmt, io.BytesIO(data), replace=True)
        db.maintain_page_counts.tick_event.wait()
    add_format('txt', txt_data)
    self.ae(status(), {(2,0),(-1,0)})
    self.ae(1, len(counted))
    p = db.get_pages(1)
    self.ae(p, Pages(2, p.algorithm, 'TXT', len(txt_data), p.timestamp))
    self.ae(db.field_for('pages', 1), 2)
    self.ae(db.get_metadata(1).pages, 2)
    self.ae(db.get_proxy_metadata(1).pages, 2)
    # test that re-adding the same format does not re-count
    add_format('txt', txt_data)
    self.ae(status(), {(2,0),(-1,0)})
    self.ae(1, len(counted))
    # test that re-adding a lower priority format does not re-count
    add_format('epub', txt_data)
    self.ae(status(), {(2,0),(-1,0)})
    self.ae(1, len(counted))
    # test that adding a higher priority format does recount
    add_format('pdf', sample_pdf_data())
    self.ae(2, len(counted))
    self.assertTrue(counted[-1].endswith('.pdf'))
    self.ae(status(), {(1,0),(-1,0)})
    p = db.get_pages(1)
    self.ae(p, Pages(1, p.algorithm, 'PDF', len(sample_pdf_data()), p.timestamp))
