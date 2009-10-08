/* d3des.h -
 *
 * Headers and defines for d3des.c
 * Graven Imagery, 1992.
 *
 * THIS SOFTWARE PLACED IN THE PUBLIC DOMAIN BY THE AUTHOUR
 * 920825 19:42 EDST
 *
 * Copyright (c) 1988,1989,1990,1991,1992 by Richard Outerbridge
 *	(GEnie : OUTER; CIS : [71755,204])
 */
 
#pragma once

#undef D2_DES		
#undef D3_DES		
 
#ifdef D3_DES
#ifndef D2_DES
#define D2_DES		/* D2_DES is needed for D3_DES */
#endif
#endif
	
#define EN0	0		/* MODE == encrypt */
#define DE1	1		/* MODE == decrypt */
 
/* Useful on 68000-ish machines, but NOT USED here. */
 
typedef union {
	unsigned long blok[2];
	unsigned short word[4];
	unsigned char byte[8];
	} M68K;
 
typedef union {
	unsigned long dblok[4];
	unsigned short dword[8];
	unsigned char dbyte[16];
	} M68K2;
 
extern void deskey(unsigned char *, short);
/*		      hexkey[8]     MODE
 * Sets the internal key register according to the hexadecimal
 * key contained in the 8 bytes of hexkey, according to the DES,
 * for encryption or decryption according to MODE.
 */
 
extern void usekey(unsigned long *);
/*		    cookedkey[32]
 * Loads the internal key register with the data in cookedkey.
 */
 
extern void cpkey(unsigned long *);
/*		   cookedkey[32]
 * Copies the contents of the internal key register into the storage
 * located at &cookedkey[0].
 */
 
extern void des(unsigned char *, unsigned char *);
/*		    from[8]	      to[8]
 * Encrypts/Decrypts (according to the key currently loaded in the
 * internal key register) one block of eight bytes at address 'from'
 * into the block at address 'to'.  They can be the same.
 */
 
#ifdef D2_DES
 
#define desDkey(a,b)	des2key((a),(b))
extern void des2key(unsigned char *, short);
/*		      hexkey[16]     MODE
 * Sets the internal key registerS according to the hexadecimal
 * keyS contained in the 16 bytes of hexkey, according to the DES,
 * for DOUBLE encryption or decryption according to MODE.
 * NOTE: this clobbers all three key registers!
 */
 
extern void Ddes(unsigned char *, unsigned char *);
/*		    from[8]	      to[8]
 * Encrypts/Decrypts (according to the keyS currently loaded in the
 * internal key registerS) one block of eight bytes at address 'from'
 * into the block at address 'to'.  They can be the same.
 */
 
extern void D2des(unsigned char *, unsigned char *);
/*		    from[16]	      to[16]
 * Encrypts/Decrypts (according to the keyS currently loaded in the
 * internal key registerS) one block of SIXTEEN bytes at address 'from'
 * into the block at address 'to'.  They can be the same.
 */
 
extern void makekey(char *, unsigned char *);
/*		*password,	single-length key[8]
 * With a double-length default key, this routine hashes a NULL-terminated
 * string into an eight-byte random-looking key, suitable for use with the
 * deskey() routine.
 */
 
#define makeDkey(a,b)	make2key((a),(b))
extern void make2key(char *, unsigned char *);
/*		*password,	double-length key[16]
 * With a double-length default key, this routine hashes a NULL-terminated
 * string into a sixteen-byte random-looking key, suitable for use with the
 * des2key() routine.
 */
 
#ifndef D3_DES	/* D2_DES only */
 
#define useDkey(a)	use2key((a))
#define cpDkey(a)	cp2key((a))
 
extern void use2key(unsigned long *);
/*		    cookedkey[64]
 * Loads the internal key registerS with the data in cookedkey.
 * NOTE: this clobbers all three key registers!
 */
 
extern voi  cp2key(unsigned long *);
/*		   cookedkey[64]
 * Copies the contents of the internal key registerS into the storage
 * located at &cookedkey[0].
 */
 
#else	/* D3_DES too */
 
#define useDkey(a)	use3key((a))
#define cpDkey(a)	cp3key((a))
 
extern void des3key(unsigned char *, short);
/*		      hexkey[24]     MODE
 * Sets the internal key registerS according to the hexadecimal
 * keyS contained in the 24 bytes of hexkey, according to the DES,
 * for DOUBLE encryption or decryption according to MODE.
 */
 
extern void use3key(unsigned long *);
/*		    cookedkey[96]
 * Loads the 3 internal key registerS with the data in cookedkey.
 */
 
extern void cp3key(unsigned long *);
/*		   cookedkey[96]
 * Copies the contents of the 3 internal key registerS into the storage
 * located at &cookedkey[0].
 */
 
extern void make3key(char *, unsigned char *);
/*		*password,	triple-length key[24]
 * With a triple-length default key, this routine hashes a NULL-terminated
 * string into a twenty-four-byte random-looking key, suitable for use with
 * the des3key() routine.
 */
 
#endif	/* D3_DES */
#endif	/* D2_DES */
 
/* d3des.h V5.09 rwo 9208.04 15:06 Graven Imagery
 ********************************************************************/

