Notes on setting up the windows development environment
========================================================

Overview
----------

calibre and all its dependencies are compiled using Visual Studio 2015. All the
following instructions must be run in a visual studio command prompt (the
various commands use unix notation, so if you want to use them directly, you
have to setup cygwin, as described below).

calibre contains build script to automate the building of the calibre
installer. These scripts make certain assumptions about where dependencies are
installed. Your best best is to setup a VM and replicate the paths mentioned
below exactly.

Microsoft Visual Studio 
----------------------------------------

1) Install Visual Studio 2015 Community Edition **Update 1**
2) If you are building 64bit, remember to use the 64bit version of the visual
studio command prompt.

Cygwin
------------

This is needed for automation of the build process, and the ease of use of the
unix shell (zsh). Install it by running: https://www.cygwin.com/setup-x86_64.exe

In cygwin, install vim, dos2unix, rsync, openssh, unzip, wget, make, zsh, bash-completion, curl

Run::
    mkdir -p ~/sw/bin ~/sw/sources ~/sw/build ~/sw/lib ~/sw/private ~/sw/include

Edit /etc/passwd and replace all occurrences of /bin/bash with /bin/zsh

Run::
    
Create a file ~/bin/winenv with the following::

    cat << '    EOF' |  sed -e 's/^ *//' > ~/bin/winenv
    #!pycygrun
    import os, subprocess, sys
    env = os.environ.copy()
    # Ensure windows based exes are used in preference to cygwin ones
    parts = filter(lambda x: '\\cygwin64\\' not in x or '\\cygwin64\\home\\kovid\\sw\\' in x, env['PATH'].split(os.pathsep))
    env['PATH'] = os.pathsep.join(parts)
    args = sys.argv[1:]
    if args[0].startswith('.'): args[0] = os.path.abspath(args[0])
    p = subprocess.Popen(args, env=env)
    raise SystemExit(p.wait())
    EOF
    chmod +x ~/bin/winenv

The following is only needed for automation (setting up ssh access to the
windows machine).

In order to build debug builds (.pdb files) and sign files, you have to be able
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

Get the calibre source code
------------------------------

Get the calibre source code::
    mkdir -p ~/build && rm -rf calibre && cd ~/build && curl -L http://code.calibre-ebook.com/dist/src | tar xvJ && mv calibre-* calibre

Build python
----------------

Get nasm.exe (needed for openssl and libjpeg-turbo) from
http://www.nasm.us/pub/nasm/releasebuilds/2.11/win32/nasm-2.11-win32.zip
and put it in ~/sw/bin (which must be in PATH)::
    chmod +x ~/sw/bin/nasm.exe

Install tortoise svn from http://tortoisesvn.net/downloads.html
Install git for windows from https://git-scm.com/download/win

Get a customized version of python that compiles with VS 2015, like this::

    git clone --depth 1 https://github.com/kovidgoyal/cpython.git && cd cpython && git checkout 2.7

PlatformToolset below corresponds to the version of Visual Studio, here 2015 (14.0)
We create externals/nasm-2.11.06 below so that the python build script does not
try to download its own nasm instead using the one we installed above (the python
build script fails to mark its nasm as executable, and therefore errors out)

First run::
    echo 'set PROGRAMFILES(x86)=%PROGRAMFILES% (x86)' > run.bat && \
    echo 'PCbuild\\build.bat -e --no-tkinter -c Release -p %1 -t Build "/p:PlatformToolset=v140"' >> run.bat && \
    mkdir -p externals/nasm-2.11.06 && \
    chmod +x run.bat 

For 64-bit ::

    ./run.bat x64 || echo '\n\nPython compilation failed!'
    ./PCbuild/amd64/python.exe Lib/test/regrtest.py -u network,cpu,subprocess,urlfetch
    ./PCbuild/amd64/python.exe /cygwin64/home/kovid/build/calibre/setup/installer/windows/install_python.py /cygwin64/home/kovid/sw/private

For 32-bit::

    ./run.bat Win32 || echo '\n\nPython compilation failed!'
    ./PCbuild/python.exe Lib/test/regrtest.py -u network,cpu,subprocess,urlfetch
    ./PCbuild/python.exe /cygwin64/home/kovid/build/calibre/setup/installer/windows/install_python.py /cygwin64/home/kovid/sw/private


Make sure ~/sw/private/python is in your PATH

Basic dependencies
--------------------

Install cmake, WiX (WiX is used to generate the .msi installer)

You have to 

Set CMAKE_PREFIX_PATH environment variable to C:\cygwin64\home\kovid\sw

This is where all dependencies will be installed.

Run::
    python /cygwin64/home/kovid/build/calibre/setup/vcvars.py > ~/.vcvars

Add `source ~/.vcvars` to `~/.zshenv`
This will allow you to use the Visual Studio tools in the cygwin shell.

Install perl and ruby (needed to build openssl and qt):
Perl: http://www.activestate.com/activeperl
Ruby: http://rubyinstaller.org/

Put both perl.exe and ruby.exe in the PATH


setuptools
--------------
Download and extract setuptools from https://pypi.python.org/pypi/setuptools/
Run::
    cd ~/sw/build/setuptools-* && sed -i.bak 's/zip_safe\s*=\s*True/zip_safe=False/' setup.py && \
    python setup.py install

Miscellaneous python packages
--------------------------------------

Run::
    ~/sw/private/python/Scripts/easy_install.exe --always-unzip -U python-dateutil dnspython mechanize pygments pyreadline pycrypto 
    # cssutils install has a harmless error, so do it separately
    ~/sw/private/python/Scripts/easy_install.exe --always-unzip -U cssutils

pywin32
----------

Run::

    git clone --depth 1 https://github.com/kovidgoyal/pywin32.git
    chmod +x swig/swig.exe
    export plat= win32 or win-amd64
    python setup.py -q build --plat-name=$plat; && \
    python setup.py -q build --plat-name=$plat; && \
    python setup.py -q build --plat-name=$plat; && \
    python setup.py -q build --plat-name=$plat; && \
    python setup.py -q build --plat-name=$plat; && \
    python setup.py -q build --plat-name=$plat;
    # Do this repeatedly until you stop getting .manifest file errors
    python setup.py -q install
    rm ~/sw/private/python/Lib/site-packages/*.chm

SQLite
---------

https://www.sqlite.org/download.html

Put sqlite3*.h from the sqlite windows amalgamation in ~/sw/include

APSW
-----

https://github.com/rogerbinns/apsw/releases

python setup.py fetch --all --missing-checksum-ok build --enable-all-extensions install test

OpenSSL
--------

https://www.openssl.org/source/

For 32-bit::
    winenv perl Configure VC-WIN32 enable-static-engine --prefix=C:/cygwin64/home/kovid/sw/private/openssl && \
    winenv ms\\do_ms.bat && winenv nmake -f ms\\ntdll.mak && winenv nmake -f ms\\ntdll.mak test && winenv nmake -f ms\\ntdll.mak install

For 64-bit::
    winenv perl Configure VC-WIN64A enable-static-engine --prefix=C:/cygwin64/home/kovid/sw/private/openssl && \
    winenv ms\\do_win64a.bat && winenv nmake -f ms\\ntdll.mak && winenv nmake -f ms\\ntdll.mak test && winenv nmake -f ms\\ntdll.mak install

ICU
-------

Download the win32 *source* .zip from http://www.icu-project.org/download

Extract to `~/sw/private`

The following *must be run in the VS Command Prompt*, not the cygwin shell

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
    winenv nmake -f win32/Makefile.msc && \
    nmake -f win32/Makefile.msc test && \
    cp zlib1.dll* ~/sw/bin && cp zlib.lib zdll.* ~/sw/lib/ && cp zconf.h zlib.h ~/sw/include/

jpeg-8
-------

Get the source code from: https://github.com/libjpeg-turbo/libjpeg-turbo/releases
Run::
    chmod +x cmakescripts/* && mkdir -p build && cd build && \
    cmake -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release -DWITH_JPEG8=1 .. && \
    nmake && \
    cp sharedlib/jpeg8.dll* ~/sw/bin/ && cp sharedlib/jpeg.lib ~/sw/lib/ && cp jconfig.h ../jerror.h ../jpeglib.h ../jmorecfg.h ~/sw/include

libpng
---------

Download the libpng .zip source file from:
http://www.libpng.org/pub/png/libpng.html

Run::
    cmake -G "NMake Makefiles" -DPNG_SHARED=1 -DCMAKE_BUILD_TYPE=Release -DZLIB_INCLUDE_DIR=C:/cygwin64/home/kovid/sw/include -DZLIB_LIBRARY=C:/cygwin64/home/kovid/sw/lib/zdll.lib . && \
    nmake && cp libpng*.dll ~/sw/bin/ && cp libpng*.lib ~/sw/lib/ && cp pnglibconf.h png.h pngconf.h ~/sw/include/

freetype
-----------

Get the source from: http://download.savannah.gnu.org/releases/freetype/

The following will build freetype both as a static (freetype262MT.lib) and as a dynamic library (freetype.dll and freetype.lib)

Run::
    find . -name ftoption.h -exec sed -i.bak '/FT_BEGIN_HEADER/a #define FT_EXPORT(x) __declspec(dllexport) x\n#define FT_EXPORT_DEF(x) __declspec(dllexport) x' {} \;
    winenv devenv builds/windows/vc2010/freetype.sln /upgrade
    export PL=x64 (change to Win32 for 32 bit build)
    winenv msbuild.exe builds/windows/vc2010/freetype.sln /t:Build /p:Platform=$PL /p:Configuration="Release Multithreaded"
    rm -f ~/sw/lib/freetype*; cp ./objs/vc2010/$PL/freetype*MT.lib ~/sw/lib/ 
    rm -rf ~/sw/include/freetype2; cp -rf include ~/sw/include/freetype2 && rm -rf ~/sw/include/freetype2/internal
    sed -i.bak s/StaticLibrary/DynamicLibrary/ builds/windows/vc2010/freetype.vcxproj
    winenv msbuild.exe builds/windows/vc2010/freetype.sln /t:Build /p:Platform=$PL /p:Configuration="Release Multithreaded"
    rm -f ~/sw/bin/freetype*; cp ./objs/vc2010/$PL/freetype*MT.dll ~/sw/bin/ && cp ./objs/vc2010/$PL/freetype*MT.lib ~/sw/lib/freetype.lib 

expat
--------

Get from: http://sourceforge.net/projects/expat/files/expat/

Run::
    mkdir -p build && cd build && \
    cmake -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release .. && \
    nmake && \
    cp expat.dll ~/sw/bin/ && cp expat.lib ~/sw/lib/ && \
    cp ../lib/expat.h ../lib/expat_external.h ~/sw/include

libxml2
-------------

Get it from: ftp://xmlsoft.org/libxml2/

Run::
    cd win32 && \
    cscript.exe configure.js include=C:/cygwin64/home/kovid/sw/include lib=C:/cygwin64/home/kovid/sw/lib prefix=C:/cygwin64/home/kovid/sw zlib=yes iconv=no && \
    winenv nmake /f Makefile.msvc && \
    cd .. && \
    rm -rf ~/sw/include/libxml2; mkdir -p ~/sw/include/libxml2/libxml && cp include/libxml/*.h ~/sw/include/libxml2/libxml/ && \
    find . -type f \( -name "*.dll" -o -name "*.dll.manifest" \)  -exec cp "{}" ~/sw/bin/ \; && \
    find .  -name libxml2.lib -exec cp "{}" ~/sw/lib/ \;

libxslt
---------

Get it from: ftp://xmlsoft.org/libxml2/

Run::
    cd win32 && \
    cscript.exe configure.js include=C:/cygwin64/home/kovid/sw/include include=C:/cygwin64/home/kovid/sw/include/libxml2 lib=C:/cygwin64/home/kovid/sw/lib prefix=C:/cygwin64/home/kovid/sw zlib=yes iconv=no &&\
    sed -i 's/#define snprintf _snprintf//' ../libxslt/win32config.h && \
    find . -name 'Makefile*' -exec sed -i 's|/OPT:NOWIN98||' {} \; && \
    winenv nmake /f Makefile.msvc && \
    rm -rf ~/sw/include/libxslt; mkdir -p ~/sw/include/libxslt ~/sw/include/libexslt && \
    cd .. && \
    cp libxslt/*.h ~/sw/include/libxslt/ && cp libexslt/*.h ~/sw/include/libexslt/ && \
    find . -type f \( -name "*.dll" -o -name "*.dll.manifest" \)  -exec cp "{}" ~/sw/bin/ \; && \
    find .  -name 'lib*xslt.lib' -exec cp "{}" ~/sw/lib/ \;

lxml
------

Get the source from: http://pypi.python.org/pypi/lxml

Change the include dirs and lib dirs by editing setupinfo.py and changing the
library_dirs() function to return::

    return ['C:/cygwin64/home/kovid/sw/lib']

and the include_dirs() function to return::

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

http://poppler.freedesktop.org

Edit poppler/poppler-config.h.cmake removing the macro definition of fmax (it
is present in VS 2015 and the macro def causes errors)

Run::
    sed -i 's/#define snprintf _snprintf/#include <algorithm>/' config.h.cmake && \
    mkdir build && cd build && \
    cmake -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release -DENABLE_CPP=0 .. && \
    nmake && cp utils/*.exe* ~/sw/bin


podofo
----------

Download from http://podofo.sourceforge.net/download.html

Run::
    mkdir build && cd build && \
    cmake -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release -DWANT_LIB64=FALSE -DPODOFO_BUILD_SHARED=TRUE -DPODOFO_BUILD_STATIC=False -DFREETYPE_INCLUDE_DIR="C:/cygwin64/home/kovid/sw/include/freetype2"  .. && \
    nmake podofo_shared && \
    rm -rf ~/sw/include/podofo; mkdir ~/sw/include/podofo && cp podofo_config.h ~/sw/include/podofo && cp -r ../src/* ~/sw/include/podofo/ && \
    cp "`find . -name '*.dll'`" ~/sw/bin/ && cp "`find . -name '*.lib'`" ~/sw/lib/


netifaces
------------
https://pypi.python.org/pypi/netifaces

Run:: 
    python setup.py build && cp `find build/ -name '*.pyd'` ~/sw/private/python/Lib/site-packages/


psutil
--------
https://pypi.python.org/pypi/psutil

Run::

    python setup.py build && rm -rf  ~/sw/private/python/Lib/site-packages/psutil && cp -r build/lib.win*/psutil ~/sw/private/python/Lib/site-packages/

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
    winenv devenv ChmLib.dsw /upgrade

Then open ChmLib.sln in Visual Studio, change the configuration to Release
(Win32|x64) and build solution, this will generate a static library in
Release/ChmLib.lib

Qt
--------
Download Qt (5.5.1) sourcecode (.zip) from: http://download.qt-project.org/official_releases/qt/

    * Extract it to C:\qt (the default location for building $SW/build) does
      not work as Qt's build system generates paths that are too long for
      windows when used from there.

    * Make sure the folder containing the ICU dlls is in the PATH. ($SW/private/icu/source/lib)

    * Slim down Qt by not building various things we dont need. Edit
      :file:`qtwebkit/Tools/qmake/mkspecs/features/configure.prf` and remove
      build_webkit2. Edit qt.pro and comment out the addModule() lines for
      qtxmlpatterns, qtdeclarative, qtquickcontrols, qtfeedback,
      qtpim, qtwebsockets, qtwebchannel, qttools, qtwebkit-examples, qt3d,
      qt-canvas3d, qtgraphicaleffects, qtscript, qtquick1, qtdocgallery,
      qtwayland, qtenginio, qtwebengine, qtdoc. Change the addModule line for
      qtwebkit to depend only on qtbase and qtmultimedia. Remove qtdeclarative
      from all addModule() lines where is is an optional dependency.

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
+        searchOrder << (QFileInfo(qAppFileName()).path().replace(QLatin1Char('/'), QLatin1Char('\\')) + QString::fromLatin1("\\app\\DLLs\\"));
+        searchOrder << (QFileInfo(qAppFileName()).path().replace(QLatin1Char('/'), QLatin1Char('\\')) + QString::fromLatin1("\\DLLs\\"));
 #endif
     searchOrder << qSystemDirectory();
 
-no-plugin-manifests is needed so that loading the plugins does not fail looking for the CRT assembly

Now, run configure and make (we have to make sure the windows perl and not cygwin perl is used)::

    chmod +x configure.bat qtbase/configure.* gnuwin32/bin/*
    rm -rf build && mkdir build && cd build
    winenv ../configure.bat -prefix C:/cygwin64/home/kovid/sw/private/qt -ltcg -opensource -release -platform win32-msvc2015 -mp -confirm-license -nomake examples -nomake tests -no-plugin-manifests -icu -openssl -I C:/cygwin64/home/kovid/sw/private/openssl/include -L C:/cygwin64/home/kovid/sw/private/openssl/lib -I C:/cygwin64/home/kovid/sw/private/icu/source/common -I C:/cygwin64/home/kovid/sw/private/icu/source/i18n -L C:/cygwin64/home/kovid/sw/private/icu/source/lib -no-angle -opengl desktop
    PATH=/cygdrive/c/qt/gnuwin32/bin:$PATH winenv nmake
    rm -rf ~/sw/private/qt && nmake install

Add $SW/private/qt/bin to PATH

SIP
-----

Available from: http://www.riverbankcomputing.co.uk/software/sip/download ::

    python configure.py -p win32-msvc2015 && winenv nmake && nmake install

PyQt5
----------

Compiling instructions::

    rm -rf build && mkdir build && cd build
    winenv python ../configure.py -c -j5 --no-designer-plugin --no-qml-plugin --verbose --confirm-license
    winenv nmake && rm -rf ~/sw/private/python/Lib/site-packages/PyQt5 && nmake install

libplist
------------

Run::
    git clone --depth 1 https://github.com/kovidgoyal/libplist.git && \
    export PLAT=`python -c "import sys; sys.stdout.write('x64' if sys.maxsize > 2**32 else 'x86')"` && \
    cd libplist && winenv msbuild VisualStudio/libplist/libplist.sln /t:Build /p:Platform=$PLAT /p:Configuration="Release" && \
    cp VisualStudio/libplist/$PLAT/Release/libplist.dll ~/sw/bin && \
    cp VisualStudio/libplist/$PLAT/Release/libplist.lib ~/sw/lib && \
    cp -r include/plist ~/sw/include

libusbmuxd
---------------

Run::
    git clone --depth 1 https://github.com/kovidgoyal/libusbmuxd.git && \
    export PLAT=`python -c "import sys; sys.stdout.write('x64' if sys.maxsize > 2**32 else 'x86')"` && \
    cd libusbmuxd && winenv msbuild VisualStudio/libusbmuxd/libusbmuxd.sln /t:Build /p:Platform=$PLAT /p:Configuration="Release" && \ 
    cp VisualStudio/libusbmuxd/$PLAT/Release/libusbmuxd.dll ~/sw/bin && \
    cp VisualStudio/libusbmuxd/$PLAT/Release/libusbmuxd.lib ~/sw/lib && \
    cp include/*.h ~/sw/include

libimobiledevice
---------------------

Run::
    git clone --depth 1 https://github.com/kovidgoyal/libimobiledevice.git && \
    export PLAT=`python -c "import sys; sys.stdout.write('x64' if sys.maxsize > 2**32 else 'x86')"` && \
    cd libimobiledevice && winenv msbuild VisualStudio/libimobiledevice/libimobiledevice.sln /t:Build /p:Platform=$PLAT /p:Configuration="Release" && \ 
    cp VisualStudio/libimobiledevice/$PLAT/Release/libimobiledevice.dll ~/sw/bin 

optipng
----------
http://optipng.sourceforge.net/
Compiling instructions::

    sed -i.bak 's/\$</%s/' src/libpng/scripts/makefile.vcwin32 && \
    winenv nmake -f build/visualc.mk && \
    cp src/optipng/optipng.exe ~/sw/bin/optipng-calibre.exe

mozjpeg
----------
https://github.com/mozilla/mozjpeg/releases
Compiling instructions::

   mkdir -p build && cd build && \
   cmake -G "NMake Makefiles" -DCMAKE_BUILD_TYPE=Release -DWITH_TURBOJPEG:BOOL=FALSE .. && \
   nmake && \
   cp jpegtran-static.exe ~/sw/bin/jpegtran-calibre.exe && \
   cp cjpeg-static.exe ~/sw/bin/cjpeg-calibre.exe

calibre
---------

Take a linux calibre tree on which you have run the following command::

    python setup.py stage1

and copy it to windows.

Run::

    python setup.py build
    python setup.py win32_freeze

This will create the .msi in the dist directory.
