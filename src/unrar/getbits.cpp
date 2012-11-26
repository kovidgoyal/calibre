#include "rar.hpp"

BitInput::BitInput()
{
  // getbits attempts to read data from InAddr, InAddr+1, InAddr+2 positions.
  // So let's allocate two additional bytes for situation, when we need to
  // read only 1 byte from the last position of buffer and avoid a crash
  // from access to next 2 bytes, which contents we do not need.
  size_t BufSize=MAX_SIZE+2;
  InBuf=new byte[BufSize];

  // Ensure that we get predictable results when accessing bytes in area
  // not filled with read data.
  memset(InBuf,0,BufSize);
}


BitInput::~BitInput()
{
  delete[] InBuf;
}


void BitInput::faddbits(uint Bits)
{
  // Function wrapped version of inline addbits to save code size.
  addbits(Bits);
}


uint BitInput::fgetbits()
{
  // Function wrapped version of inline getbits to save code size.
  return(getbits());
}
