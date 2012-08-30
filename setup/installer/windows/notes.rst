Notes on setting up the windows development environment
========================================================

Overview
----------

calibre and all its dependencies are compiled using Visual Studio 2008 express edition (free from MS). All the following instructions must be run in a visual studio command prompt unless otherwise noted.

calibre contains build script to automate the building of the calibre installer. These scripts make certain assumptions about where dependencies are installed. Your best best is to setup a VM and replicate the paths mentioned below exactly.

Basic dependencies
--------------------

Install cygwin and setup sshd (optional). Used to enable automation of the calibre build VM from linux, not needed if you are building manually.

Install MS Visual Studio 2008, cmake, python and WiX.

Set CMAKE_PREFIX_PATH environment variable to C:\cygwin\home\kovid\sw

This is where all dependencies will be installed.

Add C:\Python27\Scripts and C:\Python27 to PATH 

Edit mimetypes.py in C:\Python27\Lib and set _winreg = None to prevent reading of mimetypes from the windows registry

Install setuptools from http://pypi.python.org/pypi/setuptools
If there are no windows binaries already compiled for the version of python you are using then download the source and run the following command in the folder where the source has been unpacked::

     python setup.py install

Run the following command to install python dependencies::

    easy_install --always-unzip -U mechanize pyreadline python-dateutil dnspython cssutils clientform pycrypto

Install BeautifulSoup 3.0.x manually into site-packages (3.1.x parses broken HTML very poorly)

Install pywin32 and edit win32com\__init__.py setting _frozen = True and
__gen_path__ to a temp dir (otherwise it tries to set it to a dir in the install tree which leads to permission errors)
Note that you should use::

    import tempfile
    __gen_path__ = os.path.join(
                            tempfile.gettempdir(), "gen_py",
                            "%d.%d" % (sys.version_info[0], sys.version_info[1]))

Use gettempdir instead of the win32 api method as gettempdir returns a temp dir that is guaranteed to actually work.


Also edit win32com\client\gencache.py and change the except IOError on line 57 to catch all exceptions.

SQLite
---------

Put sqlite3*.h from the sqlite windows amlgamation in ~/sw/include

APSW
-----

Download source from http://code.google.com/p/apsw/downloads/list and run in visual studio prompt

python setup.py fetch --all build --missing-checksum-ok --enable-all-extensions install test

OpenSSL
--------

First install ActiveState Perl if you dont already have perl in windows
Download and untar the openssl tarball, follow the instructions in INSTALL.W32 (use no-asm)
to install use prefix q:\openssl

perl Configure VC-WIN32 no-asm enable-static-engine --prefix=Q:/openssl
ms\do_ms.bat
nmake -f ms\ntdll.mak
nmake -f ms\ntdll.mak test
nmake -f ms\ntdll.mak install

Qt
--------

Extract Qt sourcecode to C:\Qt\4.x.x. 

Qt uses its own routine to locate and load "system libraries" including the openssl libraries needed for "Get Books". This means that we have to apply the following patch to have Qt load the openssl libraries bundled with calibre:


--- src/corelib/plugin/qsystemlibrary.cpp	2011-02-22 05:04:00.000000000 -0700
+++ src/corelib/plugin/qsystemlibrary.cpp	2011-04-25 20:53:13.635247466 -0600
@@ -110,7 +110,7 @@ HINSTANCE QSystemLibrary::load(const wch
 
 #if !defined(QT_BOOTSTRAPPED)
     if (!onlySystemDirectory)
-        searchOrder << QFileInfo(qAppFileName()).path();
+        searchOrder << (QFileInfo(qAppFileName()).path().replace(QLatin1Char('/'), QLatin1Char('\\')) + QString::fromLatin1("\\DLLs\\"));
 #endif
     searchOrder << qSystemDirectory();
 

Now, run configure and make::

-no-plugin-manifests is needed so that loading the plugins does not fail looking for the CRT assembly

    configure -ltcg -opensource -release -qt-zlib -qt-libmng -qt-libpng -qt-libtiff -qt-libjpeg -release -platform win32-msvc2008 -no-qt3support -webkit -xmlpatterns -no-phonon -no-style-plastique -no-style-cleanlooks -no-style-motif -no-style-cde -no-declarative -no-scripttools -no-audio-backend -no-multimedia -no-dbus -no-openvg -no-opengl -no-qt3support -confirm-license -nomake examples -nomake demos -nomake docs -no-plugin-manifests -openssl -I Q:\openssl\include -L Q:\openssl\lib && nmake

Add the path to the bin folder inside the Qt dir to your system PATH.

SIP
-----

Available from: http://www.riverbankcomputing.co.uk/software/sip/download ::

    python configure.py -p win32-msvc2008
    nmake
    nmake install

PyQt4
----------

Compiling instructions::

    python configure.py -c -j5 -e QtCore -e QtGui -e QtSvg -e QtNetwork -e QtWebKit -e QtXmlPatterns --verbose --confirm-license
    nmake
    nmake install

Python Imaging Library
------------------------

Install as normal using installer at http://www.lfd.uci.edu/~gohlke/pythonlibs/

Test it on the target system with

calibre-debug -c "import _imaging, _imagingmath, _imagingft, _imagingcms"

ICU
-------

Download the win32 source .zip from http://www.icu-project.org/download

Extract to q:\icu

Add Q:\icu\bin to PATH and reboot

In a Visual Studio Command Prompt
cd to <ICU>\source
Run set PATH=%PATH%;c:\cygwin\bin
Run dos2unix on configure and runConfigureICU

Run bash ./runConfigureICU Cygwin/MSVC

Run make (note that you must have GNU make installed in cygwin)

Optionally run make check

Libunrar
----------

http://www.rarlab.com/rar/UnRARDLL.exe install and add C:\Program Files\UnrarDLL to PATH

lxml
------

http://pypi.python.org/pypi/lxml

jpeg-7
-------

Copy:: 
    jconfig.vc to jconfig.h, makejsln.vc9 to jpeg.sln,
    makeasln.vc9 to apps.sln, makejvcp.vc9 to jpeg.vcproj,
    makecvcp.vc9 to cjpeg.vcproj, makedvcp.vc9 to djpeg.vcproj,
    maketvcp.vc9 to jpegtran.vcproj, makervcp.vc9 to rdjpgcom.vcproj, and
    makewvcp.vc9 to wrjpgcom.vcproj.  (Note that the renaming is critical!)

Load jpeg.sln in Visual Studio

Goto Project->Properties->General Properties and change Configuration Type to dll

Add 

#define USE_WINDOWS_MESSAGEBOX

to jconfig.h (this will cause error messages to show up in a box)

Change the definitions of GLOBAL and EXTERN in jmorecfg.h to
#define GLOBAL(type)        __declspec(dllexport) type
#define EXTERN(type)        extern __declspec(dllexport) type

cp build/jpeg-7/Release/jpeg.dll bin/
cp build/jpeg-7/Release/jpeg.lib build/jpeg-7/Release/jpeg.exp
cp build/jpeg-7/jerror.h build/jpeg-7/jpeglib.h build/jpeg-7/jconfig.h build/jpeg-7/jmorecfg.h include/

zlib
------

nmake -f win32/Makefile.msc
nmake -f win32/Makefile.msc test

cp zlib1.dll* ../../bin
cp zlib.lib zdll.* ../../lib
cp zconf.h zlib.h ../../include


libpng
---------

cp scripts/CMakelists.txt .
mkdir build
Run cmake-gui.exe with source directory . and build directory build
You will have to point to sw/lib/zdll.lib and sw/include for zlib
Also disable PNG_NO_STDIO and PNG_NO_CONSOLE_IO

Now open PNG.sln in VS2008
Set Build type to Release

cp build/libpng-1.2.40/build/Release/libpng12.dll bin/
cp build/libpng-1.2.40/build/Release/png12.* lib/
cp build/libpng-1.2.40/png.h build/libpng-1.2.40/pngconf.h include/

freetype
-----------

Edit *all copies* of the file ftoption.h and add to generate a .lib
and a correct dll

#define FT_EXPORT(return_type) __declspec(dllexport) return_type 
#define FT_EXPORT_DEF(return_type) __declspec(dllexport) return_type


VS 2008 .sln file is present, open it

Change active build type to release mutithreaded

Project->Properties->Configuration Properties 
change configuration type to dll

cp build/freetype-2.3.9/objs/release_mt/freetype.dll bin/

Now change configuration back to static for .lib
cp build/freetype-2.3.9/objs/win32/vc2008/freetype239MT.lib lib/
cp -rf build/freetype-2.3.9/include/* include/

expat
--------

Has a VC 6 project file expat.dsw

Set active build to Relase and change build type to dll

cp build/expat-2.0.1/win32/bin/Release/*.lib lib/
cp build/expat-2.0.1/win32/bin/Release/*.exp lib/
cp build/expat-2.0.1/win32/bin/Release/*.dll bin/
cp build/expat-2.0.1/lib/expat.h build/expat-2.0.1/lib/expat_external.h include/

libxml2
-------------

cd win32
cscript configure.js include=C:\cygwin\home\kovid\sw\include lib=C:\cygwin\home\sw\lib prefix=C:\cygwin\home\kovid\sw zlib=yes iconv=no
nmake /f Makefile.msvc
nmake /f Makefile.msvc install
mv lib/libxml2.dll bin/
cp ./build/libxml2-2.7.5/win32/bin.msvc/*.manifest bin/

kdewin32-msvc
----------------

Get it from http://www.winkde.org/pub/kde/ports/win32/repository/kdesupport/
mkdir build
Run cmake

Set build type to release and configuration to dll

Build

cp build/kdewin32-msvc-0.3.9/build/include/* include/
cp build/kdewin32-msvc-0.3.9/build/bin/Release/*.dll bin/
cp build/kdewin32-msvc-0.3.9/build/bin/Release/*.lib lib/
cp build/kdewin32-msvc-0.3.9/build/bin/Release/*.exp lib/
cp -r build/kdewin32-msvc-0.3.9/include/msvc/ include/
cp build/kdewin32-msvc-0.3.9/include/*.h include/

fontconfig
---------------

Get it from http://www.winkde.org/pub/kde/ports/win32/repository/win32libs/
mkdir build
Remove subdirectory test from the bottom of CMakeLists.txt
run cmake

Set build type to release and project config to dll
Right click on the fontconfig project and select properties. Add sw/include/msvc to the include paths
Build only fontconfig

cp build/fontconfig-msvc-2.4.2-3/build/src/Release/*.dll bin
cp build/fontconfig-msvc-2.4.2-3/build/src/Release/*.lib lib
cp build/fontconfig-msvc-2.4.2-3/build/src/Release/*.exp lib
cp -r build/fontconfig-msvc-2.4.2-3/fontconfig/ include/

Also install the etc files from the font-config-bin archive from kde win32libs
It contains correct fonts.conf etc.


poppler
-------------

In Cmake: disable GTK, Qt, OPenjpeg, cpp, lcms, gtk_tests, qt_tests. Enable qt4, jpeg, png and zlib

NOTE: poppler must be built as a static library, unless you build the qt4 bindings

cp build/utils/Release/*.exe ../../bin/


podofo
----------

Add the following three lines near the top of CMakeLists.txt
SET(WANT_LIB64 FALSE)
SET(PODOFO_BUILD_SHARED TRUE)
SET(PODOFO_BUILD_STATIC FALSE)

cp build/podofo-*/build/src/Release/podofo.dll bin/
cp build/podofo-*/build/src/Release/podofo.lib lib/
cp build/podofo-*/build/src/Release/podofo.exp lib/

cp build/podofo-*/build/podofo_config.h include/podofo/
cp -r build/podofo-*/src/* include/podofo/

You have to use >=0.9.1


ImageMagick
--------------

Get the source from: http://www.imagemagick.org/download/windows/ImageMagick-windows.zip

Edit VisualMagick/configure/configure.cpp to set

int projectType = MULTITHREADEDDLL;

Run configure.bat in a  visual studio command prompt

Run configure.exe generated by configure.bat

Edit magick/magick-config.h

Undefine ProvideDllMain and MAGICKCORE_X11_DELEGATE

Now open VisualMagick/VisualDynamicMT.sln set to Release
Remove the CORE_xlib, UTIL_Imdisplay and CORE_Magick++ projects.

F7 for build project, you will get one error due to the removal of xlib, ignore
it.

netifaces
------------

Download the source tarball from http://alastairs-place.net/projects/netifaces/

Rename netifaces.c to netifaces.cpp and make the same change in setup.py

Run 

python setup.py build
cp build/lib.win32-2.7/netifaces.pyd /cygdrive/c/Python27/Lib/site-packages/


calibre
---------

Take a linux calibre tree on which you have run the following command::

    python setup.py stage1

and copy it to windows.

Run::

    python setup.py build
    python setup.py win32_freeze

This will create the .msi in the dist directory.
