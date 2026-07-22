# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>

from calibre.gui2.convert.txt_output import PluginWidget as TXTPluginWidget
from calibre.utils.localization import _


class PluginWidget(TXTPluginWidget):
    TITLE = _('TXTZ output')
    HELP = _('Options specific to') + ' TXTZ ' + _('output')
    COMMIT_NAME = 'txtz_output'
