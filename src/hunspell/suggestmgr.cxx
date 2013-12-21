#include "license.hunspell"
#include "license.myspell"

#include <stdlib.h> 
#include <string.h>
#include <stdio.h> 
#include <ctype.h>

#include "suggestmgr.hxx"
#include "htypes.hxx"
#include "csutil.hxx"

const w_char W_VLINE = { '\0', '|' };

SuggestMgr::SuggestMgr(const char * tryme, int maxn, 
                       AffixMgr * aptr)
{

  // register affix manager and check in string of chars to 
  // try when building candidate suggestions
  pAMgr = aptr;

  csconv = NULL;

  ckeyl = 0;
  ckey = NULL;
  ckey_utf = NULL;

  ctryl = 0;
  ctry = NULL;
  ctry_utf = NULL;

  utf8 = 0;
  langnum = 0;
  complexprefixes = 0;  
  
  maxSug = maxn;
  nosplitsugs = 0;
  maxngramsugs = MAXNGRAMSUGS;
  maxcpdsugs = MAXCOMPOUNDSUGS;

  if (pAMgr) {
        langnum = pAMgr->get_langnum();
        ckey = pAMgr->get_key_string();
        nosplitsugs = pAMgr->get_nosplitsugs();
        if (pAMgr->get_maxngramsugs() >= 0)
            maxngramsugs = pAMgr->get_maxngramsugs();
        utf8 = pAMgr->get_utf8();
	if (pAMgr->get_maxcpdsugs() >= 0)
	    maxcpdsugs = pAMgr->get_maxcpdsugs();
        if (!utf8)
        {
            char * enc = pAMgr->get_encoding();
            csconv = get_current_cs(enc);
            free(enc);
        }
        complexprefixes = pAMgr->get_complexprefixes();
  }

  if (ckey) {  
    if (utf8) {
        w_char t[MAXSWL];    
        ckeyl = u8_u16(t, MAXSWL, ckey);
        ckey_utf = (w_char *) malloc(ckeyl * sizeof(w_char));
        if (ckey_utf) memcpy(ckey_utf, t, ckeyl * sizeof(w_char));
        else ckeyl = 0;
    } else {
        ckeyl = strlen(ckey);
    }
  }
  
  if (tryme) {  
    ctry = mystrdup(tryme);
    if (ctry) ctryl = strlen(ctry);
    if (ctry && utf8) {
        w_char t[MAXSWL];    
        ctryl = u8_u16(t, MAXSWL, tryme);
        ctry_utf = (w_char *) malloc(ctryl * sizeof(w_char));
        if (ctry_utf) memcpy(ctry_utf, t, ctryl * sizeof(w_char));
        else ctryl = 0;
    }
  }
}


SuggestMgr::~SuggestMgr()
{
  pAMgr = NULL;
  if (ckey) free(ckey);
  ckey = NULL;
  if (ckey_utf) free(ckey_utf);
  ckey_utf = NULL;
  ckeyl = 0;
  if (ctry) free(ctry);
  ctry = NULL;
  if (ctry_utf) free(ctry_utf);
  ctry_utf = NULL;
  ctryl = 0;
  maxSug = 0;
#ifdef MOZILLA_CLIENT
  delete [] csconv;
#endif
}

int SuggestMgr::testsug(char** wlst, const char * candidate, int wl, int ns, int cpdsuggest,
   int * timer, clock_t * timelimit) {
      int cwrd = 1;
      if (ns == maxSug) return maxSug;
      for (int k=0; k < ns; k++) {
        if (strcmp(candidate,wlst[k]) == 0) cwrd = 0;
      }
      if ((cwrd) && checkword(candidate, wl, cpdsuggest, timer, timelimit)) {
        wlst[ns] = mystrdup(candidate);
        if (wlst[ns] == NULL) {
            for (int j=0; j<ns; j++) free(wlst[j]);
            return -1;
        }
        ns++;
      } 
      return ns;
}

// generate suggestions for a misspelled word
//    pass in address of array of char * pointers
// onlycompoundsug: probably bad suggestions (need for ngram sugs, too)

int SuggestMgr::suggest(char*** slst, const char * w, int nsug,
    int * onlycompoundsug)
{
  int nocompoundtwowords = 0;
  char ** wlst;    
  w_char word_utf[MAXSWL];
  int wl = 0;
  int nsugorig = nsug;
  char w2[MAXWORDUTF8LEN];
  const char * word = w;
  int oldSug = 0;

  // word reversing wrapper for complex prefixes
  if (complexprefixes) {
    strcpy(w2, w);
    if (utf8) reverseword_utf(w2); else reverseword(w2);
    word = w2;
  }
    
    if (*slst) {
        wlst = *slst;
    } else {
        wlst = (char **) malloc(maxSug * sizeof(char *));
        if (wlst == NULL) return -1;
        for (int i = 0; i < maxSug; i++) {
            wlst[i] = NULL;
        }
    }
    
    if (utf8) {
        wl = u8_u16(word_utf, MAXSWL, word);
	if (wl == -1) {
    		*slst = wlst;
		 return nsug;
	}
    }

    for (int cpdsuggest=0; (cpdsuggest<2) && (nocompoundtwowords==0); cpdsuggest++) {

    // limit compound suggestion
    if (cpdsuggest > 0) oldSug = nsug;

    // suggestions for an uppercase word (html -> HTML)
    if ((nsug < maxSug) && (nsug > -1)) {
        nsug = (utf8) ? capchars_utf(wlst, word_utf, wl, nsug, cpdsuggest) :
                    capchars(wlst, word, nsug, cpdsuggest);
    }

    // perhaps we made a typical fault of spelling
    if ((nsug < maxSug) && (nsug > -1) && (!cpdsuggest || (nsug < oldSug + maxcpdsugs))) {
      nsug = replchars(wlst, word, nsug, cpdsuggest);
    }

    // perhaps we made chose the wrong char from a related set
    if ((nsug < maxSug) && (nsug > -1) && (!cpdsuggest || (nsug < oldSug + maxcpdsugs))) {
      nsug = mapchars(wlst, word, nsug, cpdsuggest);
    }

    // only suggest compound words when no other suggestion
    if ((cpdsuggest == 0) && (nsug > nsugorig)) nocompoundtwowords=1;

    // did we swap the order of chars by mistake
    if ((nsug < maxSug) && (nsug > -1) && (!cpdsuggest || (nsug < oldSug + maxcpdsugs))) {
        nsug = (utf8) ? swapchar_utf(wlst, word_utf, wl, nsug, cpdsuggest) :
                    swapchar(wlst, word, nsug, cpdsuggest);
    }

    // did we swap the order of non adjacent chars by mistake
    if ((nsug < maxSug) && (nsug > -1) && (!cpdsuggest || (nsug < oldSug + maxcpdsugs))) {
        nsug = (utf8) ? longswapchar_utf(wlst, word_utf, wl, nsug, cpdsuggest) :
                    longswapchar(wlst, word, nsug, cpdsuggest);
    }

    // did we just hit the wrong key in place of a good char (case and keyboard)
    if ((nsug < maxSug) && (nsug > -1) && (!cpdsuggest || (nsug < oldSug + maxcpdsugs))) {
        nsug = (utf8) ? badcharkey_utf(wlst, word_utf, wl, nsug, cpdsuggest) :
                    badcharkey(wlst, word, nsug, cpdsuggest);
    }

    // did we add a char that should not be there
    if ((nsug < maxSug) && (nsug > -1) && (!cpdsuggest || (nsug < oldSug + maxcpdsugs))) {
        nsug = (utf8) ? extrachar_utf(wlst, word_utf, wl, nsug, cpdsuggest) :
                    extrachar(wlst, word, nsug, cpdsuggest);
    }


    // did we forgot a char
    if ((nsug < maxSug) && (nsug > -1) && (!cpdsuggest || (nsug < oldSug + maxcpdsugs))) {
        nsug = (utf8) ? forgotchar_utf(wlst, word_utf, wl, nsug, cpdsuggest) :
                    forgotchar(wlst, word, nsug, cpdsuggest);
    }

    // did we move a char
    if ((nsug < maxSug) && (nsug > -1) && (!cpdsuggest || (nsug < oldSug + maxcpdsugs))) {
        nsug = (utf8) ? movechar_utf(wlst, word_utf, wl, nsug, cpdsuggest) :
                    movechar(wlst, word, nsug, cpdsuggest);
    }

    // did we just hit the wrong key in place of a good char
    if ((nsug < maxSug) && (nsug > -1) && (!cpdsuggest || (nsug < oldSug + maxcpdsugs))) {
        nsug = (utf8) ? badchar_utf(wlst, word_utf, wl, nsug, cpdsuggest) :
                    badchar(wlst, word, nsug, cpdsuggest);
    }

    // did we double two characters
    if ((nsug < maxSug) && (nsug > -1) && (!cpdsuggest || (nsug < oldSug + maxcpdsugs))) {
        nsug = (utf8) ? doubletwochars_utf(wlst, word_utf, wl, nsug, cpdsuggest) :
                    doubletwochars(wlst, word, nsug, cpdsuggest);
    }

    // perhaps we forgot to hit space and two words ran together
    if (!nosplitsugs && (nsug < maxSug) && (nsug > -1) && (!cpdsuggest || (nsug < oldSug + maxcpdsugs))) {
        nsug = twowords(wlst, word, nsug, cpdsuggest);
    }

    } // repeating ``for'' statement compounding support

    if (nsug < 0) {
     // we ran out of memory - we should free up as much as possible
       for (int i = 0; i < maxSug; i++)
         if (wlst[i] != NULL) free(wlst[i]);
       free(wlst);
       wlst = NULL;
    }

    if (!nocompoundtwowords && (nsug > 0) && onlycompoundsug) *onlycompoundsug = 1;

    *slst = wlst;
    return nsug;
}

// generate suggestions for a word with typical mistake
//    pass in address of array of char * pointers
#ifdef HUNSPELL_EXPERIMENTAL
int SuggestMgr::suggest_auto(char*** slst, const char * w, int nsug)
{
    int nocompoundtwowords = 0;
    char ** wlst;
    int oldSug;

  char w2[MAXWORDUTF8LEN];
  const char * word = w;

  // word reversing wrapper for complex prefixes
  if (complexprefixes) {
    strcpy(w2, w);
    if (utf8) reverseword_utf(w2); else reverseword(w2);
    word = w2;
  }

    if (*slst) {
        wlst = *slst;
    } else {
        wlst = (char **) malloc(maxSug * sizeof(char *));
        if (wlst == NULL) return -1;
    }

    for (int cpdsuggest=0; (cpdsuggest<2) && (nocompoundtwowords==0); cpdsuggest++) {

    // limit compound suggestion
    if (cpdsuggest > 0) oldSug = nsug;

    // perhaps we made a typical fault of spelling
    if ((nsug < maxSug) && (nsug > -1))
    nsug = replchars(wlst, word, nsug, cpdsuggest);

    // perhaps we made chose the wrong char from a related set
    if ((nsug < maxSug) && (nsug > -1) && (!cpdsuggest || (nsug < oldSug + maxcpdsugs)))
      nsug = mapchars(wlst, word, nsug, cpdsuggest);

    if ((cpdsuggest==0) && (nsug>0)) nocompoundtwowords=1;

    // perhaps we forgot to hit space and two words ran together

    if ((nsug < maxSug) && (nsug > -1) && (!cpdsuggest || (nsug < oldSug + maxcpdsugs)) && check_forbidden(word, strlen(word))) {
                nsug = twowords(wlst, word, nsug, cpdsuggest);
        }
    
    } // repeating ``for'' statement compounding support

    if (nsug < 0) {
       for (int i=0;i<maxSug; i++)
         if (wlst[i] != NULL) free(wlst[i]);
       free(wlst);
       return -1;
    }

    *slst = wlst;
    return nsug;
}
#endif // END OF HUNSPELL_EXPERIMENTAL CODE

// suggestions for an uppercase word (html -> HTML)
int SuggestMgr::capchars_utf(char ** wlst, const w_char * word, int wl, int ns, int cpdsuggest)
{
  char candidate[MAXSWUTF8L];
  w_char candidate_utf[MAXSWL];
  memcpy(candidate_utf, word, wl * sizeof(w_char));
  mkallcap_utf(candidate_utf, wl, langnum);
  u16_u8(candidate, MAXSWUTF8L, candidate_utf, wl);
  return testsug(wlst, candidate, strlen(candidate), ns, cpdsuggest, NULL, NULL);
}

// suggestions for an uppercase word (html -> HTML)
int SuggestMgr::capchars(char** wlst, const char * word, int ns, int cpdsuggest)
{
  char candidate[MAXSWUTF8L];
  strcpy(candidate, word);
  mkallcap(candidate, csconv);
  return testsug(wlst, candidate, strlen(candidate), ns, cpdsuggest, NULL, NULL);
}

// suggestions for when chose the wrong char out of a related set
int SuggestMgr::mapchars(char** wlst, const char * word, int ns, int cpdsuggest)
{
  char candidate[MAXSWUTF8L];
  clock_t timelimit;
  int timer;
  candidate[0] = '\0';

  int wl = strlen(word);
  if (wl < 2 || ! pAMgr) return ns;

  int nummap = pAMgr->get_nummap();
  struct mapentry* maptable = pAMgr->get_maptable();
  if (maptable==NULL) return ns;

  timelimit = clock();
  timer = MINTIMER;
  return map_related(word, (char *) &candidate, 0, 0, wlst, cpdsuggest, ns, maptable, nummap, &timer, &timelimit);
}

int SuggestMgr::map_related(const char * word, char * candidate, int wn, int cn,
    char** wlst, int cpdsuggest,  int ns,
    const mapentry* maptable, int nummap, int * timer, clock_t * timelimit)
{
  if (*(word + wn) == '\0') {
      int cwrd = 1;
      *(candidate + cn) = '\0';
      int wl = strlen(candidate);
      for (int m=0; m < ns; m++)
          if (strcmp(candidate, wlst[m]) == 0) cwrd = 0;
      if ((cwrd) && checkword(candidate, wl, cpdsuggest, timer, timelimit)) {
          if (ns < maxSug) {
              wlst[ns] = mystrdup(candidate);
              if (wlst[ns] == NULL) return -1;
              ns++;
          }
      }
      return ns;
  } 
  int in_map = 0;
  for (int j = 0; j < nummap; j++) {
    for (int k = 0; k < maptable[j].len; k++) {
      int len = strlen(maptable[j].set[k]);
      if (strncmp(maptable[j].set[k], word + wn, len) == 0) {
        in_map = 1;
        for (int l = 0; l < maptable[j].len; l++) {
	  strcpy(candidate + cn, maptable[j].set[l]);
	  ns = map_related(word, candidate, wn + len, strlen(candidate), wlst,
		cpdsuggest, ns, maptable, nummap, timer, timelimit);
    	  if (!(*timer)) return ns;
	}
      }
    }
  }
  if (!in_map) {
     *(candidate + cn) = *(word + wn);
     ns = map_related(word, candidate, wn + 1, cn + 1, wlst, cpdsuggest,
        ns, maptable, nummap, timer, timelimit);
  }
  return ns;
}

// suggestions for a typical fault of spelling, that
// differs with more, than 1 letter from the right form.
int SuggestMgr::replchars(char** wlst, const char * word, int ns, int cpdsuggest)
{
  char candidate[MAXSWUTF8L];
  const char * r;
  int lenr, lenp;
  int wl = strlen(word);
  if (wl < 2 || ! pAMgr) return ns;
  int numrep = pAMgr->get_numrep();
  struct replentry* reptable = pAMgr->get_reptable();
  if (reptable==NULL) return ns;
  for (int i=0; i < numrep; i++ ) {
      r = word;
      lenr = strlen(reptable[i].pattern2);
      lenp = strlen(reptable[i].pattern);
      // search every occurence of the pattern in the word
      while ((r=strstr(r, reptable[i].pattern)) != NULL && (!reptable[i].end || strlen(r) == strlen(reptable[i].pattern)) &&
        (!reptable[i].start || r == word)) {
          strcpy(candidate, word);
          if (r-word + lenr + strlen(r+lenp) >= MAXSWUTF8L) break;
          strcpy(candidate+(r-word),reptable[i].pattern2);
          strcpy(candidate+(r-word)+lenr, r+lenp);
          ns = testsug(wlst, candidate, wl-lenp+lenr, ns, cpdsuggest, NULL, NULL);
          if (ns == -1) return -1;
          // check REP suggestions with space
          char * sp = strchr(candidate, ' ');
          if (sp) {
            char * prev = candidate;
            while (sp) {
              *sp = '\0';
              if (checkword(prev, strlen(prev), 0, NULL, NULL)) {
                int oldns = ns;
                *sp = ' ';
                ns = testsug(wlst, sp + 1, strlen(sp + 1), ns, cpdsuggest, NULL, NULL);
                if (ns == -1) return -1;
                if (oldns < ns) {
                  free(wlst[ns - 1]);
                  wlst[ns - 1] = mystrdup(candidate);
                  if (!wlst[ns - 1]) return -1;
                }
              }
              *sp = ' ';
              prev = sp + 1;
              sp = strchr(prev, ' ');
            }
          }
          r++; // search for the next letter
      }
   }
   return ns;
}

// perhaps we doubled two characters (pattern aba -> ababa, for example vacation -> vacacation)
int SuggestMgr::doubletwochars(char** wlst, const char * word, int ns, int cpdsuggest)
{
  char candidate[MAXSWUTF8L];
  int state=0;
  int wl = strlen(word);
  if (wl < 5 || ! pAMgr) return ns;
  for (int i=2; i < wl; i++ ) {
      if (word[i]==word[i-2]) {
          state++;
          if (state==3) {
            strcpy(candidate,word);
            strcpy(candidate+i-1,word+i+1);
            ns = testsug(wlst, candidate, wl-2, ns, cpdsuggest, NULL, NULL);
            if (ns == -1) return -1;
            state=0;
          }
      } else {
            state=0;
      }
  }
  return ns;
}

// perhaps we doubled two characters (pattern aba -> ababa, for example vacation -> vacacation)
int SuggestMgr::doubletwochars_utf(char ** wlst, const w_char * word, int wl, int ns, int cpdsuggest)
{
  w_char        candidate_utf[MAXSWL];
  char          candidate[MAXSWUTF8L];
  int state=0;
  if (wl < 5 || ! pAMgr) return ns;
  for (int i=2; i < wl; i++) {
      if (w_char_eq(word[i], word[i-2]))  {
          state++;
          if (state==3) {
            memcpy(candidate_utf, word, (i - 1) * sizeof(w_char));
            memcpy(candidate_utf+i-1, word+i+1, (wl-i-1) * sizeof(w_char));
            u16_u8(candidate, MAXSWUTF8L, candidate_utf, wl-2);
            ns = testsug(wlst, candidate, strlen(candidate), ns, cpdsuggest, NULL, NULL);
            if (ns == -1) return -1;
            state=0;
          }
      } else {
            state=0;
      }
  }
  return ns;
}

// error is wrong char in place of correct one (case and keyboard related version)
int SuggestMgr::badcharkey(char ** wlst, const char * word, int ns, int cpdsuggest)
{
  char  tmpc;
  char  candidate[MAXSWUTF8L];
  int wl = strlen(word);
  strcpy(candidate, word);
  // swap out each char one by one and try uppercase and neighbor
  // keyboard chars in its place to see if that makes a good word

  for (int i=0; i < wl; i++) {
    tmpc = candidate[i];
    // check with uppercase letters
    candidate[i] = csconv[((unsigned char)tmpc)].cupper;
    if (tmpc != candidate[i]) {
       ns = testsug(wlst, candidate, wl, ns, cpdsuggest, NULL, NULL);
       if (ns == -1) return -1;
       candidate[i] = tmpc;
    }
    // check neighbor characters in keyboard string
    if (!ckey) continue;
    char * loc = strchr(ckey, tmpc);
    while (loc) {
       if ((loc > ckey) && (*(loc - 1) != '|')) {
          candidate[i] = *(loc - 1);
          ns = testsug(wlst, candidate, wl, ns, cpdsuggest, NULL, NULL);
          if (ns == -1) return -1;
       }
       if ((*(loc + 1) != '|') && (*(loc + 1) != '\0')) {
          candidate[i] = *(loc + 1);
          ns = testsug(wlst, candidate, wl, ns, cpdsuggest, NULL, NULL);
          if (ns == -1) return -1;
       }
       loc = strchr(loc + 1, tmpc);
    }
    candidate[i] = tmpc;
  }
  return ns;
}

// error is wrong char in place of correct one (case and keyboard related version)
int SuggestMgr::badcharkey_utf(char ** wlst, const w_char * word, int wl, int ns, int cpdsuggest)
{
  w_char        tmpc;
  w_char        candidate_utf[MAXSWL];
  char          candidate[MAXSWUTF8L];
  memcpy(candidate_utf, word, wl * sizeof(w_char));
  // swap out each char one by one and try all the tryme
  // chars in its place to see if that makes a good word
  for (int i=0; i < wl; i++) {
    tmpc = candidate_utf[i];
    // check with uppercase letters
    mkallcap_utf(candidate_utf + i, 1, langnum);
    if (!w_char_eq(tmpc, candidate_utf[i])) {
       u16_u8(candidate, MAXSWUTF8L, candidate_utf, wl);
       ns = testsug(wlst, candidate, strlen(candidate), ns, cpdsuggest, NULL, NULL);
       if (ns == -1) return -1;
       candidate_utf[i] = tmpc;
    }
    // check neighbor characters in keyboard string
    if (!ckey) continue;
    w_char * loc = ckey_utf;
    while ((loc < (ckey_utf + ckeyl)) && !w_char_eq(*loc, tmpc)) loc++;
    while (loc < (ckey_utf + ckeyl)) {
       if ((loc > ckey_utf) && !w_char_eq(*(loc - 1), W_VLINE)) {
          candidate_utf[i] = *(loc - 1);
          u16_u8(candidate, MAXSWUTF8L, candidate_utf, wl);
          ns = testsug(wlst, candidate, strlen(candidate), ns, cpdsuggest, NULL, NULL);
          if (ns == -1) return -1;
       }
       if (((loc + 1) < (ckey_utf + ckeyl)) && !w_char_eq(*(loc + 1), W_VLINE)) {
          candidate_utf[i] = *(loc + 1);
          u16_u8(candidate, MAXSWUTF8L, candidate_utf, wl);
          ns = testsug(wlst, candidate, strlen(candidate), ns, cpdsuggest, NULL, NULL);
          if (ns == -1) return -1;
       }
       do { loc++; } while ((loc < (ckey_utf + ckeyl)) && !w_char_eq(*loc, tmpc));
    }
    candidate_utf[i] = tmpc;
  }
  return ns;
}

// error is wrong char in place of correct one
int SuggestMgr::badchar(char ** wlst, const char * word, int ns, int cpdsuggest)
{
  char  tmpc;
  char  candidate[MAXSWUTF8L];
  clock_t timelimit = clock();
  int timer = MINTIMER;
  int wl = strlen(word);
  strcpy(candidate, word);
  // swap out each char one by one and try all the tryme
  // chars in its place to see if that makes a good word
  for (int j=0; j < ctryl; j++) {
    for (int i=wl-1; i >= 0; i--) {
       tmpc = candidate[i];
       if (ctry[j] == tmpc) continue;
       candidate[i] = ctry[j];
       ns = testsug(wlst, candidate, wl, ns, cpdsuggest, &timer, &timelimit);
       if (ns == -1) return -1;
       if (!timer) return ns;
       candidate[i] = tmpc;
    }
  }
  return ns;
}

// error is wrong char in place of correct one
int SuggestMgr::badchar_utf(char ** wlst, const w_char * word, int wl, int ns, int cpdsuggest)
{
  w_char        tmpc;
  w_char        candidate_utf[MAXSWL];
  char          candidate[MAXSWUTF8L];
  clock_t timelimit = clock();
  int timer = MINTIMER;  
  memcpy(candidate_utf, word, wl * sizeof(w_char));
  // swap out each char one by one and try all the tryme
  // chars in its place to see if that makes a good word
  for (int j=0; j < ctryl; j++) {
    for (int i=wl-1; i >= 0; i--) {
       tmpc = candidate_utf[i];
       if (w_char_eq(tmpc, ctry_utf[j])) continue;
       candidate_utf[i] = ctry_utf[j];
       u16_u8(candidate, MAXSWUTF8L, candidate_utf, wl);
       ns = testsug(wlst, candidate, strlen(candidate), ns, cpdsuggest, &timer, &timelimit);
       if (ns == -1) return -1;
       if (!timer) return ns;
       candidate_utf[i] = tmpc;
    }
  }
  return ns;
}

// error is word has an extra letter it does not need 
int SuggestMgr::extrachar_utf(char** wlst, const w_char * word, int wl, int ns, int cpdsuggest)
{
   char   candidate[MAXSWUTF8L];
   w_char candidate_utf[MAXSWL];
   w_char * p;
   w_char tmpc = W_VLINE; // not used value, only for VCC warning message
   if (wl < 2) return ns;
   // try omitting one char of word at a time
   memcpy(candidate_utf, word, wl * sizeof(w_char));
   for (p = candidate_utf + wl - 1;  p >= candidate_utf; p--) {
       w_char tmpc2 = *p;
       if (p < candidate_utf + wl - 1) *p = tmpc;
       u16_u8(candidate, MAXSWUTF8L, candidate_utf, wl - 1);
       ns = testsug(wlst, candidate, strlen(candidate), ns, cpdsuggest, NULL, NULL);
       if (ns == -1) return -1;
       tmpc = tmpc2;
   }
   return ns;
}

// error is word has an extra letter it does not need 
int SuggestMgr::extrachar(char** wlst, const char * word, int ns, int cpdsuggest)
{
   char    tmpc = '\0';
   char    candidate[MAXSWUTF8L];
   char *  p;
   int wl = strlen(word);
   if (wl < 2) return ns;
   // try omitting one char of word at a time
   strcpy (candidate, word);
   for (p = candidate + wl - 1; p >=candidate; p--) {
      char tmpc2 = *p;
      *p = tmpc;
      ns = testsug(wlst, candidate, wl-1, ns, cpdsuggest, NULL, NULL);
      if (ns == -1) return -1;
      tmpc = tmpc2;
   }
   return ns;
}

// error is missing a letter it needs
int SuggestMgr::forgotchar(char ** wlst, const char * word, int ns, int cpdsuggest)
{
   char candidate[MAXSWUTF8L];
   char * p;
   clock_t timelimit = clock();
   int timer = MINTIMER;
   int wl = strlen(word);
   // try inserting a tryme character before every letter (and the null terminator)
   for (int i = 0;  i < ctryl;  i++) {
      strcpy(candidate, word);
      for (p = candidate + wl;  p >= candidate; p--)  {
         *(p+1) = *p;
         *p = ctry[i];
         ns = testsug(wlst, candidate, wl+1, ns, cpdsuggest, &timer, &timelimit);
         if (ns == -1) return -1;
         if (!timer) return ns;
      }
   }
   return ns;
}

// error is missing a letter it needs
int SuggestMgr::forgotchar_utf(char ** wlst, const w_char * word, int wl, int ns, int cpdsuggest)
{
   w_char  candidate_utf[MAXSWL];
   char    candidate[MAXSWUTF8L];
   w_char * p;
   clock_t timelimit = clock();
   int timer = MINTIMER;
   // try inserting a tryme character at the end of the word and before every letter
   for (int i = 0;  i < ctryl;  i++) {
      memcpy (candidate_utf, word, wl * sizeof(w_char));
      for (p = candidate_utf + wl;  p >= candidate_utf; p--)  {
         *(p + 1) = *p;
         *p = ctry_utf[i];
         u16_u8(candidate, MAXSWUTF8L, candidate_utf, wl + 1);
         ns = testsug(wlst, candidate, strlen(candidate), ns, cpdsuggest, &timer, &timelimit);
         if (ns == -1) return -1;
         if (!timer) return ns;
      }
   }
   return ns;
}


/* error is should have been two words */
int SuggestMgr::twowords(char ** wlst, const char * word, int ns, int cpdsuggest)
{
    char candidate[MAXSWUTF8L];
    char * p;
    int c1, c2;
    int forbidden = 0;
    int cwrd;

    int wl=strlen(word);
    if (wl < 3) return ns;
    
    if (langnum == LANG_hu) forbidden = check_forbidden(word, wl);

    strcpy(candidate + 1, word);
    // split the string into two pieces after every char
    // if both pieces are good words make them a suggestion
    for (p = candidate + 1;  p[1] != '\0';  p++) {
       p[-1] = *p;
       // go to end of the UTF-8 character
       while (utf8 && ((p[1] & 0xc0) == 0x80)) {
         *p = p[1];
         p++;
       }
       if (utf8 && p[1] == '\0') break; // last UTF-8 character
       *p = '\0';
       c1 = checkword(candidate,strlen(candidate), cpdsuggest, NULL, NULL);
       if (c1) {
         c2 = checkword((p+1),strlen(p+1), cpdsuggest, NULL, NULL);
         if (c2) {
            *p = ' ';

            // spec. Hungarian code (need a better compound word support)
            if ((langnum == LANG_hu) && !forbidden &&
                // if 3 repeating letter, use - instead of space
                (((p[-1] == p[1]) && (((p>candidate+1) && (p[-1] == p[-2])) || (p[-1] == p[2]))) ||
                // or multiple compounding, with more, than 6 syllables
                ((c1 == 3) && (c2 >= 2)))) *p = '-';

            cwrd = 1;
            for (int k=0; k < ns; k++)
                if (strcmp(candidate,wlst[k]) == 0) cwrd = 0;
            if (ns < maxSug) {
                if (cwrd) {
                    wlst[ns] = mystrdup(candidate);
                    if (wlst[ns] == NULL) return -1;
                    ns++;
                }
            } else return ns;
            // add two word suggestion with dash, if TRY string contains
            // "a" or "-"
            // NOTE: cwrd doesn't modified for REP twoword sugg.
            if (ctry && (strchr(ctry, 'a') || strchr(ctry, '-')) &&
                mystrlen(p + 1) > 1 &&
                mystrlen(candidate) - mystrlen(p) > 1) {
                *p = '-'; 
                for (int k=0; k < ns; k++)
                    if (strcmp(candidate,wlst[k]) == 0) cwrd = 0;
                if (ns < maxSug) {
                    if (cwrd) {
                        wlst[ns] = mystrdup(candidate);
                        if (wlst[ns] == NULL) return -1;
                        ns++;
                    }
                } else return ns;
            }
         }
       }
    }
    return ns;
}


// error is adjacent letter were swapped
int SuggestMgr::swapchar(char ** wlst, const char * word, int ns, int cpdsuggest)
{
   char candidate[MAXSWUTF8L];
   char * p;
   char tmpc;
   int wl=strlen(word);
   // try swapping adjacent chars one by one
   strcpy(candidate, word);
   for (p = candidate;  p[1] != 0;  p++) {
      tmpc = *p;
      *p = p[1];
      p[1] = tmpc;
      ns = testsug(wlst, candidate, wl, ns, cpdsuggest, NULL, NULL);
      if (ns == -1) return -1;
      p[1] = *p;
      *p = tmpc;
   }
   // try double swaps for short words
   // ahev -> have, owudl -> would
   if (wl == 4 || wl == 5) {
     candidate[0] = word[1];
     candidate[1] = word[0];
     candidate[2] = word[2];
     candidate[wl - 2] = word[wl - 1];
     candidate[wl - 1] = word[wl - 2];
     ns = testsug(wlst, candidate, wl, ns, cpdsuggest, NULL, NULL);
     if (ns == -1) return -1;
     if (wl == 5) {
        candidate[0] = word[0];
        candidate[1] = word[2];
        candidate[2] = word[1];
        ns = testsug(wlst, candidate, wl, ns, cpdsuggest, NULL, NULL);
        if (ns == -1) return -1;
     }
   }
   return ns;
}

// error is adjacent letter were swapped
int SuggestMgr::swapchar_utf(char ** wlst, const w_char * word, int wl, int ns, int cpdsuggest)
{
   w_char candidate_utf[MAXSWL];
   char   candidate[MAXSWUTF8L];
   w_char * p;
   w_char tmpc;
   int len = 0;
   // try swapping adjacent chars one by one
   memcpy (candidate_utf, word, wl * sizeof(w_char));
   for (p = candidate_utf;  p < (candidate_utf + wl - 1);  p++) {
      tmpc = *p;
      *p = p[1];
      p[1] = tmpc;
      u16_u8(candidate, MAXSWUTF8L, candidate_utf, wl);
      if (len == 0) len = strlen(candidate);
      ns = testsug(wlst, candidate, len, ns, cpdsuggest, NULL, NULL);
      if (ns == -1) return -1;
      p[1] = *p;
      *p = tmpc;
   }
   // try double swaps for short words
   // ahev -> have, owudl -> would, suodn -> sound
   if (wl == 4 || wl == 5) {
     candidate_utf[0] = word[1];
     candidate_utf[1] = word[0];
     candidate_utf[2] = word[2];
     candidate_utf[wl - 2] = word[wl - 1];
     candidate_utf[wl - 1] = word[wl - 2];
     u16_u8(candidate, MAXSWUTF8L, candidate_utf, wl);
     ns = testsug(wlst, candidate, len, ns, cpdsuggest, NULL, NULL);
     if (ns == -1) return -1;
     if (wl == 5) {
        candidate_utf[0] = word[0];
        candidate_utf[1] = word[2];
        candidate_utf[2] = word[1];
        u16_u8(candidate, MAXSWUTF8L, candidate_utf, wl);
	ns = testsug(wlst, candidate, len, ns, cpdsuggest, NULL, NULL);
        if (ns == -1) return -1;
     }
   }
   return ns;
}

// error is not adjacent letter were swapped
int SuggestMgr::longswapchar(char ** wlst, const char * word, int ns, int cpdsuggest)
{
   char candidate[MAXSWUTF8L];
   char * p;
   char * q;
   char tmpc;
   int wl=strlen(word);
   // try swapping not adjacent chars one by one
   strcpy(candidate, word);
   for (p = candidate;  *p != 0;  p++) {
    for (q = candidate;  *q != 0;  q++) {
     if (abs((int)(p-q)) > 1) {
      tmpc = *p;
      *p = *q;
      *q = tmpc;
      ns = testsug(wlst, candidate, wl, ns, cpdsuggest, NULL, NULL);
      if (ns == -1) return -1;
      *q = *p;
      *p = tmpc;
     }
    }
   }
   return ns;
}


// error is adjacent letter were swapped
int SuggestMgr::longswapchar_utf(char ** wlst, const w_char * word, int wl, int ns, int cpdsuggest)
{
   w_char candidate_utf[MAXSWL];
   char   candidate[MAXSWUTF8L];
   w_char * p;
   w_char * q;
   w_char tmpc;
   // try swapping not adjacent chars
   memcpy (candidate_utf, word, wl * sizeof(w_char));
   for (p = candidate_utf;  p < (candidate_utf + wl);  p++) {
     for (q = candidate_utf;  q < (candidate_utf + wl);  q++) {
       if (abs((int)(p-q)) > 1) {
         tmpc = *p;
         *p = *q;
         *q = tmpc;
         u16_u8(candidate, MAXSWUTF8L, candidate_utf, wl);
         ns = testsug(wlst, candidate, strlen(candidate), ns, cpdsuggest, NULL, NULL);
         if (ns == -1) return -1;
         *q = *p;
         *p = tmpc;
       }
     }
   }
   return ns;
}

// error is a letter was moved
int SuggestMgr::movechar(char ** wlst, const char * word, int ns, int cpdsuggest)
{
   char candidate[MAXSWUTF8L];
   char * p;
   char * q;
   char tmpc;

   int wl=strlen(word);
   // try moving a char
   strcpy(candidate, word);
   for (p = candidate;  *p != 0;  p++) {
     for (q = p + 1;  (*q != 0) && ((q - p) < 10);  q++) {
      tmpc = *(q-1);
      *(q-1) = *q;
      *q = tmpc;
      if ((q-p) < 2) continue; // omit swap char
      ns = testsug(wlst, candidate, wl, ns, cpdsuggest, NULL, NULL);
      if (ns == -1) return -1;
    }
    strcpy(candidate, word);
   }
   for (p = candidate + wl - 1;  p > candidate;  p--) {
     for (q = p - 1;  (q >= candidate) && ((p - q) < 10);  q--) {
      tmpc = *(q+1);
      *(q+1) = *q;
      *q = tmpc;
      if ((p-q) < 2) continue; // omit swap char
      ns = testsug(wlst, candidate, wl, ns, cpdsuggest, NULL, NULL);
      if (ns == -1) return -1;
    }
    strcpy(candidate, word);
   }   
   return ns;
}

// error is a letter was moved
int SuggestMgr::movechar_utf(char ** wlst, const w_char * word, int wl, int ns, int cpdsuggest)
{
   w_char candidate_utf[MAXSWL];
   char   candidate[MAXSWUTF8L];
   w_char * p;
   w_char * q;
   w_char tmpc;
   // try moving a char
   memcpy (candidate_utf, word, wl * sizeof(w_char));
   for (p = candidate_utf;  p < (candidate_utf + wl);  p++) {
     for (q = p + 1;  (q < (candidate_utf + wl)) && ((q - p) < 10);  q++) {
         tmpc = *(q-1);
         *(q-1) = *q;
         *q = tmpc;
         if ((q-p) < 2) continue; // omit swap char
         u16_u8(candidate, MAXSWUTF8L, candidate_utf, wl);
         ns = testsug(wlst, candidate, strlen(candidate), ns, cpdsuggest, NULL, NULL);
         if (ns == -1) return -1;
     }
     memcpy (candidate_utf, word, wl * sizeof(w_char));
   }
   for (p = candidate_utf + wl - 1;  p > candidate_utf;  p--) {
     for (q = p - 1;  (q >= candidate_utf) && ((p - q) < 10);  q--) {
         tmpc = *(q+1);
         *(q+1) = *q;
         *q = tmpc;
         if ((p-q) < 2) continue; // omit swap char
         u16_u8(candidate, MAXSWUTF8L, candidate_utf, wl);
         ns = testsug(wlst, candidate, strlen(candidate), ns, cpdsuggest, NULL, NULL);
         if (ns == -1) return -1;
     }
     memcpy (candidate_utf, word, wl * sizeof(w_char));
   }
   return ns;   
}

// generate a set of suggestions for very poorly spelled words
int SuggestMgr::ngsuggest(char** wlst, char * w, int ns, HashMgr** pHMgr, int md)
{

  int i, j;
  int lval;
  int sc, scphon;
  int lp, lpphon;
  int nonbmp = 0;

  // exhaustively search through all root words
  // keeping track of the MAX_ROOTS most similar root words
  struct hentry * roots[MAX_ROOTS];
  char * rootsphon[MAX_ROOTS];
  int scores[MAX_ROOTS];
  int scoresphon[MAX_ROOTS];
  for (i = 0; i < MAX_ROOTS; i++) {
    roots[i] = NULL;
    scores[i] = -100 * i;
    rootsphon[i] = NULL;
    scoresphon[i] = -100 * i;
  }
  lp = MAX_ROOTS - 1;
  lpphon = MAX_ROOTS - 1;
  scphon = -20000;
  int low = NGRAM_LOWERING;
  
  char w2[MAXWORDUTF8LEN];
  char f[MAXSWUTF8L];
  char * word = w;

  // word reversing wrapper for complex prefixes
  if (complexprefixes) {
    strcpy(w2, w);
    if (utf8) reverseword_utf(w2); else reverseword(w2);
    word = w2;
  }

  char mw[MAXSWUTF8L];
  w_char u8[MAXSWL];
  int nc = strlen(word);
  int n = (utf8) ? u8_u16(u8, MAXSWL, word) : nc;
  
  // set character based ngram suggestion for words with non-BMP Unicode characters
  if (n == -1) {
    utf8 = 0; // XXX not state-free
    n = nc;
    nonbmp = 1;
    low = 0;
  }

  struct hentry* hp = NULL;
  int col = -1;
  phonetable * ph = (pAMgr) ? pAMgr->get_phonetable() : NULL;
  char target[MAXSWUTF8L];
  char candidate[MAXSWUTF8L];
  if (ph) {
    if (utf8) {
      w_char _w[MAXSWL];
      int _wl = u8_u16(_w, MAXSWL, word);
      mkallcap_utf(_w, _wl, langnum);
      u16_u8(candidate, MAXSWUTF8L, _w, _wl);
    } else {
      strcpy(candidate, word);
      if (!nonbmp) mkallcap(candidate, csconv);
    }
    phonet(candidate, target, nc, *ph); // XXX phonet() is 8-bit (nc, not n)
  }

  FLAG forbiddenword = pAMgr ? pAMgr->get_forbiddenword() : FLAG_NULL;
  FLAG nosuggest = pAMgr ? pAMgr->get_nosuggest() : FLAG_NULL;
  FLAG nongramsuggest = pAMgr ? pAMgr->get_nongramsuggest() : FLAG_NULL;
  FLAG onlyincompound = pAMgr ? pAMgr->get_onlyincompound() : FLAG_NULL;

  for (i = 0; i < md; i++) {  
  while (0 != (hp = (pHMgr[i])->walk_hashtable(col, hp))) {
    if ((hp->astr) && (pAMgr) && 
       (TESTAFF(hp->astr, forbiddenword, hp->alen) ||
          TESTAFF(hp->astr, ONLYUPCASEFLAG, hp->alen) ||
          TESTAFF(hp->astr, nosuggest, hp->alen) ||
          TESTAFF(hp->astr, nongramsuggest, hp->alen) ||
          TESTAFF(hp->astr, onlyincompound, hp->alen))) continue;

    sc = ngram(3, word, HENTRY_WORD(hp), NGRAM_LONGER_WORSE + low) +
	leftcommonsubstring(word, HENTRY_WORD(hp));

    // check special pronounciation
    if ((hp->var & H_OPT_PHON) && copy_field(f, HENTRY_DATA(hp), MORPH_PHON)) {
	int sc2 = ngram(3, word, f, NGRAM_LONGER_WORSE + low) +
		+ leftcommonsubstring(word, f);
	if (sc2 > sc) sc = sc2;
    }
    
    scphon = -20000;
    if (ph && (sc > 2) && (abs(n - (int) hp->clen) <= 3)) {
      char target2[MAXSWUTF8L];
      if (utf8) {
        w_char _w[MAXSWL];
        int _wl = u8_u16(_w, MAXSWL, HENTRY_WORD(hp));
        mkallcap_utf(_w, _wl, langnum);
        u16_u8(candidate, MAXSWUTF8L, _w, _wl);
      } else {
        strcpy(candidate, HENTRY_WORD(hp));
        mkallcap(candidate, csconv);
      }
      phonet(candidate, target2, -1, *ph);
      scphon = 2 * ngram(3, target, target2, NGRAM_LONGER_WORSE);
    }

    if (sc > scores[lp]) {
      scores[lp] = sc;  
      roots[lp] = hp;
      lval = sc;
      for (j=0; j < MAX_ROOTS; j++)
        if (scores[j] < lval) {
          lp = j;
          lval = scores[j];
        }
    }


    if (scphon > scoresphon[lpphon]) {
      scoresphon[lpphon] = scphon;
      rootsphon[lpphon] = HENTRY_WORD(hp);
      lval = scphon;
      for (j=0; j < MAX_ROOTS; j++)
        if (scoresphon[j] < lval) {
          lpphon = j;
          lval = scoresphon[j];
        }
    }
  }}

  // find minimum threshold for a passable suggestion
  // mangle original word three differnt ways
  // and score them to generate a minimum acceptable score
  int thresh = 0;
  for (int sp = 1; sp < 4; sp++) {
     if (utf8) {
       for (int k=sp; k < n; k+=4) *((unsigned short *) u8 + k) = '*';
       u16_u8(mw, MAXSWUTF8L, u8, n);
       thresh = thresh + ngram(n, word, mw, NGRAM_ANY_MISMATCH + low);
     } else {
       strcpy(mw, word);
       for (int k=sp; k < n; k+=4) *(mw + k) = '*';
       thresh = thresh + ngram(n, word, mw, NGRAM_ANY_MISMATCH + low);
     }
  }
  thresh = thresh / 3;
  thresh--;

 // now expand affixes on each of these root words and
  // and use length adjusted ngram scores to select
  // possible suggestions
  char * guess[MAX_GUESS];
  char * guessorig[MAX_GUESS];
  int gscore[MAX_GUESS];
  for(i=0;i<MAX_GUESS;i++) {
     guess[i] = NULL;
     guessorig[i] = NULL;
     gscore[i] = -100 * i;
  }

  lp = MAX_GUESS - 1;

  struct guessword * glst;
  glst = (struct guessword *) calloc(MAX_WORDS,sizeof(struct guessword));
  if (! glst) {
    if (nonbmp) utf8 = 1;
    return ns;
  }

  for (i = 0; i < MAX_ROOTS; i++) {
      if (roots[i]) {
        struct hentry * rp = roots[i];
        int nw = pAMgr->expand_rootword(glst, MAX_WORDS, HENTRY_WORD(rp), rp->blen,
            	    rp->astr, rp->alen, word, nc, 
                    ((rp->var & H_OPT_PHON) ? copy_field(f, HENTRY_DATA(rp), MORPH_PHON) : NULL));

        for (int k = 0; k < nw ; k++) {
           sc = ngram(n, word, glst[k].word, NGRAM_ANY_MISMATCH + low) +
               leftcommonsubstring(word, glst[k].word);

           if (sc > thresh) {
              if (sc > gscore[lp]) {
                 if (guess[lp]) {
                    free (guess[lp]);
                    if (guessorig[lp]) {
                	free(guessorig[lp]);
                	guessorig[lp] = NULL;
            	    }
                 }
                 gscore[lp] = sc;
                 guess[lp] = glst[k].word;
                 guessorig[lp] = glst[k].orig;
                 lval = sc;
                 for (j=0; j < MAX_GUESS; j++)
                    if (gscore[j] < lval) {
                       lp = j;
                       lval = gscore[j];
                    }
              } else { 
                free(glst[k].word);
                if (glst[k].orig) free(glst[k].orig);
              }
           } else {
                free(glst[k].word);
                if (glst[k].orig) free(glst[k].orig);
           }
        }
      }
  }
  free(glst);

  // now we are done generating guesses
  // sort in order of decreasing score
  
  
  bubblesort(&guess[0], &guessorig[0], &gscore[0], MAX_GUESS);
  if (ph) bubblesort(&rootsphon[0], NULL, &scoresphon[0], MAX_ROOTS);

  // weight suggestions with a similarity index, based on
  // the longest common subsequent algorithm and resort

  int is_swap = 0;
  int re = 0;
  double fact = 1.0;
  if (pAMgr) {
	int maxd = pAMgr->get_maxdiff();
	if (maxd >= 0) fact = (10.0 - maxd)/5.0;
  }

  for (i=0; i < MAX_GUESS; i++) {
      if (guess[i]) {
        // lowering guess[i]
        char gl[MAXSWUTF8L];
        int len;
        if (utf8) {
          w_char _w[MAXSWL];
          len = u8_u16(_w, MAXSWL, guess[i]);
          mkallsmall_utf(_w, len, langnum);
          u16_u8(gl, MAXSWUTF8L, _w, len);
        } else {
          strcpy(gl, guess[i]);
          if (!nonbmp) mkallsmall(gl, csconv);
          len = strlen(guess[i]);
        }

        int _lcs = lcslen(word, gl);

        // same characters with different casing
        if ((n == len) && (n == _lcs)) {
            gscore[i] += 2000;
            break;
        }
        // using 2-gram instead of 3, and other weightening

        re = ngram(2, word, gl, NGRAM_ANY_MISMATCH + low + NGRAM_WEIGHTED) +
             ngram(2, gl, word, NGRAM_ANY_MISMATCH + low + NGRAM_WEIGHTED);
 
        gscore[i] =
          // length of longest common subsequent minus length difference
          2 * _lcs - abs((int) (n - len)) +
          // weight length of the left common substring
          leftcommonsubstring(word, gl) +
          // weight equal character positions
          (!nonbmp && commoncharacterpositions(word, gl, &is_swap) ? 1: 0) +
          // swap character (not neighboring)
          ((is_swap) ? 10 : 0) +
          // ngram
          ngram(4, word, gl, NGRAM_ANY_MISMATCH + low) +
          // weighted ngrams
	  re +
         // different limit for dictionaries with PHONE rules
          (ph ? (re < len * fact ? -1000 : 0) : (re < (n + len)*fact? -1000 : 0));
      }
  }

  bubblesort(&guess[0], &guessorig[0], &gscore[0], MAX_GUESS);

// phonetic version
  if (ph) for (i=0; i < MAX_ROOTS; i++) {
      if (rootsphon[i]) {
        // lowering rootphon[i]
        char gl[MAXSWUTF8L];
        int len;
        if (utf8) {
          w_char _w[MAXSWL];
          len = u8_u16(_w, MAXSWL, rootsphon[i]);
          mkallsmall_utf(_w, len, langnum);
          u16_u8(gl, MAXSWUTF8L, _w, len);
        } else {
          strcpy(gl, rootsphon[i]);
          if (!nonbmp) mkallsmall(gl, csconv);
          len = strlen(rootsphon[i]);
        }

        // heuristic weigthing of ngram scores
        scoresphon[i] += 2 * lcslen(word, gl) - abs((int) (n - len)) +
          // weight length of the left common substring
          leftcommonsubstring(word, gl);
      }
  }

  if (ph) bubblesort(&rootsphon[0], NULL, &scoresphon[0], MAX_ROOTS);

  // copy over
  int oldns = ns;

  int same = 0;
  for (i=0; i < MAX_GUESS; i++) {
    if (guess[i]) {
      if ((ns < oldns + maxngramsugs) && (ns < maxSug) && (!same || (gscore[i] > 1000))) {
        int unique = 1;
        // leave only excellent suggestions, if exists
        if (gscore[i] > 1000) same = 1; else if (gscore[i] < -100) {
            same = 1;
	    // keep the best ngram suggestions, unless in ONLYMAXDIFF mode
            if (ns > oldns || (pAMgr && pAMgr->get_onlymaxdiff())) {
    	        free(guess[i]);
    	        if (guessorig[i]) free(guessorig[i]);
                continue;
            }
        }
        for (j = 0; j < ns; j++) {
          // don't suggest previous suggestions or a previous suggestion with prefixes or affixes
          if ((!guessorig[i] && strstr(guess[i], wlst[j])) ||
	     (guessorig[i] && strstr(guessorig[i], wlst[j])) ||
            // check forbidden words
            !checkword(guess[i], strlen(guess[i]), 0, NULL, NULL)) unique = 0;
        }
        if (unique) {
    	    wlst[ns++] = guess[i];
    	    if (guessorig[i]) {
    		free(guess[i]);
    		wlst[ns-1] = guessorig[i];
    	    }
    	} else {
    	    free(guess[i]);
    	    if (guessorig[i]) free(guessorig[i]);
    	}
      } else {
        free(guess[i]);
    	if (guessorig[i]) free(guessorig[i]);
      }
    }
  }

  oldns = ns;
  if (ph) for (i=0; i < MAX_ROOTS; i++) {
    if (rootsphon[i]) {
      if ((ns < oldns + MAXPHONSUGS) && (ns < maxSug)) {
	int unique = 1;
        for (j = 0; j < ns; j++) {
          // don't suggest previous suggestions or a previous suggestion with prefixes or affixes
          if (strstr(rootsphon[i], wlst[j]) || 
            // check forbidden words
            !checkword(rootsphon[i], strlen(rootsphon[i]), 0, NULL, NULL)) unique = 0;
        }
        if (unique) {
            wlst[ns++] = mystrdup(rootsphon[i]);
            if (!wlst[ns - 1]) return ns - 1;
        }
      }
    }
  }

  if (nonbmp) utf8 = 1;
  return ns;
}


// see if a candidate suggestion is spelled correctly
// needs to check both root words and words with affixes

// obsolote MySpell-HU modifications:
// return value 2 and 3 marks compounding with hyphen (-)
// `3' marks roots without suffix
int SuggestMgr::checkword(const char * word, int len, int cpdsuggest, int * timer, clock_t * timelimit)
{
  struct hentry * rv=NULL;
  struct hentry * rv2=NULL;
  int nosuffix = 0;

  // check time limit
  if (timer) {
    (*timer)--;
    if (!(*timer) && timelimit) {
      if ((clock() - *timelimit) > TIMELIMIT) return 0;
      *timer = MAXPLUSTIMER;
    }
  }
  
  if (pAMgr) { 
    if (cpdsuggest==1) {
      if (pAMgr->get_compound()) {
        rv = pAMgr->compound_check(word, len, 0, 0, 100, 0, NULL, 0, 1, 0); //EXT
        if (rv && (!(rv2 = pAMgr->lookup(word)) || !rv2->astr || 
            !(TESTAFF(rv2->astr,pAMgr->get_forbiddenword(),rv2->alen) ||
            TESTAFF(rv2->astr,pAMgr->get_nosuggest(),rv2->alen)))) return 3; // XXX obsolote categorisation + only ICONV needs affix flag check?
        }
        return 0;
    }

    rv = pAMgr->lookup(word);

    if (rv) {
        if ((rv->astr) && (TESTAFF(rv->astr,pAMgr->get_forbiddenword(),rv->alen)
               || TESTAFF(rv->astr,pAMgr->get_nosuggest(),rv->alen))) return 0;
        while (rv) {
            if (rv->astr && (TESTAFF(rv->astr,pAMgr->get_needaffix(),rv->alen) ||
                TESTAFF(rv->astr, ONLYUPCASEFLAG, rv->alen) ||
            TESTAFF(rv->astr,pAMgr->get_onlyincompound(),rv->alen))) {
                rv = rv->next_homonym;
            } else break;
        }
    } else rv = pAMgr->prefix_check(word, len, 0); // only prefix, and prefix + suffix XXX

    if (rv) {
        nosuffix=1;
    } else {
        rv = pAMgr->suffix_check(word, len, 0, NULL, NULL, 0, NULL); // only suffix
    }

    if (!rv && pAMgr->have_contclass()) {
        rv = pAMgr->suffix_check_twosfx(word, len, 0, NULL, FLAG_NULL);
        if (!rv) rv = pAMgr->prefix_check_twosfx(word, len, 1, FLAG_NULL);
    }

    // check forbidden words
    if ((rv) && (rv->astr) && (TESTAFF(rv->astr,pAMgr->get_forbiddenword(),rv->alen) ||
      TESTAFF(rv->astr, ONLYUPCASEFLAG, rv->alen) ||
      TESTAFF(rv->astr,pAMgr->get_nosuggest(),rv->alen) ||
      TESTAFF(rv->astr,pAMgr->get_onlyincompound(),rv->alen))) return 0;

    if (rv) { // XXX obsolote    
      if ((pAMgr->get_compoundflag()) && 
          TESTAFF(rv->astr, pAMgr->get_compoundflag(), rv->alen)) return 2 + nosuffix; 
      return 1;
    }
  }
  return 0;
}

int SuggestMgr::check_forbidden(const char * word, int len)
{
  struct hentry * rv = NULL;

  if (pAMgr) { 
    rv = pAMgr->lookup(word);
    if (rv && rv->astr && (TESTAFF(rv->astr,pAMgr->get_needaffix(),rv->alen) ||
        TESTAFF(rv->astr,pAMgr->get_onlyincompound(),rv->alen))) rv = NULL;
    if (!(pAMgr->prefix_check(word,len,1)))
        rv = pAMgr->suffix_check(word,len, 0, NULL, NULL, 0, NULL); // prefix+suffix, suffix
    // check forbidden words
    if ((rv) && (rv->astr) && TESTAFF(rv->astr,pAMgr->get_forbiddenword(),rv->alen)) return 1;
   }
    return 0;
}

#ifdef HUNSPELL_EXPERIMENTAL
// suggest possible stems
int SuggestMgr::suggest_pos_stems(char*** slst, const char * w, int nsug)
{
    char ** wlst;    

    struct hentry * rv = NULL;

  char w2[MAXSWUTF8L];
  const char * word = w;

  // word reversing wrapper for complex prefixes
  if (complexprefixes) {
    strcpy(w2, w);
    if (utf8) reverseword_utf(w2); else reverseword(w2);
    word = w2;
  }

    int wl = strlen(word);


    if (*slst) {
        wlst = *slst;
    } else {
        wlst = (char **) calloc(maxSug, sizeof(char *));
        if (wlst == NULL) return -1;
    }

    rv = pAMgr->suffix_check(word, wl, 0, NULL, wlst, maxSug, &nsug);

    // delete dash from end of word
    if (nsug > 0) {
        for (int j=0; j < nsug; j++) {
            if (wlst[j][strlen(wlst[j]) - 1] == '-') wlst[j][strlen(wlst[j]) - 1] = '\0';
        }
    }

    *slst = wlst;
    return nsug;
}
#endif // END OF HUNSPELL_EXPERIMENTAL CODE


char * SuggestMgr::suggest_morph(const char * w)
{
    char result[MAXLNLEN];
    char * r = (char *) result;
    char * st;

    struct hentry * rv = NULL;

    *result = '\0';

    if (! pAMgr) return NULL;

  char w2[MAXSWUTF8L];
  const char * word = w;

  // word reversing wrapper for complex prefixes
  if (complexprefixes) {
    strcpy(w2, w);
    if (utf8) reverseword_utf(w2); else reverseword(w2);
    word = w2;
  }

    rv = pAMgr->lookup(word);
    
    while (rv) {
        if ((!rv->astr) || !(TESTAFF(rv->astr, pAMgr->get_forbiddenword(), rv->alen) ||
            TESTAFF(rv->astr, pAMgr->get_needaffix(), rv->alen) ||
            TESTAFF(rv->astr,pAMgr->get_onlyincompound(),rv->alen))) {
                if (!HENTRY_FIND(rv, MORPH_STEM)) {
                    mystrcat(result, " ", MAXLNLEN);                                
                    mystrcat(result, MORPH_STEM, MAXLNLEN);
                    mystrcat(result, word, MAXLNLEN);
                }
                if (HENTRY_DATA(rv)) {
                    mystrcat(result, " ", MAXLNLEN);                                
                    mystrcat(result, HENTRY_DATA2(rv), MAXLNLEN);
                }
                mystrcat(result, "\n", MAXLNLEN);
        }
        rv = rv->next_homonym;
    }
    
    st = pAMgr->affix_check_morph(word,strlen(word));
    if (st) {
        mystrcat(result, st, MAXLNLEN);
        free(st);
    }

    if (pAMgr->get_compound() && (*result == '\0'))
        pAMgr->compound_check_morph(word, strlen(word),
                     0, 0, 100, 0,NULL, 0, &r, NULL);
    
    return (*result) ? mystrdup(line_uniq(result, MSEP_REC)) : NULL;
}

#ifdef HUNSPELL_EXPERIMENTAL
char * SuggestMgr::suggest_morph_for_spelling_error(const char * word)
{
    char * p = NULL;
    char ** wlst = (char **) calloc(maxSug, sizeof(char *));
    if (!**wlst) return NULL;
    // we will use only the first suggestion
    for (int i = 0; i < maxSug - 1; i++) wlst[i] = "";
    int ns = suggest(&wlst, word, maxSug - 1, NULL);
    if (ns == maxSug) {
        p = suggest_morph(wlst[maxSug - 1]);
        free(wlst[maxSug - 1]);
    }
    if (wlst) free(wlst);
    return p;
}
#endif // END OF HUNSPELL_EXPERIMENTAL CODE

/* affixation */
char * SuggestMgr::suggest_hentry_gen(hentry * rv, char * pattern)
{
    char result[MAXLNLEN];
    *result = '\0';
    int sfxcount = get_sfxcount(pattern);

    if (get_sfxcount(HENTRY_DATA(rv)) > sfxcount) return NULL;

    if (HENTRY_DATA(rv)) {
        char * aff = pAMgr->morphgen(HENTRY_WORD(rv), rv->blen, rv->astr, rv->alen,
            HENTRY_DATA(rv), pattern, 0);
        if (aff) {
            mystrcat(result, aff, MAXLNLEN);
            mystrcat(result, "\n", MAXLNLEN);
            free(aff);
        }
    }

    // check all allomorphs
    char allomorph[MAXLNLEN];
    char * p = NULL;
    if (HENTRY_DATA(rv)) p = (char *) strstr(HENTRY_DATA2(rv), MORPH_ALLOMORPH);
    while (p) {
        struct hentry * rv2 = NULL;
        p += MORPH_TAG_LEN;
        int plen = fieldlen(p);
        strncpy(allomorph, p, plen);
        allomorph[plen] = '\0';
        rv2 = pAMgr->lookup(allomorph);
        while (rv2) {
//            if (HENTRY_DATA(rv2) && get_sfxcount(HENTRY_DATA(rv2)) <= sfxcount) {
            if (HENTRY_DATA(rv2)) {
                char * st = (char *) strstr(HENTRY_DATA2(rv2), MORPH_STEM);
                if (st && (strncmp(st + MORPH_TAG_LEN, 
                   HENTRY_WORD(rv), fieldlen(st + MORPH_TAG_LEN)) == 0)) {
                    char * aff = pAMgr->morphgen(HENTRY_WORD(rv2), rv2->blen, rv2->astr, rv2->alen,
                        HENTRY_DATA(rv2), pattern, 0);
                    if (aff) {
                        mystrcat(result, aff, MAXLNLEN);
                        mystrcat(result, "\n", MAXLNLEN);
                        free(aff);
                    }    
                }
            }
            rv2 = rv2->next_homonym;
        }
        p = strstr(p + plen, MORPH_ALLOMORPH);
    }
        
    return (*result) ? mystrdup(result) : NULL;
}

char * SuggestMgr::suggest_gen(char ** desc, int n, char * pattern) {
  char result[MAXLNLEN];
  char result2[MAXLNLEN];
  char newpattern[MAXLNLEN];
  *newpattern = '\0';
  if (n == 0) return 0;
  *result2 = '\0';
  struct hentry * rv = NULL;
  if (!pAMgr) return NULL;

// search affixed forms with and without derivational suffixes
  while(1) {

  for (int k = 0; k < n; k++) {
    *result = '\0';
    // add compound word parts (except the last one)
    char * s = (char *) desc[k];
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
    for (int i = 0; i < pln; i++) {
            // remove inflectional and terminal suffixes
            char * is = strstr(pl[i], MORPH_INFL_SFX);
            if (is) *is = '\0';
            char * ts = strstr(pl[i], MORPH_TERM_SFX);
            while (ts) {
                *ts = '_';
                ts = strstr(pl[i], MORPH_TERM_SFX);
            }
            char * st = strstr(s, MORPH_STEM);
            if (st) {
                copy_field(tok, st, MORPH_STEM);
                rv = pAMgr->lookup(tok);
                while (rv) {
                    char newpat[MAXLNLEN];
                    strcpy(newpat, pl[i]);
                    strcat(newpat, pattern);
                    char * sg = suggest_hentry_gen(rv, newpat);
                    if (!sg) sg = suggest_hentry_gen(rv, pattern);
                    if (sg) {
                        char ** gen;
                        int genl = line_tok(sg, &gen, MSEP_REC);
                        free(sg);
                        sg = NULL;
                        for (int j = 0; j < genl; j++) {
                            if (strstr(pl[i], MORPH_SURF_PFX)) {
                                int r2l = strlen(result2);
                                result2[r2l] = MSEP_REC;
                                strcpy(result2 + r2l + 1, result);
                                copy_field(result2 + strlen(result2), pl[i], MORPH_SURF_PFX);
                                mystrcat(result2, gen[j], MAXLNLEN);
                            } else {
                                sprintf(result2 + strlen(result2), "%c%s%s",
                                    MSEP_REC, result, gen[j]);
                            }
                        }
                        freelist(&gen, genl);
                    }
                    rv = rv->next_homonym;
                }
            }
    }
    freelist(&pl, pln);
  }

  if (*result2 || !strstr(pattern, MORPH_DERI_SFX)) break;
  strcpy(newpattern, pattern);
  pattern = newpattern;
  char * ds = strstr(pattern, MORPH_DERI_SFX);
  while (ds) {
    strncpy(ds, MORPH_TERM_SFX, MORPH_TAG_LEN);
    ds = strstr(pattern, MORPH_DERI_SFX);
  }
 }
  return (*result2 ? mystrdup(result2) : NULL);
}


// generate an n-gram score comparing s1 and s2
int SuggestMgr::ngram(int n, char * s1, const char * s2, int opt)
{
  int nscore = 0;
  int ns;
  int l1;
  int l2;
  int test = 0;

  if (utf8) {
    w_char su1[MAXSWL];
    w_char su2[MAXSWL];
    l1 = u8_u16(su1, MAXSWL, s1);
    l2 = u8_u16(su2, MAXSWL, s2);
    if ((l2 <= 0) || (l1 == -1)) return 0;
    // lowering dictionary word
    if (opt & NGRAM_LOWERING) mkallsmall_utf(su2, l2, langnum);
    for (int j = 1; j <= n; j++) {
      ns = 0;
      for (int i = 0; i <= (l1-j); i++) {
	int k = 0;
        for (int l = 0; l <= (l2-j); l++) {
            for (k = 0; k < j; k++) {
              w_char * c1 = su1 + i + k;
              w_char * c2 = su2 + l + k;
              if ((c1->l != c2->l) || (c1->h != c2->h)) break;
            }
            if (k == j) {
		ns++;
                break;
            } 
	}
	if (k != j && opt & NGRAM_WEIGHTED) {
	  ns--;
	  test++;
	  if (i == 0 || i == l1-j) ns--; // side weight
	}
      }
      nscore = nscore + ns;
      if (ns < 2 && !(opt & NGRAM_WEIGHTED)) break;
    }
  } else {  
    l2 = strlen(s2);
    if (l2 == 0) return 0;
    l1 = strlen(s1);
    char *t = mystrdup(s2);
    if (opt & NGRAM_LOWERING) mkallsmall(t, csconv);
    for (int j = 1; j <= n; j++) {
      ns = 0;
      for (int i = 0; i <= (l1-j); i++) {
        char c = *(s1 + i + j);
        *(s1 + i + j) = '\0';
        if (strstr(t,(s1+i))) {
	  ns++;
	} else if (opt & NGRAM_WEIGHTED) {
	  ns--;
test++;
	  if (i == 0 || i == l1-j) ns--; // side weight
	}
        *(s1 + i + j ) = c;
      }
      nscore = nscore + ns;
      if (ns < 2 && !(opt & NGRAM_WEIGHTED)) break;
    }
    free(t);
  }
  
  ns = 0;
  if (opt & NGRAM_LONGER_WORSE) ns = (l2-l1)-2;
  if (opt & NGRAM_ANY_MISMATCH) ns = abs(l2-l1)-2;
  ns = (nscore - ((ns > 0) ? ns : 0));
  return ns;
}

// length of the left common substring of s1 and (decapitalised) s2
int SuggestMgr::leftcommonsubstring(char * s1, const char * s2) {
  if (utf8) {
    w_char su1[MAXSWL];
    w_char su2[MAXSWL];
    su1[0].l = su2[0].l = su1[0].h = su2[0].h = 0;
    // decapitalize dictionary word
    if (complexprefixes) {
      int l1 = u8_u16(su1, MAXSWL, s1);
      int l2 = u8_u16(su2, MAXSWL, s2);
      if (*((short *)su1+l1-1) == *((short *)su2+l2-1)) return 1;
    } else {
      int i;
      u8_u16(su1, 1, s1);
      u8_u16(su2, 1, s2);
      unsigned short idx = (su2->h << 8) + su2->l;
      unsigned short otheridx = (su1->h << 8) + su1->l;
      if (otheridx != idx &&
         (otheridx != unicodetolower(idx, langnum))) return 0;
      int l1 = u8_u16(su1, MAXSWL, s1);
      int l2 = u8_u16(su2, MAXSWL, s2);
      for(i = 1; (i < l1) && (i < l2) &&
         (su1[i].l == su2[i].l) && (su1[i].h == su2[i].h); i++);
      return i;
    }
  } else {
    if (complexprefixes) {
      int l1 = strlen(s1);
      int l2 = strlen(s2);
      if (*(s2+l1-1) == *(s2+l2-1)) return 1;
    } else {
      char * olds = s1;
      // decapitalise dictionary word
      if ((*s1 != *s2) && (*s1 != csconv[((unsigned char)*s2)].clower)) return 0;
      do {
        s1++; s2++;
      } while ((*s1 == *s2) && (*s1 != '\0'));
      return (int)(s1 - olds);
    }
  }
  return 0;
}

int SuggestMgr::commoncharacterpositions(char * s1, const char * s2, int * is_swap) {
  int num = 0;
  int diff = 0;
  int diffpos[2];
  *is_swap = 0;
  if (utf8) {
    w_char su1[MAXSWL];
    w_char su2[MAXSWL];
    int l1 = u8_u16(su1, MAXSWL, s1);
    int l2 = u8_u16(su2, MAXSWL, s2);
    // decapitalize dictionary word
    if (complexprefixes) {
      mkallsmall_utf(su2+l2-1, 1, langnum);
    } else {
      mkallsmall_utf(su2, 1, langnum);
    }
    for (int i = 0; (i < l1) && (i < l2); i++) {
      if (((short *) su1)[i] == ((short *) su2)[i]) {
        num++;
      } else {
        if (diff < 2) diffpos[diff] = i;
        diff++;
      }
    }
    if ((diff == 2) && (l1 == l2) &&
        (((short *) su1)[diffpos[0]] == ((short *) su2)[diffpos[1]]) &&
        (((short *) su1)[diffpos[1]] == ((short *) su2)[diffpos[0]])) *is_swap = 1;
  } else {
    int i;
    char t[MAXSWUTF8L];
    strcpy(t, s2);
    // decapitalize dictionary word
    if (complexprefixes) {
      int l2 = strlen(t);
      *(t+l2-1) = csconv[((unsigned char)*(t+l2-1))].clower;
    } else {
      mkallsmall(t, csconv);
    }
    for (i = 0; (*(s1+i) != 0) && (*(t+i) != 0); i++) {
      if (*(s1+i) == *(t+i)) {
        num++;
      } else {
        if (diff < 2) diffpos[diff] = i;
        diff++;
      }
    }
    if ((diff == 2) && (*(s1+i) == 0) && (*(t+i) == 0) &&
      (*(s1+diffpos[0]) == *(t+diffpos[1])) &&
      (*(s1+diffpos[1]) == *(t+diffpos[0]))) *is_swap = 1;
  }
  return num;
}

int SuggestMgr::mystrlen(const char * word) {
  if (utf8) {
    w_char w[MAXSWL];
    return u8_u16(w, MAXSWL, word);
  } else return strlen(word);
}

// sort in decreasing order of score
void SuggestMgr::bubblesort(char** rword, char** rword2, int* rsc, int n )
{
      int m = 1;
      while (m < n) {
          int j = m;
          while (j > 0) {
            if (rsc[j-1] < rsc[j]) {
                int sctmp = rsc[j-1];
                char * wdtmp = rword[j-1];
                rsc[j-1] = rsc[j];
                rword[j-1] = rword[j];
                rsc[j] = sctmp;
                rword[j] = wdtmp;
                if (rword2) {
            	    wdtmp = rword2[j-1];
            	    rword2[j-1] = rword2[j];
            	    rword2[j] = wdtmp;
                }
                j--;
            } else break;
          }
          m++;
      }
      return;
}

// longest common subsequence
void SuggestMgr::lcs(const char * s, const char * s2, int * l1, int * l2, char ** result) {
  int n, m;
  w_char su[MAXSWL];
  w_char su2[MAXSWL];
  char * b;
  char * c;
  int i;
  int j;
  if (utf8) {
    m = u8_u16(su, MAXSWL, s);
    n = u8_u16(su2, MAXSWL, s2);
  } else {
    m = strlen(s);
    n = strlen(s2);
  }
  c = (char *) malloc((m + 1) * (n + 1));
  b = (char *) malloc((m + 1) * (n + 1));
  if (!c || !b) {
    if (c) free(c);
    if (b) free(b);
    *result = NULL;
    return;
  }
  for (i = 1; i <= m; i++) c[i*(n+1)] = 0;
  for (j = 0; j <= n; j++) c[j] = 0;
  for (i = 1; i <= m; i++) {
    for (j = 1; j <= n; j++) {
      if ( ((utf8) && (*((short *) su+i-1) == *((short *)su2+j-1)))
          || ((!utf8) && ((*(s+i-1)) == (*(s2+j-1))))) {
        c[i*(n+1) + j] = c[(i-1)*(n+1) + j-1]+1;
        b[i*(n+1) + j] = LCS_UPLEFT;
      } else if (c[(i-1)*(n+1) + j] >= c[i*(n+1) + j-1]) {
        c[i*(n+1) + j] = c[(i-1)*(n+1) + j];
        b[i*(n+1) + j] = LCS_UP;
      } else {
        c[i*(n+1) + j] = c[i*(n+1) + j-1];
        b[i*(n+1) + j] = LCS_LEFT;
      }
    }
  }
  *result = b;
  free(c);
  *l1 = m;
  *l2 = n;
}

int SuggestMgr::lcslen(const char * s, const char* s2) {
  int m;
  int n;
  int i;
  int j;
  char * result;
  int len = 0;
  lcs(s, s2, &m, &n, &result);
  if (!result) return 0;
  i = m;
  j = n;
  while ((i != 0) && (j != 0)) {
    if (result[i*(n+1) + j] == LCS_UPLEFT) {
      len++;
      i--;
      j--;
    } else if (result[i*(n+1) + j] == LCS_UP) {
      i--;
    } else j--;
  }
  free(result);
  return len;
}
