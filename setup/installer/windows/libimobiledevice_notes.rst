Notes on building libiMobileDevice for Windows
=========================================================

The following notes are intended to work in the calibre build environment described in
windows/notes.rst. In particular, third party dependencies like libxml2 and
openssl are assumed to have been built as described there.

1. Get source files, set up VS project
2. Build libcnary
3. Build libplist
4. Build libusbmuxd
5. Build libgen
6. Build libimobiledevice
7. Finished

Get source files, set up VS project
-------------------------------------

Follow these steps::
    mkdir $SW/private/imobiledevice && cd $SW/private/imobiledevice
    git clone https://github.com/Polyfun/libimobiledevice-windows.git
    cd libimobiledevice-windows && cp -r libcnary libgen vendors/include .. && cd ..
    git clone https://github.com/Polyfun/libplist.git
    git clone https://github.com/Polyfun/libusbmuxd.git
    git clone https://github.com/Polyfun/libimobiledevice.git

Create a new VS 2008 Project
    - File|New|Project…
    - Visual C++: Win32
    - Template: Win32Project
    - Name: imobiledevice
    - Location: Choose $SW/private
    - Solution: (Uncheck the create directory for solution checkbox)
    - Click OK
    - Next screen, select Application Settings tab
    - Application type: DLL 
    - Additional options: Empty project
    - Click Finish

In the tool bar Solution Configurations dropdown, select Release.
In the tool bar Solution Platforms dropdown, select Win32.
(For 64 bit choose new configuration and create x64 with properties copied from
win32).


Build libcnary
-------------------------

In VS Solution Explorer, right-click "Solution 'imobiledevice'", then click
Add|Existing Project and choose libcnary.vcproj

In VS Solution Explorer, select the libcnary project, Right click->Build


Build libplist
---------------------

In VS Solution Explorer, right-click Solution 'imobiledevice', then click
Add|Existing Project and select libplist.vcproj

In VS Solution Explorer, select the libplist project, right
click->Properties-Configuration
    - Properties|Configuration Properties|C/C++:
        General|Additional Include Directories:
        $(SolutionDir)\include
        $SW\include\libxml2 (if it exists)
        $SW\include (make sure this is last in the list)
    - Properties -> Linker -> General -> Additional Library directories: $SW/lib (for libxml2.lib)

Project Dependencies:
    Depends on: libcnary

Right-click libplist, Build. Should build with 0 errors (there will be warnings
about datatype conversion for the 64 bit build)

Build libusbmuxd
----------------------

In VS Solution Explorer, right-click Solution 'imobiledevice', then click
Add|Existing Project -> libusbmuxd.vcproj

In VS Solution Explorer, select the libusbmuxd project, then right
click->Properties->Configuration.
    - Properties|Configuration Properties|C/C++:
        General|Additional Include Directories:
            $(SolutionDir)\include
            $(SolutionDir)\libplist\include

Project Dependencies:
    Depends on: libplist

Right-click libusbmuxd, Build. Should build with 0 errors, many warnings

Build libgen
-----------------------

In VS Solution Explorer, right-click Solution 'imobiledevice', then click
Add|Existing Project -> libgen.vcpro

Right-click libgen, Build. Should build with 0 errors, 0 warnings.

Build libimobiledevice
----------------------------

In VS Solution Explorer, right-click Solution 'imobiledevice', then click
Add|Existing Project -> libimobiledevice.vcproj
    - Properties|Configuration Properties|C/C++:
        General|Additional Include Directories:
        $(ProjectDir)\include
        $(SolutionDir)\include
        $(SolutionDir)\libplist\include
        $(SolutionDir)\libgen
        $(SolutionDir)\libusbmuxd
        $SW\private\openssl\include
    - Properties -> Linker -> General -> Additional library directories:
        $SW\private\openssl\lib
        $(OutDir)
    - Properties -> Build Events ->Post Build Event -> Remove the post build event (we will copy the dlls manually)

Right click-> Project Dependencies:
    libcnary
    libgen
    libplist
    libusbmuxd

Right-click libimobiledevice, Build.
    0 errors, many warnings.

Copy the DLLs
-----------------

Run::
    cp `find Release -name '*.dll'` ~/sw/bin/

