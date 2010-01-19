#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, shutil, sys, tempfile

from PyQt4.Qt import QDialog, QWidget

from calibre.customize.ui import config
from calibre.gui2.dialogs.catalog_ui import Ui_Dialog
from calibre.gui2 import dynamic
from calibre.customize.ui import available_catalog_formats, catalog_plugins
from calibre.gui2.catalog.catalog_csv_xml import PluginWidget

class Catalog(QDialog, Ui_Dialog):

    def __init__(self, parent, dbspec, ids):
        import re, cStringIO
        from calibre import prints as info
        from PyQt4.uic import compileUi
        
        QDialog.__init__(self, parent)
        
        # Run the dialog setup generated from catalog.ui
        self.setupUi(self)
        self.dbspec, self.ids = dbspec, ids

        # Display the number of books we've been passed
        self.count.setText(unicode(self.count.text()).format(len(ids)))

        # Display the last-used title
        self.title.setText(dynamic.get('catalog_last_used_title',
            _('My Books')))

        # GwR *** Add option tabs for built-in formats
        # This code models #69 in calibre/gui2/dialogs/config/__init__.py

        self.fmts = []
        
        from calibre.customize.builtins import plugins as builtin_plugins

        for plugin in catalog_plugins():
            if plugin.name in config['disabled_plugins']:
                continue
                
            name = plugin.name.lower().replace(' ', '_')
            if type(plugin) in builtin_plugins:
                info("Adding tab for builtin Catalog plugin %s" % plugin.name)                
                try:
                    catalog_widget = __import__('calibre.gui2.catalog.'+name,
                            fromlist=[1])
                    pw = catalog_widget.PluginWidget()
                    pw.initialize()
                    pw.ICON = I('forward.svg')    
                    page = self.tabs.addTab(pw,pw.TITLE)
                    [self.fmts.append([file_type, pw.sync_enabled]) for file_type in plugin.file_types]
                    info("\tSupported formats: %s" % plugin.file_types)
                    info("\tsync_enabled: %s" % pw.sync_enabled)
    
                except ImportError:
                    info("ImportError with %s" % name)
                    continue
            else:
                # Test to see if .ui and .py files exist in tmpdir/calibre_plugin_resources
                form = os.path.join(tempfile.gettempdir(),
                                    'calibre_plugin_resources','%s.ui' % name)
                klass = os.path.join(tempfile.gettempdir(),
                                  'calibre_plugin_resources','%s.py' % name)
                compiled_form = os.path.join(tempfile.gettempdir(),
                                  'calibre_plugin_resources','%s_ui.py' % name)
                plugin_resources = os.path.join(tempfile.gettempdir(),'calibre_plugin_resources')        

                if os.path.exists(form) and os.path.exists(klass):
                    info("Adding tab for user-installed Catalog plugin %s" % plugin.name)
                    
                    # Compile the form provided in plugin.zip
                    if not os.path.exists(compiled_form) or \
                       os.stat(form).st_mtime > os.stat(compiled_form).st_mtime:
                        info('\tCompiling form', form)
                        buf = cStringIO.StringIO()
                        compileUi(form, buf)
                        dat = buf.getvalue()
                        dat = re.compile(r'QtGui.QApplication.translate\(.+?,\s+"(.+?)(?<!\\)",.+?\)', 
                                         re.DOTALL).sub(r'_("\1")', dat)
                        open(compiled_form, 'wb').write(dat)
                    
                    # Import the Catalog class from the dynamic .py file
                    try:
                        sys.path.insert(0, plugin_resources)
                        catalog_widget = __import__(name, fromlist=[1])
                        dpw = catalog_widget.PluginWidget()
                        dpw.initialize()
                        dpw.ICON = I('forward.svg')    
                        page = self.tabs.addTab(dpw, dpw.TITLE)
                        [self.fmts.append([file_type, dpw.sync_enabled]) for file_type in plugin.file_types]
                        info("\tSupported formats: %s" % plugin.file_types)
                        info("\tsync_enabled: %s" % dpw.sync_enabled)
                    except ImportError:
                        info("ImportError with %s" % name)
                        continue
                    finally:
                        sys.path.remove(plugin_resources)
                        
                else:
                    info("No dynamic tab resources found for %s" % name)

        # Generate a sorted list of installed catalog formats/sync_enabled pairs
        # Generate a parallel list of sync_enabled[True|False]ß
        self.fmts = sorted([x[0].upper() for x in self.fmts])

        # Callback when format changes
        self.format.currentIndexChanged.connect(self.format_changed)

        # Add the installed catalog format list to the format QComboBox
        self.format.addItems(self.fmts)

        pref = dynamic.get('catalog_preferred_format', 'CSV')
        idx = self.format.findText(pref)
        if idx > -1:
            self.format.setCurrentIndex(idx)

        if self.sync.isEnabled():
            self.sync.setChecked(dynamic.get('catalog_sync_to_device', True))
                            
    def format_changed(self, idx):
        print "format_changed(idx): idx: %d" % idx
        cf = unicode(self.format.currentText())
        if cf in ('EPUB', 'MOBI'):
            self.sync.setEnabled(True)
        else:
            self.sync.setDisabled(True)
            self.sync.setChecked(False)

    def accept(self):
        self.catalog_format = unicode(self.format.currentText())
        dynamic.set('catalog_preferred_format', self.catalog_format)
        self.catalog_title = unicode(self.title.text())
        dynamic.set('catalog_last_used_title', self.catalog_title)
        self.catalog_sync = bool(self.sync.isChecked())
        dynamic.set('catalog_sync_to_device', self.catalog_sync)
        QDialog.accept(self)
