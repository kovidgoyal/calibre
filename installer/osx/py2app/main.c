#include <unistd.h>
#include <sys/stat.h>
#include <pwd.h>
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <CoreFoundation/CoreFoundation.h>
#include <ApplicationServices/ApplicationServices.h>

/*
    Typedefs
*/

typedef int PyObject;
typedef void (*Py_DecRefPtr)(PyObject *);
typedef void (*Py_SetProgramNamePtr)(const char *);
typedef void (*Py_InitializePtr)(void); 
typedef int (*PyRun_SimpleFilePtr)(FILE *, const char *);
typedef void (*Py_FinalizePtr)(void);
typedef PyObject *(*PySys_GetObjectPtr)(const char *);
typedef int *(*PySys_SetArgvPtr)(int argc, char **argv);
typedef PyObject *(*PyObject_StrPtr)(PyObject *);
typedef const char *(*PyString_AsStringPtr)(PyObject *);
typedef PyObject *(*PyObject_GetAttrStringPtr)(PyObject *, const char *);
static void DefaultDecRef(PyObject *op) {
    if (op != NULL) --(*op);
}

typedef CFTypeRef id;
typedef const char *SEL;
typedef signed char BOOL;
#define NSAlertAlternateReturn 0

/*
    Forward declarations
*/
static int report_error(const char *);
static CFTypeRef getKey(const char *key);

/*
    Strings
*/
static const char *ERR_REALLYBADTITLE = "The application could not be launched.";
static const char *ERR_TITLEFORMAT = "%@ has encountered a fatal error, and will now terminate.";
static const char *ERR_NONAME = "The Info.plist file must have values for the CFBundleName or CFBundleExecutable strings.";
static const char *ERR_PYRUNTIMELOCATIONS = "The Info.plist file must have a PyRuntimeLocations array containing string values for preferred Python runtime locations.  These strings should be \"otool -L\" style mach ids; \"@executable_stub\" and \"~\" prefixes will be translated accordingly.";
static const char *ERR_NOPYTHONRUNTIME = "A Python runtime could be located.  You may need to install a framework build of Python, or edit the PyRuntimeLocations array in this application's Info.plist file.";
static const char *ERR_NOPYTHONSCRIPT = "A main script could not be located in the Resources folder.;";
static const char *ERR_LINKERRFMT = "An internal error occurred while attempting to link:\r\r%s\r\r";
static const char *ERR_UNKNOWNPYTHONEXCEPTION = "An uncaught exception was raised during execution of the main script, but its class or name could not be determined";
static const char *ERR_PYTHONEXCEPTION = "An uncaught exception was raised during execution of the main script:\r\r%@: %@\r\rThis may mean that an unexpected error has occurred, or that you do not have all of the dependencies for this application.\r\rSee the Console for a detailed traceback.";
static const char *ERR_COLONPATH = "Python applications can not currently run from paths containing a '/' (or ':' from the Terminal).";
static const char *ERR_DEFAULTURLTITLE = "Visit Website";
static const char *ERR_CONSOLEAPP = "Console.app";
static const char *ERR_CONSOLEAPPTITLE = "Open Console";
static const char *ERR_TERMINATE = "Terminate";

/*
    Constants
*/

#define PYMACAPP_DYLD_FLAGS RTLD_LAZY|RTLD_GLOBAL

/*
    Globals
*/
static CFMutableArrayRef pool;

#define USES(NAME) static __typeof__(&NAME) x ## NAME
/* ApplicationServices */
USES(LSOpenFSRef);
USES(LSFindApplicationForInfo);
USES(GetCurrentProcess);
USES(SetFrontProcess);
/* CoreFoundation */
USES(CFArrayRemoveValueAtIndex);
USES(CFStringCreateFromExternalRepresentation);
USES(CFStringAppendCString);
USES(CFStringCreateMutable);
USES(kCFTypeArrayCallBacks);
USES(CFArrayCreateMutable);
USES(CFRetain);
USES(CFRelease);
USES(CFBundleGetMainBundle);
USES(CFBundleGetValueForInfoDictionaryKey);
USES(CFArrayGetCount);
USES(CFStringCreateWithCString);
USES(CFArrayGetValueAtIndex);
USES(CFArrayAppendValue);
USES(CFStringFind);
USES(CFBundleCopyPrivateFrameworksURL);
USES(CFURLCreateWithFileSystemPathRelativeToBase);
USES(CFStringCreateWithSubstring);
USES(CFStringGetLength);
USES(CFURLGetFileSystemRepresentation);
USES(CFURLCreateWithFileSystemPath);
USES(CFShow);
USES(CFBundleCopyResourcesDirectoryURL);
USES(CFURLCreateFromFileSystemRepresentation);
USES(CFURLCreateFromFileSystemRepresentationRelativeToBase);
USES(CFStringGetCharacterAtIndex);
USES(CFURLCreateWithString);
USES(CFStringGetCString);
USES(CFStringCreateByCombiningStrings);
USES(CFDictionaryGetValue);
USES(CFBooleanGetValue);
USES(CFStringCreateArrayBySeparatingStrings);
USES(CFArrayAppendArray);
USES(CFStringCreateByCombiningStrings);
USES(CFStringCreateWithFormat);
USES(CFBundleCopyResourceURL);
USES(CFBundleCopyAuxiliaryExecutableURL);
USES(CFURLCreateCopyDeletingLastPathComponent);
USES(CFURLCreateCopyAppendingPathComponent);
USES(CFURLCopyLastPathComponent);
USES(CFStringGetMaximumSizeForEncoding);
#undef USES

/*
    objc
*/

#define CLS(name) xobjc_getClass(name)
#define MSG(receiver, selName, ...) \
    xobjc_msgSend(receiver, xsel_getUid(selName), ## __VA_ARGS__)
static id (*xobjc_getClass)(const char *name);
static SEL (*xsel_getUid)(const char *str);
static id (*xobjc_msgSend)(id self, SEL op, ...);

/*
    Cocoa
*/
static void (*xNSLog)(CFStringRef format, ...);
static BOOL (*xNSApplicationLoad)(void);
static int (*xNSRunAlertPanel)(CFStringRef title, CFStringRef msg, CFStringRef defaultButton, CFStringRef alternateButton, CFStringRef otherButton, ...);

/*
    Functions
*/

static int bind_objc_Cocoa_ApplicationServices(void) {
    static Boolean bound = false;
    if (bound) return 0;
    bound = true;
    void *cf_dylib;
    cf_dylib = dlopen("/usr/lib/libobjc.dylib", PYMACAPP_DYLD_FLAGS);
    if (cf_dylib == NULL) return -1;
#define LOOKUP(NAME) do { \
    void *tmpSymbol = dlsym( \
        cf_dylib, #NAME); \
    if (tmpSymbol == NULL) return -1; \
    x ## NAME = (__typeof__(x ## NAME))(tmpSymbol); \
    } while (0)

    LOOKUP(objc_getClass);
    LOOKUP(sel_getUid);
    LOOKUP(objc_msgSend);

    cf_dylib = dlopen(
        "/System/Library/Frameworks/Cocoa.framework/Cocoa",
        PYMACAPP_DYLD_FLAGS);
    if (cf_dylib == NULL) return -1;
    LOOKUP(NSLog);
    LOOKUP(NSApplicationLoad);
    LOOKUP(NSRunAlertPanel);

#undef LOOKUP

    cf_dylib = dlopen(
        "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices",
        PYMACAPP_DYLD_FLAGS);
    if (cf_dylib == NULL) return -1;
#define LOOKUP(NAME) do { \
    void *tmpSymbol = dlsym( \
        cf_dylib, #NAME); \
    if (tmpSymbol == NULL) return -1; \
    x ## NAME = (__typeof__(&NAME))(tmpSymbol); \
    } while (0)

    LOOKUP(GetCurrentProcess);
    LOOKUP(SetFrontProcess);
    LOOKUP(LSOpenFSRef);
    LOOKUP(LSFindApplicationForInfo);
#undef LOOKUP
    return 0;
}
    
static int bind_CoreFoundation(void) {
    static Boolean bound = false;
    void *cf_dylib;
    if (bound) return 0;
    bound = true;
    cf_dylib = dlopen(
        "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation",
        PYMACAPP_DYLD_FLAGS);
    if (cf_dylib == NULL) return -1;

#define LOOKUP(NAME) do { \
    void *tmpSymbol = dlsym( \
        cf_dylib, #NAME); \
    if (tmpSymbol == NULL) return -1; \
    x ## NAME = (__typeof__(&NAME))(tmpSymbol); \
    } while (0)

    LOOKUP(CFArrayRemoveValueAtIndex);
    LOOKUP(CFStringCreateFromExternalRepresentation);
    LOOKUP(CFStringAppendCString);
    LOOKUP(CFStringCreateMutable);
    LOOKUP(kCFTypeArrayCallBacks);
    LOOKUP(CFArrayCreateMutable);
    LOOKUP(CFRetain);
    LOOKUP(CFRelease);
    LOOKUP(CFBundleGetMainBundle);
    LOOKUP(CFBundleGetValueForInfoDictionaryKey);
    LOOKUP(CFArrayGetCount);
    LOOKUP(CFStringCreateWithCString);
    LOOKUP(CFArrayGetValueAtIndex);
    LOOKUP(CFArrayAppendValue);
    LOOKUP(CFStringFind);
    LOOKUP(CFBundleCopyPrivateFrameworksURL);
    LOOKUP(CFURLCreateWithFileSystemPathRelativeToBase);
    LOOKUP(CFStringCreateWithSubstring);
    LOOKUP(CFStringGetLength);
    LOOKUP(CFURLGetFileSystemRepresentation);
    LOOKUP(CFURLCreateWithFileSystemPath);
    LOOKUP(CFShow);
    LOOKUP(CFBundleCopyResourcesDirectoryURL);
    LOOKUP(CFURLCreateFromFileSystemRepresentation);
    LOOKUP(CFURLCreateFromFileSystemRepresentationRelativeToBase);
    LOOKUP(CFStringGetCharacterAtIndex);
    LOOKUP(CFURLCreateWithString);
    LOOKUP(CFStringGetCString);
    LOOKUP(CFStringCreateByCombiningStrings);
    LOOKUP(CFDictionaryGetValue);
    LOOKUP(CFBooleanGetValue);
    LOOKUP(CFStringCreateArrayBySeparatingStrings);
    LOOKUP(CFArrayAppendArray);
    LOOKUP(CFStringCreateByCombiningStrings);
    LOOKUP(CFStringCreateWithFormat);
    LOOKUP(CFBundleCopyResourceURL);
    LOOKUP(CFBundleCopyAuxiliaryExecutableURL);
    LOOKUP(CFURLCreateCopyDeletingLastPathComponent);
    LOOKUP(CFURLCreateCopyAppendingPathComponent);
    LOOKUP(CFURLCopyLastPathComponent);
    LOOKUP(CFStringGetMaximumSizeForEncoding);

#undef LOOKUP

    return 0;
}

#define AUTORELEASE(obj) ((obj == NULL) ? NULL : ( \
    xCFArrayAppendValue(pool, (const void *)obj), \
    xCFRelease(obj), \
    obj))
    
#define xCFSTR(s) AUTORELEASE( \
    xCFStringCreateWithCString(NULL, s, kCFStringEncodingUTF8))

static int openConsole(void) {
    OSStatus err;
    FSRef consoleRef;
    err = xLSFindApplicationForInfo(
        kLSUnknownCreator,
        NULL,
        xCFSTR(ERR_CONSOLEAPP),
        &consoleRef,
        NULL);
    if (err != noErr) return err;
    return xLSOpenFSRef((const FSRef *)&consoleRef, NULL);
}

static CFTypeRef getKey(const char *key) {
    CFTypeRef rval;
    CFStringRef cfKey = xCFStringCreateWithCString(NULL,
        key, kCFStringEncodingUTF8);
    if (!cfKey) return NULL;
    rval = xCFBundleGetValueForInfoDictionaryKey(
        xCFBundleGetMainBundle(),
        cfKey);
    xCFRelease(cfKey);
    return rval;
}

static CFStringRef getApplicationName(void) {
    static CFStringRef name = NULL;
    if (name) return name;
    name = (CFStringRef)getKey("CFBundleName");
    if (!name) name = (CFStringRef)getKey("CFBundleExecutable");
    return AUTORELEASE(name);
}


static CFStringRef getErrorTitle(CFStringRef applicationName) {
    CFStringRef res;
    if (!applicationName) return xCFSTR(ERR_REALLYBADTITLE);
    res = xCFStringCreateWithFormat(
        NULL, NULL, xCFSTR(ERR_TITLEFORMAT), applicationName);
    AUTORELEASE(res);
    return res;
}

static void ensureGUI(void) {
    ProcessSerialNumber psn;
    id app = MSG(CLS("NSApplication"), "sharedApplication");
    xNSApplicationLoad();
    MSG(app, "activateIgnoringOtherApps:", (BOOL)1);
    if (xGetCurrentProcess(&psn) == noErr) {
        xSetFrontProcess(&psn);
    }
}

static int report_error(const char *error) {
    int choice;
    id releasePool;
    if (bind_objc_Cocoa_ApplicationServices()) {
        fprintf(stderr, "%s\n", error);
        return -1;
    }
    releasePool = MSG(MSG(CLS("NSAutoreleasePool"), "alloc"), "init");
    xNSLog(xCFSTR("%@"), xCFSTR(error));
    if (!xNSApplicationLoad()) {
        xNSLog(xCFSTR("NSApplicationLoad() failed"));
    } else {
        ensureGUI();
        choice = xNSRunAlertPanel(
            getErrorTitle(getApplicationName()),
            xCFSTR("%@"),
            xCFSTR(ERR_TERMINATE),
            xCFSTR(ERR_CONSOLEAPPTITLE),
            NULL,
            xCFSTR(error));
        if (choice == NSAlertAlternateReturn) openConsole();
    }
    MSG(releasePool, "release");
    return -1;
}

static CFStringRef pathFromURL(CFURLRef anURL) {
    UInt8 buf[PATH_MAX];
    xCFURLGetFileSystemRepresentation(anURL, true, buf, sizeof(buf));
    return xCFStringCreateWithCString(NULL, (char *)buf, kCFStringEncodingUTF8);
}

static CFStringRef pyStandardizePath(CFStringRef pyLocation) {
    CFRange foundRange;
    CFURLRef fmwkURL;
    CFURLRef locURL;
    CFStringRef subpath;
    static CFStringRef prefix = NULL;
    if (!prefix) prefix = xCFSTR("@executable_path/");
    foundRange = xCFStringFind(pyLocation, prefix, 0);
    if (foundRange.location == kCFNotFound || foundRange.length == 0) {
        return NULL;
    }
    fmwkURL = xCFBundleCopyPrivateFrameworksURL(xCFBundleGetMainBundle());
    foundRange.location = foundRange.length;
    foundRange.length = xCFStringGetLength(pyLocation) - foundRange.length;
    subpath = xCFStringCreateWithSubstring(NULL, pyLocation, foundRange);
    locURL = xCFURLCreateWithFileSystemPathRelativeToBase(
        NULL,
        subpath,
        kCFURLPOSIXPathStyle,
        false,
        fmwkURL);
    xCFRelease(subpath);
    xCFRelease(fmwkURL);
    subpath = pathFromURL(locURL);
    xCFRelease(locURL);
    return subpath;
}

static Boolean doesPathExist(CFStringRef path) {
    struct stat st;
    CFURLRef locURL;
    UInt8 buf[PATH_MAX];
    locURL = xCFURLCreateWithFileSystemPath(
        NULL, path, kCFURLPOSIXPathStyle, false);
    xCFURLGetFileSystemRepresentation(locURL, true, buf, sizeof(buf));
    xCFRelease(locURL);
    return (stat((const char *)buf, &st) == -1 ? false : true);
}

static CFStringRef findPyLocation(CFArrayRef pyLocations) {
    int i;
    int cnt = xCFArrayGetCount(pyLocations);
    for (i = 0; i < cnt; i++) {
        CFStringRef newLoc;
        CFStringRef pyLocation = xCFArrayGetValueAtIndex(pyLocations, i);
        newLoc = pyStandardizePath(pyLocation);
        if (!newLoc) newLoc = pyLocation;
        if (doesPathExist(newLoc)) {
            if (newLoc == pyLocation) xCFRetain(newLoc);
            return newLoc;
        }
        if (newLoc) xCFRelease(newLoc);
    }
    return NULL;
}

static CFStringRef tildeExpand(CFStringRef path) {
    CFURLRef pathURL;
    char buf[PATH_MAX];
    CFURLRef fullPathURL;
    struct passwd *pwnam;
    char tmp;
    char *dir = NULL;

    
    xCFStringGetCString(path, buf, sizeof(buf), kCFStringEncodingUTF8);

    int i;
    if (buf[0] != '~') {
        return xCFStringCreateWithCString(
            NULL, buf, kCFStringEncodingUTF8);
    }
    /* user in path */
    i = 1;
    while (buf[i] != '\0' && buf[i] != '/') {
        i++;
    }
    if (i == 1) {
        dir = getenv("HOME");
    } else {
        tmp = buf[i];
        buf[i] = '\0';
        pwnam = getpwnam((const char *)&buf[1]);
        if (pwnam) dir = pwnam->pw_dir;
        buf[i] = tmp;
    }
    if (!dir) {
        return xCFStringCreateWithCString(NULL, buf, kCFStringEncodingUTF8);
    }
    pathURL = xCFURLCreateFromFileSystemRepresentation(
        NULL, (const UInt8*)dir, strlen(dir), false);
    fullPathURL = xCFURLCreateFromFileSystemRepresentationRelativeToBase(
        NULL, (const UInt8*)&buf[i + 1], strlen(&buf[i + 1]), false, pathURL);
    xCFRelease(pathURL);
    path = pathFromURL(fullPathURL);
    xCFRelease(fullPathURL);
    return path;
}

static void setcfenv(char *name, CFStringRef value) {
    char buf[PATH_MAX];
    xCFStringGetCString(value, buf, sizeof(buf), kCFStringEncodingUTF8);
    setenv(name, buf, 1);
}

static void setPythonPath(void) {
    CFMutableArrayRef paths;
    CFURLRef resDir;
    CFStringRef resPath;
    CFArrayRef resPackages;
    CFDictionaryRef options;

    paths = xCFArrayCreateMutable(NULL, 0, xkCFTypeArrayCallBacks);

    resDir = xCFBundleCopyResourcesDirectoryURL(xCFBundleGetMainBundle());
    resPath = pathFromURL(resDir);
    xCFArrayAppendValue(paths, resPath);
    xCFRelease(resPath);

    resPackages = getKey("PyResourcePackages");
    if (resPackages) {
        int i;
        int cnt = xCFArrayGetCount(resPackages);
        for (i = 0; i < cnt; i++) {
            resPath = tildeExpand(xCFArrayGetValueAtIndex(resPackages, i));
            if (xCFStringGetLength(resPath)) {
                if (xCFStringGetCharacterAtIndex(resPath, 0) != '/') {
                    CFURLRef absURL = xCFURLCreateWithString(
                        NULL, resPath, resDir);
                    xCFRelease(resPath);
                    resPath = pathFromURL(absURL);
                    xCFRelease(absURL);
                }
                xCFArrayAppendValue(paths, resPath);
            }
            xCFRelease(resPath);
        }
    }

    xCFRelease(resDir);

    options = getKey("PyOptions");
    if (options) {
        CFBooleanRef use_pythonpath;
        use_pythonpath = xCFDictionaryGetValue(
            options, xCFSTR("use_pythonpath"));
        if (use_pythonpath && xCFBooleanGetValue(use_pythonpath)) {
            char *ppath = getenv("PYTHONPATH");
            if (ppath) {
                CFArrayRef oldPath;
                oldPath = xCFStringCreateArrayBySeparatingStrings(
                    NULL, xCFSTR(ppath), xCFSTR(":"));
                if (oldPath) {
                    CFRange rng;
                    rng.location = 0;
                    rng.length = xCFArrayGetCount(oldPath);
                    xCFArrayAppendArray(paths, oldPath, rng);
                    xCFRelease(oldPath);
                }
            }
        }
    }

    if (xCFArrayGetCount(paths)) {
        resPath = xCFStringCreateByCombiningStrings(NULL, paths, xCFSTR(":"));
        setcfenv("PYTHONPATH", resPath);
        xCFRelease(resPath);
    }
    xCFRelease(paths);
}



static void setResourcePath(void) {
    CFURLRef resDir;
    CFStringRef resPath;
    resDir = xCFBundleCopyResourcesDirectoryURL(xCFBundleGetMainBundle());
    resPath = pathFromURL(resDir);
    xCFRelease(resDir);
    setcfenv("RESOURCEPATH", resPath);
    xCFRelease(resPath);
}

static void setExecutablePath(void) {
    char executable_path[PATH_MAX];
    uint32_t bufsize = PATH_MAX;
    if (!_NSGetExecutablePath(executable_path, &bufsize)) {
        executable_path[bufsize] = '\0';
        setenv("EXECUTABLEPATH", executable_path, 1);
    }
}

static CFStringRef getMainScript(void) {
    CFMutableArrayRef possibleMains;
    CFBundleRef bndl;
    CFStringRef e_py, e_pyc, e_pyo, path;
    int i, cnt;
    possibleMains = xCFArrayCreateMutable(NULL, 0, xkCFTypeArrayCallBacks);
    CFArrayRef firstMains = getKey("PyMainFileNames");
    if (firstMains) {
        CFRange rng;
        rng.location = 0;
        rng.length = xCFArrayGetCount(firstMains);
        xCFArrayAppendArray(possibleMains, firstMains, rng);
    }
    xCFArrayAppendValue(possibleMains, xCFSTR("__main__"));
    xCFArrayAppendValue(possibleMains, xCFSTR("__realmain__"));
    xCFArrayAppendValue(possibleMains, xCFSTR("launcher"));

    e_py = xCFSTR("py");
    e_pyc = xCFSTR("pyc");
    e_pyo = xCFSTR("pyo");

    cnt = xCFArrayGetCount(possibleMains);
    bndl = xCFBundleGetMainBundle();
    path = NULL;
    for (i = 0; i < cnt; i++) {
        CFStringRef base;
        CFURLRef resURL;
        base = xCFArrayGetValueAtIndex(possibleMains, i);
        resURL = xCFBundleCopyResourceURL(bndl, base, e_py, NULL);
        if (resURL == NULL) {
            resURL = xCFBundleCopyResourceURL(bndl, base, e_pyc, NULL);
        }
        if (resURL == NULL) {
            resURL = xCFBundleCopyResourceURL(bndl, base, e_pyo, NULL);
        }
        if (resURL != NULL) {
            path = pathFromURL(resURL);
            xCFRelease(resURL);
            break;
        }
    }
    xCFRelease(possibleMains);
    return path;
}

static int report_linkEdit_error(void) {
    CFStringRef errString;
    const char *errorString;
    char *buf;
    errorString = dlerror();
    fprintf(stderr, errorString);
    errString = xCFStringCreateWithFormat(
        NULL, NULL, xCFSTR(ERR_LINKERRFMT), errString);
    buf = alloca(xCFStringGetMaximumSizeForEncoding(
            xCFStringGetLength(errString), kCFStringEncodingUTF8));
    xCFStringGetCString(errString, buf, sizeof(buf), kCFStringEncodingUTF8);
    xCFRelease(errString);
    return report_error(buf);
}

static CFStringRef getPythonInterpreter(CFStringRef pyLocation) {
    CFBundleRef bndl;
    CFStringRef auxName;
    CFURLRef auxURL;
    CFStringRef path;

    auxName = getKey("PyExecutableName");
    if (!auxName) auxName = xCFSTR("python");
    bndl = xCFBundleGetMainBundle();
    auxURL = xCFBundleCopyAuxiliaryExecutableURL(bndl, auxName);
    if (auxURL) {
        path = pathFromURL(auxURL);
        xCFRelease(auxURL);
        return path;
    }
    return NULL;
}

static CFStringRef getErrorScript(void) {
    CFMutableArrayRef errorScripts;
    CFBundleRef bndl;
    CFStringRef path;
    int i, cnt;
    errorScripts = xCFArrayCreateMutable(NULL, 0, xkCFTypeArrayCallBacks);
    CFArrayRef firstErrorScripts = getKey("PyErrorScripts");
    if (firstErrorScripts) {
        CFRange rng;
        rng.location = 0;
        rng.length = xCFArrayGetCount(firstErrorScripts);
        xCFArrayAppendArray(errorScripts, firstErrorScripts, rng);
    }
    xCFArrayAppendValue(errorScripts, xCFSTR("__error__"));
    xCFArrayAppendValue(errorScripts, xCFSTR("__error__.py"));
    xCFArrayAppendValue(errorScripts, xCFSTR("__error__.pyc"));
    xCFArrayAppendValue(errorScripts, xCFSTR("__error__.pyo"));
    xCFArrayAppendValue(errorScripts, xCFSTR("__error__.sh"));

    cnt = xCFArrayGetCount(errorScripts);
    bndl = xCFBundleGetMainBundle();
    path = NULL;
    for (i = 0; i < cnt; i++) {
        CFStringRef base;
        CFURLRef resURL;
        base = xCFArrayGetValueAtIndex(errorScripts, i);
        resURL = xCFBundleCopyResourceURL(bndl, base, NULL, NULL);
        if (resURL) {
            path = pathFromURL(resURL);
            xCFRelease(resURL);
            break;
        }
    }
    xCFRelease(errorScripts);
    return path;
 
}

static CFMutableArrayRef get_trimmed_lines(CFStringRef output) {
    CFMutableArrayRef lines;
    CFArrayRef tmp;
    CFRange rng;
    lines = xCFArrayCreateMutable(NULL, 0, xkCFTypeArrayCallBacks);
    tmp = xCFStringCreateArrayBySeparatingStrings(
        NULL, output, xCFSTR("\n"));
    rng.location = 0;
    rng.length = xCFArrayGetCount(tmp);
    xCFArrayAppendArray(lines, tmp, rng);
    while (true) {
        CFIndex cnt = xCFArrayGetCount(lines);
        CFStringRef last;
        /* Nothing on stdout means pass silently */
        if (cnt <= 0) {
            xCFRelease(lines);
            return NULL;
        }
        last = xCFArrayGetValueAtIndex(lines, cnt - 1);
        if (xCFStringGetLength(last) > 0) break;
        xCFArrayRemoveValueAtIndex(lines, cnt - 1);
    }
    return lines;
}

static int report_script_error(const char *msg, CFStringRef cls, CFStringRef name) {
    CFStringRef errorScript;
    CFMutableArrayRef lines;
    CFRange foundRange;
    CFStringRef lastLine;
    CFStringRef output = NULL;
    CFIndex lineCount;
    CFURLRef buttonURL = NULL;
    CFStringRef buttonString = NULL;
    CFStringRef title = NULL;
    CFStringRef errmsg = NULL;
    id releasePool;
    int errBinding;
    int status = 0;
    char *buf;


    if (cls && name) {
        CFStringRef errString = xCFStringCreateWithFormat(
            NULL, NULL, xCFSTR(msg), cls, name);
        buf = alloca(xCFStringGetMaximumSizeForEncoding(
                xCFStringGetLength(errString), kCFStringEncodingUTF8));
        xCFStringGetCString(
            errString, buf, sizeof(buf), kCFStringEncodingUTF8);
        xCFRelease(errString);
    } else {
        buf = (char *)msg;
    }

    errorScript = getErrorScript();
    if (!errorScript) return report_error(buf);

    errBinding = bind_objc_Cocoa_ApplicationServices();
    if (!errBinding) {
        id task, stdoutPipe, taskData;
        CFMutableArrayRef argv;
        releasePool = MSG(MSG(CLS("NSAutoreleasePool"), "alloc"), "init");
        task = MSG(MSG(CLS("NSTask"), "alloc"), "init");
        stdoutPipe = MSG(CLS("NSPipe"), "pipe");
        MSG(task, "setLaunchPath:", xCFSTR("/bin/sh"));
        MSG(task, "setStandardOutput:", stdoutPipe);
        argv = xCFArrayCreateMutable(NULL, 0, xkCFTypeArrayCallBacks);
        xCFArrayAppendValue(argv, errorScript);
        xCFArrayAppendValue(argv, getApplicationName());
        if (cls && name) {
            xCFArrayAppendValue(argv, cls);
            xCFArrayAppendValue(argv, name);
        }
        MSG(task, "setArguments:", argv);
        /* This could throw, in theory, but /bin/sh should prevent that */
        MSG(task, "launch");
        MSG(task, "waitUntilExit");
        taskData = MSG(
            MSG(stdoutPipe, "fileHandleForReading"),
            "readDataToEndOfFile");
        xCFRelease(argv);

        status = (int)MSG(task, "terminationStatus");
        xCFRelease(task);
        if (!status && taskData) {
            output = xCFStringCreateFromExternalRepresentation(
                NULL, taskData, kCFStringEncodingUTF8);
        }

        MSG(releasePool, "release");
    }

    xCFRelease(errorScript);
    if (status || !output) return report_error(buf);

    lines = get_trimmed_lines(output);
    xCFRelease(output);
    /* Nothing on stdout means pass silently */
    if (!lines) return -1;
    lineCount = xCFArrayGetCount(lines);
    lastLine = xCFArrayGetValueAtIndex(lines, lineCount - 1);
    foundRange = xCFStringFind(lastLine, xCFSTR("ERRORURL: "), 0);
    if (foundRange.location != kCFNotFound && foundRange.length != 0) {
        CFMutableArrayRef buttonArr;
        CFArrayRef tmp;
        CFRange rng;
        buttonArr = xCFArrayCreateMutable(NULL, 0, xkCFTypeArrayCallBacks);
        tmp = xCFStringCreateArrayBySeparatingStrings(
            NULL, lastLine, xCFSTR(" "));
        lineCount -= 1;
        xCFArrayRemoveValueAtIndex(lines, lineCount);
        rng.location = 1;
        rng.length = xCFArrayGetCount(tmp) - 1;
        xCFArrayAppendArray(buttonArr, tmp, rng);
        xCFRelease(tmp);
        while (true) {
            CFStringRef tmpstr;
            if (xCFArrayGetCount(buttonArr) <= 0) break;
            tmpstr = xCFArrayGetValueAtIndex(buttonArr, 0);
            if (xCFStringGetLength(tmpstr) == 0) {
                xCFArrayRemoveValueAtIndex(buttonArr, 0);
            } else {
                break;
            }
        }

        buttonURL = xCFURLCreateWithString(
            NULL, xCFArrayGetValueAtIndex(buttonArr, 0), NULL);
        if (buttonURL) {
            xCFArrayRemoveValueAtIndex(buttonArr, 0);
            while (true) {
                CFStringRef tmpstr;
                if (xCFArrayGetCount(buttonArr) <= 0) break;
                tmpstr = xCFArrayGetValueAtIndex(buttonArr, 0);
                if (xCFStringGetLength(tmpstr) == 0) {
                    xCFArrayRemoveValueAtIndex(buttonArr, 0);
                } else {
                    break;
                }
            }
            if (xCFArrayGetCount(buttonArr) > 0) {
                buttonString = xCFStringCreateByCombiningStrings(
                    NULL, buttonArr, xCFSTR(" "));
            }
            if (!buttonString) buttonString = xCFSTR(ERR_DEFAULTURLTITLE);
        }
        xCFRelease(buttonArr);
        
    }
    if (lineCount <= 0 || errBinding) {
        xCFRelease(lines);
        return report_error(buf);
    }

    releasePool = MSG(MSG(CLS("NSAutoreleasePool"), "alloc"), "init");

    title = xCFArrayGetValueAtIndex(lines, 0);
    xCFRetain(title);
    AUTORELEASE(title);
    lineCount -= 1;
    xCFArrayRemoveValueAtIndex(lines, lineCount);
    xNSLog(xCFSTR("%@"), title);
    if (lineCount > 0) {
        CFStringRef showerr;
        errmsg = xCFStringCreateByCombiningStrings(
            NULL, lines, xCFSTR("\r"));
        AUTORELEASE(errmsg);
        showerr = MSG(
            MSG(errmsg, "componentsSeparatedByString:", xCFSTR("\r")),
            "componentsJoinedByString:", xCFSTR("\n"));
        xNSLog(xCFSTR("%@"), showerr);
    } else {
        errmsg = xCFSTR("");
    }

    ensureGUI();
    if (!buttonURL) {
        int choice = xNSRunAlertPanel(
            title, xCFSTR("%@"), xCFSTR(ERR_TERMINATE),
            xCFSTR(ERR_CONSOLEAPPTITLE), NULL, errmsg);
        if (choice == NSAlertAlternateReturn) openConsole();
    } else {
        int choice = xNSRunAlertPanel(
            title, xCFSTR("%@"), xCFSTR(ERR_TERMINATE),
            buttonString, NULL, errmsg);
        if (choice == NSAlertAlternateReturn) {
            id ws = MSG(CLS("NSWorkspace"), "sharedWorkspace");
            MSG(ws, "openURL:", buttonURL);
        }
    }
    MSG(releasePool, "release");
    xCFRelease(lines);
    return -1;
}

static int py2app_main(int argc, char * const *argv, char * const *envp) {
    CFArrayRef pyLocations;
    CFStringRef pyLocation;
    CFStringRef mainScript;
    CFStringRef pythonInterpreter;
    char *resource_path;
    char buf[PATH_MAX];
    char c_pythonInterpreter[PATH_MAX];
    char c_mainScript[PATH_MAX];
    char **argv_new;
    struct stat sb;
    void *py_dylib;
    void *tmpSymbol;
    int rval;
    FILE *mainScriptFile;


    if (!getApplicationName()) return report_error(ERR_NONAME);
    pyLocations = (CFArrayRef)getKey("PyRuntimeLocations");
    if (!pyLocations) return report_error(ERR_PYRUNTIMELOCATIONS);
    pyLocation = findPyLocation(pyLocations);
    if (!pyLocation) return report_error(ERR_NOPYTHONRUNTIME);

    setExecutablePath();
    setResourcePath();
    /* check for ':' in path, not compatible with Python due to Py_GetPath */
    /* XXX: Could work-around by creating something in /tmp I guess */
    resource_path = getenv("RESOURCEPATH");
    if ((resource_path == NULL) || (strchr(resource_path, ':') != NULL)) {
        return report_error(ERR_COLONPATH);
    }
    setPythonPath();
    setenv("ARGVZERO", argv[0], 1);

    mainScript = getMainScript();
    if (!mainScript) return report_error(ERR_NOPYTHONSCRIPT);

    pythonInterpreter = getPythonInterpreter(pyLocation);
    xCFStringGetCString(
        pythonInterpreter, c_pythonInterpreter,
        sizeof(c_pythonInterpreter), kCFStringEncodingUTF8);
    xCFRelease(pythonInterpreter);
    if (lstat(c_pythonInterpreter, &sb) == 0) {
        if (!((sb.st_mode & S_IFLNK) == S_IFLNK)) {
            setenv("PYTHONHOME", resource_path, 1);
        }
    }

    xCFStringGetCString(pyLocation, buf, sizeof(buf), kCFStringEncodingUTF8);
    py_dylib = dlopen(buf, PYMACAPP_DYLD_FLAGS);
    if (py_dylib == NULL) return report_linkEdit_error();

#define LOOKUP_SYMBOL(NAME) \
    tmpSymbol = dlsym(py_dylib, # NAME)
#define LOOKUP_DEFINEADDRESS(NAME, ADDRESS) \
    NAME ## Ptr NAME = (NAME ## Ptr)ADDRESS
#define LOOKUP_DEFINE(NAME) \
    LOOKUP_DEFINEADDRESS(NAME, (tmpSymbol))
#define LOOKUP(NAME) \
    LOOKUP_SYMBOL(NAME); \
    if ( tmpSymbol == NULL) \
        return report_linkEdit_error(); \
    LOOKUP_DEFINE(NAME)
    
    LOOKUP_SYMBOL(Py_DecRef);
    LOOKUP_DEFINEADDRESS(Py_DecRef, (tmpSymbol ? (tmpSymbol) : &DefaultDecRef));
    LOOKUP(Py_SetProgramName);
    LOOKUP(Py_Initialize);
    LOOKUP(PyRun_SimpleFile);
    LOOKUP(Py_Finalize);
    LOOKUP(PySys_GetObject);
    LOOKUP(PySys_SetArgv);
    LOOKUP(PyObject_Str);
    LOOKUP(PyString_AsString);
    LOOKUP(PyObject_GetAttrString);

#undef LOOKUP
#undef LOOKUP_DEFINE
#undef LOOKUP_DEFINEADDRESS
#undef LOOKUP_SYMBOL

    Py_SetProgramName(c_pythonInterpreter);

    Py_Initialize();

    xCFStringGetCString(
        mainScript, c_mainScript,
        sizeof(c_mainScript), kCFStringEncodingUTF8);
    xCFRelease(mainScript);

    argv_new = alloca((argc + 1) * sizeof(char *));
    argv_new[argc] = NULL;
    argv_new[0] = c_mainScript;
    memcpy(&argv_new[1], &argv[1], (argc - 1) * sizeof(char *));
    PySys_SetArgv(argc, argv_new);

    mainScriptFile = fopen(c_mainScript, "r");
    rval = PyRun_SimpleFile(mainScriptFile, c_mainScript);
    fclose(mainScriptFile);
    
    while (rval) {
        PyObject *exc, *exceptionClassName, *v, *exceptionName;
        CFStringRef clsName, excName;

        exc = PySys_GetObject("last_type");
        if ( !exc ) {
            rval = report_error(ERR_UNKNOWNPYTHONEXCEPTION);
            break;
        }

        exceptionClassName = PyObject_GetAttrString(exc, "__name__");
        if (!exceptionClassName) {
            rval = report_error(ERR_UNKNOWNPYTHONEXCEPTION);
            break;
        }

        v = PySys_GetObject("last_value");
        exceptionName = (v ? PyObject_Str(v) : NULL);

        clsName = xCFSTR(PyString_AsString(exceptionClassName));
        Py_DecRef(exceptionClassName);
        if (exceptionName) {
            excName = xCFSTR(PyString_AsString(exceptionName));
            Py_DecRef(exceptionName);
        } else {
            excName = xCFSTR("");
        }
        rval = report_script_error(ERR_PYTHONEXCEPTION, clsName, excName);
        break;
    }

    Py_Finalize();

    return rval;
}

int main(int argc, char * const *argv, char * const *envp)
{
    int rval;
    if (bind_CoreFoundation()) {
        fprintf(stderr, "CoreFoundation not found or functions missing\n");
        return -1;
    }
    if (!xCFBundleGetMainBundle()) {
        fprintf(stderr, "Not bundled, exiting\n");
        return -1;
    }
    pool = xCFArrayCreateMutable(NULL, 0, xkCFTypeArrayCallBacks);
    if (!pool) {
        fprintf(stderr, "Couldn't create global pool\n");
        return -1;
    }
    rval = py2app_main(argc, argv, envp);
    xCFRelease(pool);
    return rval;
}
