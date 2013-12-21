#ifndef _ATYPES_HXX_
#define _ATYPES_HXX_

#ifndef HUNSPELL_WARNING
#include <stdio.h>
#ifdef HUNSPELL_WARNING_ON
#define HUNSPELL_WARNING fprintf
#else
// empty inline function to switch off warnings (instead of the C99 standard variadic macros)
static inline void HUNSPELL_WARNING(FILE *, const char *, ...) {}
#endif
#endif

// HUNSTEM def.
#define HUNSTEM

#include "hashmgr.hxx"
#include "w_char.hxx"

#define SETSIZE         256
#define CONTSIZE        65536
#define MAXWORDLEN      100
#define MAXWORDUTF8LEN  256

// affentry options
#define aeXPRODUCT      (1 << 0)
#define aeUTF8          (1 << 1)
#define aeALIASF        (1 << 2)
#define aeALIASM        (1 << 3)
#define aeLONGCOND      (1 << 4)

// compound options
#define IN_CPD_NOT   0
#define IN_CPD_BEGIN 1
#define IN_CPD_END   2
#define IN_CPD_OTHER 3

// info options
#define  SPELL_COMPOUND  (1 << 0)
#define  SPELL_FORBIDDEN (1 << 1)
#define  SPELL_ALLCAP    (1 << 2)
#define  SPELL_NOCAP     (1 << 3)
#define  SPELL_INITCAP   (1 << 4)
#define  SPELL_ORIGCAP   (1 << 5)
#define  SPELL_WARN      (1 << 6)

#define MAXLNLEN        8192

#define MINCPDLEN       3
#define MAXCOMPOUND     10
#define MAXCONDLEN      20
#define MAXCONDLEN_1    (MAXCONDLEN - sizeof(char *))

#define MAXACC          1000

#define FLAG unsigned short
#define FLAG_NULL 0x00
#define FREE_FLAG(a) a = 0

#define TESTAFF( a, b , c ) flag_bsearch((unsigned short *) a, (unsigned short) b, c)

struct affentry
{
   char * strip;
   char * appnd;
   unsigned char stripl;
   unsigned char appndl;
   char  numconds;
   char  opts;
   unsigned short aflag;
   unsigned short * contclass;
   short        contclasslen;
   union {
     char conds[MAXCONDLEN];
     struct {
       char conds1[MAXCONDLEN_1];
       char * conds2;
     } l;
   } c;
   char *       morphcode;
};

struct guessword {
  char * word;
  bool allow;
  char * orig;
};

struct mapentry {
  char ** set;
  int len;
};

struct flagentry {
  FLAG * def;
  int len;
};

struct patentry {
  char * pattern;
  char * pattern2;
  char * pattern3;
  FLAG cond;
  FLAG cond2;
};

#endif
