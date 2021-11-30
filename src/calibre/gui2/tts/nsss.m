/*
 * nsss.m
 * Copyright (C) 2020 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */
#define PY_SSIZE_T_CLEAN

#include <Python.h>
#import <AppKit/AppKit.h>
// Structures {{{
typedef struct {
    PyObject_HEAD
    NSSpeechSynthesizer *nsss;
	PyObject *callback;
} NSSS;

typedef enum { MARK, END } MessageType;

static PyTypeObject NSSSType = {
    PyVarObject_HEAD_INIT(NULL, 0)
};

static void
dispatch_message(NSSS *self, MessageType which, unsigned int val) {
	PyGILState_STATE state = PyGILState_Ensure();
	PyObject *ret = PyObject_CallFunction(self->callback, "iI", which, val);
	if (ret) Py_DECREF(ret);
	else PyErr_Print();
	PyGILState_Release(state);
}

@interface SynthesizerDelegate : NSObject <NSSpeechSynthesizerDelegate> {
	@private
	NSSS *nsss;
}

- (id)initWithNSSS:(NSSS *)x;
@end

@implementation SynthesizerDelegate

- (id)initWithNSSS:(NSSS *)x {
    self = [super init];
    nsss = x;
    return self;
}

- (void)speechSynthesizer:(NSSpeechSynthesizer *)sender didFinishSpeaking:(BOOL)success {
	dispatch_message(nsss, END, success);
}

- (void)speechSynthesizer:(NSSpeechSynthesizer *)sender didEncounterSyncMessage:(NSString *)message {
	NSError *err = nil;
	NSNumber *syncProp = (NSNumber*) [sender objectForProperty: NSSpeechRecentSyncProperty error: &err];
	if (syncProp && !err) dispatch_message(nsss, MARK, syncProp.unsignedIntValue);
}

@end
// }}}

static PyObject *
NSSS_new(PyTypeObject *type, PyObject *args, PyObject *kwds) {
	PyObject *callback;
	if (!PyArg_ParseTuple(args, "O", &callback)) return NULL;
	if (!PyCallable_Check(callback)) { PyErr_SetString(PyExc_TypeError, "callback must be a callable"); return NULL; }
	NSSS *self = (NSSS *) type->tp_alloc(type, 0);
	if (self) {
		self->callback = callback;
		Py_INCREF(callback);
		self->nsss = [[NSSpeechSynthesizer alloc] initWithVoice:nil];
		if (self->nsss) {
			self->nsss.delegate = [[SynthesizerDelegate alloc] initWithNSSS:self];
		} else return PyErr_NoMemory();
	}
	return (PyObject*)self;
}

static void
NSSS_dealloc(NSSS *self) {
	if (self->nsss) {
		if (self->nsss.delegate) [self->nsss.delegate release];
		self->nsss.delegate = nil;
		[self->nsss release];
	}
	self->nsss = nil;
	Py_CLEAR(self->callback);
}

static PyObject*
as_python(NSObject *x) {
	if (!x) Py_RETURN_NONE;
	if ([x isKindOfClass:[NSString class]]) {
		NSString *s = (NSString*)x;
		return PyUnicode_FromString([s UTF8String]);
	}
	if ([x isKindOfClass:[NSNumber class]]) {
		NSNumber *n = (NSNumber*)x;
		return PyFloat_FromDouble([n doubleValue]);
	}
	Py_RETURN_NONE;
}

static PyObject*
NSSS_get_all_voices(NSSS *self, PyObject *args) {
	PyObject *ans = PyDict_New();
	if (!ans) return NULL;
	NSLocale *locale = [NSLocale autoupdatingCurrentLocale];
	for (NSSpeechSynthesizerVoiceName voice_id in [NSSpeechSynthesizer availableVoices]) {
		NSDictionary *attributes = [NSSpeechSynthesizer attributesForVoice:voice_id];
		if (attributes) {
			NSObject *lang_key = [attributes objectForKey:NSVoiceLocaleIdentifier];
			const char *lang_name = NULL;
			if (lang_key && [lang_key isKindOfClass:[NSString class]]) {
				NSString *display_name = [locale displayNameForKey:NSLocaleIdentifier value:(NSString*)lang_key];
				if (display_name) lang_name = [display_name UTF8String];
			}
#define E(x, y) #x, as_python([attributes objectForKey:y])
			PyObject *v = Py_BuildValue("{sN sN sN sN sN sz}",
					E(name, NSVoiceName), E(age, NSVoiceAge), E(gender, NSVoiceGender),
					E(demo_text, NSVoiceDemoText), E(locale_id, NSVoiceLocaleIdentifier), "language_display_name", lang_name);
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
NSSS_set_command_delimiters(NSSS *self, PyObject *args) {
	// this function doesn't actually work
	// https://openradar.appspot.com/6524554
	const char *left, *right;
	if (!PyArg_ParseTuple(args, "ss", &left, &right)) return NULL;
	NSError *err = nil;
	[self->nsss setObject:@{NSSpeechCommandPrefix:@(left), NSSpeechCommandSuffix:@(right)} forProperty:NSSpeechCommandDelimiterProperty error:&err];
	if (err) {
		PyErr_SetString(PyExc_OSError, [[NSString stringWithFormat:@"Failed to set delimiters: %@", err] UTF8String]);
		return NULL;
	}
	Py_RETURN_NONE;
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

static PyObject*
NSSS_status(NSSS *self, PyObject *args) {
	NSError *err = nil;
	NSDictionary *status = [self->nsss objectForProperty:NSSpeechStatusProperty error:&err];
	if (err) {
		PyErr_SetString(PyExc_OSError, [[err localizedDescription] UTF8String]);
		return NULL;
	}
	PyObject *ans = PyDict_New();
	if (ans) {
		NSNumber *result = [status objectForKey:NSSpeechStatusOutputBusy];
		if (result) {
			if (PyDict_SetItemString(ans, "synthesizing", [result boolValue] ? Py_True : Py_False) != 0) { Py_CLEAR(ans); return NULL; }
		}
		result = [status objectForKey:NSSpeechStatusOutputPaused];
		if (result) {
			if (PyDict_SetItemString(ans, "paused", [result boolValue] ? Py_True : Py_False) != 0) { Py_CLEAR(ans); return NULL; }
		}
	}
	return ans;
}

static PyObject*
NSSS_pause(NSSS *self, PyObject *args) {
	unsigned int boundary = NSSpeechWordBoundary;
	if (!PyArg_ParseTuple(args, "|I", &boundary)) return NULL;
	[self->nsss pauseSpeakingAtBoundary:boundary];
	Py_RETURN_NONE;
}

static PyObject*
NSSS_resume(NSSS *self, PyObject *args) {
	[self->nsss continueSpeaking];
	Py_RETURN_NONE;
}

static PyObject*
NSSS_stop(NSSS *self, PyObject *args) {
	[self->nsss stopSpeaking];
	Py_RETURN_NONE;
}


// Boilerplate {{{
#define M(name, args) { #name, (PyCFunction)NSSS_##name, args, ""}
static PyMethodDef NSSS_methods[] = {
    M(get_all_voices, METH_NOARGS),
    M(status, METH_NOARGS),
    M(resume, METH_NOARGS),
    M(stop, METH_NOARGS),
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
	M(set_command_delimiters, METH_VARARGS),
	M(pause, METH_VARARGS),
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
	PyModule_AddIntMacro(module, MARK);
	PyModule_AddIntMacro(module, END);
	PyModule_AddIntMacro(module, NSSpeechImmediateBoundary);
	PyModule_AddIntMacro(module, NSSpeechWordBoundary);
	PyModule_AddIntMacro(module, NSSpeechSentenceBoundary);

	return 0;
}

// }}}
