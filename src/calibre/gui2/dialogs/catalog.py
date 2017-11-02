#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, sys, importlib

from PyQt5.Qt import QDialog, QCoreApplication, QSize, QScrollArea

from calibre.customize.ui import config
from calibre.gui2.dialogs.catalog_ui import Ui_Dialog
from calibre.gui2 import dynamic, info_dialog
from calibre.customize.ui import catalog_plugins


class Catalog(QDialog, Ui_Dialog):

    ''' Catalog Dialog builder'''

    def __init__(self, parent, dbspec, ids, db):
        import re, cStringIO
        from calibre import prints as info
        from PyQt5.uic import compileUi

        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.dbspec, self.ids = dbspec, ids

        # Display the number of books we've been passed
        self.count.setText(unicode(self.count.text()).format(len(ids)))

        # Display the last-used title
        self.title.setText(dynamic.get('catalog_last_used_title',
            _('My books')))

        self.fmts, self.widgets = [], []

        for plugin in catalog_plugins():
            if plugin.name in config['disabled_plugins']:
                continue

            name = plugin.name.lower().replace(' ', '_')
            if getattr(plugin, 'plugin_path', None) is None:
                try:
                    catalog_widget = importlib.import_module('calibre.gui2.catalog.'+name)
                    pw = catalog_widget.PluginWidget()
                    pw.initialize(name, db)
                    pw.ICON = I('forward.png')
                    self.widgets.append(pw)
                    [self.fmts.append([file_type.upper(), pw.sync_enabled,pw]) for file_type in plugin.file_types]
                except ImportError:
                    info("ImportError initializing %s" % name)
                    continue
            else:
                # Load dynamic tab
                form = os.path.join(plugin.resources_path,'%s.ui' % name)
                klass = os.path.join(plugin.resources_path,'%s.py' % name)
                compiled_form = os.path.join(plugin.resources_path,'%s_ui.py' % name)

                if os.path.exists(form) and os.path.exists(klass):
                    # info("Adding widget for user-installed Catalog plugin %s" % plugin.name)

                    # Compile the .ui form provided in plugin.zip
                    if not os.path.exists(compiled_form):
                        # info('\tCompiling form', form)
                        buf = cStringIO.StringIO()
                        compileUi(form, buf)
                        dat = buf.getvalue()
                        dat = re.compile(r'QtGui.QApplication.translate\(.+?,\s+"(.+?)(?<!\\)",.+?\)',
                                         re.DOTALL).sub(r'_("\1")', dat)
                        open(compiled_form, 'wb').write(dat)

                    # Import the dynamic PluginWidget() from .py file provided in plugin.zip
                    try:
                        sys.path.insert(0, plugin.resources_path)
                        catalog_widget = importlib.import_module(name)
                        pw = catalog_widget.PluginWidget()
                        pw.initialize(name)
                        pw.ICON = I('forward.png')
                        self.widgets.append(pw)
                        [self.fmts.append([file_type.upper(), pw.sync_enabled,pw]) for file_type in plugin.file_types]
                    except ImportError:
                        info("ImportError with %s" % name)
                        continue
                    finally:
                        sys.path.remove(plugin.resources_path)

                else:
                    info("No dynamic tab resources found for %s" % name)

        self.widgets = sorted(self.widgets, cmp=lambda x,y:cmp(x.TITLE, y.TITLE))

        # Generate a sorted list of installed catalog formats/sync_enabled pairs
        fmts = sorted([x[0] for x in self.fmts])

        self.sync_enabled_formats = []
        for fmt in self.fmts:
            if fmt[1]:
                self.sync_enabled_formats.append(fmt[0])

        # Callbacks when format, title changes
        self.format.currentIndexChanged.connect(self.format_changed)
        self.format.currentIndexChanged.connect(self.settings_changed)
        self.title.editingFinished.connect(self.settings_changed)

        # Add the installed catalog format list to the format QComboBox
        self.format.blockSignals(True)
        self.format.addItems(fmts)

        pref = dynamic.get('catalog_preferred_format', 'CSV')
        idx = self.format.findText(pref)
        if idx > -1:
            self.format.setCurrentIndex(idx)
        self.format.blockSignals(False)

        if self.sync.isEnabled():
            self.sync.setChecked(dynamic.get('catalog_sync_to_device', True))
        self.add_to_library.setChecked(dynamic.get('catalog_add_to_library', True))

        self.format.currentIndexChanged.connect(self.show_plugin_tab)
        self.buttonBox.button(self.buttonBox.Apply).clicked.connect(self.apply)
        self.buttonBox.button(self.buttonBox.Help).clicked.connect(self.help)
        self.show_plugin_tab(None)

        geom = dynamic.get('catalog_window_geom', None)
        if geom is not None:
            self.restoreGeometry(bytes(geom))
        else:
            self.resize(self.sizeHint())

    def sizeHint(self):
        desktop = QCoreApplication.instance().desktop()
        geom = desktop.availableGeometry(self)
        nh, nw = max(300, geom.height()-50), max(400, geom.width()-70)
        return QSize(nw, nh)

    @property
    def options_widget(self):
        ans = self.tabs.widget(1)
        if isinstance(ans, QScrollArea):
            ans = ans.widget()
        return ans

    def show_plugin_tab(self, idx):
        cf = unicode(self.format.currentText()).lower()
        while self.tabs.count() > 1:
            self.tabs.removeTab(1)
        for pw in self.widgets:
            if cf in pw.formats:
                if getattr(pw, 'handles_scrolling', False):
                    self.tabs.addTab(pw, pw.TITLE)
                else:
                    self.sw__mem = s = QScrollArea(self)
                    s.setWidget(pw), s.setWidgetResizable(True)
                    self.tabs.addTab(s, pw.TITLE)
                break
        if hasattr(self.options_widget, 'show_help'):
            self.buttonBox.button(self.buttonBox.Help).setVisible(True)
        else:
            self.buttonBox.button(self.buttonBox.Help).setVisible(False)

    def format_changed(self, idx):
        cf = unicode(self.format.currentText())
        if cf in self.sync_enabled_formats:
            self.sync.setEnabled(True)
        else:
            self.sync.setDisabled(True)
            self.sync.setChecked(False)

    def settings_changed(self):
        '''
        When title/format change, invalidate Preset in E-book options tab
        '''
        cf = unicode(self.format.currentText()).lower()
        if cf in ['azw3', 'epub', 'mobi'] and hasattr(self.options_widget, 'settings_changed'):
            self.options_widget.settings_changed("title/format")

    @property
    def fmt_options(self):
        ans = {}
        if self.tabs.count() > 1:
            w = self.options_widget
            ans = w.options()
        return ans

    def save_catalog_settings(self):
        self.catalog_format = unicode(self.format.currentText())
        dynamic.set('catalog_preferred_format', self.catalog_format)
        self.catalog_title = unicode(self.title.text())
        dynamic.set('catalog_last_used_title', self.catalog_title)
        self.catalog_sync = bool(self.sync.isChecked())
        dynamic.set('catalog_sync_to_device', self.catalog_sync)
        dynamic.set('catalog_window_geom', bytearray(self.saveGeometry()))
        dynamic.set('catalog_add_to_library', self.add_to_library.isChecked())

    def apply(self, *args):
        # Store current values without building catalog
        self.save_catalog_settings()
        if self.tabs.count() > 1:
            self.options_widget.options()

    def accept(self):
        self.save_catalog_settings()
        return QDialog.accept(self)

    def help(self):
        '''
        To add help functionality for a specific format:
        In gui2.catalog.catalog_<format>.py, add the following:
            from calibre.gui2 import open_url
            from PyQt5.Qt import QUrl

        In the PluginWidget() class, add this method:
            def show_help(self):
                url = 'file:///' + P('catalog/help_<format>.html')
                open_url(QUrl(url))

        Create the help file at resources/catalog/help_<format>.html
        '''
        if self.tabs.count() > 1 and hasattr(self.options_widget,'show_help'):
            try:
                self.options_widget.show_help()
            except:
                info_dialog(self, _('No help available'),
                    _('No help available for this output format.'),
                    show_copy_button=False,
                    show=True)

    def reject(self):
        dynamic.set('catalog_window_geom', bytearray(self.saveGeometry()))
        QDialog.reject(self)
