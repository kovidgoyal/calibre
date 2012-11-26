#ifndef _RAR_GETBITS_
#define _RAR_GETBITS_

class BitInput
{
  public:
    enum BufferSize {MAX_SIZE=0x8000}; // Size of input buffer.
  protected:
    int InAddr; // Curent byte position in the buffer.
    int InBit;  // Current bit position in the current byte.
  public:
    BitInput();
    ~BitInput();

    byte *InBuf; // Dynamically allocated input buffer.

    void InitBitInput()
    {
      InAddr=InBit=0;
    }
    
    // Move forward by 'Bits' bits.
    void addbits(uint Bits)
    {
      Bits+=InBit;
      InAddr+=Bits>>3;
      InBit=Bits&7;
    }
    
    // Return 16 bits from current position in the buffer.
    // Bit at (InAddr,InBit) has the highest position in returning data.
    uint getbits()
    {
      uint BitField=(uint)InBuf[InAddr] << 16;
      BitField|=(uint)InBuf[InAddr+1] << 8;
      BitField|=(uint)InBuf[InAddr+2];
      BitField >>= (8-InBit);
      return(BitField & 0xffff);
    }
    
    void faddbits(uint Bits);
    uint fgetbits();
    
    // Check if buffer has enough space for IncPtr bytes. Returns 'true'
    // if buffer will be overflown.
    bool Overflow(uint IncPtr) 
    {
      return(InAddr+IncPtr>=MAX_SIZE);
    }
};
#endif
