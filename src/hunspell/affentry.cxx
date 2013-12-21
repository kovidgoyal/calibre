#include "license.hunspell"
#include "license.myspell"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include <ctype.h>

#include "affentry.hxx"
#include "csutil.hxx"

PfxEntry::PfxEntry(AffixMgr* pmgr, affentry* dp)
{
  // register affix manager
  pmyMgr = pmgr;

  // set up its initial values

  aflag = dp->aflag;         // flag
  strip = dp->strip;         // string to strip
  appnd = dp->appnd;         // string to append
  stripl = dp->stripl;       // length of strip string
  appndl = dp->appndl;       // length of append string
  numconds = dp->numconds;   // length of the condition
  opts = dp->opts;           // cross product flag
  // then copy over all of the conditions
  if (opts & aeLONGCOND) {
    memcpy(c.conds, dp->c.l.conds1, MAXCONDLEN_1);
    c.l.conds2 = dp->c.l.conds2;
  } else memcpy(c.conds, dp->c.conds, MAXCONDLEN);
  next = NULL;
  nextne = NULL;
  nexteq = NULL;
  morphcode = dp->morphcode;
  contclass = dp->contclass;
  contclasslen = dp->contclasslen;
}


PfxEntry::~PfxEntry()
{
    aflag = 0;
    if (appnd) free(appnd);
    if (strip) free(strip);
    pmyMgr = NULL;
    appnd = NULL;
    strip = NULL;
    if (opts & aeLONGCOND) free(c.l.conds2);
    if (morphcode && !(opts & aeALIASM)) free(morphcode);
    if (contclass && !(opts & aeALIASF)) free(contclass);
}

// add prefix to this word assuming conditions hold
char * PfxEntry::add(const char * word, int len)
{
    char tword[MAXWORDUTF8LEN + 4];

    if ((len > stripl || (len == 0 && pmyMgr->get_fullstrip())) && 
       (len >= numconds) && test_condition(word) &&
       (!stripl || (strncmp(word, strip, stripl) == 0)) &&
       ((MAXWORDUTF8LEN + 4) > (len + appndl - stripl))) {
    /* we have a match so add prefix */
              char * pp = tword;
              if (appndl) {
                  strcpy(tword,appnd);
                  pp += appndl;
               }
               strcpy(pp, (word + stripl));
               return mystrdup(tword);
     }
     return NULL;
}

inline char * PfxEntry::nextchar(char * p) {
    if (p) {
        p++;
        if (opts & aeLONGCOND) {
            // jump to the 2nd part of the condition
            if (p == c.conds + MAXCONDLEN_1) return c.l.conds2;
        // end of the MAXCONDLEN length condition
        } else if (p == c.conds + MAXCONDLEN) return NULL;
	return *p ? p : NULL;
    }
    return NULL;
}

inline int PfxEntry::test_condition(const char * st)
{
    const char * pos = NULL; // group with pos input position
    bool neg = false;        // complementer
    bool ingroup = false;    // character in the group
    if (numconds == 0) return 1;
    char * p = c.conds;
    while (1) {
      switch (*p) {
        case '\0': return 1;
        case '[': { 
                neg = false;
                ingroup = false;
                p = nextchar(p);
                pos = st; break;
            }
        case '^': { p = nextchar(p); neg = true; break; }
        case ']': { 
                if ((neg && ingroup) || (!neg && !ingroup)) return 0;
                pos = NULL;
                p = nextchar(p);
                // skip the next character
                if (!ingroup && *st) for (st++; (opts & aeUTF8) && (*st & 0xc0) == 0x80; st++);
                if (*st == '\0' && p) return 0; // word <= condition
                break;
            }
         case '.': if (!pos) { // dots are not metacharacters in groups: [.]
                p = nextchar(p);
                // skip the next character
                for (st++; (opts & aeUTF8) && (*st & 0xc0) == 0x80; st++);
                if (*st == '\0' && p) return 0; // word <= condition
                break;
            }
    default: {
                if (*st == *p) {
                    st++;
                    p = nextchar(p);
                    if ((opts & aeUTF8) && (*(st - 1) & 0x80)) { // multibyte
                        while (p && (*p & 0xc0) == 0x80) {       // character
                            if (*p != *st) {
                                if (!pos) return 0;
                                st = pos;
                                break;
                            }
                            p = nextchar(p);
                            st++;
                        }
                        if (pos && st != pos) {
                            ingroup = true;
                            while (p && *p != ']' && (p = nextchar(p)));
                        }
                    } else if (pos) {
                        ingroup = true;
                        while (p && *p != ']' && (p = nextchar(p)));
                    }
                } else if (pos) { // group
                    p = nextchar(p);
                } else return 0;
            }
      }
      if (!p) return 1;
    }
}

// check if this prefix entry matches
struct hentry * PfxEntry::checkword(const char * word, int len, char in_compound, const FLAG needflag)
{
    int                 tmpl;   // length of tmpword
    struct hentry *     he;     // hash entry of root word or NULL
    char                tmpword[MAXWORDUTF8LEN + 4];

    // on entry prefix is 0 length or already matches the beginning of the word.
    // So if the remaining root word has positive length
    // and if there are enough chars in root word and added back strip chars
    // to meet the number of characters conditions, then test it

     tmpl = len - appndl;

     if (tmpl > 0 || (tmpl == 0 && pmyMgr->get_fullstrip())) {

            // generate new root word by removing prefix and adding
            // back any characters that would have been stripped

            if (stripl) strcpy (tmpword, strip);
            strcpy ((tmpword + stripl), (word + appndl));

            // now make sure all of the conditions on characters
            // are met.  Please see the appendix at the end of
            // this file for more info on exactly what is being
            // tested

            // if all conditions are met then check if resulting
            // root word in the dictionary

            if (test_condition(tmpword)) {
                tmpl += stripl;
                if ((he = pmyMgr->lookup(tmpword)) != NULL) {
                   do {
                      if (TESTAFF(he->astr, aflag, he->alen) &&
                        // forbid single prefixes with needaffix flag
                        ! TESTAFF(contclass, pmyMgr->get_needaffix(), contclasslen) &&
                        // needflag
                        ((!needflag) || TESTAFF(he->astr, needflag, he->alen) ||
                         (contclass && TESTAFF(contclass, needflag, contclasslen))))
                            return he;
                      he = he->next_homonym; // check homonyms
                   } while (he);
                }

                // prefix matched but no root word was found
                // if aeXPRODUCT is allowed, try again but now
                // ross checked combined with a suffix

                //if ((opts & aeXPRODUCT) && in_compound) {
                if ((opts & aeXPRODUCT)) {
                   he = pmyMgr->suffix_check(tmpword, tmpl, aeXPRODUCT, this, NULL,
                        0, NULL, FLAG_NULL, needflag, in_compound);
                   if (he) return he;
                }
            }
     }
    return NULL;
}

// check if this prefix entry matches
struct hentry * PfxEntry::check_twosfx(const char * word, int len,
    char in_compound, const FLAG needflag)
{
    int                 tmpl;   // length of tmpword
    struct hentry *     he;     // hash entry of root word or NULL
    char                tmpword[MAXWORDUTF8LEN + 4];

    // on entry prefix is 0 length or already matches the beginning of the word.
    // So if the remaining root word has positive length
    // and if there are enough chars in root word and added back strip chars
    // to meet the number of characters conditions, then test it

     tmpl = len - appndl;

     if ((tmpl > 0 || (tmpl == 0 && pmyMgr->get_fullstrip())) &&
        (tmpl + stripl >= numconds)) {

            // generate new root word by removing prefix and adding
            // back any characters that would have been stripped

            if (stripl) strcpy (tmpword, strip);
            strcpy ((tmpword + stripl), (word + appndl));

            // now make sure all of the conditions on characters
            // are met.  Please see the appendix at the end of
            // this file for more info on exactly what is being
            // tested

            // if all conditions are met then check if resulting
            // root word in the dictionary

            if (test_condition(tmpword)) {
                tmpl += stripl;

                // prefix matched but no root word was found
                // if aeXPRODUCT is allowed, try again but now
                // cross checked combined with a suffix

                if ((opts & aeXPRODUCT) && (in_compound != IN_CPD_BEGIN)) {
                   he = pmyMgr->suffix_check_twosfx(tmpword, tmpl, aeXPRODUCT, this, needflag);
                   if (he) return he;
                }
            }
     }
    return NULL;
}

// check if this prefix entry matches
char * PfxEntry::check_twosfx_morph(const char * word, int len,
         char in_compound, const FLAG needflag)
{
    int                 tmpl;   // length of tmpword
    char                tmpword[MAXWORDUTF8LEN + 4];

    // on entry prefix is 0 length or already matches the beginning of the word.
    // So if the remaining root word has positive length
    // and if there are enough chars in root word and added back strip chars
    // to meet the number of characters conditions, then test it

     tmpl = len - appndl;

     if ((tmpl > 0 || (tmpl == 0 && pmyMgr->get_fullstrip())) &&
        (tmpl + stripl >= numconds)) {

            // generate new root word by removing prefix and adding
            // back any characters that would have been stripped

            if (stripl) strcpy (tmpword, strip);
            strcpy ((tmpword + stripl), (word + appndl));

            // now make sure all of the conditions on characters
            // are met.  Please see the appendix at the end of
            // this file for more info on exactly what is being
            // tested

            // if all conditions are met then check if resulting
            // root word in the dictionary

            if (test_condition(tmpword)) {
                tmpl += stripl;

                // prefix matched but no root word was found
                // if aeXPRODUCT is allowed, try again but now
                // ross checked combined with a suffix

                if ((opts & aeXPRODUCT) && (in_compound != IN_CPD_BEGIN)) {
                    return pmyMgr->suffix_check_twosfx_morph(tmpword, tmpl,
                             aeXPRODUCT, this, needflag);
                }
            }
     }
    return NULL;
}

// check if this prefix entry matches
char * PfxEntry::check_morph(const char * word, int len, char in_compound, const FLAG needflag)
{
    int                 tmpl;   // length of tmpword
    struct hentry *     he;     // hash entry of root word or NULL
    char                tmpword[MAXWORDUTF8LEN + 4];
    char                result[MAXLNLEN];
    char * st;

    *result = '\0';

    // on entry prefix is 0 length or already matches the beginning of the word.
    // So if the remaining root word has positive length
    // and if there are enough chars in root word and added back strip chars
    // to meet the number of characters conditions, then test it

     tmpl = len - appndl;

     if ((tmpl > 0 || (tmpl == 0 && pmyMgr->get_fullstrip())) &&
        (tmpl + stripl >= numconds)) {

            // generate new root word by removing prefix and adding
            // back any characters that would have been stripped

            if (stripl) strcpy (tmpword, strip);
            strcpy ((tmpword + stripl), (word + appndl));

            // now make sure all of the conditions on characters
            // are met.  Please see the appendix at the end of
            // this file for more info on exactly what is being
            // tested

            // if all conditions are met then check if resulting
            // root word in the dictionary

            if (test_condition(tmpword)) {
                tmpl += stripl;
                if ((he = pmyMgr->lookup(tmpword)) != NULL) {
                    do {
                      if (TESTAFF(he->astr, aflag, he->alen) &&
                        // forbid single prefixes with needaffix flag
                        ! TESTAFF(contclass, pmyMgr->get_needaffix(), contclasslen) &&
                        // needflag
                        ((!needflag) || TESTAFF(he->astr, needflag, he->alen) ||
                         (contclass && TESTAFF(contclass, needflag, contclasslen)))) {
                            if (morphcode) {
                                mystrcat(result, " ", MAXLNLEN);
                                mystrcat(result, morphcode, MAXLNLEN);
                            } else mystrcat(result,getKey(), MAXLNLEN);
                            if (!HENTRY_FIND(he, MORPH_STEM)) {
                                mystrcat(result, " ", MAXLNLEN);
                                mystrcat(result, MORPH_STEM, MAXLNLEN);
                                mystrcat(result, HENTRY_WORD(he), MAXLNLEN);
                            }
                            // store the pointer of the hash entry
                            if (HENTRY_DATA(he)) {
                                mystrcat(result, " ", MAXLNLEN);
                                mystrcat(result, HENTRY_DATA2(he), MAXLNLEN);
                            } else {
                                // return with debug information
                                char * flag = pmyMgr->encode_flag(getFlag());
                                mystrcat(result, " ", MAXLNLEN);
                                mystrcat(result, MORPH_FLAG, MAXLNLEN);
                                mystrcat(result, flag, MAXLNLEN);
                                free(flag);
                            }
                            mystrcat(result, "\n", MAXLNLEN);
                      }
                      he = he->next_homonym;
                    } while (he);
                }

                // prefix matched but no root word was found
                // if aeXPRODUCT is allowed, try again but now
                // ross checked combined with a suffix

                if ((opts & aeXPRODUCT) && (in_compound != IN_CPD_BEGIN)) {
                   st = pmyMgr->suffix_check_morph(tmpword, tmpl, aeXPRODUCT, this,
                     FLAG_NULL, needflag);
                   if (st) {
                        mystrcat(result, st, MAXLNLEN);
                        free(st);
                   }
                }
            }
     }
    
    if (*result) return mystrdup(result);
    return NULL;
}

SfxEntry::SfxEntry(AffixMgr * pmgr, affentry* dp)
{
  // register affix manager
  pmyMgr = pmgr;

  // set up its initial values
  aflag = dp->aflag;         // char flag
  strip = dp->strip;         // string to strip
  appnd = dp->appnd;         // string to append
  stripl = dp->stripl;       // length of strip string
  appndl = dp->appndl;       // length of append string
  numconds = dp->numconds;   // length of the condition
  opts = dp->opts;           // cross product flag

  // then copy over all of the conditions
  if (opts & aeLONGCOND) {
    memcpy(c.l.conds1, dp->c.l.conds1, MAXCONDLEN_1);
    c.l.conds2 = dp->c.l.conds2;
  } else memcpy(c.conds, dp->c.conds, MAXCONDLEN);

  rappnd = myrevstrdup(appnd);
  morphcode = dp->morphcode;
  contclass = dp->contclass;
  contclasslen = dp->contclasslen;
}


SfxEntry::~SfxEntry()
{
    aflag = 0;
    if (appnd) free(appnd);
    if (rappnd) free(rappnd);
    if (strip) free(strip);
    pmyMgr = NULL;
    appnd = NULL;
    strip = NULL;
    if (opts & aeLONGCOND) free(c.l.conds2);
    if (morphcode && !(opts & aeALIASM)) free(morphcode);
    if (contclass && !(opts & aeALIASF)) free(contclass);
}

// add suffix to this word assuming conditions hold
char * SfxEntry::add(const char * word, int len)
{
    char                tword[MAXWORDUTF8LEN + 4];

     /* make sure all conditions match */
     if ((len > stripl || (len == 0 && pmyMgr->get_fullstrip())) &&
        (len >= numconds) && test_condition(word + len, word) &&
        (!stripl || (strcmp(word + len - stripl, strip) == 0)) &&
        ((MAXWORDUTF8LEN + 4) > (len + appndl - stripl))) {
              /* we have a match so add suffix */
              strcpy(tword,word);
              if (appndl) {
                  strcpy(tword + len - stripl, appnd);
              } else {
                  *(tword + len - stripl) = '\0';
              }
              return mystrdup(tword);
     }
     return NULL;
}

inline char * SfxEntry::nextchar(char * p) {
    if (p) {
	p++;
	if (opts & aeLONGCOND) {
    	    // jump to the 2nd part of the condition
    	    if (p == c.l.conds1 + MAXCONDLEN_1) return c.l.conds2;
	// end of the MAXCONDLEN length condition
	} else if (p == c.conds + MAXCONDLEN) return NULL;
	return *p ? p : NULL;
    }
    return NULL;
}

inline int SfxEntry::test_condition(const char * st, const char * beg)
{
    const char * pos = NULL;    // group with pos input position
    bool neg = false;           // complementer
    bool ingroup = false;       // character in the group
    if (numconds == 0) return 1;
    char * p = c.conds;
    st--;
    int i = 1;
    while (1) {
      switch (*p) {
        case '\0': return 1;
        case '[': { p = nextchar(p); pos = st; break; }
        case '^': { p = nextchar(p); neg = true; break; }
        case ']': { if (!neg && !ingroup) return 0;
                i++;
                // skip the next character
                if (!ingroup) {
                    for (; (opts & aeUTF8) && (st >= beg) && (*st & 0xc0) == 0x80; st--);
                    st--;
                }                    
                pos = NULL;
                neg = false;
                ingroup = false;
                p = nextchar(p);
                if (st < beg && p) return 0; // word <= condition
                break;
            }
        case '.': if (!pos) { // dots are not metacharacters in groups: [.]
                p = nextchar(p);
                // skip the next character
                for (st--; (opts & aeUTF8) && (st >= beg) && (*st & 0xc0) == 0x80; st--);
                if (st < beg) { // word <= condition
		    if (p) return 0; else return 1;
		}
                if ((opts & aeUTF8) && (*st & 0x80)) { // head of the UTF-8 character
                    st--;
                    if (st < beg) { // word <= condition
			if (p) return 0; else return 1;
		    }
                }
                break;
            }
    default: {
                if (*st == *p) {
                    p = nextchar(p);
                    if ((opts & aeUTF8) && (*st & 0x80)) {
                        st--;
                        while (p && (st >= beg)) {
                            if (*p != *st) {
                                if (!pos) return 0;
                                st = pos;
                                break;
                            }
                            // first byte of the UTF-8 multibyte character
                            if ((*p & 0xc0) != 0x80) break;
                            p = nextchar(p);
                            st--;
                        }
                        if (pos && st != pos) {
                            if (neg) return 0;
                            else if (i == numconds) return 1;
                            ingroup = true;
                            while (p && *p != ']' && (p = nextchar(p)));
			    st--;
                        }
                        if (p && *p != ']') p = nextchar(p);
                    } else if (pos) {
                        if (neg) return 0;
                        else if (i == numconds) return 1;
                        ingroup = true;
			while (p && *p != ']' && (p = nextchar(p)));
//			if (p && *p != ']') p = nextchar(p);
                        st--;
                    }
                    if (!pos) {
                        i++;
                        st--;
                    }
                    if (st < beg && p && *p != ']') return 0; // word <= condition
                } else if (pos) { // group
                    p = nextchar(p);
                } else return 0;
            }
      }
      if (!p) return 1;
    }
}

// see if this suffix is present in the word
struct hentry * SfxEntry::checkword(const char * word, int len, int optflags,
    PfxEntry* ppfx, char ** wlst, int maxSug, int * ns, const FLAG cclass, const FLAG needflag,
    const FLAG badflag)
{
    int                 tmpl;            // length of tmpword
    struct hentry *     he;              // hash entry pointer
    unsigned char *     cp;
    char                tmpword[MAXWORDUTF8LEN + 4];
    PfxEntry* ep = ppfx;

    // if this suffix is being cross checked with a prefix
    // but it does not support cross products skip it

    if (((optflags & aeXPRODUCT) != 0) && ((opts & aeXPRODUCT) == 0))
        return NULL;

    // upon entry suffix is 0 length or already matches the end of the word.
    // So if the remaining root word has positive length
    // and if there are enough chars in root word and added back strip chars
    // to meet the number of characters conditions, then test it

    tmpl = len - appndl;
    // the second condition is not enough for UTF-8 strings
    // it checked in test_condition()

    if ((tmpl > 0 || (tmpl == 0 && pmyMgr->get_fullstrip())) &&
        (tmpl + stripl >= numconds)) {

            // generate new root word by removing suffix and adding
            // back any characters that would have been stripped or
            // or null terminating the shorter string

            strcpy (tmpword, word);
            cp = (unsigned char *)(tmpword + tmpl);
            if (stripl) {
                strcpy ((char *)cp, strip);
                tmpl += stripl;
                cp = (unsigned char *)(tmpword + tmpl);
            } else *cp = '\0';

            // now make sure all of the conditions on characters
            // are met.  Please see the appendix at the end of
            // this file for more info on exactly what is being
            // tested

            // if all conditions are met then check if resulting
            // root word in the dictionary

            if (test_condition((char *) cp, (char *) tmpword)) {

#ifdef SZOSZABLYA_POSSIBLE_ROOTS
                fprintf(stdout,"%s %s %c\n", word, tmpword, aflag);
#endif
                if ((he = pmyMgr->lookup(tmpword)) != NULL) {
                    do {
                        // check conditional suffix (enabled by prefix)
                        if ((TESTAFF(he->astr, aflag, he->alen) || (ep && ep->getCont() &&
                                    TESTAFF(ep->getCont(), aflag, ep->getContLen()))) &&
                            (((optflags & aeXPRODUCT) == 0) ||
                            (ep && TESTAFF(he->astr, ep->getFlag(), he->alen)) ||
                             // enabled by prefix
                            ((contclass) && (ep && TESTAFF(contclass, ep->getFlag(), contclasslen)))
                            ) &&
                            // handle cont. class
                            ((!cclass) ||
                                ((contclass) && TESTAFF(contclass, cclass, contclasslen))
                            ) &&
                            // check only in compound homonyms (bad flags)
                            (!badflag || !TESTAFF(he->astr, badflag, he->alen)
                            ) &&
                            // handle required flag
                            ((!needflag) ||
                              (TESTAFF(he->astr, needflag, he->alen) ||
                              ((contclass) && TESTAFF(contclass, needflag, contclasslen)))
                            )
                        ) return he;
                        he = he->next_homonym; // check homonyms
                    } while (he);

                // obsolote stemming code (used only by the
                // experimental SuffixMgr:suggest_pos_stems)
                // store resulting root in wlst
                } else if (wlst && (*ns < maxSug)) {
                    int cwrd = 1;
                    for (int k=0; k < *ns; k++)
                        if (strcmp(tmpword, wlst[k]) == 0) cwrd = 0;
                    if (cwrd) {
                        wlst[*ns] = mystrdup(tmpword);
                        if (wlst[*ns] == NULL) {
                            for (int j=0; j<*ns; j++) free(wlst[j]);
                            *ns = -1;
                            return NULL;
                        }
                        (*ns)++;
                    }
                }
            }
    }
    return NULL;
}

// see if two-level suffix is present in the word
struct hentry * SfxEntry::check_twosfx(const char * word, int len, int optflags,
    PfxEntry* ppfx, const FLAG needflag)
{
    int                 tmpl;            // length of tmpword
    struct hentry *     he;              // hash entry pointer
    unsigned char *     cp;
    char                tmpword[MAXWORDUTF8LEN + 4];
    PfxEntry* ep = ppfx;


    // if this suffix is being cross checked with a prefix
    // but it does not support cross products skip it

    if ((optflags & aeXPRODUCT) != 0 &&  (opts & aeXPRODUCT) == 0)
        return NULL;

    // upon entry suffix is 0 length or already matches the end of the word.
    // So if the remaining root word has positive length
    // and if there are enough chars in root word and added back strip chars
    // to meet the number of characters conditions, then test it

    tmpl = len - appndl;

    if ((tmpl > 0 || (tmpl == 0 && pmyMgr->get_fullstrip())) &&
       (tmpl + stripl >= numconds)) {

            // generate new root word by removing suffix and adding
            // back any characters that would have been stripped or
            // or null terminating the shorter string

            strcpy (tmpword, word);
            cp = (unsigned char *)(tmpword + tmpl);
            if (stripl) {
                strcpy ((char *)cp, strip);
                tmpl += stripl;
                cp = (unsigned char *)(tmpword + tmpl);
            } else *cp = '\0';

            // now make sure all of the conditions on characters
            // are met.  Please see the appendix at the end of
            // this file for more info on exactly what is being
            // tested

            // if all conditions are met then recall suffix_check

            if (test_condition((char *) cp, (char *) tmpword)) {
                if (ppfx) {
                    // handle conditional suffix
                    if ((contclass) && TESTAFF(contclass, ep->getFlag(), contclasslen))
                        he = pmyMgr->suffix_check(tmpword, tmpl, 0, NULL, NULL, 0, NULL, (FLAG) aflag, needflag);
                    else
                        he = pmyMgr->suffix_check(tmpword, tmpl, optflags, ppfx, NULL, 0, NULL, (FLAG) aflag, needflag);
                } else {
                    he = pmyMgr->suffix_check(tmpword, tmpl, 0, NULL, NULL, 0, NULL, (FLAG) aflag, needflag);
                }
                if (he) return he;
            }
    }
    return NULL;
}

// see if two-level suffix is present in the word
char * SfxEntry::check_twosfx_morph(const char * word, int len, int optflags,
    PfxEntry* ppfx, const FLAG needflag)
{
    int                 tmpl;            // length of tmpword
    unsigned char *     cp;
    char                tmpword[MAXWORDUTF8LEN + 4];
    PfxEntry* ep = ppfx;
    char * st;

    char result[MAXLNLEN];

    *result = '\0';

    // if this suffix is being cross checked with a prefix
    // but it does not support cross products skip it

    if ((optflags & aeXPRODUCT) != 0 &&  (opts & aeXPRODUCT) == 0)
        return NULL;

    // upon entry suffix is 0 length or already matches the end of the word.
    // So if the remaining root word has positive length
    // and if there are enough chars in root word and added back strip chars
    // to meet the number of characters conditions, then test it

    tmpl = len - appndl;

    if ((tmpl > 0 || (tmpl == 0 && pmyMgr->get_fullstrip())) &&
       (tmpl + stripl >= numconds)) {

            // generate new root word by removing suffix and adding
            // back any characters that would have been stripped or
            // or null terminating the shorter string

            strcpy (tmpword, word);
            cp = (unsigned char *)(tmpword + tmpl);
            if (stripl) {
                strcpy ((char *)cp, strip);
                tmpl += stripl;
                cp = (unsigned char *)(tmpword + tmpl);
            } else *cp = '\0';

            // now make sure all of the conditions on characters
            // are met.  Please see the appendix at the end of
            // this file for more info on exactly what is being
            // tested

            // if all conditions are met then recall suffix_check

            if (test_condition((char *) cp, (char *) tmpword)) {
                if (ppfx) {
                    // handle conditional suffix
                    if ((contclass) && TESTAFF(contclass, ep->getFlag(), contclasslen)) {
                        st = pmyMgr->suffix_check_morph(tmpword, tmpl, 0, NULL, aflag, needflag);
                        if (st) {
                            if (ppfx->getMorph()) {
                                mystrcat(result, ppfx->getMorph(), MAXLNLEN);
                                mystrcat(result, " ", MAXLNLEN);
                            }
                            mystrcat(result,st, MAXLNLEN);
                            free(st);
                            mychomp(result);
                        }
                    } else {
                        st = pmyMgr->suffix_check_morph(tmpword, tmpl, optflags, ppfx, aflag, needflag);
                        if (st) {
                            mystrcat(result, st, MAXLNLEN);
                            free(st);
                            mychomp(result);
                        }
                    }
                } else {
                        st = pmyMgr->suffix_check_morph(tmpword, tmpl, 0, NULL, aflag, needflag);
                        if (st) {
                            mystrcat(result, st, MAXLNLEN);
                            free(st);
                            mychomp(result);
                        }
                }
                if (*result) return mystrdup(result);
            }
    }
    return NULL;
}

// get next homonym with same affix
struct hentry * SfxEntry::get_next_homonym(struct hentry * he, int optflags, PfxEntry* ppfx,
    const FLAG cclass, const FLAG needflag)
{
    PfxEntry* ep = ppfx;
    FLAG eFlag = ep ? ep->getFlag() : FLAG_NULL;

    while (he->next_homonym) {
        he = he->next_homonym;
        if ((TESTAFF(he->astr, aflag, he->alen) || (ep && ep->getCont() && TESTAFF(ep->getCont(), aflag, ep->getContLen()))) &&
                            ((optflags & aeXPRODUCT) == 0 ||
                            TESTAFF(he->astr, eFlag, he->alen) ||
                             // handle conditional suffix
                            ((contclass) && TESTAFF(contclass, eFlag, contclasslen))
                            ) &&
                            // handle cont. class
                            ((!cclass) ||
                                ((contclass) && TESTAFF(contclass, cclass, contclasslen))
                            ) &&
                            // handle required flag
                            ((!needflag) ||
                              (TESTAFF(he->astr, needflag, he->alen) ||
                              ((contclass) && TESTAFF(contclass, needflag, contclasslen)))
                            )
                        ) return he;
    }
    return NULL;
}


#if 0

Appendix:  Understanding Affix Code


An affix is either a  prefix or a suffix attached to root words to make 
other words.

Basically a Prefix or a Suffix is set of AffEntry objects
which store information about the prefix or suffix along 
with supporting routines to check if a word has a particular 
prefix or suffix or a combination.

The structure affentry is defined as follows:

struct affentry
{
   unsigned short aflag;    // ID used to represent the affix
   char * strip;            // string to strip before adding affix
   char * appnd;            // the affix string to add
   unsigned char stripl;    // length of the strip string
   unsigned char appndl;    // length of the affix string
   char numconds;           // the number of conditions that must be met
   char opts;               // flag: aeXPRODUCT- combine both prefix and suffix 
   char   conds[SETSIZE];   // array which encodes the conditions to be met
};


Here is a suffix borrowed from the en_US.aff file.  This file 
is whitespace delimited.

SFX D Y 4 
SFX D   0     e          d
SFX D   y     ied        [^aeiou]y
SFX D   0     ed         [^ey]
SFX D   0     ed         [aeiou]y

This information can be interpreted as follows:

In the first line has 4 fields

Field
-----
1     SFX - indicates this is a suffix
2     D   - is the name of the character flag which represents this suffix
3     Y   - indicates it can be combined with prefixes (cross product)
4     4   - indicates that sequence of 4 affentry structures are needed to
               properly store the affix information

The remaining lines describe the unique information for the 4 SfxEntry 
objects that make up this affix.  Each line can be interpreted
as follows: (note fields 1 and 2 are as a check against line 1 info)

Field
-----
1     SFX         - indicates this is a suffix
2     D           - is the name of the character flag for this affix
3     y           - the string of chars to strip off before adding affix
                         (a 0 here indicates the NULL string)
4     ied         - the string of affix characters to add
5     [^aeiou]y   - the conditions which must be met before the affix
                    can be applied

Field 5 is interesting.  Since this is a suffix, field 5 tells us that
there are 2 conditions that must be met.  The first condition is that 
the next to the last character in the word must *NOT* be any of the 
following "a", "e", "i", "o" or "u".  The second condition is that
the last character of the word must end in "y".

So how can we encode this information concisely and be able to 
test for both conditions in a fast manner?  The answer is found
but studying the wonderful ispell code of Geoff Kuenning, et.al. 
(now available under a normal BSD license).

If we set up a conds array of 256 bytes indexed (0 to 255) and access it
using a character (cast to an unsigned char) of a string, we have 8 bits
of information we can store about that character.  Specifically we
could use each bit to say if that character is allowed in any of the 
last (or first for prefixes) 8 characters of the word.

Basically, each character at one end of the word (up to the number 
of conditions) is used to index into the conds array and the resulting 
value found there says whether the that character is valid for a 
specific character position in the word.  

For prefixes, it does this by setting bit 0 if that char is valid 
in the first position, bit 1 if valid in the second position, and so on. 

If a bit is not set, then that char is not valid for that postion in the
word.

If working with suffixes bit 0 is used for the character closest 
to the front, bit 1 for the next character towards the end, ..., 
with bit numconds-1 representing the last char at the end of the string. 

Note: since entries in the conds[] are 8 bits, only 8 conditions 
(read that only 8 character positions) can be examined at one
end of a word (the beginning for prefixes and the end for suffixes.

So to make this clearer, lets encode the conds array values for the 
first two affentries for the suffix D described earlier.


  For the first affentry:    
     numconds = 1             (only examine the last character)

     conds['e'] =  (1 << 0)   (the word must end in an E)
     all others are all 0

  For the second affentry:
     numconds = 2             (only examine the last two characters)     

     conds[X] = conds[X] | (1 << 0)     (aeiou are not allowed)
         where X is all characters *but* a, e, i, o, or u
         

     conds['y'] = (1 << 1)     (the last char must be a y)
     all other bits for all other entries in the conds array are zero


#endif

