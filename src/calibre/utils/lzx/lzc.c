/*
    File lz_nonslide.c, part of lzxcomp library
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

/* 
 * Document here
 */
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#ifdef DEBUG_PERF
#include <sys/time.h>
#include <sys/resource.h>
#endif
#include "lzc.h"

#define MAX_MATCH 253
#define MIN_MATCH 2

void lz_init(lz_info *lzi, int wsize, int max_dist,
	     int max_match, int min_match,
	     int frame_size,
	     get_chars_t get_chars,
	     output_match_t output_match,
	     output_literal_t output_literal, void *user_data)
{
  /* the reason for the separate max_dist value is LZX can't reach the 
     first three characters in its nominal window.  But using a smaller
     window results in inefficiency when dealing with reset intervals
     which are the length of the nominal window */

  lzi->wsize = wsize;
  if (max_match > wsize)
    lzi->max_match = wsize;
  else
    lzi->max_match = max_match;

  lzi->min_match = min_match;
  if (lzi->min_match < 3) lzi->min_match = 3;

  lzi->max_dist = max_dist; 
  lzi->block_buf_size = wsize + lzi->max_dist; 
  lzi->block_buf = malloc(lzi->block_buf_size);
  lzi->block_bufe = lzi->block_buf + lzi->block_buf_size;
  assert(lzi->block_buf != NULL);
  
  lzi->cur_loc = 0;
  lzi->block_loc = 0;
  lzi->chars_in_buf = 0;
  lzi->eofcount = 0;
  lzi->get_chars = get_chars;
  lzi->output_match = output_match;
  lzi->output_literal = output_literal;
  lzi->user_data = user_data;
  lzi->frame_size = frame_size;
  lzi->lentab = calloc(lzi->block_buf_size + 1, sizeof(int));
  lzi->prevtab = calloc(lzi->block_buf_size + 1, sizeof(unsigned char *));
  lzi->analysis_valid = 0;
}

void lz_release(lz_info *lzi)
{
  free(lzi->block_buf);
  free(lzi->lentab);
  free(lzi->prevtab);
}

void lz_reset(lz_info *lzi)
{
  int residual = lzi->chars_in_buf - lzi->block_loc;
  memmove(lzi->block_buf, lzi->block_buf + lzi->block_loc, residual);
  lzi->chars_in_buf = residual;
  lzi->block_loc = 0;
  lzi->analysis_valid = 0;
}

#ifdef LZNONSLIDE_MAIN
typedef struct lz_user_data
{
  FILE *infile;
  FILE *outfile;
  int R0, R1, R2;
} lz_user_data;

int tmp_get_chars(lz_info *lzi, int n, unsigned char *buf)
{
  lz_user_data *lzud = (lz_user_data *)lzi->user_data;
  return fread(buf, 1, n, lzud->infile);
}

int tmp_output_match(lz_info *lzi, int match_pos, int match_len)
{
  lz_user_data *lzud = (lz_user_data *)lzi->user_data;
  int mod_match_loc;
  
  mod_match_loc = match_pos;

  fprintf(lzud->outfile, "(%d, %d)(%d)\n", match_pos, match_len, mod_match_loc);
  return 0;
}

void tmp_output_literal(lz_info *lzi, unsigned char ch)
{
  lz_user_data *lzud = (lz_user_data *)lzi->user_data;
  fprintf(lzud->outfile, "'%c'", ch);
}

int main(int argc, char *argv[])
{
  int wsize = atoi(argv[1]);
  lz_info lzi;
  lz_user_data lzu = {stdin, stdout, 1, 1, 1};

  lz_init(&lzi, wsize, wsize, MAX_MATCH, MIN_MATCH, 8192, tmp_get_chars, tmp_output_match, tmp_output_literal,&lzu);
  lz_compress(&lzi);
  return 0;
}
#endif

int lz_left_to_process(lz_info *lzi)
{
  return lzi->chars_in_buf - lzi->block_loc;
}

static void
fill_blockbuf(lz_info *lzi, int maxchars)
{
  int toread;
  unsigned char *readhere;
  int nread;

  if (lzi->eofcount) return;
  maxchars -= lz_left_to_process(lzi);
  toread = lzi->block_buf_size - lzi->chars_in_buf;
  if (toread > maxchars) toread = maxchars;
  readhere = lzi->block_buf + lzi->chars_in_buf;
  nread = lzi->get_chars(lzi, toread, readhere);
  lzi->chars_in_buf += nread;
  if (nread != toread)
    lzi->eofcount++;
}

static void lz_analyze_block(lz_info *lzi)
{
  int *lentab, *lenp;
  unsigned char **prevtab, **prevp;
  unsigned char *bbp, *bbe;
  unsigned char *chartab[256];
  unsigned char *cursor;
  int prevlen;
  int ch;
  int maxlen;
  long wasinc;
  int max_dist = lzi->max_dist;
#ifdef DEBUG_ANALYZE_BLOCK
  static short n = 0;
#endif
#ifdef DEBUG_PERF
  struct rusage innerloop;
  struct timeval innertime, tmptime;
  struct rusage outerloop;
  struct timeval outertime;
  struct rusage initialloop;
  struct timeval initialtime;
  struct rusage totalloop;
  struct timeval totaltime;
#endif

#ifdef DEBUG_ANALYZE_BLOCK
  fprintf(stderr, "Analyzing block %d, cur_loc = %06x\n", n, lzi->cur_loc);
#endif
  memset(chartab, 0, sizeof(chartab));
  prevtab = prevp = lzi->prevtab;
  lentab = lenp = lzi->lentab;
  memset(prevtab, 0, sizeof(*prevtab) * lzi->chars_in_buf);
  memset(lentab, 0, sizeof(*lentab) * lzi->chars_in_buf);
#ifdef DEBUG_PERF
  memset(&innertime, 0, sizeof(innertime));
  memset(&outertime, 0, sizeof(outertime));
  getrusage(RUSAGE_SELF, &initialloop);
  totalloop = initialloop;
#endif
  bbp = lzi->block_buf;
  bbe = bbp + lzi->chars_in_buf;
  while (bbp < bbe) {
    if (chartab[ch = *bbp]) {
      *prevp = chartab[ch];
      *lenp = 1;
    }
    chartab[ch] = bbp;
    bbp++;
    prevp++;
    lenp++;
  }
#ifdef DEBUG_PERF
  initialtime = initialloop.ru_utime;
  getrusage(RUSAGE_SELF, &initialloop);
  timersub(&initialloop.ru_utime, &initialtime, &initialtime);
#endif
  wasinc = 1;
  for (maxlen = 1; wasinc && (maxlen < lzi->max_match); maxlen++) {
#ifdef DEBUG_PERF
    getrusage(RUSAGE_SELF, &outerloop);
#endif
    bbp = bbe - maxlen - 1;
    lenp = lentab + lzi->chars_in_buf - maxlen - 1;
    prevp = prevtab + lzi->chars_in_buf - maxlen - 1;
    wasinc = 0;
    while (bbp > lzi->block_buf) {
      if (*lenp == maxlen) {
#ifdef DEBUG_PERF
	getrusage(RUSAGE_SELF, &innerloop);
#endif
	ch = bbp[maxlen];
	cursor = *prevp;
	while(cursor && ((bbp - cursor) <= max_dist)) {
	  prevlen = *(cursor - lzi->block_buf + lentab);
	  if (cursor[maxlen] == ch) {
	    *prevp = cursor;
	    (*lenp)++;
	    wasinc++;
	    break;
	  }
	  if (prevlen != maxlen) break;
	  cursor = *(cursor - lzi->block_buf + prevtab);
	}
#ifdef DEBUG_PERF
	tmptime = innerloop.ru_utime;
	getrusage(RUSAGE_SELF, &innerloop);
	timersub(&innerloop.ru_utime, &tmptime, &tmptime);
	timeradd(&tmptime, &innertime, &innertime);
#endif
      }
      bbp--;
      prevp--;
      lenp--;
    }
#ifdef DEBUG_PERF
    tmptime = outerloop.ru_utime;
    getrusage(RUSAGE_SELF, &outerloop);
    timersub(&outerloop.ru_utime, &tmptime, &tmptime);
    timeradd(&tmptime, &outertime, &outertime);
#endif
    //    fprintf(stderr, "maxlen = %d, wasinc = %ld\n", maxlen, wasinc);
  }
#ifdef DEBUG_PERF
  totaltime = totalloop.ru_utime;
  getrusage(RUSAGE_SELF, &totalloop);
  timersub(&totalloop.ru_utime, &totaltime, &totaltime);
  fprintf(stderr, "Time spend in initial loop = %f\n", initialtime.tv_sec + initialtime.tv_usec/(double)1E6);
  fprintf(stderr, "Time spend in outer loop = %f\n", outertime.tv_sec + outertime.tv_usec/(double)1E6);
  fprintf(stderr, "Time spend in inner loop = %f\n", innertime.tv_sec + innertime.tv_usec/(double)1E6);
  fprintf(stderr, "Time spend in all loops = %f\n", totaltime.tv_sec + totaltime.tv_usec/(double)1E6);
#endif
  lzi->analysis_valid = 1;
#ifdef DEBUG_ANALYZE_BLOCK
  fprintf(stderr, "Done analyzing block %d, cur_loc = %06x\n", n++, lzi->cur_loc);
#endif
}

void lz_stop_compressing(lz_info *lzi) 
{
  lzi->stop = 1;
  /*  fprintf(stderr, "Stopping...\n");*/
}

int lz_compress(lz_info *lzi, int nchars) 
{

  unsigned char *bbp, *bbe;
  int *lenp;
  unsigned char **prevp;
  int len;
  int holdback;
  short trimmed;

  lzi->stop = 0;
  while ((lz_left_to_process(lzi) || !lzi->eofcount) && !lzi->stop && nchars > 0) {
#if 1
    if (!lzi->analysis_valid ||
	(!lzi->eofcount &&
	 ((lzi->chars_in_buf- lzi->block_loc) < nchars))) {
      int residual = lzi->chars_in_buf - lzi->block_loc;
      int bytes_to_move = lzi->max_dist + residual;
      if (bytes_to_move > lzi->chars_in_buf)
	bytes_to_move = lzi->chars_in_buf;
#ifdef DEBUG_ANALYZE_BLOCK
      fprintf(stderr, "Moving %06x, chars_in_buf %06x, residual = %06x, nchars= %06x block_loc = %06x\n", bytes_to_move, lzi->chars_in_buf, residual, nchars, lzi->block_loc);
#endif
      memmove(lzi->block_buf, lzi->block_buf + lzi->chars_in_buf - bytes_to_move,
	      bytes_to_move);
      
      lzi->block_loc = bytes_to_move - residual;
      lzi->chars_in_buf = bytes_to_move;
#ifdef DEBUG_ANALYZE_BLOCK
      fprintf(stderr, "New chars_in_buf %06x,  new block_loc = %06x, eof = %1d\n", lzi->chars_in_buf, lzi->block_loc, lzi->eofcount);
#endif
      fill_blockbuf(lzi, nchars);
#ifdef DEBUG_ANALYZE_BLOCK
      fprintf(stderr, "Really new chars_in_buf %06x,  new block_loc = %06x, eof = %1d\n", lzi->chars_in_buf, lzi->block_loc, lzi->eofcount);
#endif
      lz_analyze_block(lzi);
    }
#else
    if (!lzi->analysis_valid ||
	(lzi->block_loc - lzi->chars_in_buf) == 0) {
      lzi->block_loc = 0;
      lzi->chars_in_buf = 0;
      fill_blockbuf(lzi, nchars);
      lz_analyze_block(lzi);
    }
#endif
    prevp = lzi->prevtab + lzi->block_loc;
    lenp = lzi->lentab + lzi->block_loc;
    bbp = lzi->block_buf + lzi->block_loc;
    holdback = lzi->max_match;
    if (lzi->eofcount) holdback = 0;
    if (lzi->chars_in_buf < (nchars + lzi->block_loc))
      bbe = lzi->block_buf + lzi->chars_in_buf - holdback;
    else
      bbe = bbp + nchars;
    while ((bbp < bbe) && (!lzi->stop)) {
      trimmed = 0;
      len = *lenp;
      if (lzi->frame_size && (len > (lzi->frame_size - lzi->cur_loc % lzi->frame_size))) {
#ifdef DEBUG_TRIMMING
	fprintf(stderr, "Trim for framing: %06x %d %d\n", lzi->cur_loc,len, (lzi->frame_size - lzi->cur_loc % lzi->frame_size));
#endif
	trimmed = 1;
	len = (lzi->frame_size - lzi->cur_loc % lzi->frame_size);
      }
      if (len > nchars) {
#ifdef DEBUG_TRIMMING
	fprintf(stderr, "Trim for blocking: %06x %d %d\n", lzi->cur_loc,len, nchars);
#endif
	trimmed = 1;
	len = nchars;
      }
      if (len >= lzi->min_match) {
#ifdef LAZY
	if ((bbp < bbe -1) && !trimmed &&
	    ((lenp[1] > (len + 1)) /* || ((lenp[1] == len) && (prevp[1] > prevp[0])) */)) {
	  len = 1;
	  /* this is the lazy eval case */
	}
	else 
#endif
	  if (lzi->output_match(lzi, (*prevp - lzi->block_buf) - lzi->block_loc,
				len) < 0) {
	    //	    fprintf(stderr, "Match rejected: %06x %d\n", lzi->cur_loc, len);
	    len = 1; /* match rejected */
	  }
      }
      else
	len = 1;
      
      if (len < lzi->min_match) {
	assert(len == 1);
	lzi->output_literal(lzi, *bbp);
      }
      //      fprintf(stderr, "len = %3d, *lenp = %3d, cur_loc = %06x, block_loc = %06x\n", len, *lenp, lzi->cur_loc, lzi->block_loc);
      bbp += len;
      prevp += len;
      lenp += len;
      lzi->cur_loc += len;
      lzi->block_loc += len;
      assert(nchars >= len);
      nchars -= len;

    }
  }
  return 0;
}
