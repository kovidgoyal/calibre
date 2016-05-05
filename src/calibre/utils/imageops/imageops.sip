//Define the SIP wrapper to the imageops code
//Author - Kovid Goyal <kovid@kovidgoyal.net>

%Module(name=imageops, version=1)

%Import QtCore/QtCoremod.sip
%Import QtGui/QtGuimod.sip
%ModuleCode
#include <imageops.h>
#define CATCH \
			if (sipRes == NULL) return NULL; \
        } catch (std::out_of_range &exc) { PyErr_SetString(PyExc_ValueError, exc.what()); return NULL; \
        } catch (std::bad_alloc &) { PyErr_NoMemory(); return NULL; \
        } catch (std::exception &exc) { PyErr_SetString(PyExc_RuntimeError, exc.what()); return NULL; \
        } catch (...) { PyErr_SetString(PyExc_RuntimeError, "unknown error"); return NULL;} 
%End

QImage* remove_borders(const QImage &image, double fuzz);
%MethodCode
		try {
			sipRes = remove_borders(*a0, a1);
        CATCH
%End

QImage* grayscale(const QImage &image);
%MethodCode
		try {
			sipRes = grayscale(*a0);
        CATCH
%End
