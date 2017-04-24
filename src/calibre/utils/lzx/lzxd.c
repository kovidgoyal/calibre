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

/* LZX decompression implementation */

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <mspack.h>
#include <system.h>
#include <lzxd.h>

/* Microsoft's LZX document and their implementation of the
 * com.ms.util.cab Java package do not concur.
 *
 * In the LZX document, there is a table showing the correlation between
 * window size and the number of position slots. It states that the 1MB
 * window = 40 slots and the 2MB window = 42 slots. In the implementation,
 * 1MB = 42 slots, 2MB = 50 slots. The actual calculation is 'find the
 * first slot whose position base is equal to or more than the required
 * window size'. This would explain why other tables in the document refer
 * to 50 slots rather than 42.
 *
 * The constant NUM_PRIMARY_LENGTHS used in the decompression pseudocode
 * is not defined in the specification.
 *
 * The LZX document does not state the uncompressed block has an
 * uncompressed length field. Where does this length field come from, so
 * we can know how large the block is? The implementation has it as the 24
 * bits following after the 3 blocktype bits, before the alignment
 * padding.
 *
 * The LZX document states that aligned offset blocks have their aligned
 * offset huffman tree AFTER the main and length trees. The implementation
 * suggests that the aligned offset tree is BEFORE the main and length
 * trees.
 *
 * The LZX document decoding algorithm states that, in an aligned offset
 * block, if an extra_bits value is 1, 2 or 3, then that number of bits
 * should be read and the result added to the match offset. This is
 * correct for 1 and 2, but not 3, where just a huffman symbol (using the
 * aligned tree) should be read.
 *
 * Regarding the E8 preprocessing, the LZX document states 'No translation
 * may be performed on the last 6 bytes of the input block'. This is
 * correct.  However, the pseudocode provided checks for the *E8 leader*
 * up to the last 6 bytes. If the leader appears between -10 and -7 bytes
 * from the end, this would cause the next four bytes to be modified, at
 * least one of which would be in the last 6 bytes, which is not allowed
 * according to the spec.
 *
 * The specification states that the huffman trees must always contain at
 * least one element. However, many CAB files contain blocks where the
 * length tree is completely empty (because there are no matches), and
 * this is expected to succeed.
 */


/* LZX decompressor input macros
 *
 * STORE_BITS        stores bitstream state in lzxd_stream structure
 * RESTORE_BITS      restores bitstream state from lzxd_stream structure
 * READ_BITS(var,n)  takes N bits from the buffer and puts them in var
 * ENSURE_BITS(n)    ensures there are at least N bits in the bit buffer.
 * PEEK_BITS(n)      extracts without removing N bits from the bit buffer
 * REMOVE_BITS(n)    removes N bits from the bit buffer
 *
 * These bit access routines work by using the area beyond the MSB and the
 * LSB as a free source of zeroes when shifting. This avoids having to
 * mask any bits. So we have to know the bit width of the bit buffer
 * variable.
 *
 * The bit buffer datatype should be at least 32 bits wide: it must be
 * possible to ENSURE_BITS(16), so it must be possible to add 16 new bits
 * to the bit buffer when the bit buffer already has 1 to 15 bits left.
 */

#if HAVE_LIMITS_H
# include <limits.h>
#endif
#ifndef CHAR_BIT
# define CHAR_BIT (8)
#endif
#define BITBUF_WIDTH (sizeof(bit_buffer) * CHAR_BIT)

#define STORE_BITS do {                                                 \
  lzx->i_ptr      = i_ptr;                                              \
  lzx->i_end      = i_end;                                              \
  lzx->bit_buffer = bit_buffer;                                         \
  lzx->bits_left  = bits_left;                                          \
} while (0)

#define RESTORE_BITS do {                                               \
  i_ptr      = lzx->i_ptr;                                              \
  i_end      = lzx->i_end;                                              \
  bit_buffer = lzx->bit_buffer;                                         \
  bits_left  = lzx->bits_left;                                          \
} while (0)

#define ENSURE_BITS(nbits)                                              \
  while (bits_left < (nbits)) {                                         \
    if (i_ptr >= i_end) {                                               \
      if (lzxd_read_input(lzx)) return lzx->error;                      \
      i_ptr = lzx->i_ptr;                                               \
      i_end = lzx->i_end;                                               \
    }                                                                   \
    bit_buffer |= ((i_ptr[1] << 8) | i_ptr[0])                          \
                  << (BITBUF_WIDTH - 16 - bits_left);                   \
    bits_left  += 16;                                                   \
    i_ptr      += 2;                                                    \
  }

#define PEEK_BITS(nbits) (bit_buffer >> (BITBUF_WIDTH - (nbits)))

#define REMOVE_BITS(nbits) ((bit_buffer <<= (nbits)), (bits_left -= (nbits)))

#define READ_BITS(val, nbits) do {                                      \
  ENSURE_BITS(nbits);                                                   \
  (val) = PEEK_BITS(nbits);                                             \
  REMOVE_BITS(nbits);                                                   \
} while (0)

static int lzxd_read_input(struct lzxd_stream *lzx) {
  int read = lzx->sys->read(lzx->input, &lzx->inbuf[0], (int)lzx->inbuf_size);
  if (read < 0) return lzx->error = MSPACK_ERR_READ;

  /* huff decode's ENSURE_BYTES(16) might overrun the input stream, even
   * if those bits aren't used, so fake 2 more bytes */
  if (read == 0) {
    if (lzx->input_end) {
      D(("out of input bytes"))
      return lzx->error = MSPACK_ERR_READ;
    }
    else {
      read = 2;
      lzx->inbuf[0] = lzx->inbuf[1] = 0;
      lzx->input_end = 1;
    }
  }

  lzx->i_ptr = &lzx->inbuf[0];
  lzx->i_end = &lzx->inbuf[read];

  return MSPACK_ERR_OK;
}

/* Huffman decoding macros */

/* READ_HUFFSYM(tablename, var) decodes one huffman symbol from the
 * bitstream using the stated table and puts it in var.
 */
#define READ_HUFFSYM(tbl, var) do {                                     \
  /* huffman symbols can be up to 16 bits long */                       \
  ENSURE_BITS(16);                                                      \
  /* immediate table lookup of [tablebits] bits of the code */          \
  sym = lzx->tbl##_table[PEEK_BITS(LZX_##tbl##_TABLEBITS)];             \
  /* is the symbol is longer than [tablebits] bits? (i=node index) */   \
  if (sym >= LZX_##tbl##_MAXSYMBOLS) {                                  \
    /* decode remaining bits by tree traversal */                       \
    i = 1 << (BITBUF_WIDTH - LZX_##tbl##_TABLEBITS);                    \
    do {                                                                \
      /* one less bit. error if we run out of bits before decode */     \
      i >>= 1;                                                          \
      if (i == 0) {                                                     \
        D(("out of bits in huffman decode"))                            \
        return lzx->error = MSPACK_ERR_DECRUNCH;                        \
      }                                                                 \
      /* double node index and add 0 (left branch) or 1 (right) */      \
      sym <<= 1; sym |= (bit_buffer & i) ? 1 : 0;                       \
      /* hop to next node index / decoded symbol */                     \
      sym = lzx->tbl##_table[sym];                                      \
      /* while we are still in node indicies, not decoded symbols */    \
    } while (sym >= LZX_##tbl##_MAXSYMBOLS);                            \
  }                                                                     \
  /* result */                                                          \
  (var) = sym;                                                          \
  /* look up the code length of that symbol and discard those bits */   \
  i = lzx->tbl##_len[sym];                                              \
  REMOVE_BITS(i);                                                       \
} while (0)

/* BUILD_TABLE(tbl) builds a huffman lookup table from code lengths */
#define BUILD_TABLE(tbl)                                                \
  if (make_decode_table(LZX_##tbl##_MAXSYMBOLS, LZX_##tbl##_TABLEBITS,  \
			&lzx->tbl##_len[0], &lzx->tbl##_table[0]))      \
  {                                                                     \
    D(("failed to build %s table", #tbl))                               \
    return lzx->error = MSPACK_ERR_DECRUNCH;                            \
  }

/* make_decode_table(nsyms, nbits, length[], table[])
 *
 * This function was coded by David Tritscher. It builds a fast huffman
 * decoding table from a canonical huffman code lengths table.
 *
 * nsyms  = total number of symbols in this huffman tree.
 * nbits  = any symbols with a code length of nbits or less can be decoded
 *          in one lookup of the table.
 * length = A table to get code lengths from [0 to syms-1]
 * table  = The table to fill up with decoded symbols and pointers.
 *
 * Returns 0 for OK or 1 for error
 */

static int make_decode_table(unsigned int nsyms, unsigned int nbits,
			     unsigned char *length, unsigned short *table)
{
  register unsigned short sym;
  register unsigned int leaf, fill;
  register unsigned char bit_num;
  unsigned int pos         = 0; /* the current position in the decode table */
  unsigned int table_mask  = 1 << nbits;
  unsigned int bit_mask    = table_mask >> 1; /* don't do 0 length codes */
  unsigned int next_symbol = bit_mask; /* base of allocation for long codes */

  /* fill entries for codes short enough for a direct mapping */
  for (bit_num = 1; bit_num <= nbits; bit_num++) {
    for (sym = 0; sym < nsyms; sym++) {
      if (length[sym] != bit_num) continue;
      leaf = pos;
      if((pos += bit_mask) > table_mask) return 1; /* table overrun */
      /* fill all possible lookups of this symbol with the symbol itself */
      for (fill = bit_mask; fill-- > 0;) table[leaf++] = sym;
    }
    bit_mask >>= 1;
  }

  /* full table already? */
  if (pos == table_mask) return 0;

  /* clear the remainder of the table */
  for (sym = pos; sym < table_mask; sym++) table[sym] = 0xFFFF;

  /* allow codes to be up to nbits+16 long, instead of nbits */
  pos <<= 16;
  table_mask <<= 16;
  bit_mask = 1 << 15;

  for (bit_num = nbits+1; bit_num <= 16; bit_num++) {
    for (sym = 0; sym < nsyms; sym++) {
      if (length[sym] != bit_num) continue;

      leaf = pos >> 16;
      for (fill = 0; fill < bit_num - nbits; fill++) {
	/* if this path hasn't been taken yet, 'allocate' two entries */
	if (table[leaf] == 0xFFFF) {
	  table[(next_symbol << 1)] = 0xFFFF;
	  table[(next_symbol << 1) + 1] = 0xFFFF;
	  table[leaf] = next_symbol++;
	}
	/* follow the path and select either left or right for next bit */
	leaf = table[leaf] << 1;
	if ((pos >> (15-fill)) & 1) leaf++;
      }
      table[leaf] = sym;

      if ((pos += bit_mask) > table_mask) return 1; /* table overflow */
    }
    bit_mask >>= 1;
  }

  /* full table? */
  if (pos == table_mask) return 0;

  /* either erroneous table, or all elements are 0 - let's find out. */
  for (sym = 0; sym < nsyms; sym++) if (length[sym]) return 1;
  return 0;
}


/* READ_LENGTHS(tablename, first, last) reads in code lengths for symbols
 * first to last in the given table. The code lengths are stored in their
 * own special LZX way.
 */
#define READ_LENGTHS(tbl, first, last) do {                            \
  STORE_BITS;                                                          \
  if (lzxd_read_lens(lzx, &lzx->tbl##_len[0], (first),                 \
    (unsigned int)(last))) return lzx->error;                          \
  RESTORE_BITS;                                                        \
} while (0)

static int lzxd_read_lens(struct lzxd_stream *lzx, unsigned char *lens,
			  unsigned int first, unsigned int last)
{
  /* bit buffer and huffman symbol decode variables */
  register unsigned int bit_buffer;
  register int bits_left, i;
  register unsigned short sym;
  unsigned char *i_ptr, *i_end;

  unsigned int x, y;
  int z;

  RESTORE_BITS;
  
  /* read lengths for pretree (20 symbols, lengths stored in fixed 4 bits) */
  for (x = 0; x < 20; x++) {
    READ_BITS(y, 4);
    lzx->PRETREE_len[x] = y;
  }
  BUILD_TABLE(PRETREE);

  for (x = first; x < last; ) {
    READ_HUFFSYM(PRETREE, z);
    if (z == 17) {
      /* code = 17, run of ([read 4 bits]+4) zeros */
      READ_BITS(y, 4); y += 4;
      while (y--) lens[x++] = 0;
    }
    else if (z == 18) {
      /* code = 18, run of ([read 5 bits]+20) zeros */
      READ_BITS(y, 5); y += 20;
      while (y--) lens[x++] = 0;
    }
    else if (z == 19) {
      /* code = 19, run of ([read 1 bit]+4) [read huffman symbol] */
      READ_BITS(y, 1); y += 4;
      READ_HUFFSYM(PRETREE, z);
      z = lens[x] - z; if (z < 0) z += 17;
      while (y--) lens[x++] = z;
    }
    else {
      /* code = 0 to 16, delta current length entry */
      z = lens[x] - z; if (z < 0) z += 17;
      lens[x++] = z;
    }
  }

  STORE_BITS;

  return MSPACK_ERR_OK;
}

/* LZX static data tables:
 *
 * LZX uses 'position slots' to represent match offsets.  For every match,
 * a small 'position slot' number and a small offset from that slot are
 * encoded instead of one large offset.
 *
 * position_base[] is an index to the position slot bases
 *
 * extra_bits[] states how many bits of offset-from-base data is needed.
 */
static unsigned int  position_base[51];
static unsigned char extra_bits[51];

static void lzxd_static_init(void) {
  int i, j;

  for (i = 0, j = 0; i < 50; i += 2) {
    extra_bits[i]   = j; /* 0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7... */
    extra_bits[i+1] = j;
    if ((i != 0) && (j < 17)) j++; /* 0,0,1,2,3,4...15,16,17,17,17,17... */
  }
  extra_bits[50] = 17;

  for (i = 0, j = 0; i < 51; i++) {
    position_base[i] = j; /* 0,1,2,3,4,6,8,12,16,24,32,... */
    j += 1 << extra_bits[i]; /* 1,1,1,1,2,2,4,4,8,8,16,16,32,32,... */
  }
}

static void lzxd_reset_state(struct lzxd_stream *lzx) {
  int i;

  lzx->R0              = 1;
  lzx->R1              = 1;
  lzx->R2              = 1;
  lzx->header_read     = 0;
  lzx->block_remaining = 0;
  lzx->block_type      = LZX_BLOCKTYPE_INVALID;

  /* initialise tables to 0 (because deltas will be applied to them) */
  for (i = 0; i < LZX_MAINTREE_MAXSYMBOLS; i++) lzx->MAINTREE_len[i] = 0;
  for (i = 0; i < LZX_LENGTH_MAXSYMBOLS; i++)   lzx->LENGTH_len[i]   = 0;
}

/*-------- main LZX code --------*/

struct lzxd_stream *lzxd_init(struct mspack_system *system,
			      struct mspack_file *input,
			      struct mspack_file *output,
			      int window_bits,
			      int reset_interval,
			      int input_buffer_size,
			      off_t output_length)
{
  unsigned int window_size = 1 << window_bits;
  struct lzxd_stream *lzx;

  if (!system) return NULL;

  /* LZX supports window sizes of 2^15 (32Kb) through 2^21 (2Mb) */
  if (window_bits < 15 || window_bits > 21) return NULL;

  input_buffer_size = (input_buffer_size + 1) & -2;
  if (!input_buffer_size) return NULL;

  /* initialise static data */
  lzxd_static_init();

  /* allocate decompression state */
  if (!(lzx = system->alloc(system, sizeof(struct lzxd_stream)))) {
    return NULL;
  }

  /* allocate decompression window and input buffer */
  lzx->window = system->alloc(system, (size_t) window_size);
  lzx->inbuf  = system->alloc(system, (size_t) input_buffer_size);
  if (!lzx->window || !lzx->inbuf) {
    system->free(lzx->window);
    system->free(lzx->inbuf);
    system->free(lzx);
    return NULL;
  }

  /* initialise decompression state */
  lzx->sys             = system;
  lzx->input           = input;
  lzx->output          = output;
  lzx->offset          = 0;
  lzx->length          = output_length;

  lzx->inbuf_size      = input_buffer_size;
  lzx->window_size     = 1 << window_bits;
  lzx->window_posn     = 0;
  lzx->frame_posn      = 0;
  lzx->frame           = 0;
  lzx->reset_interval  = reset_interval;
  lzx->intel_filesize  = 0;
  lzx->intel_curpos    = 0;

  /* window bits:    15  16  17  18  19  20  21
   * position slots: 30  32  34  36  38  42  50  */
  lzx->posn_slots      = ((window_bits == 21) ? 50 :
			  ((window_bits == 20) ? 42 : (window_bits << 1)));
  lzx->intel_started   = 0;
  lzx->input_end       = 0;

  lzx->error = MSPACK_ERR_OK;

  lzx->i_ptr = lzx->i_end = &lzx->inbuf[0];
  lzx->o_ptr = lzx->o_end = &lzx->e8_buf[0];
  lzx->bit_buffer = lzx->bits_left = 0;

  lzxd_reset_state(lzx);
  return lzx;
}

void lzxd_set_output_length(struct lzxd_stream *lzx, off_t out_bytes) {
  if (lzx) lzx->length = out_bytes;
}

int lzxd_decompress(struct lzxd_stream *lzx, off_t out_bytes) {
  /* bitstream reading and huffman variables */
  register unsigned int bit_buffer;
  register int bits_left, i=0;
  register unsigned short sym;
  unsigned char *i_ptr, *i_end;

  int match_length, length_footer, extra, verbatim_bits, bytes_todo;
  int this_run, main_element, aligned_bits, j;
  unsigned char *window, *runsrc, *rundest, buf[12];
  unsigned int frame_size=0, end_frame, match_offset, window_posn;
  unsigned int R0, R1, R2;

  /* easy answers */
  if (!lzx || (out_bytes < 0)) return MSPACK_ERR_ARGS;
  if (lzx->error) return lzx->error;

  /* flush out any stored-up bytes before we begin */
  i = lzx->o_end - lzx->o_ptr;
  if ((off_t) i > out_bytes) i = (int) out_bytes;
  if (i) {
    if (lzx->sys->write(lzx->output, lzx->o_ptr, i) != i) {
      return lzx->error = MSPACK_ERR_WRITE;
    }
    lzx->o_ptr  += i;
    lzx->offset += i;
    out_bytes   -= i;
  }
  if (out_bytes == 0) return MSPACK_ERR_OK;

  /* restore local state */
  RESTORE_BITS;
  window = lzx->window;
  window_posn = lzx->window_posn;
  R0 = lzx->R0;
  R1 = lzx->R1;
  R2 = lzx->R2;

  end_frame = (unsigned int)((lzx->offset + out_bytes) / LZX_FRAME_SIZE) + 1;

  while (lzx->frame < end_frame) {
    /* have we reached the reset interval? (if there is one?) */
    if (lzx->reset_interval && ((lzx->frame % lzx->reset_interval) == 0)) {
      if (lzx->block_remaining) {
	D(("%d bytes remaining at reset interval", lzx->block_remaining))
	return lzx->error = MSPACK_ERR_DECRUNCH;
      }

      /* re-read the intel header and reset the huffman lengths */
      lzxd_reset_state(lzx);
    }

    /* read header if necessary */
    if (!lzx->header_read) {
      /* read 1 bit. if bit=0, intel filesize = 0.
       * if bit=1, read intel filesize (32 bits) */
      j = 0; READ_BITS(i, 1); if (i) { READ_BITS(i, 16); READ_BITS(j, 16); }
      lzx->intel_filesize = (i << 16) | j;
      lzx->header_read = 1;
    } 

    /* calculate size of frame: all frames are 32k except the final frame
     * which is 32kb or less. this can only be calculated when lzx->length
     * has been filled in. */
    frame_size = LZX_FRAME_SIZE;
    if (lzx->length && (lzx->length - lzx->offset) < (off_t)frame_size) {
      frame_size = lzx->length - lzx->offset;
    }

    /* decode until one more frame is available */
    bytes_todo = lzx->frame_posn + frame_size - window_posn;
    while (bytes_todo > 0) {
      /* initialise new block, if one is needed */
      if (lzx->block_remaining == 0) {
	/* realign if previous block was an odd-sized UNCOMPRESSED block */
	if ((lzx->block_type == LZX_BLOCKTYPE_UNCOMPRESSED) &&
	    (lzx->block_length & 1))
	{
	  if (i_ptr == i_end) {
	    if (lzxd_read_input(lzx)) return lzx->error;
	    i_ptr = lzx->i_ptr;
	    i_end = lzx->i_end;
	  }
	  i_ptr++;
	}

	/* read block type (3 bits) and block length (24 bits) */
	READ_BITS(lzx->block_type, 3);
	READ_BITS(i, 16); READ_BITS(j, 8);
	lzx->block_remaining = lzx->block_length = (i << 8) | j;
	/*D(("new block t%d len %u", lzx->block_type, lzx->block_length))*/

	/* read individual block headers */
	switch (lzx->block_type) {
	case LZX_BLOCKTYPE_ALIGNED:
	  /* read lengths of and build aligned huffman decoding tree */
	  for (i = 0; i < 8; i++) { READ_BITS(j, 3); lzx->ALIGNED_len[i] = j; }
	  BUILD_TABLE(ALIGNED);
	  /* no break -- rest of aligned header is same as verbatim */
	case LZX_BLOCKTYPE_VERBATIM:
	  /* read lengths of and build main huffman decoding tree */
	  READ_LENGTHS(MAINTREE, 0, 256);
	  READ_LENGTHS(MAINTREE, 256, LZX_NUM_CHARS + (lzx->posn_slots << 3));
	  BUILD_TABLE(MAINTREE);
	  /* if the literal 0xE8 is anywhere in the block... */
	  if (lzx->MAINTREE_len[0xE8] != 0) lzx->intel_started = 1;
	  /* read lengths of and build lengths huffman decoding tree */
	  READ_LENGTHS(LENGTH, 0, LZX_NUM_SECONDARY_LENGTHS);
	  BUILD_TABLE(LENGTH);
	  break;

	case LZX_BLOCKTYPE_UNCOMPRESSED:
	  /* because we can't assume otherwise */
	  lzx->intel_started = 1;

	  /* read 1-16 (not 0-15) bits to align to bytes */
	  ENSURE_BITS(16);
	  if (bits_left > 16) i_ptr -= 2;
	  bits_left = 0; bit_buffer = 0;

	  /* read 12 bytes of stored R0 / R1 / R2 values */
	  for (rundest = &buf[0], i = 0; i < 12; i++) {
	    if (i_ptr == i_end) {
	      if (lzxd_read_input(lzx)) return lzx->error;
	      i_ptr = lzx->i_ptr;
	      i_end = lzx->i_end;
	    }
	    *rundest++ = *i_ptr++;
	  }
	  R0 = buf[0] | (buf[1] << 8) | (buf[2]  << 16) | (buf[3]  << 24);
	  R1 = buf[4] | (buf[5] << 8) | (buf[6]  << 16) | (buf[7]  << 24);
	  R2 = buf[8] | (buf[9] << 8) | (buf[10] << 16) | (buf[11] << 24);
	  break;

	default:
	  D(("bad block type"))
	  return lzx->error = MSPACK_ERR_DECRUNCH;
	}
      }

      /* decode more of the block:
       * run = min(what's available, what's needed) */
      this_run = lzx->block_remaining;
      if (this_run > bytes_todo) this_run = bytes_todo;

      /* assume we decode exactly this_run bytes, for now */
      bytes_todo           -= this_run;
      lzx->block_remaining -= this_run;

      /* decode at least this_run bytes */
      switch (lzx->block_type) {
      case LZX_BLOCKTYPE_VERBATIM:
	while (this_run > 0) {
	  READ_HUFFSYM(MAINTREE, main_element);
	  if (main_element < LZX_NUM_CHARS) {
	    /* literal: 0 to LZX_NUM_CHARS-1 */
	    window[window_posn++] = main_element;
	    this_run--;
	  }
	  else {
	    /* match: LZX_NUM_CHARS + ((slot<<3) | length_header (3 bits)) */
	    main_element -= LZX_NUM_CHARS;

	    /* get match length */
	    match_length = main_element & LZX_NUM_PRIMARY_LENGTHS;
	    if (match_length == LZX_NUM_PRIMARY_LENGTHS) {
	      READ_HUFFSYM(LENGTH, length_footer);
	      match_length += length_footer;
	    }
	    match_length += LZX_MIN_MATCH;
	  
	    /* get match offset */
	    switch ((match_offset = (main_element >> 3))) {
	    case 0: match_offset = R0;                                  break;
	    case 1: match_offset = R1; R1=R0;        R0 = match_offset; break;
	    case 2: match_offset = R2; R2=R0;        R0 = match_offset; break;
	    case 3: match_offset = 1;  R2=R1; R1=R0; R0 = match_offset; break;
	    default:
	      extra = extra_bits[match_offset];
	      READ_BITS(verbatim_bits, extra);
	      match_offset = position_base[match_offset] - 2 + verbatim_bits;
	      R2 = R1; R1 = R0; R0 = match_offset;
	    }

	    if ((window_posn + match_length) > lzx->window_size) {
	      D(("match ran over window wrap"))
	      return lzx->error = MSPACK_ERR_DECRUNCH;
	    }
	    
	    /* copy match */
	    rundest = &window[window_posn];
	    i = match_length;
	    /* does match offset wrap the window? */
	    if (match_offset > window_posn) {
	      /* j = length from match offset to end of window */
	      j = match_offset - window_posn;
	      if (j > (int) lzx->window_size) {
		D(("match offset beyond window boundaries"))
		return lzx->error = MSPACK_ERR_DECRUNCH;
	      }
	      runsrc = &window[lzx->window_size - j];
	      if (j < i) {
		/* if match goes over the window edge, do two copy runs */
		i -= j; while (j-- > 0) *rundest++ = *runsrc++;
		runsrc = window;
	      }
	      while (i-- > 0) *rundest++ = *runsrc++;
	    }
	    else {
	      runsrc = rundest - match_offset;
	      while (i-- > 0) *rundest++ = *runsrc++;
	    }

	    this_run    -= match_length;
	    window_posn += match_length;
	  }
	} /* while (this_run > 0) */
	break;

      case LZX_BLOCKTYPE_ALIGNED:
	while (this_run > 0) {
	  READ_HUFFSYM(MAINTREE, main_element);
	  if (main_element < LZX_NUM_CHARS) {
	    /* literal: 0 to LZX_NUM_CHARS-1 */
	    window[window_posn++] = main_element;
	    this_run--;
	  }
	  else {
	    /* match: LZX_NUM_CHARS + ((slot<<3) | length_header (3 bits)) */
	    main_element -= LZX_NUM_CHARS;

	    /* get match length */
	    match_length = main_element & LZX_NUM_PRIMARY_LENGTHS;
	    if (match_length == LZX_NUM_PRIMARY_LENGTHS) {
	      READ_HUFFSYM(LENGTH, length_footer);
	      match_length += length_footer;
	    }
	    match_length += LZX_MIN_MATCH;

	    /* get match offset */
	    switch ((match_offset = (main_element >> 3))) {
	    case 0: match_offset = R0;                             break;
	    case 1: match_offset = R1; R1 = R0; R0 = match_offset; break;
	    case 2: match_offset = R2; R2 = R0; R0 = match_offset; break;
	    default:
	      extra = extra_bits[match_offset];
	      match_offset = position_base[match_offset] - 2;
	      if (extra > 3) {
		/* verbatim and aligned bits */
		extra -= 3;
		READ_BITS(verbatim_bits, extra);
		match_offset += (verbatim_bits << 3);
		READ_HUFFSYM(ALIGNED, aligned_bits);
		match_offset += aligned_bits;
	      }
	      else if (extra == 3) {
		/* aligned bits only */
		READ_HUFFSYM(ALIGNED, aligned_bits);
		match_offset += aligned_bits;
	      }
	      else if (extra > 0) { /* extra==1, extra==2 */
		/* verbatim bits only */
		READ_BITS(verbatim_bits, extra);
		match_offset += verbatim_bits;
	      }
	      else /* extra == 0 */ {
		/* ??? not defined in LZX specification! */
		match_offset = 1;
	      }
	      /* update repeated offset LRU queue */
	      R2 = R1; R1 = R0; R0 = match_offset;
	    }

	    if ((window_posn + match_length) > lzx->window_size) {
	      D(("match ran over window wrap"))
	      return lzx->error = MSPACK_ERR_DECRUNCH;
	    }

	    /* copy match */
	    rundest = &window[window_posn];
	    i = match_length;
	    /* does match offset wrap the window? */
	    if (match_offset > window_posn) {
	      /* j = length from match offset to end of window */
	      j = match_offset - window_posn;
	      if (j > (int) lzx->window_size) {
		D(("match offset beyond window boundaries"))
		return lzx->error = MSPACK_ERR_DECRUNCH;
	      }
	      runsrc = &window[lzx->window_size - j];
	      if (j < i) {
		/* if match goes over the window edge, do two copy runs */
		i -= j; while (j-- > 0) *rundest++ = *runsrc++;
		runsrc = window;
	      }
	      while (i-- > 0) *rundest++ = *runsrc++;
	    }
	    else {
	      runsrc = rundest - match_offset;
	      while (i-- > 0) *rundest++ = *runsrc++;
	    }

	    this_run    -= match_length;
	    window_posn += match_length;
	  }
	} /* while (this_run > 0) */
	break;

      case LZX_BLOCKTYPE_UNCOMPRESSED:
	/* as this_run is limited not to wrap a frame, this also means it
	 * won't wrap the window (as the window is a multiple of 32k) */
	rundest = &window[window_posn];
	window_posn += this_run;
	while (this_run > 0) {
	  if ((i = i_end - i_ptr)) {
	    if (i > this_run) i = this_run;
	    lzx->sys->copy(i_ptr, rundest, (size_t) i);
	    rundest  += i;
	    i_ptr    += i;
	    this_run -= i;
	  }
	  else {
	    if (lzxd_read_input(lzx)) return lzx->error;
	    i_ptr = lzx->i_ptr;
	    i_end = lzx->i_end;
	  }
	}
	break;

      default:
        D(("Default Here."));
	return lzx->error = MSPACK_ERR_DECRUNCH; /* might as well */
      }

      /* did the final match overrun our desired this_run length? */
      if (this_run < 0) {
	if ((unsigned int)(-this_run) > lzx->block_remaining) {
	  D(("overrun went past end of block by %d (%d remaining)",
	     -this_run, lzx->block_remaining ))
	  return lzx->error = MSPACK_ERR_DECRUNCH;
	}
	lzx->block_remaining -= -this_run;
      }
    } /* while (bytes_todo > 0) */

    /* streams don't extend over frame boundaries */
    if ((window_posn - lzx->frame_posn) != frame_size) {
      D(("decode beyond output frame limits! %d != %d",
	 window_posn - lzx->frame_posn, frame_size))
     /* Ignored */
#if 0
      	return lzx->error = MSPACK_ERR_DECRUNCH; 
#endif
    }

    /* re-align input bitstream */
    if (bits_left > 0) ENSURE_BITS(16);
    if (bits_left & 15) REMOVE_BITS(bits_left & 15);

    /* check that we've used all of the previous frame first */
    if (lzx->o_ptr != lzx->o_end) {
      D(("%d avail bytes, new %d frame", lzx->o_end-lzx->o_ptr, frame_size))
      return lzx->error = MSPACK_ERR_DECRUNCH;
    }

    /* does this intel block _really_ need decoding? */
    if (lzx->intel_started && lzx->intel_filesize &&
	(lzx->frame <= 32768) && (frame_size > 10))
    {
      unsigned char *data    = &lzx->e8_buf[0];
      unsigned char *dataend = &lzx->e8_buf[frame_size - 10];
      signed int curpos      = lzx->intel_curpos;
      signed int filesize    = lzx->intel_filesize;
      signed int abs_off, rel_off;

      /* copy e8 block to the e8 buffer and tweak if needed */
      lzx->o_ptr = data;
      lzx->sys->copy(&lzx->window[lzx->frame_posn], data, frame_size);

      while (data < dataend) {
	if (*data++ != 0xE8) { curpos++; continue; }
	abs_off = data[0] | (data[1]<<8) | (data[2]<<16) | (data[3]<<24);
	if ((abs_off >= -curpos) && (abs_off < filesize)) {
	  rel_off = (abs_off >= 0) ? abs_off - curpos : abs_off + filesize;
	  data[0] = (unsigned char) rel_off;
	  data[1] = (unsigned char) (rel_off >> 8);
	  data[2] = (unsigned char) (rel_off >> 16);
	  data[3] = (unsigned char) (rel_off >> 24);
	}
	data += 4;
	curpos += 5;
      }
      lzx->intel_curpos += frame_size;
    }
    else {
      lzx->o_ptr = &lzx->window[lzx->frame_posn];
      if (lzx->intel_filesize) lzx->intel_curpos += frame_size;
    }
    lzx->o_end = &lzx->o_ptr[frame_size];

    /* write a frame */
    i = (out_bytes < (off_t)frame_size) ? (unsigned int)out_bytes : frame_size;
    if (lzx->sys->write(lzx->output, lzx->o_ptr, i) != i) {
      return lzx->error = MSPACK_ERR_WRITE;
    }
    lzx->o_ptr  += i;
    lzx->offset += i;
    out_bytes   -= i;

    /* advance frame start position */
    lzx->frame_posn += frame_size;
    lzx->frame++;

    /* wrap window / frame position pointers */
    if (window_posn == lzx->window_size)     window_posn = 0;
    if (lzx->frame_posn == lzx->window_size) lzx->frame_posn = 0;

  } /* while (lzx->frame < end_frame) */

  if (out_bytes) {
    D(("bytes left to output"))
    return lzx->error = MSPACK_ERR_DECRUNCH;
  }

  /* store local state */
  STORE_BITS;
  lzx->window_posn = window_posn;
  lzx->R0 = R0;
  lzx->R1 = R1;
  lzx->R2 = R2;

  return MSPACK_ERR_OK;
}

void lzxd_free(struct lzxd_stream *lzx) {
  struct mspack_system *sys;
  if (lzx) {
    sys = lzx->sys;
    sys->free(lzx->inbuf);
    sys->free(lzx->window);
    sys->free(lzx);
  }
}
