#include "rar.hpp"

#if defined(_EMX) && !defined(_DJGPP)
#include "unios2.cpp"
#endif

bool WideToChar(const wchar *Src,char *Dest,size_t DestSize)
{
  bool RetCode=true;
  *Dest=0; // Set 'Dest' to zero just in case the conversion will fail.

#ifdef _WIN_ALL
  if (WideCharToMultiByte(CP_ACP,0,Src,-1,Dest,(int)DestSize,NULL,NULL)==0)
    RetCode=false;

#elif defined(_APPLE)
  WideToUtf(Src,Dest,DestSize);

#elif defined(MBFUNCTIONS)
  size_t ResultingSize=wcstombs(Dest,Src,DestSize);
  if (ResultingSize==(size_t)-1)
    RetCode=false;
  if (ResultingSize==0 && *Src!=0)
    RetCode=false;

  if ((!RetCode || *Dest==0 && *Src!=0) && DestSize>NM && wcslen(Src)<NM)
  {
    /* Workaround for strange Linux Unicode functions bug.
       Some of wcstombs and mbstowcs implementations in some situations
       (we are yet to find out what it depends on) can return an empty
       string and success code if buffer size value is too large.
    */
    return(WideToChar(Src,Dest,NM));
  }

#else
  if (UnicodeEnabled())
  {
#if defined(_EMX) && !defined(_DJGPP)
    int len=Min(wcslen(Src)+1,DestSize-1);
    if (uni_fromucs((UniChar*)Src,len,Dest,(size_t*)&DestSize)==-1 ||
        DestSize>len*2)
      RetCode=false;
    Dest[DestSize]=0;
#endif
  }
  else
    for (int I=0;I<DestSize;I++)
    {
      Dest[I]=(char)Src[I];
      if (Src[I]==0)
        break;
    }
#endif

  // We tried to return the empty string if conversion is failed,
  // but it does not work well. WideCharToMultiByte returns 'failed' code
  // and partially converted string even if we wanted to convert only a part
  // of string and passed DestSize smaller than required for fully converted
  // string. Such call is the valid behavior in RAR code and we do not expect
  // the empty string in this case.

  return(RetCode);
}


bool CharToWide(const char *Src,wchar *Dest,size_t DestSize)
{
  bool RetCode=true;
  *Dest=0; // Set 'Dest' to zero just in case the conversion will fail.

#ifdef _WIN_ALL
  if (MultiByteToWideChar(CP_ACP,0,Src,-1,Dest,(int)DestSize)==0)
    RetCode=false;

#elif defined(_APPLE)
  UtfToWide(Src,Dest,DestSize);

#elif defined(MBFUNCTIONS)
  size_t ResultingSize=mbstowcs(Dest,Src,DestSize);
  if (ResultingSize==(size_t)-1)
    RetCode=false;
  if (ResultingSize==0 && *Src!=0)
    RetCode=false;

  if ((!RetCode || *Dest==0 && *Src!=0) && DestSize>NM && strlen(Src)<NM)
  {
    /* Workaround for strange Linux Unicode functions bug.
       Some of wcstombs and mbstowcs implementations in some situations
       (we are yet to find out what it depends on) can return an empty
       string and success code if buffer size value is too large.
    */
    return(CharToWide(Src,Dest,NM));
  }
#else
  if (UnicodeEnabled())
  {
#if defined(_EMX) && !defined(_DJGPP)
    int len=Min(strlen(Src)+1,DestSize-1);
    if (uni_toucs((char*)Src,len,(UniChar*)Dest,(size_t*)&DestSize)==-1 ||
        DestSize>len)
      DestSize=0;
    RetCode=false;
#endif
  }
  else
    for (int I=0;I<DestSize;I++)
    {
      Dest[I]=(wchar_t)Src[I];
      if (Src[I]==0)
        break;
    }
#endif

  // We tried to return the empty string if conversion is failed,
  // but it does not work well. MultiByteToWideChar returns 'failed' code
  // even if we wanted to convert only a part of string and passed DestSize
  // smaller than required for fully converted string. Such call is the valid
  // behavior in RAR code and we do not expect the empty string in this case.

  return(RetCode);
}


// SrcSize is in wide characters, not in bytes.
byte* WideToRaw(const wchar *Src,byte *Dest,size_t SrcSize)
{
  for (size_t I=0;I<SrcSize;I++,Src++)
  {
    Dest[I*2]=(byte)*Src;
    Dest[I*2+1]=(byte)(*Src>>8);
    if (*Src==0)
      break;
  }
  return(Dest);
}


wchar* RawToWide(const byte *Src,wchar *Dest,size_t DestSize)
{
  for (size_t I=0;I<DestSize;I++)
    if ((Dest[I]=Src[I*2]+(Src[I*2+1]<<8))==0)
      break;
  return(Dest);
}


void WideToUtf(const wchar *Src,char *Dest,size_t DestSize)
{
  long dsize=(long)DestSize;
  dsize--;
  while (*Src!=0 && --dsize>=0)
  {
    uint c=*(Src++);
    if (c<0x80)
      *(Dest++)=c;
    else
      if (c<0x800 && --dsize>=0)
      {
        *(Dest++)=(0xc0|(c>>6));
        *(Dest++)=(0x80|(c&0x3f));
      }
      else
        if (c<0x10000 && (dsize-=2)>=0)
        {
          *(Dest++)=(0xe0|(c>>12));
          *(Dest++)=(0x80|((c>>6)&0x3f));
          *(Dest++)=(0x80|(c&0x3f));
        }
        else
          if (c < 0x200000 && (dsize-=3)>=0)
          {
            *(Dest++)=(0xf0|(c>>18));
            *(Dest++)=(0x80|((c>>12)&0x3f));
            *(Dest++)=(0x80|((c>>6)&0x3f));
            *(Dest++)=(0x80|(c&0x3f));
          }
  }
  *Dest=0;
}


// Dest can be NULL if we only need to check validity of Src.
bool UtfToWide(const char *Src,wchar *Dest,size_t DestSize)
{
  bool Success=true;
  long dsize=(long)DestSize;
  dsize--;
  while (*Src!=0)
  {
    uint c=(byte)*(Src++),d;
    if (c<0x80)
      d=c;
    else
      if ((c>>5)==6)
      {
        if ((*Src&0xc0)!=0x80)
          break;
        d=((c&0x1f)<<6)|(*Src&0x3f);
        Src++;
      }
      else
        if ((c>>4)==14)
        {
          if ((Src[0]&0xc0)!=0x80 || (Src[1]&0xc0)!=0x80)
            break;
          d=((c&0xf)<<12)|((Src[0]&0x3f)<<6)|(Src[1]&0x3f);
          Src+=2;
        }
        else
          if ((c>>3)==30)
          {
            if ((Src[0]&0xc0)!=0x80 || (Src[1]&0xc0)!=0x80 || (Src[2]&0xc0)!=0x80)
              break;
            d=((c&7)<<18)|((Src[0]&0x3f)<<12)|((Src[1]&0x3f)<<6)|(Src[2]&0x3f);
            Src+=3;
          }
          else
          {
            // Skip bad character, but continue processing, so we can handle
            // archived UTF-8 file names even if one of characters is corrupt.
            Success=false;
            continue;
          }
    if (Dest!=NULL && --dsize<0)
      break;
    if (d>0xffff)
    {
      if (Dest!=NULL && --dsize<0)
        break;
      if (d>0x10ffff)
      {
        // UTF-8 is restricted by RFC 3629 to end at 0x10ffff.
        Success=false;
        continue;
      }
      if (Dest!=NULL)
      {
        *(Dest++)=((d-0x10000)>>10)+0xd800;
        *(Dest++)=(d&0x3ff)+0xdc00;
      }
    }
    else
      if (Dest!=NULL)
        *(Dest++)=d;
  }
  if (Dest!=NULL)
    *Dest=0;
  return Success;
}


bool UnicodeEnabled()
{
#ifdef UNICODE_SUPPORTED
  #ifdef _EMX
    return(uni_ready);
  #else
    return(true);
  #endif
#else
  return(false);
#endif
}


int wcsicomp(const wchar *s1,const wchar *s2)
{
  char Ansi1[NM*sizeof(wchar)],Ansi2[NM*sizeof(wchar)];
  WideToChar(s1,Ansi1,sizeof(Ansi1));
  WideToChar(s2,Ansi2,sizeof(Ansi2));
  return(stricomp(Ansi1,Ansi2));
}


static int wcsnicomp_w2c(const wchar *s1,const wchar *s2,size_t n)
{
  char Ansi1[NM*2],Ansi2[NM*2];
  GetAsciiName(s1,Ansi1,ASIZE(Ansi1));
  GetAsciiName(s2,Ansi2,ASIZE(Ansi2));
  return(stricomp(Ansi1,Ansi2));
}


int wcsnicomp(const wchar *s1,const wchar *s2,size_t n)
{
  return(wcsnicomp_w2c(s1,s2,n));
}


#ifndef SFX_MODULE
wchar* wcslower(wchar *Str)
{
  for (wchar *ChPtr=Str;*ChPtr;ChPtr++)
    if (*ChPtr<128)
      *ChPtr=loctolower((byte)*ChPtr);
  return(Str);
}
#endif


#ifndef SFX_MODULE
wchar* wcsupper(wchar *Str)
{
  for (wchar *ChPtr=Str;*ChPtr;ChPtr++)
    if (*ChPtr<128)
      *ChPtr=loctoupper((byte)*ChPtr);
  return(Str);
}
#endif


int toupperw(int ch)
{
  return((ch<128) ? loctoupper(ch):ch);
}


int tolowerw(int ch)
{
#ifdef _WIN_ALL
  return((int)(LPARAM)CharLowerW((wchar *)(uint)ch));
#else
  return((ch<128) ? loctolower(ch):ch);
#endif
}


int atoiw(const wchar *s)
{
  int n=0;
  while (*s>='0' && *s<='9')
  {
    n=n*10+(*s-'0');
    s++;
  }
  return(n);
}


#ifdef DBCS_SUPPORTED
SupportDBCS gdbcs;

SupportDBCS::SupportDBCS()
{
  Init();
}


void SupportDBCS::Init()
{
  CPINFO CPInfo;
  GetCPInfo(CP_ACP,&CPInfo);
  DBCSMode=CPInfo.MaxCharSize > 1;
  for (uint I=0;I<ASIZE(IsLeadByte);I++)
    IsLeadByte[I]=IsDBCSLeadByte(I)!=0;
}


char* SupportDBCS::charnext(const char *s)
{
  // Zero cannot be the trail byte. So if next byte after the lead byte
  // is 0, the string is corrupt and we'll better return the pointer to 0,
  // to break string processing loops.
  return (char *)(IsLeadByte[(byte)*s] && s[1]!=0 ? s+2:s+1);
}


size_t SupportDBCS::strlend(const char *s)
{
  size_t Length=0;
  while (*s!=0)
  {
    if (IsLeadByte[(byte)*s])
      s+=2;
    else
      s++;
    Length++;
  }
  return(Length);
}


char* SupportDBCS::strchrd(const char *s, int c)
{
  while (*s!=0)
    if (IsLeadByte[(byte)*s])
      s+=2;
    else
      if (*s==c)
        return((char *)s);
      else
        s++;
  return(NULL);
}


void SupportDBCS::copychrd(char *dest,const char *src)
{
  dest[0]=src[0];
  if (IsLeadByte[(byte)src[0]])
    dest[1]=src[1];
}


char* SupportDBCS::strrchrd(const char *s, int c)
{
  const char *found=NULL;
  while (*s!=0)
    if (IsLeadByte[(byte)*s])
      s+=2;
    else
    {
      if (*s==c)
        found=s;
      s++;
    }
  return((char *)found);
}
#endif
