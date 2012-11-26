#ifndef _RAR_COMPRESS_
#define _RAR_COMPRESS_

class ComprDataIO;
class PackingFileTable;

#define MAX_LZ_MATCH    0x101

#define MAXWINSIZE      0x400000
#define MAXWINMASK      (MAXWINSIZE-1)

#define LOW_DIST_REP_COUNT 16

#define NC 299  /* alphabet = {0, 1, 2, ..., NC - 1} */
#define DC  60
#define LDC 17
#define RC  28
#define HUFF_TABLE_SIZE (NC+DC+RC+LDC)
#define BC  20

#define NC20 298  /* alphabet = {0, 1, 2, ..., NC - 1} */
#define DC20 48
#define RC20 28
#define BC20 19
#define MC20 257

// Largest alphabet size among all values listed above.
#define LARGEST_TABLE_SIZE 299

enum {CODE_HUFFMAN,CODE_LZ,CODE_LZ2,CODE_REPEATLZ,CODE_CACHELZ,
      CODE_STARTFILE,CODE_ENDFILE,CODE_VM,CODE_VMDATA};


enum FilterType {
  FILTER_NONE, FILTER_PPM /*dummy*/, FILTER_E8, FILTER_E8E9,
  FILTER_UPCASETOLOW, FILTER_AUDIO, FILTER_RGB, FILTER_DELTA,
  FILTER_ITANIUM, FILTER_E8E9V2
};

#endif
