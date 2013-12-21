#ifndef _BASEAFF_HXX_
#define _BASEAFF_HXX_

#include "hunvisapi.h"

class LIBHUNSPELL_DLL_EXPORTED AffEntry
{
protected:
    char *         appnd;
    char *         strip;
    unsigned char  appndl;
    unsigned char  stripl;
    char           numconds;
    char           opts;
    unsigned short aflag;
    union {
        char       conds[MAXCONDLEN];
        struct {
            char   conds1[MAXCONDLEN_1];
            char * conds2;
        } l;
    } c;
    char *           morphcode;
    unsigned short * contclass;
    short            contclasslen;
};

#endif
