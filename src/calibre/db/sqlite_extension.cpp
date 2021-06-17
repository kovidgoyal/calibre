/*
 * sqlite_extension.cpp
 * Copyright (C) 2021 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define UNICODE
#include <Python.h>
#include <stdlib.h>
#include <string>
#include <locale>
#include <vector>
#include <sqlite3ext.h>
#include <unicode/unistr.h>
#include <unicode/uchar.h>
#include <unicode/translit.h>
#include <unicode/errorcode.h>
#include <unicode/brkiter.h>
#include "../utils/cpp_binding.h"
SQLITE_EXTENSION_INIT1

typedef int (*token_callback_func)(void *, int, const char *, int, int, int);


// UTF-8 decode taken from: https://bjoern.hoehrmann.de/utf-8/decoder/dfa/

static const uint8_t utf8_data[] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 00..1f
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 20..3f
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 40..5f
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 60..7f
  1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9, // 80..9f
  7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7, // a0..bf
  8,8,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2, // c0..df
  0xa,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x4,0x3,0x3, // e0..ef
  0xb,0x6,0x6,0x6,0x5,0x8,0x8,0x8,0x8,0x8,0x8,0x8,0x8,0x8,0x8,0x8, // f0..ff
  0x0,0x1,0x2,0x3,0x5,0x8,0x7,0x1,0x1,0x1,0x4,0x6,0x1,0x1,0x1,0x1, // s0..s0
  1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,1,1,1,1,0,1,0,1,1,1,1,1,1, // s1..s2
  1,2,1,1,1,1,1,2,1,2,1,1,1,1,1,1,1,1,1,1,1,1,1,2,1,1,1,1,1,1,1,1, // s3..s4
  1,2,1,1,1,1,1,1,1,2,1,1,1,1,1,1,1,1,1,1,1,1,1,3,1,3,1,1,1,1,1,1, // s5..s6
  1,3,1,1,1,1,1,3,1,3,1,1,1,1,1,1,1,3,1,1,1,1,1,1,1,1,1,1,1,1,1,1, // s7..s8
};


typedef enum UTF8State { UTF8_ACCEPT = 0, UTF8_REJECT = 1} UTF8State;

uint32_t
decode_utf8(UTF8State* state, uint32_t* codep, uint8_t byte) {
  uint32_t type = utf8_data[byte];

  *codep = (*state != UTF8_ACCEPT) ?
    (byte & 0x3fu) | (*codep << 6) :
    (0xff >> type) & (byte);

  *state = (UTF8State) utf8_data[256 + *state*16 + type];
  return *state;
}


static void
populate_icu_string(const char *text, int text_sz, icu::UnicodeString &str, std::vector<int> &byte_offsets) {
    UTF8State state = UTF8_ACCEPT, prev = UTF8_ACCEPT;
    uint32_t codep = 0;
    for (int i = 0, pos = 0; i < text_sz; i++) {
        switch(decode_utf8(&state, &codep, text[i])) {
            case UTF8_ACCEPT: {
                size_t sz = str.length();
                str.append((UChar32)codep);
                sz = str.length() - sz;
                for (size_t x = 0; x < sz; x++) byte_offsets.push_back(pos);
                pos = i + 1;
            }
                break;
            case UTF8_REJECT:
                state = UTF8_ACCEPT;
                if (prev != UTF8_ACCEPT && i > 0) i--;
                break;
        }
        prev = state;
    }
    byte_offsets.push_back(text_sz);
}

class Tokenizer {
private:
    icu::Transliterator *diacritics_remover;
    std::vector<int> byte_offsets;
    std::string token_buf;
    token_callback_func current_callback;
    void *current_callback_ctx;

    bool is_token_char(UChar32 ch) const {
        switch(u_charType(ch)) {
            case U_UPPERCASE_LETTER:
            case U_LOWERCASE_LETTER:
            case U_TITLECASE_LETTER:
            case U_MODIFIER_LETTER:
            case U_OTHER_LETTER:
            case U_DECIMAL_DIGIT_NUMBER:
            case U_LETTER_NUMBER:
            case U_OTHER_NUMBER:
            case U_PRIVATE_USE_CHAR:
                return true;
            default:
                return false;
        }
    }

    int send_token(const icu::UnicodeString &token, int32_t start_offset, int32_t end_offset, int flags = 0) {
        token_buf.clear(); token_buf.reserve(4 * token.length());
        token.toUTF8String(token_buf);
        return current_callback(current_callback_ctx, flags, token_buf.c_str(), (int)token_buf.size(), byte_offsets[start_offset], byte_offsets[end_offset]);
    }

public:
    int constructor_error;
    Tokenizer(const char **args, int nargs) :
        diacritics_remover(NULL),
        byte_offsets(), token_buf(),
        current_callback(NULL), current_callback_ctx(NULL), constructor_error(SQLITE_OK)
    {
        bool remove_diacritics = true;
        for (int i = 0; i < nargs; i++) {
            if (strcmp(args[i], "remove_diacritics") == 0) {
                i++;
                if (i < nargs && strcmp(args[i], "0") == 0) remove_diacritics = false;
            }
        }
        if (remove_diacritics) {
            icu::ErrorCode status;
            diacritics_remover = icu::Transliterator::createInstance("NFD; [:M:] Remove; NFC", UTRANS_FORWARD, status);
            if (status.isFailure()) {
                fprintf(stderr, "Failed to create ICU transliterator to remove diacritics with error: %s\n", status.errorName());
                constructor_error = SQLITE_INTERNAL;
            }
        }
    }
    ~Tokenizer() {
        if (diacritics_remover) icu::Transliterator::unregister(diacritics_remover->getID());
        diacritics_remover = NULL;
    }

    int tokenize(void *callback_ctx, int flags, const char *text, int text_sz, token_callback_func callback) {
        current_callback = callback; current_callback_ctx = callback_ctx;
        icu::UnicodeString str(text_sz, 0, 0);
        byte_offsets.clear();
        byte_offsets.reserve(text_sz + 8);
        populate_icu_string(text, text_sz, str, byte_offsets);
        str.foldCase(U_FOLD_CASE_DEFAULT);
        int32_t offset = str.getChar32Start(0);
        int rc;
        bool for_query = (flags & FTS5_TOKENIZE_QUERY) != 0;
        while (offset < str.length()) {
            // soak up non-token chars
            while (offset < str.length() && !is_token_char(str.char32At(offset))) offset = str.moveIndex32(offset, 1);
            if (offset >= str.length()) break;
            // get the length of the sequence of token chars
            int32_t start_offset = offset;
            while (offset < str.length() && is_token_char(str.char32At(offset))) offset = str.moveIndex32(offset, 1);
            if (offset > start_offset) {
                icu::UnicodeString token(str, start_offset, offset - start_offset);
                token.foldCase(U_FOLD_CASE_DEFAULT);
                if ((rc = send_token(token, start_offset, offset)) != SQLITE_OK) return rc;
                if (!for_query && diacritics_remover) {
                    icu::UnicodeString tt(token);
                    diacritics_remover->transliterate(tt);
                    if (tt != token) {
                        if ((rc = send_token(tt, start_offset, offset, FTS5_TOKEN_COLOCATED)) != SQLITE_OK) return rc;
                    }
                }
            }
        }
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
    try {
        Tokenizer *p = new Tokenizer(azArg, nArg);
        *ppOut = reinterpret_cast<Fts5Tokenizer *>(p);
        if (p->constructor_error != SQLITE_OK)  {
            rc = p->constructor_error;
            delete p;
        }
    } catch (std::bad_alloc const&) {
        return SQLITE_NOMEM;
    } catch (...) {
        return SQLITE_ERROR;
    }
    return rc;
}

static int
tok_tokenize(Fts5Tokenizer *tokenizer_ptr, void *callback_ctx, int flags, const char *text, int text_sz, token_callback_func callback) {
    Tokenizer *p = reinterpret_cast<Tokenizer*>(tokenizer_ptr);
    try {
        return p->tokenize(callback_ctx, flags, text, text_sz, callback);
    } catch (std::bad_alloc const&) {
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
    fts5api->xCreateTokenizer(fts5api, "unicode61", reinterpret_cast<void *>(fts5api), &tok, NULL);
    return SQLITE_OK;
}
}

static PyObject*
get_locales_for_break_iteration(PyObject *self, PyObject *args) {
    std::unique_ptr<icu::StringEnumeration> locs(icu::BreakIterator::getAvailableLocales());
    icu::ErrorCode status;
    pyobject_raii ans(PyList_New(0));
    if (ans) {
        const icu::UnicodeString *item;
        while ((item = locs->snext(status))) {
            std::string name;
            item->toUTF8String(name);
            pyobject_raii pn(PyUnicode_FromString(name.c_str()));
            if (pn) PyList_Append(ans.ptr(), pn.ptr());
        }
        if (status.isFailure()) {
            PyErr_Format(PyExc_RuntimeError, "Failed to iterate over locales with error: %s", status.errorName());
            return NULL;
        }
    }
    return ans.detach();
}

static PyMethodDef methods[] = {
    {"get_locales_for_break_iteration", get_locales_for_break_iteration, METH_NOARGS,
     "Get list of available locales for break iteration"
    },
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
