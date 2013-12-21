#ifndef _MYSPELLMGR_H_
#define _MYSPELLMGR_H_

#include "hunvisapi.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct Hunhandle Hunhandle;

LIBHUNSPELL_DLL_EXPORTED Hunhandle *Hunspell_create(const char * affpath, const char * dpath);

LIBHUNSPELL_DLL_EXPORTED Hunhandle *Hunspell_create_key(const char * affpath, const char * dpath,
    const char * key);

LIBHUNSPELL_DLL_EXPORTED void Hunspell_destroy(Hunhandle *pHunspell);

/* spell(word) - spellcheck word
 * output: 0 = bad word, not 0 = good word
 */
LIBHUNSPELL_DLL_EXPORTED int Hunspell_spell(Hunhandle *pHunspell, const char *);

LIBHUNSPELL_DLL_EXPORTED char *Hunspell_get_dic_encoding(Hunhandle *pHunspell);

/* suggest(suggestions, word) - search suggestions
 * input: pointer to an array of strings pointer and the (bad) word
 *   array of strings pointer (here *slst) may not be initialized
 * output: number of suggestions in string array, and suggestions in
 *   a newly allocated array of strings (*slts will be NULL when number
 *   of suggestion equals 0.)
 */
LIBHUNSPELL_DLL_EXPORTED int Hunspell_suggest(Hunhandle *pHunspell, char*** slst, const char * word);

 /* morphological functions */

 /* analyze(result, word) - morphological analysis of the word */

LIBHUNSPELL_DLL_EXPORTED int Hunspell_analyze(Hunhandle *pHunspell, char*** slst, const char * word);

 /* stem(result, word) - stemmer function */

LIBHUNSPELL_DLL_EXPORTED int Hunspell_stem(Hunhandle *pHunspell, char*** slst, const char * word);

 /* stem(result, analysis, n) - get stems from a morph. analysis
  * example:
  * char ** result, result2;
  * int n1 = Hunspell_analyze(result, "words");
  * int n2 = Hunspell_stem2(result2, result, n1);   
  */

LIBHUNSPELL_DLL_EXPORTED int Hunspell_stem2(Hunhandle *pHunspell, char*** slst, char** desc, int n);

 /* generate(result, word, word2) - morphological generation by example(s) */

LIBHUNSPELL_DLL_EXPORTED int Hunspell_generate(Hunhandle *pHunspell, char*** slst, const char * word,
    const char * word2);

 /* generate(result, word, desc, n) - generation by morph. description(s)
  * example:
  * char ** result;
  * char * affix = "is:plural"; // description depends from dictionaries, too
  * int n = Hunspell_generate2(result, "word", &affix, 1);
  * for (int i = 0; i < n; i++) printf("%s\n", result[i]);
  */

LIBHUNSPELL_DLL_EXPORTED int Hunspell_generate2(Hunhandle *pHunspell, char*** slst, const char * word,
    char** desc, int n);

  /* functions for run-time modification of the dictionary */

  /* add word to the run-time dictionary */
  
LIBHUNSPELL_DLL_EXPORTED int Hunspell_add(Hunhandle *pHunspell, const char * word);

  /* add word to the run-time dictionary with affix flags of
   * the example (a dictionary word): Hunspell will recognize
   * affixed forms of the new word, too.
   */
  
LIBHUNSPELL_DLL_EXPORTED int Hunspell_add_with_affix(Hunhandle *pHunspell, const char * word, const char * example);

  /* remove word from the run-time dictionary */

LIBHUNSPELL_DLL_EXPORTED int Hunspell_remove(Hunhandle *pHunspell, const char * word);

  /* free suggestion lists */

LIBHUNSPELL_DLL_EXPORTED void Hunspell_free_list(Hunhandle *pHunspell, char *** slst, int n);

#ifdef __cplusplus
}
#endif

#endif
