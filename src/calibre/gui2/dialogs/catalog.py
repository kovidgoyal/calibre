#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import importlib
import os
import sys
import weakref
from qt.core import (
    QDialog, QDialogButtonBox, QScrollArea, QSize
)

from calibre.customize import PluginInstallationType
from calibre.customize.ui import catalog_plugins, config
from calibre.gui2 import dynamic, info_dialog
from calibre.gui2.dialogs.catalog_ui import Ui_Dialog


class Catalog(QDialog, Ui_Dialog):

    ''' Catalog Dialog builder'''

    def __init__(self, parent, dbspec, ids, db):
        import re
        from PyQt6.uic import compileUi

        from calibre import prints as info

        QDialog.__init__(self, parent)
        self.setupUi(self)
        self.dbspec, self.ids = dbspec, ids

        # Display the number of books we've been passed
        self.count.setText(str(self.count.text()).format(len(ids)))

        # Display the last-used title
        self.title.setText(dynamic.get('catalog_last_used_title',
            _('My books')))

        self.fmts, self.widgets = [], []

        for plugin in catalog_plugins():
            if plugin.name in config['disabled_plugins']:
                continue

            name = plugin.name.lower().replace(' ', '_')
            if getattr(plugin, 'installation_type', None) is PluginInstallationType.BUILTIN:
                try:
                    catalog_widget = importlib.import_module('calibre.gui2.catalog.'+name)
                    pw = catalog_widget.PluginWidget()
                    pw.parent_ref = weakref.ref(self)
                    pw.initialize(name, db)
                    pw.ICON = 'forward.png'
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
                        from polyglot.io import PolyglotStringIO

                        # info('\tCompiling form', form)
                        buf = PolyglotStringIO()
                        compileUi(form, buf)
                        dat = buf.getvalue()
                        dat = re.compile(r'QtGui.QApplication.translate\(.+?,\s+"(.+?)(?<!\\)",.+?\)',
                                         re.DOTALL).sub(r'_("\1")', dat)
                        open(compiled_form, 'wb').write(dat.encode('utf-8'))

                    # Import the dynamic PluginWidget() from .py file provided in plugin.zip
                    try:
                        sys.path.insert(0, plugin.resources_path)
                        catalog_widget = importlib.import_module(name)
                        pw = catalog_widget.PluginWidget()
                        pw.initialize(name)
                        pw.ICON = 'forward.png'
                        self.widgets.append(pw)
                        [self.fmts.append([file_type.upper(), pw.sync_enabled,pw]) for file_type in plugin.file_types]
                    except ImportError:
                        info("ImportError with %s" % name)
                        continue
                    finally:
                        sys.path.remove(plugin.resources_path)

                else:
                    info("No dynamic tab resources found for %s" % name)

        self.widgets = sorted(self.widgets, key=lambda x: x.TITLE)

        # Generate a sorted list of installed catalog formats/sync_enabled pairs
        fmts = sorted(x[0] for x in self.fmts)

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
        self.buttonBox.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        self.buttonBox.button(QDialogButtonBox.StandardButton.Help).clicked.connect(self.help)
        self.show_plugin_tab(None)

        self.restore_geometry(dynamic, 'catalog_window_geom')
        g = self.screen().availableSize()
        self.setMaximumWidth(g.width() - 50)
        self.setMaximumHeight(g.height() - 50)

    def sizeHint(self):
        geom = self.screen().availableSize()
        nh, nw = max(300, geom.height()-50), max(400, geom.width()-70)
        return QSize(nw, nh)

    @property
    def options_widget(self):
        ans = self.tabs.widget(1)
        if isinstance(ans, QScrollArea):
            ans = ans.widget()
        return ans

    def show_plugin_tab(self, idx):
        cf = str(self.format.currentText()).lower()
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
            self.buttonBox.button(QDialogButtonBox.StandardButton.Help).setVisible(True)
        else:
            self.buttonBox.button(QDialogButtonBox.StandardButton.Help).setVisible(False)

    def format_changed(self, idx):
        cf = str(self.format.currentText())
        if cf in self.sync_enabled_formats:
            self.sync.setEnabled(True)
        else:
            self.sync.setDisabled(True)
            self.sync.setChecked(False)

    def settings_changed(self):
        '''
        When title/format change, invalidate Preset in E-book options tab
        '''
        cf = str(self.format.currentText()).lower()
        if cf in ('azw3', 'epub', 'mobi') and hasattr(self.options_widget, 'settings_changed'):
            self.options_widget.settings_changed("title/format")

    @property
    def fmt_options(self):
        ans = {}
        if self.tabs.count() > 1:
            w = self.options_widget
            ans = w.options()
        return ans

    def save_catalog_settings(self):
        self.catalog_format = str(self.format.currentText())
        dynamic.set('catalog_preferred_format', self.catalog_format)
        self.catalog_title = str(self.title.text())
        dynamic.set('catalog_last_used_title', self.catalog_title)
        self.catalog_sync = bool(self.sync.isChecked())
        dynamic.set('catalog_sync_to_device', self.catalog_sync)
        self.save_geometry(dynamic, 'catalog_window_geom')
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
            from qt.core import QUrl

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
        self.save_geometry(dynamic, 'catalog_window_geom')
        QDialog.reject(self)
