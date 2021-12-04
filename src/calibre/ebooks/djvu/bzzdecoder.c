/*
 * bzzdecoder.c
 * Copyright (C) 2014 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */


#define PY_SSIZE_T_CLEAN
#include <Python.h>

#ifdef _MSC_VER
#include "stdint.h"
// inline does not work with the visual studio C compiler
#define inline
#else
#include <inttypes.h>
#endif

#define STRFY(x) #x
#define STRFY2(x) STRFY(x)
#define CORRUPT PyErr_SetString(PyExc_ValueError, "Corrupt bitstream at line: " STRFY2(__LINE__))

typedef uint8_t bool;

typedef struct Table {
    uint16_t p;
    uint16_t m;
    uint8_t  up;
    uint8_t  dn;
} Table;

typedef struct State {
    char *raw;
    char *end;
    uint32_t  p[256];
    uint32_t  m[256];
    uint8_t    up[256];
    uint8_t    dn[256];
    // machine independent ffz
    char          ffzt[256];
    uint8_t byte;
    uint8_t scount;
    uint8_t delay;
    uint32_t  a;
    uint32_t  code;
    uint32_t  fence;
    uint32_t  subend;
    uint32_t  buffer;
    uint32_t  nrun;
    bool      is_eof;
    uint32_t  xsize;
    uint8_t  *buf;

} State;

static Table default_ztable[256] = // {{{
{
  /* This table has been designed for the ZPCoder
   * by running the following command in file 'zptable.sn':
   * (fast-crude (steady-mat 0.0035  0.0002) 260)))
   */
  { 0x8000,  0x0000,  84, 145 },    /* 000: p=0.500000 (    0,    0) */
  { 0x8000,  0x0000,   3,   4 },    /* 001: p=0.500000 (    0,    0) */
  { 0x8000,  0x0000,   4,   3 },    /* 002: p=0.500000 (    0,    0) */
  { 0x6bbd,  0x10a5,   5,   1 },    /* 003: p=0.465226 (    0,    0) */
  { 0x6bbd,  0x10a5,   6,   2 },    /* 004: p=0.465226 (    0,    0) */
  { 0x5d45,  0x1f28,   7,   3 },    /* 005: p=0.430708 (    0,    0) */
  { 0x5d45,  0x1f28,   8,   4 },    /* 006: p=0.430708 (    0,    0) */
  { 0x51b9,  0x2bd3,   9,   5 },    /* 007: p=0.396718 (    0,    0) */
  { 0x51b9,  0x2bd3,  10,   6 },    /* 008: p=0.396718 (    0,    0) */
  { 0x4813,  0x36e3,  11,   7 },    /* 009: p=0.363535 (    0,    0) */
  { 0x4813,  0x36e3,  12,   8 },    /* 010: p=0.363535 (    0,    0) */
  { 0x3fd5,  0x408c,  13,   9 },    /* 011: p=0.331418 (    0,    0) */
  { 0x3fd5,  0x408c,  14,  10 },    /* 012: p=0.331418 (    0,    0) */
  { 0x38b1,  0x48fd,  15,  11 },    /* 013: p=0.300585 (    0,    0) */
  { 0x38b1,  0x48fd,  16,  12 },    /* 014: p=0.300585 (    0,    0) */
  { 0x3275,  0x505d,  17,  13 },    /* 015: p=0.271213 (    0,    0) */
  { 0x3275,  0x505d,  18,  14 },    /* 016: p=0.271213 (    0,    0) */
  { 0x2cfd,  0x56d0,  19,  15 },    /* 017: p=0.243438 (    0,    0) */
  { 0x2cfd,  0x56d0,  20,  16 },    /* 018: p=0.243438 (    0,    0) */
  { 0x2825,  0x5c71,  21,  17 },    /* 019: p=0.217391 (    0,    0) */
  { 0x2825,  0x5c71,  22,  18 },    /* 020: p=0.217391 (    0,    0) */
  { 0x23ab,  0x615b,  23,  19 },    /* 021: p=0.193150 (    0,    0) */
  { 0x23ab,  0x615b,  24,  20 },    /* 022: p=0.193150 (    0,    0) */
  { 0x1f87,  0x65a5,  25,  21 },    /* 023: p=0.170728 (    0,    0) */
  { 0x1f87,  0x65a5,  26,  22 },    /* 024: p=0.170728 (    0,    0) */
  { 0x1bbb,  0x6962,  27,  23 },    /* 025: p=0.150158 (    0,    0) */
  { 0x1bbb,  0x6962,  28,  24 },    /* 026: p=0.150158 (    0,    0) */
  { 0x1845,  0x6ca2,  29,  25 },    /* 027: p=0.131418 (    0,    0) */
  { 0x1845,  0x6ca2,  30,  26 },    /* 028: p=0.131418 (    0,    0) */
  { 0x1523,  0x6f74,  31,  27 },    /* 029: p=0.114460 (    0,    0) */
  { 0x1523,  0x6f74,  32,  28 },    /* 030: p=0.114460 (    0,    0) */
  { 0x1253,  0x71e6,  33,  29 },    /* 031: p=0.099230 (    0,    0) */
  { 0x1253,  0x71e6,  34,  30 },    /* 032: p=0.099230 (    0,    0) */
  { 0x0fcf,  0x7404,  35,  31 },    /* 033: p=0.085611 (    0,    0) */
  { 0x0fcf,  0x7404,  36,  32 },    /* 034: p=0.085611 (    0,    0) */
  { 0x0d95,  0x75d6,  37,  33 },    /* 035: p=0.073550 (    0,    0) */
  { 0x0d95,  0x75d6,  38,  34 },    /* 036: p=0.073550 (    0,    0) */
  { 0x0b9d,  0x7768,  39,  35 },    /* 037: p=0.062888 (    0,    0) */
  { 0x0b9d,  0x7768,  40,  36 },    /* 038: p=0.062888 (    0,    0) */
  { 0x09e3,  0x78c2,  41,  37 },    /* 039: p=0.053539 (    0,    0) */
  { 0x09e3,  0x78c2,  42,  38 },    /* 040: p=0.053539 (    0,    0) */
  { 0x0861,  0x79ea,  43,  39 },    /* 041: p=0.045365 (    0,    0) */
  { 0x0861,  0x79ea,  44,  40 },    /* 042: p=0.045365 (    0,    0) */
  { 0x0711,  0x7ae7,  45,  41 },    /* 043: p=0.038272 (    0,    0) */
  { 0x0711,  0x7ae7,  46,  42 },    /* 044: p=0.038272 (    0,    0) */
  { 0x05f1,  0x7bbe,  47,  43 },    /* 045: p=0.032174 (    0,    0) */
  { 0x05f1,  0x7bbe,  48,  44 },    /* 046: p=0.032174 (    0,    0) */
  { 0x04f9,  0x7c75,  49,  45 },    /* 047: p=0.026928 (    0,    0) */
  { 0x04f9,  0x7c75,  50,  46 },    /* 048: p=0.026928 (    0,    0) */
  { 0x0425,  0x7d0f,  51,  47 },    /* 049: p=0.022444 (    0,    0) */
  { 0x0425,  0x7d0f,  52,  48 },    /* 050: p=0.022444 (    0,    0) */
  { 0x0371,  0x7d91,  53,  49 },    /* 051: p=0.018636 (    0,    0) */
  { 0x0371,  0x7d91,  54,  50 },    /* 052: p=0.018636 (    0,    0) */
  { 0x02d9,  0x7dfe,  55,  51 },    /* 053: p=0.015421 (    0,    0) */
  { 0x02d9,  0x7dfe,  56,  52 },    /* 054: p=0.015421 (    0,    0) */
  { 0x0259,  0x7e5a,  57,  53 },    /* 055: p=0.012713 (    0,    0) */
  { 0x0259,  0x7e5a,  58,  54 },    /* 056: p=0.012713 (    0,    0) */
  { 0x01ed,  0x7ea6,  59,  55 },    /* 057: p=0.010419 (    0,    0) */
  { 0x01ed,  0x7ea6,  60,  56 },    /* 058: p=0.010419 (    0,    0) */
  { 0x0193,  0x7ee6,  61,  57 },    /* 059: p=0.008525 (    0,    0) */
  { 0x0193,  0x7ee6,  62,  58 },    /* 060: p=0.008525 (    0,    0) */
  { 0x0149,  0x7f1a,  63,  59 },    /* 061: p=0.006959 (    0,    0) */
  { 0x0149,  0x7f1a,  64,  60 },    /* 062: p=0.006959 (    0,    0) */
  { 0x010b,  0x7f45,  65,  61 },    /* 063: p=0.005648 (    0,    0) */
  { 0x010b,  0x7f45,  66,  62 },    /* 064: p=0.005648 (    0,    0) */
  { 0x00d5,  0x7f6b,  67,  63 },    /* 065: p=0.004506 (    0,    0) */
  { 0x00d5,  0x7f6b,  68,  64 },    /* 066: p=0.004506 (    0,    0) */
  { 0x00a5,  0x7f8d,  69,  65 },    /* 067: p=0.003480 (    0,    0) */
  { 0x00a5,  0x7f8d,  70,  66 },    /* 068: p=0.003480 (    0,    0) */
  { 0x007b,  0x7faa,  71,  67 },    /* 069: p=0.002602 (    0,    0) */
  { 0x007b,  0x7faa,  72,  68 },    /* 070: p=0.002602 (    0,    0) */
  { 0x0057,  0x7fc3,  73,  69 },    /* 071: p=0.001843 (    0,    0) */
  { 0x0057,  0x7fc3,  74,  70 },    /* 072: p=0.001843 (    0,    0) */
  { 0x003b,  0x7fd7,  75,  71 },    /* 073: p=0.001248 (    0,    0) */
  { 0x003b,  0x7fd7,  76,  72 },    /* 074: p=0.001248 (    0,    0) */
  { 0x0023,  0x7fe7,  77,  73 },    /* 075: p=0.000749 (    0,    0) */
  { 0x0023,  0x7fe7,  78,  74 },    /* 076: p=0.000749 (    0,    0) */
  { 0x0013,  0x7ff2,  79,  75 },    /* 077: p=0.000402 (    0,    0) */
  { 0x0013,  0x7ff2,  80,  76 },    /* 078: p=0.000402 (    0,    0) */
  { 0x0007,  0x7ffa,  81,  77 },    /* 079: p=0.000153 (    0,    0) */
  { 0x0007,  0x7ffa,  82,  78 },    /* 080: p=0.000153 (    0,    0) */
  { 0x0001,  0x7fff,  81,  79 },    /* 081: p=0.000027 (    0,    0) */
  { 0x0001,  0x7fff,  82,  80 },    /* 082: p=0.000027 (    0,    0) */
  { 0x5695,  0x0000,   9,  85 },    /* 083: p=0.411764 (    2,    3) */
  { 0x24ee,  0x0000,  86, 226 },    /* 084: p=0.199988 (    1,    0) */
  { 0x8000,  0x0000,   5,   6 },    /* 085: p=0.500000 (    3,    3) */
  { 0x0d30,  0x0000,  88, 176 },    /* 086: p=0.071422 (    4,    0) */
  { 0x481a,  0x0000,  89, 143 },    /* 087: p=0.363634 (    1,    2) */
  { 0x0481,  0x0000,  90, 138 },    /* 088: p=0.024388 (   13,    0) */
  { 0x3579,  0x0000,  91, 141 },    /* 089: p=0.285711 (    1,    3) */
  { 0x017a,  0x0000,  92, 112 },    /* 090: p=0.007999 (   41,    0) */
  { 0x24ef,  0x0000,  93, 135 },    /* 091: p=0.199997 (    1,    5) */
  { 0x007b,  0x0000,  94, 104 },    /* 092: p=0.002611 (  127,    0) */
  { 0x1978,  0x0000,  95, 133 },    /* 093: p=0.137929 (    1,    8) */
  { 0x0028,  0x0000,  96, 100 },    /* 094: p=0.000849 (  392,    0) */
  { 0x10ca,  0x0000,  97, 129 },    /* 095: p=0.090907 (    1,   13) */
  { 0x000d,  0x0000,  82,  98 },    /* 096: p=0.000276 ( 1208,    0) */
  { 0x0b5d,  0x0000,  99, 127 },    /* 097: p=0.061537 (    1,   20) */
  { 0x0034,  0x0000,  76,  72 },    /* 098: p=0.001102 ( 1208,    1) */
  { 0x078a,  0x0000, 101, 125 },    /* 099: p=0.040815 (    1,   31) */
  { 0x00a0,  0x0000,  70, 102 },    /* 100: p=0.003387 (  392,    1) */
  { 0x050f,  0x0000, 103, 123 },    /* 101: p=0.027397 (    1,   47) */
  { 0x0117,  0x0000,  66,  60 },    /* 102: p=0.005912 (  392,    2) */
  { 0x0358,  0x0000, 105, 121 },    /* 103: p=0.018099 (    1,   72) */
  { 0x01ea,  0x0000, 106, 110 },    /* 104: p=0.010362 (  127,    1) */
  { 0x0234,  0x0000, 107, 119 },    /* 105: p=0.011940 (    1,  110) */
  { 0x0144,  0x0000,  66, 108 },    /* 106: p=0.006849 (  193,    1) */
  { 0x0173,  0x0000, 109, 117 },    /* 107: p=0.007858 (    1,  168) */
  { 0x0234,  0x0000,  60,  54 },    /* 108: p=0.011925 (  193,    2) */
  { 0x00f5,  0x0000, 111, 115 },    /* 109: p=0.005175 (    1,  256) */
  { 0x0353,  0x0000,  56,  48 },    /* 110: p=0.017995 (  127,    2) */
  { 0x00a1,  0x0000,  69, 113 },    /* 111: p=0.003413 (    1,  389) */
  { 0x05c5,  0x0000, 114, 134 },    /* 112: p=0.031249 (   41,    1) */
  { 0x011a,  0x0000,  65,  59 },    /* 113: p=0.005957 (    2,  389) */
  { 0x03cf,  0x0000, 116, 132 },    /* 114: p=0.020618 (   63,    1) */
  { 0x01aa,  0x0000,  61,  55 },    /* 115: p=0.009020 (    2,  256) */
  { 0x0285,  0x0000, 118, 130 },    /* 116: p=0.013652 (   96,    1) */
  { 0x0286,  0x0000,  57,  51 },    /* 117: p=0.013672 (    2,  168) */
  { 0x01ab,  0x0000, 120, 128 },    /* 118: p=0.009029 (  146,    1) */
  { 0x03d3,  0x0000,  53,  47 },    /* 119: p=0.020710 (    2,  110) */
  { 0x011a,  0x0000, 122, 126 },    /* 120: p=0.005961 (  222,    1) */
  { 0x05c5,  0x0000,  49,  41 },    /* 121: p=0.031250 (    2,   72) */
  { 0x00ba,  0x0000, 124,  62 },    /* 122: p=0.003925 (  338,    1) */
  { 0x08ad,  0x0000,  43,  37 },    /* 123: p=0.046979 (    2,   47) */
  { 0x007a,  0x0000,  72,  66 },    /* 124: p=0.002586 (  514,    1) */
  { 0x0ccc,  0x0000,  39,  31 },    /* 125: p=0.069306 (    2,   31) */
  { 0x01eb,  0x0000,  60,  54 },    /* 126: p=0.010386 (  222,    2) */
  { 0x1302,  0x0000,  33,  25 },    /* 127: p=0.102940 (    2,   20) */
  { 0x02e6,  0x0000,  56,  50 },    /* 128: p=0.015695 (  146,    2) */
  { 0x1b81,  0x0000,  29, 131 },    /* 129: p=0.148935 (    2,   13) */
  { 0x045e,  0x0000,  52,  46 },    /* 130: p=0.023648 (   96,    2) */
  { 0x24ef,  0x0000,  23,  17 },    /* 131: p=0.199999 (    3,   13) */
  { 0x0690,  0x0000,  48,  40 },    /* 132: p=0.035533 (   63,    2) */
  { 0x2865,  0x0000,  23,  15 },    /* 133: p=0.218748 (    2,    8) */
  { 0x09de,  0x0000,  42, 136 },    /* 134: p=0.053434 (   41,    2) */
  { 0x3987,  0x0000, 137,   7 },    /* 135: p=0.304346 (    2,    5) */
  { 0x0dc8,  0x0000,  38,  32 },    /* 136: p=0.074626 (   41,    3) */
  { 0x2c99,  0x0000,  21, 139 },    /* 137: p=0.241378 (    2,    7) */
  { 0x10ca,  0x0000, 140, 172 },    /* 138: p=0.090907 (   13,    1) */
  { 0x3b5f,  0x0000,  15,   9 },    /* 139: p=0.312499 (    3,    7) */
  { 0x0b5d,  0x0000, 142, 170 },    /* 140: p=0.061537 (   20,    1) */
  { 0x5695,  0x0000,   9,  85 },    /* 141: p=0.411764 (    2,    3) */
  { 0x078a,  0x0000, 144, 168 },    /* 142: p=0.040815 (   31,    1) */
  { 0x8000,  0x0000, 141, 248 },    /* 143: p=0.500000 (    2,    2) */
  { 0x050f,  0x0000, 146, 166 },    /* 144: p=0.027397 (   47,    1) */
  { 0x24ee,  0x0000, 147, 247 },    /* 145: p=0.199988 (    0,    1) */
  { 0x0358,  0x0000, 148, 164 },    /* 146: p=0.018099 (   72,    1) */
  { 0x0d30,  0x0000, 149, 197 },    /* 147: p=0.071422 (    0,    4) */
  { 0x0234,  0x0000, 150, 162 },    /* 148: p=0.011940 (  110,    1) */
  { 0x0481,  0x0000, 151,  95 },    /* 149: p=0.024388 (    0,   13) */
  { 0x0173,  0x0000, 152, 160 },    /* 150: p=0.007858 (  168,    1) */
  { 0x017a,  0x0000, 153, 173 },    /* 151: p=0.007999 (    0,   41) */
  { 0x00f5,  0x0000, 154, 158 },    /* 152: p=0.005175 (  256,    1) */
  { 0x007b,  0x0000, 155, 165 },    /* 153: p=0.002611 (    0,  127) */
  { 0x00a1,  0x0000,  70, 156 },    /* 154: p=0.003413 (  389,    1) */
  { 0x0028,  0x0000, 157, 161 },    /* 155: p=0.000849 (    0,  392) */
  { 0x011a,  0x0000,  66,  60 },    /* 156: p=0.005957 (  389,    2) */
  { 0x000d,  0x0000,  81, 159 },    /* 157: p=0.000276 (    0, 1208) */
  { 0x01aa,  0x0000,  62,  56 },    /* 158: p=0.009020 (  256,    2) */
  { 0x0034,  0x0000,  75,  71 },    /* 159: p=0.001102 (    1, 1208) */
  { 0x0286,  0x0000,  58,  52 },    /* 160: p=0.013672 (  168,    2) */
  { 0x00a0,  0x0000,  69, 163 },    /* 161: p=0.003387 (    1,  392) */
  { 0x03d3,  0x0000,  54,  48 },    /* 162: p=0.020710 (  110,    2) */
  { 0x0117,  0x0000,  65,  59 },    /* 163: p=0.005912 (    2,  392) */
  { 0x05c5,  0x0000,  50,  42 },    /* 164: p=0.031250 (   72,    2) */
  { 0x01ea,  0x0000, 167, 171 },    /* 165: p=0.010362 (    1,  127) */
  { 0x08ad,  0x0000,  44,  38 },    /* 166: p=0.046979 (   47,    2) */
  { 0x0144,  0x0000,  65, 169 },    /* 167: p=0.006849 (    1,  193) */
  { 0x0ccc,  0x0000,  40,  32 },    /* 168: p=0.069306 (   31,    2) */
  { 0x0234,  0x0000,  59,  53 },    /* 169: p=0.011925 (    2,  193) */
  { 0x1302,  0x0000,  34,  26 },    /* 170: p=0.102940 (   20,    2) */
  { 0x0353,  0x0000,  55,  47 },    /* 171: p=0.017995 (    2,  127) */
  { 0x1b81,  0x0000,  30, 174 },    /* 172: p=0.148935 (   13,    2) */
  { 0x05c5,  0x0000, 175, 193 },    /* 173: p=0.031249 (    1,   41) */
  { 0x24ef,  0x0000,  24,  18 },    /* 174: p=0.199999 (   13,    3) */
  { 0x03cf,  0x0000, 177, 191 },    /* 175: p=0.020618 (    1,   63) */
  { 0x2b74,  0x0000, 178, 222 },    /* 176: p=0.235291 (    4,    1) */
  { 0x0285,  0x0000, 179, 189 },    /* 177: p=0.013652 (    1,   96) */
  { 0x201d,  0x0000, 180, 218 },    /* 178: p=0.173910 (    6,    1) */
  { 0x01ab,  0x0000, 181, 187 },    /* 179: p=0.009029 (    1,  146) */
  { 0x1715,  0x0000, 182, 216 },    /* 180: p=0.124998 (    9,    1) */
  { 0x011a,  0x0000, 183, 185 },    /* 181: p=0.005961 (    1,  222) */
  { 0x0fb7,  0x0000, 184, 214 },    /* 182: p=0.085105 (   14,    1) */
  { 0x00ba,  0x0000,  69,  61 },    /* 183: p=0.003925 (    1,  338) */
  { 0x0a67,  0x0000, 186, 212 },    /* 184: p=0.056337 (   22,    1) */
  { 0x01eb,  0x0000,  59,  53 },    /* 185: p=0.010386 (    2,  222) */
  { 0x06e7,  0x0000, 188, 210 },    /* 186: p=0.037382 (   34,    1) */
  { 0x02e6,  0x0000,  55,  49 },    /* 187: p=0.015695 (    2,  146) */
  { 0x0496,  0x0000, 190, 208 },    /* 188: p=0.024844 (   52,    1) */
  { 0x045e,  0x0000,  51,  45 },    /* 189: p=0.023648 (    2,   96) */
  { 0x030d,  0x0000, 192, 206 },    /* 190: p=0.016529 (   79,    1) */
  { 0x0690,  0x0000,  47,  39 },    /* 191: p=0.035533 (    2,   63) */
  { 0x0206,  0x0000, 194, 204 },    /* 192: p=0.010959 (  120,    1) */
  { 0x09de,  0x0000,  41, 195 },    /* 193: p=0.053434 (    2,   41) */
  { 0x0155,  0x0000, 196, 202 },    /* 194: p=0.007220 (  183,    1) */
  { 0x0dc8,  0x0000,  37,  31 },    /* 195: p=0.074626 (    3,   41) */
  { 0x00e1,  0x0000, 198, 200 },    /* 196: p=0.004750 (  279,    1) */
  { 0x2b74,  0x0000, 199, 243 },    /* 197: p=0.235291 (    1,    4) */
  { 0x0094,  0x0000,  72,  64 },    /* 198: p=0.003132 (  424,    1) */
  { 0x201d,  0x0000, 201, 239 },    /* 199: p=0.173910 (    1,    6) */
  { 0x0188,  0x0000,  62,  56 },    /* 200: p=0.008284 (  279,    2) */
  { 0x1715,  0x0000, 203, 237 },    /* 201: p=0.124998 (    1,    9) */
  { 0x0252,  0x0000,  58,  52 },    /* 202: p=0.012567 (  183,    2) */
  { 0x0fb7,  0x0000, 205, 235 },    /* 203: p=0.085105 (    1,   14) */
  { 0x0383,  0x0000,  54,  48 },    /* 204: p=0.019021 (  120,    2) */
  { 0x0a67,  0x0000, 207, 233 },    /* 205: p=0.056337 (    1,   22) */
  { 0x0547,  0x0000,  50,  44 },    /* 206: p=0.028571 (   79,    2) */
  { 0x06e7,  0x0000, 209, 231 },    /* 207: p=0.037382 (    1,   34) */
  { 0x07e2,  0x0000,  46,  38 },    /* 208: p=0.042682 (   52,    2) */
  { 0x0496,  0x0000, 211, 229 },    /* 209: p=0.024844 (    1,   52) */
  { 0x0bc0,  0x0000,  40,  34 },    /* 210: p=0.063636 (   34,    2) */
  { 0x030d,  0x0000, 213, 227 },    /* 211: p=0.016529 (    1,   79) */
  { 0x1178,  0x0000,  36,  28 },    /* 212: p=0.094593 (   22,    2) */
  { 0x0206,  0x0000, 215, 225 },    /* 213: p=0.010959 (    1,  120) */
  { 0x19da,  0x0000,  30,  22 },    /* 214: p=0.139999 (   14,    2) */
  { 0x0155,  0x0000, 217, 223 },    /* 215: p=0.007220 (    1,  183) */
  { 0x24ef,  0x0000,  26,  16 },    /* 216: p=0.199998 (    9,    2) */
  { 0x00e1,  0x0000, 219, 221 },    /* 217: p=0.004750 (    1,  279) */
  { 0x320e,  0x0000,  20, 220 },    /* 218: p=0.269229 (    6,    2) */
  { 0x0094,  0x0000,  71,  63 },    /* 219: p=0.003132 (    1,  424) */
  { 0x432a,  0x0000,  14,   8 },    /* 220: p=0.344827 (    6,    3) */
  { 0x0188,  0x0000,  61,  55 },    /* 221: p=0.008284 (    2,  279) */
  { 0x447d,  0x0000,  14, 224 },    /* 222: p=0.349998 (    4,    2) */
  { 0x0252,  0x0000,  57,  51 },    /* 223: p=0.012567 (    2,  183) */
  { 0x5ece,  0x0000,   8,   2 },    /* 224: p=0.434782 (    4,    3) */
  { 0x0383,  0x0000,  53,  47 },    /* 225: p=0.019021 (    2,  120) */
  { 0x8000,  0x0000, 228,  87 },    /* 226: p=0.500000 (    1,    1) */
  { 0x0547,  0x0000,  49,  43 },    /* 227: p=0.028571 (    2,   79) */
  { 0x481a,  0x0000, 230, 246 },    /* 228: p=0.363634 (    2,    1) */
  { 0x07e2,  0x0000,  45,  37 },    /* 229: p=0.042682 (    2,   52) */
  { 0x3579,  0x0000, 232, 244 },    /* 230: p=0.285711 (    3,    1) */
  { 0x0bc0,  0x0000,  39,  33 },    /* 231: p=0.063636 (    2,   34) */
  { 0x24ef,  0x0000, 234, 238 },    /* 232: p=0.199997 (    5,    1) */
  { 0x1178,  0x0000,  35,  27 },    /* 233: p=0.094593 (    2,   22) */
  { 0x1978,  0x0000, 138, 236 },    /* 234: p=0.137929 (    8,    1) */
  { 0x19da,  0x0000,  29,  21 },    /* 235: p=0.139999 (    2,   14) */
  { 0x2865,  0x0000,  24,  16 },    /* 236: p=0.218748 (    8,    2) */
  { 0x24ef,  0x0000,  25,  15 },    /* 237: p=0.199998 (    2,    9) */
  { 0x3987,  0x0000, 240,   8 },    /* 238: p=0.304346 (    5,    2) */
  { 0x320e,  0x0000,  19, 241 },    /* 239: p=0.269229 (    2,    6) */
  { 0x2c99,  0x0000,  22, 242 },    /* 240: p=0.241378 (    7,    2) */
  { 0x432a,  0x0000,  13,   7 },    /* 241: p=0.344827 (    3,    6) */
  { 0x3b5f,  0x0000,  16,  10 },    /* 242: p=0.312499 (    7,    3) */
  { 0x447d,  0x0000,  13, 245 },    /* 243: p=0.349998 (    2,    4) */
  { 0x5695,  0x0000,  10,   2 },    /* 244: p=0.411764 (    3,    2) */
  { 0x5ece,  0x0000,   7,   1 },    /* 245: p=0.434782 (    3,    4) */
  { 0x8000,  0x0000, 244,  83 },    /* 246: p=0.500000 (    2,    2) */
  { 0x8000,  0x0000, 249, 250 },    /* 247: p=0.500000 (    1,    1) */
  { 0x5695,  0x0000,  10,   2 },    /* 248: p=0.411764 (    3,    2) */
  { 0x481a,  0x0000,  89, 143 },    /* 249: p=0.363634 (    1,    2) */
  { 0x481a,  0x0000, 230, 246 },    /* 250: p=0.363634 (    2,    1) */
};  // }}}

#define MIN(x, y) ((x < y) ? x : y)

#define ffz(ffzt, x) ((x>=0xff00) ? (ffzt[x&0xff]+8) : (ffzt[(x>>8)&0xff]))

#define TRUE 1
#define FALSE 0
#define MAXBLOCK 4096
#define FREQMAX  4
#define CTXIDS  3

static inline bool read_byte(State *state) {
    if (state->raw <= state->end) {
        state->byte = *(state->raw++);
        return TRUE;
    }
    return FALSE;
}

static bool preload(State *state) {
    while (state->scount <= 24) {
        if (!read_byte(state)) {
            state->byte = 0xff;
            if (--state->delay < 1) {
                PyErr_SetString(PyExc_ValueError, "Unexpected end of input"); return FALSE;
            }
        }
        state->buffer = ((state->buffer)<<8) | state->byte;
        state->scount += 8;
    }
    return TRUE;
}

static void initialize_tables(State* state) {
    int32_t i, j;
    for (i = 0; i < 256; i++) {
        state->p[i] = default_ztable[i].p; state->m[i] = default_ztable[i].m; state->up[i] = default_ztable[i].up; state->dn[i] = default_ztable[i].dn;
        j = i;
        while (j & 0x80) {
            state->ffzt[i] += 1;
            j <<= 1;
        }
    }
}

static bool init_state(State *state) {
    // Initialize tables
    initialize_tables(state);
    // Codebit counter
    // Read first 16 bits of code
    if (!read_byte(state)) state->byte = 0xff;
    state->code = state->byte << 8;
    if (!read_byte(state)) state->byte = 0xff;
    state->code = state->code | state->byte;

    // preload buffer
    state->delay = 25; state->scount = 0;
    if (!preload(state)) return FALSE;
    state->fence = MIN(state->code, 0x7fff);

    // Alloc buffer
    state->buf = (uint8_t*) calloc(MAXBLOCK * 1024, sizeof(uint8_t));
    if (state->buf == NULL) { PyErr_NoMemory(); return FALSE; }
    return TRUE;
}

static inline int32_t decode_sub_simple(State *state, int32_t mps, uint32_t z) {
    int32_t shift = 0;

    /* Test MPS/LPS */
    if (z > state->code) {
        /* LPS branch */
        z = 0x10000 - z;
        state->a = state->a + z;
        state->code = state->code + z;
        /* LPS renormalization */
        shift = ffz(state->ffzt, state->a);
        state->scount -= shift;
        state->a = (uint16_t)(state->a<<shift);
        state->code = (uint16_t)(state->code<<shift) | ((state->buffer>>state->scount) & ((1<<shift)-1));
        if (state->scount<16) {
            if (!preload(state)) return -1;
        }
        state->fence = MIN(state->code, 0x7fff);
        return mps ^ 1;
    }

    /* MPS renormalization */
    state->scount -= 1;
    state->a = (uint16_t)(z<<1);
    state->code = (uint16_t)(state->code<<1) | ((state->buffer>>state->scount) & 1);
    if (state->scount<16) {
        if (!preload(state)) return -1;
    }
    state->fence = MIN(state->code, 0x7fff);
    return mps;
}


static inline int32_t zpcodec_decoder(State *state) {
    return decode_sub_simple(state, 0, 0x8000 + (state->a >> 1));
}

static inline int32_t decode_raw(State *state, int32_t bits) {
    int32_t n = 1, m = 1 << bits, b = 0;
    while (n < m) {
        b = zpcodec_decoder(state);
        n = (n << 1) | b;
    }
    return n - m;
}

static inline int32_t decode_sub(State *state, uint8_t *ctx, int32_t index, uint32_t z)
{
    /* Save bit */
    int32_t bit = (ctx[index] & 1), shift;
    /* Avoid interval reversion */
    unsigned int d = 0x6000 + ((z+state->a)>>2);
    if (z > d) z = d;
    /* Test MPS/LPS */
    if (z > state->code) {
        /* LPS branch */
        z = 0x10000 - z;
        state->a = state->a + z;
        state->code = state->code + z;
        /* LPS adaptation */
        ctx[index] = state->dn[ctx[index]];
        /* LPS renormalization */
        shift = ffz(state->ffzt, state->a);
        state->scount -= shift;
        state->a = (uint16_t)(state->a<<shift);
        state->code = (uint16_t)(state->code<<shift) | ((state->buffer>>state->scount) & ((1<<shift)-1));
        if (state->scount<16) { if (!preload(state)) return -1; }
        state->fence = MIN(state->code, 0x7fff);
        return bit ^ 1;
    } else {
        /* MPS adaptation */
        if (state->a >= state->m[ctx[index]])
            ctx[index] = state->up[ctx[index]];
        /* MPS renormalization */
        state->scount -= 1;
        state->a = (uint16_t)(z<<1);
        state->code = (uint16_t)(state->code<<1) | ((state->buffer>>state->scount) & 1);
        if (state->scount<16) { if (!preload(state)) return -1; }
        state->fence = MIN(state->code, 0x7fff);
        return bit;
    }
}



static inline int32_t zpcodec_decode(State *state, uint8_t *ctx, int32_t index) {
    uint32_t z = state->a + state->p[ctx[index]];
    if (z <= state->fence) {
        state->a = z;
        return ctx[index] & 1;
    }
    return decode_sub(state, ctx, index, z);
}

static inline int32_t decode_binary(State *state, uint8_t *ctx, int32_t index, int bits) {
  int n = 1, m = (1<<bits), b = 0;
  while (n < m) {
      b = zpcodec_decode(state, ctx, index + n);
      n = (n<<1) | b;
    }
  return n - m;
}


static bool decode(State *state, uint8_t *ctx) {
    uint8_t mtf[256] = { // {{{
  0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
  0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F,
  0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
  0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F,
  0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27,
  0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F,
  0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37,
  0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F,
  0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47,
  0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F,
  0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57,
  0x58, 0x59, 0x5A, 0x5B, 0x5C, 0x5D, 0x5E, 0x5F,
  0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67,
  0x68, 0x69, 0x6A, 0x6B, 0x6C, 0x6D, 0x6E, 0x6F,
  0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77,
  0x78, 0x79, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F,
  0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87,
  0x88, 0x89, 0x8A, 0x8B, 0x8C, 0x8D, 0x8E, 0x8F,
  0x90, 0x91, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97,
  0x98, 0x99, 0x9A, 0x9B, 0x9C, 0x9D, 0x9E, 0x9F,
  0xA0, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7,
  0xA8, 0xA9, 0xAA, 0xAB, 0xAC, 0xAD, 0xAE, 0xAF,
  0xB0, 0xB1, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6, 0xB7,
  0xB8, 0xB9, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF,
  0xC0, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7,
  0xC8, 0xC9, 0xCA, 0xCB, 0xCC, 0xCD, 0xCE, 0xCF,
  0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7,
  0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE, 0xDF,
  0xE0, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7,
  0xE8, 0xE9, 0xEA, 0xEB, 0xEC, 0xED, 0xEE, 0xEF,
  0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7,
  0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF};  // }}}
    int32_t fc = 0, freq[FREQMAX] = {0}, fadd = 4, mtfno = 3, markerpos = -1, ctxid = 0, fshift = 0, k = 0, count[256] = {0}, last = 0, tmp = 0;
    uint32_t *posn = NULL, n = 0, i = 0;
    uint8_t j = 0, c = 0;

    state->xsize = decode_raw(state, 24);
    if (!state->xsize) return FALSE;
    if (state->xsize > MAXBLOCK * 1024)  { CORRUPT; goto end; }
    posn = (uint32_t*)calloc(state->xsize, sizeof(uint32_t));
    if (posn == NULL) { PyErr_NoMemory(); goto end; }

    // Decode Estimation Speed
    if (zpcodec_decoder(state)) {
        fshift += 1;
        if (zpcodec_decoder(state)) fshift += 1;
    }

    for (i = 0; i < state->xsize; i++) {
        if (PyErr_Occurred()) goto end;

        ctxid = CTXIDS - 1; if (ctxid > mtfno) ctxid = mtfno;
        if (zpcodec_decode(state, ctx, ctxid)) { mtfno=0; state->buf[i] = mtf[mtfno]; goto rotate; }

        ctxid += CTXIDS;
        if (zpcodec_decode(state, ctx, ctxid)) { mtfno = 1; state->buf[i] = mtf[mtfno]; goto rotate; }

        ctxid = 2 * CTXIDS;
        for (j = 1; j < 8; j++) {
            if (zpcodec_decode(state, ctx, ctxid)) {
                mtfno = (1 << j) + decode_binary(state, ctx, ctxid, j);
                state->buf[i] = mtf[mtfno];
                goto rotate;
            }
            ctxid += 1 << j;
        }

        mtfno=256;
        state->buf[i]=0;
        markerpos=i;
        continue;

        // Rotate mtf according to empirical frequencies (new!)
        rotate:
        // Adjust frequencies for overflow
        fadd = fadd + (fadd>>fshift);
        if (fadd > 0x10000000) {
            fadd    >>= 24;
            freq[0] >>= 24;
            freq[1] >>= 24;
            freq[2] >>= 24;
            freq[3] >>= 24;
            for (k=4; k<FREQMAX; k++) freq[k] = freq[k]>>24;
        }
        // Relocate new char according to new freq
        fc = fadd;
        if (mtfno < FREQMAX) fc += freq[mtfno];
        for (k=mtfno; k>=FREQMAX; k--)
            mtf[k] = mtf[k-1];
        for (; k>0 && fc>=freq[k-1]; k--) {
            mtf[k] = mtf[k-1];
            freq[k] = freq[k-1];
        }
        mtf[k] = state->buf[i];
        freq[k] = fc;
    } // end loop on i

    ////////// Reconstruct the string
    if (markerpos<1 || (uint32_t)markerpos>=state->xsize) { CORRUPT; goto end; }
    // Allocate pointers
    // Fill count buffer
    for (i=0; i<(uint32_t)markerpos; i++)
    {
        c = state->buf[i];
        posn[i] = (c<<24) | (count[c] & 0xffffff);
        count[c] += 1;
    }
    for (i=markerpos+1; i<state->xsize; i++)
    {
        c = state->buf[i];
        posn[i] = (c<<24) | (count[c] & 0xffffff);
        count[c] += 1;
    }
    // Compute sorted char positions
    last = 1;
    for (i=0; i<256; i++)
    {
        tmp = count[i];
        count[i] = last;
        last += tmp;
    }
    // Undo the sort transform
    i = 0;
    last = state->xsize-1;
    while (last>0)
    {
        n = posn[i];
        c = (posn[i]>>24);
        state->buf[--last] = c;
        i = count[c] + (n & 0xffffff);
    }
    if (i != markerpos) { CORRUPT; goto end; }

end:
    if (posn != NULL) { free(posn); posn = NULL; }
    if (PyErr_Occurred()) return FALSE;
    return state->xsize != 0;
}

static PyObject *
bzz_decompress(PyObject *self, PyObject *args) {
    Py_ssize_t input_len = 0, i;
    State state = {0};
    uint8_t ctx[300] = {0};
    char *buf = NULL, *pos = NULL, *tmp = NULL;
    size_t buflen = 0, blocksize = MAXBLOCK * 1024;
    PyObject *ans = NULL;

    if (!PyArg_ParseTuple(args, "y#", &(state.raw), &input_len))
		return NULL;
    state.end = state.raw + input_len - 1;

    if (!init_state(&state)) goto end;

    buf = (char *)calloc(blocksize, sizeof(char));
    if (buf == NULL) { PyErr_NoMemory(); goto end; }
    buflen = blocksize;
    pos = buf;

    while (!state.is_eof) {
        if (!state.xsize) {  // decode is needed
            if (!decode(&state, ctx)) {
                if (PyErr_Occurred()) goto end;
                state.xsize = 1;
                state.is_eof = TRUE;
            }
            state.xsize -= 1;
        }

        if (state.xsize > 0) {
            while (buflen - (pos - buf) <= state.xsize) {
                tmp = (char*) realloc(buf, buflen + (buflen * sizeof(char)));
                if (tmp == NULL) {
                    PyErr_NoMemory(); goto end;
                }
                buflen += buflen * sizeof(char);
                pos = tmp + (pos - buf);
                buf = tmp; tmp = NULL;
            }
            memcpy(pos, state.buf, state.xsize);
            pos += state.xsize;
        }
        state.xsize = 0;
    }

end:
    if (state.buf != NULL) free(state.buf);
    if (!PyErr_Occurred()) {
        buflen = 0;
        for (i = 0; i < 3; i++) {
            buflen <<= 8; buflen += (uint8_t)buf[i];
        }
        Py_ssize_t psz = MIN(buflen, pos - buf);
        ans = Py_BuildValue("y#", buf + 3, psz);
    }
    if (buf != NULL) free(buf);
    if (PyErr_Occurred()) return NULL;
    return ans;
}

static char bzzdec_doc[] = "Decompress BZZ encoded strings (used in DJVU)";

static PyMethodDef bzzdec_methods[] = {
    {"decompress", bzz_decompress, METH_VARARGS,
    "decompress(bytestring) -> decompressed bytestring\n\n"
    		"Decompress a BZZ compressed byte string. "
    },

    {NULL, NULL, 0, NULL}
};

static int
exec_module(PyObject *module) { return 0; }
static PyModuleDef_Slot slots[] = { {Py_mod_exec, exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {
    .m_base     = PyModuleDef_HEAD_INIT,
    .m_name     = "bzzdec",
    .m_doc      = bzzdec_doc,
    .m_methods  = bzzdec_methods,
    .m_slots    = slots,
};

CALIBRE_MODINIT_FUNC PyInit_bzzdec(void) { return PyModuleDef_Init(&module_def); }
