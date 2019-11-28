/*
    File lzx_layer.c, part of lzxcomp library
    Copyright (C) 2002 Matthew T. Russotto

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation; version 2.1 only

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

*/

/* Force using (actually working) non-sliding version. */
#define NONSLIDE 1
#define LZ_ONEBUFFER 1
#define LAZY 1

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h> /* for memset on Linux */
#include <assert.h>
#include <math.h>

#ifdef BYTE_ORDER
# if BYTE_ORDER == BIG_ENDIAN
#  define LZX_BIG_ENDIAN
# endif /* BYTE_ORDER == BIG_ENDIAN */
#endif /* BYTE_ORDER */

#ifdef NONSLIDE
#include "lzc.h"
#else
#include "hash_slide.h"
#include "lz_slide.h"
#endif
#include "lzxc.h"

/* these named constants are from the Microsoft LZX documentation */
#define MIN_MATCH                            2
#define MAX_MATCH                          257
#define NUM_CHARS                          256
#define NUM_PRIMARY_LENGTHS                  7
#define NUM_SECONDARY_LENGTHS              249

/* the names of these constants are specific to this library */
#define LZX_MAX_CODE_LENGTH                 16
#define LZX_FRAME_SIZE                   32768
#define LZX_PRETREE_SIZE                    20
#define LZX_ALIGNED_BITS                     3
#define LZX_ALIGNED_SIZE                     8

#define LZX_VERBATIM_BLOCK                   1
#define LZX_ALIGNED_OFFSET_BLOCK             2

/* Debugging defines useful during development.  All add diagnostic output
   at various points in the system */

/*#define DEBUG_MATCHES       *//* When matches come in from the LZ engine */
/*#define DEBUG_MATCHES_2     *//* When matches are being output           */
/*#define DEBUG_HUFFMAN       *//* When huffman trees are built            */
/*#define DEBUG_ENTROPY       *//* In entropy calculation                  */
/*#define DEBUG_LZ            *//* Uncompressed input reconstructed from
                                 LZ engine                               */
/*#define DEBUG_BITBUF        *//* Raw output to upper layer               */
/*#define DEBUG_EXTRA_BITS    *//* Savings due to extra bits huffman tree  */
/*#define DEBUG_POSITION_SLOT_LOOKUP */
/*#define DEBUG_TREE_COMPRESSION   *//* During RLE compression of trees    */

/* number of position slots given window_size-5 */
/* as corrected by Caie */
short num_position_slots[] = {30, 32, 34, 36, 38, 42, 50};
unsigned long position_base[51];
unsigned char extra_bits[52];
double rloge2;

typedef struct ih_elem {
  int freq;
  short sym;
  short pathlength;
  struct ih_elem *parent;
  struct ih_elem *left;
  struct ih_elem *right;
} ih_elem;

typedef struct h_elem {
  int freq;
  short sym;
  short pathlength;
  struct ih_elem *parent;
  unsigned short code;
} h_elem;

typedef struct huff_entry {
  short codelength;
  unsigned short code;
} huff_entry;

static int cmp_leaves(const void *in_a, const void *in_b)
{
  const struct h_elem *a = in_a;
  const struct h_elem *b = in_b;

  if (!a->freq && b->freq)
    return 1;
  if (a->freq && !b->freq)
    return -1;

  if (a->freq == b->freq)
    return a->sym - b->sym;

  return a->freq - b->freq;
}

static int
cmp_pathlengths(const void *in_a, const void *in_b)
{
  const struct h_elem *a = in_a;
  const struct h_elem *b = in_b;

  if (a->pathlength == b->pathlength)
#if 0
    return a->sym - b->sym;
#else
  /* see note on canonical pathlengths */
    return b->sym - a->sym;
#endif
  return b->pathlength - a->pathlength;
}

/* standard huffman building algorithm */
static void
build_huffman_tree(int nelem, int max_code_length, int *freq, huff_entry *tree)
{
  h_elem *leaves = malloc(nelem * sizeof(h_elem));
  ih_elem *inodes;
  ih_elem *next_inode;
  ih_elem *cur_inode;
  h_elem *cur_leaf;
  int leaves_left;
  int nleaves;
  int pathlength;
  unsigned short cur_code;
  short codes_too_long = 0;
  ih_elem *f1, *f2;
  int i;

  for (i = 0; i < nelem; i++) {
    leaves[i].freq = freq[i];
    leaves[i].sym = i;
    leaves[i].pathlength = 0;
  }
  qsort(leaves, nelem, sizeof(h_elem), cmp_leaves);
  for (leaves_left = 0; leaves_left < nelem; leaves_left++) {
#ifdef DEBUG_HUFFMAN
    fprintf(stderr, "%3d: %3d '%c'\n", leaves_left, leaves[leaves_left].freq,
	    leaves[leaves_left].sym);
#endif
    if (!leaves[leaves_left].freq) break;
  }
  nleaves = leaves_left;

  if (nleaves >= 2) {
    inodes = malloc((nelem-1) * sizeof(ih_elem));
    do {
      if (codes_too_long) {
	for (leaves_left = 0; leaves_left < nelem; leaves_left++) {
	  if (!leaves[leaves_left].freq) break;
	  if (leaves[leaves_left].freq != 1) {
	    leaves[leaves_left].freq >>= 1;
	    codes_too_long = 0;
	  }
	}
	assert (!codes_too_long);
      }

      cur_leaf = leaves;
      next_inode = cur_inode = inodes;

      do {
	f1 = f2 = NULL;
	if (leaves_left &&
	    ((cur_inode == next_inode) ||
	     (cur_leaf->freq <= cur_inode->freq))) {
	  f1 = (ih_elem *)cur_leaf++;
	  leaves_left--;
	}
	else if (cur_inode != next_inode) {
	  f1 = cur_inode++;
	}

	if (leaves_left &&
	    ((cur_inode == next_inode) ||
	     (cur_leaf->freq <= cur_inode->freq))) {
	  f2 = (ih_elem *)cur_leaf++;
	  leaves_left--;
	}
	else if (cur_inode != next_inode) {
	  f2 = cur_inode++;
	}

#ifdef DEBUG_HUFFMAN
	fprintf(stderr, "%d %d\n", f1, f2);
#endif
	if (f1 && f2) {
	  next_inode->freq = f1->freq + f2->freq;
	  next_inode->sym = -1;
	  next_inode->left = f1;
	  next_inode->right = f2;
	  next_inode->parent = NULL;
	  f1->parent = next_inode;
	  f2->parent = next_inode;
	  if (f1->pathlength > f2->pathlength)
	    next_inode->pathlength = f1->pathlength + 1;
	  else
	    next_inode->pathlength = f2->pathlength + 1;
	  if (next_inode->pathlength > max_code_length) {
	    codes_too_long = 1;
	    break;
	  }
	  next_inode++;
	}
      }
      while (f1 && f2);
    }
    while (codes_too_long);

#ifdef DEBUG_HUFFMAN
    cur_inode = inodes;
    while (cur_inode < next_inode) {
      fprintf(stderr, "%d l: %3d%c  r: %3d%c  freq: %8d\n",
	      cur_inode - inodes,
	      (cur_inode->left->sym!=-1)?(((struct h_elem *)cur_inode->left)-leaves):(cur_inode->left-inodes),
	      (cur_inode->left->sym!=-1)?'l':'i',
	      (cur_inode->right->sym!=-1)?(((struct h_elem *)cur_inode->right)-leaves):(cur_inode->right-inodes),
	      (cur_inode->right->sym!=-1)?'l':'i',
	      (cur_inode->freq)
	      );
      cur_inode++;
    }
#endif

    /* now traverse tree depth-first */
    cur_inode = next_inode - 1;
    pathlength = 0;
    cur_inode->pathlength = -1;
    do {
      /* precondition: at unmarked node*/
      if (cur_inode->sym == -1) /*&& (cur_inode->left)*/ {
	/* left node of unmarked node is unmarked */
	cur_inode = cur_inode->left;
	cur_inode->pathlength = -1;
	pathlength++;
      }
      else {
	/* mark node */
	cur_inode->pathlength = pathlength;
#if 0
	if (cur_inode->right) {
	  /* right node of previously unmarked node is unmarked */
	  cur_inode = cur_inode->right;
	  cur_inode->pathlength = -1;
	  pathlength++;
	}
	else
#endif
	  {

	    /* time to come up.  Keep coming up until an unmarked node is reached */
	    /* or the tree is exhausted */
	    do {
	      cur_inode = cur_inode->parent;
	      pathlength--;
	    }
	    while (cur_inode && (cur_inode->pathlength != -1));
	    if (cur_inode) {
	      /* found unmarked node; mark it and go right */
	      cur_inode->pathlength = pathlength;
	      cur_inode = cur_inode->right;
	      cur_inode->pathlength = -1;
	      pathlength++;
	      /* would be complex if cur_inode could be null here.  It can't */
	    }
	  }
      }
    }
    while (cur_inode);

#ifdef DEBUG_HUFFMAN
    cur_inode = inodes;
    while (cur_inode < next_inode) {
      fprintf(stderr, "%d l: %3d%c  r: %3d%c  freq: %8d  pathlength %4d\n",
	      cur_inode - inodes,
	      (cur_inode->left->sym!=-1)?(((struct h_elem *)cur_inode->left)-leaves):(cur_inode->left-inodes),
	      (cur_inode->left->sym!=-1)?'l':'i',
	      (cur_inode->right->sym!=-1)?(((struct h_elem *)cur_inode->right)-leaves):(cur_inode->right-inodes),
	      (cur_inode->right->sym!=-1)?'l':'i',
	      (cur_inode->freq),
	      (cur_inode->pathlength)
	      );
      cur_inode++;
    }
#endif
    free(inodes);

    /* the pathlengths are already in order, so this sorts by symbol */
    qsort(leaves, nelem, sizeof(h_elem), cmp_pathlengths);

    /**
	Microsoft's second condition on its canonical huffman codes is:

	For each level, starting at the deepest level of the tree and then
	moving upwards, leaf nodes must start as far left as possible. An
	alternative way of stating this constraint is that if any tree node
	has children then all tree nodes to the left of it with the same path
	length must also have children.

	These 'alternatives' are not equivalent.  The latter alternative gives
	the common canonical code where the longest code is all zeros.  The former
	gives an opposite code where the longest code is all ones.  Microsoft uses the
	former alternative.
    **/

#if 0
    pathlength = leaves[0].pathlength;
    cur_code = 0;
    for (i = 0; i < nleaves; i++) {
      while (leaves[i].pathlength < pathlength) {
	assert(!(cur_code & 1));
	cur_code >>= 1;
	pathlength--;
      }
      leaves[i].code = cur_code;
      cur_code++;
    }
#else
    pathlength = leaves[nleaves-1].pathlength;
    assert(leaves[0].pathlength <= 16); /* this method cannot deal with bigger codes, though
					   the other canonical method can in some cases
					   (because it starts with zeros ) */
    cur_code = 0;
    for (i = nleaves - 1; i >= 0; i--) {
      while (leaves[i].pathlength > pathlength) {
	cur_code <<= 1;
	pathlength++;
      }
      leaves[i].code = cur_code;
      cur_code++;
    }
#endif

#ifdef DEBUG_HUFFMAN
    for (i = 0; i < nleaves; i++) {
      char code[18];
      int j;

      cur_code = leaves[i].code;
      code[leaves[i].pathlength] = 0;
      for (j = leaves[i].pathlength-1; j >= 0; j--) {
	if (cur_code & 1) code[j] = '1';
	else code[j] = '0';
	cur_code >>= 1;
      }
      fprintf(stderr, "%3d: %3d %3d %-16.16s '%c'\n", i, leaves[i].freq, leaves[i].pathlength, code,
	      leaves[i].sym);
    }
#endif
  }
  else if (nleaves == 1) {
    /* 0 symbols is OK (not according to doc, but according to Caie) */
    /* but if only one symbol is present, two symbols are required */
    nleaves = 2;
    leaves[0].pathlength = leaves[1].pathlength = 1;
    if (leaves[1].sym > leaves[0].sym) {
      leaves[1].code = 1;
      leaves[0].code = 0;
    }
    else {
      leaves[0].code = 1;
      leaves[1].code = 0;
    }
  }

  memset(tree, 0, nelem * sizeof(huff_entry));
  for (i = 0; i < nleaves; i++) {
    tree[leaves[i].sym].codelength = leaves[i].pathlength;
    tree[leaves[i].sym].code = leaves[i].code;
  }

  free(leaves);
}

/* from Stuart Caie's code -- I'm hoping this code is too small to encumber
   this file.  If not, you could rip it out and hard-code the tables */

static void lzx_init_static(void)
{
  int i, j;

  if (extra_bits[49]) return;

  rloge2 = 1.0/log(2);
  for (i=0, j=0; i <= 50; i += 2) {
    extra_bits[i] = extra_bits[i+1] = j; /* 0,0,0,0,1,1,2,2,3,3... */
    if ((i != 0) && (j < 17)) j++; /* 0,0,1,2,3,4...15,16,17,17,17,17... */
  }

  for (i=0, j=0; i <= 50; i++) {
    position_base[i] = j; /* 0,1,2,3,4,6,8,12,16,24,32,... */
    j += 1 << extra_bits[i]; /* 1,1,1,1,2,2,4,4,8,8,16,16,32,32,... */
  }
}

struct lzxc_data
{
  void *in_arg;
  void *out_arg;
  void *mark_frame_arg;
  lzxc_get_bytes_t get_bytes;
  lzxc_at_eof_t at_eof;
  lzxc_put_bytes_t put_bytes;
  lzxc_mark_frame_t mark_frame;
  struct lz_info *lzi;
  /* a 'frame' is an 0x8000 byte thing.  Called that because otherwise
     I'd confuse myself overloading 'block' */
  int left_in_frame;
  int left_in_block;
  int R0, R1, R2;
  int num_position_slots;
  /* this is the LZX block size */
  int block_size;
  int *main_freq_table;
  int length_freq_table[NUM_SECONDARY_LENGTHS];
  int aligned_freq_table[LZX_ALIGNED_SIZE];
  uint32_t *block_codes;
  uint32_t *block_codesp;
  huff_entry *main_tree;
  huff_entry length_tree[NUM_SECONDARY_LENGTHS];
  huff_entry aligned_tree[LZX_ALIGNED_SIZE];
  int main_tree_size;
  uint16_t bit_buf;
  int bits_in_buf;
  double main_entropy;
  double last_ratio;
  uint8_t *prev_main_treelengths;
  uint8_t prev_length_treelengths[NUM_SECONDARY_LENGTHS];
  uint32_t len_uncompressed_input;
  uint32_t len_compressed_output;
  short need_1bit_header;
  short subdivide; /* 0 = don't subdivide, 1 = allowed, -1 = requested */
};

static int
lzx_get_chars(lz_info *lzi, int n, unsigned char *buf)
{
  /* force lz compression to stop after every block */
  int chars_read;
  int chars_pad;

  lzxc_data *lzud = (lzxc_data *)lzi->user_data;
#ifdef OLDFRAMING
  if (lzud->subdivide < 0) return 0;
  if (n > lzud->left_in_frame)
    n = lzud->left_in_frame;
  if (n > lzud->left_in_block)
    n = lzud->left_in_block;
#endif
  chars_read = lzud->get_bytes(lzud->in_arg, n, buf);
#ifdef OLDFRAMING
  lzud->left_in_frame -= chars_read;
  lzud->left_in_block -= chars_read;
#else
  lzud->left_in_frame -= chars_read % LZX_FRAME_SIZE;
  if (lzud->left_in_frame < 0)
    lzud->left_in_frame += LZX_FRAME_SIZE;
#endif
  if ((chars_read < n) && (lzud->left_in_frame)) {
    chars_pad = n - chars_read;
    if (chars_pad > lzud->left_in_frame) chars_pad = lzud->left_in_frame;
    /* never emit a full frame of padding.  This prevents silliness when
       lzx_compress is called when at EOF but EOF not yet detected */
    if (chars_pad == LZX_FRAME_SIZE) chars_pad = 0;
#ifdef OLDFRAMING
    if (chars_pad > lzud->left_in_block) chars_pad = lzud->left_in_block;
#endif
    memset(buf + chars_read, 0, chars_pad);
    lzud->left_in_frame -= chars_pad;
#ifdef OLDFRAMING
    lzud->left_in_block -= chars_pad;
#endif
    chars_read += chars_pad;
  }
  return chars_read;
}

#ifdef NONSLIDE
static int find_match_at(lz_info *lzi, int loc, int match_len, int *match_locp)
{
  unsigned char *matchb;
  unsigned char *nmatchb;
  unsigned char *c1, *c2;
  int j;

  if (-*match_locp == loc) return -1;
  if (loc < match_len) return -1;

  matchb = lzi->block_buf + lzi->block_loc + *match_locp;
  nmatchb = lzi->block_buf + lzi->block_loc - loc;
  c1 = matchb;
  c2 = nmatchb;
  for (j = 0; j < match_len; j++) {
    if (*c1++ != *c2++) break;
  }
  if (j == match_len) {
#ifdef DEBUG_MATCHES
    fprintf(stderr, "match found %d, old = %d new = %d len = %d\n", lzi->cur_loc, -*match_locp, loc, match_len);
#endif
    *match_locp = -loc;
    return 0;
  }
  return -1;
}
#else
static int find_match_at(lz_info *lzi, int loc, int match_len, int *match_locp)
{
  unsigned char *matchb;
  unsigned char *nmatchb;
  unsigned char *c1, *c2;
  int j;

  if (-*match_locp == loc) return -1;
  if (loc < match_len) return -1;

  matchb = lzi->slide_bufp + *match_locp;
  if (matchb < lzi->slide_buf) matchb += lzi->slide_buf_size;
  nmatchb = lzi->slide_bufp - loc;
  if (nmatchb < lzi->slide_buf) nmatchb += lzi->slide_buf_size;
  c1 = matchb;
  c2 = nmatchb;
  for (j = 0; j < match_len; j++) {
    if (*c1++ != *c2++) break;
    if (c1 == lzi->slide_bufe) c1 = lzi->slide_buf;
    if (c2 == lzi->slide_bufe) c2 = lzi->slide_buf;
  }
  if (j == match_len) {
#ifdef DEBUG_MATCHES
    fprintf(stderr, "match found %d, old = %d new = %d len = %d\n", lzi->cur_loc, -*match_locp, loc, match_len);
#endif
    *match_locp = -loc;
    return 0;
  }
  return -1;
}
#endif
static void check_entropy(lzxc_data *lzud, int main_index)
{
  /* entropy = - sum_alphabet P(x) * log2 P(x) */
  /* entropy = - sum_alphabet f(x)/N * log2 (f(x)/N) */
  /* entropy = - 1/N sum_alphabet f(x) * (log2 f(x) - log2 N) */
  /* entropy = - 1/N (sum_alphabet f(x) * log2 f(x)) - sum_alphabet f(x) log2 N */
  /* entropy = - 1/N (sum_alphabet f(x) * log2 f(x)) - log2 N sum_alphabet f(x)  */
  /* entropy = - 1/N (sum_alphabet f(x) * log2 f(x)) - N * log2 N   */

  /* entropy = - 1/N ((sum_alphabet f(x) * log2 f(x) ) - N * log2 N) */
  /* entropy = - 1/N ((sum_alphabet f(x) * ln f(x) * 1/ln 2) - N * ln N * 1/ln 2) */
  /* entropy = 1/(N ln 2) (N * ln N - (sum_alphabet f(x) * ln f(x))) */
  /* entropy = 1/(N ln 2) (N * ln N + (sum_alphabet -f(x) * ln f(x))) */

  /* entropy = 1/(N ln 2) ( sum_alphabet ln N * f(x) + (sum_alphabet -f(x) * ln f(x))) */
  /* entropy = 1/(N ln 2) ( sum_alphabet ln N * f(x) +  (-f(x) * ln f(x))) */
  /* entropy = -1/(N ln 2) ( sum_alphabet -ln N * f(x) +  (f(x) * ln f(x))) */
  /* entropy = -1/(N ln 2) ( sum_alphabet f(x)(- ln N  + ln f(x))) */
  /* entropy = -1/(N ln 2) ( sum_alphabet f(x)(ln f(x)/N)) */
  /* entropy = -1/N  ( sum_alphabet (1/(ln 2))f(x)(ln f(x)/N)) */
  /* entropy = -1/N  ( sum_alphabet f(x)(log2 f(x)/N)) */
  /* entropy = -  ( sum_alphabet f(x)/N(log2 f(x)/N)) */
  /* entropy = -  ( sum_alphabet P(x)(log2 P(x))) */


    double freq;
    double n_ln_n;
    double rn_ln2;
    double cur_ratio;
    int n;

    /* delete old entropy accumulation */
    if (lzud->main_freq_table[main_index] != 1) {
      freq = (double)lzud->main_freq_table[main_index]-1;
      lzud->main_entropy += freq * log(freq);
    }
    /* add new entropy accumulation */
    freq = (double)lzud->main_freq_table[main_index];
    lzud->main_entropy -= freq * log(freq);
    n = lzud->block_codesp - lzud->block_codes;

    if (((n & 0xFFF) == 0) && (lzud->left_in_block >= 0x1000)) {
      n_ln_n = (double)n * log((double)n);
      rn_ln2 = rloge2 / (double)n;
      cur_ratio = (n * rn_ln2 *(n_ln_n + lzud->main_entropy) + 24 + 3 * 80 + NUM_CHARS + (lzud->main_tree_size-NUM_CHARS)*3 + NUM_SECONDARY_LENGTHS ) / (double)n;
#ifdef DEBUG_ENTROPY
      fprintf(stderr, "n = %d\n", n);
      fprintf(stderr, "main entropy = %f\n", rn_ln2 *(n_ln_n + lzud->main_entropy) );
      fprintf(stderr, "compression ratio (raw) = %f\n", 100.0 * rn_ln2 *(n_ln_n + lzud->main_entropy) /9.0 );
      fprintf(stderr, "compression ratio (ovh) = %f\n", 100.0 * cur_ratio/9.0);
#endif
      if (cur_ratio > lzud->last_ratio) {
#ifdef DEBUG_ENTROPY
	fprintf(stderr, "resetting huffman tables at %d\n", n);
#endif
	lzud->subdivide = -1;
	lz_stop_compressing(lzud->lzi);
      }
      lzud->last_ratio = cur_ratio;
    }
}

static int
lzx_output_match(lz_info *lzi, int match_pos, int match_len)
{
  lzxc_data *lzud = (lzxc_data *)lzi->user_data;
  uint32_t formatted_offset;
  uint32_t position_footer;
  uint8_t length_footer;
  uint8_t length_header;
  uint16_t len_pos_header;
  int position_slot;
  short btdt;

#ifdef DEBUG_LZ
  {
    int i;
    int pos;
    for (i = 0; i < match_len; i++) {

#ifdef NONSLIDE
      pos = match_pos + lzi->block_loc + i;
      fprintf(stderr, "%c", lzi->block_buf[pos]);
#else
      pos = match_pos + lzi->front_offset + i;
      if (pos > lzi->slide_buf_size)
	pos -= lzi->slide_buf_size;
      fprintf(stderr, "%c", lzi->slide_buf[pos]);
#endif
    }
  }
#endif
  position_footer = 0;
  btdt = 0;
 testforr:
  if (match_pos == -lzud->R0) {
    match_pos = 0;
    formatted_offset = 0;
    position_slot = 0;
  }
  else if (match_pos == -lzud->R1) {
    lzud->R1 = lzud->R0;
    lzud->R0 = -match_pos;
    match_pos = 1;
    formatted_offset = 1;
    position_slot = 1;
  }
  else if (match_pos == -lzud->R2) {
    lzud->R2 = lzud->R0;
    lzud->R0 = -match_pos;
    match_pos = 2;
    formatted_offset = 2;
    position_slot = 2;
  }
  else {
    if (!btdt) {
      btdt = 1;
      if (find_match_at(lzi, lzud->R0, match_len, &match_pos) == 0)
	goto testforr;
      if (find_match_at(lzi, lzud->R1, match_len, &match_pos) == 0)
	goto testforr;
      if (find_match_at(lzi, lzud->R2, match_len, &match_pos) == 0)
	goto testforr;
    }

    formatted_offset = -match_pos + 2;

    if ((match_len < 3) ||
	((formatted_offset >= 64) && (match_len < 4)) ||
	((formatted_offset >= 2048) && (match_len < 5)) ||
	((formatted_offset >= 65536) && (match_len < 6))) {
      /* reject matches where extra_bits will likely be bigger than just outputting
	 literals.  The numbers are basically derived through guessing
         and trial and error */
      return -1; /* reject the match */
    }

    lzud->R2 = lzud->R1;
    lzud->R1 = lzud->R0;
    lzud->R0 = -match_pos;

  /* calculate position base using binary search of table; if log2 can be
     done in hardware, approximation might work;
     trunc(log2(formatted_offset*formatted_offset)) gets either the proper
     position slot or the next one, except for slots 0, 1, and 39-49

     Slots 0-1 are handled by the R0-R1 procedures

     Slots 36-49 (formatted_offset >= 262144) can be found by
     (formatted_offset/131072) + 34 ==
     (formatted_offset >> 17) + 34;
  */
    if (formatted_offset >= 262144) {
      position_slot = (formatted_offset >> 17) + 34;
    }
    else {
      int left, right, mid;

      left = 3;
      right = lzud->num_position_slots - 1;
      position_slot = -1;
      while (left <= right) {
	mid = (left + right)/2;
	if ((position_base[mid] <= formatted_offset) &&
	    position_base[mid+1] > formatted_offset) {
	  position_slot = mid;
	  break;
	}
#if 0
	fprintf(stderr, "BEFORE: %06x %06x %06x %06x\n",
		position_base[left], position_base[mid],
		formatted_offset, position_base[right]);
#endif
	if (formatted_offset > position_base[mid])
	  /* too low */
	  left = mid + 1;
	else /* too high */
	  right = mid;
#if 0
	fprintf(stderr, "AFTER : %06x %06x %06x %06x\n",
		position_base[left], position_base[mid],
		formatted_offset, position_base[right]);
#endif
      }
#ifdef DEBUG_POSITION_SLOT_LOOKUP
      if (position_slot < 0) {
	fprintf(stderr, "lmr npr: %d %d %d %d\n", left, mid, right, lzud->num_position_slots);
	fprintf(stderr, "AFTER : %07d %07d %07d %07d\n",
		position_base[left], position_base[mid],
		formatted_offset, position_base[right]);
	fprintf(stderr, "(%d, %d, %d, %d, %d)\n", match_pos, match_len, formatted_offset, position_slot, position_footer);
      }
#endif
      assert(position_slot >= 0);
      /* FIXME precalc extra_mask table */
    }
    position_footer = ((1UL << extra_bits[position_slot]) - 1) & formatted_offset;
  }
#ifdef DEBUG_MATCHES
#ifdef NONSLIDE
  fprintf(stderr, "(%08x, %d, %d, %d, %d, %d)\n", lzud->lzi->cur_loc , match_pos, match_len, formatted_offset, position_slot, position_footer);
#else
  fprintf(stderr, "(%08x, %d, %d, %d, %d, %d)\n", lzud->lzi->cur_loc - lzud->lzi->chars_in_match , match_pos, match_len, formatted_offset, position_slot, position_footer);
#endif
#endif
  /* match length = 8 bits */
  /* position_slot = 6 bits */
  /* position_footer = 17 bits */
  /* total = 31 bits */
  /* plus one to say whether it's a literal or not */
  *lzud->block_codesp++ = 0x80000000 | /* bit 31 in intelligent bit ordering */
    (position_slot << 25) | /* bits 30-25 */
    (position_footer << 8) | /* bits 8-24 */
    (match_len - MIN_MATCH); /* bits 0-7 */

  if (match_len < (NUM_PRIMARY_LENGTHS + MIN_MATCH)) {
    length_header = match_len - MIN_MATCH;
    /*    length_footer = 255; */ /* not necessary */
  }
  else {
    length_header = NUM_PRIMARY_LENGTHS;
    length_footer = match_len - (NUM_PRIMARY_LENGTHS + MIN_MATCH);
    lzud->length_freq_table[length_footer]++;
  }
  len_pos_header = (position_slot << 3) | length_header;
  lzud->main_freq_table[len_pos_header + NUM_CHARS]++;
  if (extra_bits[position_slot] >= 3) {
    lzud->aligned_freq_table[position_footer & 7]++;
  }
#ifndef OLDFRAMING
  lzud->left_in_block -= match_len;
#endif
  if (lzud->subdivide)
    check_entropy(lzud, len_pos_header + NUM_CHARS);
  return 0; /* accept the match */
}

static void
lzx_output_literal(lz_info *lzi, unsigned char ch)
{
  lzxc_data *lzud = (lzxc_data *)lzi->user_data;

#ifndef OLDFRAMING
  lzud->left_in_block--;
#endif
  *lzud->block_codesp++ = ch;
#ifdef DEBUG_LZ
  fprintf(stderr, "%c", ch);
#endif
  lzud->main_freq_table[ch]++;
  if (lzud->subdivide)
    check_entropy(lzud, ch);
}

static void lzx_write_bits(lzxc_data *lzxd, int nbits, uint32_t bits)
{
  int cur_bits;
  int shift_bits;
  int rshift_bits;
  uint16_t mask_bits;

#ifdef DEBUG_BITBUF
  fprintf(stderr, "WB: %2d %08x\n", nbits, bits);
#endif
  cur_bits = lzxd->bits_in_buf;
  while ((cur_bits + nbits) >= 16) {
    shift_bits = 16 - cur_bits;
    rshift_bits = nbits - shift_bits;
    if (shift_bits == 16) {
      lzxd->bit_buf = (bits>>rshift_bits) & 0xFFFF;
    }
    else {
      mask_bits = (1U << shift_bits) - 1;
      lzxd->bit_buf <<= shift_bits;
      lzxd->bit_buf |= (bits>>rshift_bits) & mask_bits;
    }
#ifdef DEBUG_BITBUF
    fprintf(stderr, "WBB: %04x\n", lzxd->bit_buf);
#endif
#ifdef LZX_BIG_ENDIAN
    lzxd->bit_buf = ((lzxd->bit_buf & 0xFF)<<8) | (lzxd->bit_buf >> 8);
#endif
    lzxd->put_bytes(lzxd->out_arg, sizeof(lzxd->bit_buf), &lzxd->bit_buf);
    lzxd->len_compressed_output += sizeof(lzxd->bit_buf);
    lzxd->bit_buf = 0;
    nbits -= shift_bits;
    cur_bits = 0;
  }
  /* (cur_bits + nbits) < 16.  If nbits = 0, we're done.
     otherwise move bits in */
  shift_bits = nbits;
  mask_bits = (1U << shift_bits) - 1;
  lzxd->bit_buf <<= shift_bits;
  lzxd->bit_buf |= bits & mask_bits;
  cur_bits += nbits;

#ifdef DEBUG_BITBUF
  fprintf(stderr, "OBB: %2d %04x\n", cur_bits, lzxd->bit_buf);
#endif
  lzxd->bits_in_buf = cur_bits;
}

static void lzx_align_output(lzxc_data *lzxd)
{
  if (lzxd->bits_in_buf) {
    lzx_write_bits(lzxd, 16 - lzxd->bits_in_buf, 0);
  }
  if (lzxd->mark_frame)
    lzxd->mark_frame(lzxd->mark_frame_arg, lzxd->len_uncompressed_input, lzxd->len_compressed_output);
}

static void
lzx_write_compressed_literals(lzxc_data *lzxd, int block_type)
{
  uint32_t *cursor = lzxd->block_codes;
  uint32_t *endp = lzxd->block_codesp;
  uint16_t position_slot;
  uint32_t position_footer;
  uint32_t match_len_m2; /* match length minus 2, which is MIN_MATCH */
  uint32_t verbatim_bits;
  uint32_t block_code;
  uint16_t length_header;
  uint16_t length_footer;
  uint16_t len_pos_header;
  huff_entry *huffe;
  int frame_count = (lzxd->len_uncompressed_input % LZX_FRAME_SIZE);

  lzxd->len_uncompressed_input -= frame_count; /* will be added back in later */
  while (cursor < endp) {
    block_code = *cursor++;
    if (block_code & 0x80000000) {
      /*
       *    0x80000000 |                bit 31 in intelligent bit ordering
       * (position_slot << 25) |        bits 30-25
       * (position_footer << 8) |       bits 8-24
       * (match_len - MIN_MATCH);       bits 0-7
       *
       */

      match_len_m2 = block_code & 0xFF; /* 8 bits */
      position_footer = (block_code >> 8)& 0x1FFFF; /* 17 bits */
      position_slot = (block_code >> 25) & 0x3F; /* 6 bits */

#ifdef DEBUG_MATCHES_2
      fprintf(stderr, "%08x, %3d %2d %d\n", lzxd->len_uncompressed_input + frame_count, match_len_m2, position_slot, position_footer);
#endif
      if (match_len_m2 < NUM_PRIMARY_LENGTHS) {
	length_header = match_len_m2;
	length_footer = 255; /* personal encoding for NULL */
      }
      else {
	length_header = NUM_PRIMARY_LENGTHS;
	length_footer = match_len_m2 - NUM_PRIMARY_LENGTHS;
      }
      len_pos_header = (position_slot << 3) | length_header;
      huffe = &lzxd->main_tree[len_pos_header+NUM_CHARS];
      lzx_write_bits(lzxd, huffe->codelength, huffe->code);
      if (length_footer != 255) {
	huffe = &lzxd->length_tree[length_footer];
	lzx_write_bits(lzxd, huffe->codelength, huffe->code);
      }
      if ((block_type == LZX_ALIGNED_OFFSET_BLOCK) && (extra_bits[position_slot] >= 3)) {
	/* aligned offset block and code */
	verbatim_bits = position_footer >> 3;
	lzx_write_bits(lzxd, extra_bits[position_slot] - 3, verbatim_bits);
	huffe = &lzxd->aligned_tree[position_footer&7];
	lzx_write_bits(lzxd, huffe->codelength, huffe->code);
      }
      else {
	verbatim_bits = position_footer;
	lzx_write_bits(lzxd, extra_bits[position_slot], verbatim_bits);
      }
      frame_count += match_len_m2 + 2;
    }
    else {
      /* literal */
      assert(block_code < NUM_CHARS);
      huffe = &lzxd->main_tree[block_code];
      lzx_write_bits(lzxd, huffe->codelength, huffe->code);
      frame_count++;
    }
    if (frame_count == LZX_FRAME_SIZE) {
      lzxd->len_uncompressed_input += frame_count;
      lzx_align_output(lzxd);
      frame_count = 0;
    }
#ifdef DEBUG_MATCHES_2
    if (frame_count > LZX_FRAME_SIZE) {
      fprintf(stderr, "uncomp_len = %x, frame_count = %x, block_code = %08x, match_len_m2 = %d", lzxd->len_uncompressed_input, frame_count, block_code, match_len_m2);
    }
#endif
    assert (frame_count < LZX_FRAME_SIZE);
  }
  lzxd->len_uncompressed_input += frame_count;
}

static int
lzx_write_compressed_tree(struct lzxc_data *lzxd,
			  struct huff_entry *tree, uint8_t *prevlengths,
			  int treesize)
{
  unsigned char *codes;
  unsigned char *runs;
  int freqs[LZX_PRETREE_SIZE];
  int cur_run;
  int last_len;
  huff_entry pretree[20];
  unsigned char *codep;
  unsigned char *codee;
  unsigned char *runp;
  int excess;
  int i;
  int cur_code;

  codep = codes = malloc(treesize*sizeof(char));
  runp = runs = malloc(treesize*sizeof(char));
  memset(freqs, 0, sizeof(freqs));
  cur_run = 1;
  last_len = tree[0].codelength;
  for (i = 1; i <= treesize; i++) {
    if ((i == treesize) || (tree[i].codelength != last_len)) {
      if (last_len == 0) {
	while (cur_run >= 20) {
	  excess =  cur_run - 20;
	  if (excess > 31) excess = 31;
	  *codep++ = 18;
	  *runp++ = excess;
	  cur_run -= excess + 20;
	  freqs[18]++;
	}
	while (cur_run >= 4) {
	  excess =  cur_run - 4;
	  if (excess > 15) excess = 15;
	  *codep++ = 17;
	  *runp++ = excess;
	  cur_run -= excess + 4;
	  freqs[17]++;
	}
	while (cur_run > 0) {
	  *codep = prevlengths[i - cur_run];
	  freqs[*codep++]++;
	  *runp++ = 0; /* not necessary */
	  cur_run--;
	}
      }
      else {
	while (cur_run >= 4) {
	  if (cur_run == 4) excess = 0;
	  else excess = 1;
	  *codep++ = 19;
	  *runp++ = excess;
	  freqs[19]++;
	  /* right, MS lies again.  Code is NOT
	     prev_len + len (mod 17), it's prev_len - len (mod 17)*/
	  *codep = prevlengths[i-cur_run] - last_len;
	  if (*codep > 16) *codep += 17;
	  freqs[*codep++]++;
	  *runp++ = 0; /* not necessary */
	  cur_run -= excess+4;
	}
	while (cur_run > 0) {
	  *codep = prevlengths[i-cur_run] - last_len;
	  if (*codep > 16) *codep += 17;
	  *runp++ = 0; /* not necessary */
	  cur_run--;
	  freqs[*codep++]++;
	}
      }
      if (i != treesize)
	last_len = tree[i].codelength;
      cur_run = 0;
    }
    cur_run++;
  }
  codee = codep;
#ifdef DEBUG_TREE_COMPRESSION
  *codep++ = 255;
  *runp++ = 255;
  fprintf(stderr, "num:  len  code  run\n");
  for (i = 0; i < treesize; i++) {
    fprintf(stderr, "%3d:  %2d   %2d    %2d\n", i, tree[i].codelength, codes[i], runs[i]);
  }
#endif
  /* now create the huffman table and write out the pretree */
  build_huffman_tree(LZX_PRETREE_SIZE, 16, freqs, pretree);
  for (i = 0; i < LZX_PRETREE_SIZE; i++) {
    lzx_write_bits(lzxd, 4, pretree[i].codelength);
  }
  codep = codes;
  runp = runs;
  cur_run = 0;
  while (codep < codee) {
    cur_code = *codep++;
    lzx_write_bits(lzxd, pretree[cur_code].codelength, pretree[cur_code].code);
    if (cur_code == 17) {
      cur_run += *runp + 4;
      lzx_write_bits(lzxd, 4, *runp);
    }
    else if (cur_code == 18) {
      cur_run += *runp + 20;
      lzx_write_bits(lzxd, 5, *runp);
    }
    else if (cur_code == 19) {
      cur_run += *runp + 4;
      lzx_write_bits(lzxd, 1, *runp);
      cur_code = *codep++;
      lzx_write_bits(lzxd, pretree[cur_code].codelength, pretree[cur_code].code);
      runp++;
    }
    else {
      cur_run++;
    }
    runp++;
  }
  free(codes);
  free(runs);
  return 0;
}

void
lzxc_reset(lzxc_data *lzxd)
{
  lzxd->need_1bit_header = 1;
  lzxd->R0 = lzxd->R1 = lzxd->R2 = 1;
  memset(lzxd->prev_main_treelengths, 0, lzxd->main_tree_size * sizeof(uint8_t));
  memset(lzxd->prev_length_treelengths, 0, NUM_SECONDARY_LENGTHS * sizeof(uint8_t));
  lz_reset(lzxd->lzi);
}

int lzxc_compress_block(lzxc_data *lzxd, int block_size, int subdivide)
{
  int i;
  uint32_t written_sofar = 0;
  int block_type;
  long uncomp_bits;
  long comp_bits;
  long comp_bits_ovh;
  long uncomp_length;

  if ((lzxd->block_size != block_size) || (lzxd->block_codes == NULL)) {
    if (lzxd->block_codes != NULL) free(lzxd->block_codes);
    lzxd->block_size = block_size;
    lzxd->block_codes =  malloc(block_size * sizeof(uint32_t));
  }
  lzxd->subdivide = subdivide?1:0;

  lzxd->left_in_block = block_size;
  lzxd->left_in_frame = LZX_FRAME_SIZE;
  lzxd->main_entropy = 0.0;
  lzxd->last_ratio = 9999999.0;
  lzxd->block_codesp = lzxd->block_codes;

  memset(lzxd->length_freq_table, 0, NUM_SECONDARY_LENGTHS * sizeof(int));
  memset(lzxd->main_freq_table, 0, lzxd->main_tree_size * sizeof(int));
  memset(lzxd->aligned_freq_table, 0, LZX_ALIGNED_SIZE * sizeof(int));
  do {
    lz_compress(lzxd->lzi, lzxd->left_in_block);
    if (lzxd->left_in_frame == 0)
      lzxd->left_in_frame = LZX_FRAME_SIZE;

    if ((lzxd->subdivide<0) || !lzxd->left_in_block ||
	(!lz_left_to_process(lzxd->lzi) && lzxd->at_eof(lzxd->in_arg))) {
      /* now one block is LZ-analyzed. */
      /* time to write it out */
      uncomp_length = lzxd->block_size - lzxd->left_in_block - written_sofar;
      /* uncomp_length will sometimes be 0 when input length is
	 an exact multiple of frame size */
      if (uncomp_length == 0)
	  continue;
      if (lzxd->subdivide < 0) {
#ifdef DEBUG_ENTROPY
	fprintf(stderr, "subdivided\n");
#endif
	lzxd->subdivide = 1;
      }

      if (lzxd->need_1bit_header) {
	/* one bit Intel preprocessing header */
	/* always 0 because this implementation doesn't do Intel preprocessing */
	lzx_write_bits(lzxd, 1, 0);
	lzxd->need_1bit_header = 0;
      }

      /* handle extra bits */
      uncomp_bits = comp_bits = 0;
      build_huffman_tree(LZX_ALIGNED_SIZE, 7, lzxd->aligned_freq_table, lzxd->aligned_tree);
      for (i = 0; i < LZX_ALIGNED_SIZE; i++) {
	uncomp_bits += lzxd->aligned_freq_table[i]* 3;
	comp_bits += lzxd->aligned_freq_table[i]* lzxd->aligned_tree[i].codelength;
      }
      comp_bits_ovh = comp_bits + LZX_ALIGNED_SIZE * 3;
      if (comp_bits_ovh < uncomp_bits)
      	block_type = LZX_ALIGNED_OFFSET_BLOCK;
      else
	block_type = LZX_VERBATIM_BLOCK;

#ifdef DEBUG_EXTRA_BITS
      fprintf(stderr, "Extra bits uncompressed: %5d  compressed:  %5d  compressed w/overhead %5d gain/loss %5d\n", uncomp_bits, comp_bits, comp_bits_ovh, uncomp_bits - comp_bits_ovh);
#endif

      /* block type */
      lzx_write_bits(lzxd, 3, block_type);
      /* uncompressed length */
      lzx_write_bits(lzxd, 24, uncomp_length);

      written_sofar = lzxd->block_size - lzxd->left_in_block;

      /* now write out the aligned offset trees if present */
      if (block_type == LZX_ALIGNED_OFFSET_BLOCK) {
	for (i = 0; i < LZX_ALIGNED_SIZE; i++) {
	  lzx_write_bits(lzxd, 3, lzxd->aligned_tree[i].codelength);
	}
      }
      /* end extra bits */
      build_huffman_tree(lzxd->main_tree_size, LZX_MAX_CODE_LENGTH,
			 lzxd->main_freq_table, lzxd->main_tree);
      build_huffman_tree(NUM_SECONDARY_LENGTHS, 16,
			 lzxd->length_freq_table, lzxd->length_tree);



      /* now write the pre-tree and tree for main 1 */
      lzx_write_compressed_tree(lzxd, lzxd->main_tree, lzxd->prev_main_treelengths, NUM_CHARS);

      /* now write the pre-tree and tree for main 2*/
      lzx_write_compressed_tree(lzxd, lzxd->main_tree + NUM_CHARS,
				lzxd->prev_main_treelengths + NUM_CHARS,
				lzxd->main_tree_size - NUM_CHARS);

      /* now write the pre tree and tree for length */
      lzx_write_compressed_tree(lzxd, lzxd->length_tree, lzxd->prev_length_treelengths,
				NUM_SECONDARY_LENGTHS);

      /* now write literals */
      lzx_write_compressed_literals(lzxd, block_type);

      /* copy treelengths somewhere safe to do delta compression */
      for (i = 0; i < lzxd->main_tree_size; i++) {
	lzxd->prev_main_treelengths[i] = lzxd->main_tree[i].codelength;
      }
      for (i = 0; i < NUM_SECONDARY_LENGTHS; i++) {
	lzxd->prev_length_treelengths[i] = lzxd->length_tree[i].codelength;
      }
      lzxd->main_entropy = 0.0;
      lzxd->last_ratio = 9999999.0;
      lzxd->block_codesp = lzxd->block_codes;

      memset(lzxd->length_freq_table, 0, NUM_SECONDARY_LENGTHS * sizeof(int));
      memset(lzxd->main_freq_table, 0, lzxd->main_tree_size * sizeof(int));
      memset(lzxd->aligned_freq_table, 0, LZX_ALIGNED_SIZE * sizeof(int));
    }
  }
  while (lzxd->left_in_block && (lz_left_to_process(lzxd->lzi) || !lzxd->at_eof(lzxd->in_arg)));
  return 0;
}

int lzxc_init(struct lzxc_data **lzxdp, int wsize_code,
	     lzxc_get_bytes_t get_bytes, void *get_bytes_arg,
	     lzxc_at_eof_t at_eof,
	     lzxc_put_bytes_t put_bytes, void *put_bytes_arg,
	     lzxc_mark_frame_t mark_frame, void *mark_frame_arg)
{
  int wsize;
  struct lzxc_data *lzxd;

  if ((wsize_code < 15) || (wsize_code > 21)) {
    return -1;
  }
  lzx_init_static();

  *lzxdp = lzxd = malloc(sizeof(*lzxd));
  if (lzxd == 0)
    return -2;

  lzxd->in_arg = get_bytes_arg;
  lzxd->out_arg = put_bytes_arg;
  lzxd->mark_frame_arg = mark_frame_arg;
  lzxd->get_bytes = get_bytes;
  lzxd->put_bytes = put_bytes;
  lzxd->at_eof = at_eof;
  lzxd->mark_frame = mark_frame;

  wsize = 1 << (wsize_code);

  lzxd->bits_in_buf = 0;
  lzxd->block_size = 0;
  lzxd->block_codes = NULL;
  lzxd->num_position_slots = num_position_slots[wsize_code-15];
  lzxd->main_tree_size = (NUM_CHARS + 8 * lzxd->num_position_slots);

  lzxd->main_freq_table = malloc(sizeof(int) * lzxd->main_tree_size);
  lzxd->main_tree = malloc(sizeof(huff_entry)* lzxd->main_tree_size);
  lzxd->prev_main_treelengths = malloc(sizeof(uint8_t)*lzxd->main_tree_size);

  lzxd->lzi = malloc(sizeof (*lzxd->lzi));
  /* the -3 prevents matches at wsize, wsize-1, wsize-2, all of which are illegal */
  lz_init(lzxd->lzi, wsize, wsize - 3, MAX_MATCH, MIN_MATCH, LZX_FRAME_SIZE,
	  lzx_get_chars, lzx_output_match, lzx_output_literal,lzxd);
  lzxd->len_uncompressed_input = 0;
  lzxd->len_compressed_output = 0;
  lzxc_reset(lzxd);
  return 0;
}

int lzxc_finish(struct lzxc_data *lzxd, struct lzxc_results *lzxr)
{
  /*  lzx_align_output(lzxd);  Not needed as long as frame padding is in place */
  if (lzxr) {
    lzxr->len_compressed_output = lzxd->len_compressed_output;
    lzxr->len_uncompressed_input = lzxd->len_uncompressed_input;
  }
  lz_release(lzxd->lzi);
  free(lzxd->lzi);
  free(lzxd->prev_main_treelengths);
  free(lzxd->main_tree);
  free(lzxd->main_freq_table);
  if (lzxd->block_codes) {
    free(lzxd->block_codes);
  }
  free(lzxd);
  return 0;
}
