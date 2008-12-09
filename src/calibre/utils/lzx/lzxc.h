/*
    File lzx_compress.h, part of lzxcomp library
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

#if BYTE_ORDER == BIG_ENDIAN
# define LZX_BIG_ENDIAN
#endif

/* the names of these constants are specific to this library */
#define LZX_MAX_CODE_LENGTH                 16
#define LZX_FRAME_SIZE                   32768
#define LZX_PRETREE_SIZE                    20
#define LZX_ALIGNED_BITS                     3
#define LZX_ALIGNED_SIZE                     8

#define LZX_VERBATIM_BLOCK                   1
#define LZX_ALIGNED_OFFSET_BLOCK             2

typedef struct lzx_data lzx_data;
typedef int (*lzx_get_bytes_t)(void *arg, int n, void *buf);
typedef int (*lzx_put_bytes_t)(void *arg, int n, void *buf);
typedef void (*lzx_mark_frame_t)(void *arg, uint32_t uncomp, uint32_t comp);
typedef int (*lzx_at_eof_t)(void *arg);

typedef struct lzx_results
{
  /* add more here? Error codes, # blocks, # frames, etc? */
  long len_compressed_output;
  long len_uncompressed_input;
} lzx_results;

int lzx_init(struct lzx_data **lzxdp, int wsize_code, 
	     lzx_get_bytes_t get_bytes, void *get_bytes_arg,
	     lzx_at_eof_t at_eof,
	     lzx_put_bytes_t put_bytes, void *put_bytes_arg,
	     lzx_mark_frame_t mark_frame, void *mark_frame_arg);

void  lzx_reset(lzx_data *lzxd);

int lzx_compress_block(lzx_data *lzxd, int block_size, int subdivide);

int lzx_finish(struct lzx_data *lzxd, struct lzx_results *lzxr);

