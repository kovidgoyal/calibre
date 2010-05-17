# Makefile to test the winutil module
# Invoke with nmake /f  Makefile.winutil

test : winutil.pyd
    \python26\python.exe -c "import winutil; winutil.set_debug(True); print repr(winutil.strftime(u'%b %a %A')); "
#python.exe -c "import winutil; winutil.set_debug(True); print winutil.get_usb_devices(); print winutil.get_mounted_volumes_for_usb_device(0x054c, 0x031e)"

winutil.pyd : winutil.obj
	link.exe /DLL /nologo /INCREMENTAL:NO /LIBPATH:c:\Python26\libs \
	/LIBPATH:c:\Python26\PCBuild shell32.lib setupapi.lib 	Wininet.lib /EXPORT:initwinutil \
	winutil.obj /OUT:winutil.pyd


winutil.obj : winutil.c
	cl.exe /c /nologo /Ox /MD /W3 /GX /DNDEBUG -Ic:\Python26\include \
	-Ic:\Python26\PC -Ic:\WinDDK\6001.18001\inc\api /Tcwinutil.c /Fowinutil.obj

clean :
	del winutil.pyd winutil.obj winutil.exp winutil.lib
