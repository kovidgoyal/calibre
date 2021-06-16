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
    bool remove_diacritics;
    std::vector<int> byte_offsets;
    token_callback_func current_callback;
    void *current_callback_ctx;
    std::string token_buf;

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

    int send_token(int32_t start_offset, int32_t end_offset, int flags = 0) {
        return current_callback(current_callback_ctx, flags, token_buf.c_str(), token_buf.size(), byte_offsets[start_offset], byte_offsets[end_offset]);
    }

public:
    Tokenizer(const char **args, int nargs) : remove_diacritics(true), byte_offsets(), token_buf() {
        for (int i = 0; i < nargs; i++) {
            if (strcmp(args[i], "remove_diacritics") == 0) {
                i++;
                if (i < nargs && strcmp(args[i], "0") == 0) remove_diacritics = false;
            }
        }
    }

    int tokenize(void *callback_ctx, int flags, const char *text, int text_sz, token_callback_func callback) {
        current_callback = callback; current_callback_ctx = callback_ctx;
        icu::UnicodeString str(text_sz, 0, 0);
        byte_offsets.clear();
        byte_offsets.reserve(text_sz + 8);
        populate_icu_string(text, text_sz, str, byte_offsets);
        str.foldCase(U_FOLD_CASE_DEFAULT);
        int32_t offset = str.getChar32Start(0);
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
                token_buf.clear(); token_buf.reserve(4 * (offset - start_offset));
                token.toUTF8String(token_buf);
                int rc = send_token(start_offset, offset);
                if (rc != SQLITE_OK) return rc;
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
    try {
        Tokenizer *p = new Tokenizer(azArg, nArg);
        *ppOut = reinterpret_cast<Fts5Tokenizer *>(p);
    } catch (std::bad_alloc &ex) {
        return SQLITE_NOMEM;
    } catch (...) {
        return SQLITE_ERROR;
    }
    return SQLITE_OK;
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
    fts5api->xCreateTokenizer(fts5api, "unicode61", reinterpret_cast<void *>(fts5api), &tok, NULL);
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
