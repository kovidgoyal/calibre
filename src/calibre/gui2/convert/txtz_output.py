# -*- coding: utf-8 -*-


__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'


from calibre.gui2.convert.txt_output import PluginWidget as TXTPluginWidget


class PluginWidget(TXTPluginWidget):

    TITLE = _('TXTZ output')
    HELP = _('Options specific to')+' TXTZ '+_('output')
    COMMIT_NAME = 'txtz_output'
