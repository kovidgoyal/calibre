// (c) 2001,2004 by Max Alekseyev
// ver. 2.1

#include <stddef.h>

#define INCL_DOSMODULEMGR
#include <os2.h>

typedef void* UconvObject;
typedef unsigned short UniChar;

int uni_init(int codepage);

int uni_done();

int uni_toucs(           /* translate to Unicode                   */
	      char*,     /* I - input string                       */
	      size_t,    /* I - length of input string (chars)     */
	      UniChar*,  /* O - output Unicode string              */
	      size_t* ); /* O - length of output string (UniChars) */

int uni_fromucs(            /* translate from Unicode                */
		UniChar*,   /* I - input Unicode string              */
		size_t,     /* I - length of input string (UniChars) */
		char*,      /* O - output string                     */
		size_t* );  /* O - length of output string (chars)   */

/* IMPLEMENTATION */

static int (*uniMapCpToUcsCp) (
	  unsigned long, /* I  - Codepage to convert         */
	  UniChar*,      /* O  - Output buffer               */
	  size_t );      /* I  - UniChars in output buffer   */

static int (*uniCreateUconvObject) (
	  UniChar*,      /* I  - Unicode name of uconv table */
	  UconvObject* );/* O  - Uconv object handle         */

static int (*uniFreeUconvObject) (
          UconvObject ); /* I  - Uconv object handle         */

static int (*uniUconvToUcs) (
	  UconvObject,   /* I  - Uconv object handle         */
	  void**,        /* IO - Input buffer                */
	  size_t*,       /* IO - Input buffer size (bytes)   */
	  UniChar**,     /* IO - Output buffer size          */
	  size_t*,       /* IO - Output size (chars)         */
	  size_t* );     /* IO - Substitution count          */

static int (*uniUconvFromUcs) (
	  UconvObject,   /* I  - Uconv object handle         */
	  UniChar**,     /* IO - Input buffer                */
	  size_t*,       /* IO - Input buffer size (bytes)   */
	  void**,        /* IO - Output buffer size          */
	  size_t*,       /* IO - Output size (chars)         */
	  size_t* );     /* IO - Substitution count          */

static int uni_ready = 0;
static HMODULE uni_UCONV;
static UconvObject uni_obj;

int uni_init(int codepage) {
    UniChar unistr[256];

    uni_ready = 0;

    if(!&DosLoadModule) {
	/* DOS enviroment detected */
	return -1;
    }

    if( DosLoadModule(0,0,(PCSZ)"UCONV",&uni_UCONV) ) {
	/* no Unicode API found (obsolete OS/2 version) */
	return -2;
    }

    if( !DosQueryProcAddr(uni_UCONV,0,(PCSZ)"UniMapCpToUcsCp",     (PPFN)&uniMapCpToUcsCp     ) &&
        !DosQueryProcAddr(uni_UCONV,0,(PCSZ)"UniUconvToUcs",       (PPFN)&uniUconvToUcs       ) &&
        !DosQueryProcAddr(uni_UCONV,0,(PCSZ)"UniUconvFromUcs",     (PPFN)&uniUconvFromUcs     ) &&
        !DosQueryProcAddr(uni_UCONV,0,(PCSZ)"UniCreateUconvObject",(PPFN)&uniCreateUconvObject) &&
        !DosQueryProcAddr(uni_UCONV,0,(PCSZ)"UniFreeUconvObject",  (PPFN)&uniFreeUconvObject  )
      ) {
	unistr[0] = 0;
	if( (!codepage || !uniMapCpToUcsCp(codepage, unistr, 256)) && !uniCreateUconvObject(unistr,&uni_obj) ) {
	    uni_ready = 1;
	    return 0;
	}
    }
    DosFreeModule(uni_UCONV);
    return -2;
}

int uni_toucs(char* src, size_t srclen, UniChar* dst, size_t* dstlen) {
    size_t srcbytes, srcsize, dstsize, subsc=0;

    if(!uni_ready) return -1;

    dstsize = srcbytes = srclen * sizeof(UniChar);

    if( uniUconvToUcs(uni_obj,(void**)&src,&srclen,&dst,&dstsize,&subsc) ) {
        return -1;
    }
    *dstlen = srcbytes - dstsize;
    return 0;
}

int uni_fromucs(UniChar* src, size_t srclen, char* dst, size_t* dstlen) {
    size_t srcbytes, srcsize, dstsize, subsc=0;

    if(!uni_ready) return -1;

    dstsize = srcbytes = *dstlen;

    if( uniUconvFromUcs(uni_obj,&src,&srclen,(void**)&dst,&dstsize,&subsc) ) {
        return -1;
    }
    *dstlen = srcbytes - dstsize;
    return 0;
}

int uni_done() {
    if( uni_ready ) {
      uniFreeUconvObject(uni_obj);
      DosFreeModule(uni_UCONV);
      uni_ready = 0;
    }
    return 0;
}
