__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os
from optparse import OptionParser

from calibre.customize.conversion import OptionRecommendation, DummyReporter
from calibre.ebooks.conversion.plumber import Plumber
from calibre.customize.ui import plugin_for_catalog_format
from calibre.utils.logging import Log


def gui_convert(input, output, recommendations, notification=DummyReporter(),
        abort_after_input_dump=False, log=None, override_input_metadata=False):
    recommendations = list(recommendations)
    recommendations.append(('verbose', 2, OptionRecommendation.HIGH))
    if log is None:
        log = Log()
    plumber = Plumber(input, output, log, report_progress=notification,
            abort_after_input_dump=abort_after_input_dump,
            override_input_metadata=override_input_metadata)
    plumber.merge_ui_recommendations(recommendations)

    plumber.run()


def gui_convert_recipe(input, output, recommendations, notification=DummyReporter(),
        abort_after_input_dump=False, log=None, override_input_metadata=False):
    os.environ['CALIBRE_RECIPE_URN'] = input
    gui_convert('from-gui.recipe', output, recommendations, notification=notification,
            abort_after_input_dump=abort_after_input_dump, log=log,
            override_input_metadata=override_input_metadata)


def gui_convert_override(input, output, recommendations, notification=DummyReporter(),
        abort_after_input_dump=False, log=None):
    gui_convert(input, output, recommendations, notification=notification,
            abort_after_input_dump=abort_after_input_dump, log=log,
            override_input_metadata=True)


def gui_catalog(fmt, title, dbspec, ids, out_file_name, sync, fmt_options, connected_device,
        notification=DummyReporter(), log=None):
    if log is None:
        log = Log()
    from calibre.library import db
    from calibre.utils.config import prefs
    prefs.refresh()
    db = db(read_only=True)
    db.catalog_plugin_on_device_temp_mapping = dbspec

    # Create a minimal OptionParser that we can append to
    parser = OptionParser()
    args = []
    parser.add_option("--verbose", action="store_true", dest="verbose", default=True)
    opts, args = parser.parse_args()

    # Populate opts
    # opts.gui_search_text = something
    opts.catalog_title = title
    opts.connected_device = connected_device
    opts.ids = ids
    opts.search_text = None
    opts.sort_by = None
    opts.sync = sync

    # Extract the option dictionary to comma-separated lists
    for option in fmt_options:
        if isinstance(fmt_options[option],list):
            setattr(opts,option, ','.join(fmt_options[option]))
        else:
            setattr(opts,option, fmt_options[option])

    # Fetch and run the plugin for fmt
    # Returns 0 if successful, 1 if no catalog built
    plugin = plugin_for_catalog_format(fmt)
    return plugin.run(out_file_name, opts, db, notification=notification)
