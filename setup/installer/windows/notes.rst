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
4) If you are building 64bit, remember to use the 64bit version of the visual
studio command prompt.

I've read that it is possible to use the 64-bit compiler that comes with the
Windows SDK With VS 2008 Express Edition, but I can't be bothered figuring it
out. Just use the Professional Edition.

Cygwin
------------

This is needed for automation of the build process, and the ease of use of the
unix shell (bash).

Install vim, dos2unix, rsync, openssh, unzip, wget, make, zsh, bash-completion, curl at a minimum.

After installing python run::
    python setup/vcvars.py && echo 'source ~/.vcvars' >> ~/.zshrc

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

    * The following steps must all be run in an administrator cygwin shell

    * First clean out any existing cygwin ssh setup with::
        net stop sshd
        cygrunsrv -R sshd
        net user sshd /DELETE
        net user cyg_server /DELETE (delete any other cygwin users account you
        can list them with net user)
        rm -R /etc/ssh*
        mkpasswd -cl > /etc/passwd
        mkgroup --local > /etc/group
    * Assign the necessary rights to the normal user account (administrator
      cygwin command prompt needed - editrights is available in \cygwin\bin)::
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

Edit /cygdrive/c/Python27/Lib/mimetypes.py and set _winreg = None to prevent reading
of mimetypes from the windows registry

Python packages
------------------

Install setuptools from http://pypi.python.org/pypi/setuptools. Use the source
tarball. Edit setup.py and set zip_safe=False. Then run::

     python setup.py install

Run the following command to install python dependencies::

    easy_install --always-unzip -U mechanize python-dateutil dnspython cssutils clientform pycrypto cssselect

Install pyreadline from https://pypi.python.org/pypi/pyreadline/2.0

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

Download source from http://code.google.com/p/apsw/downloads/list and run 

python setup.py fetch --all --missing-checksum-ok build --enable-all-extensions install test

Build requirements
-------------------

Install perl and ruby (needed to build openssl and qt):
Perl: http://www.activestate.com/activeperl
Ruby: http://rubyinstaller.org/

Put both perl.exe and ruby.exe in the PATH

Get nasm.exe from (needed for openssl and libjpeg-turbo)
http://www.nasm.us/pub/nasm/releasebuilds/2.11/win32/nasm-2.11-win32.zip
and put it in ~/sw/bin (which must be in PATH)

OpenSSL
--------

Download and untar the openssl tarball.
To install use a private prefix: --prefix=C:/cygwin64/home/kovid/sw/private/openssl

The following *MUST BE RUN* in a Visual Studio Command prompt and not in a cygwin
environment.

For 32-bit::
    perl Configure VC-WIN32 no-asm enable-static-engine --prefix=C:/cygwin64/home/kovid/sw/private/openssl
    ms\do_ms.bat && nmake -f ms\ntdll.mak && nmake -f ms\ntdll.mak test && nmake -f ms\ntdll.mak install

For 64-bit::
    perl Configure VC-WIN64A no-asm enable-static-engine --prefix=C:/cygwin64/home/kovid/sw/private/openssl
    ms\do_win64a.bat && nmake -f ms\ntdll.mak && nmake -f ms\ntdll.mak test && nmake -f ms\ntdll.mak install

ICU
-------

Download the win32 *source* .zip from http://www.icu-project.org/download

Extract to C:\cygwin64\home\kovid\sw\private\icu

The following must be run in the VS Command Prompt, not the cygwin ssh shell

cd to <ICU>\source::

    set PATH=%PATH%;C:\cygwin64\bin
    dos2unix runConfigureICU
    bash ./runConfigureICU Cygwin/MSVC
    make

Make sure the folder containing the ICU dlls is in the PATH. ($SW/private/icu/source/lib)
This is needed for building Qt.

zlib
------

http://www.zlib.net/

Build with::
    nmake -f win32/Makefile.msc
    nmake -f win32/Makefile.msc test
    cp zlib1.dll* ~/sw/bin && cp zlib.lib zdll.* ~/sw/lib/ && cp zconf.h zlib.h ~/sw/include/

jpeg-8
-------

Get the source code from: http://sourceforge.net/projects/libjpeg-turbo/files/

Run::
    chmod +x cmakescripts/* && mkdir -p build && cd build 
    cmake -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release -DWITH_JPEG8=1 ..
    nmake
    cp sharedlib/jpeg8.dll* ~/sw/bin/ && cp sharedlib/jpeg.lib ~/sw/lib/ && cp jconfig.h ../jerror.h ../jpeglib.h ../jmorecfg.h ~/sw/include

libpng
---------

Download the libpng .zip source file from:
http://www.libpng.org/pub/png/libpng.html

Run::
    mkdir -p build && cd build
    cmake -G "NMake Makefiles" -DPNG_SHARED=1 -DCMAKE_BUILD_TYPE=Release -DZLIB_INCLUDE_DIR=C:/cygwin64/home/kovid/sw/include -DZLIB_LIBRARY=C:/cygwin64/home/kovid/sw/lib/zdll.lib ..
    nmake
    cp libpng*.dll ~/sw/bin/ && cp libpng*.lib ~/sw/lib/ && cp pnglibconf.h ../png.h ../pngconf.h ~/sw/include/

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

    * Change active build type to release multithreaded

    * Project->Properties->Configuration Properties change configuration type
      to dll and build solution

cp "`find . -name freetype.dll`" ~/sw/bin/ && cp "`find . -name freetype.lib`" ~/sw/lib/

Now change configuration back to static for .lib and build solution

cp "`find . -name 'freetype*MT.lib'`" ~/sw/lib/
cp -rf include ~/sw/include/freetype2 && rm -rf ~/sw/include/freetype2/internal

TODO: Test if this bloody thing actually works on 64 bit (apparently freetype
assumes sizeof(long) == sizeof(ptr) which is not true in Win64. See for
example: http://forum.openscenegraph.org/viewtopic.php?t=2880

expat
--------

Get from: http://sourceforge.net/projects/expat/files/expat/

Apparently expat requires stdint.h which VS 2008 does not have. So we get our
own.

Run::
    cd lib && wget http://msinttypes.googlecode.com/svn/trunk/stdint.h && cd ..
    mkdir -p build && cd build
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

NOTE: Built as MT rather than MD so no manifest

Change the type to Release and config to x64 or Win32 and Build solution and
then::
    cp "`find . -name '*.dll'`" ~/sw/bin/
    cp "`find . -name '*.lib'`" ~/sw/lib/iconv.lib
    cp "`find . -name iconv.h`" ~/sw/include/

Information for using a static version of libiconv is at the link above.

libxml2
-------------

Get it from: ftp://xmlsoft.org/libxml2/

Run::
    cd win32
    cscript.exe configure.js include=C:/cygwin64/home/kovid/sw/include lib=C:/cygwin64/home/kovid/sw/lib prefix=C:/cygwin64/home/kovid/sw zlib=yes iconv=yes
    nmake /f Makefile.msvc
    cd ..
    mkdir -p ~/sw/include/libxml2/libxml && cp include/libxml/*.h ~/sw/include/libxml2/libxml/
    find . -type f \( -name "*.dll" -o -name "*.dll.manifest" \)  -exec cp "{}" ~/sw/bin/ \;
    find .  -name libxml2.lib -exec cp "{}" ~/sw/lib/ \;

libxslt
---------

Get it from: ftp://xmlsoft.org/libxml2/

Run::
    cd win32
    cscript.exe configure.js include=C:/cygwin64/home/kovid/sw/include include=C:/cygwin64/home/kovid/sw/include/libxml2 lib=C:/cygwin64/home/kovid/sw/lib prefix=C:/cygwin64/home/kovid/sw zlib=yes iconv=yes
    nmake /f Makefile.msvc
    mkdir -p ~/sw/include/libxslt ~/sw/include/libexslt
    cd ..
    cp libxslt/*.h ~/sw/include/libxslt/
    cp libexslt/*.h ~/sw/include/libexslt/
    find . -type f \( -name "*.dll" -o -name "*.dll.manifest" \)  -exec cp "{}" ~/sw/bin/ \;
    find .  -name 'lib*xslt.lib' -exec cp "{}" ~/sw/lib/ \;

lxml
------

Get the source from: http://pypi.python.org/pypi/lxml

Change the include dirs and lib dirs by editing setupinfo.py and changing the
library_dirs() function to return::

    return ['C:/cygwin64/home/kovid/sw/lib']

and the include_dirs() function to return

    return ['C:/cygwin64/home/kovid/sw/include/libxml2', 'C:/cygwin64/home/kovid/sw/include']

Run::
    python setup.py install


Python Imaging Library
------------------------

Download from http://pypi.python.org/pypi/Pillow/
Edit setup.py setting the ROOT values, like this::

    SW = r'C:\cygwin64\home\kovid\sw'
    JPEG_ROOT = ZLIB_ROOT = FREETYPE_ROOT = (SW+r'\lib', SW+r'\include')

Set zip_safe=False

Build and install with::
    python setup.py install

poppler
-------------

mkdir build

Run the cmake GUI which will find the various dependencies automatically.
On 64 bit cmake might not let you choose Visual Studio 2008, in whcih case
leave the source field blank, click configure choose Visual Studio 2008 and
then enter the source field.

In cmake: disable GTK, Qt, openjpeg, cpp, lcms, gtk_tests, qt_tests. Enable
jpeg, png and zlib::

    cp build/utils/Release/*.exe ~/sw/bin

podofo
----------

Download from http://podofo.sourceforge.net/download.html

mkdir build

Add the following three lines near the top of CMakeLists.txt
SET(WANT_LIB64 FALSE)
SET(PODOFO_BUILD_SHARED TRUE)
SET(PODOFO_BUILD_STATIC FALSE)

PoDoFo's CMakeLists.txt is pretty bad. Run the cmake-gui and fill in values for
freetype2 and open ssl (choose any one .lib for the libcrypto variable, you
will have to fix it manually in Visual Studio later anyway). Then generate the
VisualStudio solution. In the solution. In the Solution got to
Project->Properties->Linker->Input and add the second ssl library. And in
C++->General add the openssl include dir.

Now build only the project podofo_shared (release mode)

Run::
    cp "`find . -name '*.dll'`" ~/sw/bin/
    cp "`find . -name '*.lib'`" ~/sw/lib/
    mkdir ~/sw/include/podofo
    cp build/podofo_config.h ~/sw/include/podofo
    cp -r src/* ~/sw/include/podofo/


ImageMagick
--------------

Get the source from: http://www.imagemagick.org/download/windows/ImageMagick-windows.zip
Unzip it and then run::
    chmod +x `find . -name '*.exe'`

Edit VisualMagick/configure/configure.cpp to set

int projectType = MULTITHREADEDDLL;

Open configure.sln and build it to create configure.exe

Run configure.exe set 32/64 bit disable X11 and OpenMPI and click the Edit
magick-baseconfig.h button

Undefine ProvideDllMain 

Now open VisualMagick/VisualDynamicMT.sln set to Release

Remove the UTIL_IMdisplay and CORE_Magick++ projects.

F7 for build solution.

netifaces
------------

Download the source tarball from http://alastairs-place.net/projects/netifaces/

Run:: 
    python setup.py build
    cp `find build/ -name '*.pyd'` /cygdrive/c/Python27/Lib/site-packages/


psutil
--------

Download the source tarball

Run

Python setup.py build
cp -r build/lib.win*/* /cygdrive/c/Python27/Lib/site-packages/

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
    cd src && unzip ../ChmLib-ds6.zip
Then open ChmLib.dsw in Visual Studio, change the configuration to Release
(Win32|x64) and build solution, this will generate a static library in
Release/ChmLib.lib

Qt
--------
Download Qt sourcecode (.zip) from: http://download.qt-project.org/official_releases/qt/

    * Extract it to C:\qt (the default location for building $SW/build) does
      not work as Qt's build system generates paths that are too long for
      windows when used from there.

    * Make sure the folder containing the ICU dlls is in the PATH. ($SW/private/icu/source/lib)

    * Edit qtwinextras/src/winextras/winshobjidl_p.h and comment out the
      declaration of SHARDAPPIDINFOLINK (just replace the containing ifdef with
      #if 0). This struct is already defined in the header files from the
      windows sdk and this redefinition will cause a compiler error.

    * VS 2008 does not have stdint.h which WebKit needs, so run the following::
        wget -O qtwebkit/Source/ThirdParty/leveldb/include/stdint.h 'http://msinttypes.googlecode.com/svn/trunk/stdint.h'
        cp qtwebkit/Source/ThirdParty/leveldb/include/stdint.h qtwebkit/Source/JavaScriptCore/os-win32

    * Slim down Qt by not building various things we dont need. Edit
      :file:`qtwebkit/Tools/qmake/mkspecs/features/configure.prf` and remove
      build_webkit2. Edit qt.pro and comment out the addModule() lines for
      qtxmlpatterns, qtdeclarative, qtquick1, qtwebsockets. Change the
      addModule line for qtwebkit to depend on qtbase instead of qtdeclarative.

    * Qt uses its own routine to locate and load "system libraries" including
      the openssl libraries needed for "Get Books". This means that we have to
      apply the following patch to have Qt load the openssl libraries bundled
      with calibre:

--- qtbase/src/corelib/plugin/qsystemlibrary.cpp	2011-02-22 05:04:00.000000000 -0700
+++ qtbase/src/corelib/plugin/qsystemlibrary.cpp	2011-04-25 20:53:13.635247466 -0600
@@ -110,7 +110,7 @@ HINSTANCE QSystemLibrary::load(const wch
 
 #if !defined(QT_BOOTSTRAPPED)
     if (!onlySystemDirectory)
-        searchOrder << QFileInfo(qAppFileName()).path();
+        searchOrder << (QFileInfo(qAppFileName()).path().replace(QLatin1Char('/'), QLatin1Char('\\')) + QString::fromLatin1("\\DLLs\\"));
 #endif
     searchOrder << qSystemDirectory();
 
-no-plugin-manifests is needed so that loading the plugins does not fail looking for the CRT assembly

Now, run configure and make (we have to make sure the windows perl and not cygwin perl is used)::

    chmod +x configure.bat qtbase/configure.* gnuwin32/bin/*
    rm -rf build && mkdir -p build && cd build
    PATH=`ls -d /cygdrive/c/Perl*/bin`:$PATH ../configure.bat -prefix $SW/private/qt -ltcg -opensource -release -platform win32-msvc2008 -mp -confirm-license -nomake examples -nomake tests -no-plugin-manifests -icu -openssl -I $SW/private/openssl/include -L $SW/private/openssl/lib -I $SW/private/icu/source/common -I $SW/private/icu/source/i18n -L $SW/private/icu/source/lib -no-angle -opengl desktop
    PATH=`ls -d /cygdrive/c/Perl*/bin`:/cygdrive/c/qt/gnuwin32/bin:$PATH nmake
    rm -rf $SW/private/qt && nmake install

Add $SW/private/qt/bin to PATH

SIP
-----

Available from: http://www.riverbankcomputing.co.uk/software/sip/download ::

    python configure.py -p win32-msvc2008 && nmake && nmake install

PyQt5
----------

Compiling instructions::

    rm -rf build && mkdir build && cd build
    python ../configure.py -c -j5 --no-designer-plugin --no-qml-plugin --verbose --confirm-license
    nmake && rm -rf /cygdrive/c/Python27/Lib/site-packages/PyQt5 && nmake install


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
