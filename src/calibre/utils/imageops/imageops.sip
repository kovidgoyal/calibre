//Define the SIP wrapper to the imageops code
//Author - Kovid Goyal <kovid@kovidgoyal.net>

%Module(name=imageops, version=1)

%Import QtCore/QtCoremod.sip
%Import QtGui/QtGuimod.sip
%ModuleCode
#include <imageops.h>
%End

QImage* remove_borders(const QImage &image, double fuzz);
%MethodCode
		try {
			sipRes = remove_borders(*a0, a1);
			if (sipRes == NULL) return NULL;
		} catch (std::bad_alloc) { PyErr_NoMemory(); return NULL; }
%End
