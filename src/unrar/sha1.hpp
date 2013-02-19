#ifndef _RAR_SHA1_
#define _RAR_SHA1_

#define HW 5

typedef struct {
    uint32 state[5];
    uint32 count[2];
    unsigned char buffer[64];

    unsigned char workspace[64]; // Temporary buffer.
} hash_context;

void hash_initial( hash_context * c );
void hash_process( hash_context * c, unsigned char * data, size_t len,
                   bool handsoff);
void hash_final( hash_context * c, uint32[HW], bool handsoff);

#endif
