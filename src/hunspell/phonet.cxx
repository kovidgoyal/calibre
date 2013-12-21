/*  phonetic.c - generic replacement aglogithms for phonetic transformation
    Copyright (C) 2000 Bjoern Jacke

    This library is free software; you can redistribute it and/or
    modify it under the terms of the GNU Lesser General Public
    License version 2.1 as published by the Free Software Foundation;
 
    This library is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
    Lesser General Public License for more details.
 
    You should have received a copy of the GNU Lesser General Public
    License along with this library; If not, see
    <http://www.gnu.org/licenses/>.

    Changelog:

    2000-01-05  Bjoern Jacke <bjoern at j3e.de>
                Initial Release insprired by the article about phonetic
                transformations out of c't 25/1999

    2007-07-26  Bjoern Jacke <bjoern at j3e.de>
		Released under MPL/GPL/LGPL tri-license for Hunspell
		
    2007-08-23  Laszlo Nemeth <nemeth at OOo>
                Porting from Aspell to Hunspell using C-like structs
*/

#include <stdlib.h> 
#include <string.h>
#include <stdio.h> 
#include <ctype.h>

#include "csutil.hxx"
#include "phonet.hxx"

void init_phonet_hash(phonetable & parms) 
  {
    int i, k;

    for (i = 0; i < HASHSIZE; i++) {
      parms.hash[i] = -1;
    }

    for (i = 0; parms.rules[i][0] != '\0'; i += 2) {
      /**  set hash value  **/
      k = (unsigned char) parms.rules[i][0];

      if (parms.hash[k] < 0) {
	parms.hash[k] = i;
      }
    }
  }

// like strcpy but safe if the strings overlap
//   but only if dest < src
static inline void strmove(char * dest, char * src) {
  while (*src) 
    *dest++ = *src++;
  *dest = '\0';
}

static int myisalpha(char ch) {
  if ((unsigned char) ch < 128) return isalpha(ch);
  return 1;
}

/*  phonetic transcription algorithm                   */
/*  see: http://aspell.net/man-html/Phonetic-Code.html */
/*  convert string to uppercase before this call       */
int phonet (const char * inword, char * target,
              int len,
	      phonetable & parms)
  {
    /**       Do phonetic transformation.       **/
    /**  "len" = length of "inword" incl. '\0'. **/

    /**  result:  >= 0:  length of "target"    **/
    /**            otherwise:  error            **/

    int  i,j,k=0,n,p,z;
    int  k0,n0,p0=-333,z0;
    char c, c0;
    const char * s;
    typedef unsigned char uchar;    
    char word[MAXPHONETUTF8LEN + 1];
    if (len == -1) len = strlen(inword);
    if (len > MAXPHONETUTF8LEN) return 0;
    strcpy(word, inword);
  
    /**  check word  **/
    i = j = z = 0;
    while ((c = word[i]) != '\0') {
      n = parms.hash[(uchar) c];
      z0 = 0;

      if (n >= 0) {
        /**  check all rules for the same letter  **/
        while (parms.rules[n][0] == c) {

          /**  check whole string  **/
          k = 1;   /** number of found letters  **/
          p = 5;   /** default priority  **/
          s = parms.rules[n];
          s++;     /**  important for (see below)  "*(s-1)"  **/
          
          while (*s != '\0'  &&  word[i+k] == *s
                 &&  !isdigit ((unsigned char) *s)  &&  strchr ("(-<^$", *s) == NULL) {
            k++;
            s++;
          }
          if (*s == '(') {
            /**  check letters in "(..)"  **/
            if (myisalpha(word[i+k])  // ...could be implied?
                && strchr(s+1, word[i+k]) != NULL) {
              k++;
              while (*s != ')')
                s++;
              s++;
            }
          }
          p0 = (int) *s;
          k0 = k;
          while (*s == '-'  &&  k > 1) {
            k--;
            s++;
          }
          if (*s == '<')
            s++;
          if (isdigit ((unsigned char) *s)) {
            /**  determine priority  **/
            p = *s - '0';
            s++;
          }
          if (*s == '^'  &&  *(s+1) == '^')
            s++;

          if (*s == '\0'
              || (*s == '^'  
                  && (i == 0  ||  ! myisalpha(word[i-1]))
                  && (*(s+1) != '$'
                      || (! myisalpha(word[i+k0]) )))
              || (*s == '$'  &&  i > 0  
                  &&  myisalpha(word[i-1])
                  && (! myisalpha(word[i+k0]) ))) 
          {
            /**  search for followup rules, if:     **/
            /**  parms.followup and k > 1  and  NO '-' in searchstring **/
            c0 = word[i+k-1];
            n0 = parms.hash[(uchar) c0];

//            if (parms.followup  &&  k > 1  &&  n0 >= 0
            if (k > 1  &&  n0 >= 0
                &&  p0 != (int) '-'  &&  word[i+k] != '\0') {
              /**  test follow-up rule for "word[i+k]"  **/
              while (parms.rules[n0][0] == c0) {

                /**  check whole string  **/
                k0 = k;
                p0 = 5;
                s = parms.rules[n0];
                s++;
                while (*s != '\0'  &&  word[i+k0] == *s
                       && ! isdigit((unsigned char) *s)  &&  strchr("(-<^$",*s) == NULL) {
                  k0++;
                  s++;
                }
                if (*s == '(') {
                  /**  check letters  **/
                  if (myisalpha(word[i+k0])
                      &&  strchr (s+1, word[i+k0]) != NULL) {
                    k0++;
                    while (*s != ')'  &&  *s != '\0')
                      s++;
                    if (*s == ')')
                      s++;
                  }
                }
                while (*s == '-') {
                  /**  "k0" gets NOT reduced   **/
                  /**  because "if (k0 == k)"  **/
                  s++;
                }
                if (*s == '<')
                  s++;
                if (isdigit ((unsigned char) *s)) {
                  p0 = *s - '0';
                  s++;
                }

                if (*s == '\0'
                    /**  *s == '^' cuts  **/
                    || (*s == '$'  &&  ! myisalpha(word[i+k0]))) 
                {
                  if (k0 == k) {
                    /**  this is just a piece of the string  **/
                    n0 += 2;
                    continue;
                  }

                  if (p0 < p) {
                    /**  priority too low  **/
                    n0 += 2;
                    continue;
                  }
                  /**  rule fits; stop search  **/
                  break;
                }
                n0 += 2;
              } /**  End of "while (parms.rules[n0][0] == c0)"  **/

              if (p0 >= p  && parms.rules[n0][0] == c0) {
                n += 2;
                continue;
              }
            } /** end of follow-up stuff **/

            /**  replace string  **/
            s = parms.rules[n+1];
            p0 = (parms.rules[n][0] != '\0'
                 &&  strchr (parms.rules[n]+1,'<') != NULL) ? 1:0;
            if (p0 == 1 &&  z == 0) {
              /**  rule with '<' is used  **/
              if (j > 0  &&  *s != '\0'
                 && (target[j-1] == c  ||  target[j-1] == *s)) {
                j--;
              }
              z0 = 1;
              z = 1;
              k0 = 0;
              while (*s != '\0'  &&  word[i+k0] != '\0') {
                word[i+k0] = *s;
                k0++;
                s++;
              }
              if (k > k0)
                strmove (&word[0]+i+k0, &word[0]+i+k);

              /**  new "actual letter"  **/
              c = word[i];
            }
            else { /** no '<' rule used **/
              i += k - 1;
              z = 0;
              while (*s != '\0'
                     &&  *(s+1) != '\0'  &&  j < len) {
                if (j == 0  ||  target[j-1] != *s) {
                  target[j] = *s;
                  j++;
                }
                s++;
              }
              /**  new "actual letter"  **/
              c = *s;
              if (parms.rules[n][0] != '\0'
                 &&  strstr (parms.rules[n]+1, "^^") != NULL) {
                if (c != '\0') {
                  target[j] = c;
                  j++;
                }
                strmove (&word[0], &word[0]+i+1);
                i = 0;
                z0 = 1;
              }
            }
            break;
          }  /** end of follow-up stuff **/
          n += 2;
        } /**  end of while (parms.rules[n][0] == c)  **/
      } /**  end of if (n >= 0)  **/
      if (z0 == 0) {
//        if (k && (assert(p0!=-333),!p0) &&  j < len &&  c != '\0'
//           && (!parms.collapse_result  ||  j == 0  ||  target[j-1] != c)){
        if (k && !p0 && j < len &&  c != '\0'
           && (1 || j == 0  ||  target[j-1] != c)){
           /**  condense only double letters  **/
          target[j] = c;
	  ///printf("\n setting \n");
          j++;
        }

        i++;
        z = 0;
	k=0;
      }
    }  /**  end of   while ((c = word[i]) != '\0')  **/

    target[j] = '\0';
    return (j);

  }  /**  end of function "phonet"  **/
