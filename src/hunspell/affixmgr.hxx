#ifndef _AFFIXMGR_HXX_
#define _AFFIXMGR_HXX_

#include "hunvisapi.h"

#include <stdio.h>

#include "atypes.hxx"
#include "baseaffix.hxx"
#include "hashmgr.hxx"
#include "phonet.hxx"
#include "replist.hxx"

// check flag duplication
#define dupSFX        (1 << 0)
#define dupPFX        (1 << 1)

class PfxEntry;
class SfxEntry;

class LIBHUNSPELL_DLL_EXPORTED AffixMgr
{

  PfxEntry *          pStart[SETSIZE];
  SfxEntry *          sStart[SETSIZE];
  PfxEntry *          pFlag[SETSIZE];
  SfxEntry *          sFlag[SETSIZE];
  HashMgr *           pHMgr;
  HashMgr **          alldic;
  int *               maxdic;
  char *              keystring;
  char *              trystring;
  char *              encoding;
  struct cs_info *    csconv;
  int                 utf8;
  int                 complexprefixes;
  FLAG                compoundflag;
  FLAG                compoundbegin;
  FLAG                compoundmiddle;
  FLAG                compoundend;
  FLAG                compoundroot;
  FLAG                compoundforbidflag;
  FLAG                compoundpermitflag;
  int                 checkcompounddup;
  int                 checkcompoundrep;
  int                 checkcompoundcase;
  int                 checkcompoundtriple;
  int                 simplifiedtriple;
  FLAG                forbiddenword;
  FLAG                nosuggest;
  FLAG                nongramsuggest;
  FLAG                needaffix;
  int                 cpdmin;
  int                 numrep;
  replentry *         reptable;
  RepList *           iconvtable;
  RepList *           oconvtable;
  int                 nummap;
  mapentry *          maptable;
  int                 numbreak;
  char **             breaktable;
  int                 numcheckcpd;
  patentry *          checkcpdtable;
  int                 simplifiedcpd;
  int                 numdefcpd;
  flagentry *         defcpdtable;
  phonetable *        phone;
  int                 maxngramsugs;
  int                 maxcpdsugs;
  int                 maxdiff;
  int                 onlymaxdiff;
  int                 nosplitsugs;
  int                 sugswithdots;
  int                 cpdwordmax;
  int                 cpdmaxsyllable;
  char *              cpdvowels;
  w_char *            cpdvowels_utf16;
  int                 cpdvowels_utf16_len;
  char *              cpdsyllablenum;
  const char *        pfxappnd; // BUG: not stateless
  const char *        sfxappnd; // BUG: not stateless
  FLAG                sfxflag;  // BUG: not stateless
  char *              derived;  // BUG: not stateless
  SfxEntry *          sfx;      // BUG: not stateless
  PfxEntry *          pfx;      // BUG: not stateless
  int                 checknum;
  char *              wordchars;
  unsigned short *    wordchars_utf16;
  int                 wordchars_utf16_len;
  char *              ignorechars;
  unsigned short *    ignorechars_utf16;
  int                 ignorechars_utf16_len;
  char *              version;
  char *              lang;
  int                 langnum;
  FLAG                lemma_present;
  FLAG                circumfix;
  FLAG                onlyincompound;
  FLAG                keepcase;
  FLAG                forceucase;
  FLAG                warn;
  int                 forbidwarn;
  FLAG                substandard;
  int                 checksharps;
  int                 fullstrip;

  int                 havecontclass; // boolean variable
  char                contclasses[CONTSIZE]; // flags of possible continuing classes (twofold affix)

public:

  AffixMgr(const char * affpath, HashMgr** ptr, int * md,
    const char * key = NULL);
  ~AffixMgr();
  struct hentry *     affix_check(const char * word, int len,
            const unsigned short needflag = (unsigned short) 0,
            char in_compound = IN_CPD_NOT);
  struct hentry *     prefix_check(const char * word, int len,
            char in_compound, const FLAG needflag = FLAG_NULL);
  inline int isSubset(const char * s1, const char * s2);
  struct hentry *     prefix_check_twosfx(const char * word, int len,
            char in_compound, const FLAG needflag = FLAG_NULL);
  inline int isRevSubset(const char * s1, const char * end_of_s2, int len);
  struct hentry *     suffix_check(const char * word, int len, int sfxopts,
            PfxEntry* ppfx, char ** wlst, int maxSug, int * ns,
            const FLAG cclass = FLAG_NULL, const FLAG needflag = FLAG_NULL,
            char in_compound = IN_CPD_NOT);
  struct hentry *     suffix_check_twosfx(const char * word, int len,
            int sfxopts, PfxEntry* ppfx, const FLAG needflag = FLAG_NULL);

  char * affix_check_morph(const char * word, int len,
            const FLAG needflag = FLAG_NULL, char in_compound = IN_CPD_NOT);
  char * prefix_check_morph(const char * word, int len,
            char in_compound, const FLAG needflag = FLAG_NULL);
  char * suffix_check_morph (const char * word, int len, int sfxopts,
            PfxEntry * ppfx, const FLAG cclass = FLAG_NULL,
            const FLAG needflag = FLAG_NULL, char in_compound = IN_CPD_NOT);

  char * prefix_check_twosfx_morph(const char * word, int len,
            char in_compound, const FLAG needflag = FLAG_NULL);
  char * suffix_check_twosfx_morph(const char * word, int len,
            int sfxopts, PfxEntry * ppfx, const FLAG needflag = FLAG_NULL);

  char * morphgen(char * ts, int wl, const unsigned short * ap,
            unsigned short al, char * morph, char * targetmorph, int level);

  int    expand_rootword(struct guessword * wlst, int maxn, const char * ts,
            int wl, const unsigned short * ap, unsigned short al, char * bad,
            int, char *);

  short       get_syllable (const char * word, int wlen);
  int         cpdrep_check(const char * word, int len);
  int         cpdpat_check(const char * word, int len, hentry * r1, hentry * r2,
                    const char affixed);
  int         defcpd_check(hentry *** words, short wnum, hentry * rv,
                    hentry ** rwords, char all);
  int         cpdcase_check(const char * word, int len);
  inline int  candidate_check(const char * word, int len);
  void        setcminmax(int * cmin, int * cmax, const char * word, int len);
  struct hentry * compound_check(const char * word, int len, short wordnum,
            short numsyllable, short maxwordnum, short wnum, hentry ** words,
            char hu_mov_rule, char is_sug, int * info);

  int compound_check_morph(const char * word, int len, short wordnum,
            short numsyllable, short maxwordnum, short wnum, hentry ** words,
            char hu_mov_rule, char ** result, char * partresult);

  struct hentry * lookup(const char * word);
  int                 get_numrep() const;
  struct replentry *  get_reptable() const;
  RepList *           get_iconvtable() const;
  RepList *           get_oconvtable() const;
  struct phonetable * get_phonetable() const;
  int                 get_nummap() const;
  struct mapentry *   get_maptable() const;
  int                 get_numbreak() const;
  char **             get_breaktable() const;
  char *              get_encoding();
  int                 get_langnum() const;
  char *              get_key_string();
  char *              get_try_string() const;
  const char *        get_wordchars() const;
  unsigned short *    get_wordchars_utf16(int * len) const;
  char *              get_ignore() const;
  unsigned short *    get_ignore_utf16(int * len) const;
  int                 get_compound() const;
  FLAG                get_compoundflag() const;
  FLAG                get_compoundbegin() const;
  FLAG                get_forbiddenword() const;
  FLAG                get_nosuggest() const;
  FLAG                get_nongramsuggest() const;
  FLAG                get_needaffix() const;
  FLAG                get_onlyincompound() const;
  FLAG                get_compoundroot() const;
  FLAG                get_lemma_present() const;
  int                 get_checknum() const;
  const char *        get_prefix() const;
  const char *        get_suffix() const;
  const char *        get_derived() const;
  const char *        get_version() const;
  int                 have_contclass() const;
  int                 get_utf8() const;
  int                 get_complexprefixes() const;
  char *              get_suffixed(char ) const;
  int                 get_maxngramsugs() const;
  int                 get_maxcpdsugs() const;
  int                 get_maxdiff() const;
  int                 get_onlymaxdiff() const;
  int                 get_nosplitsugs() const;
  int                 get_sugswithdots(void) const;
  FLAG                get_keepcase(void) const;
  FLAG                get_forceucase(void) const;
  FLAG                get_warn(void) const;
  int                 get_forbidwarn(void) const;
  int                 get_checksharps(void) const;
  char *              encode_flag(unsigned short aflag) const;
  int                 get_fullstrip() const;

private:
  int  parse_file(const char * affpath, const char * key);
  int  parse_flag(char * line, unsigned short * out, FileMgr * af);
  int  parse_num(char * line, int * out, FileMgr * af);
  int  parse_cpdsyllable(char * line, FileMgr * af);
  int  parse_reptable(char * line, FileMgr * af);
  int  parse_convtable(char * line, FileMgr * af, RepList ** rl, const char * keyword);
  int  parse_phonetable(char * line, FileMgr * af);
  int  parse_maptable(char * line, FileMgr * af);
  int  parse_breaktable(char * line, FileMgr * af);
  int  parse_checkcpdtable(char * line, FileMgr * af);
  int  parse_defcpdtable(char * line, FileMgr * af);
  int  parse_affix(char * line, const char at, FileMgr * af, char * dupflags);

  void reverse_condition(char *);
  void debugflag(char * result, unsigned short flag);
  int condlen(char *);
  int encodeit(affentry &entry, char * cs);
  int build_pfxtree(PfxEntry* pfxptr);
  int build_sfxtree(SfxEntry* sfxptr);
  int process_pfx_order();
  int process_sfx_order();
  PfxEntry * process_pfx_in_order(PfxEntry * ptr, PfxEntry * nptr);
  SfxEntry * process_sfx_in_order(SfxEntry * ptr, SfxEntry * nptr);
  int process_pfx_tree_to_list();
  int process_sfx_tree_to_list();
  int redundant_condition(char, char * strip, int stripl,
      const char * cond, int);
};

#endif

