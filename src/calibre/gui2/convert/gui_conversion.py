# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.conversion.plumber import Plumber, DummyReporter
from calibre.utils.logging import Log
from calibre.customize.conversion import OptionRecommendation

def gui_convert(input, output, recommendations, notification=DummyReporter()):
    recommendations = list(recommendations)
    recommendations.append(('verbose', 2, OptionRecommendation.HIGH))
    plumber = Plumber(input, output, Log(), report_progress=notification)
    plumber.merge_ui_recommendations(recommendations)

    plumber.run()

