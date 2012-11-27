#include "rar.hpp"

#ifndef SFX_MODULE
extern uint CRCTab[256];
#endif

#define NROUNDS 32

#define  rol(x,n,xsize)  (((x)<<(n)) | ((x)>>(xsize-(n))))
#define  ror(x,n,xsize)  (((x)>>(n)) | ((x)<<(xsize-(n))))

#define substLong(t) ( (uint)SubstTable[(uint)t&255] | \
           ((uint)SubstTable[(int)(t>> 8)&255]<< 8) | \
           ((uint)SubstTable[(int)(t>>16)&255]<<16) | \
           ((uint)SubstTable[(int)(t>>24)&255]<<24) )

CryptKeyCacheItem CryptData::Cache[4];
int CryptData::CachePos=0;


#ifndef SFX_MODULE
static byte InitSubstTable[256]={
  215, 19,149, 35, 73,197,192,205,249, 28, 16,119, 48,221,  2, 42,
  232,  1,177,233, 14, 88,219, 25,223,195,244, 90, 87,239,153,137,
  255,199,147, 70, 92, 66,246, 13,216, 40, 62, 29,217,230, 86,  6,
   71, 24,171,196,101,113,218,123, 93, 91,163,178,202, 67, 44,235,
  107,250, 75,234, 49,167,125,211, 83,114,157,144, 32,193,143, 36,
  158,124,247,187, 89,214,141, 47,121,228, 61,130,213,194,174,251,
   97,110, 54,229,115, 57,152, 94,105,243,212, 55,209,245, 63, 11,
  164,200, 31,156, 81,176,227, 21, 76, 99,139,188,127, 17,248, 51,
  207,120,189,210,  8,226, 41, 72,183,203,135,165,166, 60, 98,  7,
  122, 38,155,170, 69,172,252,238, 39,134, 59,128,236, 27,240, 80,
  131,  3, 85,206,145, 79,154,142,159,220,201,133, 74, 64, 20,129,
  224,185,138,103,173,182, 43, 34,254, 82,198,151,231,180, 58, 10,
  118, 26,102, 12, 50,132, 22,191,136,111,162,179, 45,  4,148,108,
  161, 56, 78,126,242,222, 15,175,146, 23, 33,241,181,190, 77,225,
    0, 46,169,186, 68, 95,237, 65, 53,208,253,168,  9, 18,100, 52,
  116,184,160, 96,109, 37, 30,106,140,104,150,  5,204,117,112, 84
};
#endif



void CryptData::DecryptBlock(byte *Buf,size_t Size)
{
  rin.blockDecrypt(Buf,Size,Buf);
}


#ifndef SFX_MODULE
void CryptData::EncryptBlock20(byte *Buf)
{
  uint A,B,C,D,T,TA,TB;
#if defined(BIG_ENDIAN) || !defined(PRESENT_INT32) || !defined(ALLOW_NOT_ALIGNED_INT)
  A=((uint)Buf[0]|((uint)Buf[1]<<8)|((uint)Buf[2]<<16)|((uint)Buf[3]<<24))^Key[0];
  B=((uint)Buf[4]|((uint)Buf[5]<<8)|((uint)Buf[6]<<16)|((uint)Buf[7]<<24))^Key[1];
  C=((uint)Buf[8]|((uint)Buf[9]<<8)|((uint)Buf[10]<<16)|((uint)Buf[11]<<24))^Key[2];
  D=((uint)Buf[12]|((uint)Buf[13]<<8)|((uint)Buf[14]<<16)|((uint)Buf[15]<<24))^Key[3];
#else
  uint32 *BufPtr=(uint32 *)Buf;
  A=BufPtr[0]^Key[0];
  B=BufPtr[1]^Key[1];
  C=BufPtr[2]^Key[2];
  D=BufPtr[3]^Key[3];
#endif
  for(int I=0;I<NROUNDS;I++)
  {
    T=((C+rol(D,11,32))^Key[I&3]);
    TA=A^substLong(T);
    T=((D^rol(C,17,32))+Key[I&3]);
    TB=B^substLong(T);
    A=C;
    B=D;
    C=TA;
    D=TB;
  }
#if defined(BIG_ENDIAN) || !defined(PRESENT_INT32) || !defined(ALLOW_NOT_ALIGNED_INT)
  C^=Key[0];
  Buf[0]=(byte)C;
  Buf[1]=(byte)(C>>8);
  Buf[2]=(byte)(C>>16);
  Buf[3]=(byte)(C>>24);
  D^=Key[1];
  Buf[4]=(byte)D;
  Buf[5]=(byte)(D>>8);
  Buf[6]=(byte)(D>>16);
  Buf[7]=(byte)(D>>24);
  A^=Key[2];
  Buf[8]=(byte)A;
  Buf[9]=(byte)(A>>8);
  Buf[10]=(byte)(A>>16);
  Buf[11]=(byte)(A>>24);
  B^=Key[3];
  Buf[12]=(byte)B;
  Buf[13]=(byte)(B>>8);
  Buf[14]=(byte)(B>>16);
  Buf[15]=(byte)(B>>24);
#else
  BufPtr[0]=C^Key[0];
  BufPtr[1]=D^Key[1];
  BufPtr[2]=A^Key[2];
  BufPtr[3]=B^Key[3];
#endif
  UpdKeys(Buf);
}


void CryptData::DecryptBlock20(byte *Buf)
{
  byte InBuf[16];
  uint A,B,C,D,T,TA,TB;
#if defined(BIG_ENDIAN) || !defined(PRESENT_INT32) || !defined(ALLOW_NOT_ALIGNED_INT)
  A=((uint)Buf[0]|((uint)Buf[1]<<8)|((uint)Buf[2]<<16)|((uint)Buf[3]<<24))^Key[0];
  B=((uint)Buf[4]|((uint)Buf[5]<<8)|((uint)Buf[6]<<16)|((uint)Buf[7]<<24))^Key[1];
  C=((uint)Buf[8]|((uint)Buf[9]<<8)|((uint)Buf[10]<<16)|((uint)Buf[11]<<24))^Key[2];
  D=((uint)Buf[12]|((uint)Buf[13]<<8)|((uint)Buf[14]<<16)|((uint)Buf[15]<<24))^Key[3];
#else
  uint32 *BufPtr=(uint32 *)Buf;
  A=BufPtr[0]^Key[0];
  B=BufPtr[1]^Key[1];
  C=BufPtr[2]^Key[2];
  D=BufPtr[3]^Key[3];
#endif
  memcpy(InBuf,Buf,sizeof(InBuf));
  for(int I=NROUNDS-1;I>=0;I--)
  {
    T=((C+rol(D,11,32))^Key[I&3]);
    TA=A^substLong(T);
    T=((D^rol(C,17,32))+Key[I&3]);
    TB=B^substLong(T);
    A=C;
    B=D;
    C=TA;
    D=TB;
  }
#if defined(BIG_ENDIAN) || !defined(PRESENT_INT32) || !defined(ALLOW_NOT_ALIGNED_INT)
  C^=Key[0];
  Buf[0]=(byte)C;
  Buf[1]=(byte)(C>>8);
  Buf[2]=(byte)(C>>16);
  Buf[3]=(byte)(C>>24);
  D^=Key[1];
  Buf[4]=(byte)D;
  Buf[5]=(byte)(D>>8);
  Buf[6]=(byte)(D>>16);
  Buf[7]=(byte)(D>>24);
  A^=Key[2];
  Buf[8]=(byte)A;
  Buf[9]=(byte)(A>>8);
  Buf[10]=(byte)(A>>16);
  Buf[11]=(byte)(A>>24);
  B^=Key[3];
  Buf[12]=(byte)B;
  Buf[13]=(byte)(B>>8);
  Buf[14]=(byte)(B>>16);
  Buf[15]=(byte)(B>>24);
#else
  BufPtr[0]=C^Key[0];
  BufPtr[1]=D^Key[1];
  BufPtr[2]=A^Key[2];
  BufPtr[3]=B^Key[3];
#endif
  UpdKeys(InBuf);
}


void CryptData::UpdKeys(byte *Buf)
{
  for (int I=0;I<16;I+=4)
  {
    Key[0]^=CRCTab[Buf[I]];
    Key[1]^=CRCTab[Buf[I+1]];
    Key[2]^=CRCTab[Buf[I+2]];
    Key[3]^=CRCTab[Buf[I+3]];
  }
}


void CryptData::Swap(byte *Ch1,byte *Ch2)
{
  byte Ch=*Ch1;
  *Ch1=*Ch2;
  *Ch2=Ch;
}
#endif


void CryptData::SetCryptKeys(SecPassword *Password,const byte *Salt,bool Encrypt,bool OldOnly,bool HandsOffHash)
{
  if (!Password->IsSet())
    return;
  wchar PlainPsw[MAXPASSWORD];
  Password->Get(PlainPsw,ASIZE(PlainPsw));
  if (OldOnly)
  {
#ifndef SFX_MODULE
    if (CRCTab[1]==0)
      InitCRC();
    char Psw[MAXPASSWORD];
    memset(Psw,0,sizeof(Psw));

    // We need to use ASCII password for older encryption algorithms.
    WideToChar(PlainPsw,Psw,ASIZE(Psw));
    Psw[ASIZE(Psw)-1]=0;

    size_t PswLength=strlen(Psw);

    SetOldKeys(Psw);
    Key[0]=0xD3A3B879L;
    Key[1]=0x3F6D12F7L;
    Key[2]=0x7515A235L;
    Key[3]=0xA4E7F123L;

    memcpy(SubstTable,InitSubstTable,sizeof(SubstTable));
    for (int J=0;J<256;J++)
      for (size_t I=0;I<PswLength;I+=2)
      {
        uint N1=(byte)CRCTab [ (byte(Psw[I])   - J) &0xff];
        uint N2=(byte)CRCTab [ (byte(Psw[I+1]) + J) &0xff];
        for (int K=1;N1!=N2;N1=(N1+1)&0xff,K++)
          Swap(&SubstTable[N1],&SubstTable[(N1+I+K)&0xff]);
      }
    for (size_t I=0;I<PswLength;I+=16)
      EncryptBlock20((byte *)&Psw[I]);
    cleandata(Psw,sizeof(Psw));
#endif
    cleandata(PlainPsw,sizeof(PlainPsw));
    return;
  }

  bool Cached=false;
  for (uint I=0;I<ASIZE(Cache);I++)
    if (Cache[I].Password==*Password &&
        (Salt==NULL && !Cache[I].SaltPresent || Salt!=NULL &&
        Cache[I].SaltPresent && memcmp(Cache[I].Salt,Salt,SALT_SIZE)==0) &&
        Cache[I].HandsOffHash==HandsOffHash)
    {
      memcpy(AESKey,Cache[I].AESKey,sizeof(AESKey));
      memcpy(AESInit,Cache[I].AESInit,sizeof(AESInit));
      Cached=true;
      break;
    }

  if (!Cached)
  {
    byte RawPsw[2*MAXPASSWORD+SALT_SIZE];
    WideToRaw(PlainPsw,RawPsw);
    size_t RawLength=2*wcslen(PlainPsw);
    if (Salt!=NULL)
    {
      memcpy(RawPsw+RawLength,Salt,SALT_SIZE);
      RawLength+=SALT_SIZE;
    }
    hash_context c;
    hash_initial(&c);

    const int HashRounds=0x40000;
    for (int I=0;I<HashRounds;I++)
    {
      hash_process( &c, RawPsw, RawLength, HandsOffHash);
      byte PswNum[3];
      PswNum[0]=(byte)I;
      PswNum[1]=(byte)(I>>8);
      PswNum[2]=(byte)(I>>16);
      hash_process( &c, PswNum, 3, HandsOffHash);
      if (I%(HashRounds/16)==0)
      {
        hash_context tempc=c;
        uint32 digest[5];
        hash_final( &tempc, digest, HandsOffHash);
        AESInit[I/(HashRounds/16)]=(byte)digest[4];
      }
    }
    uint32 digest[5];
    hash_final( &c, digest, HandsOffHash);
    for (int I=0;I<4;I++)
      for (int J=0;J<4;J++)
        AESKey[I*4+J]=(byte)(digest[I]>>(J*8));

    Cache[CachePos].Password=*Password;
    if ((Cache[CachePos].SaltPresent=(Salt!=NULL))==true)
      memcpy(Cache[CachePos].Salt,Salt,SALT_SIZE);
    Cache[CachePos].HandsOffHash=HandsOffHash;
    memcpy(Cache[CachePos].AESKey,AESKey,sizeof(AESKey));
    memcpy(Cache[CachePos].AESInit,AESInit,sizeof(AESInit));
    CachePos=(CachePos+1)%ASIZE(Cache);

    cleandata(RawPsw,sizeof(RawPsw));
  }
  rin.init(Encrypt ? Rijndael::Encrypt : Rijndael::Decrypt,AESKey,AESInit);
  cleandata(PlainPsw,sizeof(PlainPsw));
}


#ifndef SFX_MODULE
void CryptData::SetOldKeys(const char *Password)
{
  uint PswCRC=CRC(0xffffffff,Password,strlen(Password));
  OldKey[0]=PswCRC&0xffff;
  OldKey[1]=(PswCRC>>16)&0xffff;
  OldKey[2]=OldKey[3]=0;
  PN1=PN2=PN3=0;
  byte Ch;
  while ((Ch=*Password)!=0)
  {
    PN1+=Ch;
    PN2^=Ch;
    PN3+=Ch;
    PN3=(byte)rol(PN3,1,8);
    OldKey[2]^=Ch^CRCTab[Ch];
    OldKey[3]+=Ch+(CRCTab[Ch]>>16);
    Password++;
  }
}


void CryptData::SetAV15Encryption()
{
  OldKey[0]=0x4765;
  OldKey[1]=0x9021;
  OldKey[2]=0x7382;
  OldKey[3]=0x5215;
}


void CryptData::SetCmt13Encryption()
{
  PN1=0;
  PN2=7;
  PN3=77;
}


void CryptData::Crypt(byte *Data,uint Count,int Method)
{
  if (Method==OLD_DECODE)
    Decode13(Data,Count);
  else
    if (Method==OLD_ENCODE)
      Encode13(Data,Count);
    else
      Crypt15(Data,Count);
}


void CryptData::Encode13(byte *Data,uint Count)
{
  while (Count--)
  {
    PN2+=PN3;
    PN1+=PN2;
    *Data+=PN1;
    Data++;
  }
}


void CryptData::Decode13(byte *Data,uint Count)
{
  while (Count--)
  {
    PN2+=PN3;
    PN1+=PN2;
    *Data-=PN1;
    Data++;
  }
}


void CryptData::Crypt15(byte *Data,uint Count)
{
  while (Count--)
  {
    OldKey[0]+=0x1234;
    OldKey[1]^=CRCTab[(OldKey[0] & 0x1fe)>>1];
    OldKey[2]-=CRCTab[(OldKey[0] & 0x1fe)>>1]>>16;
    OldKey[0]^=OldKey[2];
    OldKey[3]=ror(OldKey[3]&0xffff,1,16)^OldKey[1];
    OldKey[3]=ror(OldKey[3]&0xffff,1,16);
    OldKey[0]^=OldKey[3];
    *Data^=(byte)(OldKey[0]>>8);
    Data++;
  }
}
#endif


