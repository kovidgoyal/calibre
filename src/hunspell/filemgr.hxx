/* file manager class - read lines of files [filename] OR [filename.hz] */
#ifndef _FILEMGR_HXX_
#define _FILEMGR_HXX_

#include "hunvisapi.h"

class LIBHUNSPELL_DLL_EXPORTED FileMgr
{
protected:
    char *buf;
    char *pos;
    size_t buflen;
    char last;
    int linenum;

public:
    FileMgr(const char *data, const size_t dlen);
    ~FileMgr();
    char * getline();
    int getlinenum();
};
#endif
