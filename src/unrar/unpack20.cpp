#include "rar.hpp"

void Unpack::CopyString20(unsigned int Length,unsigned int Distance)
{
  LastDist=OldDist[OldDistPtr++ & 3]=Distance;
  LastLength=Length;
  DestUnpSize-=Length;

  unsigned int DestPtr=UnpPtr-Distance;
  if (DestPtr<MAXWINSIZE-300 && UnpPtr<MAXWINSIZE-300)
  {
    Window[UnpPtr++]=Window[DestPtr++];
    Window[UnpPtr++]=Window[DestPtr++];
    while (Length>2)
    {
      Length--;
      Window[UnpPtr++]=Window[DestPtr++];
    }
  }
  else
    while (Length--)
    {
      Window[UnpPtr]=Window[DestPtr++ & MAXWINMASK];
      UnpPtr=(UnpPtr+1) & MAXWINMASK;
    }
}


void Unpack::Unpack20(bool Solid)
{
  static unsigned char LDecode[]={0,1,2,3,4,5,6,7,8,10,12,14,16,20,24,28,32,40,48,56,64,80,96,112,128,160,192,224};
  static unsigned char LBits[]=  {0,0,0,0,0,0,0,0,1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4,  4,  5,  5,  5,  5};
  static int DDecode[]={0,1,2,3,4,6,8,12,16,24,32,48,64,96,128,192,256,384,512,768,1024,1536,2048,3072,4096,6144,8192,12288,16384,24576,32768U,49152U,65536,98304,131072,196608,262144,327680,393216,458752,524288,589824,655360,720896,786432,851968,917504,983040};
  static unsigned char DBits[]=  {0,0,0,0,1,1,2, 2, 3, 3, 4, 4, 5, 5,  6,  6,  7,  7,  8,  8,   9,   9,  10,  10,  11,  11,  12,   12,   13,   13,    14,    14,   15,   15,    16,    16,    16,    16,    16,    16,    16,    16,    16,    16,    16,    16,    16,    16};
  static unsigned char SDDecode[]={0,4,8,16,32,64,128,192};
  static unsigned char SDBits[]=  {2,2,3, 4, 5, 6,  6,  6};
  unsigned int Bits;

  if (Suspended)
    UnpPtr=WrPtr;
  else
  {
    UnpInitData(Solid);
    if (!UnpReadBuf())
      return;
    if (!Solid)
      if (!ReadTables20())
        return;
    --DestUnpSize;
  }

  while (DestUnpSize>=0)
  {
    UnpPtr&=MAXWINMASK;

    if (InAddr>ReadTop-30)
      if (!UnpReadBuf())
        break;
    if (((WrPtr-UnpPtr) & MAXWINMASK)<270 && WrPtr!=UnpPtr)
    {
      OldUnpWriteBuf();
      if (Suspended)
        return;
    }
    if (UnpAudioBlock)
    {
      int AudioNumber=DecodeNumber(&MD[UnpCurChannel]);

      if (AudioNumber==256)
      {
        if (!ReadTables20())
          break;
        continue;
      }
      Window[UnpPtr++]=DecodeAudio(AudioNumber);
      if (++UnpCurChannel==UnpChannels)
        UnpCurChannel=0;
      --DestUnpSize;
      continue;
    }

    int Number=DecodeNumber(&LD);
    if (Number<256)
    {
      Window[UnpPtr++]=(byte)Number;
      --DestUnpSize;
      continue;
    }
    if (Number>269)
    {
      int Length=LDecode[Number-=270]+3;
      if ((Bits=LBits[Number])>0)
      {
        Length+=getbits()>>(16-Bits);
        addbits(Bits);
      }

      int DistNumber=DecodeNumber(&DD);
      unsigned int Distance=DDecode[DistNumber]+1;
      if ((Bits=DBits[DistNumber])>0)
      {
        Distance+=getbits()>>(16-Bits);
        addbits(Bits);
      }

      if (Distance>=0x2000)
      {
        Length++;
        if (Distance>=0x40000L)
          Length++;
      }

      CopyString20(Length,Distance);
      continue;
    }
    if (Number==269)
    {
      if (!ReadTables20())
        break;
      continue;
    }
    if (Number==256)
    {
      CopyString20(LastLength,LastDist);
      continue;
    }
    if (Number<261)
    {
      unsigned int Distance=OldDist[(OldDistPtr-(Number-256)) & 3];
      int LengthNumber=DecodeNumber(&RD);
      int Length=LDecode[LengthNumber]+2;
      if ((Bits=LBits[LengthNumber])>0)
      {
        Length+=getbits()>>(16-Bits);
        addbits(Bits);
      }
      if (Distance>=0x101)
      {
        Length++;
        if (Distance>=0x2000)
        {
          Length++;
          if (Distance>=0x40000)
            Length++;
        }
      }
      CopyString20(Length,Distance);
      continue;
    }
    if (Number<270)
    {
      unsigned int Distance=SDDecode[Number-=261]+1;
      if ((Bits=SDBits[Number])>0)
      {
        Distance+=getbits()>>(16-Bits);
        addbits(Bits);
      }
      CopyString20(2,Distance);
      continue;
   }
  }
  ReadLastTables();
  OldUnpWriteBuf();
}


bool Unpack::ReadTables20()
{
  byte BitLength[BC20];
  unsigned char Table[MC20*4];
  int TableSize,N,I;
  if (InAddr>ReadTop-25)
    if (!UnpReadBuf())
      return(false);
  unsigned int BitField=getbits();
  UnpAudioBlock=(BitField & 0x8000);

  if (!(BitField & 0x4000))
    memset(UnpOldTable20,0,sizeof(UnpOldTable20));
  addbits(2);

  if (UnpAudioBlock)
  {
    UnpChannels=((BitField>>12) & 3)+1;
    if (UnpCurChannel>=UnpChannels)
      UnpCurChannel=0;
    addbits(2);
    TableSize=MC20*UnpChannels;
  }
  else
    TableSize=NC20+DC20+RC20;

  for (I=0;I<BC20;I++)
  {
    BitLength[I]=(byte)(getbits() >> 12);
    addbits(4);
  }
  MakeDecodeTables(BitLength,&BD,BC20);
  I=0;
  while (I<TableSize)
  {
    if (InAddr>ReadTop-5)
      if (!UnpReadBuf())
        return(false);
    int Number=DecodeNumber(&BD);
    if (Number<16)
    {
      Table[I]=(Number+UnpOldTable20[I]) & 0xf;
      I++;
    }
    else
      if (Number==16)
      {
        N=(getbits() >> 14)+3;
        addbits(2);
        while (N-- > 0 && I<TableSize)
        {
          Table[I]=Table[I-1];
          I++;
        }
      }
      else
      {
        if (Number==17)
        {
          N=(getbits() >> 13)+3;
          addbits(3);
        }
        else
        {
          N=(getbits() >> 9)+11;
          addbits(7);
        }
        while (N-- > 0 && I<TableSize)
          Table[I++]=0;
      }
  }
  if (InAddr>ReadTop)
    return(true);
  if (UnpAudioBlock)
    for (I=0;I<UnpChannels;I++)
      MakeDecodeTables(&Table[I*MC20],&MD[I],MC20);
  else
  {
    MakeDecodeTables(&Table[0],&LD,NC20);
    MakeDecodeTables(&Table[NC20],&DD,DC20);
    MakeDecodeTables(&Table[NC20+DC20],&RD,RC20);
  }
  memcpy(UnpOldTable20,Table,sizeof(UnpOldTable20));
  return(true);
}


void Unpack::ReadLastTables()
{
  if (ReadTop>=InAddr+5)
    if (UnpAudioBlock)
    {
      if (DecodeNumber(&MD[UnpCurChannel])==256)
        ReadTables20();
    }
    else
      if (DecodeNumber(&LD)==269)
        ReadTables20();
}


void Unpack::UnpInitData20(int Solid)
{
  if (!Solid)
  {
    UnpAudioBlock=UnpChannelDelta=UnpCurChannel=0;
    UnpChannels=1;

    memset(AudV,0,sizeof(AudV));
    memset(UnpOldTable20,0,sizeof(UnpOldTable20));
    memset(MD,0,sizeof(MD));
  }
}


byte Unpack::DecodeAudio(int Delta)
{
  struct AudioVariables *V=&AudV[UnpCurChannel];
  V->ByteCount++;
  V->D4=V->D3;
  V->D3=V->D2;
  V->D2=V->LastDelta-V->D1;
  V->D1=V->LastDelta;
  int PCh=8*V->LastChar+V->K1*V->D1+V->K2*V->D2+V->K3*V->D3+V->K4*V->D4+V->K5*UnpChannelDelta;
  PCh=(PCh>>3) & 0xFF;

  unsigned int Ch=PCh-Delta;

  int D=((signed char)Delta)<<3;

  V->Dif[0]+=abs(D);
  V->Dif[1]+=abs(D-V->D1);
  V->Dif[2]+=abs(D+V->D1);
  V->Dif[3]+=abs(D-V->D2);
  V->Dif[4]+=abs(D+V->D2);
  V->Dif[5]+=abs(D-V->D3);
  V->Dif[6]+=abs(D+V->D3);
  V->Dif[7]+=abs(D-V->D4);
  V->Dif[8]+=abs(D+V->D4);
  V->Dif[9]+=abs(D-UnpChannelDelta);
  V->Dif[10]+=abs(D+UnpChannelDelta);

  UnpChannelDelta=V->LastDelta=(signed char)(Ch-V->LastChar);
  V->LastChar=Ch;

  if ((V->ByteCount & 0x1F)==0)
  {
    unsigned int MinDif=V->Dif[0],NumMinDif=0;
    V->Dif[0]=0;
    for (int I=1;I<sizeof(V->Dif)/sizeof(V->Dif[0]);I++)
    {
      if (V->Dif[I]<MinDif)
      {
        MinDif=V->Dif[I];
        NumMinDif=I;
      }
      V->Dif[I]=0;
    }
    switch(NumMinDif)
    {
      case 1:
        if (V->K1>=-16)
          V->K1--;
        break;
      case 2:
        if (V->K1<16)
          V->K1++;
        break;
      case 3:
        if (V->K2>=-16)
          V->K2--;
        break;
      case 4:
        if (V->K2<16)
          V->K2++;
        break;
      case 5:
        if (V->K3>=-16)
          V->K3--;
        break;
      case 6:
        if (V->K3<16)
          V->K3++;
        break;
      case 7:
        if (V->K4>=-16)
          V->K4--;
        break;
      case 8:
        if (V->K4<16)
          V->K4++;
        break;
      case 9:
        if (V->K5>=-16)
          V->K5--;
        break;
      case 10:
        if (V->K5<16)
          V->K5++;
        break;
    }
  }
  return((byte)Ch);
}
