#ifndef DUKPY_H
#define DUKPY_H

#include <Python.h>
#include "duktape/duktape.h"

typedef struct DukContext_ DukContext;
typedef struct DukObject_ DukObject;
typedef struct DukEnum_ DukEnum;


/* module.c */

PyObject DukUndefined;
#define Duk_undefined (&DukUndefined)


/* context.c */

struct DukContext_ {
    PyObject_HEAD
    duk_context *ctx;
    DukContext *heap_manager;
};

PyTypeObject DukContext_Type;

DukContext *DukContext_get(duk_context *ctx);


/* proxy.c */

struct DukObject_ {
    PyObject_HEAD
    DukContext *context;
    DukObject *parent;
};

PyTypeObject DukObject_Type;
PyTypeObject DukArray_Type;
PyTypeObject DukFunction_Type;
PyTypeObject DukEnum_Type;

DukObject *DukObject_from_DukContext(DukContext *context, duk_idx_t index);
DukObject *DukObject_from_ctx(duk_context *ctx, duk_idx_t index);
int DukObject_push(DukObject *self, duk_context *ctx);

DukObject *DukArray_from_ctx(duk_context *ctx, duk_idx_t index);
DukObject *DukFunction_from_ctx(duk_context *ctx, duk_idx_t index);

typedef enum {
    DUKENUM_KEYS,
    DUKENUM_VALUES,
    DUKENUM_PAIRS
} dukenum_mode_t;

struct DukEnum_ {
    PyObject_HEAD
    DukObject base;
    dukenum_mode_t mode;
};

DukEnum *DukEnum_from_DukContext(DukContext *context, dukenum_mode_t mode);


/* conversions.c */

int python_to_duk(duk_context *ctx, PyObject *value);
PyObject *duk_to_python(duk_context *ctx, duk_idx_t index);


#endif /* DUKPY_H */
