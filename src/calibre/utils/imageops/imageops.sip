//Define the SIP wrapper to the imageops code
//Author - Kovid Goyal <kovid@kovidgoyal.net>

%Module(name=imageops, version=1)

%Import QtCore/QtCoremod.sip
%Import QtGui/QtGuimod.sip
%ModuleCode
#include <imageops.h>
#define IMAGEOPS_PREFIX \
            try {
#define IMAGEOPS_SUFFIX \
        } catch (std::out_of_range &exc) { PyErr_SetString(PyExc_ValueError, exc.what()); return NULL; \
        } catch (std::bad_alloc &) { PyErr_NoMemory(); return NULL; \
        } catch (std::exception &exc) { PyErr_SetString(PyExc_Exception, exc.what()); return NULL; \
        } catch (...) { PyErr_SetString(PyExc_RuntimeError, "unknown error"); return NULL;} 
%End

QImage* remove_borders(const QImage &image, double fuzz);
%MethodCode
        IMAGEOPS_PREFIX
			sipRes = new QImage(remove_borders(*a0, a1));
        IMAGEOPS_SUFFIX
%End

QImage* grayscale(const QImage &image);
%MethodCode
        IMAGEOPS_PREFIX
			sipRes = new QImage(grayscale(*a0));
        IMAGEOPS_SUFFIX
%End

QImage gaussian_sharpen(const QImage &img, const float radius, const float sigma, const bool high_quality=true);
%MethodCode
        IMAGEOPS_PREFIX
			sipRes = new QImage(gaussian_sharpen(*a0, a1, a2, a3));
        IMAGEOPS_SUFFIX
%End

QImage gaussian_blur(const QImage &img, const float radius, const float sigma);
%MethodCode
        IMAGEOPS_PREFIX
			sipRes = new QImage(gaussian_blur(*a0, a1, a2));
        IMAGEOPS_SUFFIX
%End
