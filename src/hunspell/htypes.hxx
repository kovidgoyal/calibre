#ifndef _HTYPES_HXX_
#define _HTYPES_HXX_

#define ROTATE_LEN   5

#define ROTATE(v,q) \
   (v) = ((v) << (q)) | (((v) >> (32 - q)) & ((1 << (q))-1));

// hentry options
#define H_OPT        (1 << 0)
#define H_OPT_ALIASM (1 << 1)
#define H_OPT_PHON   (1 << 2)

// see also csutil.hxx
#define HENTRY_WORD(h) &(h->word[0])

// approx. number  of user defined words
#define USERWORD 1000

struct hentry
{
  unsigned char blen; // word length in bytes
  unsigned char clen; // word length in characters (different for UTF-8 enc.)
  short    alen;      // length of affix flag vector
  unsigned short * astr;  // affix flag vector
  struct   hentry * next; // next word with same hash code
  struct   hentry * next_homonym; // next homonym word (with same hash code)
  char     var;       // variable fields (only for special pronounciation yet)
  char     word[1];   // variable-length word (8-bit or UTF-8 encoding)
};

#endif
