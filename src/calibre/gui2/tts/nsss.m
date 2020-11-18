/*
 * nsss.m
 * Copyright (C) 2020 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include <Python.h>
#import <AppKit/AppKit.h>
// Structures {{{
typedef struct {
    PyObject_HEAD
    NSSpeechSynthesizer *nsss;
} NSSS;


static PyTypeObject NSSSType = {
    PyVarObject_HEAD_INIT(NULL, 0)
};
// }}}

static PyObject *
NSSS_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
	NSSS *self = (NSSS *) type->tp_alloc(type, 0);
	if (self) {
		self->nsss = [[NSSpeechSynthesizer alloc] initWithVoice:nil];
		if (self->nsss) {

		} else PyErr_NoMemory();
	}
	return (PyObject*)self;
}

static void
NSSS_dealloc(NSSS *self) {
	if (self->nsss) [self->nsss release];
	self->nsss = nil;
}

static PyObject*
NSSS_get_all_voices(NSSS *self, PyObject *args) {
	PyObject *ans = PyDict_New();
	if (!ans) return NULL;
	for (NSSpeechSynthesizerVoiceName voice_id in [NSSpeechSynthesizer availableVoices]) {
		NSDictionary *attributes = [NSSpeechSynthesizer attributesForVoice:voice_id];
		if (attributes) {
			NSString *name = [attributes objectForKey:NSVoiceName];
			NSString *age = [attributes objectForKey:NSVoiceAge];
			NSString *gender = [attributes objectForKey:NSVoiceGender];
			NSString *demo_text = [attributes objectForKey:NSVoiceDemoText];
			NSString *locale_id = [attributes objectForKey:NSVoiceLocaleIdentifier];
#define E(x) #x, (x ? [x UTF8String] : NULL)
			PyObject *v = Py_BuildValue("{ss ss ss ss ss}", E(name), E(age), E(gender), E(demo_text), E(locale_id));
			if (!v) { Py_DECREF(ans); return NULL; }
#undef E
			if (PyDict_SetItemString(ans, [voice_id UTF8String], v) != 0) {
				Py_DECREF(ans); Py_DECREF(v); return NULL;
			}
			Py_DECREF(v);
		}
	}
	return ans;
}


static PyObject*
NSSS_get_current_voice(NSSS *self, PyObject *args) {
	return Py_BuildValue("s", [[self->nsss voice] UTF8String]);
}

static PyObject*
NSSS_set_current_voice(NSSS *self, PyObject *args) {
	const char *name;
	if (!PyArg_ParseTuple(args, "s", &name)) return NULL;
	BOOL ok = [self->nsss setVoice:@(name)];
	if (ok) Py_RETURN_TRUE;
	Py_RETURN_FALSE;
}

static PyObject*
NSSS_any_application_speaking(NSSS *self, PyObject *args) {
	return Py_BuildValue("O", NSSpeechSynthesizer.anyApplicationSpeaking ? Py_True : Py_False);
}

static PyObject*
NSSS_speaking(NSSS *self, PyObject *args) {
	return Py_BuildValue("O", self->nsss.speaking ? Py_True : Py_False);
}

static PyObject*
NSSS_get_current_volume(NSSS *self, PyObject *args) {
	return Py_BuildValue("f", self->nsss.volume);
}

static PyObject*
NSSS_set_current_volume(NSSS *self, PyObject *args) {
	float vol;
	if (!PyArg_ParseTuple(args, "f", &vol)) return NULL;
	self->nsss.volume = vol;
	return Py_BuildValue("f", self->nsss.volume);
}

static PyObject*
NSSS_get_current_rate(NSSS *self, PyObject *args) {
	return Py_BuildValue("f", self->nsss.rate);
}

static PyObject*
NSSS_set_current_rate(NSSS *self, PyObject *args) {
	float vol;
	if (!PyArg_ParseTuple(args, "f", &vol)) return NULL;
	self->nsss.rate = vol;
	return Py_BuildValue("f", self->nsss.rate);
}

static PyObject*
NSSS_speak(NSSS *self, PyObject *args) {
	const char *text;
	if (!PyArg_ParseTuple(args, "s", &text)) return NULL;
	if ([self->nsss startSpeakingString:@(text)]) Py_RETURN_TRUE;
	Py_RETURN_FALSE;
}


static PyObject*
NSSS_start_saving_to_path(NSSS *self, PyObject *args) {
	const char *text, *path;
	if (!PyArg_ParseTuple(args, "ss", &text, &path)) return NULL;
	NSURL *url = [NSURL fileURLWithPath:@(path) isDirectory: NO];
	BOOL ok = [self->nsss startSpeakingString:@(text) toURL:url];
	[url release];
	if (ok) Py_RETURN_TRUE;
	Py_RETURN_FALSE;
}

// Boilerplate {{{
#define M(name, args) { #name, (PyCFunction)NSSS_##name, args, ""}
static PyMethodDef NSSS_methods[] = {
    M(get_all_voices, METH_NOARGS),
    M(speak, METH_VARARGS),
    M(start_saving_to_path, METH_VARARGS),
    M(speaking, METH_NOARGS),

    M(any_application_speaking, METH_NOARGS),
    M(get_current_voice, METH_NOARGS),
    M(set_current_voice, METH_VARARGS),
    M(get_current_volume, METH_NOARGS),
    M(set_current_volume, METH_VARARGS),
    M(get_current_rate, METH_NOARGS),
    M(set_current_rate, METH_VARARGS),
    {NULL, NULL, 0, NULL}
};
#undef M

int
nsss_init_module(PyObject *module) {
    NSSSType.tp_name = "cocoa.NSSpeechSynthesizer";
    NSSSType.tp_doc = "Wrapper for NSSpeechSynthesizer";
    NSSSType.tp_basicsize = sizeof(NSSS);
    NSSSType.tp_itemsize = 0;
    NSSSType.tp_flags = Py_TPFLAGS_DEFAULT;
    NSSSType.tp_new = NSSS_new;
    NSSSType.tp_methods = NSSS_methods;
	NSSSType.tp_dealloc = (destructor)NSSS_dealloc;
	if (PyType_Ready(&NSSSType) < 0) return -1;

	Py_INCREF(&NSSSType);
    if (PyModule_AddObject(module, "NSSpeechSynthesizer", (PyObject *) &NSSSType) < 0) {
        Py_DECREF(&NSSSType);
        return -1;
    }

	return 0;
}

// }}}
