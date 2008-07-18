/*--[lzxglue.c]----------------------------------------------------------------
 | Copyright (C) 2004 DRS
 |
 | This file is part of the "openclit" library for processing .LIT files.
 |
 | "Openclit" is free software; you can redistribute it and/or modify
 | it under the terms of the GNU General Public License as published by
 | the Free Software Foundation; either version 2 of the License, or
 | (at your option) any later version.
 |
 | This program is distributed in the hope that it will be useful,
 | but WITHOUT ANY WARRANTY; without even the implied warranty of
 | MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 | GNU General Public License for more details.
 |
 | You should have received a copy of the GNU General Public License
 | along with this program; if not, write to the Free Software
 | Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 |
 | The GNU General Public License may also be available at the following
 | URL: http://www.gnu.org/licenses/gpl.html
*/

/* This provides a "glue" between Stuart Caie's libmspack library and the
 * Openclit calls to the earlier LZX library.  
 * 
 * This way, I should be able to use the files unmodified.
 */
#include <stdio.h>
#include <stdlib.h>
#include "litlib.h"
#include "mspack.h"
#include "lzx.h"

typedef struct memory_file
{
    unsigned int magic;	/* 0xB5 */
    void * buffer;
    int total_bytes;
    int current_bytes;
} memory_file;


void * glue_alloc(struct mspack_system *this, size_t bytes)
{
    void * p;
    p = (void *)malloc(bytes);
    if (p == NULL)  {
        lit_error(ERR_R|ERR_LIBC,"Malloc(%d) failed!", bytes); 
    }
    return p;
}

void glue_free(void * p)
{
    free(p);
}

void glue_copy(void *src, void *dest, size_t bytes)
{
    memcpy(dest, src, bytes);
}

struct mspack_file * glue_open(struct mspack_system *this, char *filename,
    int mode)
{
    lit_error(0,"MSPACK_OPEN unsupported!");
    return NULL;
}

void glue_close(struct mspack_file * file) {
    return;
}


int glue_read(struct mspack_file * file, void * buffer, int bytes)
{
    memory_file * mem;
    int remaining;

    mem = (memory_file *)file;
    if (mem->magic != 0xB5) return -1;
  
    remaining = mem->total_bytes - mem->current_bytes;
    if (!remaining)  return 0;
    if (bytes > remaining) bytes = remaining;
    memcpy(buffer, (unsigned char *)mem->buffer+mem->current_bytes, bytes);
    mem->current_bytes += bytes;
    return bytes;
}

int glue_write(struct mspack_file * file, void * buffer, int bytes)
{
    memory_file * mem;
    int remaining;

    mem = (memory_file *)file;
    if (mem->magic != 0xB5) return -1;
  
    remaining = mem->total_bytes - mem->current_bytes;
    if (!remaining)  return 0;
    if (bytes > remaining) { 
        lit_error(0,"MSPACK_READ tried to write %d bytes, only %d left.",
            bytes, remaining);
        bytes = remaining;
    }
    memcpy((unsigned char *)mem->buffer+mem->current_bytes, buffer, bytes);
    mem->current_bytes += bytes;
    return bytes;
}

struct mspack_system lzxglue_system = 
{
    glue_open, 
    glue_close,
    glue_read,   /* Read */
    glue_write,  /* Write */
    NULL,   /* Seek */
    NULL,   /* Tell */
    NULL,   /* Message */
    glue_alloc,
    glue_free,
    glue_copy,
    NULL    /* Termination */
};

int LZXwindow;
struct lzxd_stream * lzx_stream = NULL;


/* Can't really init here,don't know enough */
int LZXinit(int window) 
{
    LZXwindow = window;
    lzx_stream = NULL;

    return 0;
}

/* Doesn't exist. Oh well, reinitialize state every time anyway */
void LZXreset(void)
{
    return;
}

int LZXdecompress(unsigned char *inbuf, unsigned char *outbuf, 
    unsigned int inlen, unsigned int outlen)
{
    int err;
    memory_file source;
    memory_file dest;

    source.magic = 0xB5;
    source.buffer = inbuf;
    source.current_bytes = 0;
    source.total_bytes = inlen;

    dest.magic = 0xB5;
    dest.buffer = outbuf;
    dest.current_bytes = 0;
    dest.total_bytes = outlen;
    
    lzx_stream = lzxd_init(&lzxglue_system, (struct mspack_file *)&source,
        (struct mspack_file *)&dest, LZXwindow, 
        0x7fff /* Never reset, I do it */, 4096, outlen);
    err = -1;
    if (lzx_stream) err = lzxd_decompress(lzx_stream, outlen);

    lzxd_free(lzx_stream);
    lzx_stream = NULL;
    return err;
}
