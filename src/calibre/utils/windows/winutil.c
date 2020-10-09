/*
:mod:`winutil` -- Interface to Windows
============================================

.. module:: winutil
    :platform: Windows
    :synopsis: Various methods to interface with the operating system

.. moduleauthor:: Kovid Goyal <kovid@kovidgoyal.net> Copyright 2008

This module contains utility functions to interface with the windows operating
system. It should be compiled with the same version of VisualStudio used to
compile python. It hasn't been tested with MinGW. We try to use unicode
wherever possible in this module.

.. function:: special_folder_path(csidl_id) -> path
    Get paths to common system folders.
    See windows documentation of SHGetFolderPath.
    The paths are returned as unicode objects. `csidl_id` should be one
    of the symbolic constants defined in this module. You can also `OR`
    a symbolic constant with :data:`CSIDL_FLAG_CREATE` to force the operating
    system to create a folder if it does not exist. For example::

        >>> from winutil import *
        >>> special_folder_path(CSIDL_APPDATA)
        u'C:\\Documents and Settings\\Kovid Goyal\\Application Data'
        >>>  special_folder_path(CSIDL_PERSONAL)
        u'C:\\Documents and Settings\\Kovid Goyal\\My Documents'

.. function:: internet_connected() -> Return True if there is an active
   internet connection.

*/


#define UNICODE
#include <Windows.h>
#include <Wininet.h>
#include <LMcons.h>
#include <locale.h>
#include <Python.h>
#include <structseq.h>
#include <shlobj.h>
#include <stdio.h>
#include <setupapi.h>
#include <devguid.h>
#include <cfgmgr32.h>
#include <stdarg.h>
#include <time.h>

#define BUFSIZE    512
#define MAX_DRIVES 26

static PyObject *
winutil_folder_path(PyObject *self, PyObject *args) {
    int res; DWORD dwFlags;
    PyObject *ans = NULL;
    TCHAR wbuf[MAX_PATH]; CHAR buf[4*MAX_PATH];
    memset(wbuf, 0, sizeof(TCHAR)*MAX_PATH); memset(buf, 0, sizeof(CHAR)*MAX_PATH);

    if (!PyArg_ParseTuple(args, "l", &dwFlags)) return NULL;

    res = SHGetFolderPath(NULL, dwFlags, NULL, 0, wbuf);
    if (res != S_OK) {
        if (res == E_FAIL) PyErr_SetString(PyExc_ValueError, "Folder does not exist.");
        PyErr_SetString(PyExc_ValueError, "Folder not valid");
        return NULL;
    }
    res = WideCharToMultiByte(CP_UTF8, 0, wbuf, -1, buf, 4*MAX_PATH, NULL, NULL);
    ans = PyUnicode_DecodeUTF8(buf, res-1, "strict");
    return ans;
}

static PyObject *
winutil_internet_connected(PyObject *self, PyObject *args) {
    DWORD flags;
    BOOL ans = InternetGetConnectedState(&flags, 0);
    if (ans) Py_RETURN_TRUE;
    Py_RETURN_FALSE;
}

static PyObject *
winutil_prepare_for_restart(PyObject *self, PyObject *args) {
    FILE *f1 = NULL, *f2 = NULL;
    if (stdout != NULL) fclose(stdout);
    if (stderr != NULL) fclose(stderr);
    _wfreopen_s(&f1, L"NUL", L"a+t", stdout);
    _wfreopen_s(&f2, L"NUL", L"a+t", stderr);
    Py_RETURN_NONE;
}

static PyObject *
winutil_get_max_stdio(PyObject *self, PyObject *args) {
    return Py_BuildValue("i", _getmaxstdio());
}

static PyObject *
winutil_set_max_stdio(PyObject *self, PyObject *args) {
    int num = 0;
    if (!PyArg_ParseTuple(args, "i", &num)) return NULL;
    if (_setmaxstdio(num) == -1) return PyErr_SetFromErrno(PyExc_ValueError);
    Py_RETURN_NONE;
}

static PyObject *
winutil_username(PyObject *self) {
    wchar_t buf[UNLEN + 1] = {0};
    DWORD sz = sizeof(buf)/sizeof(buf[0]);
    if (!GetUserName(buf, &sz)) {
        PyErr_SetFromWindowsErr(0);
        return NULL;
    }
    return PyUnicode_FromWideChar(buf, wcslen(buf));
}

static PyObject *
winutil_temp_path(PyObject *self) {
    wchar_t buf[MAX_PATH + 1] = {0};
    DWORD sz = sizeof(buf)/sizeof(buf[0]);
    if (!GetTempPath(sz, buf)) {
        PyErr_SetFromWindowsErr(0);
        return NULL;
    }
    return PyUnicode_FromWideChar(buf, wcslen(buf));
}


static PyObject *
winutil_locale_name(PyObject *self) {
    wchar_t buf[LOCALE_NAME_MAX_LENGTH + 1] = {0};
    if (!GetUserDefaultLocaleName(buf, sizeof(buf)/sizeof(buf[0]))) {
        PyErr_SetFromWindowsErr(0);
        return NULL;
    }
    return PyUnicode_FromWideChar(buf, wcslen(buf));
}


static PyObject *
winutil_localeconv(PyObject *self) {
    struct lconv *d = localeconv();
#define W(name) #name, d->_W_##name
    return Py_BuildValue(
        "{su su su su su su su su}",
        W(decimal_point), W(thousands_sep), W(int_curr_symbol), W(currency_symbol),
        W(mon_decimal_point), W(mon_thousands_sep), W(positive_sign), W(negative_sign)
    );
#undef W
}


static PyObject*
winutil_close_handle(PyObject *self, PyObject *pyhandle) {
    if (!PyLong_Check(pyhandle)) { PyErr_SetString(PyExc_TypeError, "handle must be an int"); return NULL; }
    if (!CloseHandle(PyLong_AsVoidPtr(pyhandle))) return PyErr_SetFromWindowsErr(0);
    Py_RETURN_NONE;
}

static const char winutil_doc[] = "Defines utility methods to interface with windows.";
extern PyObject *winutil_add_to_recent_docs(PyObject *self, PyObject *args);
extern PyObject *winutil_file_association(PyObject *self, PyObject *args);
extern PyObject *winutil_friendly_name(PyObject *self, PyObject *args);
extern PyObject *winutil_notify_associations_changed(PyObject *self, PyObject *args);
extern PyObject *winutil_move_to_trash(PyObject *self, PyObject *args);
extern PyObject *winutil_manage_shortcut(PyObject *self, PyObject *args);
extern PyObject *winutil_get_file_id(PyObject *self, PyObject *args);
extern PyObject *winutil_create_file(PyObject *self, PyObject *args);
extern PyObject *winutil_delete_file(PyObject *self, PyObject *args);
extern PyObject *winutil_create_hard_link(PyObject *self, PyObject *args);
extern PyObject *winutil_nlinks(PyObject *self, PyObject *args);
extern PyObject *winutil_set_file_attributes(PyObject *self, PyObject *args);
extern PyObject *winutil_get_file_size(PyObject *self, PyObject *args);
extern PyObject *winutil_set_file_pointer(PyObject *self, PyObject *args);
extern PyObject *winutil_read_file(PyObject *self, PyObject *args);
extern PyObject *winutil_get_disk_free_space(PyObject *self, PyObject *args);
extern PyObject *winutil_move_file(PyObject *self, PyObject *args);
extern PyObject *winutil_read_directory_changes(PyObject *self, PyObject *args);

static PyMethodDef winutil_methods[] = {
    {"special_folder_path", winutil_folder_path, METH_VARARGS,
    "special_folder_path(csidl_id) -> path\n\n"
            "Get paths to common system folders. "
            "See windows documentation of SHGetFolderPath. "
            "The paths are returned as unicode objects. csidl_id should be one "
            "of the symbolic constants defined in this module. You can also OR "
            "a symbolic constant with CSIDL_FLAG_CREATE to force the operating "
            "system to create a folder if it does not exist."},

    {"internet_connected", winutil_internet_connected, METH_VARARGS,
        "internet_connected()\n\nReturn True if there is an active internet connection"
    },

    {"prepare_for_restart", winutil_prepare_for_restart, METH_VARARGS,
        "prepare_for_restart()\n\nRedirect output streams so that the child process does not lock the temp files"
    },

    {"getmaxstdio", winutil_get_max_stdio, METH_VARARGS,
        "getmaxstdio()\n\nThe maximum number of open file handles."
    },

    {"setmaxstdio", winutil_set_max_stdio, METH_VARARGS,
        "setmaxstdio(num)\n\nSet the maximum number of open file handles."
    },

    {"username", (PyCFunction)winutil_username, METH_NOARGS,
        "username()\n\nGet the current username as a unicode string."
    },

    {"temp_path", (PyCFunction)winutil_temp_path, METH_NOARGS,
        "temp_path()\n\nGet the current temporary dir as a unicode string."
    },

    {"locale_name", (PyCFunction)winutil_locale_name, METH_NOARGS,
        "locale_name()\n\nGet the current locale name as a unicode string."
    },

    {"localeconv", (PyCFunction)winutil_localeconv, METH_NOARGS,
        "localeconv()\n\nGet the locale conventions as unicode strings."
    },

    {"move_file", (PyCFunction)winutil_move_file, METH_VARARGS,
        "move_file()\n\nRename the specified file."
    },

    {"add_to_recent_docs", (PyCFunction)winutil_add_to_recent_docs, METH_VARARGS,
        "add_to_recent_docs()\n\nAdd a path to the recent documents list"
    },

    {"file_association", (PyCFunction)winutil_file_association, METH_VARARGS,
        "file_association()\n\nGet the executable associated with the given file extension"
    },

    {"friendly_name", (PyCFunction)winutil_friendly_name, METH_VARARGS,
        "friendly_name()\n\nGet the friendly name for the specified prog_id/exe"
    },

    {"notify_associations_changed", (PyCFunction)winutil_notify_associations_changed, METH_VARARGS,
        "notify_associations_changed()\n\nNotify the OS that file associations have changed"
    },

    {"move_to_trash", (PyCFunction)winutil_move_to_trash, METH_VARARGS,
        "move_to_trash()\n\nMove the specified path to trash"
    },

    {"manage_shortcut", (PyCFunction)winutil_manage_shortcut, METH_VARARGS,
        "manage_shortcut()\n\nManage a shortcut"
    },

    {"get_file_id", (PyCFunction)winutil_get_file_id, METH_VARARGS,
        "get_file_id(path)\n\nGet the windows file id (volume_num, file_index_high, file_index_low)"
    },

    {"create_file", (PyCFunction)winutil_create_file, METH_VARARGS,
        "create_file(path, desired_access, share_mode, creation_disposition, flags_and_attributes)\n\nWrapper for CreateFile"
    },

    {"get_file_size", (PyCFunction)winutil_get_file_size, METH_O,
        "get_file_size(handle)\n\nWrapper for GetFileSizeEx"
    },

    {"set_file_pointer", (PyCFunction)winutil_set_file_pointer, METH_VARARGS,
        "set_file_pointer(handle, pos, method=FILE_BEGIN)\n\nWrapper for SetFilePointer"
    },

    {"read_file", (PyCFunction)winutil_read_file, METH_VARARGS,
        "set_file_pointer(handle, chunk_size=16KB)\n\nWrapper for ReadFile"
    },

    {"get_disk_free_space", (PyCFunction)winutil_get_disk_free_space, METH_VARARGS,
        "get_disk_free_space(path)\n\nWrapper for GetDiskFreeSpaceEx"
    },

    {"close_handle", (PyCFunction)winutil_close_handle, METH_O,
        "close_handle(handle)\n\nWrapper for CloseHandle"
    },

    {"delete_file", (PyCFunction)winutil_delete_file, METH_VARARGS,
        "delete_file(path)\n\nWrapper for DeleteFile"
    },

    {"create_hard_link", (PyCFunction)winutil_create_hard_link, METH_VARARGS,
        "create_hard_link(path, existing_path)\n\nWrapper for CreateHardLink"
    },

    {"nlinks", (PyCFunction)winutil_nlinks, METH_VARARGS,
        "nlinks(path)\n\nReturn the number of hardlinks"
    },

    {"set_file_attributes", (PyCFunction)winutil_set_file_attributes, METH_VARARGS,
        "set_file_attributes(path, attrs)\n\nWrapper for SetFileAttributes"
    },

    {"move_file", (PyCFunction)winutil_move_file, METH_VARARGS,
        "move_file(a, b, flags)\n\nWrapper for MoveFileEx"
    },

    {"read_directory_changes", (PyCFunction)winutil_read_directory_changes, METH_VARARGS,
        "read_directory_changes(handle, buffer, subtree, flags)\n\nWrapper for ReadDirectoryChangesW"
    },

    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef winutil_module = {
    /* m_base     */ PyModuleDef_HEAD_INIT,
    /* m_name     */ "winutil",
    /* m_doc      */ winutil_doc,
    /* m_size     */ -1,
    /* m_methods  */ winutil_methods,
    /* m_slots    */ 0,
    /* m_traverse */ 0,
    /* m_clear    */ 0,
    /* m_free     */ 0,
};
CALIBRE_MODINIT_FUNC PyInit_winutil(void) {
    PyObject *m = PyModule_Create(&winutil_module);

    if (m == NULL) {
        return NULL;
    }

    PyModule_AddIntConstant(m, "CSIDL_ADMINTOOLS", CSIDL_ADMINTOOLS);
    PyModule_AddIntConstant(m, "CSIDL_APPDATA", CSIDL_APPDATA);
    PyModule_AddIntConstant(m, "CSIDL_COMMON_ADMINTOOLS", CSIDL_COMMON_ADMINTOOLS);
    PyModule_AddIntConstant(m, "CSIDL_COMMON_APPDATA", CSIDL_COMMON_APPDATA);
    PyModule_AddIntConstant(m, "CSIDL_COMMON_DOCUMENTS", CSIDL_COMMON_DOCUMENTS);
    PyModule_AddIntConstant(m, "CSIDL_COOKIES", CSIDL_COOKIES);
    PyModule_AddIntConstant(m, "CSIDL_FLAG_CREATE", CSIDL_FLAG_CREATE);
    PyModule_AddIntConstant(m, "CSIDL_FLAG_DONT_VERIFY", CSIDL_FLAG_DONT_VERIFY);
    PyModule_AddIntConstant(m, "CSIDL_FONTS", CSIDL_FONTS);
    PyModule_AddIntConstant(m, "CSIDL_HISTORY", CSIDL_HISTORY);
    PyModule_AddIntConstant(m, "CSIDL_INTERNET_CACHE", CSIDL_INTERNET_CACHE);
    PyModule_AddIntConstant(m, "CSIDL_LOCAL_APPDATA", CSIDL_LOCAL_APPDATA);
    PyModule_AddIntConstant(m, "CSIDL_MYPICTURES", CSIDL_MYPICTURES);
    PyModule_AddIntConstant(m, "CSIDL_PERSONAL", CSIDL_PERSONAL);
    PyModule_AddIntConstant(m, "CSIDL_PROGRAM_FILES", CSIDL_PROGRAM_FILES);
    PyModule_AddIntConstant(m, "CSIDL_PROGRAM_FILES_COMMON", CSIDL_PROGRAM_FILES_COMMON);
    PyModule_AddIntConstant(m, "CSIDL_SYSTEM", CSIDL_SYSTEM);
    PyModule_AddIntConstant(m, "CSIDL_WINDOWS", CSIDL_WINDOWS);
    PyModule_AddIntConstant(m, "CSIDL_PROFILE", CSIDL_PROFILE);
    PyModule_AddIntConstant(m, "CSIDL_STARTUP", CSIDL_STARTUP);
    PyModule_AddIntConstant(m, "CSIDL_COMMON_STARTUP", CSIDL_COMMON_STARTUP);
    PyModule_AddIntConstant(m, "CREATE_NEW", CREATE_NEW);
    PyModule_AddIntConstant(m, "CREATE_ALWAYS", CREATE_ALWAYS);
    PyModule_AddIntConstant(m, "OPEN_EXISTING", OPEN_EXISTING);
    PyModule_AddIntConstant(m, "OPEN_ALWAYS", OPEN_ALWAYS);
    PyModule_AddIntConstant(m, "TRUNCATE_EXISTING", TRUNCATE_EXISTING);
    PyModule_AddIntConstant(m, "FILE_SHARE_READ", FILE_SHARE_READ);
    PyModule_AddIntConstant(m, "FILE_SHARE_WRITE", FILE_SHARE_WRITE);
    PyModule_AddIntConstant(m, "FILE_SHARE_DELETE", FILE_SHARE_DELETE);
    PyModule_AddIntConstant(m, "FILE_SHARE_VALID_FLAGS", FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE);
    PyModule_AddIntConstant(m, "FILE_ATTRIBUTE_READONLY", FILE_ATTRIBUTE_READONLY);
    PyModule_AddIntConstant(m, "FILE_ATTRIBUTE_NORMAL", FILE_ATTRIBUTE_NORMAL);
    PyModule_AddIntConstant(m, "FILE_ATTRIBUTE_TEMPORARY", FILE_ATTRIBUTE_TEMPORARY);
    PyModule_AddIntConstant(m, "FILE_FLAG_DELETE_ON_CLOSE", FILE_FLAG_DELETE_ON_CLOSE);
    PyModule_AddIntConstant(m, "FILE_FLAG_SEQUENTIAL_SCAN", FILE_FLAG_SEQUENTIAL_SCAN);
    PyModule_AddIntConstant(m, "FILE_FLAG_RANDOM_ACCESS", FILE_FLAG_RANDOM_ACCESS);
    PyModule_AddIntConstant(m, "GENERIC_READ", GENERIC_READ);
    PyModule_AddIntConstant(m, "GENERIC_WRITE", GENERIC_WRITE);
    PyModule_AddIntConstant(m, "DELETE", DELETE);
    PyModule_AddIntConstant(m, "FILE_BEGIN", FILE_BEGIN);
    PyModule_AddIntConstant(m, "FILE_CURRENT", FILE_CURRENT);
    PyModule_AddIntConstant(m, "FILE_END", FILE_END);
    PyModule_AddIntConstant(m, "MOVEFILE_COPY_ALLOWED", MOVEFILE_COPY_ALLOWED);
    PyModule_AddIntConstant(m, "MOVEFILE_CREATE_HARDLINK", MOVEFILE_CREATE_HARDLINK);
    PyModule_AddIntConstant(m, "MOVEFILE_DELAY_UNTIL_REBOOT", MOVEFILE_DELAY_UNTIL_REBOOT);
    PyModule_AddIntConstant(m, "MOVEFILE_FAIL_IF_NOT_TRACKABLE", MOVEFILE_FAIL_IF_NOT_TRACKABLE);
    PyModule_AddIntConstant(m, "MOVEFILE_REPLACE_EXISTING", MOVEFILE_REPLACE_EXISTING);
    PyModule_AddIntConstant(m, "MOVEFILE_WRITE_THROUGH", MOVEFILE_WRITE_THROUGH);
    PyModule_AddIntConstant(m, "FILE_NOTIFY_CHANGE_FILE_NAME", FILE_NOTIFY_CHANGE_FILE_NAME);
    PyModule_AddIntConstant(m, "FILE_NOTIFY_CHANGE_DIR_NAME", FILE_NOTIFY_CHANGE_DIR_NAME);
    PyModule_AddIntConstant(m, "FILE_NOTIFY_CHANGE_ATTRIBUTES", FILE_NOTIFY_CHANGE_ATTRIBUTES);
    PyModule_AddIntConstant(m, "FILE_NOTIFY_CHANGE_SIZE", FILE_NOTIFY_CHANGE_SIZE);
    PyModule_AddIntConstant(m, "FILE_NOTIFY_CHANGE_LAST_WRITE", FILE_NOTIFY_CHANGE_LAST_WRITE);
    PyModule_AddIntConstant(m, "FILE_NOTIFY_CHANGE_LAST_ACCESS", FILE_NOTIFY_CHANGE_LAST_ACCESS);
    PyModule_AddIntConstant(m, "FILE_NOTIFY_CHANGE_CREATION", FILE_NOTIFY_CHANGE_CREATION);
    PyModule_AddIntConstant(m, "FILE_NOTIFY_CHANGE_SECURITY", FILE_NOTIFY_CHANGE_SECURITY);
    PyModule_AddIntConstant(m, "FILE_ACTION_ADDED", FILE_ACTION_ADDED);
    PyModule_AddIntConstant(m, "FILE_ACTION_REMOVED", FILE_ACTION_REMOVED);
    PyModule_AddIntConstant(m, "FILE_ACTION_MODIFIED", FILE_ACTION_MODIFIED);
    PyModule_AddIntConstant(m, "FILE_ACTION_RENAMED_OLD_NAME", FILE_ACTION_RENAMED_OLD_NAME);
    PyModule_AddIntConstant(m, "FILE_ACTION_RENAMED_NEW_NAME", FILE_ACTION_RENAMED_NEW_NAME);
    PyModule_AddIntConstant(m, "FILE_LIST_DIRECTORY", FILE_LIST_DIRECTORY);
    PyModule_AddIntConstant(m, "FILE_FLAG_BACKUP_SEMANTICS", FILE_FLAG_BACKUP_SEMANTICS);

    return m;
}
