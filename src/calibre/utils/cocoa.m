/*
 * cocoa.m
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define PY_SSIZE_T_CLEAN
#import <AppKit/AppKit.h>
#import <AppKit/NSWindow.h>
#import <Availability.h>
#import <IOKit/pwr_mgt/IOPMLib.h>

#include <string.h>
#include <Python.h>

extern int nsss_init_module(PyObject*);

static void
disable_window_tabbing(void) {
	if ([NSWindow respondsToSelector:@selector(allowsAutomaticWindowTabbing)])
        NSWindow.allowsAutomaticWindowTabbing = NO;
}

static void
remove_cocoa_menu_items(void) {
	// Remove (disable) the "Start Dictation..." and "Emoji & Symbols" menu
	// items from the "Edit" menu
	[[NSUserDefaults standardUserDefaults] setBool:YES forKey:@"NSDisabledDictationMenuItem"];
	[[NSUserDefaults standardUserDefaults] setBool:YES forKey:@"NSDisabledCharacterPaletteMenuItem"];

	// Remove (don't have) the "Enter Full Screen" menu item from the "View" menu
	[[NSUserDefaults standardUserDefaults] setBool:NO forKey:@"NSFullScreenMenuItemEverywhere"];
}

static PyObject*
disable_cocoa_ui_elements(PyObject *self, PyObject *args) {
	PyObject *tabbing = Py_True, *menu_items = Py_True;
	if (!PyArg_ParseTuple(args, "|OO", &tabbing, &menu_items)) return NULL;
	if (PyObject_IsTrue(tabbing)) disable_window_tabbing();
	if (PyObject_IsTrue(menu_items)) remove_cocoa_menu_items();
	Py_RETURN_NONE;
}


static PyObject*
enable_cocoa_multithreading(PyObject *self, PyObject *args) {
	if (![NSThread isMultiThreaded]) [[NSThread new] start];
	Py_RETURN_NONE;
}


static PyObject*
send2trash(PyObject *self, PyObject *args) {
	(void)self;
	char *path = NULL;
    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;
	@autoreleasepool {
		NSError* ns_error = nil;
		if (![[NSFileManager defaultManager] trashItemAtURL:[NSURL fileURLWithPath:@(path)] resultingItemURL:nil error:&ns_error]) {
			PyErr_SetString(PyExc_OSError, [[ns_error localizedDescription] UTF8String]);
		}
	}
	if (PyErr_Occurred()) return NULL;
	Py_RETURN_NONE;
}

// Notifications {{{
static PyObject *notification_activated_callback = NULL;

static void
macos_notification_callback(const char* user_id) {
	if (notification_activated_callback) {
		PyObject *ret = PyObject_CallFunction(notification_activated_callback, "z", user_id);
		if (ret == NULL) PyErr_Print();
		else Py_DECREF(ret);
	}
}


@interface NotificationDelegate : NSObject <NSUserNotificationCenterDelegate>
@end


static void
cocoa_send_notification(const char *identifier, const char *title, const char *subtitle, const char *informativeText, const char* path_to_image) {
	@autoreleasepool {
    NSUserNotificationCenter *center = [NSUserNotificationCenter defaultUserNotificationCenter];
    if (!center) {return;}
    if (!center.delegate) center.delegate = [[NotificationDelegate alloc] init];
    NSUserNotification *n = [NSUserNotification new];
    NSImage *img = nil;
    if (path_to_image) {
		img = [[NSImage alloc] initWithContentsOfURL:[NSURL fileURLWithPath:@(path_to_image)]];
        if (img) {
            [n setValue:img forKey:@"_identityImage"];
            [n setValue:@(false) forKey:@"_identityImageHasBorder"];
        }
		[img release];
    }
#define SET(x) { \
    if (x) { \
        n.x = @(x); \
    }}
    SET(title); SET(subtitle); SET(informativeText);
#undef SET
    if (identifier) {
        n.userInfo = @{@"user_id": @(identifier)};
    }
    [center deliverNotification:n];
	}
}

@implementation NotificationDelegate
    - (void)userNotificationCenter:(NSUserNotificationCenter *)center
            didDeliverNotification:(NSUserNotification *)notification {
        (void)(center); (void)(notification);
    }

    - (BOOL) userNotificationCenter:(NSUserNotificationCenter *)center
            shouldPresentNotification:(NSUserNotification *)notification {
        (void)(center); (void)(notification);
        return YES;
    }

    - (void) userNotificationCenter:(NSUserNotificationCenter *)center
            didActivateNotification:(NSUserNotification *)notification {
        (void)(center);
			macos_notification_callback(notification.userInfo[@"user_id"] ? [notification.userInfo[@"user_id"] UTF8String] : NULL);
    }
@end

static PyObject*
set_notification_activated_callback(PyObject *self, PyObject *callback) {
    (void)self;
    if (notification_activated_callback) Py_DECREF(notification_activated_callback);
    notification_activated_callback = callback;
    Py_INCREF(callback);
    Py_RETURN_NONE;

}

static PyObject*
send_notification(PyObject *self, PyObject *args) {
	(void)self;
    char *identifier = NULL, *title = NULL, *subtitle = NULL, *informativeText = NULL, *path_to_image = NULL;
    if (!PyArg_ParseTuple(args, "zsz|zz", &identifier, &title, &informativeText, &path_to_image, &subtitle)) return NULL;
	cocoa_send_notification(identifier, title, subtitle, informativeText, path_to_image);

    Py_RETURN_NONE;
}
// }}}


static PyObject*
cursor_blink_time(PyObject *self) {
    (void)self;
    NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
    double on_period_ms = [defaults doubleForKey:@"NSTextInsertionPointBlinkPeriodOn"];
    double off_period_ms = [defaults doubleForKey:@"NSTextInsertionPointBlinkPeriodOff"];
    double period_ms = [defaults doubleForKey:@"NSTextInsertionPointBlinkPeriod"];
    double max_value = 60 * 1000.0, ans = -1.0;
    if (on_period_ms || off_period_ms) {
        ans = on_period_ms + off_period_ms;
    } else if (period_ms) {
        ans = period_ms;
    }
	if (ans > max_value) ans = 0.0;
    return PyFloat_FromDouble(ans);
}

static PyObject*
transient_scroller(PyObject *self) {
    (void)self;
    return PyBool_FromLong([NSScroller preferredScrollerStyle] == NSScrollerStyleOverlay);
}

static PyObject*
locale_names(PyObject *self, PyObject *args) {
	PyObject *ans = PyTuple_New(PyTuple_GET_SIZE(args));
	if (!ans) return NULL;
	NSLocale *locale = [NSLocale autoupdatingCurrentLocale];

	for (Py_ssize_t i = 0; i < PyTuple_GET_SIZE(ans); i++) {
		PyObject *x = PyTuple_GET_ITEM(args, i);
		if (!PyUnicode_Check(x)) { PyErr_SetString(PyExc_TypeError, "language codes must be unicode"); Py_CLEAR(ans); return NULL; }
		if (PyUnicode_READY(x) != 0) { Py_CLEAR(ans); return NULL; }
		const char *code = PyUnicode_AsUTF8(x);
		if (code == NULL) { Py_CLEAR(ans); return NULL; }
		NSString *display_name = [locale displayNameForKey:NSLocaleIdentifier value:@(code)];
		if (display_name) {
			PyObject *p = PyUnicode_FromString([display_name UTF8String]);
			if (!p) { Py_CLEAR(ans); return NULL; }
			PyTuple_SET_ITEM(ans, i, p);
		} else {
			Py_INCREF(x);
			PyTuple_SET_ITEM(ans, i, x);
		}
	}
	return ans;
}

static PyObject*
create_io_pm_assertion(PyObject *self, PyObject *args) {
	char *type, *reason;
	int on = 1;
	if (!PyArg_ParseTuple(args, "ss|p", &type, &reason, &on)) return NULL;
	IOPMAssertionID assertionID;
	IOReturn rc = IOPMAssertionCreateWithName(@(type), on ? kIOPMAssertionLevelOn : kIOPMAssertionLevelOff, @(reason), &assertionID);
	if (rc == kIOReturnSuccess) {
		unsigned long long aid = assertionID;
		return PyLong_FromUnsignedLongLong(aid);
	}
	PyErr_SetString(PyExc_OSError, mach_error_string(rc));
	return NULL;
}

static PyObject*
release_io_pm_assertion(PyObject *self, PyObject *args) {
	unsigned long long aid;
	if (!PyArg_ParseTuple(args, "K", &aid)) return NULL;
	IOReturn rc = IOPMAssertionRelease(aid);
	if (rc == kIOReturnSuccess) { Py_RETURN_NONE; }
	PyErr_SetString(PyExc_OSError, mach_error_string(rc));
	return NULL;
}

static PyObject*
set_requires_aqua_system_appearance(PyObject *self, PyObject *yes) {
    NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
    if (PyObject_IsTrue(yes)) {
        [defaults setBool:YES forKey:@"NSRequiresAquaSystemAppearance"];
    } else {
        if (yes == Py_None) [defaults removeObjectForKey:@"NSRequiresAquaSystemAppearance"];
        else [defaults setBool:NO forKey:@"NSRequiresAquaSystemAppearance"];
    }
    Py_RETURN_NONE;
}

static PyObject*
get_requires_aqua_system_appearance(PyObject *self, PyObject *unused) {
    NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
    if ([defaults objectForKey:@"NSRequiresAquaSystemAppearance"]) {
        if ([defaults boolForKey:@"NSRequiresAquaSystemAppearance"]) { Py_RETURN_TRUE; }
        Py_RETURN_FALSE;
    }
    Py_RETURN_NONE;
}

static PyObject*
set_appearance(PyObject *self, PyObject *args) {
    const char *val;
    if (!PyArg_ParseTuple(args, "s", &val)) return NULL;
    [NSApplication sharedApplication];
    if (strcmp(val, "system") == 0) {
        NSApp.appearance = nil;
    } else if (strcmp(val, "light") == 0) {
        NSApp.appearance = [NSAppearance appearanceNamed:NSAppearanceNameAqua];
    }  else if (strcmp(val, "dark") == 0) {
        NSApp.appearance = [NSAppearance appearanceNamed:NSAppearanceNameDarkAqua];
    } else {
        PyErr_Format(PyExc_KeyError, "Unknown appearance type: %s", val);
        return NULL;
    }
    Py_RETURN_NONE;

}

static PyObject*
get_appearance(PyObject *self, PyObject *args) {
    int effective = 0;
    if (!PyArg_ParseTuple(args, "|p", &effective)) return NULL;
    [NSApplication sharedApplication];
    if (effective) {
        if (!NSApp.effectiveAppearance) return PyUnicode_FromString("");
        return PyUnicode_FromString([NSApp.effectiveAppearance.name UTF8String]);
    }
    if (!NSApp.appearance) return PyUnicode_FromString("");
    return PyUnicode_FromString([NSApp.appearance.name UTF8String]);
}


static PyMethodDef module_methods[] = {
    {"get_appearance", (PyCFunction)get_appearance, METH_VARARGS, ""},
    {"set_appearance", (PyCFunction)set_appearance, METH_VARARGS, ""},
    {"set_requires_aqua_system_appearance", (PyCFunction)set_requires_aqua_system_appearance, METH_O, ""},
    {"get_requires_aqua_system_appearance", (PyCFunction)get_requires_aqua_system_appearance, METH_NOARGS, ""},
    {"transient_scroller", (PyCFunction)transient_scroller, METH_NOARGS, ""},
    {"cursor_blink_time", (PyCFunction)cursor_blink_time, METH_NOARGS, ""},
    {"enable_cocoa_multithreading", (PyCFunction)enable_cocoa_multithreading, METH_NOARGS, ""},
    {"set_notification_activated_callback", (PyCFunction)set_notification_activated_callback, METH_O, ""},
    {"send_notification", (PyCFunction)send_notification, METH_VARARGS, ""},
    {"disable_cocoa_ui_elements", (PyCFunction)disable_cocoa_ui_elements, METH_VARARGS, ""},
    {"send2trash", (PyCFunction)send2trash, METH_VARARGS, ""},
    {"locale_names", (PyCFunction)locale_names, METH_VARARGS, ""},
    {"create_io_pm_assertion", (PyCFunction)create_io_pm_assertion, METH_VARARGS, ""},
    {"release_io_pm_assertion", (PyCFunction)release_io_pm_assertion, METH_VARARGS, ""},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static int
exec_module(PyObject *module) {
	if (nsss_init_module(module) == -1) return -1;
#define A(which) if (PyModule_AddStringConstant(module, #which, [(__bridge NSString *)which UTF8String]) == -1) return -1;
	A(kIOPMAssertionTypePreventUserIdleSystemSleep);
	A(kIOPMAssertionTypePreventUserIdleDisplaySleep);
	A(kIOPMAssertionTypePreventSystemSleep);
	A(kIOPMAssertionTypeNoIdleSleep);
	A(kIOPMAssertionTypeNoDisplaySleep);
#undef A
	return 0;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {
    .m_base     = PyModuleDef_HEAD_INIT,
    .m_name     = "cocoa",
    .m_methods  = module_methods,
    .m_slots    = slots,
};

CALIBRE_MODINIT_FUNC PyInit_cocoa(void) {
	return PyModuleDef_Init(&module_def);
}
