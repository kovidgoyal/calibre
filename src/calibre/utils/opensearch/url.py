# -*- coding: utf-8 -*-


__license__ = 'GPL 3'
__copyright__ = '2006, Ed Summers <ehs@pobox.com>'
__docformat__ = 'restructuredtext en'


class URL(object):
    '''
    Class for representing a URL in an opensearch v1.1 query
    '''

    def __init__(self, type='', template='', method='GET'):
        self.type = type
        self.template = template
        self.method = 'GET'
        self.params = []
