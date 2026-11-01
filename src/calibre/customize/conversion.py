"""
Defines the plugin system for conversions.
"""

import numbers
import os
import re
import shutil
from typing import IO, TYPE_CHECKING, cast

from calibre import CurrentDir
from calibre.customize import Plugin
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from optparse import Values

    from qt.core import QWidget

    from calibre.db.legacy import LibraryDatabase
    from calibre.ebooks.oeb.base import Manifest, OEBBook
    from calibre.ebooks.oeb.stylizer import Stylizer
    from calibre.gui2.convert import Widget
    from calibre.utils.logging import Log

    #: Creates the widget for configuring a conversion plugin in the GUI, see :func:`gui_configuration_widget`
    type PluginWidgetFactory = Callable[
        [QWidget, Callable[[str], OptionRecommendation | None], Callable[[str], str | None], LibraryDatabase, int | None], Widget
    ]


class ConversionOption:
    """
    Class representing conversion options
    """

    def __init__(
        self,
        name: str = '',
        help: str | None = None,
        long_switch: str | None = None,
        short_switch: str | None = None,
        choices: Sequence[str] | None = None,
    ) -> None:
        self.name = name
        self.help = help
        self.long_switch = long_switch
        self.short_switch = short_switch
        self.choices = choices

        if self.long_switch is None:
            self.long_switch = self.name.replace('_', '-')

        self.validate_parameters()

    def validate_parameters(self) -> None:
        """
        Validate the parameters passed to :meth:`__init__`.
        """
        if re.match(r'[a-zA-Z_]([a-zA-Z0-9_])*', self.name) is None:
            raise ValueError(self.name + ' is not a valid Python identifier')
        if not self.help:
            raise ValueError('You must set the help text')

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        return self.name == getattr(other, 'name', other)

    def clone(self) -> ConversionOption:
        return ConversionOption(
            name=self.name,
            help=self.help,
            long_switch=self.long_switch,
            short_switch=self.short_switch,
            choices=self.choices,
        )


class OptionRecommendation:
    LOW = 1
    MED = 2
    HIGH = 3

    def __init__(
        self,
        recommended_value: object = None,
        level: int = LOW,
        *,
        option: ConversionOption | None = None,
        name: str = '',
        help: str | None = None,
        long_switch: str | None = None,
        short_switch: str | None = None,
        choices: Sequence[str] | None = None,
    ) -> None:
        """
        An option recommendation. That is, an option as well as its recommended
        value and the level of the recommendation. Either specify an existing
        :class:`ConversionOption` via option or the parameters for creating one.
        """
        self.level = level
        # Must be a number, string or None, as checked by validate_parameters(),
        # but can be changed to any value from the GUI after construction, see
        # Plumber.merge_ui_recommendations()
        self.recommended_value = recommended_value
        if option is None:
            option = ConversionOption(name=name, help=help, long_switch=long_switch, short_switch=short_switch, choices=choices)
        self.option = option

        self.validate_parameters()

    @property
    def help(self) -> str | None:
        return self.option.help

    def clone(self) -> OptionRecommendation:
        return OptionRecommendation(recommended_value=self.recommended_value, level=self.level, option=self.option.clone())

    def validate_parameters(self) -> None:
        if self.option.choices and self.recommended_value not in self.option.choices:
            raise ValueError(f'OpRec: {self.option.name}: Recommended value not in choices')
        if not (isinstance(self.recommended_value, (numbers.Number, bytes, str)) or self.recommended_value is None):
            raise ValueError(f'OpRec: {self.option.name}:' + repr(self.recommended_value) + ' is not a string or a number')


class DummyReporter:
    def __init__(self) -> None:
        self.cancel_requested = False

    def __call__(self, percent: float, msg: str = '') -> None:
        pass


def gui_configuration_widget(
    name: str,
    parent: QWidget,
    get_option_by_name: Callable[[str], OptionRecommendation | None],
    get_option_help: Callable[[str], str | None],
    db: LibraryDatabase,
    book_id: int | None,
    for_output: bool = True,
) -> Widget | None:
    import importlib

    def widget_factory(cls: PluginWidgetFactory) -> Widget:
        return cls(parent, get_option_by_name, get_option_help, db, book_id)

    if for_output:
        try:
            output_widget = importlib.import_module('calibre.gui2.convert.' + name)
            pw = output_widget.PluginWidget
            pw.ICON = 'back.png'
            pw.HELP = _('Options specific to the output format.')
            return widget_factory(pw)
        except ImportError:
            pass
    else:
        try:
            input_widget = importlib.import_module('calibre.gui2.convert.' + name)
            pw = input_widget.PluginWidget
            pw.ICON = 'forward.png'
            pw.HELP = _('Options specific to the input format.')
            return widget_factory(pw)
        except ImportError:
            pass
    return None


class InputFormatPlugin(Plugin):
    """
    InputFormatPlugins are responsible for converting a document into
    HTML+OPF+CSS+etc.
    The results of the conversion *must* be encoded in UTF-8.
    The main action happens in :meth:`convert`.
    """

    type = _('Conversion input')
    supported_platforms = ['windows', 'osx', 'linux']
    commit_name = None  # unique name under which options for this plugin are saved
    ui_data = None

    #: Set of file types for which this plugin should be run
    #: For example: ``set(['azw', 'mobi', 'prc'])``
    file_types = set()

    #: If True, this input plugin generates a collection of images,
    #: one per HTML file. This can be set dynamically, in the convert method
    #: if the input files can be both image collections and non-image collections.
    #: If you set this to True, you must implement the get_images() method that returns
    #: a list of images.
    is_image_collection = False

    #: Number of CPU cores used by this plugin.
    #: A value of -1 means that it uses all available cores
    core_usage = 1

    #: If set to True, the input plugin will perform special processing
    #: to make its output suitable for viewing
    for_viewer = False

    #: The encoding that this input plugin creates files in. A value of
    #: None means that the encoding is undefined and must be
    #: detected individually
    output_encoding = 'utf-8'

    #: Options shared by all Input format plugins. Do not override
    #: in sub-classes. Use :attr:`options` instead. Every option must be an
    #: instance of :class:`OptionRecommendation`.
    common_options = {
        OptionRecommendation(
            name='input_encoding',
            recommended_value=None,
            level=OptionRecommendation.LOW,
            help=_(
                'Specify the character encoding of the input document. If '
                'set this option will override any encoding declared by the '
                'document itself. Particularly useful for documents that '
                'do not declare an encoding or that have erroneous '
                'encoding declarations.'
            ),
        )
    }

    #: Options to customize the behavior of this plugin. Every option must be an
    #: instance of :class:`OptionRecommendation`.
    options = set()

    #: A set of 3-tuples of the form
    #: (option_name, recommended_value, recommendation_level)
    recommendations = set()

    def __init__(self, plugin_path: str | None) -> None:
        Plugin.__init__(self, plugin_path)
        self.report_progress: Callable[[float, str], object] = DummyReporter()

    def get_images(self) -> list[str]:
        """
        Return a list of absolute paths to the images, if this input plugin
        represents an image collection. The list of images is in the same order
        as the spine and the TOC.
        """
        raise NotImplementedError()

    def convert(self, stream: IO[bytes], options: Values, file_ext: str, log: Log, accelerators: dict[str, str]) -> str | OEBBook | None:
        """
        This method must be implemented in sub-classes. It must return
        the path to the created OPF file or an :class:`OEBBook` instance.
        All output should be contained in the current folder.
        If this plugin creates files outside the current
        folder they must be deleted/marked for deletion before this method
        returns.

        :param stream:   A file like object that contains the input file.
        :param options:  Options to customize the conversion process.
                         Guaranteed to have attributes corresponding
                         to all the options declared by this plugin. In
                         addition, it will have a verbose attribute that
                         takes integral values from zero upwards. Higher numbers
                         mean be more verbose. Another useful attribute is
                         ``input_profile`` that is an instance of
                         :class:`calibre.customize.profiles.InputProfile`.
        :param file_ext: The extension (without the .) of the input file. It
                         is guaranteed to be one of the `file_types` supported
                         by this plugin.
        :param log: A :class:`calibre.utils.logging.Log` object. All output
                    should use this object.
        :param accelerators: A dictionary of various information that the input
                             plugin can get easily that would speed up the
                             subsequent stages of the conversion.

        """
        raise NotImplementedError()

    def __call__(
        self, stream: IO[bytes] | str, options: Values, file_ext: str, log: Log, accelerators: dict[str, str], output_dir: str
    ) -> str | OEBBook | None:
        try:
            log(f'InputFormatPlugin: {self.name} running')
            if hasattr(stream, 'name'):
                log('on', stream.name)
        except Exception:
            # In case stdout is broken
            pass

        with CurrentDir(output_dir):
            for x in os.listdir('.'):
                shutil.rmtree(x) if os.path.isdir(x) else os.remove(x)

            # For recipe input the plumber passes the path to the recipe
            # file rather than a stream, which the recipe input plugin handles
            ret = self.convert(cast('IO[bytes]', stream), options, file_ext, log, accelerators)

        return ret

    def postprocess_book(self, oeb: OEBBook, opts: Values, log: Log) -> None:
        """
        Called to allow the input plugin to perform postprocessing after
        the book has been parsed.
        """
        pass

    def specialize(self, oeb: OEBBook, opts: Values, log: Log, output_fmt: str) -> None:
        """
        Called to allow the input plugin to specialize the parsed book
        for a particular output format. Called after postprocess_book
        and before any transforms are performed on the parsed book.
        """
        pass

    def gui_configuration_widget(
        self,
        parent: QWidget,
        get_option_by_name: Callable[[str], OptionRecommendation | None],
        get_option_help: Callable[[str], str | None],
        db: LibraryDatabase,
        book_id: int | None = None,
    ) -> Widget | None:
        """
        Called to create the widget used for configuring this plugin in the
        calibre GUI. The widget must be an instance of the PluginWidget class.
        See the builtin input plugins for examples.
        """
        name = self.name.lower().replace(' ', '_')
        return gui_configuration_widget(name, parent, get_option_by_name, get_option_help, db, book_id, for_output=False)


class OutputFormatPlugin(Plugin):
    """
    OutputFormatPlugins are responsible for converting an OEB document
    (OPF+HTML) into an output e-book.

    The OEB document can be assumed to be encoded in UTF-8.
    The main action happens in :meth:`convert`.
    """

    type = _('Conversion output')
    supported_platforms = ['windows', 'osx', 'linux']
    commit_name = None  # unique name under which options for this plugin are saved
    ui_data = None

    #: The file type (extension without leading period) that this
    #: plugin outputs
    file_type: str | None = None

    #: Options shared by all Input format plugins. Do not override
    #: in sub-classes. Use :attr:`options` instead. Every option must be an
    #: instance of :class:`OptionRecommendation`.
    common_options = {
        OptionRecommendation(
            name='pretty_print',
            recommended_value=False,
            level=OptionRecommendation.LOW,
            help=_(
                'If specified, the output plugin will try to create output '
                'that is as human readable as possible. May not have any effect '
                'for some output plugins.'
            ),
        )
    }

    #: Options to customize the behavior of this plugin. Every option must be an
    #: instance of :class:`OptionRecommendation`.
    options = set()

    #: A set of 3-tuples of the form
    #: (option_name, recommended_value, recommendation_level)
    recommendations = set()

    @property
    def description(self) -> str:
        return _('Convert e-books to the %s format') % (self.file_type or '').upper()

    def __init__(self, plugin_path: str | None) -> None:
        Plugin.__init__(self, plugin_path)
        self.report_progress: Callable[[float, str], object] = DummyReporter()

    def convert(self, oeb_book: OEBBook, output: str, input_plugin: InputFormatPlugin, opts: Values, log: Log) -> None:
        """
        Render the contents of `oeb_book` (which is an instance of
        :class:`calibre.ebooks.oeb.OEBBook`) to the file specified by output.

        :param output: Either a file like object or a string. If it is a string
                       it is the path to a folder that may or may not exist. The output
                       plugin should write its output into that folder. If it is a file like
                       object, the output plugin should write its output into the file.
        :param input_plugin: The input plugin that was used at the beginning of
                             the conversion pipeline.
        :param opts: Conversion options. Guaranteed to have attributes
                     corresponding to the OptionRecommendations of this plugin.
        :param log: The logger. Print debug/info messages etc. using this.

        """
        self.oeb = oeb_book
        raise NotImplementedError()

    @property
    def is_periodical(self) -> bool:
        return bool(self.oeb.metadata.publication_type) and str(self.oeb.metadata.publication_type[0]).startswith('periodical:')

    def specialize_options(self, log: Log, opts: Values, input_fmt: str) -> None:
        """
        Can be used to change the values of conversion options, as used by the
        conversion pipeline.
        """
        pass

    def specialize_css_for_output(self, log: Log, opts: Values, item: Manifest.Item, stylizer: Stylizer) -> None:
        """
        Can be used to make changes to the CSS during the CSS flattening
        process.

        :param item: The item (HTML file) being processed
        :param stylizer: A Stylizer object containing the flattened styles for
                         item. You can get the style for any element by
                         stylizer.style(element).

        """
        pass

    def gui_configuration_widget(
        self,
        parent: QWidget,
        get_option_by_name: Callable[[str], OptionRecommendation | None],
        get_option_help: Callable[[str], str | None],
        db: LibraryDatabase,
        book_id: int | None = None,
    ) -> Widget | None:
        """
        Called to create the widget used for configuring this plugin in the
        calibre GUI. The widget must be an instance of the PluginWidget class.
        See the builtin output plugins for examples.
        """
        name = self.name.lower().replace(' ', '_')
        return gui_configuration_widget(name, parent, get_option_by_name, get_option_help, db, book_id, for_output=True)
