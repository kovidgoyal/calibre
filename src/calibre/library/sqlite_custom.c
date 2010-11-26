#define UNICODE
#include <Python.h>


#include <stdlib.h>

#include <sqlite3ext.h>
SQLITE_EXTENSION_INIT1

#ifdef _MSC_VER
#define MYEXPORT __declspec(dllexport)
#else
#define MYEXPORT
#endif

// sortconcat {{{

typedef struct {
    unsigned char *val;
    int index;
    int length;
} SortConcatItem;

typedef struct {
    SortConcatItem **vals;
    int count;
    int length;
} SortConcatList;

static void sort_concat_step(sqlite3_context *context, int argc, sqlite3_value **argv) {
    const unsigned char *val;
    int idx, sz;
    SortConcatList *list;

    assert(argc == 2);

    list = (SortConcatList*) sqlite3_aggregate_context(context, sizeof(*list));
    if (list == NULL) return;

    if (list->vals == NULL) {
        list->vals = (SortConcatItem**)calloc(100, sizeof(SortConcatItem*));
        if (list->vals == NULL) return;
        list->length = 100;
        list->count = 0;
    }

    if (list->count == list->length) {
        list->vals = (SortConcatItem**)realloc(list->vals, list->length + 100);
        if (list->vals == NULL) return;
        list->length = list->length + 100;
    }

    list->vals[list->count] = (SortConcatItem*)calloc(1, sizeof(SortConcatItem));
    if (list->vals[list->count] == NULL) return;
    
    idx = sqlite3_value_int(argv[0]);
    val = sqlite3_value_text(argv[1]);
    sz  = sqlite3_value_bytes(argv[1]);
    if (idx == 0 || val == NULL || sz == 0) {free(list->vals[list->count]); return;}



    list->vals[list->count]->val = (unsigned char*)calloc(sz, sizeof(unsigned char));
    if (list->vals[list->count]->val == NULL) 
        {free(list->vals[list->count]); return;}
    list->vals[list->count]->index = idx;
    list->vals[list->count]->length = sz;
    memcpy(list->vals[list->count]->val, val, sz);
    list->count = list->count + 1;

}

static void sort_concat_free(SortConcatList *list) {
    int i;
    if (list == NULL) return;
    for (i = 0; i < list->count; i++) {
        free(list->vals[i]->val);
        free(list->vals[i]);
    }
}

static int sort_concat_cmp(const void *a_, const void *b_) {
    return (*((SortConcatItem**)a_))->index - (*((SortConcatItem**)b_))->index;
}

static unsigned char* sort_concat_do_finalize(SortConcatList *list, const unsigned char join) {
    unsigned char *ans, *pos;
    int sz = 0, i;

    for (i = 0; i < list->count; i++) { 
        sz += list->vals[i]->length;
    }
    sz += list->count;

    ans = (unsigned char *) calloc(sz, sizeof(unsigned char));
    if (ans == NULL) return ans;

    pos = ans;
    for (i = 0; i < list->count; i++) {
        if (list->vals[i]->length > 0) {
            memcpy(pos, list->vals[i]->val, list->vals[i]->length);
            pos += list->vals[i]->length;
            if (i < list->count -1) { *pos = join; pos += 1; }
        }
    }

    return ans;

}

static void sort_concat_finalize(sqlite3_context *context) {
    SortConcatList *list;
    unsigned char *ans;

    list = (SortConcatList*) sqlite3_aggregate_context(context, sizeof(*list));

    if (list != NULL && list->vals != NULL && list->count > 0) {
        qsort(list->vals, list->count, sizeof(list->vals[0]), sort_concat_cmp);
        ans = sort_concat_do_finalize(list, ',');
        if (ans != NULL) sqlite3_result_text(context, (char*)ans, -1, SQLITE_TRANSIENT);
        free(ans);
        sort_concat_free(list);
    }

}

static void sort_concat_finalize2(sqlite3_context *context) {
    SortConcatList *list;
    unsigned char *ans;

    list = (SortConcatList*) sqlite3_aggregate_context(context, sizeof(*list));

    if (list != NULL && list->vals != NULL && list->count > 0) {
        qsort(list->vals, list->count, sizeof(list->vals[0]), sort_concat_cmp);
        ans = sort_concat_do_finalize(list, '|');
        if (ans != NULL) sqlite3_result_text(context, (char*)ans, -1, SQLITE_TRANSIENT);
        free(ans);
        sort_concat_free(list);
    }

}

// }}}

MYEXPORT int sqlite3_extension_init(
    sqlite3 *db, char **pzErrMsg, const sqlite3_api_routines *pApi){
  SQLITE_EXTENSION_INIT2(pApi);
  sqlite3_create_function(db, "sortconcat", 2, SQLITE_UTF8, NULL, NULL, sort_concat_step, sort_concat_finalize);
  sqlite3_create_function(db, "sort_concat", 2, SQLITE_UTF8, NULL, NULL, sort_concat_step, sort_concat_finalize2);
  return 0;
}

static PyObject *
sqlite_custom_init_funcs(PyObject *self, PyObject *args) {
    Py_RETURN_NONE;
}

static PyMethodDef sqlite_custom_methods[] = {
    {"init_funcs", sqlite_custom_init_funcs, METH_VARARGS,
        "init_funcs()\n\nInitialize module."
    },

    {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initsqlite_custom(void) {
    PyObject *m;
    m = Py_InitModule3("sqlite_custom", sqlite_custom_methods,
    "Implementation of custom sqlite methods in C for speed."
    );
    if (m == NULL) return;
}
