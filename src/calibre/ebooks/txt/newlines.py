# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os

class TxtNewlines(object):

    NEWLINE_TYPES = {
                        'system'  : os.linesep,
                        'unix'    : '\n',
                        'old_mac' : '\r',
                        'windows' : '\r\n'
                     }

    def __init__(self, newline_type):
        self.newline = self.NEWLINE_TYPES.get(newline_type.lower(), os.linesep)

def specified_newlines(newline, text):
    if newline == os.linesep:
        return text

    return text.replace(os.linesep, newline)
