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

*/

#pragma once

typedef struct lzxc_data lzxc_data;
typedef int (*lzxc_get_bytes_t)(void *arg, int n, void *buf);
typedef int (*lzxc_put_bytes_t)(void *arg, int n, void *buf);
typedef void (*lzxc_mark_frame_t)(void *arg, uint32_t uncomp, uint32_t comp);
typedef int (*lzxc_at_eof_t)(void *arg);

typedef struct lzxc_results
{
  /* add more here? Error codes, # blocks, # frames, etc? */
  long len_compressed_output;
  long len_uncompressed_input;
} lzxc_results;

int lzxc_init(struct lzxc_data **lzxdp, int wsize_code,
	     lzxc_get_bytes_t get_bytes, void *get_bytes_arg,
	     lzxc_at_eof_t at_eof,
	     lzxc_put_bytes_t put_bytes, void *put_bytes_arg,
	     lzxc_mark_frame_t mark_frame, void *mark_frame_arg);

void lzxc_reset(lzxc_data *lzxd);

int lzxc_compress_block(lzxc_data *lzxd, int block_size, int subdivide);

int lzxc_finish(struct lzxc_data *lzxd, struct lzxc_results *lzxr);
