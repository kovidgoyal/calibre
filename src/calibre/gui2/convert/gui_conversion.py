# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import logging

from calibre.ebooks.conversion.plumber import Plumber
from calibre.utils.logging import Log

def gui_convert(input, output, recommendations):
    plumber = Plumber(input, output, Log())
    plumber.merge_ui_recommendations(recommendations)
    
    plumber.run()

