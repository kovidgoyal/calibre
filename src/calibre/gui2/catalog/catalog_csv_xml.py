#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2 import gprefs
from calibre.gui2.ui import get_gui
from PyQt5.Qt import QWidget, QListWidgetItem, Qt, QVBoxLayout, QLabel, QListWidget


class PluginWidget(QWidget):

    TITLE = _('CSV/XML options')
    HELP  = _('Options specific to')+' CSV/XML '+_('output')
    sync_enabled = False
    formats = set(['csv', 'xml'])

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.la = la = QLabel(_('Fields to include in output:'))
        la.setWordWrap(True)
        l.addWidget(la)
        self.db_fields = QListWidget(self)
        l.addWidget(self.db_fields)
        self.la2 = la = QLabel(_('Drag and drop to re-arrange fields'))
        l.addWidget(la)
        self.db_fields.setDragEnabled(True)
        self.db_fields.setDragDropMode(QListWidget.InternalMove)
        self.db_fields.setDefaultDropAction(Qt.MoveAction)
        self.db_fields.setAlternatingRowColors(True)
        self.db_fields.setObjectName("db_fields")

    def initialize(self, catalog_name, db):
        self.name = catalog_name
        from calibre.library.catalogs import FIELDS
        db = get_gui().current_db
        self.all_fields = {x for x in FIELDS if x != 'all'} | set(db.custom_field_keys())
        sort_order = gprefs.get(self.name + '_db_fields_sort_order', {})
        fm = db.field_metadata

        def name(x):
            if x == 'isbn':
                return 'ISBN'
            if x == 'library_name':
                return _('Library name')
            if x.endswith('_index'):
                return name(x[:-len('_index')]) + ' ' + _('Number')
            return fm[x].get('name') or x

        def key(x):
            return (sort_order.get(x, 10000), name(x))

        self.db_fields.clear()
        for x in sorted(self.all_fields, key=key):
            QListWidgetItem(name(x) + ' (%s)' % x, self.db_fields).setData(Qt.UserRole, x)
            if x.startswith('#') and fm[x]['datatype'] == 'series':
                x += '_index'
                QListWidgetItem(name(x) + ' (%s)' % x, self.db_fields).setData(Qt.UserRole, x)

        # Restore the activated fields from last use
        fields = frozenset(gprefs.get(self.name+'_db_fields', self.all_fields))
        for x in range(self.db_fields.count()):
            item = self.db_fields.item(x)
            item.setCheckState(Qt.Checked if unicode(item.data(Qt.UserRole)) in fields else Qt.Unchecked)

    def options(self):
        # Save the currently activated fields
        fields, all_fields = [], []
        for x in xrange(self.db_fields.count()):
            item = self.db_fields.item(x)
            all_fields.append(unicode(item.data(Qt.UserRole)))
            if item.checkState() == Qt.Checked:
                fields.append(unicode(item.data(Qt.UserRole)))
        gprefs.set(self.name+'_db_fields', fields)
        gprefs.set(self.name + '_db_fields_sort_order', {x:i for i, x in enumerate(all_fields)})

        # Return a dictionary with current options for this widget
        if len(fields):
            return {'fields':fields}
        else:
            return {'fields':['all']}
