#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap, os, glob

from calibre.customize import FileTypePlugin
from calibre.constants import numeric_version
from polyglot.builtins import unicode_type


class HTML2ZIP(FileTypePlugin):
    name = 'HTML to ZIP'
    author = 'Kovid Goyal'
    description = textwrap.dedent(_('''\
Follow all local links in an HTML file and create a ZIP \
file containing all linked files. This plugin is run \
every time you add an HTML file to the library.\
'''))
    version = numeric_version
    file_types = {'html', 'htm', 'xhtml', 'xhtm', 'shtm', 'shtml'}
    supported_platforms = ['windows', 'osx', 'linux']
    on_import = True

    def run(self, htmlfile):
        import codecs
        from calibre import prints
        from calibre.ptempfile import TemporaryDirectory
        from calibre.gui2.convert.gui_conversion import gui_convert
        from calibre.customize.conversion import OptionRecommendation
        from calibre.ebooks.epub import initialize_container

        with TemporaryDirectory('_plugin_html2zip') as tdir:
            recs =[('debug_pipeline', tdir, OptionRecommendation.HIGH)]
            recs.append(['keep_ligatures', True, OptionRecommendation.HIGH])
            if self.site_customization and self.site_customization.strip():
                sc = self.site_customization.strip()
                enc, _, bf = sc.partition('|')
                if enc:
                    try:
                        codecs.lookup(enc)
                    except Exception:
                        prints('Ignoring invalid input encoding for HTML:', enc)
                    else:
                        recs.append(['input_encoding', enc, OptionRecommendation.HIGH])
                if bf == 'bf':
                    recs.append(['breadth_first', True,
                        OptionRecommendation.HIGH])
            gui_convert(htmlfile, tdir, recs, abort_after_input_dump=True)
            of = self.temporary_file('_plugin_html2zip.zip')
            tdir = os.path.join(tdir, 'input')
            opf = glob.glob(os.path.join(tdir, '*.opf'))[0]
            ncx = glob.glob(os.path.join(tdir, '*.ncx'))
            if ncx:
                os.remove(ncx[0])
            epub = initialize_container(of.name, os.path.basename(opf))
            epub.add_dir(tdir)
            epub.close()

        return of.name

    def customization_help(self, gui=False):
        return _('Character encoding for the input HTML files. Common choices '
        'include: cp1252, cp1251, latin1 and utf-8.')

    def do_user_config(self, parent=None):
        '''
        This method shows a configuration dialog for this plugin. It returns
        True if the user clicks OK, False otherwise. The changes are
        automatically applied.
        '''
        from PyQt5.Qt import (QDialog, QDialogButtonBox, QVBoxLayout,
                QLabel, Qt, QLineEdit, QCheckBox)

        config_dialog = QDialog(parent)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        v = QVBoxLayout(config_dialog)

        def size_dialog():
            config_dialog.resize(config_dialog.sizeHint())

        button_box.accepted.connect(config_dialog.accept)
        button_box.rejected.connect(config_dialog.reject)
        config_dialog.setWindowTitle(_('Customize') + ' ' + self.name)
        from calibre.customize.ui import (plugin_customization,
                customize_plugin)
        help_text = self.customization_help(gui=True)
        help_text = QLabel(help_text, config_dialog)
        help_text.setWordWrap(True)
        help_text.setTextInteractionFlags(Qt.LinksAccessibleByMouse | Qt.LinksAccessibleByKeyboard)
        help_text.setOpenExternalLinks(True)
        v.addWidget(help_text)
        bf = QCheckBox(_('Add linked files in breadth first order'))
        bf.setToolTip(_('Normally, when following links in HTML files'
            ' calibre does it depth first, i.e. if file A links to B and '
            ' C, but B links to D, the files are added in the order A, B, D, C. '
            ' With this option, they will instead be added as A, B, C, D'))
        sc = plugin_customization(self)
        if not sc:
            sc = ''
        sc = sc.strip()
        enc = sc.partition('|')[0]
        bfs = sc.partition('|')[-1]
        bf.setChecked(bfs == 'bf')
        sc = QLineEdit(enc, config_dialog)
        v.addWidget(sc)
        v.addWidget(bf)
        v.addWidget(button_box)
        size_dialog()
        config_dialog.exec_()

        if config_dialog.result() == QDialog.Accepted:
            sc = unicode_type(sc.text()).strip()
            if bf.isChecked():
                sc += '|bf'
            customize_plugin(self, sc)

        return config_dialog.result()
