#ifndef _RAR_TYPES_
#define _RAR_TYPES_

typedef unsigned char    byte;   // unsigned 8 bits
typedef unsigned short   ushort; // preferably 16 bits, but can be more
typedef unsigned int     uint;   // 32 bits or more

#define PRESENT_INT32 // undefine if signed 32 bits is not available

typedef unsigned int     uint32; // 32 bits exactly
typedef   signed int     int32;  // signed 32 bits exactly

// If compiler does not support 64 bit variables, we can define
// uint64 and int64 as 32 bit, but it will limit the maximum processed
// file size to 2 GB.
#if defined(__BORLANDC__) || defined(_MSC_VER)
typedef   unsigned __int64 uint64; // unsigned 64 bits
typedef     signed __int64  int64; // signed 64 bits
#else
typedef unsigned long long uint64; // unsigned 64 bits
typedef   signed long long  int64; // signed 64 bits
#endif


#if defined(_WIN_ALL) || defined(__GNUC__) || defined(__sgi) || defined(_AIX) || defined(__sun) || defined(__hpux) || defined(_OSF_SOURCE)
typedef wchar_t wchar;
#else
typedef ushort wchar;
#endif

// Get lowest 16 bits.
#define GET_SHORT16(x) (sizeof(ushort)==2 ? (ushort)(x):((x)&0xffff))

// Get lowest 32 bits.
#define GET_UINT32(x)  (sizeof(uint32)==4 ? (uint32)(x):((x)&0xffffffff))

// Make 64 bit integer from two 32 bit.
#define INT32TO64(high,low) ((((uint64)(high))<<32)+((uint64)low))

// Special int64 value, large enough to never be found in real life.
// We use it in situations, when we need to indicate that parameter 
// is not defined and probably should be calculated inside of function.
// Lower part is intentionally 0x7fffffff, not 0xffffffff, to make it 
// compatible with 32 bit int64.
#define INT64NDF INT32TO64(0x7fffffff,0x7fffffff)

#endif
