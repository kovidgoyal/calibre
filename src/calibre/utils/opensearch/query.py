# -*- coding: utf-8 -*-


__license__ = 'GPL 3'
__copyright__ = '2006, Ed Summers <ehs@pobox.com>'
__docformat__ = 'restructuredtext en'

from polyglot.urllib import parse_qs, urlencode, urlparse, urlunparse


class Query(object):
    '''
    Represents an opensearch query Really this class is just a
    helper for substituting values into the macros in a format.

    format = 'http://beta.indeed.com/opensearch?q={searchTerms}&start={startIndex}&limit={count}'
    q = Query(format)
    q.searchTerms('zx81')
    q.startIndex = 1
    q.count = 25
    print q.url()
    '''

    standard_macros = ['searchTerms', 'count', 'startIndex', 'startPage',
        'language', 'outputEncoding', 'inputEncoding']

    def __init__(self, format):
        '''
        Create a query object by passing it the url format obtained
        from the opensearch Description.
        '''
        self.format = format

        # unpack the url to a tuple
        self.url_parts = urlparse(format)

        # unpack the query string to a dictionary
        self.query_string = parse_qs(self.url_parts[4])

        # look for standard macros and create a mapping of the
        # opensearch names to the service specific ones
        # so q={searchTerms} will result in a mapping between searchTerms and q
        self.macro_map = {}
        for key,values in self.query_string.items():
            # TODO eventually optional/required params should be
            # distinguished somehow (the ones with/without trailing ?
            macro = values[0].replace('{', '').replace('}', '').replace('?', '')
            if macro in Query.standard_macros:
                self.macro_map[macro] = key

    def url(self):
        # copy the original query string
        query_string = dict(self.query_string)

        # iterate through macros and set the position in the querystring
        for macro, name in self.macro_map.items():
            if hasattr(self, macro):
                # set the name/value pair
                query_string[name] = [getattr(self, macro)]
            else:
                # remove the name/value pair
                del(query_string[name])

        # copy the url parts and substitute in our new query string
        url_parts = list(self.url_parts)
        url_parts[4] = urlencode(query_string, 1)

        # recompose and return url
        return urlunparse(tuple(url_parts))

    def has_macro(self, macro):
        return macro in self.macro_map
