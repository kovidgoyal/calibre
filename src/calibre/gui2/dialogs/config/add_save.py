#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap

from PyQt4.Qt import QTabWidget

from calibre.gui2.dialogs.config.add_save_ui import Ui_TabWidget
from calibre.library.save_to_disk import config
from calibre.utils.config import prefs
from calibre.gui2.widgets import FilenamePattern

class AddSave(QTabWidget, Ui_TabWidget):

    def __init__(self, parent=None):
        QTabWidget.__init__(self, parent)
        self.setupUi(self)
        while self.count() > 3:
            self.removeTab(3)
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


        self.opt_read_metadata_from_filename.setChecked(not prefs['read_file_metadata'])
        self.filename_pattern = FilenamePattern(self)
        self.metadata_box.layout().insertWidget(0, self.filename_pattern)
        self.opt_swap_author_names.setChecked(prefs['swap_author_names'])
        self.opt_add_formats_to_existing.setChecked(prefs['add_formats_to_existing'])
        help = '\n'.join(textwrap.wrap(c.get_option('template').help, 75))
        self.save_template.initialize('save_to_disk', opts.template, help)
        self.send_template.initialize('send_to_device', opts.send_template, help)

    def validate(self):
        return self.save_template.validate() and self.send_template.validate()

    def save_settings(self):
        if not self.validate():
            return False
        c = config()
        for x in ('asciiize', 'update_metadata', 'save_cover', 'write_opf',
                'replace_whitespace', 'to_lowercase'):
            c.set(x, getattr(self, 'opt_'+x).isChecked())
        for x in ('formats', 'timefmt'):
            val = unicode(getattr(self, 'opt_'+x).text()).strip()
            if x == 'formats' and not val:
                val = 'all'
            c.set(x, val)
        self.save_template.save_settings(c, 'template')
        self.send_template.save_settings(c, 'send_template')
        prefs['read_file_metadata'] = not bool(self.opt_read_metadata_from_filename.isChecked())
        pattern = self.filename_pattern.commit()
        prefs['filename_pattern'] = pattern
        prefs['swap_author_names'] = bool(self.opt_swap_author_names.isChecked())
        prefs['add_formats_to_existing'] = bool(self.opt_add_formats_to_existing.isChecked())

        return True



if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    app=QApplication([])
    a = AddSave()
    a.show()
    app.exec_()
    a.save_settings()

