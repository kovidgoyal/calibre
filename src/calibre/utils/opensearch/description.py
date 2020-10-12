# -*- coding: utf-8 -*-


__license__ = 'GPL 3'
__copyright__ = '''
2011, John Schember <john@nachtimwald.com>,
2006, Ed Summers <ehs@pobox.com>
'''
__docformat__ = 'restructuredtext en'

from contextlib import closing

from calibre import browser
from calibre.utils.xml_parse import safe_xml_fromstring
from calibre.utils.opensearch.url import URL


class Description(object):
    '''
    A class for representing OpenSearch Description files.
    '''

    def __init__(self, url=""):
        '''
        The constructor which may pass an optional url to load from.

        d = Description("http://www.example.com/description")
        '''
        if url:
            self.load(url)

    def load(self, url):
        '''
        For loading up a description object from a url. Normally
        you'll probably just want to pass a URL into the constructor.
        '''
        br = browser()
        with closing(br.open(url, timeout=15)) as f:
            doc = safe_xml_fromstring(f.read())

        # version 1.1 has repeating Url elements.
        self.urls = []
        for element in doc.xpath('//*[local-name() = "Url"]'):
            template = element.get('template')
            type = element.get('type')
            if template and type:
                url = URL()
                url.template = template
                url.type = type
                self.urls.append(url)
        # Stanza catalogs.
        for element in doc.xpath('//*[local-name() = "link"]'):
            if element.get('rel') != 'search':
                continue
            href = element.get('href')
            type = element.get('type')
            if href and type:
                url = URL()
                url.template = href
                url.type = type
                self.urls.append(url)

        # this is version 1.0 specific.
        self.url = ''
        if not self.urls:
            self.url = ''.join(doc.xpath('//*[local-name() = "Url"][1]//text()'))
        self.format = ''.join(doc.xpath('//*[local-name() = "Format"][1]//text()'))

        self.shortname = ''.join(doc.xpath('//*[local-name() = "ShortName"][1]//text()'))
        self.longname = ''.join(doc.xpath('//*[local-name() = "LongName"][1]//text()'))
        self.description = ''.join(doc.xpath('//*[local-name() = "Description"][1]//text()'))
        self.image = ''.join(doc.xpath('//*[local-name() = "Image"][1]//text()'))
        self.sameplesearch = ''.join(doc.xpath('//*[local-name() = "SampleSearch"][1]//text()'))
        self.developer = ''.join(doc.xpath('//*[local-name() = "Developer"][1]//text()'))
        self.contact = ''.join(doc.xpath('/*[local-name() = "Contact"][1]//text()'))
        self.attribution = ''.join(doc.xpath('//*[local-name() = "Attribution"][1]//text()'))
        self.syndicationright = ''.join(doc.xpath('//*[local-name() = "SyndicationRight"][1]//text()'))

        tag_text = ' '.join(doc.xpath('//*[local-name() = "Tags"]//text()'))
        if tag_text is not None:
            self.tags = tag_text.split(' ')

        self.adultcontent = doc.xpath('boolean(//*[local-name() = "AdultContent" and contains(., "true")])')

    def get_url_by_type(self, type):
        '''
        Walks available urls and returns them by type. Only
        appropriate in opensearch v1.1 where there can be multiple
        query targets. Returns none if no such type is found.

        url = description.get_url_by_type('application/rss+xml')
        '''
        for url in self.urls:
            if url.type == type:
                return url
        return None

    def get_best_template(self):
        '''
        OK, best is a value judgement, but so be it. You'll get
        back either the atom, rss or first template available. This
        method handles the main difference between opensearch v1.0 and v1.1
        '''
        # version 1.0
        if self.url:
            return self.url

        # atom
        if self.get_url_by_type('application/atom+xml'):
            return self.get_url_by_type('application/atom+xml').template

        # rss
        if self.get_url_by_type('application/rss+xml'):
            return self.get_url_by_type('application/rss+xml').template

        # other possible rss type
        if self.get_url_by_type('text/xml'):
            return self.get_url_by_Type('text/xml').template

        # otherwise just the first one
        if len(self.urls) > 0:
            return self.urls[0].template

        # out of luck
        return None
