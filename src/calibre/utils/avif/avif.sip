//Define the SIP wrapper to the AVIF image format plugin
//Author - Kovid Goyal <kovid@kovidgoyal.net>

%Module(name=avif)

%Import QtCore/QtCoremod.sip
%Import QtGui/QtGuimod.sip

%ModuleCode
#include <avif_plugin.h>
%End

// Importing this module is what makes Qt able to read AVIF images, the
// registration happens when the shared object is loaded. This function simply
// verifies that it worked.
bool register_avif_image_format();
%MethodCode
        sipRes = register_avif_image_format();
%End

bool is_avif(const char *data /Array/, size_t len /ArraySize/);
%MethodCode
        sipRes = is_avif(a0, a1);
%End

%InitialisationCode
        register_avif_image_format();
%End
