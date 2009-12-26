#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap

from PyQt4.Qt import QTabWidget

from calibre.gui2.dialogs.config.add_save_ui import Ui_TabWidget
from calibre.library.save_to_disk import config, FORMAT_ARG_DESCS, \
                                         preprocess_template
from calibre.gui2 import error_dialog
from calibre.utils.config import prefs
from calibre.gui2.widgets import FilenamePattern

class AddSave(QTabWidget, Ui_TabWidget):

    def __init__(self, parent=None):
        QTabWidget.__init__(self, parent)
        self.setupUi(self)
        while self.count() > 2:
            self.removeTab(2)
        c = config()
        opts = c.parse()
        for x in ('asciiize', 'update_metadata', 'save_cover', 'write_opf',
                'replace_whitespace', 'to_lowercase'):
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
                opts.template, help)

        variables = sorted(FORMAT_ARG_DESCS.keys())
        rows = []
        for var in variables:
            rows.append(u'<tr><td>%s</td><td>%s</td></tr>'%
                    (var, FORMAT_ARG_DESCS[var]))
        table = u'<table>%s</table>'%(u'\n'.join(rows))
        self.template_variables.setText(table)

        self.opt_read_metadata_from_filename.setChecked(not prefs['read_file_metadata'])
        self.filename_pattern = FilenamePattern(self)
        self.metadata_box.layout().insertWidget(0, self.filename_pattern)
        self.opt_swap_author_names.setChecked(prefs['swap_author_names'])

    def validate(self):
        tmpl = preprocess_template(self.opt_template.text())
        fa = {}
        for x in FORMAT_ARG_DESCS.keys():
            fa[x]=''
        try:
            tmpl.format(**fa)
        except Exception, err:
            error_dialog(self, _('Invalid template'),
                    '<p>'+_('The template %s is invalid:')%tmpl + \
                    '<br>'+str(err), show=True)
            return False
        return True

    def save_settings(self):
        if not self.validate():
            return False
        c = config()
        for x in ('asciiize', 'update_metadata', 'save_cover', 'write_opf',
                'replace_whitespace', 'to_lowercase'):
            c.set(x, getattr(self, 'opt_'+x).isChecked())
        for x in ('formats', 'template', 'timefmt'):
            val = unicode(getattr(self, 'opt_'+x).text()).strip()
            if x == 'formats' and not val:
                val = 'all'
            c.set(x, val)
        self.opt_template.save_history('save_to_disk_template_history')
        prefs['read_file_metadata'] = not bool(self.opt_read_metadata_from_filename.isChecked())
        pattern = self.filename_pattern.commit()
        prefs['filename_pattern'] = pattern
        prefs['swap_author_names'] = bool(self.opt_swap_author_names.isChecked())

        return True



if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app=QApplication([])
    a = AddSave()
    a.show()
    app.exec_()
    a.save_settings()

