# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

import os
from optparse import OptionParser
from typing import TYPE_CHECKING, cast

from calibre.constants import iswindows
from calibre.customize.conversion import DummyReporter, OptionRecommendation
from calibre.customize.ui import plugin_for_catalog_format
from calibre.ebooks.conversion.plumber import Plumber
from calibre.utils.logging import Log

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Mapping

    from calibre.ebooks.conversion.plumber import ProgressReporter


def gui_convert(
    input: str,
    output: str,
    recommendations: Iterable[tuple[str, object, int]],
    notification: ProgressReporter = DummyReporter(),
    abort_after_input_dump: bool = False,
    log: Log | None = None,
    override_input_metadata: bool = False,
) -> None:
    recommendations = list(recommendations)
    recommendations.append(('verbose', 2, OptionRecommendation.HIGH))
    if log is None:
        log = Log()
    plumber = Plumber(
        input,
        output,
        log,
        report_progress=notification,
        abort_after_input_dump=abort_after_input_dump,
        override_input_metadata=override_input_metadata,
    )
    plumber.merge_ui_recommendations(recommendations)

    plumber.run()


def gui_convert_recipe(
    input: str,
    output: str,
    recommendations: Iterable[tuple[str, object, int]],
    notification: ProgressReporter = DummyReporter(),
    abort_after_input_dump: bool = False,
    log: Log | None = None,
    override_input_metadata: bool = False,
) -> None:
    os.environ['CALIBRE_RECIPE_URN'] = input
    gui_convert(
        'from-gui.recipe',
        output,
        recommendations,
        notification=notification,
        abort_after_input_dump=abort_after_input_dump,
        log=log,
        override_input_metadata=override_input_metadata,
    )


def gui_convert_override(
    input: str,
    output: str,
    recommendations: Iterable[tuple[str, object, int]],
    notification: ProgressReporter = DummyReporter(),
    abort_after_input_dump: bool = False,
    log: Log | None = None,
) -> None:
    gui_convert(
        input,
        output,
        recommendations,
        notification=notification,
        abort_after_input_dump=abort_after_input_dump,
        log=log,
        override_input_metadata=True,
    )


def gui_catalog(
    library_path: str,
    temp_db_path: str,
    fmt: str,
    title: str,
    dbspec: dict[int, dict[str, object]],
    ids: Collection[int],
    out_file_name: str,
    sync: bool,
    fmt_options: Mapping[str, object],
    connected_device: dict[str, object],
    notification: ProgressReporter = DummyReporter(),
    log: Log | None = None,
) -> object:
    if log is None:
        log = Log()
    from calibre.utils.config import prefs

    prefs.refresh()

    # Open the temp database created while still in the GUI thread
    from calibre.db.legacy import LibraryDatabase

    db = LibraryDatabase(library_path, temp_db_path=temp_db_path)
    try:
        setattr(db, 'catalog_plugin_on_device_temp_mapping', dbspec)

        # Create a minimal OptionParser that we can append to
        parser = OptionParser()
        args = []
        parser.add_option('--verbose', action='store_true', dest='verbose', default=True)
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
            if isinstance(fmt_options[option], list):
                setattr(opts, option, ','.join(cast('list[str]', fmt_options[option])))
            else:
                setattr(opts, option, fmt_options[option])

        # Fetch and run the plugin for fmt
        # Returns 0 if successful, 1 if no catalog built
        plugin = plugin_for_catalog_format(fmt)
        if plugin is None:
            raise ValueError(f'No catalog plugin available for the format: {fmt}')
        return plugin.run(out_file_name, opts, db, notification=notification)
    finally:
        db.close()
        from calibre.db.backend import rmtree_with_retry

        try:
            rmtree_with_retry(os.path.dirname(temp_db_path))
        except PermissionError:
            if not iswindows:  # probably some antivirus holding a file open, the folder will be deleted on exit anyway
                raise
