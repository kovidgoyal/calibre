Notes on setting up the windows development environment
========================================================

Overview
----------

calibre and all its dependencies are compiled using Visual Studio 2008. All the
following instructions must be run in a visual studio command prompt (the
various commands use unix notation, so if you want to use them directly, you
have to setup cygwin).

calibre contains build script to automate the building of the calibre
installer. These scripts make certain assumptions about where dependencies are
installed. Your best best is to setup a VM and replicate the paths mentioned
below exactly.

Microsoft Visual Studio and Windows SDK
----------------------------------------

You have to use Visual Studio 2008 as that is the version Python 2.x works 
with.

You need Visual Studio 2008 Express Edition for 32-bit and Professional for 64
bit. 

1) Install Visual Studio
2) Install Visual Studio SP1 from http://www.microsoft.com/en-us/download/details.aspx?id=10986
   (First check if the version of VS 2008 you have is not already SP1)
3) Install The Windows SDK. You need to install a version that is built for VS
2008. Get it from here: http://www.microsoft.com/en-us/download/details.aspx?id=3138
4) If you are building 64bit, edit the properties of the Visual Studio command
prompt shortcut to pass "amd64" instead of "x86" to the vsvars.bat file so that
it uses the 64 bit tools.

I've read that it is possible to use the 64-bit compiler that comes with the
Windows SDK With VS 2008 Express Edition, but I can't be bothered figuring it
out. Just use the Professional Edition.

Cygwin
------------

This is needed for automation of the build process, and the ease of use of the
unix shell (bash).

Install, vim, rsync, openssh, unzip, wget, make at a minimum.

After installing python run::
    python setup/vcvars.py && echo 'source ~/.vcvars' >> ~/.bash_profile

To allow you to use the visual studio tools in the cygwin shell.

The following is only needed for automation (setting up ssh access to the
windows machine).

In order to build debug builds (.pdb files and sign files), you have to be able
to login as the normal user account with ssh. To do this, follow these steps:

    * Setup a password for your user account
    * Follow the steps here:
      http://pcsupport.about.com/od/windows7/ht/auto-logon-windows-7.htm or
      http://pcsupport.about.com/od/windowsxp/ht/auto-logon-xp.htm to allow the
      machine to bootup without having to enter the password
    * First clean out any existing cygwin ssh setup with::
        net stop sshd
        cygrunsrv -R sshd
        net user sshd /DELETE
        net user cyg_server /DELETE (delete any other cygwin users account you
        can list them with net user)
        rm -R /etc/ssh*
        mkpasswd -cl > /etc/passwd
        mkgroup --local > /etc/group
    * Assign the necessary rights to the normal user account::
        editrights.exe -a SeAssignPrimaryTokenPrivilege -u kovid
        editrights.exe -a SeCreateTokenPrivilege -u kovid
        editrights.exe -a SeTcbPrivilege -u kovid
        editrights.exe -a SeServiceLogonRight -u kovid
    * Run::
        ssh-host-config
      And answer (yes) to all questions. If it asks do you want to use a
      different user name, specify the name of your user account and enter
      username and password (it asks on Win 7 not on Win XP)
    * On Windows XP, I also had to run::
        passwd -R
      to allow sshd to use my normal user account even with public key
      authentication. See http://cygwin.com/cygwin-ug-net/ntsec.html for
      details. On Windows 7 this wasn't necessary for some reason.
    * Start sshd with::
        net start sshd
    * See http://www.kgx.net.nz/2010/03/cygwin-sshd-and-windows-7/ for details

Pass port 22 through Windows firewall. Create ~/.ssh/authorized_keys

Basic dependencies
--------------------

Install cmake, python, WiX (WiX is used to generate the .msi installer)

You have to 

Set CMAKE_PREFIX_PATH environment variable to C:\cygwin\home\kovid\sw

This is where all dependencies will be installed.

Add C:\Python27\Scripts and C:\Python27 to PATH 

Edit mimetypes.py in C:\Python27\Lib and set _winreg = None to prevent reading
of mimetypes from the windows registry

Python packages
------------------

Install setuptools from http://pypi.python.org/pypi/setuptools. Use the source
tarball. Edit setup.py and set zip_safe=False. Then run::

     python setup.py install

Run the following command to install python dependencies::

    easy_install --always-unzip -U mechanize pyreadline python-dateutil dnspython cssutils clientform pycrypto cssselect

Install pywin32 and edit win32com\__init__.py setting _frozen = True and
__gen_path__ to a temp dir (otherwise it tries to set it to a dir in the
install tree which leads to permission errors)
Note that you should use::

    import tempfile
    __gen_path__ = os.path.join(
                            tempfile.gettempdir(), "gen_py",
                            "%d.%d" % (sys.version_info[0], sys.version_info[1]))

Use gettempdir instead of the win32 api method as gettempdir returns a temp dir
that is guaranteed to actually work.

Also edit win32com\client\gencache.py and change the except IOError on line 57
to catch all exceptions.

SQLite
---------

Put sqlite3*.h from the sqlite windows amalgamation in ~/sw/include

APSW
-----

Download source from http://code.google.com/p/apsw/downloads/list and run in visual studio prompt

python setup.py fetch --all --missing-checksum-ok build --enable-all-extensions install test

OpenSSL
--------

First install ActiveState Perl if you dont already have perl in windows

Then, get nasm.exe from
http://www.nasm.us/pub/nasm/releasebuilds/2.05/nasm-2.05-win32.zip and put it
somewhere on your PATH (I chose ~/sw/bin)

Download and untar the openssl tarball, follow the instructions in INSTALL.(W32|W64)
to install use prefix q:\openssl

For 32-bit::
    perl Configure VC-WIN32 no-asm enable-static-engine --prefix=Q:/openssl
    ms\do_ms.bat
    nmake -f ms\ntdll.mak
    nmake -f ms\ntdll.mak test
    nmake -f ms\ntdll.mak install

For 64-bit::
    perl Configure VC-WIN64A no-asm enable-static-engine --prefix=C:/cygwin/home/kovid/sw/private/openssl
    ms\do_win64a
    nmake -f ms\ntdll.mak
    nmake -f ms\ntdll.mak test
    nmake -f ms\ntdll.mak install

Qt
--------
Download Qt sourcecode (.zip) from: http://qt-project.org/downloads
Extract Qt sourcecode to C:\Qt\current

Qt uses its own routine to locate and load "system libraries" including the
openssl libraries needed for "Get Books". This means that we have to apply the
following patch to have Qt load the openssl libraries bundled with calibre:


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

    ./configure.exe -ltcg -opensource -release -qt-zlib -qt-libmng -qt-libpng -qt-libtiff -qt-libjpeg -release -platform win32-msvc2008 -no-qt3support -webkit -xmlpatterns -no-phonon -no-style-plastique -no-style-cleanlooks -no-style-motif -no-style-cde -no-declarative -no-scripttools -no-audio-backend -no-multimedia -no-dbus -no-openvg -no-opengl -no-qt3support -confirm-license -nomake examples -nomake demos -nomake docs -nomake tools -no-plugin-manifests -openssl -I $OPENSSL_DIR/include -L $OPENSSL_DIR/lib && nmake

Add the path to the bin folder inside the Qt dir to your system PATH.

SIP
-----

Available from: http://www.riverbankcomputing.co.uk/software/sip/download ::

    python configure.py -p win32-msvc2008 && nmake && nmake install

PyQt4
----------

Compiling instructions::

    python configure.py -c -j5 -e QtCore -e QtGui -e QtSvg -e QtNetwork -e QtWebKit -e QtXmlPatterns --verbose --confirm-license
    nmake
    nmake install

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

zlib
------

Build with::
    nmake -f win32/Makefile.msc
    nmake -f win32/Makefile.msc test

    cp zlib1.dll* ../../bin
    cp zlib.lib zdll.* ../../lib
    cp zconf.h zlib.h ../../include

jpeg-8
-------

Get the source code from: http://sourceforge.net/projects/libjpeg-turbo/files/

Run::
    chmod +x cmakescripts/* && cd build 
    cmake -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release -DWITH_JPEG8=1 ..
    nmake
    cp sharedlib/jpeg8.dll* ~/sw/bin/
    cp sharedlib/jpeg.lib ~/sw/lib/
    cp jconfig.h ../jerror.h ../jpeglib.h ../jmorecfg.h ~/sw/include

libpng
---------

Download the libpng .zip source file from:
http://www.libpng.org/pub/png/libpng.html

Run::
    mkdir build && cd build
    cmake -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release -DZLIB_INCLUDE_DIR=C:/cygwin/home/kovid/sw/include -DZLIB_LIBRARY=C:/cygwin/home/kovid/sw/lib/zdll.lib ..
    nmake
    cp libpng*.dll ~/sw/bin/
    cp libpng*.lib ~/sw/lib/
    cp pnglibconf.h ../png.h ../pngconf.h ~/sw/include/

freetype
-----------

Get the .zip source from: http://download.savannah.gnu.org/releases/freetype/

Edit *all copies* of the file ftoption.h and add to generate a .lib
and a correct dll

#define FT_EXPORT(return_type) __declspec(dllexport) return_type 
#define FT_EXPORT_DEF(return_type) __declspec(dllexport) return_type


VS 2008 .sln file is present, open it

    * If you are doing x64 build, click the Win32 dropdown, select
      Configuration manager->Active solution platform -> New -> x64

    * Change active build type to release mutithreaded

    * Project->Properties->Configuration Properties change configuration type
      to dll and build solution

cp "`find . -name *.dll`" ~/sw/bin/
cp "`find . -name freetype.lib`" ~/sw/lib/

Now change configuration back to static for .lib and build solution
cp "`find . -name freetype*MT.lib`" ~/sw/lib/

cp build/freetype-2.3.9/objs/win32/vc2008/freetype239MT.lib lib/
cp -rf include/* ~/sw/include/

TODO: Test if this bloody thing actually works on 64 bit (apparently freetype
assumes sizeof(long) == sizeof(ptr) which is not true in Win64. See for
example: http://forum.openscenegraph.org/viewtopic.php?t=2880

expat
--------

Get from: http://sourceforge.net/projects/expat/files/expat/

Apparently expat requires stdint.h which VS 2008 does not have. So we get our
own.

Run::
    cd lib
    wget http://msinttypes.googlecode.com/svn/trunk/stdint.h
    mkdir build && cd build
    cmake -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release ..
    nmake
    cp expat.dll ~/sw/bin/ && cp expat.lib ~/sw/lib/
    cp ../lib/expat.h ../lib/expat_external.h ~/sw/include

libiconv
----------

Run::
    mkdir vs2008 && cd vs2008

Then follow these instructions:
http://www.codeproject.com/Articles/302012/How-to-Build-libiconv-with-Microsoft-Visual-Studio

Change the type to Release and config to x64 or Win32 and Build solution and
then::
    cp "`find . -name *.dll`" ~/sw/bin/
    cp "`find . -name *.dll.manifest`" ~/sw/bin/
    cp "`find . -name *.lib`" ~/sw/lib/iconv.lib
    cp "`find . -name iconv.h`" ~/sw/include/

Information for using a static version of libiconv is at the link above.

libxml2
-------------

Get it from: ftp://xmlsoft.org/libxml2/

Run::
    cd win32
    cscript.exe configure.js include=C:/cygwin/home/kovid/sw/include lib=C:/cygwin/home/kovid/sw/lib prefix=C:/cygwin/home/kovid/sw zlib=yes iconv=yes
    nmake /f Makefile.msvc
    mkdir -p ~/sw/include/libxml2/libxml
    cp include/libxml/*.h ~/sw/include/libxml2/libxml/
    find . -type f \( -name "*.dll" -o -name "*.dll.manifest" \)  -exec cp "{}" ~/sw/bin/ \;
    find .  -name libxml2.lib -exec cp "{}" ~/sw/lib/ \;

libxslt
---------

Get it from: ftp://xmlsoft.org/libxml2/

Run::
    cd win32
    cscript.exe configure.js include=C:/cygwin/home/kovid/sw/include include=C:/cygwin/home/kovid/sw/include/libxml2 lib=C:/cygwin/home/kovid/sw/lib prefix=C:/cygwin/home/kovid/sw zlib=yes iconv=yes
    nmake /f Makefile.msvc
    mkdir -p ~/sw/include/libxslt ~/sw/include/libexslt
    cp libxslt/*.h ~/sw/include/libxslt/
    cp libexslt/*.h ~/sw/include/libexslt/
    find . -type f \( -name "*.dll" -o -name "*.dll.manifest" \)  -exec cp "{}" ~/sw/bin/ \;
    find .  -name lib*xslt.lib -exec cp "{}" ~/sw/lib/ \;

lxml
------

Get the source from: http://pypi.python.org/pypi/lxml

Add the following to the top of setupoptions.py::
    if option == 'cflags':
        return ['-IC:/cygwin/home/kovid/sw/include/libxml2',
                '-IC:/cygwin/home/kovid/sw/include']
    else:
        return ['-LC:/cygwin/home/kovid/sw/lib'] 

Then, edit src/lxml/includes/etree_defs.h and change the section starting with
#ifndef LIBXML2_NEW_BUFFER
to
#ifdef LIBXML2_NEW_BUFFER
#  define xmlBufContent(buf) xmlBufferContent(buf)
#  define xmlBufLength(buf) xmlBufferLength(buf)
#endif

Run::
    python setup.py install

Python Imaging Library
------------------------

For 32-bit:
Install as normal using installer at http://www.lfd.uci.edu/~gohlke/pythonlibs/

For 64-bit:
Download from http://pypi.python.org/pypi/Pillow/
Edit setup.py setting the ROOT values, like this::

    SW = r'C:\cygwin\home\kovid\sw'
    JPEG_ROOT = ZLIB_ROOT = FREETYPE_ROOT = (SW+r'\lib', SW+r'\include')

Build and install with::
    python setup.py build
    python setup.py install

Note that the lcms module will not be built. PIL requires lcms-1.x but only
lcms-2.x can be compiled as a 64 bit library.

Test it on the target system with

calibre-debug -c "from PIL import Image; import _imaging, _imagingmath, _imagingft"

kdewin32-msvc
----------------

I dont think this is needed any more, I've left it here just in case I'm wrong.

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

poppler
-------------

mkdir build

Run the cmake GUI which will find the various dependencies automatically.
On 64 bit cmake might not let you choose Visual Studio 2008, in whcih case
leave the source field blank, click configure choose Visual Studio 2008 and
then enter the source field.

In Cmake: disable GTK, Qt, OPenjpeg, cpp, lcms, gtk_tests, qt_tests. Enable
jpeg, png and zlib::

    cp build/utils/Release/*.exe ../../bin/

podofo
----------

Download from http://podofo.sourceforge.net/download.html

Add the following three lines near the top of CMakeLists.txt
SET(WANT_LIB64 FALSE)
SET(PODOFO_BUILD_SHARED TRUE)
SET(PODOFO_BUILD_STATIC FALSE)

Run::
    cp "`find . -name *.dll`" ~/sw/bin/
    cp "`find . -name *.lib`" ~/sw/lib/
    mkdir ~/sw/include/podofo
    cp build/podofo_config.h ~/sw/include/podofo
    cp -r src/* ~/sw/include/podofo/


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

F7 for build solution, you will get one error due to the removal of xlib, ignore
it.

netifaces
------------

Download the source tarball from http://alastairs-place.net/projects/netifaces/

Rename netifaces.c to netifaces.cpp and make the same change in setup.py

Run:: 
    python setup.py build
    cp `find build/ -name *.pyd` /cygdrive/c/Python27/Lib/site-packages/


psutil
--------

Download the source tarball

Run

Python setup.py build
cp -r build/lib.win32-*/* /cygdrive/c/Python27/Lib/site-packages/

easylzma
----------

This is only needed to build the portable installer.

Get it from http://lloyd.github.com/easylzma/ (use the trunk version)

Run cmake and build the Visual Studio solution (generates CLI tools and dll and
static lib automatically)

chmlib
-------

Download the zip source code from: http://www.jedrea.com/chmlib/
Run::
    cd src && unzip ./ChmLib-ds6.zip
Then open ChmLib.dsw in Visual Studio, change the configuration to Release
(Win32|x64) and build solution, this will generate a static library in
Release/ChmLib.lib

libimobiledevice
------------------

See libimobiledevice_notes.rst

calibre
---------

Take a linux calibre tree on which you have run the following command::

    python setup.py stage1

and copy it to windows.

Run::

    python setup.py build
    python setup.py win32_freeze

This will create the .msi in the dist directory.
