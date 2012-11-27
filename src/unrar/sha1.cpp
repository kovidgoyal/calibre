#include "rar.hpp"

/*
SHA-1 in C
By Steve Reid <steve@edmweb.com>
100% Public Domain

Test Vectors (from FIPS PUB 180-1)
"abc"
  A9993E36 4706816A BA3E2571 7850C26C 9CD0D89D
"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"
  84983E44 1C3BD26E BAAE4AA1 F95129E5 E54670F1
A million repetitions of "a"
  34AA973C D4C4DAA4 F61EEB2B DBAD2731 6534016F
*/

#if !defined(LITTLE_ENDIAN) && !defined(BIG_ENDIAN)
  #if defined(_M_IX86) || defined(_M_I86) || defined(__alpha)
    #define LITTLE_ENDIAN
  #else
    #error "LITTLE_ENDIAN or BIG_ENDIAN must be defined"
	#endif
#endif

/* #define SHA1HANDSOFF * Copies data before messing with it. */

#define rol(value, bits) (((value) << (bits)) | ((value) >> (32 - (bits))))

/* blk0() and blk() perform the initial expand. */
/* I got the idea of expanding during the round function from SSLeay */
#ifdef LITTLE_ENDIAN
#define blk0(i) (block->l[i] = (rol(block->l[i],24)&0xFF00FF00) \
    |(rol(block->l[i],8)&0x00FF00FF))
#else
#define blk0(i) block->l[i]
#endif
#define blk(i) (block->l[i&15] = rol(block->l[(i+13)&15]^block->l[(i+8)&15] \
    ^block->l[(i+2)&15]^block->l[i&15],1))

/* (R0+R1), R2, R3, R4 are the different operations used in SHA1 */
#define R0(v,w,x,y,z,i) {z+=((w&(x^y))^y)+blk0(i)+0x5A827999+rol(v,5);w=rol(w,30);}
#define R1(v,w,x,y,z,i) {z+=((w&(x^y))^y)+blk(i)+0x5A827999+rol(v,5);w=rol(w,30);}
#define R2(v,w,x,y,z,i) {z+=(w^x^y)+blk(i)+0x6ED9EBA1+rol(v,5);w=rol(w,30);}
#define R3(v,w,x,y,z,i) {z+=(((w|x)&y)|(w&x))+blk(i)+0x8F1BBCDC+rol(v,5);w=rol(w,30);}
#define R4(v,w,x,y,z,i) {z+=(w^x^y)+blk(i)+0xCA62C1D6+rol(v,5);w=rol(w,30);}

#ifdef _MSC_VER
#pragma optimize( "", off )
// We need to disable the optimization to really wipe these variables.
#endif
static void wipevars(uint32 &a,uint32 &b,uint32 &c,uint32 &d,uint32 &e)
{
  // Wipe used variables for safety reason.
  a=b=c=d=e=0;
}
#ifdef _MSC_VER
#pragma optimize( "", on )
#endif

/* Hash a single 512-bit block. This is the core of the algorithm. */

void SHA1Transform(uint32 state[5], unsigned char workspace[64], unsigned char buffer[64], bool handsoff)
{
#ifndef SFX_MODULE
  uint32 a, b, c, d, e;
#endif
  typedef union {
    unsigned char c[64];
    uint32 l[16];
} CHAR64LONG16;
CHAR64LONG16* block;
    if (handsoff)
    {
      block = (CHAR64LONG16*)workspace;
      memcpy(block, buffer, 64);
    }
    else
      block = (CHAR64LONG16*)buffer;
#ifdef SFX_MODULE
    static int pos[80][5];
    static bool pinit=false;
    if (!pinit)
    {
      for (int I=0,P=0;I<80;I++,P=(P ? P-1:4))
      {
        pos[I][0]=P;
        pos[I][1]=(P+1)%5;
        pos[I][2]=(P+2)%5;
        pos[I][3]=(P+3)%5;
        pos[I][4]=(P+4)%5;
      }
      pinit=true;
    }
    uint32 s[5];
    for (int I=0;I<sizeof(s)/sizeof(s[0]);I++)
      s[I]=state[I];

    for (int I=0;I<16;I++)
      R0(s[pos[I][0]],s[pos[I][1]],s[pos[I][2]],s[pos[I][3]],s[pos[I][4]],I);
    for (int I=16;I<20;I++)
      R1(s[pos[I][0]],s[pos[I][1]],s[pos[I][2]],s[pos[I][3]],s[pos[I][4]],I);
    for (int I=20;I<40;I++)
      R2(s[pos[I][0]],s[pos[I][1]],s[pos[I][2]],s[pos[I][3]],s[pos[I][4]],I);
    for (int I=40;I<60;I++)
      R3(s[pos[I][0]],s[pos[I][1]],s[pos[I][2]],s[pos[I][3]],s[pos[I][4]],I);
    for (int I=60;I<80;I++)
      R4(s[pos[I][0]],s[pos[I][1]],s[pos[I][2]],s[pos[I][3]],s[pos[I][4]],I);

    for (int I=0;I<sizeof(s)/sizeof(s[0]);I++)
      state[I]+=s[I];
#else
    /* Copy context->state[] to working vars */
    a = state[0];
    b = state[1];
    c = state[2];
    d = state[3];
    e = state[4];
    /* 4 rounds of 20 operations each. Loop unrolled. */
    R0(a,b,c,d,e, 0); R0(e,a,b,c,d, 1); R0(d,e,a,b,c, 2); R0(c,d,e,a,b, 3);
    R0(b,c,d,e,a, 4); R0(a,b,c,d,e, 5); R0(e,a,b,c,d, 6); R0(d,e,a,b,c, 7);
    R0(c,d,e,a,b, 8); R0(b,c,d,e,a, 9); R0(a,b,c,d,e,10); R0(e,a,b,c,d,11);
    R0(d,e,a,b,c,12); R0(c,d,e,a,b,13); R0(b,c,d,e,a,14); R0(a,b,c,d,e,15);
    R1(e,a,b,c,d,16); R1(d,e,a,b,c,17); R1(c,d,e,a,b,18); R1(b,c,d,e,a,19);
    R2(a,b,c,d,e,20); R2(e,a,b,c,d,21); R2(d,e,a,b,c,22); R2(c,d,e,a,b,23);
    R2(b,c,d,e,a,24); R2(a,b,c,d,e,25); R2(e,a,b,c,d,26); R2(d,e,a,b,c,27);
    R2(c,d,e,a,b,28); R2(b,c,d,e,a,29); R2(a,b,c,d,e,30); R2(e,a,b,c,d,31);
    R2(d,e,a,b,c,32); R2(c,d,e,a,b,33); R2(b,c,d,e,a,34); R2(a,b,c,d,e,35);
    R2(e,a,b,c,d,36); R2(d,e,a,b,c,37); R2(c,d,e,a,b,38); R2(b,c,d,e,a,39);
    R3(a,b,c,d,e,40); R3(e,a,b,c,d,41); R3(d,e,a,b,c,42); R3(c,d,e,a,b,43);
    R3(b,c,d,e,a,44); R3(a,b,c,d,e,45); R3(e,a,b,c,d,46); R3(d,e,a,b,c,47);
    R3(c,d,e,a,b,48); R3(b,c,d,e,a,49); R3(a,b,c,d,e,50); R3(e,a,b,c,d,51);
    R3(d,e,a,b,c,52); R3(c,d,e,a,b,53); R3(b,c,d,e,a,54); R3(a,b,c,d,e,55);
    R3(e,a,b,c,d,56); R3(d,e,a,b,c,57); R3(c,d,e,a,b,58); R3(b,c,d,e,a,59);
    R4(a,b,c,d,e,60); R4(e,a,b,c,d,61); R4(d,e,a,b,c,62); R4(c,d,e,a,b,63);
    R4(b,c,d,e,a,64); R4(a,b,c,d,e,65); R4(e,a,b,c,d,66); R4(d,e,a,b,c,67);
    R4(c,d,e,a,b,68); R4(b,c,d,e,a,69); R4(a,b,c,d,e,70); R4(e,a,b,c,d,71);
    R4(d,e,a,b,c,72); R4(c,d,e,a,b,73); R4(b,c,d,e,a,74); R4(a,b,c,d,e,75);
    R4(e,a,b,c,d,76); R4(d,e,a,b,c,77); R4(c,d,e,a,b,78); R4(b,c,d,e,a,79);
    /* Add the working vars back into context.state[] */
    state[0] += a;
    state[1] += b;
    state[2] += c;
    state[3] += d;
    state[4] += e;

    /* Wipe variables */
// Such wipe method does not work in optimizing compilers.
//    a = b = c = d = e = 0;
//    memset(&a,0,sizeof(a));

    wipevars(a,b,c,d,e);
#endif
}


/* Initialize new context */

void hash_initial(hash_context* context)
{
    /* SHA1 initialization constants */
    context->state[0] = 0x67452301;
    context->state[1] = 0xEFCDAB89;
    context->state[2] = 0x98BADCFE;
    context->state[3] = 0x10325476;
    context->state[4] = 0xC3D2E1F0;
    context->count[0] = context->count[1] = 0;
}


/* Run your data through this. */
void hash_process( hash_context * context, unsigned char * data, size_t len,
                   bool handsoff )
{
unsigned int i, j;
uint blen = ((uint)len)<<3;

    j = (context->count[0] >> 3) & 63;
    if ((context->count[0] += blen) < blen ) context->count[1]++;
    context->count[1] += (uint32)(len >> 29);
    if ((j + len) > 63) {
        memcpy(&context->buffer[j], data, (i = 64-j));
        SHA1Transform(context->state, context->workspace, context->buffer, handsoff);
        for ( ; i + 63 < len; i += 64) {
#ifdef ALLOW_NOT_ALIGNED_INT
            SHA1Transform(context->state, context->workspace, &data[i], handsoff);
#else
            unsigned char buffer[64];
            memcpy(buffer,data+i,sizeof(buffer));
            SHA1Transform(context->state, context->workspace, buffer, handsoff);
            memcpy(data+i,buffer,sizeof(buffer));
#endif
#ifdef BIG_ENDIAN
            if (!handsoff)
            {
              unsigned char *d=data+i;
              for (int k=0;k<64;k+=4)
              {
                byte b0=d[k],b1=d[k+1];
                d[k]=d[k+3];
                d[k+1]=d[k+2];
                d[k+2]=b1;
                d[k+3]=b0;
              }
            }
#endif
        }
        j = 0;
    }
    else i = 0;
    if (len > i)
      memcpy(&context->buffer[j], &data[i], len - i);
}


/* Add padding and return the message digest. */

void hash_final( hash_context* context, uint32 digest[5], bool handsoff)
{
uint i, j;
unsigned char finalcount[8];

    for (i = 0; i < 8; i++) {
        finalcount[i] = (unsigned char)((context->count[(i >= 4 ? 0 : 1)]
         >> ((3-(i & 3)) * 8) ) & 255);  /* Endian independent */
    }
    unsigned char ch=(unsigned char)'\200';
    hash_process(context, &ch, 1, handsoff);
    while ((context->count[0] & 504) != 448) {
        ch=0;
        hash_process(context, &ch, 1, handsoff);
    }
    hash_process(context, finalcount, 8, handsoff);  /* Should cause a SHA1Transform() */
    for (i = 0; i < 5; i++) {
        digest[i] = context->state[i] & 0xffffffff;
    }
    /* Wipe variables */
    cleandata(&i,sizeof(i));
    cleandata(&j,sizeof(j));
    cleandata(context->buffer, 64);
    cleandata(context->state, 20);
    cleandata(context->count, 8);
    cleandata(&finalcount, 8);
    if (handsoff)
      memset(context->workspace,0,sizeof(context->workspace)); // Wipe the temporary buffer.
//      SHA1Transform(context->state, context->workspace, context->buffer, true); /* make SHA1Transform overwrite it's own static vars */
}


