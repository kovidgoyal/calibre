/*
    File lz_nonslide.h, part of lzxcomp library
    Copyright (C) 2002 Matthew T. Russotto

    This program is free software; you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation; version 2.1 only

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
*/
typedef struct lz_info lz_info;
typedef int (*get_chars_t)(lz_info *lzi, int n, u_char *buf);
typedef int (*output_match_t)(lz_info *lzi, int match_pos, int match_len);
typedef void (*output_literal_t)(lz_info *lzi, u_char ch);

struct lz_info
{
  int wsize; /* window size in bytes */
  int max_match; /* size of longest match in bytes */
  int min_match;
  u_char *block_buf;
  u_char *block_bufe;
  int block_buf_size;
  int chars_in_buf;
  int cur_loc;            /* location within stream */
  int block_loc;
  int frame_size;
  int max_dist;
  u_char **prevtab;
  int *lentab;
  short eofcount;
  short stop;
  short analysis_valid;

  get_chars_t get_chars;
  output_match_t output_match;
  output_literal_t output_literal;
  void *user_data;
};

void lz_init(lz_info *lzi, int wsize, int max_dist,
	     int max_match, int min_match,
	     int frame_size,
	     get_chars_t get_chars,
	     output_match_t output_match,
	     output_literal_t output_literal, void *user_data);

void lz_release(lz_info *lzi);

void lz_reset(lz_info *lzi);
void lz_stop_compressing(lz_info *lzi);
int lz_left_to_process(lz_info *lzi); /* returns # chars read in but unprocessed */
int lz_compress(lz_info *lzi, int nchars);
