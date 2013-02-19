#ifndef _RAR_OS_
#define _RAR_OS_

#define FALSE 0
#define TRUE  1

#ifdef __EMX__
  #define INCL_BASE
#endif

#if defined(RARDLL) && !defined(SILENT)
#define SILENT
#endif

#define ENABLE_BAD_ALLOC // Undefine if std::bad_alloc is not supported.

#ifdef ENABLE_BAD_ALLOC
  #include <new>
#endif


#if defined(_WIN_ALL) || defined(_EMX)

#define LITTLE_ENDIAN
#define NM  1024

#ifdef _WIN_ALL

#define STRICT
#define UNICODE
#undef WINVER
#undef _WIN32_WINNT
#define WINVER 0x0501
#define _WIN32_WINNT 0x0501


#define WIN32_LEAN_AND_MEAN

#include <windows.h>
#include <prsht.h>
#include <shlwapi.h>
#include <shellapi.h>
#include <shlobj.h>
#include <winioctl.h>



#endif // _WIN_ALL

#include <sys/types.h>
#include <sys/stat.h>
#include <dos.h>

#if !defined(_EMX) && !defined(_MSC_VER)
  #include <dir.h>
#endif
#ifdef _MSC_VER
  #if _MSC_VER<1500
    #define for if (0) ; else for
  #endif
  #include <direct.h>
#else
  #include <dirent.h>
#endif // _MSC_VER

#ifdef _EMX
  #include <unistd.h>
  #include <pwd.h>
  #include <grp.h>
  #include <errno.h>
  #ifdef _DJGPP
    #include <utime.h>
  #else
    #include <os2.h>
    #include <sys/utime.h>
    #include <emx/syscalls.h>
  #endif
#endif

#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <ctype.h>
#include <fcntl.h>
#include <dos.h>
#include <io.h>
#include <time.h>
#include <signal.h>

#define ENABLE_ACCESS

#define DefConfigName  "rar.ini"
#define DefLogName     "rar.log"


#define PATHDIVIDER  "\\"
#define PATHDIVIDERW L"\\"
#define CPATHDIVIDER '\\'
#define MASKALL      "*"
#define MASKALLW     L"*"

#define READBINARY   "rb"
#define READTEXT     "rt"
#define UPDATEBINARY "r+b"
#define CREATEBINARY "w+b"
#define WRITEBINARY  "wb"
#define APPENDTEXT   "at"

#if defined(_WIN_ALL)
  #ifdef _MSC_VER
    #define _stdfunction __cdecl

    #ifdef SFX_MODULE
      // We want to keep SFX module small, so let compiler to decide.
      #define _forceinline inline
    #else
      #define _forceinline __forceinline
    #endif

  #else
    #define _stdfunction _USERENTRY
    #define _forceinline inline
  #endif
#else
  #define _stdfunction
  #define _forceinline inline
#endif

#endif

#ifdef _UNIX

#define  NM  1024

#ifdef _BEOS
#include <be/kernel/fs_info.h>
#include <be/kernel/fs_attr.h>
#endif

#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/file.h>
#if defined(__QNXNTO__)
  #include <sys/param.h>
#endif
#if defined(RAR_SMP) && defined(__APPLE__)
  #include <sys/sysctl.h>
#endif
#if defined(__FreeBSD__) || defined (__NetBSD__) || defined (__OpenBSD__) || defined(__APPLE__)
  #include <sys/param.h>
  #include <sys/mount.h>
#else
#endif
#include <pwd.h>
#include <grp.h>
#include <wchar.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include <string.h>
#include <ctype.h>
#include <fcntl.h>
#include <errno.h>
#include <dirent.h>
#include <time.h>
#include <signal.h>
#include <utime.h>
#include <locale.h>

#ifdef  S_IFLNK
#define SAVE_LINKS
#endif

#define ENABLE_ACCESS

#define DefConfigName  ".rarrc"
#define DefLogName     ".rarlog"


#define PATHDIVIDER  "/"
#define PATHDIVIDERW L"/"
#define CPATHDIVIDER '/'
#define MASKALL      "*"
#define MASKALLW     L"*"

#define READBINARY   "r"
#define READTEXT     "r"
#define UPDATEBINARY "r+"
#define CREATEBINARY "w+"
#define WRITEBINARY  "w"
#define APPENDTEXT   "a"

#define _stdfunction 
#define _forceinline inline

#ifdef _APPLE
  #if defined(__BIG_ENDIAN__) && !defined(BIG_ENDIAN)
    #define BIG_ENDIAN
    #undef LITTLE_ENDIAN
  #endif
  #if defined(__i386__) && !defined(LITTLE_ENDIAN)
    #define LITTLE_ENDIAN
    #undef BIG_ENDIAN
  #endif
#endif

#if defined(__sparc) || defined(sparc) || defined(__hpux)
  #ifndef BIG_ENDIAN
     #define BIG_ENDIAN
  #endif
#endif

#endif

  typedef const char* MSGID;

#define safebuf static

#if !defined(LITTLE_ENDIAN) && !defined(BIG_ENDIAN)
  #if defined(__i386) || defined(i386) || defined(__i386__)
    #define LITTLE_ENDIAN
  #elif defined(BYTE_ORDER) && BYTE_ORDER == LITTLE_ENDIAN
    #define LITTLE_ENDIAN
  #elif defined(BYTE_ORDER) && BYTE_ORDER == BIG_ENDIAN
    #define BIG_ENDIAN
  #else
    #error "Neither LITTLE_ENDIAN nor BIG_ENDIAN are defined. Define one of them."
  #endif
#endif

#if defined(LITTLE_ENDIAN) && defined(BIG_ENDIAN)
  #if defined(BYTE_ORDER) && BYTE_ORDER == BIG_ENDIAN
    #undef LITTLE_ENDIAN
  #elif defined(BYTE_ORDER) && BYTE_ORDER == LITTLE_ENDIAN
    #undef BIG_ENDIAN
  #else
    #error "Both LITTLE_ENDIAN and BIG_ENDIAN are defined. Undef one of them."
  #endif
#endif

#if !defined(BIG_ENDIAN) && !defined(_WIN_CE) && defined(_WIN_ALL)
// Allow not aligned integer access, increases speed in some operations.
#define ALLOW_NOT_ALIGNED_INT
#endif

#if defined(__sparc) || defined(sparc) || defined(__sparcv9)
// Prohibit not aligned access to data structures in text compression
// algorithm, increases memory requirements
#define STRICT_ALIGNMENT_REQUIRED
#endif

#endif // _RAR_OS_
