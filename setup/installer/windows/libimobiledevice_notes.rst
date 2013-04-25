Notes on building libiMobileDevice for Windows
=========================================================

1. Get source files, set up VS project
2. Build libcnary
3. Build libgen
4. Build libplist
5. Build libusbmuxd
6. Build libimobiledevice
7. Exporting libimobiledevice entry points
8. Finished

Get source files, set up VS project
-------------------------------------

Starting with source downloaded from https://github.com/storoj/libimobiledevice-win32

Now create a new directory in which we will work::
    mkdir imobiledevice
    cp -r libcnary libgen vendors/include libimobiledevice libplist libusbmuxd imobiledevice
    cd imobiledevice
    rm `find . -name '*.props'`
    rm `find . -name *.vcxproj*`
    rm `find . -name *.txt`
    cd ..
    mv imobiledevice ~/sw/private/

In include/unistd.h, comment out line 11::

    // #include <getopt.h> /* getopt from: http://www.pwilson.net/sample.html.

Create a new VS 2008 Project
    - File|New|Project…
    - Visual C++: Win32
    - Template: Win32Project
    - Name: imobiledevice
    - Location: Choose ~/sw/private
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

In VS Solution Explorer, right-click Solution 'imobiledevice', then click
Add|New Project.
    - Name: libcnary
    - Location: Add \imobiledevice to the end of the default location
    - Visual C++: Win32, Template: Win32 Project
    - Click OK
    - Application Settings: Static library (not using precompiled headers)
    - Click Finish

In VS Solution Explorer, select the libcnary project, Project->Show All files.
    - Right-click the include folder, select 'Include In Project'.
    - Select all the .c files, right click, select 'Include In Project'
    - Select all the .c files, right click -> Properties -> C/C++ -> Advanced -> Compile as C++ code
    - Properties|Configuration Properties|C/C++:
        General|Additional Include Directories:
        "$(ProjectDir)\include"
    - If 64bits, then Right click->Properties->Configuration Manager change
      Win32 to x64 for the libcnary project and check the Build checkbox
    - Right-click libcnary, Build. Should build with 0 errors, 0 warnings.


Build libplist
---------------------

In VS Solution Explorer, right-click Solution 'imobiledevice', then click
Add|New Project.
    - Name: libplist
    - Visual C++: Win32, Template: Win32 Project
    - Location: Add \imobiledevice to the end of the default location
    - Click OK
    - Application Settings: DLL (Empty project)
    - Click Finish

In VS Solution Explorer, select the libplist project, then click the 'Show all files'
button.
    - Right-click the include folder, select Include In Project
    - Right-click the src folder, select Include In Project
    - Set 7 C files to compile as C++
        Advanced|Compile As: Compile as C++ Code (/TP)
        base64.c, bplist.c, bytearray.c, hashtable.c, plist.c, ptarray.c, xplist.c
    - Properties|Configuration Properties|C/C++:
        General|Additional Include Directories:
        $(ProjectDir)\include
        $(SolutionDir)\include
        $(SolutionDir)\libcnary\include
        $SW\include\libxml2 (if it exists)
        $SW\include (make sure this is last in the list)
    - Properties|C/C++|Preprocessor
        Preprocessor Definitions: Add the following items
        __STDC_FORMAT_MACROS
        plist_EXPORTS
    - Properties -> Linker -> General -> Additional Library directories: ~/sw/lib (for libxml2.lib)
    - Properties -> Linker -> Input -> Additional Dependencies: libxml2.lib
    - Project Dependencies:
        Depends on: libcnary
    - If 64bits, then Right click->Properties->Configuration Manager change
      Win32 to x64 for the libcnary project and check the Build checkbox
    - Right-click libplist, Build. Should build with 0 errors (there will be
      warnings about datatype conversion for the 64 bit build)

Build libusbmuxd
----------------------

In VS Solution Explorer, right-click Solution 'imobiledevice', then click
Add|New Project.
    - Name: libusbmuxd
    - Visual C++: Win32, Template: Win32 Project
    - Location: Add \imobiledevice to the end of the default location
    - Click OK
    - Application Settings: DLL (Empty project)
    - Click Finish

In VS Solution Explorer, select the libusbmuxd project, then click the 'Show all files'
button.
    - Select all 7 files, right-click, Include In Project.
    - Set 3 C files to compile as C++
        Advanced|Compile As: Compile as C++ Code (/TP)
        libusbmuxd.c, sock_stuff.c, utils.c
    - Properties|Configuration Properties|C/C++:
        General|Additional Include Directories:
        $(SolutionDir)\include
        $(SolutionDir)\libplist\include
    - Properties|Linker|Input|Additional Dependencies:
        ws2_32.lib
    - Properties|C/C++|Preprocessor
        Preprocessor Definitions: add 'HAVE_PLIST'
    - Project Dependencies:
        Depends on: libplist
    - Edit sock_stuff.c #227:
        fprintf(stderr, "%s: gethostbyname returned NULL address!\n",
					__FUNCTION__);
    - Edit libusbmuxd\usbmuxd.h, insert at #26:
        #ifdef LIBUSBMUXD_EXPORTS
        # define LIBUSBMUXD_API __declspec( dllexport )
        #else
        # define LIBUSBMUXD_API __declspec( dllimport )
        #endif
        Then, at each function, insert LIBUSBMUXD_API ahead of declaration:
        usbmuxd_subscribe
        usbmuxd_unsubscribe
        usbmuxd_get_device_list
        usbmuxd_device_list_free
        usbmuxd_get_device_by_udid
        usbmuxd_connect
        usbmuxd_disconnect
        usbmuxd_send
        usbmuxd_recv_timeout
        usbmuxd_recv
        usbmuxd_set_use_inotify
        usbmuxd_set_debug_level

    - If 64bits, then Right click->Properties->Configuration Manager change
      Win32 to x64 for the libcnary project and check the Build checkbox
    - Right-click libusbmuxd, Build. Should build with 0 errors, 10 or 14 warnings

Build libgen
-----------------------

In VS Solution Explorer, right-click Solution 'imobiledevice', then click
Add|New Project.
    - Name: libgen
    - Visual C++: Win32, Template: Win32 Project
    - Location: Add \imobiledevice to the end of the default location
    - Click OK
    - Application Settings: Static library (not using precompiled headers)
    - Click Finish

In VS Solution Explorer, select the libgen project, then click the 'Show all files'
button.
    - Select libgen.cpp and libgen.h, right click, select 'Include In Project'
    - Open libgen.cpp, comment out line 5::
        // #include <fileapi.h> 
      (This is a Windows 8 include file, not needed to build in Win 7)
    - If 64bits, then Right click->Properties->Configuration Manager change
      Win32 to x64 for the libcnary project and check the Build checkbox
    - Right-click libgen, Build. Should build with 0 errors, 0 warnings.

Build libimobiledevice
----------------------------

In VS Solution Explorer, right-click Solution 'imobiledevice', then click
Add|New Project.
    - Name: libimobiledevice
    - Visual C++: Win32, Template: Win32 Project
    - Location: Add \imobiledevice to the end of the default location
    - Click OK
    - Application Settings: DLL (Empty project)
    - Click Finish

    - Right-click the include folder, select Include In Project
    - Right-click the src folder, select Include In Project
    - Set .c files to compile as C++
        Advanced|Compile As: Compile as C++ Code (/TP)
    - Properties|Configuration Properties|C/C++:
        General|Additional Include Directories:
        $(ProjectDir)\include
        $(SolutionDir)\include
        $(SolutionDir)\libplist\include
        $(SolutionDir)\libgen
        $(SolutionDir)\libusbmuxd
        $SW\private\openssl\include
    - Edit afc.c #35:
        Comment out lines 35-37 (Synchapi.h is a Windows 8 include file)
    - Edit userprofile.c and add at line 25:
        #include <Windows.h>
    - Properties -> Linker -> General -> Additional library directories:
        $SW\private\openssl\lib
        $(OutDir)
    - Properties|Linker|Input|Additional Dependencies:
        libeay32.lib
        ssleay32.lib
        libplist.lib
        libgen.lib
        libusbmuxd.lib
        ws2_32.lib
    - Properties|C/C++|Preprocessor
        Preprocessor Definitions:
            ASN1_STATIC
            HAVE_OPENSSL
            __LITTLE_ENDIAN__
            _LIB
    - Project Dependencies:
        libcnary
        libgen
        libplist
        libusbmuxd
    - If 64bits, then Right click->Properties->Configuration Manager change
      Win32 to x64 for the libcnary project and check the Build checkbox
    - Edit libimobiledevice\include\libimobiledevice\afc.h
        At #26, insert
        #define AFC_API __declspec( dllexport )
        Then, at each function, insert AFC_API ahead of declaration
        afc_client_new
        afc_client_free
        afc_get_device_info
        afc_read_directory
        afc_get_file_info
        afc_file_open
        afc_file_close
        afc_file_lock
        afc_file_read
        afc_file_write
        afc_file_seek
        afc_file_tell
        afc_file_truncate
        afc_remove_path
        afc_rename_path
        afc_make_directory
        afc_truncate
        afc_make_link
        afc_set_file_time
        afc_get_device_info_key

    - Edit libimobiledevice\include\libimobiledevice\housearrest.h
        At #26, insert
        #define HOUSE_ARREST_API __declspec( dllexport )
        Then, at each function, insert HOUSE_ARREST_API ahead of declaration
        house_arrest_client_new
        house_arrest_client_free
        house_arrest_send_request
        house_arrest_send_command
        house_arrest_get_result
        afc_client_new_from_house_arrest_client

    - Edit libimobiledevice\include\libimobiledevice\installation_proxy.h
        At #26, insert
        #define INSTALLATION_PROXY_API __declspec( dllexport )
        Then, at each function, insert INSTALLATION_PROXY_API ahead of declaration
        instproxy_client_new
        instproxy_client_free
        instproxy_browse
        instproxy_install
        instproxy_upgrade
        instproxy_uninstall
        instproxy_lookup_archives
        instproxy_archive
        instproxy_restore
        instproxy_remove_archive
        instproxy_client_options_new
        instproxy_client_options_add
        instproxy_client_options_free

    - Edit libimobiledevice\include\libimobiledevice\libimobiledevice.h
        At #26, insert
        #define LIBIMOBILEDEVICE_API __declspec( dllexport )
        Then, at each function, insert LIBIMOBILEDEVICE_API ahead of declaration
        idevice_set_debug_level
        idevice_event_subscribe
        idevice_event_unsubscribe
        idevice_get_device_list
        idevice_device_list_free
        idevice_new
        idevice_free
        idevice_connect
        idevice_disconnect
        idevice_connection_send
        idevice_connection_receive_timeout
        idevice_connection_receive
        idevice_get_handle
        idevice_get_udid

    - Edit libimobiledevice\include\libimobiledevice\lockdown.h
        At #27, insert
        #define LOCKDOWN_API __declspec( dllexport )
        Then, at each function, insert LOCKDOWN_API ahead of declaration
        lockdownd_client_new
        lockdownd_client_new_with_handshake
        lockdownd_client_free
        lockdownd_query_type
        lockdownd_get_value
        lockdownd_set_value
        lockdownd_remove_value
        lockdownd_start_service
        lockdownd_start_session
        lockdownd_stop_session
        lockdownd_send
        lockdownd_receive
        lockdownd_pair
        lockdownd_validate_pair
        lockdownd_unpair
        lockdownd_activate
        lockdownd_deactivate
        lockdownd_enter_recovery
        lockdownd_goodbye
        lockdownd_getdevice_udid
        lockdownd_get_device_name
        lockdownd_get_sync_data
        lockdownd_data_classes_free
        lockdownd_service_descriptor_free

    - Right-click libimobiledevice, Build.
        0 errors, 60 warnings.

Copy the DLLs
-----------------

Run::
    cp `find . -name '*.dll'` ~/sw/bin/

