#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt4.Qt import (QWidget, QGridLayout, QGroupBox, QListView, Qt)
from calibre.gui2.preferences.metadata_sources import FieldsModel as FM

class FieldsModel(FM): # {{{

    def __init__(self, plugin):
        FM.__init__(self)
        self.plugin = plugin
        self.exclude = frozenset(['title', 'authors']) | self.exclude
        self.prefs = self.plugin.prefs

    def initialize(self):
        fields = self.plugin.touched_fields
        self.fields = []
        for x in fields:
            if not x.startswith('identifier:') and x not in self.exclude:
                self.fields.append(x)
        self.fields.sort(key=lambda x:self.descs.get(x, x))
        self.reset()

    def state(self, field, defaults=False):
        src = self.prefs.defaults if defaults else self.prefs
        return (Qt.Unchecked if field in src['ignore_fields']
                    else Qt.Checked)

    def restore_defaults(self):
        self.overrides = dict([(f, self.state(f, True)) for f in self.fields])
        self.reset()

    def commit(self):
        val = [k for k, v in self.overrides.iteritems() if v == Qt.Unchecked]
        self.prefs['ignore_fields'] = val

# }}}

class ConfigWidget(QWidget):

    def __init__(self, plugin):
        QWidget.__init__(self)
        self.plugin = plugin

        self.l = l = QGridLayout()
        self.setLayout(l)

        self.gb = QGroupBox(_('Downloaded metadata fields'), self)
        l.addWidget(self.gb, 0, 0)
        self.gb.l = QGridLayout()
        self.gb.setLayout(self.gb.l)
        self.fields_view = v = QListView(self)
        self.gb.l.addWidget(v, 0, 0)
        v.setFlow(v.LeftToRight)
        v.setWrapping(True)
        v.setResizeMode(v.Adjust)
        self.fields_model = FieldsModel(self.plugin)
        self.fields_model.initialize()
        v.setModel(self.fields_model)

    def commit(self):
        self.fields_model.commit()

