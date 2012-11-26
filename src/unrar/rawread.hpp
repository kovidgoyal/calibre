#ifndef _RAR_RAWREAD_
#define _RAR_RAWREAD_

class RawRead
{
  private:
    Array<byte> Data;
    File *SrcFile;
    size_t DataSize;
    size_t ReadPos;
#ifndef SHELL_EXT
    CryptData *Crypt;
#endif
  public:
    RawRead(File *SrcFile);
    void Read(size_t Size);
    void Read(byte *SrcData,size_t Size);
    void Get(byte &Field);
    void Get(ushort &Field);
    void Get(uint &Field);
    void Get8(int64 &Field);
    void Get(byte *Field,size_t Size);
    void Get(wchar *Field,size_t Size);
    uint GetCRC(bool ProcessedOnly);
    size_t Size() {return DataSize;}
    size_t PaddedSize() {return Data.Size()-DataSize;}
#ifndef SHELL_EXT
    void SetCrypt(CryptData *Crypt) {RawRead::Crypt=Crypt;}
#endif
};

#endif
