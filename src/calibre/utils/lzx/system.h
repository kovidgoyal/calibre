/* This file is part of libmspack.
 * (C) 2003-2004 Stuart Caie.
 *
 * libmspack is free software; you can redistribute it and/or modify it under
 * the terms of the GNU Lesser General Public License (LGPL) version 2.1
 *
 * For further details, see the file COPYING.LIB distributed with libmspack
 */

#pragma once

#ifdef _MSC_VER
#define inline
#endif

#ifdef DEBUG
# include <stdio.h>
# define D(x) do { printf("%s:%d (%s) ",__FILE__, __LINE__, __FUNCTION__); \
                   printf x ; fputc('\n', stdout); fflush(stdout);} while (0);
#else
# define D(x)
#endif

/* endian-neutral reading of little-endian data */
#define __egi32(a,n) ( (((a)[n+3]) << 24) | (((a)[n+2]) << 16) | \
		       (((a)[n+1]) <<  8) |  ((a)[n+0])        )
#define EndGetI64(a) ((((unsigned long long int) __egi32(a,4)) << 32) | \
		      ((unsigned int) __egi32(a,0)))
#define EndGetI32(a) __egi32(a,0)
#define EndGetI16(a) ((((a)[1])<<8)|((a)[0]))

/* endian-neutral reading of big-endian data */
#define EndGetM32(a) ((((a)[0])<<24)|(((a)[1])<<16)|(((a)[2])<<8)|((a)[3]))
#define EndGetM16(a) ((((a)[0])<<8)|((a)[1]))

extern struct mspack_system *mspack_default_system;

/* returns the length of a file opened for reading */
extern int mspack_sys_filelen(struct mspack_system *system,
			      struct mspack_file *file, off_t *length);

/* validates a system structure */
extern int mspack_valid_system(struct mspack_system *sys);

/* Can't redfine intrinsics in Microsoft Visual C */
#ifndef _MSC_VER

/* inline memcmp() */
static inline int memcmp(const void *s1, const void *s2, size_t n) {
  unsigned char *c1 = (unsigned char *) s1;
  unsigned char *c2 = (unsigned char *) s2;
  if (n == 0) return 0;
  while (--n && (*c1 == *c2)) c1++, c2++;
  return *c1 - *c2;
}

/* inline strlen() */
static inline size_t strlen(const char *s) {
  const char *e = s;
  while (*e) e++;
  return e - s;
}
#endif
