// XUnzip.h  Version 1.3
//
// Authors:      Mark Adler et al. (see below)
//
// Modified by:  Lucian Wischik
//               lu@wischik.com
//
// Version 1.0   - Turned C files into just a single CPP file
//               - Made them compile cleanly as C++ files
//               - Gave them simpler APIs
//               - Added the ability to zip/unzip directly in memory without 
//                 any intermediate files
// 
// Modified by:  Hans Dietrich
//               hdietrich@gmail.com
//
///////////////////////////////////////////////////////////////////////////////
//
// Lucian Wischik's comments:
// --------------------------
// THIS FILE is almost entirely based upon code by info-zip.
// It has been modified by Lucian Wischik.
// The original code may be found at http://www.info-zip.org
// The original copyright text follows.
//
///////////////////////////////////////////////////////////////////////////////
//
// Original authors' comments:
// ---------------------------
// This is version 2002-Feb-16 of the Info-ZIP copyright and license. The 
// definitive version of this document should be available at 
// ftp://ftp.info-zip.org/pub/infozip/license.html indefinitely.
// 
// Copyright (c) 1990-2002 Info-ZIP.  All rights reserved.
//
// For the purposes of this copyright and license, "Info-ZIP" is defined as
// the following set of individuals:
//
//   Mark Adler, John Bush, Karl Davis, Harald Denker, Jean-Michel Dubois,
//   Jean-loup Gailly, Hunter Goatley, Ian Gorman, Chris Herborth, Dirk Haase,
//   Greg Hartwig, Robert Heath, Jonathan Hudson, Paul Kienitz, 
//   David Kirschbaum, Johnny Lee, Onno van der Linden, Igor Mandrichenko, 
//   Steve P. Miller, Sergio Monesi, Keith Owens, George Petrov, Greg Roelofs, 
//   Kai Uwe Rommel, Steve Salisbury, Dave Smith, Christian Spieler, 
//   Antoine Verheijen, Paul von Behren, Rich Wales, Mike White
//
// This software is provided "as is", without warranty of any kind, express
// or implied.  In no event shall Info-ZIP or its contributors be held liable
// for any direct, indirect, incidental, special or consequential damages
// arising out of the use of or inability to use this software.
//
// Permission is granted to anyone to use this software for any purpose,
// including commercial applications, and to alter it and redistribute it
// freely, subject to the following restrictions:
//
//    1. Redistributions of source code must retain the above copyright notice,
//       definition, disclaimer, and this list of conditions.
//
//    2. Redistributions in binary form (compiled executables) must reproduce 
//       the above copyright notice, definition, disclaimer, and this list of 
//       conditions in documentation and/or other materials provided with the 
//       distribution. The sole exception to this condition is redistribution 
//       of a standard UnZipSFX binary as part of a self-extracting archive; 
//       that is permitted without inclusion of this license, as long as the 
//       normal UnZipSFX banner has not been removed from the binary or disabled.
//
//    3. Altered versions--including, but not limited to, ports to new 
//       operating systems, existing ports with new graphical interfaces, and 
//       dynamic, shared, or static library versions--must be plainly marked 
//       as such and must not be misrepresented as being the original source.  
//       Such altered versions also must not be misrepresented as being 
//       Info-ZIP releases--including, but not limited to, labeling of the 
//       altered versions with the names "Info-ZIP" (or any variation thereof, 
//       including, but not limited to, different capitalizations), 
//       "Pocket UnZip", "WiZ" or "MacZip" without the explicit permission of 
//       Info-ZIP.  Such altered versions are further prohibited from 
//       misrepresentative use of the Zip-Bugs or Info-ZIP e-mail addresses or 
//       of the Info-ZIP URL(s).
//
//    4. Info-ZIP retains the right to use the names "Info-ZIP", "Zip", "UnZip",
//       "UnZipSFX", "WiZ", "Pocket UnZip", "Pocket Zip", and "MacZip" for its 
//       own source and binary releases.
//
///////////////////////////////////////////////////////////////////////////////

#ifndef XUNZIP_H
#define XUNZIP_H


#ifndef XZIP_H
DECLARE_HANDLE(HZIP);	// An HZIP identifies a zip file that has been opened
#endif

typedef DWORD ZRESULT;
// return codes from any of the zip functions. Listed later.

#define ZIP_HANDLE   1
#define ZIP_FILENAME 2
#define ZIP_MEMORY   3

typedef struct
{ int index;                 // index of this file within the zip
  char name[MAX_PATH];       // filename within the zip
  DWORD attr;                // attributes, as in GetFileAttributes.
  FILETIME atime,ctime,mtime;// access, create, modify filetimes
  long comp_size;            // sizes of item, compressed and uncompressed. These
  long unc_size;             // may be -1 if not yet known (e.g. being streamed in)
} ZIPENTRY;

typedef struct
{ int index;                 // index of this file within the zip
  TCHAR name[MAX_PATH];      // filename within the zip
  DWORD attr;                // attributes, as in GetFileAttributes.
  FILETIME atime,ctime,mtime;// access, create, modify filetimes
  long comp_size;            // sizes of item, compressed and uncompressed. These
  long unc_size;             // may be -1 if not yet known (e.g. being streamed in)
} ZIPENTRYW;


///////////////////////////////////////////////////////////////////////////////
//
// OpenZip()
//
// Purpose:     Open an existing zip archive file
//
// Parameters:  z      - archive file name if flags is ZIP_FILENAME;  for other
//                       uses see below
//              len    - for memory (ZIP_MEMORY) should be the buffer size;
//                       for other uses, should be 0
//              flags  - indicates usage, see below;  for files, this will be
//                       ZIP_FILENAME
//
// Returns:     HZIP   - non-zero if zip archive opened ok, otherwise 0
//
HZIP OpenZip(void *z, unsigned int len, DWORD flags);
// OpenZip - opens a zip file and returns a handle with which you can
// subsequently examine its contents. You can open a zip file from:
// from a pipe:             OpenZip(hpipe_read,0, ZIP_HANDLE);
// from a file (by handle): OpenZip(hfile,0,      ZIP_HANDLE);
// from a file (by name):   OpenZip("c:\\test.zip",0, ZIP_FILENAME);
// from a memory block:     OpenZip(bufstart, buflen, ZIP_MEMORY);
// If the file is opened through a pipe, then items may only be
// accessed in increasing order, and an item may only be unzipped once,
// although GetZipItem can be called immediately before and after unzipping
// it. If it's opened i	n any other way, then full random access is possible.
// Note: pipe input is not yet implemented.


///////////////////////////////////////////////////////////////////////////////
//
// GetZipItem()
//
// Purpose:     Get information about an item in an open zip archive
//
// Parameters:  hz      - handle of open zip archive
//              index   - index number (0 based) of item in zip 
//              ze      - pointer to a ZIPENTRY (if ANSI) or ZIPENTRYW struct
//                        (if Unicode)
//
// Returns:     ZRESULT - ZR_OK if success, otherwise some other value
//

#ifdef _UNICODE
#define GetZipItem GetZipItemW
#else
#define GetZipItem GetZipItemA
#endif

ZRESULT GetZipItemA(HZIP hz, int index, ZIPENTRY *ze);
ZRESULT GetZipItemW(HZIP hz, int index, ZIPENTRYW *ze);
// GetZipItem - call this to get information about an item in the zip.
// If index is -1 and the file wasn't opened through a pipe,
// then it returns information about the whole zipfile
// (and in particular ze.index returns the number of index items).
// Note: the item might be a directory (ze.attr & FILE_ATTRIBUTE_DIRECTORY)
// See below for notes on what happens when you unzip such an item.
// Note: if you are opening the zip through a pipe, then random access
// is not possible and GetZipItem(-1) fails and you can't discover the number
// of items except by calling GetZipItem on each one of them in turn,
// starting at 0, until eventually the call fails. Also, in the event that
// you are opening through a pipe and the zip was itself created into a pipe,
// then then comp_size and sometimes unc_size as well may not be known until
// after the item has been unzipped.


///////////////////////////////////////////////////////////////////////////////
//
// FindZipItem()
//
// Purpose:     Find item by name and return information about it
//
// Parameters:  hz      - handle of open zip archive
//              name    - name of file to look for inside zip archive
//              ic      - TRUE = case insensitive
//              index   - pointer to index number returned, or -1
//              ze      - pointer to a ZIPENTRY (if ANSI) or ZIPENTRYW struct
//                        (if Unicode)
//
// Returns:     ZRESULT - ZR_OK if success, otherwise some other value
//

#ifdef _UNICODE
#define FindZipItem FindZipItemW
#else
#define FindZipItem FindZipItemA
#endif

ZRESULT FindZipItemA(HZIP hz, const TCHAR *name, bool ic, int *index, ZIPENTRY *ze);
ZRESULT FindZipItemW(HZIP hz, const TCHAR *name, bool ic, int *index, ZIPENTRYW *ze);
// FindZipItem - finds an item by name. ic means 'insensitive to case'.
// It returns the index of the item, and returns information about it.
// If nothing was found, then index is set to -1 and the function returns
// an error code.


///////////////////////////////////////////////////////////////////////////////
//
// UnzipItem()
//
// Purpose:     Find item by index and unzip it
//
// Parameters:  hz      - handle of open zip archive
//              index   - index number of file to unzip
//              dst     - target file name of unzipped file
//              len     - for memory (ZIP_MEMORY. length of buffer;
//                        otherwise 0
//              flags   - indicates usage, see below;  for files, this will be
//                        ZIP_FILENAME
//
// Returns:     ZRESULT - ZR_OK if success, otherwise some other value
//

ZRESULT UnzipItem(HZIP hz, int index, void *dst, unsigned int len, DWORD flags);
// UnzipItem - given an index to an item, unzips it. You can unzip to:
// to a pipe:             UnzipItem(hz,i, hpipe_write,0,ZIP_HANDLE);
// to a file (by handle): UnzipItem(hz,i, hfile,0,ZIP_HANDLE);
// to a file (by name):   UnzipItem(hz,i, ze.name,0,ZIP_FILENAME);
// to a memory block:     UnzipItem(hz,i, buf,buflen,ZIP_MEMORY);
// In the final case, if the buffer isn't large enough to hold it all,
// then the return code indicates that more is yet to come. If it was
// large enough, and you want to know precisely how big, GetZipItem.
// Note: zip files are normally stored with relative pathnames. If you
// unzip with ZIP_FILENAME a relative pathname then the item gets created
// relative to the current directory - it first ensures that all necessary
// subdirectories have been created. Also, the item may itself be a directory.
// If you unzip a directory with ZIP_FILENAME, then the directory gets created.
// If you unzip it to a handle or a memory block, then nothing gets created
// and it emits 0 bytes.


///////////////////////////////////////////////////////////////////////////////
//
// CloseZip()
//
// Purpose:     Close an open zip archive
//
// Parameters:  hz      - handle to an open zip archive
//
// Returns:     ZRESULT - ZR_OK if success, otherwise some other value
//
ZRESULT CloseZip(HZIP hz);
// CloseZip - the zip handle must be closed with this function.

unsigned int FormatZipMessage(ZRESULT code, char *buf,unsigned int len);
// FormatZipMessage - given an error code, formats it as a string.
// It returns the length of the error message. If buf/len points
// to a real buffer, then it also writes as much as possible into there.


// These are the result codes:
#define ZR_OK         0x00000000     // nb. the pseudo-code zr-recent is never returned,
#define ZR_RECENT     0x00000001     // but can be passed to FormatZipMessage.
// The following come from general system stuff (e.g. files not openable)
#define ZR_GENMASK    0x0000FF00
#define ZR_NODUPH     0x00000100     // couldn't duplicate the handle
#define ZR_NOFILE     0x00000200     // couldn't create/open the file
#define ZR_NOALLOC    0x00000300     // failed to allocate some resource
#define ZR_WRITE      0x00000400     // a general error writing to the file
#define ZR_NOTFOUND   0x00000500     // couldn't find that file in the zip
#define ZR_MORE       0x00000600     // there's still more data to be unzipped
#define ZR_CORRUPT    0x00000700     // the zipfile is corrupt or not a zipfile
#define ZR_READ       0x00000800     // a general error reading the file
// The following come from mistakes on the part of the caller
#define ZR_CALLERMASK 0x00FF0000
#define ZR_ARGS       0x00010000     // general mistake with the arguments
#define ZR_NOTMMAP    0x00020000     // tried to ZipGetMemory, but that only works on mmap zipfiles, which yours wasn't
#define ZR_MEMSIZE    0x00030000     // the memory size is too small
#define ZR_FAILED     0x00040000     // the thing was already failed when you called this function
#define ZR_ENDED      0x00050000     // the zip creation has already been closed
#define ZR_MISSIZE    0x00060000     // the indicated input file size turned out mistaken
#define ZR_PARTIALUNZ 0x00070000     // the file had already been partially unzipped
#define ZR_ZMODE      0x00080000     // tried to mix creating/opening a zip 
// The following come from bugs within the zip library itself
#define ZR_BUGMASK    0xFF000000
#define ZR_NOTINITED  0x01000000     // initialisation didn't work
#define ZR_SEEK       0x02000000     // trying to seek in an unseekable file
#define ZR_NOCHANGE   0x04000000     // changed its mind on storage, but not allowed
#define ZR_FLATE      0x05000000     // an internal error in the de/inflation code





// e.g.
//
// SetCurrentDirectory("c:\\docs\\stuff");
// HZIP hz = OpenZip("c:\\stuff.zip",0,ZIP_FILENAME);
// ZIPENTRY ze; GetZipItem(hz,-1,&ze); int numitems=ze.index;
// for (int i=0; i<numitems; i++)
// { GetZipItem(hz,i,&ze);
//   UnzipItem(hz,i,ze.name,0,ZIP_FILENAME);
// }
// CloseZip(hz);
//
//
// HRSRC hrsrc = FindResource(hInstance,MAKEINTRESOURCE(1),RT_RCDATA);
// HANDLE hglob = LoadResource(hInstance,hrsrc);
// void *zipbuf=LockResource(hglob);
// unsigned int ziplen=SizeofResource(hInstance,hrsrc);
// HZIP hz = OpenZip(zipbuf, ziplen, ZIP_MEMORY);
//   - unzip to a membuffer -
// ZIPENTRY ze; int i; FindZipItem(hz,"file.dat",&i,&ze);
// char *ibuf = new char[ze.unc_size];
// UnzipItem(hz,i, ibuf, ze.unc_size,ZIP_MEMORY);
// delete[] buf;
//   - unzip to a fixed membuff -
// ZIPENTRY ze; int i; FindZipItem(hz,"file.dat",&i,&ze);
// char ibuf[1024]; ZIPRESULT zr=ZR_MORE; unsigned long totsize=0;
// while (zr==ZR_MORE)
// { zr = UnzipItem(hz,i, ibuf,1024,ZIP_MEMORY);
//   unsigned long bufsize=1024; if (zr==ZR_OK) bufsize=ze.unc_size-totsize;
//   totsize+=bufsize;
// }
//   - unzip to a pipe -
// HANDLE hthread=CreateWavReaderThread(&hread,&hwrite);
// FindZipItem(hz,"sound.wav",&i,&ze);
// UnzipItem(hz,i, hwrite,0,ZIP_HANDLE);
// CloseHandle(hwrite);
// WaitForSingleObject(hthread,INFINITE);
// CloseHandle(hread); CloseHandle(hthread);
//   - finished -
// CloseZip(hz);
// // note: no need to free resources obtained through Find/Load/LockResource
//
//
// SetCurrentDirectory("c:\\docs\\pipedzipstuff");
// HANDLE hread,hwrite; CreatePipe(&hread,&hwrite);
// CreateZipWriterThread(hwrite);
// HZIP hz = OpenZip(hread,0,ZIP_HANDLE);
// for (int i=0; ; i++)
// { ZIPENTRY ze; ZRESULT res = GetZipItem(hz,i,&ze);
//   if (res!=ZE_OK) break; // no more
//   UnzipItem(hz,i, ze.name,0,ZIP_FILENAME);
// }
// CloseZip(hz);
//




// Now we indulge in a little skullduggery so that the code works whether
// the user has included just zip or both zip and unzip.
// Idea: if header files for both zip and unzip are present, then presumably
// the cpp files for zip and unzip are both present, so we will call
// one or the other of them based on a dynamic choice. If the header file
// for only one is present, then we will bind to that particular one.
HZIP OpenZipU(void *z,unsigned int len,DWORD flags);
ZRESULT CloseZipU(HZIP hz);
unsigned int FormatZipMessageU(ZRESULT code, char *buf,unsigned int len);
bool IsZipHandleU(HZIP hz);
#define OpenZip OpenZipU

#ifdef XZIP_H
#undef CloseZip
#define CloseZip(hz) (IsZipHandleU(hz)?CloseZipU(hz):CloseZipZ(hz))
#else
#define CloseZip CloseZipU
#define FormatZipMessage FormatZipMessageU
#endif


#endif //XUNZIP_H
