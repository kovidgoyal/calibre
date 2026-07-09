#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import glob
import os
import textwrap

from calibre.constants import numeric_version
from calibre.customize import FileTypePlugin


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

    def parse_my_settings(self, sc):
        if not sc:
            sc = ''
        if sc.startswith('{'):
            import json
            try:
                return json.loads(sc)
            except Exception:
                return {}
        else:
            sc = sc.strip()
            enc, _, bfs = sc.partition('|')
            return {'encoding': enc, 'breadth_first': bfs == 'bf'}

    def run(self, htmlfile):
        import codecs

        from calibre import prints
        from calibre.customize.conversion import OptionRecommendation
        from calibre.ebooks.epub import initialize_container
        from calibre.gui2.convert.gui_conversion import gui_convert
        from calibre.ptempfile import TemporaryDirectory

        with TemporaryDirectory('_plugin_html2zip') as tdir:
            recs =[('debug_pipeline', tdir, OptionRecommendation.HIGH)]
            recs.append(['keep_ligatures', True, OptionRecommendation.HIGH])
            if self.site_customization and self.site_customization.strip():
                settings = self.parse_my_settings(self.site_customization)
                enc = settings.get('encoding')
                if enc:
                    try:
                        codecs.lookup(enc)
                    except Exception:
                        prints('Ignoring invalid input encoding for HTML:', enc)
                    else:
                        recs.append(['input_encoding', enc, OptionRecommendation.HIGH])
                if settings.get('breadth_first'):
                    recs.append(['breadth_first', True, OptionRecommendation.HIGH])
                if settings.get('allow_local_files_outside_root'):
                    recs.append(['allow_local_files_outside_root', True, OptionRecommendation.HIGH])
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
        'include: utf-8, cp1252, cp1251 and latin1.')

    def do_user_config(self, parent=None):
        '''
        This method shows a configuration dialog for this plugin. It returns
        True if the user clicks OK, False otherwise. The changes are
        automatically applied.
        '''
        import json

        from qt.core import QCheckBox, QDialog, QDialogButtonBox, QLabel, QLineEdit, Qt, QVBoxLayout

        config_dialog = QDialog(parent)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        v = QVBoxLayout(config_dialog)

        def size_dialog():
            config_dialog.resize(config_dialog.sizeHint())

        button_box.accepted.connect(config_dialog.accept)
        button_box.rejected.connect(config_dialog.reject)
        config_dialog.setWindowTitle(_('Customize') + ' ' + self.name)
        from calibre.customize.ui import customize_plugin, plugin_customization
        help_text = self.customization_help(gui=True)
        help_text = QLabel(help_text, config_dialog)
        help_text.setWordWrap(True)
        help_text.setMinimumWidth(300)
        help_text.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse | Qt.TextInteractionFlag.LinksAccessibleByKeyboard)
        help_text.setOpenExternalLinks(True)
        v.addWidget(help_text)
        bf = QCheckBox(_('Add linked files in breadth first order'))
        bf.setToolTip(_('Normally, when following links in HTML files'
            ' calibre does it depth first, i.e. if file A links to B and '
            ' C, but B links to D, the files are added in the order A, B, D, C. '
            ' With this option, they will instead be added as A, B, C, D'))
        lr = QCheckBox(_('Allow resources outside the HTML file root folder'))
        from calibre.customize.ui import plugin_for_input_format
        hi = plugin_for_input_format('html')
        for opt in hi.options:
            if opt.option.name == 'allow_local_files_outside_root':
                lr.setToolTip(opt.help)
                break
        settings = self.parse_my_settings(plugin_customization(self))
        bf.setChecked(bool(settings.get('breadth_first')))
        lr.setChecked(bool(settings.get('allow_local_files_outside_root')))
        sc = QLineEdit(str(settings.get('encoding', '')), config_dialog)
        v.addWidget(sc)
        v.addWidget(bf)
        v.addWidget(lr)
        v.addWidget(button_box)
        size_dialog()
        config_dialog.exec()

        if config_dialog.result() == QDialog.DialogCode.Accepted:
            settings = {}
            enc = str(sc.text()).strip()
            if enc:
                settings['encoding'] = enc
            if bf.isChecked():
                settings['breadth_first'] = True
            if lr.isChecked():
                settings['allow_local_files_outside_root'] = True
            customize_plugin(self, json.dumps(settings, ensure_ascii=True))

        return config_dialog.result()
