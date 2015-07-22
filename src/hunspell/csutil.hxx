#ifndef __CSUTILHXX__
#define __CSUTILHXX__

#include "hunvisapi.h"

// First some base level utility routines

#include <string.h>
#include "w_char.hxx"
#include "htypes.hxx"

#ifdef MOZILLA_CLIENT
#include "nscore.h" // for mozalloc headers
#endif

// casing
#define NOCAP   0
#define INITCAP 1
#define ALLCAP  2
#define HUHCAP  3
#define HUHINITCAP  4

// default encoding and keystring
#define SPELL_ENCODING  "ISO8859-1"
#define SPELL_KEYSTRING "qwertyuiop|asdfghjkl|zxcvbnm" 

// default morphological fields
#define MORPH_STEM        "st:"
#define MORPH_ALLOMORPH   "al:"
#define MORPH_POS         "po:"
#define MORPH_DERI_PFX    "dp:"
#define MORPH_INFL_PFX    "ip:"
#define MORPH_TERM_PFX    "tp:"
#define MORPH_DERI_SFX    "ds:"
#define MORPH_INFL_SFX    "is:"
#define MORPH_TERM_SFX    "ts:"
#define MORPH_SURF_PFX    "sp:"
#define MORPH_FREQ        "fr:"
#define MORPH_PHON        "ph:"
#define MORPH_HYPH        "hy:"
#define MORPH_PART        "pa:"
#define MORPH_FLAG        "fl:"
#define MORPH_HENTRY      "_H:"
#define MORPH_TAG_LEN     strlen(MORPH_STEM)

#define MSEP_FLD ' '
#define MSEP_REC '\n'
#define MSEP_ALT '\v'

// default flags
#define DEFAULTFLAGS   65510
#define FORBIDDENWORD  65510
#define ONLYUPCASEFLAG 65511

// fopen or optional _wfopen to fix long pathname problem of WIN32
LIBHUNSPELL_DLL_EXPORTED FILE * myfopen(const char * path, const char * mode);

// convert UTF-16 characters to UTF-8
LIBHUNSPELL_DLL_EXPORTED char * u16_u8(char * dest, int size, const w_char * src, int srclen);

// convert UTF-8 characters to UTF-16
LIBHUNSPELL_DLL_EXPORTED int u8_u16(w_char * dest, int size, const char * src);

// sort 2-byte vector
LIBHUNSPELL_DLL_EXPORTED void flag_qsort(unsigned short flags[], int begin, int end);

// binary search in 2-byte vector
LIBHUNSPELL_DLL_EXPORTED int flag_bsearch(unsigned short flags[], unsigned short flag, int right);

// remove end of line char(s)
LIBHUNSPELL_DLL_EXPORTED void mychomp(char * s);

// duplicate string
LIBHUNSPELL_DLL_EXPORTED char * mystrdup(const char * s);

// strcat for limited length destination string
LIBHUNSPELL_DLL_EXPORTED char * mystrcat(char * dest, const char * st, int max);

// duplicate reverse of string
LIBHUNSPELL_DLL_EXPORTED char * myrevstrdup(const char * s);

// parse into tokens with char delimiter
LIBHUNSPELL_DLL_EXPORTED char * mystrsep(char ** sptr, const char delim);
// parse into tokens with char delimiter
LIBHUNSPELL_DLL_EXPORTED char * mystrsep2(char ** sptr, const char delim);

// parse into tokens with char delimiter
LIBHUNSPELL_DLL_EXPORTED char * mystrrep(char *, const char *, const char *);

// append s to ends of every lines in text
LIBHUNSPELL_DLL_EXPORTED void strlinecat(char * lines, const char * s);

// tokenize into lines with new line
LIBHUNSPELL_DLL_EXPORTED int line_tok(const char * text, char *** lines, char breakchar);

// tokenize into lines with new line and uniq in place
LIBHUNSPELL_DLL_EXPORTED char * line_uniq(char * text, char breakchar);
LIBHUNSPELL_DLL_EXPORTED char * line_uniq_app(char ** text, char breakchar);

// change oldchar to newchar in place
LIBHUNSPELL_DLL_EXPORTED char * tr(char * text, char oldc, char newc);

// reverse word
LIBHUNSPELL_DLL_EXPORTED int reverseword(char *);

// reverse word
LIBHUNSPELL_DLL_EXPORTED int reverseword_utf(char *);

// remove duplicates
LIBHUNSPELL_DLL_EXPORTED int uniqlist(char ** list, int n);

// free character array list
LIBHUNSPELL_DLL_EXPORTED void freelist(char *** list, int n);

// character encoding information
struct cs_info {
  unsigned char ccase;
  unsigned char clower;
  unsigned char cupper;
};

LIBHUNSPELL_DLL_EXPORTED int initialize_utf_tbl();
LIBHUNSPELL_DLL_EXPORTED void free_utf_tbl();
LIBHUNSPELL_DLL_EXPORTED unsigned short unicodetoupper(unsigned short c, int langnum);
LIBHUNSPELL_DLL_EXPORTED unsigned short unicodetolower(unsigned short c, int langnum);
LIBHUNSPELL_DLL_EXPORTED int unicodeisalpha(unsigned short c);

LIBHUNSPELL_DLL_EXPORTED struct cs_info * get_current_cs(const char * es);

// get language identifiers of language codes
LIBHUNSPELL_DLL_EXPORTED int get_lang_num(const char * lang);

// get characters of the given 8bit encoding with lower- and uppercase forms
LIBHUNSPELL_DLL_EXPORTED char * get_casechars(const char * enc);

// convert null terminated string to all caps using encoding
LIBHUNSPELL_DLL_EXPORTED void enmkallcap(char * d, const char * p, const char * encoding);

// convert null terminated string to all little using encoding
LIBHUNSPELL_DLL_EXPORTED void enmkallsmall(char * d, const char * p, const char * encoding);

// convert null terminated string to have initial capital using encoding
LIBHUNSPELL_DLL_EXPORTED void enmkinitcap(char * d, const char * p, const char * encoding);

// convert null terminated string to all caps
LIBHUNSPELL_DLL_EXPORTED void mkallcap(char * p, const struct cs_info * csconv);

// convert null terminated string to all little
LIBHUNSPELL_DLL_EXPORTED void mkallsmall(char * p, const struct cs_info * csconv);

// convert null terminated string to have initial capital
LIBHUNSPELL_DLL_EXPORTED void mkinitcap(char * p, const struct cs_info * csconv);

// convert first nc characters of UTF-8 string to little
LIBHUNSPELL_DLL_EXPORTED void mkallsmall_utf(w_char * u, int nc, int langnum);

// convert first nc characters of UTF-8 string to capital
LIBHUNSPELL_DLL_EXPORTED void mkallcap_utf(w_char * u, int nc, int langnum);

// get type of capitalization
LIBHUNSPELL_DLL_EXPORTED int get_captype(char * q, int nl, cs_info *);

// get type of capitalization (UTF-8)
LIBHUNSPELL_DLL_EXPORTED int get_captype_utf8(w_char * q, int nl, int langnum);

// strip all ignored characters in the string
LIBHUNSPELL_DLL_EXPORTED void remove_ignored_chars_utf(char * word, unsigned short ignored_chars[], int ignored_len);

// strip all ignored characters in the string
LIBHUNSPELL_DLL_EXPORTED void remove_ignored_chars(char * word, char * ignored_chars);

LIBHUNSPELL_DLL_EXPORTED int parse_string(char * line, char ** out, int ln);

LIBHUNSPELL_DLL_EXPORTED int parse_array(char * line, char ** out, unsigned short ** out_utf16,
    int * out_utf16_len, int utf8, int ln);

LIBHUNSPELL_DLL_EXPORTED int fieldlen(const char * r);
LIBHUNSPELL_DLL_EXPORTED char * copy_field(char * dest, const char * morph, const char * var);

LIBHUNSPELL_DLL_EXPORTED int morphcmp(const char * s, const char * t);

LIBHUNSPELL_DLL_EXPORTED int get_sfxcount(const char * morph);

// conversion function for protected memory
LIBHUNSPELL_DLL_EXPORTED void store_pointer(char * dest, char * source);

// conversion function for protected memory
LIBHUNSPELL_DLL_EXPORTED char * get_stored_pointer(const char * s);

// hash entry macros
LIBHUNSPELL_DLL_EXPORTED inline char* HENTRY_DATA(struct hentry *h)
{
    char *ret;
    if (!h->var)
        ret = NULL;
    else if (h->var & H_OPT_ALIASM)
        ret = get_stored_pointer(HENTRY_WORD(h) + h->blen + 1);
    else 
        ret = HENTRY_WORD(h) + h->blen + 1;
    return ret;
}

// NULL-free version for warning-free OOo build
LIBHUNSPELL_DLL_EXPORTED inline const char* HENTRY_DATA2(const struct hentry *h)
{
    const char *ret;
    if (!h->var)
        ret = "";
    else if (h->var & H_OPT_ALIASM)
        ret = get_stored_pointer(HENTRY_WORD(h) + h->blen + 1);
    else
        ret = HENTRY_WORD(h) + h->blen + 1;
    return ret;
}

LIBHUNSPELL_DLL_EXPORTED inline char* HENTRY_FIND(struct hentry *h, const char *p)
{
    return (HENTRY_DATA(h) ? strstr(HENTRY_DATA(h), p) : NULL);
}

#define w_char_eq(a,b) (((a).l == (b).l) && ((a).h == (b).h))

#endif
