/*
 * wintoast.cpp
 * Copyright (C) 2024 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "common.h"

#include "wintoastlib.h"
using namespace WinToastLib;

static const char*
err_as_atring(WinToast::WinToastError e) {
    switch(e) {
        case WinToast::WinToastError::NoError: return  "No error";
        case WinToast::WinToastError::NotInitialized: return  "The library has not been initialized";
        case WinToast::WinToastError::SystemNotSupported: return  "The OS does not support WinToast";
        case WinToast::WinToastError::ShellLinkNotCreated: return  "The library was not able to create a Shell Link for the app";
        case WinToast::WinToastError::InvalidAppUserModelID: return  "The AUMI is not a valid one";
        case WinToast::WinToastError::InvalidParameters: return  "Invalid parameters, please double-check the AUMI or App Name";
        case WinToast::WinToastError::InvalidHandler: return  "Invalid handler";
        case WinToast::WinToastError::NotDisplayed: return  "The toast was created correctly but WinToast was not able to display the toast";
        case WinToast::WinToastError::UnknownError: break;
    }
    return "UnknownError";

}

static PyObject*
set_error(const char *fmt, WinToast::WinToastError error, PyObject *a, PyObject *b) {
    PyErr_Format(PyExc_OSError, fmt, err_as_atring(error), a, b);
    return NULL;
}

class WinToastHandler : public WinToastLib::IWinToastHandler {
public:
    WinToastHandler() {}
    // Public interfaces
    void toastActivated() const override {}
    void toastActivated(int actionIndex) const override {
        wchar_t buf[250];
        swprintf_s(buf, L"Button clicked: %d", actionIndex);
    }
    void toastDismissed(WinToastDismissalReason state) const override {}
    void toastFailed() const override {}
};

static PyObject*
initialize_toast(PyObject *self, PyObject *args) {
    wchar_raii appname, app_user_model_id;
    int sp = WinToast::SHORTCUT_POLICY_IGNORE;
    if (!PyArg_ParseTuple(args, "O&O&|i", py_to_wchar_no_none, &appname, py_to_wchar_no_none, &app_user_model_id, &sp)) return NULL;
    WinToast::WinToastError error = WinToast::WinToastError::NoError;
    WinToast::instance()->setAppName(appname.ptr());
    WinToast::instance()->setAppUserModelId(app_user_model_id.ptr());
    WinToast::instance()->setShortcutPolicy((WinToast::ShortcutPolicy)sp);
    if (!WinToast::instance()->initialize(&error)) {
        return set_error("Failed to initialize WinToast with error: %s using appname: %S and app model id: %S", error, PyTuple_GET_ITEM(args, 0), PyTuple_GET_ITEM(args, 1));
    }
    Py_RETURN_NONE;
}

static PyObject*
notify(PyObject *self, PyObject *args) {
    wchar_raii title, message, icon_path;
    if (!PyArg_ParseTuple(args, "O&O&O&", py_to_wchar_no_none, &title, py_to_wchar_no_none, &message, py_to_wchar_no_none, &icon_path)) return NULL;
	scoped_com_initializer com;
	if (!com.succeeded()) { PyErr_SetString(PyExc_OSError, "Failed to initialize COM"); return NULL; }
    WinToastTemplate templ = WinToastTemplate(WinToastTemplate::ImageAndText02);
    templ.setImagePath(icon_path.ptr(), WinToastTemplate::CropHint::Square);
    templ.setFirstLine(title.ptr());
    templ.setSecondLine(message.ptr());
    templ.setDuration(WinToastTemplate::Duration::Short);
    WinToast::WinToastError error = WinToast::WinToastError::NoError;
    INT64 id = WinToast::instance()->showToast(templ, new WinToastHandler(), &error);
    if (id == -1 || error != WinToast::WinToastError::NoError) {
        return set_error("Failed to show notification with error: %s using title: %S and message: %S", error, PyTuple_GET_ITEM(args, 0), PyTuple_GET_ITEM(args, 1));
    }
    unsigned long long pid = id;
    return PyLong_FromUnsignedLongLong(pid);
}

static int
exec_module(PyObject *m) {
    if (PyModule_AddIntConstant(m, "SHORTCUT_POLICY_IGNORE", WinToast::SHORTCUT_POLICY_IGNORE) != 0) return -1;
    if (PyModule_AddIntConstant(m, "SHORTCUT_POLICY_REQUIRE_CREATE", WinToast::SHORTCUT_POLICY_REQUIRE_CREATE) != 0) return -1;
    if (PyModule_AddIntConstant(m, "SHORTCUT_POLICY_REQUIRE_NO_CREATE", WinToast::SHORTCUT_POLICY_REQUIRE_NO_CREATE) != 0) return -1;
    return 0;
}

PyMODINIT_FUNC PyInit_wintoast(void) {
#define M(name, args) { #name, name, args, ""}
    static PyModuleDef_Slot slots[] = { {Py_mod_exec, (void*)exec_module}, {0, NULL} };
    static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};
    static PyMethodDef methods[] = {
        M(initialize_toast, METH_VARARGS),
        M(notify, METH_VARARGS),
        {0},
    };
    module_def.m_name     = "wintoast";
    module_def.m_slots    = slots;
    module_def.m_methods  = methods;
	return PyModuleDef_Init(&module_def);
}
