# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.conversion.plumber import Plumber
from calibre.utils.logging import Log
from calibre.customize.conversion import OptionRecommendation, DummyReporter

def gui_convert(input, output, recommendations, notification=DummyReporter(),
        abort_after_input_dump=False):
    recommendations = list(recommendations)
    recommendations.append(('verbose', 2, OptionRecommendation.HIGH))
    plumber = Plumber(input, output, Log(), report_progress=notification,
            abort_after_input_dump=abort_after_input_dump)
    plumber.merge_ui_recommendations(recommendations)

    plumber.run()

