#include "rar.hpp"

RawRead::RawRead(File *SrcFile)
{
  RawRead::SrcFile=SrcFile;
  ReadPos=0;
  DataSize=0;
#ifndef SHELL_EXT
  Crypt=NULL;
#endif
}


void RawRead::Read(size_t Size)
{
#if !defined(SHELL_EXT) && !defined(RAR_NOCRYPT)
  if (Crypt!=NULL)
  {
    size_t CurSize=Data.Size();
    size_t SizeToRead=Size-(CurSize-DataSize);
    if (SizeToRead>0)
    {
      size_t AlignedReadSize=SizeToRead+((~SizeToRead+1)&0xf);
      Data.Add(AlignedReadSize);
      size_t ReadSize=SrcFile->Read(&Data[CurSize],AlignedReadSize);
      Crypt->DecryptBlock(&Data[CurSize],AlignedReadSize);
      DataSize+=ReadSize==0 ? 0:Size;
    }
    else
      DataSize+=Size;
  }
  else
#endif
    if (Size!=0)
    {
      Data.Add(Size);
      DataSize+=SrcFile->Read(&Data[DataSize],Size);
    }
}


void RawRead::Read(byte *SrcData,size_t Size)
{
  if (Size!=0)
  {
    Data.Add(Size);
    memcpy(&Data[DataSize],SrcData,Size);
    DataSize+=Size;
  }
}


void RawRead::Get(byte &Field)
{
  if (ReadPos<DataSize)
  {
    Field=Data[ReadPos];
    ReadPos++;
  }
  else
    Field=0;
}


void RawRead::Get(ushort &Field)
{
  if (ReadPos+1<DataSize)
  {
    Field=Data[ReadPos]+(Data[ReadPos+1]<<8);
    ReadPos+=2;
  }
  else
    Field=0;
}


void RawRead::Get(uint &Field)
{
  if (ReadPos+3<DataSize)
  {
    Field=Data[ReadPos]+(Data[ReadPos+1]<<8)+(Data[ReadPos+2]<<16)+
          (Data[ReadPos+3]<<24);
    ReadPos+=4;
  }
  else
    Field=0;
}


void RawRead::Get8(int64 &Field)
{
  uint Low,High;
  Get(Low);
  Get(High);
  Field=INT32TO64(High,Low);
}


void RawRead::Get(byte *Field,size_t Size)
{
  if (ReadPos+Size-1<DataSize)
  {
    memcpy(Field,&Data[ReadPos],Size);
    ReadPos+=Size;
  }
  else
    memset(Field,0,Size);
}


void RawRead::Get(wchar *Field,size_t Size)
{
  if (ReadPos+2*Size-1<DataSize)
  {
    RawToWide(&Data[ReadPos],Field,Size);
    ReadPos+=sizeof(wchar)*Size;
  }
  else
    memset(Field,0,sizeof(wchar)*Size);
}


uint RawRead::GetCRC(bool ProcessedOnly)
{
  return(DataSize>2 ? CRC(0xffffffff,&Data[2],(ProcessedOnly ? ReadPos:DataSize)-2):0xffffffff);
}
