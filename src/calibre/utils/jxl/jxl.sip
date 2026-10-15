//Define the SIP wrapper to the JPEG-XL image format plugin
//Author - Kovid Goyal <kovid@kovidgoyal.net>

%Module(name=jxl)

%Import QtCore/QtCoremod.sip
%Import QtGui/QtGuimod.sip

%ModuleCode
#include <jxl_plugin.h>
%End

// Importing this module is what makes Qt able to read and write JPEG-XL
// images, the registration happens when the shared object is loaded. This
// function simply verifies that it worked.
bool register_jxl_image_format();
%MethodCode
        sipRes = register_jxl_image_format();
%End

bool is_jxl(const char *data /Array/, size_t len /ArraySize/);
%MethodCode
        sipRes = is_jxl(a0, a1);
%End

%InitialisationCode
        register_jxl_image_format();
%End
