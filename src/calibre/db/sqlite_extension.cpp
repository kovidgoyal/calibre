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
#include <map>
#include <cstring>
#include <sqlite3ext.h>
#include <unicode/unistr.h>
#include <unicode/uchar.h>
#include <unicode/translit.h>
#include <unicode/errorcode.h>
#include <unicode/brkiter.h>
#include <unicode/uscript.h>
#include "../utils/cpp_binding.h"
SQLITE_EXTENSION_INIT1

typedef int (*token_callback_func)(void *, int, const char *, int, int, int);


// Converting SQLITE text to ICU strings {{{
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
// }}}

static char ui_language[16] = {0};

class IteratorDescription {
    public:
        const char *language;
        UScriptCode script;
};

struct char_cmp {
    bool operator () (const char *a, const char *b) const
    {
        return strcmp(a,b)<0;
    }
};

typedef std::unique_ptr<icu::BreakIterator> BreakIterator;

class Tokenizer {
private:
    bool remove_diacritics;
    std::unique_ptr<icu::Transliterator> diacritics_remover;
    std::vector<int> byte_offsets;
    std::string token_buf, current_ui_language;
    token_callback_func current_callback;
    void *current_callback_ctx;
    std::map<const char*, BreakIterator, char_cmp> iterators;

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
            case U_CURRENCY_SYMBOL:
            case U_OTHER_SYMBOL:
            case U_PRIVATE_USE_CHAR:
                return true;
            default:
                break;;
        }
        return false;
    }

    int send_token(const icu::UnicodeString &token, int32_t start_offset, int32_t end_offset, int flags = 0) {
        token_buf.clear(); token_buf.reserve(4 * token.length());
        token.toUTF8String(token_buf);
        return current_callback(current_callback_ctx, flags, token_buf.c_str(), (int)token_buf.size(), byte_offsets[start_offset], byte_offsets[end_offset]);
    }

    const char* iterator_language_for_script(UScriptCode script) const {
        switch (script) {
            default:
                return "";
            case USCRIPT_THAI:
            case USCRIPT_LAO:
                return "th_TH";
            case USCRIPT_KHMER:
                return "km_KH";
            case USCRIPT_MYANMAR:
                return "my_MM";
            case USCRIPT_HIRAGANA:
            case USCRIPT_KATAKANA:
                return "ja_JP";
            case USCRIPT_HANGUL:
                return "ko_KR";
            case USCRIPT_HAN:
            case USCRIPT_SIMPLIFIED_HAN:
            case USCRIPT_TRADITIONAL_HAN:
            case USCRIPT_HAN_WITH_BOPOMOFO:
                return "zh";
        }
    }

    bool at_script_boundary(IteratorDescription &current, UChar32 next_codepoint) const {
        UErrorCode err;
        UScriptCode script = uscript_getScript(next_codepoint, &err);
        if (script == USCRIPT_COMMON || script == USCRIPT_INVALID_CODE || script == USCRIPT_INHERITED) return false;
        if (current.script == script) return false;
        const char *lang = iterator_language_for_script(script);
        if (strcmp(current.language, lang) == 0) return false;
        current.script = script; current.language = lang;
        return true;
    }

    void ensure_basic_iterator(void) {
        if (current_ui_language != ui_language || iterators.find("") == iterators.end()) {
            current_ui_language.clear(); current_ui_language = ui_language;
            icu::ErrorCode status;
            if (current_ui_language.empty()) {
                iterators[""] = BreakIterator(icu::BreakIterator::createWordInstance(icu::Locale::getDefault(), status));
            } else {
                ensure_lang_iterator(ui_language);
            }
        }
    }

    BreakIterator& ensure_lang_iterator(const char *lang = "") {
        auto ans = iterators.find(lang);
        if (ans == iterators.end()) {
            icu::ErrorCode status;
            iterators[lang] = BreakIterator(icu::BreakIterator::createWordInstance(icu::Locale::createCanonical(lang), status));
            if (status.isFailure()) {
                iterators[lang] = BreakIterator(icu::BreakIterator::createWordInstance(icu::Locale::getDefault(), status));
            }
            ans = iterators.find(lang);
        }
        return ans->second;
    }

    int tokenize_script_block(const icu::UnicodeString &str, int32_t block_start, int32_t block_limit, bool for_query, token_callback_func callback, void *callback_ctx, BreakIterator &word_iterator) {
        word_iterator->setText(str.tempSubStringBetween(block_start, block_limit));
        int32_t token_start_pos = word_iterator->first() + block_start, token_end_pos;
        int rc = SQLITE_OK;
        do {
            token_end_pos = word_iterator->next();
            if (token_end_pos == icu::BreakIterator::DONE) token_end_pos = block_limit;
            else token_end_pos += block_start;
            if (token_end_pos > token_start_pos) {
                bool is_token = false;
                for (int32_t pos = token_start_pos; !is_token && pos < token_end_pos; pos = str.moveIndex32(pos, 1)) {
                    if (is_token_char(str.char32At(pos))) is_token = true;
                }
                if (is_token) {
                    icu::UnicodeString token(str, token_start_pos, token_end_pos - token_start_pos);
                    token.foldCase(U_FOLD_CASE_DEFAULT);
                    if ((rc = send_token(token, token_start_pos, token_end_pos)) != SQLITE_OK) return rc;
                    if (!for_query && remove_diacritics) {
                        icu::UnicodeString tt(token);
                        diacritics_remover->transliterate(tt);
                        if (tt != token) {
                            if ((rc = send_token(tt, token_start_pos, token_end_pos, FTS5_TOKEN_COLOCATED)) != SQLITE_OK) return rc;
                        }
                    }
                }
            }
            token_start_pos = token_end_pos;
        } while (token_end_pos < block_limit);
        return rc;
    }

public:
    int constructor_error;
    Tokenizer(const char **args, int nargs) :
        remove_diacritics(true), diacritics_remover(),
        byte_offsets(), token_buf(), current_ui_language(ui_language),
        current_callback(NULL), current_callback_ctx(NULL), iterators(),

        constructor_error(SQLITE_OK)
    {
        for (int i = 0; i < nargs; i++) {
            if (strcmp(args[i], "remove_diacritics") == 0) {
                i++;
                if (i < nargs && strcmp(args[i], "0") == 0) remove_diacritics = false;
            }
        }
        if (remove_diacritics) {
            icu::ErrorCode status;
            diacritics_remover.reset(icu::Transliterator::createInstance("NFD; [:M:] Remove; NFC", UTRANS_FORWARD, status));
            if (status.isFailure()) {
                fprintf(stderr, "Failed to create ICU transliterator to remove diacritics with error: %s\n", status.errorName());
                constructor_error = SQLITE_INTERNAL;
                diacritics_remover.reset(NULL);
                remove_diacritics = false;
            }
        }
    }

    int tokenize(void *callback_ctx, int flags, const char *text, int text_sz, token_callback_func callback) {
        ensure_basic_iterator();
        current_callback = callback; current_callback_ctx = callback_ctx;
        icu::UnicodeString str(text_sz, 0, 0);
        byte_offsets.clear();
        byte_offsets.reserve(text_sz + 8);
        populate_icu_string(text, text_sz, str, byte_offsets);
        int32_t offset = str.getChar32Start(0);
        int rc = SQLITE_OK;
        bool for_query = (flags & FTS5_TOKENIZE_QUERY) != 0;
        IteratorDescription state;
        state.language = ""; state.script = USCRIPT_COMMON;
        int32_t start_script_block_at = offset;
        BreakIterator &word_iterator = ensure_lang_iterator(state.language);
        while (offset < str.length()) {
            while (offset < str.length()) {
                UChar32 ch = str.char32At(offset);
                if (at_script_boundary(state, ch)) {
                    if (offset > start_script_block_at) {
                        if ((rc = tokenize_script_block(
                            str, start_script_block_at, offset,
                            for_query, callback, callback_ctx, word_iterator)) != SQLITE_OK) return rc;
                    }
                    break;
                }
                offset = str.moveIndex32(offset, 1);
            }
        }
        if (offset > start_script_block_at) {
            rc = tokenize_script_block(str, start_script_block_at, offset, for_query, callback, callback_ctx, word_iterator);
        }
        return rc;
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

static PyObject*
set_ui_language(PyObject *self, PyObject *args) {
    const char *val;
    if (!PyArg_ParseTuple(args, "s", &val)) return NULL;
    strncpy(ui_language, val, sizeof(ui_language) - 1);
    Py_RETURN_NONE;
}

static int
py_callback(void *ctx, int flags, const char *text, int text_length, int start_offset, int end_offset) {
    PyObject *ans = reinterpret_cast<PyObject*>(ctx);
    pyobject_raii item(Py_BuildValue("{ss# si si si}", "text", text, text_length, "start", start_offset, "end", end_offset, "flags", flags));
    if (item) PyList_Append(ans, item.ptr());
    return SQLITE_OK;
}

static PyObject*
tokenize(PyObject *self, PyObject *args) {
    const char *text; int text_length, remove_diacritics = 1, flags = FTS5_TOKENIZE_DOCUMENT;
    if (!PyArg_ParseTuple(args, "s#|pi", &text, &text_length, &remove_diacritics, &flags)) return NULL;
    const char *targs[2] = {"remove_diacritics", "2"};
    if (!remove_diacritics) targs[1] = "0";
    Tokenizer t(targs, sizeof(targs)/sizeof(targs[0]));
    pyobject_raii ans(PyList_New(0));
    t.tokenize(ans.ptr(), flags, text, text_length, py_callback);
    return ans.detach();
}

static PyMethodDef methods[] = {
    {"get_locales_for_break_iteration", get_locales_for_break_iteration, METH_NOARGS,
     "Get list of available locales for break iteration"
    },
    {"set_ui_language", set_ui_language, METH_VARARGS,
     "Set the current UI language"
    },
    {"tokenize", tokenize, METH_VARARGS,
     "Tokenize a string, useful for testing"
    },
    {NULL, NULL, 0, NULL}
};

static int
exec_module(PyObject *mod) {
    if (PyModule_AddIntMacro(mod, FTS5_TOKENIZE_QUERY) != 0) return 1;
    if (PyModule_AddIntMacro(mod, FTS5_TOKENIZE_DOCUMENT) != 0) return 1;
    if (PyModule_AddIntMacro(mod, FTS5_TOKENIZE_PREFIX) != 0) return 1;
    if (PyModule_AddIntMacro(mod, FTS5_TOKENIZE_AUX) != 0) return 1;
    if (PyModule_AddIntMacro(mod, FTS5_TOKEN_COLOCATED) != 0) return 1;
    return 0;
}

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
