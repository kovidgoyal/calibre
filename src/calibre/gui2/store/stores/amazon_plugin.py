# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)
store_version = 2 # Needed for dynamic plugin loading

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import random
from contextlib import closing

from lxml import html

from PyQt4.Qt import QUrl

from calibre import browser
from calibre.gui2 import open_url
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult

class AmazonKindleStore(StorePlugin):

    search_url = 'http://www.amazon.com/s/?url=search-alias%3Ddigital-text&field-keywords='
    details_url = 'http://amazon.com/dp/'
    drm_search_text = u'Simultaneous Device Usage'
    drm_free_text = u'Unlimited'

    def open(self, parent=None, detail_item=None, external=False):
        '''
        Amazon comes with a number of difficulties.

        QWebView has major issues with Amazon.com. The largest of
        issues is it simply doesn't work on a number of pages.

        When connecting to a number parts of Amazon.com (Kindle library
        for instance) QNetworkAccessManager fails to connect with a
        NetworkError of 399 - ProtocolFailure. The strange thing is,
        when I check QNetworkRequest.HttpStatusCodeAttribute when the
        399 error is returned the status code is 200 (Ok). However, once
        the QNetworkAccessManager decides there was a NetworkError it
        does not download the page from Amazon. So I can't even set the
        HTML in the QWebView myself.

        There is http://bugreports.qt.nokia.com/browse/QTWEBKIT-259 an
        open bug about the issue but it is not correct. We can set the
        useragent (Arora does) to something else and the above issue
        will persist. This http://developer.qt.nokia.com/forums/viewthread/793
        gives a bit more information about the issue but as of now (27/Feb/2011)
        there is no solution or work around.

        We cannot change the The linkDelegationPolicy to allow us to avoid
        QNetworkAccessManager because it only works links. Forms aren't
        included so the same issue persists on any part of the site (login)
        that use a form to load a new page.

        Using an aStore was evaluated but I've decided against using it.
        There are three major issues with an aStore. Because checkout is
        handled by sending the user to Amazon we can't put it in a QWebView.
        If we're sending the user to Amazon sending them there directly is
        nicer. Also, we cannot put the aStore in a QWebView and let it open the
        redirection the users default browser because the cookies with the
        shopping cart won't transfer.

        Another issue with the aStore is how it handles the referral. It only
        counts the referral for the items in the shopping card / the item
        that directed the user to Amazon. Kindle books do not use the shopping
        cart and send the user directly to Amazon for the purchase. In this
        instance we would only get referral credit for the one book that the
        aStore directs to Amazon that the user buys. Any other purchases we
        won't get credit for.

        The last issue with the aStore is performance. Even though it's an
        Amazon site it's alow. So much slower than Amazon.com that it makes
        me not want to browse books using it. The look and feel are lesser
        issues. So is the fact that it almost seems like the purchase is
        with calibre. This can cause some support issues because we can't
        do much for issues with Amazon.com purchase hiccups.

        Another option that was evaluated was the Product Advertising API.
        The reasons against this are complexity. It would take a lot of work
        to basically re-create Amazon.com within calibre. The Product
        Advertising API is also designed with being run on a server not
        in an app. The signing keys would have to be made avaliable to ever
        calibre user which means bad things could be done with our account.

        The Product Advertising API also assumes the same browser for easy
        shopping cart transfer to Amazon. With QWebView not working and there
        not being an easy way to transfer cookies between a QWebView and the
        users default browser this won't work well.

        We could create our own website on the calibre server and create an
        Amazon Product Advertising API store. However, this goes back to the
        complexity argument. Why spend the time recreating Amazon.com

        The final and largest issue against using the Product Advertising API
        is the Efficiency Guidelines:

        "Each account used to access the Product Advertising API will be allowed
        an initial usage limit of 2,000 requests per hour. Each account will
        receive an additional 500 requests per hour (up to a maximum of 25,000
        requests per hour) for every $1 of shipped item revenue driven per hour
        in a trailing 30-day period. Usage thresholds are recalculated daily based
        on revenue performance."

        With over two million users a limit of 2,000 request per hour could
        render our store unusable for no other reason than Amazon rate
        limiting our traffic.

        The best (I use the term lightly here) solution is to open Amazon.com
        in the users default browser and set the affiliate id as part of the url.
        '''
        aff_id = {'tag': 'josbl0e-cpb-20'}
        # Use Kovid's affiliate id 30% of the time.
        if random.randint(1, 10) in (1, 2, 3):
            aff_id['tag'] = 'calibrebs-20'
        store_link = 'http://www.amazon.com/Kindle-eBooks/b/?ie=UTF&node=1286228011&ref_=%(tag)s&ref=%(tag)s&tag=%(tag)s&linkCode=ur2&camp=1789&creative=390957' % aff_id
        if detail_item:
            aff_id['asin'] = detail_item
            store_link = 'http://www.amazon.com/dp/%(asin)s/?tag=%(tag)s' % aff_id
        open_url(QUrl(store_link))

    def search(self, query, max_results=10, timeout=60):
        url = self.search_url + query.encode('ascii', 'backslashreplace').replace('%', '%25').replace('\\x', '%').replace(' ', '+')
        br = browser()

        counter = max_results
        with closing(br.open(url, timeout=timeout)) as f:
            doc = html.fromstring(f.read().decode('latin-1', 'replace'))

            data_xpath = '//div[contains(@class, "prod")]'
            format_xpath = './/ul[contains(@class, "rsltL")]//span[contains(@class, "lrg") and not(contains(@class, "bld"))]/text()'
            asin_xpath = '@name'
            cover_xpath = './/img[@class="productImage"]/@src'
            title_xpath = './/h3[@class="newaps"]/a//text()'
            author_xpath = './/h3[@class="newaps"]//span[contains(@class, "reg")]//text()'
            price_xpath = './/ul[contains(@class, "rsltL")]//span[contains(@class, "lrg") and contains(@class, "bld")]/text()'

            for data in doc.xpath(data_xpath):
                if counter <= 0:
                    break

                # Even though we are searching digital-text only Amazon will still
                # put in results for non Kindle books (author pages). Se we need
                # to explicitly check if the item is a Kindle book and ignore it
                # if it isn't.
                format = ''.join(data.xpath(format_xpath))
                if 'kindle' not in format.lower():
                    continue

                # We must have an asin otherwise we can't easily reference the
                # book later.
                asin = data.xpath(asin_xpath)
                if asin:
                    asin = asin[0]
                else:
                    continue

                cover_url = ''.join(data.xpath(cover_xpath))

                title = ''.join(data.xpath(title_xpath))
                author = ''.join(data.xpath(author_xpath))
                try:
                    author = author.split('by ', 1)[1].split(" (")[0]
                except:
                    pass

                price = ''.join(data.xpath(price_xpath))

                counter -= 1

                s = SearchResult()
                s.cover_url = cover_url.strip()
                s.title = title.strip()
                s.author = author.strip()
                s.price = price.strip()
                s.detail_item = asin.strip()
                s.formats = 'Kindle'

                yield s

    def get_details(self, search_result, timeout):
        url = self.details_url

        br = browser()
        with closing(br.open(url + search_result.detail_item, timeout=timeout)) as nf:
            idata = html.fromstring(nf.read())
            if idata.xpath('boolean(//div[@class="content"]//li/b[contains(text(), "' +
                           self.drm_search_text + '")])'):
                if idata.xpath('boolean(//div[@class="content"]//li[contains(., "' +
                               self.drm_free_text + '") and contains(b, "' +
                               self.drm_search_text + '")])'):
                    search_result.drm = SearchResult.DRM_UNLOCKED
                else:
                    search_result.drm = SearchResult.DRM_UNKNOWN
            else:
                search_result.drm = SearchResult.DRM_LOCKED
        return True
