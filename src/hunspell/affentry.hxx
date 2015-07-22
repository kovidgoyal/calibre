#ifndef _AFFIX_HXX_
#define _AFFIX_HXX_

#include "hunvisapi.h"

#include "atypes.hxx"
#include "baseaffix.hxx"
#include "affixmgr.hxx"

/* A Prefix Entry  */

class LIBHUNSPELL_DLL_EXPORTED PfxEntry : protected AffEntry
{
private:
       PfxEntry(const PfxEntry&);
       PfxEntry& operator = (const PfxEntry&);
private:
       AffixMgr*    pmyMgr;

       PfxEntry * next;
       PfxEntry * nexteq;
       PfxEntry * nextne;
       PfxEntry * flgnxt;

public:

  PfxEntry(AffixMgr* pmgr, affentry* dp );
  ~PfxEntry();

  inline bool          allowCross() { return ((opts & aeXPRODUCT) != 0); }
  struct hentry *      checkword(const char * word, int len, char in_compound, 
                            const FLAG needflag = FLAG_NULL);

  struct hentry *      check_twosfx(const char * word, int len, char in_compound, const FLAG needflag = FLAG_NULL);

  char *      check_morph(const char * word, int len, char in_compound,
                            const FLAG needflag = FLAG_NULL);

  char *      check_twosfx_morph(const char * word, int len,
                  char in_compound, const FLAG needflag = FLAG_NULL);

  inline FLAG getFlag()   { return aflag;   }
  inline const char *  getKey()    { return appnd;  } 
  char *               add(const char * word, int len);

  inline short getKeyLen() { return appndl; } 

  inline const char *  getMorph()    { return morphcode;  } 

  inline const unsigned short * getCont()    { return contclass;  } 
  inline short           getContLen()    { return contclasslen;  } 

  inline PfxEntry *    getNext()   { return next;   }
  inline PfxEntry *    getNextNE() { return nextne; }
  inline PfxEntry *    getNextEQ() { return nexteq; }
  inline PfxEntry *    getFlgNxt() { return flgnxt; }

  inline void   setNext(PfxEntry * ptr)   { next = ptr;   }
  inline void   setNextNE(PfxEntry * ptr) { nextne = ptr; }
  inline void   setNextEQ(PfxEntry * ptr) { nexteq = ptr; }
  inline void   setFlgNxt(PfxEntry * ptr) { flgnxt = ptr; }
  
  inline char * nextchar(char * p);
  inline int    test_condition(const char * st);
};




/* A Suffix Entry */

class LIBHUNSPELL_DLL_EXPORTED SfxEntry : protected AffEntry
{
private:
       SfxEntry(const SfxEntry&);
       SfxEntry& operator = (const SfxEntry&);
private:
       AffixMgr*    pmyMgr;
       char *       rappnd;

       SfxEntry *   next;
       SfxEntry *   nexteq;
       SfxEntry *   nextne;
       SfxEntry *   flgnxt;
           
       SfxEntry *   l_morph;
       SfxEntry *   r_morph;
       SfxEntry *   eq_morph;

public:

  SfxEntry(AffixMgr* pmgr, affentry* dp );
  ~SfxEntry();

  inline bool          allowCross() { return ((opts & aeXPRODUCT) != 0); }
  struct hentry *   checkword(const char * word, int len, int optflags, 
                    PfxEntry* ppfx, char ** wlst, int maxSug, int * ns,
//                    const FLAG cclass = FLAG_NULL, const FLAG needflag = FLAG_NULL, char in_compound=IN_CPD_NOT);
                    const FLAG cclass = FLAG_NULL, const FLAG needflag = FLAG_NULL, const FLAG badflag = 0);

  struct hentry *   check_twosfx(const char * word, int len, int optflags, PfxEntry* ppfx, const FLAG needflag = FLAG_NULL);

  char *      check_twosfx_morph(const char * word, int len, int optflags,
                 PfxEntry* ppfx, const FLAG needflag = FLAG_NULL);
  struct hentry * get_next_homonym(struct hentry * he);
  struct hentry * get_next_homonym(struct hentry * word, int optflags, PfxEntry* ppfx, 
    const FLAG cclass, const FLAG needflag);


  inline FLAG getFlag()   { return aflag;   }
  inline const char *  getKey()    { return rappnd; } 
  char *               add(const char * word, int len);


  inline const char *  getMorph()    { return morphcode;  } 

  inline const unsigned short * getCont()    { return contclass;  } 
  inline short           getContLen()    { return contclasslen;  } 
  inline const char *  getAffix()    { return appnd; } 

  inline short getKeyLen() { return appndl; } 

  inline SfxEntry *    getNext()   { return next;   }
  inline SfxEntry *    getNextNE() { return nextne; }
  inline SfxEntry *    getNextEQ() { return nexteq; }

  inline SfxEntry *    getLM() { return l_morph; }
  inline SfxEntry *    getRM() { return r_morph; }
  inline SfxEntry *    getEQM() { return eq_morph; }
  inline SfxEntry *    getFlgNxt() { return flgnxt; }

  inline void   setNext(SfxEntry * ptr)   { next = ptr;   }
  inline void   setNextNE(SfxEntry * ptr) { nextne = ptr; }
  inline void   setNextEQ(SfxEntry * ptr) { nexteq = ptr; }
  inline void   setFlgNxt(SfxEntry * ptr) { flgnxt = ptr; }

  inline char * nextchar(char * p);
  inline int    test_condition(const char * st, const char * begin);

};

#endif


