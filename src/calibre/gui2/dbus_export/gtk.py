#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

# Demo program to explore the GTK DBus interface, which is only partially documented
# at https://wiki.gnome.org/Projects/GLib/GApplication/DBusAPI

import sys, dbus, struct, time, signal
from threading import Thread
from pprint import pformat

from gi.repository import Gtk, Gdk, GdkX11  # noqa

from polyglot.builtins import unicode_type, iteritems

UI_INFO = """
<ui>
  <menubar name='MenuBar'>
    <menu action='FileMenu'>
      <menu action='FileNew'>
        <menuitem action='FileNewStandard' />
        <menuitem action='FileNewFoo' />
        <menuitem action='FileNewGoo' />
      </menu>
      <separator />
      <menuitem action='FileQuit' />
    </menu>
    <menu action='EditMenu'>
      <menuitem action='EditCopy' />
      <menuitem action='EditPaste' />
      <menuitem action='EditSomething' />
    </menu>
    <menu action='ChoicesMenu'>
      <menuitem action='ChoiceOne'/>
      <menuitem action='ChoiceTwo'/>
      <separator />
      <menuitem action='ChoiceThree'/>
      <separator />
      <menuitem action='DisabledAction'/>
      <menuitem action='InvisibleAction'/>
      <menuitem action='TooltipAction'/>
      <menuitem action='IconAction'/>
    </menu>
  </menubar>
  <toolbar name='ToolBar'>
    <toolitem action='FileNewStandard' />
    <toolitem action='FileQuit' />
  </toolbar>
  <popup name='PopupMenu'>
    <menuitem action='EditCopy' />
    <menuitem action='EditPaste' />
    <menuitem action='EditSomething' />
  </popup>
</ui>
"""


class MenuExampleWindow(Gtk.ApplicationWindow):

    def __init__(self, app):
        Gtk.Window.__init__(self, application=app, title="Menu Example")

        self.set_default_size(800, 600)
        self.scroll = s = Gtk.ScrolledWindow()
        s.set_hexpand(True), s.set_vexpand(True)
        s.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        s.set_min_content_height(450)
        self.label = la = Gtk.TextView()
        la.set_text = la.get_buffer().set_text
        s.add(la)

        action_group = Gtk.ActionGroup("my_actions")

        self.add_file_menu_actions(action_group)
        self.add_edit_menu_actions(action_group)
        self.add_choices_menu_actions(action_group)

        uimanager = self.create_ui_manager()
        uimanager.insert_action_group(action_group)

        menubar = uimanager.get_widget("/MenuBar")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.pack_start(menubar, False, False, 0)

        toolbar = uimanager.get_widget("/ToolBar")
        box.pack_start(toolbar, False, False, 0)

        eventbox = Gtk.EventBox()
        eventbox.connect("button-press-event", self.on_button_press_event)
        box.pack_start(s, False, False, 0)
        box.pack_start(eventbox, True, True, 0)

        label = Gtk.Label("Right-click to see the popup menu.")
        eventbox.add(label)

        self.popup = uimanager.get_widget("/PopupMenu")

        self.add(box)
        i = Gtk.Image.new_from_stock(Gtk.STOCK_OK, Gtk.IconSize.MENU)
        # Currently the menu items image is not exported over DBus, so probably
        # best to stick with using dbusmenu
        uimanager.get_widget('/MenuBar/ChoicesMenu/IconAction')
        uimanager.get_widget('/MenuBar/ChoicesMenu/IconAction').set_image(i)
        uimanager.get_widget('/MenuBar/ChoicesMenu/IconAction').set_always_show_image(True)

    def add_file_menu_actions(self, action_group):
        action_filemenu = Gtk.Action("FileMenu", "File", None, None)
        action_group.add_action(action_filemenu)

        action_filenewmenu = Gtk.Action("FileNew", None, None, Gtk.STOCK_NEW)
        action_group.add_action(action_filenewmenu)

        action_new = Gtk.Action("FileNewStandard", "_New",
            "Create a new file", Gtk.STOCK_NEW)
        action_new.connect("activate", self.on_menu_file_new_generic)
        action_group.add_action_with_accel(action_new, '<Ctrl>N')

        action_group.add_actions([
            ("FileNewFoo", None, "New Foo", None, "Create new foo",
             self.on_menu_file_new_generic),
            ("FileNewGoo", None, "_New Goo", None, "Create new goo",
             self.on_menu_file_new_generic),
        ])

        action_filequit = Gtk.Action("FileQuit", None, None, Gtk.STOCK_QUIT)
        action_filequit.connect("activate", self.on_menu_file_quit)
        action_group.add_action_with_accel(action_filequit, '<Ctrl>Q')

    def add_edit_menu_actions(self, action_group):
        action_group.add_actions([
            ("EditMenu", None, "Edit"),
            ("EditCopy", Gtk.STOCK_COPY, None, None, None,
             self.on_menu_others),
            ("EditPaste", Gtk.STOCK_PASTE, None, None, None,
             self.on_menu_others),
            ("EditSomething", None, "Something", "<control><alt>S", None,
             self.on_menu_others)
        ])

    def add_choices_menu_actions(self, action_group):
        action_group.add_action(Gtk.Action("ChoicesMenu", "Choices", None,
            None))

        action_group.add_radio_actions([
            ("ChoiceOne", None, "One", None, None, 1),
            ("ChoiceTwo", None, "Two", None, None, 2)
        ], 1, self.on_menu_choices_changed)

        three = Gtk.ToggleAction("ChoiceThree", "Three", None, None)
        three.connect("toggled", self.on_menu_choices_toggled)
        action_group.add_action(three)
        ad = Gtk.Action('DisabledAction', 'Disabled Action', None, None)
        ad.set_sensitive(False)
        action_group.add_action(ad)
        ia = Gtk.Action('InvisibleAction', 'Invisible Action', None, None)
        ia.set_visible(False)
        action_group.add_action(ia)
        ta = Gtk.Action('TooltipAction', 'Tooltip Action', 'A tooltip', None)
        action_group.add_action(ta)
        action_group.add_action(Gtk.Action('IconAction', 'Icon Action', None, None))

    def create_ui_manager(self):
        uimanager = Gtk.UIManager()

        # Throws exception if something went wrong
        uimanager.add_ui_from_string(UI_INFO)

        # Add the accelerator group to the toplevel window
        accelgroup = uimanager.get_accel_group()
        self.add_accel_group(accelgroup)
        return uimanager

    def on_menu_file_new_generic(self, widget):
        print("A File|New menu item was selected.")

    def on_menu_file_quit(self, widget):
        app.quit()

    def on_menu_others(self, widget):
        print("Menu item " + widget.get_name() + " was selected")

    def on_menu_choices_changed(self, widget, current):
        print(current.get_name() + " was selected.")

    def on_menu_choices_toggled(self, widget):
        if widget.get_active():
            print(widget.get_name() + " activated")
        else:
            print(widget.get_name() + " deactivated")

    def on_button_press_event(self, widget, event):
        # Check if right mouse button was preseed
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            self.popup.popup(None, None, None, None, event.button, event.time)
            return True  # event has been handled


def convert(v):
    if isinstance(v, (unicode_type, bytes)):
        return unicode_type(v)
    if isinstance(v, dbus.Struct):
        return tuple(convert(val) for val in v)
    if isinstance(v, list):
        return [convert(val) for val in v]
    if isinstance(v, dict):
        return {convert(k):convert(val) for k, val in iteritems(v)}
    if isinstance(v, dbus.Boolean):
        return bool(v)
    if isinstance(v, (dbus.UInt32, dbus.UInt16)):
        return int(v)
    return v


class MyApplication(Gtk.Application):

    def do_activate(self):
        win = self.window = MenuExampleWindow(self)
        win.show_all()
        self.get_xprop_data()
        Thread(target=self.print_dbus_data).start()

    def get_xprop_data(self):
        win_id = self.window.get_window().get_xid()
        try:
            import xcb, xcb.xproto
        except ImportError:
            raise SystemExit('You must install the python-xpyb XCB bindings')
        conn = xcb.Connection()
        atoms = conn.core.ListProperties(win_id).reply().atoms
        atom_names = {atom:conn.core.GetAtomNameUnchecked(atom) for atom in atoms}
        atom_names = {k:bytes(a.reply().name.buf()) for k, a in iteritems(atom_names)}
        property_names = {name:atom for atom, name in iteritems(atom_names) if
            name.startswith('_GTK') or name.startswith('_UNITY') or name.startswith('_GNOME')}
        replies = {name:conn.core.GetProperty(False, win_id, atom, xcb.xproto.GetPropertyType.Any, 0, 2 ** 32 - 1) for name, atom in iteritems(property_names)}

        type_atom_cache = {}

        def get_property_value(property_reply):
            if property_reply.format == 8:
                is_list_of_strings = 0 in property_reply.value[:-1]
                ans = bytes(property_reply.value.buf())
                if property_reply.type not in type_atom_cache:
                    type_atom_cache[property_reply.type] = bytes(conn.core.GetAtomNameUnchecked(property_reply.type).reply().name.buf())
                if type_atom_cache[property_reply.type] == b'UTF8_STRING':
                    ans = ans.decode('utf-8')
                if is_list_of_strings:
                    ans = ans.split('\0')
                return ans
            elif property_reply.format in (16, 32):
                return list(struct.unpack(b'I' * property_reply.value_len,
                                        property_reply.value.buf()))

            return None
        props = {name:get_property_value(r.reply()) for name, r in iteritems(replies)}
        ans = ['\nX Window properties:']
        for name in sorted(props):
            ans.append('%s: %r' % (name, props[name]))
        self.xprop_data = '\n'.join(ans)
        self.object_path = props['_UNITY_OBJECT_PATH']
        self.bus_name = props['_GTK_UNIQUE_BUS_NAME']

    def print(self, *args):
        self.data.append(' '.join(map(str, args)))

    def print_menu_start(self, bus, group=0, seen=None):
        groups = set()
        seen = seen or set()
        seen.add(group)
        print = self.print
        print('\nMenu description (Group %d)' % group)
        for item in bus.call_blocking(self.bus_name, self.object_path, 'org.gtk.Menus', 'Start', 'au', ([group],)):
            print('Subscription group:', item[0])
            print('Menu number:', item[1])
            for menu_item in item[2]:
                menu_item = {unicode_type(k):convert(v) for k, v in iteritems(menu_item)}
                if ':submenu' in menu_item:
                    groups.add(menu_item[':submenu'][0])
                if ':section' in menu_item:
                    groups.add(menu_item[':section'][0])
                print(pformat(menu_item))
        for other_group in sorted(groups - seen):
            self.print_menu_start(bus, other_group, seen)

    def print_dbus_data(self):
        bus = dbus.SessionBus()
        time.sleep(0.5)
        self.data = []
        self.get_actions_description(bus)
        self.print_menu_start(bus)
        self.data.append(self.xprop_data)
        self.window.label.set_text('\n'.join(self.data))

    def get_actions_description(self, bus):
        print = self.print
        print('\nActions description')
        self.actions_desc = d = {}
        adata = bus.call_blocking(self.bus_name, self.object_path, 'org.gtk.Actions', 'DescribeAll', '', ())
        for name in sorted(adata):
            data = adata[name]
            d[name] = {'enabled':convert(data[0]), 'param type': convert(data[1]), 'state':convert(data[2])}
            print('Name:', name)
            print(pformat(d[name]))

    def do_startup(self):
        Gtk.Application.do_startup(self)


app = MyApplication(application_id='com.calibre-ebook.test-gtk')
signal.signal(signal.SIGINT, signal.SIG_DFL)
sys.exit(app.run(sys.argv))
