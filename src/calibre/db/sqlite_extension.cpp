/*
 * sqlite_extension.cpp
 * Copyright (C) 2021 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define UNICODE
#include <Python.h>
#include <stdlib.h>
#include <new>
#include <sqlite3ext.h>
SQLITE_EXTENSION_INIT1

typedef int (*token_callback_func)(void *, int, const char *, int, int, int);

class Tokenizer {
public:
    Tokenizer(const char **args, int nargs) {
    }

    int tokenize(void *callback_ctx, int flags, const char *text, int text_sz, token_callback_func callback) {
        return SQLITE_OK;
    }
};

// boilerplate {{{
static int
fts5_api_from_db(sqlite3 *db, fts5_api **ppApi) {
    sqlite3_stmt *pStmt = 0;
    *ppApi = 0;
    int rc = sqlite3_prepare(db, "SELECT fts5(?1)", -1, &pStmt, 0);
    if (rc == SQLITE_OK) {
        sqlite3_bind_pointer(pStmt, 1, reinterpret_cast<void *>(ppApi), "fts5_api_ptr", 0);
        (void)sqlite3_step(pStmt);
        rc = sqlite3_finalize(pStmt);
    }
    return rc;
}

static int
tok_create(void *sqlite3, const char **azArg, int nArg, Fts5Tokenizer **ppOut) {
    int rc = SQLITE_OK;
    Tokenizer *p = new (std::nothrow) Tokenizer(azArg, nArg);
    if (p) *ppOut = reinterpret_cast<Fts5Tokenizer *>(p);
    else rc = SQLITE_NOMEM;
    return rc;
}

static int
tok_tokenize(Fts5Tokenizer *tokenizer_ptr, void *callback_ctx, int flags, const char *text, int text_sz, token_callback_func callback) {
    Tokenizer *p = reinterpret_cast<Tokenizer*>(tokenizer_ptr);
    try {
        return p->tokenize(callback_ctx, flags, text, text_sz, callback);
    } catch (std::bad_alloc &ex) {
        return SQLITE_NOMEM;
    } catch (...) {
        return SQLITE_ERROR;
    }

}

static void
tok_delete(Fts5Tokenizer *p) {
    Tokenizer *t = reinterpret_cast<Tokenizer*>(p);
    delete t;
}

extern "C" {
#ifdef _MSC_VER
#define MYEXPORT __declspec(dllexport)
#else
#define MYEXPORT __attribute__ ((visibility ("default")))
#endif

MYEXPORT int
calibre_sqlite_extension_init(sqlite3 *db, char **pzErrMsg, const sqlite3_api_routines *pApi){
    SQLITE_EXTENSION_INIT2(pApi);
    fts5_api *fts5api = NULL;
    int rc = fts5_api_from_db(db, &fts5api);
    if (rc != SQLITE_OK) {
        *pzErrMsg = (char*)"Failed to get FTS 5 API with error code";
        return rc;
    }
    if (!fts5api || fts5api->iVersion < 2) {
        *pzErrMsg = (char*)"FTS 5 iVersion too old or NULL pointer";
        return SQLITE_ERROR;
    }
    fts5_tokenizer tok = {tok_create, tok_delete, tok_tokenize};
    fts5api->xCreateTokenizer(fts5api, "calibre", reinterpret_cast<void *>(fts5api), &tok, NULL);
    return SQLITE_OK;
}
}


static PyMethodDef methods[] = {
    {NULL, NULL, 0, NULL}
};

static int
exec_module(PyObject *mod) { return 0; }

static PyModuleDef_Slot slots[] = { {Py_mod_exec, (void*)exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

extern "C" {
CALIBRE_MODINIT_FUNC PyInit_sqlite_extension(void) {
    module_def.m_name     = "sqlite_extension";
    module_def.m_doc      = "Implement ICU based tokenizer for FTS5";
    module_def.m_methods  = methods;
    module_def.m_slots    = slots;
    return PyModuleDef_Init(&module_def);
}
} // }}}
