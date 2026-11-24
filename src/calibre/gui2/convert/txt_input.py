# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

from typing import TYPE_CHECKING, cast

from qt.core import QListWidgetItem, Qt

from calibre.ebooks.conversion.config import OPTIONS
from calibre.ebooks.conversion.plugins.txt_input import MD_EXTENSIONS
from calibre.gui2.convert import Widget, option_choices
from calibre.gui2.convert.txt_input_ui import Ui_Form
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable

    from qt.core import QWidget

    from calibre.db.legacy import LibraryDatabase
    from calibre.gui2.convert import GetHelp, GetOption, OptionWidget


class PluginWidget(Widget, Ui_Form):
    TITLE = _('TXT input')
    HELP = _('Options specific to') + ' TXT ' + _('input')
    COMMIT_NAME = 'txt_input'
    ICON = 'mimetypes/txt.png'

    def __init__(self, parent: QWidget | None, get_option: GetOption, get_help: GetHelp, db: LibraryDatabase | None = None, book_id: int | None = None) -> None:
        Widget.__init__(self, parent, OPTIONS['input']['txt'])
        self.markdown_label.setText(self.markdown_label.text().format('https://daringfireball.net/projects/markdown'))
        self.markdown_extensions_label.setText(self.markdown_extensions_label.text().format('https://python-markdown.github.io/extensions/'))
        self.db, self.book_id = db, book_id
        for x in option_choices(get_option, 'paragraph_type'):
            self.opt_paragraph_type.addItem(x)
        for x in option_choices(get_option, 'formatting_type'):
            self.opt_formatting_type.addItem(x)
        self.md_map = {}
        for name, text in MD_EXTENSIONS.items():
            i = QListWidgetItem(f'{name} - {text}', self.opt_markdown_extensions)
            i.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            i.setData(Qt.ItemDataRole.UserRole, name)
            self.md_map[name] = i

        self.initialize_options(get_option, get_help, db, book_id)

    def set_value_handler(self, g: OptionWidget, val: object) -> bool:
        if g is self.opt_markdown_extensions:
            for i in self.md_map.values():
                i.setCheckState(Qt.CheckState.Unchecked)
            for x in cast('str', val).split(','):
                x = x.strip()
                if x in self.md_map:
                    self.md_map[x].setCheckState(Qt.CheckState.Checked)
            return True
        return False

    def get_value_handler(self, g: OptionWidget) -> object:
        if g is not self.opt_markdown_extensions:
            return Widget.get_value_handler(self, g)
        return ', '.join(str(i.data(Qt.ItemDataRole.UserRole) or '') for i in self.md_map.values() if i.checkState() == Qt.CheckState.Checked)

    def connect_gui_obj_handler(self, gui_obj: OptionWidget, slot: Callable[..., None]) -> None:
        if gui_obj is not self.opt_markdown_extensions:
            raise NotImplementedError()
        self.opt_markdown_extensions.itemChanged.connect(self.changed_signal)
