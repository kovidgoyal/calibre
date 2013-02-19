// This CRC function is based on Intel Slicing-by-8 algorithm.
//
// Original Intel Slicing-by-8 code is available here:
//
//    http://sourceforge.net/projects/slicing-by-8/
//
// Original Intel Slicing-by-8 code is licensed as:
//    
//    Copyright (c) 2004-2006 Intel Corporation - All Rights Reserved
//    
//    This software program is licensed subject to the BSD License, 
//    available at http://www.opensource.org/licenses/bsd-license.html


#include "rar.hpp"

// CRCTab duplicates crc_tables[0], but we still need it to decrypt
// old version RAR archives. GUI code might use it for ZIP encryption.
uint CRCTab[256];

static uint crc_tables[8][256]; // Tables for Slicing-by-8.

void InitCRC()
{
  for (uint I=0;I<256;I++) // Build the classic CRC32 lookup table.
  {
    uint C=I;
    for (uint J=0;J<8;J++)
      C=(C & 1) ? (C>>1)^0xEDB88320L : (C>>1);
    CRCTab[I]=crc_tables[0][I]=C;
  }

	for (uint I=0;I<=256;I++) // Build additional lookup tables.
  {
		uint C=crc_tables[0][I];
		for (uint J=1;J<8;J++)
    {
			C=crc_tables[0][(byte)C]^(C>>8);
			crc_tables[J][I]=C;
		}
	}
}


uint CRC(uint StartCRC,const void *Addr,size_t Size)
{
  if (CRCTab[1]==0)
    InitCRC();
  byte *Data=(byte *)Addr;

  // Align Data to 8 for better performance.
  for (;Size>0 && ((long)Data & 7);Size--,Data++)
    StartCRC=crc_tables[0][(byte)(StartCRC^Data[0])]^(StartCRC>>8);

  for (;Size>=8;Size-=8,Data+=8)
  {
#ifdef BIG_ENDIAN
		StartCRC ^= Data[0]|(Data[1] << 8)|(Data[2] << 16)|(Data[3] << 24);
#else
		StartCRC ^= *(uint32 *) Data;
#endif
		StartCRC = crc_tables[7][(byte) StartCRC       ] ^
               crc_tables[6][(byte)(StartCRC >> 8) ] ^
               crc_tables[5][(byte)(StartCRC >> 16)] ^
               crc_tables[4][(byte)(StartCRC >> 24)] ^
               crc_tables[3][Data[4]] ^
               crc_tables[2][Data[5]] ^
               crc_tables[1][Data[6]] ^
               crc_tables[0][Data[7]];
	}

  for (;Size>0;Size--,Data++) // Process left data.
    StartCRC=crc_tables[0][(byte)(StartCRC^Data[0])]^(StartCRC>>8);

  return(StartCRC);
}


#ifndef SFX_MODULE
// For RAR 1.4 archives in case somebody still has them.
ushort OldCRC(ushort StartCRC,const void *Addr,size_t Size)
{
  byte *Data=(byte *)Addr;
  for (size_t I=0;I<Size;I++)
  {
    StartCRC=(StartCRC+Data[I])&0xffff;
    StartCRC=((StartCRC<<1)|(StartCRC>>15))&0xffff;
  }
  return(StartCRC);
}
#endif
