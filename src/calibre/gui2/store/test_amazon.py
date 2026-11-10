#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import unittest

from calibre.gui2.store.amazon_live import MONEY_PAT, parse_results


def result(
    asin: str,
    title: str,
    by_row: str,
    format_name: str = 'Kindle Edition',
    price: str = '€14.78',
    extra: str = '',
    cls: str = '',
    dp_slug: str = 'ebook',
) -> str:
    href = f'/Some-Title-{dp_slug}/dp/{asin}/ref=sr_1_1'
    return f'''<div data-component-type="s-search-result" data-asin="{asin}" data-index="1" class="s-result-item {cls}">
<img class="s-image" src="https://m.media-amazon.com/images/I/{asin}.jpg">
<a href="{href}"><h2><span>{title}</span></h2></a>
<div class="a-row">{by_row}</div>
<div class="a-row a-spacing-mini a-size-base a-color-base"><a class="a-size-base a-link-normal a-text-bold" href="{href}">{format_name}</a> </div>
<div class="a-row"><a href="{href}"><span class="a-price"><span class="a-offscreen">{price}</span><span aria-hidden="true">x</span></span></a></div>
{extra}
</div>'''


def by(*authors: str, label: str = 'by ', linked: bool = True) -> str:
    parts = [f'<span class="a-size-base">{label}</span>']
    for i, a in enumerate(authors):
        if i:
            parts.append('<span class="a-size-base">, </span>')
        if linked:
            parts.append(f'<a class="a-size-base a-link-normal" href="/{a.replace(" ", "-")}/e/B004MQ8KQ4">{a}</a> ')
        else:
            parts.append(f'<span class="a-size-base">{a}</span>')
    parts.append('<span class="a-letter-space"></span><span class="a-size-base a-color-secondary"> | </span>')
    parts.append('<span class="a-size-base a-color-secondary">Sold by: </span><a class="a-size-base" href="/Some-Title-ebook/dp/B0FRV1V54C/ref=x">Amazon</a>')
    return ''.join(parts)


def page(*results: str) -> str:
    return '<html><body><div class="s-main-slot s-result-list">' + ''.join(results) + '</div></body></html>'


class TestAmazonStore(unittest.TestCase):
    def test_amazon_store_results(self) -> None:
        raw = page(
            result('B0AAAAAAAA', 'Advertised', by('Ad Author'), cls='AdHolder'),
            result('B0FRV1V54C', 'The End of Everything', '<span class="a-size-base a-color-secondary">English edition</span> | ' + by('M. John Harrison')),
            # A print book in the results, without a Kindle edition
            result('1800812949', 'The End of Everything', by('M. John Harrison'), format_name='Hardcover', dp_slug='hardcover'),
            # In Kindle Unlimited, so the price shown is zero
            result(
                'B0B4FC637R',
                'The End of Everything',
                by('Nate Johnson', label='von '),
                format_name='Kindle Ausgabe',
                price='0,00 €',
                extra='<div class="a-row a-size-base a-color-secondary"><span>Oder für 0,89 € kaufen</span></div>',
            ),
            # Authors without pages of their own, in plain text
            result('B07W3QHB1W', 'Immortal Academy', by('S.L. Morgan', 'Keary Taylor', linked=False)),
            # The same book again
            result('B0FRV1V54C', 'The End of Everything', by('M. John Harrison')),
        )
        results = list(parse_results(raw, 10))
        self.assertEqual([r.detail_item for r in results], ['B0FRV1V54C', 'B0B4FC637R', 'B07W3QHB1W'])
        self.assertEqual([r.title for r in results], ['The End of Everything', 'The End of Everything', 'Immortal Academy'])
        self.assertEqual([r.author for r in results], ['M. John Harrison', 'Nate Johnson', 'S.L. Morgan, Keary Taylor'])
        self.assertEqual([r.price for r in results], ['€14.78', '0,89 €', '€14.78'])
        self.assertEqual(results[0].cover_url, 'https://m.media-amazon.com/images/I/B0FRV1V54C.jpg')
        self.assertEqual({r.formats for r in results}, {'Kindle'})
        self.assertEqual(len(list(parse_results(raw, 2))), 2)

    def test_amazon_store_query(self) -> None:
        from calibre.gui2.store import amazon_live

        queries: list[object] = []

        def fake_search(store: object, query: object, timeout: float) -> str:
            queries.append(query)
            return page(result('B0FRV1V54C', 'The End of Everything', by('M. John Harrison')))

        orig = amazon_live.search_results_html
        amazon_live.search_results_html = fake_search
        try:
            # The Get books dialog passes the query as UTF-8 encoded bytes
            results = list(amazon_live.search_amazon(None, 'end everything m. john harrison café'.encode(), 10, 60))
        finally:
            amazon_live.search_results_html = orig
        self.assertEqual(queries, ['end everything m. john harrison café'])
        self.assertEqual([r.detail_item for r in results], ['B0FRV1V54C'])

    def test_amazon_store_money(self) -> None:
        for text, expected in (
            ('Or INR 93.25 to buy', 'INR 93.25'),
            ('Or $0.99 to buy', '$0.99'),
            ('Ou 0,99 € à l’achat', '0,99 €'),
            ('Oppure 1,99 € per l’acquisto', '1,99 €'),
            ('O compra por MX$18.00', 'MX$18.00'),
            ('Or ₹380 to buy', '₹380'),
        ):
            m = MONEY_PAT.search(text)
            self.assertIsNotNone(m, text)
            assert m is not None
            self.assertEqual(m.group(), expected)
        self.assertIsNone(MONEY_PAT.search('Free with Kindle Unlimited membership'))


def find_tests() -> unittest.TestSuite:
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestAmazonStore)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_cli

    run_cli(find_tests())
