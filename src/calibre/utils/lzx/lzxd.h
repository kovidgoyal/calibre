/* This file is part of libmspack.
 * (C) 2003-2004 Stuart Caie.
 *
 * The LZX method was created by Jonathan Forbes and Tomi Poutanen, adapted
 * by Microsoft Corporation.
 *
 * libmspack is free software; you can redistribute it and/or modify it under
 * the terms of the GNU Lesser General Public License (LGPL) version 2.1
 *
 * For further details, see the file COPYING.LIB distributed with libmspack
 */

#pragma once

#include <sys/types.h>


/* LZX compression / decompression definitions */

/* some constants defined by the LZX specification */
#define LZX_MIN_MATCH                (2)
#define LZX_MAX_MATCH                (257)
#define LZX_NUM_CHARS                (256)
#define LZX_BLOCKTYPE_INVALID        (0)   /* also blocktypes 4-7 invalid */
#define LZX_BLOCKTYPE_VERBATIM       (1)
#define LZX_BLOCKTYPE_ALIGNED        (2)
#define LZX_BLOCKTYPE_UNCOMPRESSED   (3)
#define LZX_PRETREE_NUM_ELEMENTS     (20)
#define LZX_ALIGNED_NUM_ELEMENTS     (8)   /* aligned offset tree #elements */
#define LZX_NUM_PRIMARY_LENGTHS      (7)   /* this one missing from spec! */
#define LZX_NUM_SECONDARY_LENGTHS    (249) /* length tree #elements */

/* LZX huffman defines: tweak tablebits as desired */
#define LZX_PRETREE_MAXSYMBOLS  (LZX_PRETREE_NUM_ELEMENTS)
#define LZX_PRETREE_TABLEBITS   (6)
#define LZX_MAINTREE_MAXSYMBOLS (LZX_NUM_CHARS + 50*8)
#define LZX_MAINTREE_TABLEBITS  (12)
#define LZX_LENGTH_MAXSYMBOLS   (LZX_NUM_SECONDARY_LENGTHS+1)
#define LZX_LENGTH_TABLEBITS    (12)
#define LZX_ALIGNED_MAXSYMBOLS  (LZX_ALIGNED_NUM_ELEMENTS)
#define LZX_ALIGNED_TABLEBITS   (7)
#define LZX_LENTABLE_SAFETY (64)  /* table decoding overruns are allowed */

#define LZX_FRAME_SIZE (32768) /* the size of a frame in LZX */

struct lzxd_stream {
  struct mspack_system *sys;      /* I/O routines                            */
  struct mspack_file   *input;    /* input file handle                       */
  struct mspack_file   *output;   /* output file handle                      */

  off_t   offset;                 /* number of bytes actually output         */
  off_t   length;                 /* overall decompressed length of stream   */

  unsigned char *window;          /* decoding window                         */
  unsigned int   window_size;     /* window size                             */
  unsigned int   window_posn;     /* decompression offset within window      */
  unsigned int   frame_posn;      /* current frame offset within in window   */
  unsigned int   frame;           /* the number of 32kb frames processed     */
  unsigned int   reset_interval;  /* which frame do we reset the compressor? */

  unsigned int   R0, R1, R2;      /* for the LRU offset system               */
  unsigned int   block_length;    /* uncompressed length of this LZX block   */
  unsigned int   block_remaining; /* uncompressed bytes still left to decode */

  signed int     intel_filesize;  /* magic header value used for transform   */
  signed int     intel_curpos;    /* current offset in transform space       */

  unsigned char  intel_started;   /* has intel E8 decoding started?          */
  unsigned char  block_type;      /* type of the current block               */
  unsigned char  header_read;     /* have we started decoding at all yet?    */
  unsigned char  posn_slots;      /* how many posn slots in stream?          */
  unsigned char  input_end;       /* have we reached the end of input?       */

  int error;

  /* I/O buffering */
  unsigned char *inbuf, *i_ptr, *i_end, *o_ptr, *o_end;
  unsigned int  bit_buffer, bits_left, inbuf_size;

  /* huffman code lengths */
  unsigned char PRETREE_len  [LZX_PRETREE_MAXSYMBOLS  + LZX_LENTABLE_SAFETY];
  unsigned char MAINTREE_len [LZX_MAINTREE_MAXSYMBOLS + LZX_LENTABLE_SAFETY];
  unsigned char LENGTH_len   [LZX_LENGTH_MAXSYMBOLS   + LZX_LENTABLE_SAFETY];
  unsigned char ALIGNED_len  [LZX_ALIGNED_MAXSYMBOLS  + LZX_LENTABLE_SAFETY];

  /* huffman decoding tables */
  unsigned short PRETREE_table [(1 << LZX_PRETREE_TABLEBITS) +
				(LZX_PRETREE_MAXSYMBOLS * 2)];
  unsigned short MAINTREE_table[(1 << LZX_MAINTREE_TABLEBITS) +
				(LZX_MAINTREE_MAXSYMBOLS * 2)];
  unsigned short LENGTH_table  [(1 << LZX_LENGTH_TABLEBITS) +
				(LZX_LENGTH_MAXSYMBOLS * 2)];
  unsigned short ALIGNED_table [(1 << LZX_ALIGNED_TABLEBITS) +
				(LZX_ALIGNED_MAXSYMBOLS * 2)];

  /* this is used purely for doing the intel E8 transform */
  unsigned char  e8_buf[LZX_FRAME_SIZE];
};

/* allocates LZX decompression state for decoding the given stream.
 *
 * - returns NULL if window_bits is outwith the range 15 to 21 (inclusive).
 *
 * - uses system->alloc() to allocate memory
 *
 * - returns NULL if not enough memory
 *
 * - window_bits is the size of the LZX window, from 32Kb (15) to 2Mb (21).
 *
 * - reset_interval is how often the bitstream is reset, measured in
 *   multiples of 32Kb bytes output. For CAB LZX streams, this is always 0
 *   (does not occur).
 *
 * - input_buffer_size is how many bytes to use as an input bitstream buffer
 *
 * - output_length is the length in bytes of the entirely decompressed
 *   output stream, if known in advance. It is used to correctly perform
 *   the Intel E8 transformation, which must stop 6 bytes before the very
 *   end of the decompressed stream. It is not otherwise used or adhered
 *   to. If the full decompressed length is known in advance, set it here.
 *   If it is NOT known, use the value 0, and call lzxd_set_output_length()
 *   once it is known. If never set, 4 of the final 6 bytes of the output
 *   stream may be incorrect.
 */
extern struct lzxd_stream *lzxd_init(struct mspack_system *system,
				     struct mspack_file *input,
				     struct mspack_file *output,
				     int window_bits,
				     int reset_interval,
				     int input_buffer_size,
				     off_t output_length);

/* see description of output_length in lzxd_init() */
extern void lzxd_set_output_length(struct lzxd_stream *lzx,
				   off_t output_length);

/* decompresses, or decompresses more of, an LZX stream.
 *
 * - out_bytes of data will be decompressed and the function will return
 *   with an MSPACK_ERR_OK return code.
 *
 * - decompressing will stop as soon as out_bytes is reached. if the true
 *   amount of bytes decoded spills over that amount, they will be kept for
 *   a later invocation of lzxd_decompress().
 *
 * - the output bytes will be passed to the system->write() function given in
 *   lzxd_init(), using the output file handle given in lzxd_init(). More
 *   than one call may be made to system->write().
 *
 * - LZX will read input bytes as necessary using the system->read() function
 *   given in lzxd_init(), using the input file handle given in lzxd_init().
 *   This will continue until system->read() returns 0 bytes, or an error.
 *   input streams should convey an "end of input stream" by refusing to
 *   supply all the bytes that LZX asks for when they reach the end of the
 *   stream, rather than return an error code.
 *
 * - if an error code other than MSPACK_ERR_OK is returned, the stream should
 *   be considered unusable and lzxd_decompress() should not be called again
 *   on this stream.
 */
extern int lzxd_decompress(struct lzxd_stream *lzx, off_t out_bytes);

/* frees all state associated with an LZX data stream
 *
 * - calls system->free() using the system pointer given in lzxd_init()
 */
void lzxd_free(struct lzxd_stream *lzx);

