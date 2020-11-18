/*
 * cocoa_wrapper.c
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include <Python.h>

extern int cocoa_transient_scroller(void);
extern double cocoa_cursor_blink_time(void);
extern void cocoa_send_notification(const char *identitifer, const char *title, const char *subtitle, const char *informativeText, const char* path_to_image);
extern const char* cocoa_send2trash(const char *utf8_path);
extern void activate_cocoa_multithreading(void);
extern void disable_window_tabbing(void);
extern void remove_cocoa_menu_items(void);
extern int nsss_init_module(PyObject*);

static PyObject *notification_activated_callback = NULL;

static PyObject*
transient_scroller(PyObject *self) {
    (void)self;
    return PyBool_FromLong(cocoa_transient_scroller());
}

static PyObject*
cursor_blink_time(PyObject *self) {
    (void)self;
    double ans = cocoa_cursor_blink_time();
    return PyFloat_FromDouble(ans);
}

void
macos_notification_callback(const char* user_id) {
	if (notification_activated_callback) {
		PyObject *ret = PyObject_CallFunction(notification_activated_callback, "z", user_id);
		if (ret == NULL) PyErr_Print();
		else Py_DECREF(ret);
	}
}

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

static PyObject*
send2trash(PyObject *self, PyObject *args) {
	(void)self;
	char *path = NULL;
    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;
	const char *err = cocoa_send2trash(path);
	if (err) {
		PyErr_SetString(PyExc_OSError, err);
		free((void*)err);
		return NULL;
	}
	Py_RETURN_NONE;
}

static PyObject*
enable_cocoa_multithreading(PyObject *self, PyObject *args) {
	activate_cocoa_multithreading();
	Py_RETURN_NONE;
}

static PyObject*
disable_cocoa_ui_elements(PyObject *self, PyObject *args) {
	PyObject *tabbing = Py_True, *menu_items = Py_True;
	if (!PyArg_ParseTuple(args, "|OO", &tabbing, &menu_items)) return NULL;
	if (PyObject_IsTrue(tabbing)) disable_window_tabbing();
	if (PyObject_IsTrue(menu_items)) remove_cocoa_menu_items();
	Py_RETURN_NONE;
}



static PyMethodDef module_methods[] = {
    {"transient_scroller", (PyCFunction)transient_scroller, METH_NOARGS, ""},
    {"cursor_blink_time", (PyCFunction)cursor_blink_time, METH_NOARGS, ""},
    {"enable_cocoa_multithreading", (PyCFunction)enable_cocoa_multithreading, METH_NOARGS, ""},
    {"set_notification_activated_callback", (PyCFunction)set_notification_activated_callback, METH_O, ""},
    {"send_notification", (PyCFunction)send_notification, METH_VARARGS, ""},
    {"disable_cocoa_ui_elements", (PyCFunction)disable_cocoa_ui_elements, METH_VARARGS, ""},
    {"send2trash", (PyCFunction)send2trash, METH_VARARGS, ""},
    {NULL, NULL, 0, NULL}        /* Sentinel */
};

static int
exec_module(PyObject *module) {
	if (nsss_init_module(module) == -1) return -1;
	return 0;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {
    .m_base     = PyModuleDef_HEAD_INIT,
    .m_name     = "cocoa",
    .m_methods  = module_methods,
    .m_slots    = slots,
};

CALIBRE_MODINIT_FUNC PyInit_cocoa(void) { return PyModuleDef_Init(&module_def); }
