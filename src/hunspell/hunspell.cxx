#include "license.hunspell"
#include "license.myspell"

#include <stdlib.h>
#include <string.h>
#include <stdio.h>

#include "hunspell.hxx"
#include "hunspell.h"
#ifndef MOZILLA_CLIENT
#    include "config.h"
#endif
#include "csutil.hxx"

Hunspell::Hunspell(const char * affpath, const char * dpath, const char * key)
{
    encoding = NULL;
    csconv = NULL;
    utf8 = 0;
    complexprefixes = 0;
    affixpath = mystrdup(affpath);
    maxdic = 0;

    /* first set up the hash manager */
    pHMgr[0] = new HashMgr(dpath, affpath, key);
    if (pHMgr[0]) maxdic = 1;

    /* next set up the affix manager */
    /* it needs access to the hash manager lookup methods */
    pAMgr = new AffixMgr(affpath, pHMgr, &maxdic, key);

    /* get the preferred try string and the dictionary */
    /* encoding from the Affix Manager for that dictionary */
    char * try_string = pAMgr->get_try_string();
    encoding = pAMgr->get_encoding();
    langnum = pAMgr->get_langnum();
    utf8 = pAMgr->get_utf8();
    if (!utf8)
        csconv = get_current_cs(encoding);
    complexprefixes = pAMgr->get_complexprefixes();
    wordbreak = pAMgr->get_breaktable();

    /* and finally set up the suggestion manager */
    pSMgr = new SuggestMgr(try_string, MAXSUGGESTION, pAMgr);
    if (try_string) free(try_string);
}

Hunspell::~Hunspell()
{
    if (pSMgr) delete pSMgr;
    if (pAMgr) delete pAMgr;
    for (int i = 0; i < maxdic; i++) delete pHMgr[i];
    maxdic = 0;
    pSMgr = NULL;
    pAMgr = NULL;
#ifdef MOZILLA_CLIENT
    delete [] csconv;
#endif
    csconv= NULL;
    if (encoding) free(encoding);
    encoding = NULL;
    if (affixpath) free(affixpath);
    affixpath = NULL;
}

// load extra dictionaries
int Hunspell::add_dic(const char * dpath, const char * key) {
    if (maxdic == MAXDIC || !affixpath) return 1;
    pHMgr[maxdic] = new HashMgr(dpath, affixpath, key);
    if (pHMgr[maxdic]) maxdic++; else return 1;
    return 0;
}

// make a copy of src at destination while removing all leading
// blanks and removing any trailing periods after recording
// their presence with the abbreviation flag
// also since already going through character by character,
// set the capitalization type
// return the length of the "cleaned" (and UTF-8 encoded) word

int Hunspell::cleanword2(char * dest, const char * src,
    w_char * dest_utf, int * nc, int * pcaptype, int * pabbrev)
{
   unsigned char * p = (unsigned char *) dest;
   const unsigned char * q = (const unsigned char * ) src;

   // first skip over any leading blanks
   while ((*q != '\0') && (*q == ' ')) q++;

   // now strip off any trailing periods (recording their presence)
   *pabbrev = 0;
   int nl = strlen((const char *)q);
   while ((nl > 0) && (*(q+nl-1)=='.')) {
       nl--;
       (*pabbrev)++;
   }

   // if no characters are left it can't be capitalized
   if (nl <= 0) {
       *pcaptype = NOCAP;
       *p = '\0';
       return 0;
   }

   strncpy(dest, (char *) q, nl);
   *(dest + nl) = '\0';
   nl = strlen(dest);
   if (utf8) {
      *nc = u8_u16(dest_utf, MAXWORDLEN, dest);
      // don't check too long words
      if (*nc >= MAXWORDLEN) return 0;
      if (*nc == -1) { // big Unicode character (non BMP area)
         *pcaptype = NOCAP;
         return nl;
      }
     *pcaptype = get_captype_utf8(dest_utf, *nc, langnum);
   } else {
     *pcaptype = get_captype(dest, nl, csconv);
     *nc = nl;
   }
   return nl;
}

int Hunspell::cleanword(char * dest, const char * src,
    int * pcaptype, int * pabbrev)
{
   unsigned char * p = (unsigned char *) dest;
   const unsigned char * q = (const unsigned char * ) src;
   int firstcap = 0;

   // first skip over any leading blanks
   while ((*q != '\0') && (*q == ' ')) q++;

   // now strip off any trailing periods (recording their presence)
   *pabbrev = 0;
   int nl = strlen((const char *)q);
   while ((nl > 0) && (*(q+nl-1)=='.')) {
       nl--;
       (*pabbrev)++;
   }

   // if no characters are left it can't be capitalized
   if (nl <= 0) {
       *pcaptype = NOCAP;
       *p = '\0';
       return 0;
   }

   // now determine the capitalization type of the first nl letters
   int ncap = 0;
   int nneutral = 0;
   int nc = 0;

   if (!utf8) {
      while (nl > 0) {
         nc++;
         if (csconv[(*q)].ccase) ncap++;
         if (csconv[(*q)].cupper == csconv[(*q)].clower) nneutral++;
         *p++ = *q++;
         nl--;
      }
      // remember to terminate the destination string
      *p = '\0';
      firstcap = csconv[(unsigned char)(*dest)].ccase;
   } else {
      unsigned short idx;
      w_char t[MAXWORDLEN];
      nc = u8_u16(t, MAXWORDLEN, src);
      for (int i = 0; i < nc; i++) {
         idx = (t[i].h << 8) + t[i].l;
         unsigned short low = unicodetolower(idx, langnum);
         if (idx != low) ncap++;
         if (unicodetoupper(idx, langnum) == low) nneutral++;
      }
      u16_u8(dest, MAXWORDUTF8LEN, t, nc);
      if (ncap) {
         idx = (t[0].h << 8) + t[0].l;
         firstcap = (idx != unicodetolower(idx, langnum));
      }
   }

   // now finally set the captype
   if (ncap == 0) {
        *pcaptype = NOCAP;
   } else if ((ncap == 1) && firstcap) {
        *pcaptype = INITCAP;
   } else if ((ncap == nc) || ((ncap + nneutral) == nc)){
        *pcaptype = ALLCAP;
   } else if ((ncap > 1) && firstcap) {
        *pcaptype = HUHINITCAP;
   } else {
        *pcaptype = HUHCAP;
   }
   return strlen(dest);
}

void Hunspell::mkallcap(char * p)
{
  if (utf8) {
      w_char u[MAXWORDLEN];
      int nc = u8_u16(u, MAXWORDLEN, p);
      unsigned short idx;
      for (int i = 0; i < nc; i++) {
         idx = (u[i].h << 8) + u[i].l;
         if (idx != unicodetoupper(idx, langnum)) {
            u[i].h = (unsigned char) (unicodetoupper(idx, langnum) >> 8);
            u[i].l = (unsigned char) (unicodetoupper(idx, langnum) & 0x00FF);
         }
      }
      u16_u8(p, MAXWORDUTF8LEN, u, nc);
  } else {
    while (*p != '\0') {
        *p = csconv[((unsigned char) *p)].cupper;
        p++;
    }
  }
}

int Hunspell::mkallcap2(char * p, w_char * u, int nc)
{
  if (utf8) {
      unsigned short idx;
      for (int i = 0; i < nc; i++) {
         idx = (u[i].h << 8) + u[i].l;
         unsigned short up = unicodetoupper(idx, langnum);
         if (idx != up) {
            u[i].h = (unsigned char) (up >> 8);
            u[i].l = (unsigned char) (up & 0x00FF);
         }
      }
      u16_u8(p, MAXWORDUTF8LEN, u, nc);
      return strlen(p);
  } else {
    while (*p != '\0') {
        *p = csconv[((unsigned char) *p)].cupper;
        p++;
    }
  }
  return nc;
}


void Hunspell::mkallsmall(char * p)
{
    while (*p != '\0') {
        *p = csconv[((unsigned char) *p)].clower;
        p++;
    }
}

int Hunspell::mkallsmall2(char * p, w_char * u, int nc)
{
  if (utf8) {
      unsigned short idx;
      for (int i = 0; i < nc; i++) {
         idx = (u[i].h << 8) + u[i].l;
         unsigned short low = unicodetolower(idx, langnum);
         if (idx != low) {
            u[i].h = (unsigned char) (low >> 8);
            u[i].l = (unsigned char) (low & 0x00FF);
         }
      }
      u16_u8(p, MAXWORDUTF8LEN, u, nc);
      return strlen(p);
  } else {
    while (*p != '\0') {
        *p = csconv[((unsigned char) *p)].clower;
        p++;
    }
  }
  return nc;
}

// convert UTF-8 sharp S codes to latin 1
char * Hunspell::sharps_u8_l1(char * dest, char * source) {
    char * p = dest;
    *p = *source;
    for (p++, source++; *(source - 1); p++, source++) {
        *p = *source;
        if (*source == '\x9F') *--p = '\xDF';
    }
    return dest;
}

// recursive search for right ss - sharp s permutations
hentry * Hunspell::spellsharps(char * base, char * pos, int n,
        int repnum, char * tmp, int * info, char **root) {
    pos = strstr(pos, "ss");
    if (pos && (n < MAXSHARPS)) {
        *pos = '\xC3';
        *(pos + 1) = '\x9F';
        hentry * h = spellsharps(base, pos + 2, n + 1, repnum + 1, tmp, info, root);
        if (h) return h;
        *pos = 's';
        *(pos + 1) = 's';
        h = spellsharps(base, pos + 2, n + 1, repnum, tmp, info, root);
        if (h) return h;
    } else if (repnum > 0) {
        if (utf8) return checkword(base, info, root);
        return checkword(sharps_u8_l1(tmp, base), info, root);
    }
    return NULL;
}

int Hunspell::is_keepcase(const hentry * rv) {
    return pAMgr && rv->astr && pAMgr->get_keepcase() &&
        TESTAFF(rv->astr, pAMgr->get_keepcase(), rv->alen);
}

/* insert a word to the beginning of the suggestion array and return ns */
int Hunspell::insert_sug(char ***slst, char * word, int ns) {
    char * dup = mystrdup(word);
    if (!dup) return ns;
    if (ns == MAXSUGGESTION) {
        ns--;
        free((*slst)[ns]);
    }
    for (int k = ns; k > 0; k--) (*slst)[k] = (*slst)[k - 1];
    (*slst)[0] = dup;
    return ns + 1;
}

int Hunspell::spell(const char * word, int * info, char ** root)
{
  struct hentry * rv=NULL;
  // need larger vector. For example, Turkish capital letter I converted a
  // 2-byte UTF-8 character (dotless i) by mkallsmall.
  char cw[MAXWORDUTF8LEN];
  char wspace[MAXWORDUTF8LEN];
  w_char unicw[MAXWORDLEN];
  // Hunspell supports XML input of the simplified API (see manual)
  if (strcmp(word, SPELL_XML) == 0) return 1;
  int nc = strlen(word);
  int wl2 = 0;
  if (utf8) {
    if (nc >= MAXWORDUTF8LEN) return 0;
  } else {
    if (nc >= MAXWORDLEN) return 0;
  }
  int captype = 0;
  int abbv = 0;
  int wl = 0;

  // input conversion
  RepList * rl = (pAMgr) ? pAMgr->get_iconvtable() : NULL;
  if (rl && rl->conv(word, wspace)) wl = cleanword2(cw, wspace, unicw, &nc, &captype, &abbv);
  else wl = cleanword2(cw, word, unicw, &nc, &captype, &abbv);

  int info2 = 0;
  if (wl == 0 || maxdic == 0) return 1;
  if (root) *root = NULL;

  // allow numbers with dots, dashes and commas (but forbid double separators: "..", "--" etc.)
  enum { NBEGIN, NNUM, NSEP };
  int nstate = NBEGIN;
  int i;

  for (i = 0; (i < wl); i++) {
    if ((cw[i] <= '9') && (cw[i] >= '0')) {
        nstate = NNUM;
    } else if ((cw[i] == ',') || (cw[i] == '.') || (cw[i] == '-')) {
        if ((nstate == NSEP) || (i == 0)) break;
        nstate = NSEP;
    } else break;
  }
  if ((i == wl) && (nstate == NNUM)) return 1;
  if (!info) info = &info2; else *info = 0;

  switch(captype) {
     case HUHCAP:
     case HUHINITCAP:
            *info += SPELL_ORIGCAP;
     case NOCAP: {
            rv = checkword(cw, info, root);
            if ((abbv) && !(rv)) {
                memcpy(wspace,cw,wl);
                *(wspace+wl) = '.';
                *(wspace+wl+1) = '\0';
                rv = checkword(wspace, info, root);
            }
            break;
         }
     case ALLCAP: {
            *info += SPELL_ORIGCAP;
            rv = checkword(cw, info, root);
            if (rv) break;
            if (abbv) {
                memcpy(wspace,cw,wl);
                *(wspace+wl) = '.';
                *(wspace+wl+1) = '\0';
                rv = checkword(wspace, info, root);
                if (rv) break;
            }
            // Spec. prefix handling for Catalan, French, Italian:
	    // prefixes separated by apostrophe (SANT'ELIA -> Sant'+Elia).
            if (pAMgr && strchr(cw, '\'')) {
                wl = mkallsmall2(cw, unicw, nc);
        	//There are no really sane circumstances where this could fail,
        	//but anyway...
        	if (char * apostrophe = strchr(cw, '\'')) {
                    if (utf8) {
            	        w_char tmpword[MAXWORDLEN];
            	        *apostrophe = '\0';
            	        wl2 = u8_u16(tmpword, MAXWORDLEN, cw);
            	        *apostrophe = '\'';
		        if (wl2 < nc) {
		            mkinitcap2(apostrophe + 1, unicw + wl2 + 1, nc - wl2 - 1);
			    rv = checkword(cw, info, root);
			    if (rv) break;
		        }
                    } else {
		        mkinitcap2(apostrophe + 1, unicw, nc);
		        rv = checkword(cw, info, root);
		        if (rv) break;
		    }
		}
		mkinitcap2(cw, unicw, nc);
		rv = checkword(cw, info, root);
		if (rv) break;
            }
            if (pAMgr && pAMgr->get_checksharps() && strstr(cw, "SS")) {
                char tmpword[MAXWORDUTF8LEN];
                wl = mkallsmall2(cw, unicw, nc);
                memcpy(wspace,cw,(wl+1));
                rv = spellsharps(wspace, wspace, 0, 0, tmpword, info, root);
                if (!rv) {
                    wl2 = mkinitcap2(cw, unicw, nc);
                    rv = spellsharps(cw, cw, 0, 0, tmpword, info, root);
                }
                if ((abbv) && !(rv)) {
                    *(wspace+wl) = '.';
                    *(wspace+wl+1) = '\0';
                    rv = spellsharps(wspace, wspace, 0, 0, tmpword, info, root);
                    if (!rv) {
                        memcpy(wspace, cw, wl2);
                        *(wspace+wl2) = '.';
                        *(wspace+wl2+1) = '\0';
                        rv = spellsharps(wspace, wspace, 0, 0, tmpword, info, root);
                    }
                }
                if (rv) break;
            }
        }
     case INITCAP: {
             *info += SPELL_ORIGCAP;
             wl = mkallsmall2(cw, unicw, nc);
             memcpy(wspace,cw,(wl+1));
             wl2 = mkinitcap2(cw, unicw, nc);
             if (captype == INITCAP) *info += SPELL_INITCAP;
             rv = checkword(cw, info, root);
             if (captype == INITCAP) *info -= SPELL_INITCAP;
             // forbid bad capitalization
             // (for example, ijs -> Ijs instead of IJs in Dutch)
             // use explicit forms in dic: Ijs/F (F = FORBIDDENWORD flag)
             if (*info & SPELL_FORBIDDEN) {
                rv = NULL;
                break;
             }
             if (rv && is_keepcase(rv) && (captype == ALLCAP)) rv = NULL;
             if (rv) break;

             rv = checkword(wspace, info, root);
             if (abbv && !rv) {

                 *(wspace+wl) = '.';
                 *(wspace+wl+1) = '\0';
                 rv = checkword(wspace, info, root);
                 if (!rv) {
                    memcpy(wspace, cw, wl2);
                    *(wspace+wl2) = '.';
                    *(wspace+wl2+1) = '\0';
    	    	    if (captype == INITCAP) *info += SPELL_INITCAP;
                    rv = checkword(wspace, info, root);
    	    	    if (captype == INITCAP) *info -= SPELL_INITCAP;
                    if (rv && is_keepcase(rv) && (captype == ALLCAP)) rv = NULL;
                    break;
                 }
             }
             if (rv && is_keepcase(rv) &&
                ((captype == ALLCAP) ||
                   // if CHECKSHARPS: KEEPCASE words with \xDF  are allowed
                   // in INITCAP form, too.
                   !(pAMgr->get_checksharps() &&
                      ((utf8 && strstr(wspace, "\xC3\x9F")) ||
                      (!utf8 && strchr(wspace, '\xDF')))))) rv = NULL;
             break;
           }
  }

  if (rv) {
      if (pAMgr && pAMgr->get_warn() && rv->astr &&
          TESTAFF(rv->astr, pAMgr->get_warn(), rv->alen)) {
              *info += SPELL_WARN;
	      if (pAMgr->get_forbidwarn()) return 0;
              return HUNSPELL_OK_WARN;
      }
      return HUNSPELL_OK;
  }

  // recursive breaking at break points
  if (wordbreak) {
    char * s;
    char r;
    int nbr = 0;
    wl = strlen(cw);
    int numbreak = pAMgr ? pAMgr->get_numbreak() : 0;

    // calculate break points for recursion limit
    for (int j = 0; j < numbreak; j++) {
      s = cw;
      do {
      	s = (char *) strstr(s, wordbreak[j]);
      	if (s) { 
		nbr++;
		s++;
	}
      } while (s);
    } 
    if (nbr >= 10) return 0;

    // check boundary patterns (^begin and end$)
    for (int j = 0; j < numbreak; j++) {
      int plen = strlen(wordbreak[j]);
      if (plen == 1 || plen > wl) continue;
      if (wordbreak[j][0] == '^' && strncmp(cw, wordbreak[j] + 1, plen - 1) == 0
        && spell(cw + plen - 1)) return 1;
      if (wordbreak[j][plen - 1] == '$' &&
        strncmp(cw + wl - plen + 1, wordbreak[j], plen - 1) == 0) {
	    r = cw[wl - plen + 1];
	    cw[wl - plen + 1] = '\0';
    	    if (spell(cw)) return 1;
	    cw[wl - plen + 1] = r;
	}
    }

    // other patterns
    for (int j = 0; j < numbreak; j++) {
      int plen = strlen(wordbreak[j]);
      s=(char *) strstr(cw, wordbreak[j]);
      if (s && (s > cw) && (s < cw + wl - plen)) {
	if (!spell(s + plen)) continue;
        r = *s;
        *s = '\0';
        // examine 2 sides of the break point
        if (spell(cw)) return 1;
        *s = r;

        // LANG_hu: spec. dash rule
	if (langnum == LANG_hu && strcmp(wordbreak[j], "-") == 0) {
	  r = s[1];
	  s[1] = '\0';
          if (spell(cw)) return 1; // check the first part with dash
          s[1] = r;
	}
        // end of LANG speficic region

      }
    }
  }

  return 0;
}

struct hentry * Hunspell::checkword(const char * w, int * info, char ** root)
{
  struct hentry * he = NULL;
  int len, i;
  char w2[MAXWORDUTF8LEN];
  const char * word;

  char * ignoredchars = pAMgr->get_ignore();
  if (ignoredchars != NULL) {
     strcpy(w2, w);
     if (utf8) {
        int ignoredchars_utf16_len;
        unsigned short * ignoredchars_utf16 = pAMgr->get_ignore_utf16(&ignoredchars_utf16_len);
        remove_ignored_chars_utf(w2, ignoredchars_utf16, ignoredchars_utf16_len);
     } else {
        remove_ignored_chars(w2,ignoredchars);
     }
     word = w2;
  } else word = w;

  len = strlen(word);

  if (!len)
      return NULL;

  // word reversing wrapper for complex prefixes
  if (complexprefixes) {
    if (word != w2) {
      strcpy(w2, word);
      word = w2;
    }
    if (utf8) reverseword_utf(w2); else reverseword(w2);
  }

  // look word in hash table
  for (i = 0; (i < maxdic) && !he; i ++) {
  he = (pHMgr[i])->lookup(word);

  // check forbidden and onlyincompound words
  if ((he) && (he->astr) && (pAMgr) && TESTAFF(he->astr, pAMgr->get_forbiddenword(), he->alen)) {
    if (info) *info += SPELL_FORBIDDEN;
    // LANG_hu section: set dash information for suggestions
    if (langnum == LANG_hu) {
        if (pAMgr->get_compoundflag() &&
            TESTAFF(he->astr, pAMgr->get_compoundflag(), he->alen)) {
                if (info) *info += SPELL_COMPOUND;
        }
    }
    return NULL;
  }

  // he = next not needaffix, onlyincompound homonym or onlyupcase word
  while (he && (he->astr) &&
    ((pAMgr->get_needaffix() && TESTAFF(he->astr, pAMgr->get_needaffix(), he->alen)) ||
       (pAMgr->get_onlyincompound() && TESTAFF(he->astr, pAMgr->get_onlyincompound(), he->alen)) ||
       (info && (*info & SPELL_INITCAP) && TESTAFF(he->astr, ONLYUPCASEFLAG, he->alen))
    )) he = he->next_homonym;
  }

  // check with affixes
  if (!he && pAMgr) {
     // try stripping off affixes */
     he = pAMgr->affix_check(word, len, 0);

     // check compound restriction and onlyupcase
     if (he && he->astr && (
        (pAMgr->get_onlyincompound() &&
    	    TESTAFF(he->astr, pAMgr->get_onlyincompound(), he->alen)) ||
        (info && (*info & SPELL_INITCAP) &&
    	    TESTAFF(he->astr, ONLYUPCASEFLAG, he->alen)))) {
    	    he = NULL;
     }

     if (he) {
        if ((he->astr) && (pAMgr) && TESTAFF(he->astr, pAMgr->get_forbiddenword(), he->alen)) {
            if (info) *info += SPELL_FORBIDDEN;
            return NULL;
        }
        if (root) {
            *root = mystrdup(he->word);
            if (*root && complexprefixes) {
                if (utf8) reverseword_utf(*root); else reverseword(*root);
            }
        }
     // try check compound word
     } else if (pAMgr->get_compound()) {
          he = pAMgr->compound_check(word, len, 0, 0, 100, 0, NULL, 0, 0, info);
          // LANG_hu section: `moving rule' with last dash
          if ((!he) && (langnum == LANG_hu) && (word[len-1] == '-')) {
             char * dup = mystrdup(word);
             if (!dup) return NULL;
             dup[len-1] = '\0';
             he = pAMgr->compound_check(dup, len-1, -5, 0, 100, 0, NULL, 1, 0, info);
             free(dup);
          }
          // end of LANG speficic region
          if (he) {
                if (root) {
                    *root = mystrdup(he->word);
                    if (*root && complexprefixes) {
                        if (utf8) reverseword_utf(*root); else reverseword(*root);
                    }
                }
                if (info) *info += SPELL_COMPOUND;
          }
     }

  }

  return he;
}

int Hunspell::suggest(char*** slst, const char * word)
{
  int onlycmpdsug = 0;
  char cw[MAXWORDUTF8LEN];
  char wspace[MAXWORDUTF8LEN];
  if (!pSMgr || maxdic == 0) return 0;
  w_char unicw[MAXWORDLEN];
  *slst = NULL;
  // process XML input of the simplified API (see manual)
  if (strncmp(word, SPELL_XML, sizeof(SPELL_XML) - 3) == 0) {
     return spellml(slst, word);
  }
  int nc = strlen(word);
  if (utf8) {
    if (nc >= MAXWORDUTF8LEN) return 0;
  } else {
    if (nc >= MAXWORDLEN) return 0;
  }
  int captype = 0;
  int abbv = 0;
  int wl = 0;

  // input conversion
  RepList * rl = (pAMgr) ? pAMgr->get_iconvtable() : NULL;
  if (rl && rl->conv(word, wspace)) wl = cleanword2(cw, wspace, unicw, &nc, &captype, &abbv);
  else wl = cleanword2(cw, word, unicw, &nc, &captype, &abbv);

  if (wl == 0) return 0;
  int ns = 0;
  int capwords = 0;

  // check capitalized form for FORCEUCASE
  if (pAMgr && captype == NOCAP && pAMgr->get_forceucase()) {
    int info = SPELL_ORIGCAP;
    char ** wlst;
    if (checkword(cw, &info, NULL)) {
        if (*slst) {
            wlst = *slst;
        } else {
            wlst = (char **) malloc(MAXSUGGESTION * sizeof(char *));
            if (wlst == NULL) return -1;
            *slst = wlst;
            for (int i = 0; i < MAXSUGGESTION; i++) {
                wlst[i] = NULL;
            }
        }
        wlst[0] = mystrdup(cw);
        mkinitcap(wlst[0]);
        return 1;
    }
  }
 
  switch(captype) {
     case NOCAP:   {
                     ns = pSMgr->suggest(slst, cw, ns, &onlycmpdsug);
                     break;
                   }

     case INITCAP: {
                     capwords = 1;
                     ns = pSMgr->suggest(slst, cw, ns, &onlycmpdsug);
                     if (ns == -1) break;
                     memcpy(wspace,cw,(wl+1));
                     mkallsmall2(wspace, unicw, nc);
                     ns = pSMgr->suggest(slst, wspace, ns, &onlycmpdsug);
                     break;
                   }
     case HUHINITCAP:
                    capwords = 1;
     case HUHCAP: {
                     ns = pSMgr->suggest(slst, cw, ns, &onlycmpdsug);
                     if (ns != -1) {
                        int prevns;
    		        // something.The -> something. The
                        char * dot = strchr(cw, '.');
		        if (dot && (dot > cw)) {
		            int captype_;
		            if (utf8) {
		               w_char w_[MAXWORDLEN];
			       int wl_ = u8_u16(w_, MAXWORDLEN, dot + 1);
		               captype_ = get_captype_utf8(w_, wl_, langnum);
		            } else captype_ = get_captype(dot+1, strlen(dot+1), csconv);
		    	    if (captype_ == INITCAP) {
                        	char * st = mystrdup(cw);
                        	if (st) st = (char *) realloc(st, wl + 2);
				if (st) {
                        		st[(dot - cw) + 1] = ' ';
                        		strcpy(st + (dot - cw) + 2, dot + 1);
                    			ns = insert_sug(slst, st, ns);
					free(st);
				}
		    	    }
		        }
                        if (captype == HUHINITCAP) {
                            // TheOpenOffice.org -> The OpenOffice.org
                            memcpy(wspace,cw,(wl+1));
                            mkinitsmall2(wspace, unicw, nc);
                            ns = pSMgr->suggest(slst, wspace, ns, &onlycmpdsug);
                        }
                        memcpy(wspace,cw,(wl+1));
                        mkallsmall2(wspace, unicw, nc);
                        if (spell(wspace)) ns = insert_sug(slst, wspace, ns);
                        prevns = ns;
                        ns = pSMgr->suggest(slst, wspace, ns, &onlycmpdsug);
                        if (captype == HUHINITCAP) {
                            mkinitcap2(wspace, unicw, nc);
                            if (spell(wspace)) ns = insert_sug(slst, wspace, ns);
                            ns = pSMgr->suggest(slst, wspace, ns, &onlycmpdsug);
                        }
                        // aNew -> "a New" (instead of "a new")
                        for (int j = prevns; j < ns; j++) {
                           char * space = strchr((*slst)[j],' ');
                           if (space) {
                                int slen = strlen(space + 1);
                                // different case after space (need capitalisation)
                                if ((slen < wl) && strcmp(cw + wl - slen, space + 1)) {
                                    w_char w[MAXWORDLEN];
                                    int wc = 0;
                                    char * r = (*slst)[j];
                                    if (utf8) wc = u8_u16(w, MAXWORDLEN, space + 1);
                                    mkinitcap2(space + 1, w, wc);
                                    // set as first suggestion
                                    for (int k = j; k > 0; k--) (*slst)[k] = (*slst)[k - 1];
                                    (*slst)[0] = r;
                                }
                           }
                        }
                     }
                     break;
                   }

     case ALLCAP: {
                     memcpy(wspace, cw, (wl+1));
                     mkallsmall2(wspace, unicw, nc);
                     ns = pSMgr->suggest(slst, wspace, ns, &onlycmpdsug);
                     if (ns == -1) break;
                     if (pAMgr && pAMgr->get_keepcase() && spell(wspace))
                        ns = insert_sug(slst, wspace, ns);
                     mkinitcap2(wspace, unicw, nc);
                     ns = pSMgr->suggest(slst, wspace, ns, &onlycmpdsug);
                     for (int j=0; j < ns; j++) {
                        mkallcap((*slst)[j]);
                        if (pAMgr && pAMgr->get_checksharps()) {
                            char * pos;
                            if (utf8) {
                                pos = strstr((*slst)[j], "\xC3\x9F");
                                while (pos) {
                                    *pos = 'S';
                                    *(pos+1) = 'S';
                                    pos = strstr(pos+2, "\xC3\x9F");
                                }
                            } else {
                                pos = strchr((*slst)[j], '\xDF');
                                while (pos) {
                                    (*slst)[j] = (char *) realloc((*slst)[j], strlen((*slst)[j]) + 2);
                                    mystrrep((*slst)[j], "\xDF", "SS");
                                    pos = strchr((*slst)[j], '\xDF');
                                }
                            }
                        }
                     }
                     break;
                   }
  }

 // LANG_hu section: replace '-' with ' ' in Hungarian
  if (langnum == LANG_hu) {
      for (int j=0; j < ns; j++) {
          char * pos = strchr((*slst)[j],'-');
          if (pos) {
              int info;
              char w[MAXWORDUTF8LEN];
              *pos = '\0';
              strcpy(w, (*slst)[j]);
              strcat(w, pos + 1);
              spell(w, &info, NULL);
              if ((info & SPELL_COMPOUND) && (info & SPELL_FORBIDDEN)) {
                  *pos = ' ';
              } else *pos = '-';
          }
      }
  }
  // END OF LANG_hu section

  // try ngram approach since found nothing or only compound words
  if (pAMgr && (ns == 0 || onlycmpdsug) && (pAMgr->get_maxngramsugs() != 0) && (*slst)) {
      switch(captype) {
          case NOCAP: {
              ns = pSMgr->ngsuggest(*slst, cw, ns, pHMgr, maxdic);
              break;
          }
	  case HUHINITCAP:
              capwords = 1;
          case HUHCAP: {
              memcpy(wspace,cw,(wl+1));
              mkallsmall2(wspace, unicw, nc);
              ns = pSMgr->ngsuggest(*slst, wspace, ns, pHMgr, maxdic);
	      break;
          }
         case INITCAP: {
              capwords = 1;
              memcpy(wspace,cw,(wl+1));
              mkallsmall2(wspace, unicw, nc);
              ns = pSMgr->ngsuggest(*slst, wspace, ns, pHMgr, maxdic);
              break;
          }
          case ALLCAP: {
              memcpy(wspace,cw,(wl+1));
              mkallsmall2(wspace, unicw, nc);
	      int oldns = ns;
              ns = pSMgr->ngsuggest(*slst, wspace, ns, pHMgr, maxdic);
              for (int j = oldns; j < ns; j++)
                  mkallcap((*slst)[j]);
              break;
         }
      }
  }

  // try dash suggestion (Afo-American -> Afro-American)
  if (char * pos = strchr(cw, '-')) {
     char * ppos = cw;
     int nodashsug = 1;
     char ** nlst = NULL;
     int nn = 0;
     int last = 0;
     if (*slst) {
        for (int j = 0; j < ns && nodashsug == 1; j++) {
           if (strchr((*slst)[j], '-')) nodashsug = 0;
        }
     }
     while (nodashsug && !last) {
	if (*pos == '\0') last = 1; else *pos = '\0';
        if (!spell(ppos)) {
          nn = suggest(&nlst, ppos);
          for (int j = nn - 1; j >= 0; j--) {
            strncpy(wspace, cw, ppos - cw);
            strcpy(wspace + (ppos - cw), nlst[j]);
            if (!last) {
            	strcat(wspace, "-");
		strcat(wspace, pos + 1);
	    }
            ns = insert_sug(slst, wspace, ns);
            free(nlst[j]);
          }
          if (nlst != NULL) free(nlst);
          nodashsug = 0;
        }
	if (!last) {
          *pos = '-';
          ppos = pos + 1;
          pos = strchr(ppos, '-');
        }
	if (!pos) pos = cw + strlen(cw);
     }
  }

  // word reversing wrapper for complex prefixes
  if (complexprefixes) {
    for (int j = 0; j < ns; j++) {
      if (utf8) reverseword_utf((*slst)[j]); else reverseword((*slst)[j]);
    }
  }

  // capitalize
  if (capwords) for (int j=0; j < ns; j++) {
      mkinitcap((*slst)[j]);
  }

  // expand suggestions with dot(s)
  if (abbv && pAMgr && pAMgr->get_sugswithdots()) {
    for (int j = 0; j < ns; j++) {
      (*slst)[j] = (char *) realloc((*slst)[j], strlen((*slst)[j]) + 1 + abbv);
      strcat((*slst)[j], word + strlen(word) - abbv);
    }
  }

  // remove bad capitalized and forbidden forms
  if (pAMgr && (pAMgr->get_keepcase() || pAMgr->get_forbiddenword())) {
  switch (captype) {
    case INITCAP:
    case ALLCAP: {
      int l = 0;
      for (int j=0; j < ns; j++) {
        if (!strchr((*slst)[j],' ') && !spell((*slst)[j])) {
          char s[MAXSWUTF8L];
          w_char w[MAXSWL];
          int len;
          if (utf8) {
            len = u8_u16(w, MAXSWL, (*slst)[j]);
          } else {
            strcpy(s, (*slst)[j]);
            len = strlen(s);
          }
          mkallsmall2(s, w, len);
          free((*slst)[j]);
          if (spell(s)) {
            (*slst)[l] = mystrdup(s);
            if ((*slst)[l]) l++;
          } else {
            mkinitcap2(s, w, len);
            if (spell(s)) {
              (*slst)[l] = mystrdup(s);
              if ((*slst)[l]) l++;
            }
          }
        } else {
          (*slst)[l] = (*slst)[j];
          l++;
        }
      }
      ns = l;
    }
  }
  }

  // remove duplications
  int l = 0;
  for (int j = 0; j < ns; j++) {
    (*slst)[l] = (*slst)[j];
    for (int k = 0; k < l; k++) {
      if (strcmp((*slst)[k], (*slst)[j]) == 0) {
        free((*slst)[j]);
        l--;
        break;
      }
    }
    l++;
  }
  ns = l;

  // output conversion
  rl = (pAMgr) ? pAMgr->get_oconvtable() : NULL;
  for (int j = 0; rl && j < ns; j++) {
    if (rl->conv((*slst)[j], wspace)) {
      free((*slst)[j]);
      (*slst)[j] = mystrdup(wspace);
    }
  }

  // if suggestions removed by nosuggest, onlyincompound parameters
  if (l == 0 && *slst) {
    free(*slst);
    *slst = NULL;
  }
  return l;
}

void Hunspell::free_list(char *** slst, int n) {
        freelist(slst, n);
}

char * Hunspell::get_dic_encoding()
{
  return encoding;
}

#ifdef HUNSPELL_EXPERIMENTAL
// XXX need UTF-8 support
int Hunspell::suggest_auto(char*** slst, const char * word)
{
  char cw[MAXWORDUTF8LEN];
  char wspace[MAXWORDUTF8LEN];
  if (!pSMgr || maxdic == 0) return 0;
  int wl = strlen(word);
  if (utf8) {
    if (wl >= MAXWORDUTF8LEN) return 0;
  } else {
    if (wl >= MAXWORDLEN) return 0;
  }
  int captype = 0;
  int abbv = 0;
  wl = cleanword(cw, word, &captype, &abbv);
  if (wl == 0) return 0;
  int ns = 0;
  *slst = NULL; // HU, nsug in pSMgr->suggest

  switch(captype) {
     case NOCAP:   {
                     ns = pSMgr->suggest_auto(slst, cw, ns);
                     if (ns>0) break;
                     break;
                   }

     case INITCAP: {
                     memcpy(wspace,cw,(wl+1));
                     mkallsmall(wspace);
                     ns = pSMgr->suggest_auto(slst, wspace, ns);
                     for (int j=0; j < ns; j++)
                       mkinitcap((*slst)[j]);
                     ns = pSMgr->suggest_auto(slst, cw, ns);
                     break;

                   }

     case HUHINITCAP:
     case HUHCAP: {
                     ns = pSMgr->suggest_auto(slst, cw, ns);
                     if (ns == 0) {
                        memcpy(wspace,cw,(wl+1));
                        mkallsmall(wspace);
                        ns = pSMgr->suggest_auto(slst, wspace, ns);
                     }
                     break;
                   }

     case ALLCAP: {
                     memcpy(wspace,cw,(wl+1));
                     mkallsmall(wspace);
                     ns = pSMgr->suggest_auto(slst, wspace, ns);

                     mkinitcap(wspace);
                     ns = pSMgr->suggest_auto(slst, wspace, ns);

                     for (int j=0; j < ns; j++)
                       mkallcap((*slst)[j]);
                     break;
                   }
  }

  // word reversing wrapper for complex prefixes
  if (complexprefixes) {
    for (int j = 0; j < ns; j++) {
      if (utf8) reverseword_utf((*slst)[j]); else reverseword((*slst)[j]);
    }
  }

  // expand suggestions with dot(s)
  if (abbv && pAMgr && pAMgr->get_sugswithdots()) {
    for (int j = 0; j < ns; j++) {
      (*slst)[j] = (char *) realloc((*slst)[j], strlen((*slst)[j]) + 1 + abbv);
      strcat((*slst)[j], word + strlen(word) - abbv);
    }
  }

  // LANG_hu section: replace '-' with ' ' in Hungarian
  if (langnum == LANG_hu) {
      for (int j=0; j < ns; j++) {
          char * pos = strchr((*slst)[j],'-');
          if (pos) {
              int info;
              char w[MAXWORDUTF8LEN];
              *pos = '\0';
              strcpy(w, (*slst)[j]);
              strcat(w, pos + 1);
              spell(w, &info, NULL);
              if ((info & SPELL_COMPOUND) && (info & SPELL_FORBIDDEN)) {
                  *pos = ' ';
              } else *pos = '-';
          }
      }
  }
  // END OF LANG_hu section
  return ns;
}
#endif

int Hunspell::stem(char*** slst, char ** desc, int n)
{
  char result[MAXLNLEN];
  char result2[MAXLNLEN];
  *slst = NULL;
  if (n == 0) return 0;
  *result2 = '\0';
  for (int i = 0; i < n; i++) {
    *result = '\0';
    // add compound word parts (except the last one)
    char * s = (char *) desc[i];
    char * part = strstr(s, MORPH_PART);
    if (part) {
        char * nextpart = strstr(part + 1, MORPH_PART);
        while (nextpart) {
            copy_field(result + strlen(result), part, MORPH_PART);
            part = nextpart;
            nextpart = strstr(part + 1, MORPH_PART);
        }
        s = part;
    }

    char **pl;
    char tok[MAXLNLEN];
    strcpy(tok, s);
    char * alt = strstr(tok, " | ");
    while (alt) {
        alt[1] = MSEP_ALT;
        alt = strstr(alt, " | ");
    }
    int pln = line_tok(tok, &pl, MSEP_ALT);
    for (int k = 0; k < pln; k++) {
        // add derivational suffixes
        if (strstr(pl[k], MORPH_DERI_SFX)) {
            // remove inflectional suffixes
            char * is = strstr(pl[k], MORPH_INFL_SFX);
            if (is) *is = '\0';
            char * sg = pSMgr->suggest_gen(&(pl[k]), 1, pl[k]);
            if (sg) {
                char ** gen;
                int genl = line_tok(sg, &gen, MSEP_REC);
                free(sg);
                for (int j = 0; j < genl; j++) {
                    sprintf(result2 + strlen(result2), "%c%s%s",
                            MSEP_REC, result, gen[j]);
                }
                freelist(&gen, genl);
            }
        } else {
            sprintf(result2 + strlen(result2), "%c%s", MSEP_REC, result);
            if (strstr(pl[k], MORPH_SURF_PFX)) {
                copy_field(result2 + strlen(result2), pl[k], MORPH_SURF_PFX);
            }
            copy_field(result2 + strlen(result2), pl[k], MORPH_STEM);
        }
    }
    freelist(&pl, pln);
  }
  int sln = line_tok(result2, slst, MSEP_REC);
  return uniqlist(*slst, sln);

}

int Hunspell::stem(char*** slst, const char * word)
{
  char ** pl;
  int pln = analyze(&pl, word);
  int pln2 = stem(slst, pl, pln);
  freelist(&pl, pln);
  return pln2;
}

#ifdef HUNSPELL_EXPERIMENTAL
int Hunspell::suggest_pos_stems(char*** slst, const char * word)
{
  char cw[MAXWORDUTF8LEN];
  char wspace[MAXWORDUTF8LEN];
  if (! pSMgr || maxdic == 0) return 0;
  int wl = strlen(word);
  if (utf8) {
    if (wl >= MAXWORDUTF8LEN) return 0;
  } else {
    if (wl >= MAXWORDLEN) return 0;
  }
  int captype = 0;
  int abbv = 0;
  wl = cleanword(cw, word, &captype, &abbv);
  if (wl == 0) return 0;

  int ns = 0; // ns=0 = normalized input

  *slst = NULL; // HU, nsug in pSMgr->suggest

  switch(captype) {
     case HUHCAP:
     case NOCAP:   {
                     ns = pSMgr->suggest_pos_stems(slst, cw, ns);

                     if ((abbv) && (ns == 0)) {
                         memcpy(wspace,cw,wl);
                         *(wspace+wl) = '.';
                         *(wspace+wl+1) = '\0';
                         ns = pSMgr->suggest_pos_stems(slst, wspace, ns);
                     }

                     break;
                   }

     case INITCAP: {

                     ns = pSMgr->suggest_pos_stems(slst, cw, ns);

                     if (ns == 0 || ((*slst)[0][0] == '#')) {
                        memcpy(wspace,cw,(wl+1));
                        mkallsmall(wspace);
                        ns = pSMgr->suggest_pos_stems(slst, wspace, ns);
                     }

                     break;

                   }

     case ALLCAP: {
                     ns = pSMgr->suggest_pos_stems(slst, cw, ns);
                     if (ns != 0) break;

                     memcpy(wspace,cw,(wl+1));
                     mkallsmall(wspace);
                     ns = pSMgr->suggest_pos_stems(slst, wspace, ns);

                     if (ns == 0) {
                         mkinitcap(wspace);
                         ns = pSMgr->suggest_pos_stems(slst, wspace, ns);
                     }
                     break;
                   }
  }

  return ns;
}
#endif // END OF HUNSPELL_EXPERIMENTAL CODE

const char * Hunspell::get_wordchars()
{
  return pAMgr->get_wordchars();
}

unsigned short * Hunspell::get_wordchars_utf16(int * len)
{
  return pAMgr->get_wordchars_utf16(len);
}

void Hunspell::mkinitcap(char * p)
{
  if (!utf8) {
    if (*p != '\0') *p = csconv[((unsigned char)*p)].cupper;
  } else {
      int len;
      w_char u[MAXWORDLEN];
      len = u8_u16(u, MAXWORDLEN, p);
      unsigned short i = unicodetoupper((u[0].h << 8) + u[0].l, langnum);
      u[0].h = (unsigned char) (i >> 8);
      u[0].l = (unsigned char) (i & 0x00FF);
      u16_u8(p, MAXWORDUTF8LEN, u, len);
  }
}

int Hunspell::mkinitcap2(char * p, w_char * u, int nc)
{
  if (!utf8) {
    if (*p != '\0') *p = csconv[((unsigned char)*p)].cupper;
  } else if (nc > 0) {
      unsigned short i = unicodetoupper((u[0].h << 8) + u[0].l, langnum);
      u[0].h = (unsigned char) (i >> 8);
      u[0].l = (unsigned char) (i & 0x00FF);
      u16_u8(p, MAXWORDUTF8LEN, u, nc);
      return strlen(p);
  }
  return nc;
}

int Hunspell::mkinitsmall2(char * p, w_char * u, int nc)
{
  if (!utf8) {
    if (*p != '\0') *p = csconv[((unsigned char)*p)].clower;
  } else if (nc > 0) {
      unsigned short i = unicodetolower((u[0].h << 8) + u[0].l, langnum);
      u[0].h = (unsigned char) (i >> 8);
      u[0].l = (unsigned char) (i & 0x00FF);
      u16_u8(p, MAXWORDUTF8LEN, u, nc);
      return strlen(p);
  }
  return nc;
}

int Hunspell::add(const char * word)
{
    if (pHMgr[0]) return (pHMgr[0])->add(word);
    return 0;
}

int Hunspell::add_with_affix(const char * word, const char * example)
{
    if (pHMgr[0]) return (pHMgr[0])->add_with_affix(word, example);
    return 0;
}

int Hunspell::remove(const char * word)
{
    if (pHMgr[0]) return (pHMgr[0])->remove(word);
    return 0;
}

const char * Hunspell::get_version()
{
  return pAMgr->get_version();
}

struct cs_info * Hunspell::get_csconv()
{
  return csconv;
}

void Hunspell::cat_result(char * result, char * st)
{
    if (st) {
        if (*result) mystrcat(result, "\n", MAXLNLEN);
        mystrcat(result, st, MAXLNLEN);
        free(st);
    }
}

int Hunspell::analyze(char*** slst, const char * word)
{
  char cw[MAXWORDUTF8LEN];
  char wspace[MAXWORDUTF8LEN];
  w_char unicw[MAXWORDLEN];
  int wl2 = 0;
  *slst = NULL;
  if (! pSMgr || maxdic == 0) return 0;
  int nc = strlen(word);
  if (utf8) {
    if (nc >= MAXWORDUTF8LEN) return 0;
  } else {
    if (nc >= MAXWORDLEN) return 0;
  }
  int captype = 0;
  int abbv = 0;
  int wl = 0;

  // input conversion
  RepList * rl = (pAMgr) ? pAMgr->get_iconvtable() : NULL;
  if (rl && rl->conv(word, wspace)) wl = cleanword2(cw, wspace, unicw, &nc, &captype, &abbv);
  else wl = cleanword2(cw, word, unicw, &nc, &captype, &abbv);

  if (wl == 0) {
      if (abbv) {
          for (wl = 0; wl < abbv; wl++) cw[wl] = '.';
          cw[wl] = '\0';
          abbv = 0;
      } else return 0;
  }

  char result[MAXLNLEN];
  char * st = NULL;

  *result = '\0';

  int n = 0;
  int n2 = 0;
  int n3 = 0;

  // test numbers
  // LANG_hu section: set dash information for suggestions
  if (langnum == LANG_hu) {
  while ((n < wl) &&
        (((cw[n] <= '9') && (cw[n] >= '0')) || (((cw[n] == '.') || (cw[n] == ',')) && (n > 0)))) {
        n++;
        if ((cw[n] == '.') || (cw[n] == ',')) {
                if (((n2 == 0) && (n > 3)) ||
                        ((n2 > 0) && ((cw[n-1] == '.') || (cw[n-1] == ',')))) break;
                n2++;
                n3 = n;
        }
  }

  if ((n == wl) && (n3 > 0) && (n - n3 > 3)) return 0;
  if ((n == wl) || ((n>0) && ((cw[n]=='%') || (cw[n]=='\xB0')) && checkword(cw+n, NULL, NULL))) {
        mystrcat(result, cw, MAXLNLEN);
        result[n - 1] = '\0';
        if (n == wl) cat_result(result, pSMgr->suggest_morph(cw + n - 1));
        else {
                char sign = cw[n];
                cw[n] = '\0';
                cat_result(result, pSMgr->suggest_morph(cw + n - 1));
                mystrcat(result, "+", MAXLNLEN); // XXX SPEC. MORPHCODE
                cw[n] = sign;
                cat_result(result, pSMgr->suggest_morph(cw + n));
        }
        return line_tok(result, slst, MSEP_REC);
  }
  }
  // END OF LANG_hu section

  switch(captype) {
     case HUHCAP:
     case HUHINITCAP:
     case NOCAP:  {
                    cat_result(result, pSMgr->suggest_morph(cw));
                    if (abbv) {
                        memcpy(wspace,cw,wl);
                        *(wspace+wl) = '.';
                        *(wspace+wl+1) = '\0';
                        cat_result(result, pSMgr->suggest_morph(wspace));
                    }
                    break;
                }
     case INITCAP: {
                     wl = mkallsmall2(cw, unicw, nc);
                     memcpy(wspace,cw,(wl+1));
                     wl2 = mkinitcap2(cw, unicw, nc);
                     cat_result(result, pSMgr->suggest_morph(wspace));
                     cat_result(result, pSMgr->suggest_morph(cw));
                     if (abbv) {
                         *(wspace+wl) = '.';
                         *(wspace+wl+1) = '\0';
                         cat_result(result, pSMgr->suggest_morph(wspace));

                         memcpy(wspace, cw, wl2);
                         *(wspace+wl2) = '.';
                         *(wspace+wl2+1) = '\0';

                         cat_result(result, pSMgr->suggest_morph(wspace));
                     }
                     break;
                   }
     case ALLCAP: {
                     cat_result(result, pSMgr->suggest_morph(cw));
                     if (abbv) {
                         memcpy(wspace,cw,wl);
                         *(wspace+wl) = '.';
                         *(wspace+wl+1) = '\0';
                         cat_result(result, pSMgr->suggest_morph(cw));
                     }
                     wl = mkallsmall2(cw, unicw, nc);
                     memcpy(wspace,cw,(wl+1));
                     wl2 = mkinitcap2(cw, unicw, nc);

                     cat_result(result, pSMgr->suggest_morph(wspace));
                     cat_result(result, pSMgr->suggest_morph(cw));
                     if (abbv) {
                         *(wspace+wl) = '.';
                         *(wspace+wl+1) = '\0';
                         cat_result(result, pSMgr->suggest_morph(wspace));

                         memcpy(wspace, cw, wl2);
                         *(wspace+wl2) = '.';
                         *(wspace+wl2+1) = '\0';

                         cat_result(result, pSMgr->suggest_morph(wspace));
                     }
                     break;
                   }
  }

  if (*result) {
    // word reversing wrapper for complex prefixes
    if (complexprefixes) {
      if (utf8) reverseword_utf(result); else reverseword(result);
    }
    return line_tok(result, slst, MSEP_REC);
  }

  // compound word with dash (HU) I18n
  char * dash = NULL;
  int nresult = 0;
  // LANG_hu section: set dash information for suggestions
  if (langnum == LANG_hu) dash = (char *) strchr(cw,'-');
  if ((langnum == LANG_hu) && dash) {
      *dash='\0';
      // examine 2 sides of the dash
      if (dash[1] == '\0') { // base word ending with dash
        if (spell(cw)) {
		char * p = pSMgr->suggest_morph(cw);
		if (p) {
		    int ret = line_tok(p, slst, MSEP_REC);
		    free(p);
		    return ret;
		}
		
	}
      } else if ((dash[1] == 'e') && (dash[2] == '\0')) { // XXX (HU) -e hat.
        if (spell(cw) && (spell("-e"))) {
                        st = pSMgr->suggest_morph(cw);
                        if (st) {
                                mystrcat(result, st, MAXLNLEN);
                                free(st);
                        }
                        mystrcat(result,"+", MAXLNLEN); // XXX spec. separator in MORPHCODE
                        st = pSMgr->suggest_morph("-e");
                        if (st) {
                                mystrcat(result, st, MAXLNLEN);
                                free(st);
                        }
                        return line_tok(result, slst, MSEP_REC);
                }
      } else {
      // first word ending with dash: word- XXX ???
        char r2 = *(dash + 1);
        dash[0]='-';
        dash[1]='\0';
        nresult = spell(cw);
        dash[1] = r2;
        dash[0]='\0';
        if (nresult && spell(dash+1) && ((strlen(dash+1) > 1) ||
                ((dash[1] > '0') && (dash[1] < '9')))) {
                            st = pSMgr->suggest_morph(cw);
                            if (st) {
                                mystrcat(result, st, MAXLNLEN);
                                    free(st);
                                mystrcat(result,"+", MAXLNLEN); // XXX spec. separator in MORPHCODE
                            }
                            st = pSMgr->suggest_morph(dash+1);
                            if (st) {
                                    mystrcat(result, st, MAXLNLEN);
                                    free(st);
                            }
                            return line_tok(result, slst, MSEP_REC);
                        }
      }
      // affixed number in correct word
     if (nresult && (dash > cw) && (((*(dash-1)<='9') &&
                        (*(dash-1)>='0')) || (*(dash-1)=='.'))) {
         *dash='-';
         n = 1;
         if (*(dash - n) == '.') n++;
         // search first not a number character to left from dash
         while (((dash - n)>=cw) && ((*(dash - n)=='0') || (n < 3)) && (n < 6)) {
            n++;
         }
         if ((dash - n) < cw) n--;
         // numbers: valami1000000-hoz
         // examine 100000-hoz, 10000-hoz 1000-hoz, 10-hoz,
         // 56-hoz, 6-hoz
         for(; n >= 1; n--) {
            if ((*(dash - n) >= '0') && (*(dash - n) <= '9') && checkword(dash - n, NULL, NULL)) {
                    mystrcat(result, cw, MAXLNLEN);
                    result[dash - cw - n] = '\0';
                        st = pSMgr->suggest_morph(dash - n);
                        if (st) {
                        mystrcat(result, st, MAXLNLEN);
                                free(st);
                        }
                        return line_tok(result, slst, MSEP_REC);
            }
         }
     }
  }
  return 0;
}

int Hunspell::generate(char*** slst, const char * word, char ** pl, int pln)
{
  *slst = NULL;
  if (!pSMgr || !pln) return 0;
  char **pl2;
  int pl2n = analyze(&pl2, word);
  int captype = 0;
  int abbv = 0;
  char cw[MAXWORDUTF8LEN];
  cleanword(cw, word, &captype, &abbv);
  char result[MAXLNLEN];
  *result = '\0';

  for (int i = 0; i < pln; i++) {
    cat_result(result, pSMgr->suggest_gen(pl2, pl2n, pl[i]));
  }
  freelist(&pl2, pl2n);

  if (*result) {
    // allcap
    if (captype == ALLCAP) mkallcap(result);

    // line split
    int linenum = line_tok(result, slst, MSEP_REC);

    // capitalize
    if (captype == INITCAP || captype == HUHINITCAP) {
        for (int j=0; j < linenum; j++) mkinitcap((*slst)[j]);
    }

    // temporary filtering of prefix related errors (eg.
    // generate("undrinkable", "eats") --> "undrinkables" and "*undrinks")

    int r = 0;
    for (int j=0; j < linenum; j++) {
        if (!spell((*slst)[j])) {
            free((*slst)[j]);
            (*slst)[j] = NULL;
        } else {
            if (r < j) (*slst)[r] = (*slst)[j];
            r++;
        }
    }
    if (r > 0) return r;
    free(*slst);
    *slst = NULL;
  }
  return 0;
}

int Hunspell::generate(char*** slst, const char * word, const char * pattern)
{
  char **pl;
  int pln = analyze(&pl, pattern);
  int n = generate(slst, word, pl, pln);
  freelist(&pl, pln);
  return uniqlist(*slst, n);
}

// minimal XML parser functions
int Hunspell::get_xml_par(char * dest, const char * par, int max)
{
   char * d = dest;
   if (!par) return 0;
   char end = *par;
   char * dmax = dest + max;
   if (end == '>') end = '<';
   else if (end != '\'' && end != '"') return 0; // bad XML
   for (par++; d < dmax && *par != '\0' && *par != end; par++, d++) *d = *par;
   *d = '\0';
   mystrrep(dest, "&lt;", "<");
   mystrrep(dest, "&amp;", "&");
   return (int)(d - dest);
}

int Hunspell::get_langnum() const
{
   return langnum;
}

// return the beginning of the element (attr == NULL) or the attribute
const char * Hunspell::get_xml_pos(const char * s, const char * attr)
{
  const char * end = strchr(s, '>');
  const char * p = s;
  if (attr == NULL) return end;
  do {
    p = strstr(p, attr);
    if (!p || p >= end) return 0;
  } while (*(p-1) != ' ' &&  *(p-1) != '\n');
  return p + strlen(attr);
}

int Hunspell::check_xml_par(const char * q, const char * attr, const char * value) {
  char cw[MAXWORDUTF8LEN];
  if (get_xml_par(cw, get_xml_pos(q, attr), MAXWORDUTF8LEN - 1) &&
    strcmp(cw, value) == 0) return 1;
  return 0;
}

int Hunspell::get_xml_list(char ***slst, char * list, const char * tag) {
    int n = 0;
    char * p;
    if (!list) return 0;
    for (p = list; (p = strstr(p, tag)); p++) n++;
    if (n == 0) return 0;
    *slst = (char **) malloc(sizeof(char *) * n);
    if (!*slst) return 0;
    for (p = list, n = 0; (p = strstr(p, tag)); p++, n++) {
        int l = strlen(p);
        (*slst)[n] = (char *) malloc(l + 1);
        if (!(*slst)[n]) return n;
        if (!get_xml_par((*slst)[n], p + strlen(tag) - 1, l)) {
            free((*slst)[n]);
            break;
        }
    }
    return n;
}

int Hunspell::spellml(char*** slst, const char * word)
{
  char *q, *q2;
  char cw[MAXWORDUTF8LEN], cw2[MAXWORDUTF8LEN];
  q = (char *) strstr(word, "<query");
  if (!q) return 0; // bad XML input
  q2 = strchr(q, '>');
  if (!q2) return 0; // bad XML input
  q2 = strstr(q2, "<word");
  if (!q2) return 0; // bad XML input
  if (check_xml_par(q, "type=", "analyze")) {
      int n = 0, s = 0;
      if (get_xml_par(cw, strchr(q2, '>'), MAXWORDUTF8LEN - 10)) n = analyze(slst, cw);
      if (n == 0) return 0;
      // convert the result to <code><a>ana1</a><a>ana2</a></code> format
      for (int i = 0; i < n; i++) s+= strlen((*slst)[i]);
      char * r = (char *) malloc(6 + 5 * s + 7 * n + 7 + 1); // XXX 5*s->&->&amp;
      if (!r) return 0;
      strcpy(r, "<code>");
      for (int i = 0; i < n; i++) {
        int l = strlen(r);
        strcpy(r + l, "<a>");
        strcpy(r + l + 3, (*slst)[i]);
        mystrrep(r + l + 3, "\t", " ");
        mystrrep(r + l + 3, "<", "&lt;");
        mystrrep(r + l + 3, "&", "&amp;");
        strcat(r, "</a>");
        free((*slst)[i]);
      }
      strcat(r, "</code>");
      (*slst)[0] = r;
      return 1;
  } else if (check_xml_par(q, "type=", "stem")) {
      if (get_xml_par(cw, strchr(q2, '>'), MAXWORDUTF8LEN - 1)) return stem(slst, cw);
  } else if (check_xml_par(q, "type=", "generate")) {
      int n = get_xml_par(cw, strchr(q2, '>'), MAXWORDUTF8LEN - 1);
      if (n == 0) return 0;
      char * q3 = strstr(q2 + 1, "<word");
      if (q3) {
        if (get_xml_par(cw2, strchr(q3, '>'), MAXWORDUTF8LEN - 1)) {
            return generate(slst, cw, cw2);
        }
      } else {
        if ((q2 = strstr(q2 + 1, "<code"))) {
          char ** slst2;
          if ((n = get_xml_list(&slst2, strchr(q2, '>'), "<a>"))) {
            int n2 = generate(slst, cw, slst2, n);
            freelist(&slst2, n);
            return uniqlist(*slst, n2);
          }
          freelist(&slst2, n);
        }
      }
  }
  return 0;
}


#ifdef HUNSPELL_EXPERIMENTAL
// XXX need UTF-8 support
char * Hunspell::morph_with_correction(const char * word)
{
  char cw[MAXWORDUTF8LEN];
  char wspace[MAXWORDUTF8LEN];
  if (! pSMgr || maxdic == 0) return NULL;
  int wl = strlen(word);
  if (utf8) {
    if (wl >= MAXWORDUTF8LEN) return NULL;
  } else {
    if (wl >= MAXWORDLEN) return NULL;
  }
  int captype = 0;
  int abbv = 0;
  wl = cleanword(cw, word, &captype, &abbv);
  if (wl == 0) return NULL;

  char result[MAXLNLEN];
  char * st = NULL;

  *result = '\0';


  switch(captype) {
     case NOCAP:   {
                     st = pSMgr->suggest_morph_for_spelling_error(cw);
                     if (st) {
                        mystrcat(result, st, MAXLNLEN);
                        free(st);
                     }
                     if (abbv) {
                         memcpy(wspace,cw,wl);
                         *(wspace+wl) = '.';
                         *(wspace+wl+1) = '\0';
                         st = pSMgr->suggest_morph_for_spelling_error(wspace);
                         if (st) {
                            if (*result) mystrcat(result, "\n", MAXLNLEN);
                            mystrcat(result, st, MAXLNLEN);
                            free(st);
                                                 }
                     }
                                         break;
                   }
     case INITCAP: {
                     memcpy(wspace,cw,(wl+1));
                     mkallsmall(wspace);
                     st = pSMgr->suggest_morph_for_spelling_error(wspace);
                     if (st) {
                        mystrcat(result, st, MAXLNLEN);
                        free(st);
                     }
                     st = pSMgr->suggest_morph_for_spelling_error(cw);
                     if (st) {
                        if (*result) mystrcat(result, "\n", MAXLNLEN);
                        mystrcat(result, st, MAXLNLEN);
                        free(st);
                     }
                     if (abbv) {
                         memcpy(wspace,cw,wl);
                         *(wspace+wl) = '.';
                         *(wspace+wl+1) = '\0';
                         mkallsmall(wspace);
                         st = pSMgr->suggest_morph_for_spelling_error(wspace);
                         if (st) {
                            if (*result) mystrcat(result, "\n", MAXLNLEN);
                            mystrcat(result, st, MAXLNLEN);
                            free(st);
                         }
                         mkinitcap(wspace);
                         st = pSMgr->suggest_morph_for_spelling_error(wspace);
                         if (st) {
                            if (*result) mystrcat(result, "\n", MAXLNLEN);
                            mystrcat(result, st, MAXLNLEN);
                            free(st);
                         }
                     }
                     break;
                   }
     case HUHCAP: {
                     st = pSMgr->suggest_morph_for_spelling_error(cw);
                     if (st) {
                        mystrcat(result, st, MAXLNLEN);
                        free(st);
                     }
                     memcpy(wspace,cw,(wl+1));
                     mkallsmall(wspace);
                     st = pSMgr->suggest_morph_for_spelling_error(wspace);
                     if (st) {
                        if (*result) mystrcat(result, "\n", MAXLNLEN);
                        mystrcat(result, st, MAXLNLEN);
                        free(st);
                     }
                     break;
                 }
     case ALLCAP: {
                     memcpy(wspace,cw,(wl+1));
                     st = pSMgr->suggest_morph_for_spelling_error(wspace);
                     if (st) {
                        mystrcat(result, st, MAXLNLEN);
                        free(st);
                     }
                     mkallsmall(wspace);
                     st = pSMgr->suggest_morph_for_spelling_error(wspace);
                     if (st) {
                        if (*result) mystrcat(result, "\n", MAXLNLEN);
                        mystrcat(result, st, MAXLNLEN);
                        free(st);
                     }
                     mkinitcap(wspace);
                     st = pSMgr->suggest_morph_for_spelling_error(wspace);
                     if (st) {
                        if (*result) mystrcat(result, "\n", MAXLNLEN);
                        mystrcat(result, st, MAXLNLEN);
                        free(st);
                     }
                     if (abbv) {
                        memcpy(wspace,cw,(wl+1));
                        *(wspace+wl) = '.';
                        *(wspace+wl+1) = '\0';
                        if (*result) mystrcat(result, "\n", MAXLNLEN);
                        st = pSMgr->suggest_morph_for_spelling_error(wspace);
                        if (st) {
                            mystrcat(result, st, MAXLNLEN);
                            free(st);
                        }
                        mkallsmall(wspace);
                        st = pSMgr->suggest_morph_for_spelling_error(wspace);
                        if (st) {
                          if (*result) mystrcat(result, "\n", MAXLNLEN);
                          mystrcat(result, st, MAXLNLEN);
                          free(st);
                        }
                        mkinitcap(wspace);
                        st = pSMgr->suggest_morph_for_spelling_error(wspace);
                        if (st) {
                          if (*result) mystrcat(result, "\n", MAXLNLEN);
                          mystrcat(result, st, MAXLNLEN);
                          free(st);
                        }
                     }
                     break;
                   }
  }

  if (*result) return mystrdup(result);
  return NULL;
}

#endif // END OF HUNSPELL_EXPERIMENTAL CODE

Hunhandle *Hunspell_create(const char * affpath, const char * dpath)
{
        return (Hunhandle*)(new Hunspell(affpath, dpath));
}

Hunhandle *Hunspell_create_key(const char * affpath, const char * dpath,
    const char * key)
{
        return (Hunhandle*)(new Hunspell(affpath, dpath, key));
}

void Hunspell_destroy(Hunhandle *pHunspell)
{
        delete (Hunspell*)(pHunspell);
}

int Hunspell_spell(Hunhandle *pHunspell, const char *word)
{
        return ((Hunspell*)pHunspell)->spell(word);
}

char *Hunspell_get_dic_encoding(Hunhandle *pHunspell)
{
        return ((Hunspell*)pHunspell)->get_dic_encoding();
}

int Hunspell_suggest(Hunhandle *pHunspell, char*** slst, const char * word)
{
        return ((Hunspell*)pHunspell)->suggest(slst, word);
}

int Hunspell_analyze(Hunhandle *pHunspell, char*** slst, const char * word)
{
        return ((Hunspell*)pHunspell)->analyze(slst, word);
}

int Hunspell_stem(Hunhandle *pHunspell, char*** slst, const char * word)
{
        return ((Hunspell*)pHunspell)->stem(slst, word);
}

int Hunspell_stem2(Hunhandle *pHunspell, char*** slst, char** desc, int n)
{
        return ((Hunspell*)pHunspell)->stem(slst, desc, n);
}

int Hunspell_generate(Hunhandle *pHunspell, char*** slst, const char * word,
    const char * word2)
{
        return ((Hunspell*)pHunspell)->generate(slst, word, word2);
}

int Hunspell_generate2(Hunhandle *pHunspell, char*** slst, const char * word,
    char** desc, int n)
{
        return ((Hunspell*)pHunspell)->generate(slst, word, desc, n);
}

  /* functions for run-time modification of the dictionary */

  /* add word to the run-time dictionary */

int Hunspell_add(Hunhandle *pHunspell, const char * word) {
        return ((Hunspell*)pHunspell)->add(word);
}

  /* add word to the run-time dictionary with affix flags of
   * the example (a dictionary word): Hunspell will recognize
   * affixed forms of the new word, too.
   */

int Hunspell_add_with_affix(Hunhandle *pHunspell, const char * word,
        const char * example) {
        return ((Hunspell*)pHunspell)->add_with_affix(word, example);
}

  /* remove word from the run-time dictionary */

int Hunspell_remove(Hunhandle *pHunspell, const char * word) {
        return ((Hunspell*)pHunspell)->remove(word);
}

void Hunspell_free_list(Hunhandle *, char *** slst, int n) {
        freelist(slst, n);
}
