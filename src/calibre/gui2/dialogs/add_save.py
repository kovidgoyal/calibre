#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap

from PyQt4.Qt import QTabWidget

from calibre.gui2.dialogs.add_save_ui import Ui_TabWidget
from calibre.library.save_to_disk import config, FORMAT_ARG_DESCS


class AddSave(QTabWidget, Ui_TabWidget):

    def __init__(self, parent=None):
        QTabWidget.__init__(self, parent)
        self.setupUi(self)
        c = config()
        opts = c.parse()
        for x in ('asciiize', 'update_metadata', 'save_cover', 'write_opf'):
            g = getattr(self, 'opt_'+x)
            g.setChecked(getattr(opts, x))
            help = '\n'.join(textwrap.wrap(c.get_option(x).help, 75))
            g.setToolTip(help)
            g.setWhatsThis(help)

        for x in ('formats', 'timefmt'):
            g = getattr(self, 'opt_'+x)
            g.setText(getattr(opts, x))
            help = '\n'.join(textwrap.wrap(c.get_option(x).help, 75))
            g.setToolTip(help)
            g.setWhatsThis(help)

        help = '\n'.join(textwrap.wrap(c.get_option('template').help, 75))
        self.opt_template.initialize('save_to_disk_template_history',
                opts.template, help=help)

        variables = sorted(FORMAT_ARG_DESCS.keys())
        rows = []
        for var in variables:
            rows.append(u'<tr><td>%s</td><td>%s</td></tr>'%
                    (var, FORMAT_ARG_DESCS[var]))
        table = u'<table>%s</table>'%(u'\n'.join(rows))
        self.template_variables.setText(table)

    def save_settings(self):
        c = config()
        for x in ('asciiize', 'update_metadata', 'save_cover', 'write_opf'):
            c.set(x, getattr(self, 'opt_'+x).isChecked())
        for x in ('formats', 'template', 'timefmt'):
            c.set(x, unicode(getattr(self, 'opt_'+x).text()).strip())



if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app=QApplication([])
    a = AddSave()
    a.show()
    app.exec_()
    a.save_settings()

