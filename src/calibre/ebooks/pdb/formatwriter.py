# -*- coding: utf-8 -*-


'''
Interface defining the necessary public functions for a pdb format writer.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'


class FormatWriter(object):

    def __init__(self, opts, log):
        raise NotImplementedError()

    def write_content(self, oeb_book, output_stream, metadata=None):
        raise NotImplementedError()
