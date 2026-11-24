#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid@kovidgoyal.net>

import codecs
import importlib
import textwrap
from functools import partial
from typing import TYPE_CHECKING, cast

from qt.core import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFont,
    QFontComboBox,
    QFontInfo,
    QIcon,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    Qt,
    QTextEdit,
    QWidget,
    pyqtSignal,
)

from calibre import prepare_string_for_xml
from calibre.customize.conversion import OptionRecommendation
from calibre.customize.ui import plugin_for_input_format
from calibre.ebooks.conversion.config import GuiRecommendations, load_defaults, load_specifics
from calibre.ebooks.conversion.config import save_defaults as save_defaults_
from calibre.gui2.font_family_chooser import FontFamilyChooser
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping, Sequence

    from qt.core import QObject

    from calibre.customize.conversion import InputFormatPlugin, OutputFormatPlugin
    from calibre.db.legacy import LibraryDatabase

    #: Returns the OptionRecommendation for the named option
    type GetOption = Callable[[str], OptionRecommendation | None]
    #: Returns the help text for the named option
    type GetHelp = Callable[[str], str | None]
    #: The GUI object for an option, or a placeholder string for options that
    #: are handled entirely by the *_handler() methods of a Widget subclass
    type OptionWidget = QWidget | str


def config_widget_for_input_plugin(plugin: InputFormatPlugin) -> type[Widget] | None:
    name = plugin.name.lower().replace(' ', '_')
    try:
        return importlib.import_module('calibre.gui2.convert.' + name).PluginWidget
    except ImportError:
        # If this is not a builtin plugin, we have to import it differently
        if plugin.__module__ and plugin.__module__.startswith('calibre_plugins.'):
            try:
                ans = importlib.import_module(plugin.__module__ + '.' + name).PluginWidget
            except ImportError, AttributeError, TypeError:
                pass
            else:
                if issubclass(ans, Widget):
                    return ans
    return None


def bulk_defaults_for_input_format(fmt: str) -> dict[str, object]:
    plugin = plugin_for_input_format(fmt)
    if plugin is not None:
        w = config_widget_for_input_plugin(plugin)
        if w is not None:
            assert w.COMMIT_NAME is not None
            return load_defaults(w.COMMIT_NAME)
    return {}


def option_choices(get_option: GetOption, name: str) -> Sequence[str]:
    """Return the choices of the named option, which must exist and have choices"""
    rec = get_option(name)
    assert rec is not None and rec.option.choices is not None
    return rec.option.choices


class Widget(QWidget):
    TITLE = _('Unknown')
    ICON = 'config.png'
    HELP = ''
    COMMIT_NAME: str | None = None
    # If True, leading and trailing spaces are removed from line and text edit
    # fields
    STRIP_TEXT_FIELDS = True
    # Set on plugin widget classes by the conversion preferences
    conv_plugin: InputFormatPlugin | OutputFormatPlugin

    changed_signal = pyqtSignal()
    set_help_signal = pyqtSignal(object)

    def __init__(self, parent: QWidget | None, options: Iterable[str]) -> None:
        options = list(options)
        QWidget.__init__(self, parent)
        if hasattr(self, 'setupUi'):
            self.setupUi(self)  # type: ignore
        self._options = options
        commit_name = self.COMMIT_NAME
        assert commit_name is not None
        self._name = self.commit_name = commit_name
        self._icon = QIcon.ic(self.ICON)
        for name in self._options:
            if not hasattr(self, 'opt_' + name):
                raise Exception(f'Option {name} missing in {self.__class__.__name__}')
            self.connect_gui_obj(getattr(self, 'opt_' + name))

    def initialize_options(self, get_option: GetOption, get_help: GetHelp, db: LibraryDatabase | None = None, book_id: int | None = None) -> None:
        """
        :param get_option: A callable that takes one argument: the option name
        and returns the corresponding OptionRecommendation.
        :param get_help: A callable that takes the option name and return a help
        string.
        """
        defaults = load_defaults(self._name)
        defaults.merge_recommendations(get_option, OptionRecommendation.LOW, self._options)

        if db is not None and book_id is not None:  # book_id is None in bulk conversion, which has no specifics
            specifics = load_specifics(db, book_id)
            specifics.merge_recommendations(get_option, OptionRecommendation.HIGH, self._options, only_existing=True)
            defaults.update(specifics)

        self.apply_recommendations(defaults)
        self.setup_help(get_help)

        def process_child(child: QObject) -> None:
            for g in child.children():
                if isinstance(g, QLabel):
                    buddy = g.buddy()
                    if buddy is not None and hasattr(buddy, '_help'):
                        setattr(g, '_help', buddy._help)
                        htext = str(buddy.toolTip()).strip()
                        g.setToolTip(htext)
                        g.setWhatsThis(htext)
                        setattr(g.__class__, 'enterEvent', lambda obj, event: self.set_help(getattr(obj, '_help', obj.toolTip())))
                else:
                    process_child(g)

        process_child(self)

    def restore_defaults(self, get_option: GetOption) -> None:
        defaults = GuiRecommendations()
        defaults.merge_recommendations(get_option, OptionRecommendation.LOW, self._options)
        self.apply_recommendations(defaults)

    def commit_options(self, save_defaults: bool = False) -> GuiRecommendations:
        recs = self.create_recommendations()
        if save_defaults:
            save_defaults_(self.commit_name, recs)
        return recs

    def create_recommendations(self) -> GuiRecommendations:
        recs = GuiRecommendations()
        for name in self._options:
            gui_opt = getattr(self, 'opt_' + name, None)
            if gui_opt is None:
                continue
            recs[name] = self.get_value(gui_opt)
        return recs

    def apply_recommendations(self, recs: Mapping[str, object]) -> None:
        for name, val in recs.items():
            gui_opt = getattr(self, 'opt_' + name, None)
            if gui_opt is None:
                continue
            self.set_value(gui_opt, val)
            if name in getattr(recs, 'disabled_options', []):
                gui_opt.setDisabled(True)

    def get_value(self, g: OptionWidget) -> object:
        from calibre.gui2.convert.regex_builder import RegexEdit
        from calibre.gui2.convert.xpath_wizard import XPathEdit
        from calibre.gui2.widgets import EncodingComboBox

        ret = self.get_value_handler(g)
        if ret != 'this is a dummy return value, xcswx1avcx4x':
            return ret
        if hasattr(g, 'get_value_for_config'):
            return g.get_value_for_config
        if isinstance(g, (QSpinBox, QDoubleSpinBox)):
            return g.value()
        elif isinstance(g, (QLineEdit, QTextEdit, QPlainTextEdit)):
            func = getattr(g, 'toPlainText', getattr(g, 'text', None))
            assert func is not None
            ans = str(func())
            if self.STRIP_TEXT_FIELDS:
                ans = ans.strip()
            if not ans:
                ans = None
            return ans
        elif isinstance(g, QFontComboBox):
            return str(QFontInfo(g.currentFont()).family())
        elif isinstance(g, FontFamilyChooser):
            return g.font_family
        elif isinstance(g, EncodingComboBox):
            ans = str(g.currentText()).strip()
            try:
                codecs.lookup(ans)
            except Exception:
                ans = ''
            if not ans:
                ans = None
            return ans
        elif isinstance(g, QComboBox):
            return str(g.currentText())
        elif isinstance(g, QCheckBox):
            return bool(g.isChecked())
        elif isinstance(g, XPathEdit):
            return g.xpath or None
        elif isinstance(g, RegexEdit):
            return g.regex or None
        else:
            raise TypeError(f"Can't get value from {type(g)}")

    def gui_obj_changed(self, gui_obj: OptionWidget, *args: object) -> None:
        self.changed_signal.emit()

    def connect_gui_obj(self, g: OptionWidget) -> None:
        f = partial(self.gui_obj_changed, g)
        try:
            self.connect_gui_obj_handler(g, f)
            return
        except NotImplementedError:
            pass
        from calibre.gui2.convert.regex_builder import RegexEdit
        from calibre.gui2.convert.xpath_wizard import XPathEdit

        if isinstance(g, (QSpinBox, QDoubleSpinBox)):
            g.valueChanged.connect(f)
        elif isinstance(g, (QLineEdit, QTextEdit, QPlainTextEdit)):
            g.textChanged.connect(f)
        elif isinstance(g, QComboBox):
            g.editTextChanged.connect(f)
            g.currentIndexChanged.connect(f)
        elif isinstance(g, QCheckBox):
            g.stateChanged.connect(f)
        elif isinstance(g, (XPathEdit, RegexEdit)):
            g.edit.editTextChanged.connect(f)
            g.edit.currentIndexChanged.connect(f)
        elif isinstance(g, FontFamilyChooser):
            g.family_changed.connect(f)
        else:
            raise TypeError(f"Can't connect {type(g)}")

    def connect_gui_obj_handler(self, gui_obj: OptionWidget, slot: Callable[..., None]) -> None:
        raise NotImplementedError()

    def set_value(self, g: OptionWidget, val: object) -> None:
        from calibre.gui2.convert.regex_builder import RegexEdit
        from calibre.gui2.convert.xpath_wizard import XPathEdit
        from calibre.gui2.widgets import EncodingComboBox

        if self.set_value_handler(g, val):
            return
        if hasattr(g, 'set_value_for_config'):
            setattr(g, 'set_value_for_config', val)
            return
        if isinstance(g, (QSpinBox, QDoubleSpinBox)):
            g.setValue(cast('int', val))
        elif isinstance(g, (QLineEdit, QTextEdit, QPlainTextEdit)):
            if not val:
                val = ''
            func = getattr(g, 'setPlainText', getattr(g, 'setText', None))
            assert func is not None
            func(val)
            getattr(g, 'setCursorPosition', lambda x: x)(0)
        elif isinstance(g, QFontComboBox):
            g.setCurrentFont(QFont(val or ''))
        elif isinstance(g, FontFamilyChooser):
            g.font_family = cast('str | None', val)
        elif isinstance(g, EncodingComboBox):
            if val:
                g.setEditText(cast('str', val))
            else:
                g.setCurrentIndex(0)
        elif isinstance(g, QComboBox) and val:
            text = cast('str', val)
            idx = g.findText(text, Qt.MatchFlag.MatchFixedString)
            if idx < 0:
                g.addItem(text)
                idx = g.findText(text, Qt.MatchFlag.MatchFixedString)
            g.setCurrentIndex(idx)
        elif isinstance(g, QCheckBox):
            g.setCheckState(Qt.CheckState.Checked if bool(val) else Qt.CheckState.Unchecked)
        elif isinstance(g, (XPathEdit, RegexEdit)):
            g.edit.setText(cast('str | None', val) or '')
        else:
            raise Exception(f"Can't set value {val!r} in {cast('QWidget', g).objectName()!s}")
        self.post_set_value(g, val)

    def set_help(self, msg: str | None) -> None:
        if msg and getattr(msg, 'strip', lambda: True)():
            try:
                self.set_help_signal.emit(msg)
            except Exception:
                pass

    def setup_help(self, help_provider: GetHelp) -> None:
        for name in self._options:
            g = getattr(self, 'opt_' + name, None)
            if g is None:
                continue
            help = help_provider(name)
            if not help:
                continue
            if self.setup_help_handler(g, help):
                continue
            setattr(g, '_help', help)
            self.setup_widget_help(g)

    def setup_widget_help(self, g: QWidget) -> None:
        w = textwrap.TextWrapper(80)
        htext = '<div>{}</div>'.format(prepare_string_for_xml('\n'.join(w.wrap(getattr(g, '_help')))))
        g.setToolTip(htext)
        g.setWhatsThis(htext)
        setattr(g.__class__, 'enterEvent', lambda obj, event: self.set_help(getattr(obj, '_help', obj.toolTip())))

    def set_value_handler(self, g: OptionWidget, val: object) -> bool:
        "Return True iff you handle setting the value for g"
        return False

    def post_set_value(self, g: OptionWidget, val: object) -> None:
        pass

    def get_value_handler(self, g: OptionWidget) -> object:
        return 'this is a dummy return value, xcswx1avcx4x'

    def post_get_value(self, g: OptionWidget) -> None:
        pass

    def setup_help_handler(self, g: OptionWidget, help: str) -> bool:
        return False

    def break_cycles(self) -> None:
        self.db = None

    def pre_commit_check(self) -> bool:
        return True

    def commit(self, save_defaults: bool = False) -> GuiRecommendations:
        return self.commit_options(save_defaults)

    def config_title(self) -> str:
        return self.TITLE

    def config_icon(self) -> QIcon:
        return self._icon
