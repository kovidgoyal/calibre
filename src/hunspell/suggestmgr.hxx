#ifndef _SUGGESTMGR_HXX_
#define _SUGGESTMGR_HXX_

#define MAXSWL 100
#define MAXSWUTF8L (MAXSWL * 4)
#define MAX_ROOTS 100
#define MAX_WORDS 100
#define MAX_GUESS 200
#define MAXNGRAMSUGS 4
#define MAXPHONSUGS 2
#define MAXCOMPOUNDSUGS 3

// timelimit: max ~1/4 sec (process time on Linux) for a time consuming function
#define TIMELIMIT (CLOCKS_PER_SEC >> 2)
#define MINTIMER 100
#define MAXPLUSTIMER 100

#define NGRAM_LONGER_WORSE  (1 << 0)
#define NGRAM_ANY_MISMATCH  (1 << 1)
#define NGRAM_LOWERING      (1 << 2)
#define NGRAM_WEIGHTED      (1 << 3)

#include "hunvisapi.h"

#include "atypes.hxx"
#include "affixmgr.hxx"
#include "hashmgr.hxx"
#include "langnum.hxx"
#include <time.h>

enum { LCS_UP, LCS_LEFT, LCS_UPLEFT };

class LIBHUNSPELL_DLL_EXPORTED SuggestMgr
{
private:
  SuggestMgr(const SuggestMgr&);
  SuggestMgr& operator = (const SuggestMgr&);
private:
  char *          ckey;
  int             ckeyl;
  w_char *        ckey_utf;

  char *          ctry;
  int             ctryl;
  w_char *        ctry_utf;

  AffixMgr*       pAMgr;
  int             maxSug;
  struct cs_info * csconv;
  int             utf8;
  int             langnum;
  int             nosplitsugs;
  int             maxngramsugs;
  int             maxcpdsugs;
  int             complexprefixes;


public:
  SuggestMgr(const char * tryme, int maxn, AffixMgr *aptr);
  ~SuggestMgr();

  int suggest(char*** slst, const char * word, int nsug, int * onlycmpdsug);
  int ngsuggest(char ** wlst, char * word, int ns, HashMgr** pHMgr, int md);
  int suggest_auto(char*** slst, const char * word, int nsug);
  int suggest_stems(char*** slst, const char * word, int nsug);
  int suggest_pos_stems(char*** slst, const char * word, int nsug);

  char * suggest_morph(const char * word);
  char * suggest_gen(char ** pl, int pln, char * pattern);
  char * suggest_morph_for_spelling_error(const char * word);

private:
   int testsug(char** wlst, const char * candidate, int wl, int ns, int cpdsuggest,
     int * timer, clock_t * timelimit);
   int checkword(const char *, int, int, int *, clock_t *);
   int check_forbidden(const char *, int);

   int capchars(char **, const char *, int, int);
   int replchars(char**, const char *, int, int);
   int doubletwochars(char**, const char *, int, int);
   int forgotchar(char **, const char *, int, int);
   int swapchar(char **, const char *, int, int);
   int longswapchar(char **, const char *, int, int);
   int movechar(char **, const char *, int, int);
   int extrachar(char **, const char *, int, int);
   int badcharkey(char **, const char *, int, int);
   int badchar(char **, const char *, int, int);
   int twowords(char **, const char *, int, int);
   int fixstems(char **, const char *, int);

   int capchars_utf(char **, const w_char *, int wl, int, int);
   int doubletwochars_utf(char**, const w_char *, int wl, int, int);
   int forgotchar_utf(char**, const w_char *, int wl, int, int);
   int extrachar_utf(char**, const w_char *, int wl, int, int);
   int badcharkey_utf(char **, const w_char *, int wl, int, int);
   int badchar_utf(char **, const w_char *, int wl, int, int);
   int swapchar_utf(char **, const w_char *, int wl, int, int);
   int longswapchar_utf(char **, const w_char *, int, int, int);
   int movechar_utf(char **, const w_char *, int, int, int);

   int mapchars(char**, const char *, int, int);
   int map_related(const char *, char *, int, int, char ** wlst, int, int, const mapentry*, int, int *, clock_t *);
   int ngram(int n, char * s1, const char * s2, int opt);
   int mystrlen(const char * word);
   int leftcommonsubstring(char * s1, const char * s2);
   int commoncharacterpositions(char * s1, const char * s2, int * is_swap);
   void bubblesort( char ** rwd, char ** rwd2, int * rsc, int n);
   void lcs(const char * s, const char * s2, int * l1, int * l2, char ** result);
   int lcslen(const char * s, const char* s2);
   char * suggest_hentry_gen(hentry * rv, char * pattern);

};

#endif

