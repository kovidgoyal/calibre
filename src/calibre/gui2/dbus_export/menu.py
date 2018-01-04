#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

# Support for excporting Qt's MenuBars/Menus over DBUS. The API is defined in
# dbus-menu.xml from the libdbusmenu project https://launchpad.net/libdbusmenu

import dbus, sip
from PyQt5.Qt import (
    QApplication, QMenu, QIcon, QKeySequence, QObject, QEvent, QTimer, pyqtSignal, Qt)

from calibre.utils.dbus_service import Object, BusName, method as dbus_method, dbus_property, signal as dbus_signal
from calibre.gui2.dbus_export.utils import (
    setup_for_cli_run, swap_mnemonic_char, key_sequence_to_dbus_shortcut, icon_to_dbus_menu_icon)

null = object()


def PropDict(mapping=()):
    return dbus.Dictionary(mapping, signature='sv')


def create_properties_for_action(ac, previous=None):
    ans = PropDict()
    if ac.isSeparator():
        ans['type'] = 'separator'
        if not ac.isVisible():
            ans['visible'] = False
        return ans
    text = ac.text() or ac.iconText()
    if text:
        ans['label'] = swap_mnemonic_char(text)
    if not ac.isEnabled():
        ans['enabled'] = False
    if not ac.isVisible() or ac.property('blocked') is True:
        ans['visible'] = False
    if ac.menu() is not None:
        ans['children-display'] = 'submenu'
    if ac.isCheckable():
        exclusive = ac.actionGroup() is not None and ac.actionGroup().isExclusive()
        ans['toggle-type'] = 'radio' if exclusive else 'checkmark'
        ans['toggle-state'] = int(ac.isChecked())
    shortcuts = ac.shortcuts()
    if shortcuts:
        sc = dbus.Array(signature='as')
        for s in shortcuts:
            if not s.isEmpty():
                for x in key_sequence_to_dbus_shortcut(s):
                    sc.append(dbus.Array(x, signature='s'))
        if sc:
            ans['shortcut'] = sc[:1]  # Unity fails to display the shortcuts at all if more than one is specified
    if ac.isIconVisibleInMenu():
        icon = ac.icon()
        if previous and previous.get('x-qt-icon-cache-key') == icon.cacheKey():
            for x in 'icon-data x-qt-icon-cache-key'.split():
                ans[x] = previous[x]
        else:
            data = icon_to_dbus_menu_icon(ac.icon())
            if data is not None:
                ans['icon-data'] = data
                ans['x-qt-icon-cache-key'] = icon.cacheKey()
    return ans


def menu_actions(menu):
    try:
        return menu.actions()
    except TypeError:
        if isinstance(menu, QMenu):
            return QMenu.actions(menu)
        raise


class DBusMenu(QObject):

    handle_event_signal = pyqtSignal(object, object, object, object)

    def __init__(self, object_path, parent=None, bus=None):
        QObject.__init__(self, parent)
        # Unity barfs is the Event DBUS method does not return immediately, so
        # handle it asynchronously
        self.handle_event_signal.connect(self.handle_event, type=Qt.QueuedConnection)
        self.dbus_api = DBusMenuAPI(self, object_path, bus=bus)
        self.set_status = self.dbus_api.set_status
        self._next_id = 0
        self.action_changed_timer = t = QTimer(self)
        t.setInterval(0), t.setSingleShot(True), t.timeout.connect(self.actions_changed)
        self.layout_changed_timer = t = QTimer(self)
        t.setInterval(0), t.setSingleShot(True), t.timeout.connect(self.layouts_changed)
        self.init_maps()

    @property
    def object_path(self):
        return self.dbus_api._object_path

    def init_maps(self, qmenu=None):
        self.action_changes = set()
        self.layout_changes = set()
        self.qmenu = qmenu
        self._id_to_action, self._action_to_id = {}, {}
        self._action_properties = {}

    @property
    def next_id(self):
        self._next_id += 1
        return self._next_id

    def id_to_action(self, action_id):
        if self.qmenu is None:
            return None
        return self._id_to_action.get(action_id)

    def action_to_id(self, action):
        if self.qmenu is None:
            return None
        return self._action_to_id.get(action)

    def action_properties(self, action_id, restrict_to=None):
        if self.qmenu is None:
            return {}
        ans = self._action_properties.get(action_id, PropDict())
        if restrict_to:
            ans = PropDict({k:v for k, v in ans.iteritems() if k in restrict_to})
        return ans

    def publish_new_menu(self, qmenu=None):
        self.init_maps(qmenu)
        if qmenu is not None:
            qmenu.destroyed.connect(lambda obj=None:self.publish_new_menu())
            ac = qmenu.menuAction()
            self.add_action(ac)
        self.dbus_api.LayoutUpdated(self.dbus_api.revision, 0)

    def set_visible(self, visible):
        ac = self.id_to_action(0)
        if ac is not None and self.qmenu is not None:
            changed = False
            blocked = not visible
            for ac in menu_actions(ac.menu()):
                ac_id = self.action_to_id(ac)
                if ac_id is not None:
                    old = ac.property('blocked')
                    if old is not blocked:
                        ac.setProperty('blocked', blocked)
                        self.action_changes.add(ac_id)
                        changed = True
            if changed:
                self.action_changed_timer.start()

    def add_action(self, ac):
        ac_id = 0 if ac.menu() is self.qmenu else self.next_id
        self._id_to_action[ac_id] = ac
        self._action_to_id[ac] = ac_id
        self._action_properties[ac_id] = create_properties_for_action(ac)
        if ac.menu() is not None:
            self.add_menu(ac.menu())

    def add_menu(self, menu):
        menu.installEventFilter(self)
        for ac in menu_actions(menu):
            self.add_action(ac)

    def eventFilter(self, obj, ev):
        ac = getattr(obj, 'menuAction', lambda : None)()
        ac_id = self.action_to_id(ac)
        if ac_id is not None:
            etype = ev.type()
            if etype == QEvent.ActionChanged:
                ac_id = self.action_to_id(ev.action())
                self.action_changes.add(ac_id)
                self.action_changed_timer.start()
            elif etype == QEvent.ActionAdded:
                self.layout_changes.add(ac_id)
                self.layout_changed_timer.start()
                self.add_action(ev.action())
            elif etype == QEvent.ActionRemoved:
                self.layout_changes.add(ac_id)
                self.layout_changed_timer.start()
                self.action_removed(ev.action())
        return False

    def actions_changed(self):
        updated_props = dbus.Array(signature='(ia{sv})')
        removed_props = dbus.Array(signature='(ias)')
        for ac_id in self.action_changes:
            ac = self.id_to_action(ac_id)
            if ac is None:
                continue
            old_props = self.action_properties(ac_id)
            new_props = self._action_properties[ac_id] = create_properties_for_action(ac, old_props)
            removed = set(old_props) - set(new_props)
            if removed:
                removed_props.append((ac_id, dbus.Array(removed, signature='as')))
            updated = PropDict({k:v for k, v in new_props.iteritems() if v != old_props.get(k, null)})
            if updated:
                updated_props.append((ac_id, updated))
        self.action_changes = set()
        if updated_props or removed_props:
            self.dbus_api.ItemsPropertiesUpdated(updated_props, removed_props)
        return updated_props, removed_props

    def layouts_changed(self):
        changes = set()
        for ac_id in self.layout_changes:
            if ac_id in self._id_to_action:
                changes.add(ac_id)
        self.layout_changes = set()
        if changes:
            self.dbus_api.revision += 1
            for change in changes:
                self.dbus_api.LayoutUpdated(self.dbus_api.revision, change)
        return changes

    def action_is_in_a_menu(self, ac):
        if sip.isdeleted(ac):
            return False
        all_menus = {a.menu() for a in self._action_to_id if not sip.isdeleted(a)}
        all_menus.discard(None)
        return bool(set(ac.associatedWidgets()).intersection(all_menus))

    def action_removed(self, ac):
        if not self.action_is_in_a_menu(ac):
            ac_id = self._action_to_id.pop(ac, None)
            self._id_to_action.pop(ac_id, None)
            self._action_properties.pop(ac_id, None)

    def get_layout(self, parent_id, depth, property_names):
        # Ensure any pending updates are done, as they are needed now
        self.actions_changed()
        self.layouts_changed()
        property_names = property_names or None
        props = self.action_properties(parent_id, property_names)
        return parent_id, props, self.get_layout_children(parent_id, depth, property_names)

    def get_layout_children(self, parent_id, depth, property_names):
        ans = dbus.Array(signature='v')
        ac = self.id_to_action(parent_id)
        if ac is not None and depth != 0 and ac.menu() is not None:
            for child in menu_actions(ac.menu()):
                child_id = self.action_to_id(child)
                if child_id is not None:
                    props = self.action_properties(child_id, property_names)
                    ans.append((child_id, props, self.get_layout_children(child_id, depth - 1, property_names)))
        return ans

    def get_properties(self, ids=None, property_names=None):
        property_names = property_names or None
        ans = dbus.Array(signature='(ia{sv})')
        for action_id in (ids or self._id_to_action):
            ans.append((action_id, self.action_properties(action_id, property_names)))
        return ans

    def handle_event(self, action_id, event, data, timestamp):
        ac = self.id_to_action(action_id)
        if event == 'clicked':
            if ac.isCheckable():
                ac.toggle()
            ac.triggered.emit(ac.isCheckable() and ac.isChecked())

    def handle_about_to_show(self, ac):
        child_ids = {self.action_to_id(x) for x in menu_actions(ac.menu())}
        child_ids.discard(None)
        ac_id = self.action_to_id(ac)
        ac.menu().aboutToShow.emit()
        if ac_id in self.layout_changes or child_ids.intersection(self.action_changes):
            return True
        return False


class DBusMenuAPI(Object):

    IFACE = 'com.canonical.dbusmenu'

    def __init__(self, menu, object_path, bus=None):
        if bus is None:
            bus = dbus.SessionBus()
        Object.__init__(self, bus, object_path)
        self.status = 'normal'
        self.menu = menu
        self.revision = 0

    @dbus_property(IFACE, signature='u')
    def Version(self):
        return 3  # GTK 3 uses 3, KDE 4 uses 2

    @dbus_property(IFACE, signature='s', emits_changed_signal=True)
    def Status(self):
        return self.status

    def set_status(self, normal=True):
        self.status = 'normal' if normal else 'notice'
        self.PropertiesChanged(self.IFACE, {'Status': self.status}, [])

    @dbus_property(IFACE, signature='s')
    def TextDirection(self):
        return 'ltr' if QApplication.instance().isLeftToRight() else 'rtl'

    @dbus_property(IFACE, signature='as')
    def IconThemePath(self):
        return dbus.Array(signature='s')

    @dbus_method(IFACE, in_signature='iias', out_signature='u(ia{sv}av)')
    def GetLayout(self, parentId, recursionDepth, propertyNames):
        layout = self.menu.get_layout(parentId, recursionDepth, propertyNames)
        return self.revision, layout

    @dbus_method(IFACE, in_signature='aias', out_signature='a(ia{sv})')
    def GetGroupProperties(self, ids, propertyNames):
        return self.menu.get_properties(ids, propertyNames)

    @dbus_method(IFACE, in_signature='is', out_signature='v')
    def GetProperty(self, id, name):
        return self.menu.action_properties(id).get(name, '')

    @dbus_method(IFACE, in_signature='isvu', out_signature='')
    def Event(self, id, eventId, data, timestamp):
        ''' This is called by the applet to notify the application an event happened on a
        menu item. eventId can be one of the following::
            * "clicked"
            * "hovered"
            * "opened"
            * "closed"
        Vendor specific events can be added by prefixing them with "x-<vendor>-"'''
        if self.menu.id_to_action(id) is not None:
            self.menu.handle_event_signal.emit(id, eventId, data, timestamp)

    @dbus_method(IFACE, in_signature='a(isvu)', out_signature='ai')
    def EventGroup(self, events):
        ''' Used to pass a set of events as a single message for possibily
        several different menuitems.  This is done to optimize DBus traffic.
        Should return a list of ids that are not found. events is a list of
        events in the same format as used for the Event method.'''
        missing = dbus.Array(signature='u')
        for id, eventId, data, timestamp in events:
            if self.menu.id_to_action(id) is not None:
                self.menu.handle_event_signal.emit(id, eventId, data, timestamp)
            else:
                missing.append(id)
        return missing

    @dbus_method(IFACE, in_signature='i', out_signature='b')
    def AboutToShow(self, id):
        ac = self.menu.id_to_action(id)
        if ac is not None and ac.menu() is not None:
            return self.menu.handle_about_to_show(ac)
        return False

    @dbus_method(IFACE, in_signature='ai', out_signature='aiai')
    def AboutToShowGroup(self, ids):
        updates_needed = dbus.Array(signature='i')
        id_errors = dbus.Array(signature='i')
        for ac_id in ids:
            ac = self.menu.id_to_action(id)
            if ac is not None and ac.menu() is not None:
                if self.menu.handle_about_to_show(ac):
                    updates_needed.append(ac_id)
            else:
                id_errors.append(ac_id)
        return updates_needed, id_errors

    @dbus_signal(IFACE, 'a(ia{sv})a(ias)')
    def ItemsPropertiesUpdated(self, updatedProps, removedProps):
        pass

    @dbus_signal(IFACE, 'ui')
    def LayoutUpdated(self, revision, parent):
        pass

    @dbus_signal(IFACE, 'iu')
    def ItemActivationRequested(self, id, timestamp):
        pass


def test():
    setup_for_cli_run()
    app = QApplication([])
    bus = dbus.SessionBus()
    dbus_name = BusName('com.calibre-ebook.TestDBusMenu', bus=bus, do_not_queue=True)
    m = QMenu()
    ac = m.addAction(QIcon(I('window-close.png')), 'Quit', app.quit)
    ac.setShortcut(QKeySequence('Ctrl+Q'))
    menu = DBusMenu('/Menu', bus=bus)
    menu.publish_new_menu(m)
    app.exec_()
    del dbus_name


if __name__ == '__main__':
    test()
