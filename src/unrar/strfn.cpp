#include "rar.hpp"

const char *NullToEmpty(const char *Str)
{
  return(Str==NULL ? "":Str);
}


const wchar *NullToEmpty(const wchar *Str)
{
  return(Str==NULL ? L"":Str);
}




char *IntNameToExt(const char *Name)
{
  static char OutName[NM];
  IntToExt(Name,OutName);
  return(OutName);
}


void ExtToInt(const char *Src,char *Dest)
{
#ifdef _WIN_ALL
  CharToOemA(Src,Dest);
#else
  if (Dest!=Src)
    strcpy(Dest,Src);
#endif
}


void IntToExt(const char *Src,char *Dest)
{
#ifdef _WIN_ALL
  OemToCharA(Src,Dest);
#else
  if (Dest!=Src)
    strcpy(Dest,Src);
#endif
}


char* strlower(char *Str)
{
#ifdef _WIN_ALL
  CharLowerA((LPSTR)Str);
#else
  for (char *ChPtr=Str;*ChPtr;ChPtr++)
    *ChPtr=(char)loctolower(*ChPtr);
#endif
  return(Str);
}


char* strupper(char *Str)
{
#ifdef _WIN_ALL
  CharUpperA((LPSTR)Str);
#else
  for (char *ChPtr=Str;*ChPtr;ChPtr++)
    *ChPtr=(char)loctoupper(*ChPtr);
#endif
  return(Str);
}


int stricomp(const char *Str1,const char *Str2)
{
  char S1[NM*2],S2[NM*2];
  strncpyz(S1,Str1,ASIZE(S1));
  strncpyz(S2,Str2,ASIZE(S2));
  return(strcmp(strupper(S1),strupper(S2)));
}


int strnicomp(const char *Str1,const char *Str2,size_t N)
{
  char S1[NM*2],S2[NM*2];
  strncpyz(S1,Str1,ASIZE(S1));
  strncpyz(S2,Str2,ASIZE(S2));
  return(strncmp(strupper(S1),strupper(S2),N));
}


char* RemoveEOL(char *Str)
{
  for (int I=(int)strlen(Str)-1;I>=0 && (Str[I]=='\r' || Str[I]=='\n' || Str[I]==' ' || Str[I]=='\t');I--)
    Str[I]=0;
  return(Str);
}


char* RemoveLF(char *Str)
{
  for (int I=(int)strlen(Str)-1;I>=0 && (Str[I]=='\r' || Str[I]=='\n');I--)
    Str[I]=0;
  return(Str);
}


wchar* RemoveLF(wchar *Str)
{
  for (int I=(int)wcslen(Str)-1;I>=0 && (Str[I]=='\r' || Str[I]=='\n');I--)
    Str[I]=0;
  return(Str);
}


unsigned char loctolower(unsigned char ch)
{
#ifdef _WIN_ALL
  // Convert to LPARAM first to avoid a warning in 64 bit mode.
  return((int)(LPARAM)CharLowerA((LPSTR)ch));
#else
  return(tolower(ch));
#endif
}


unsigned char loctoupper(unsigned char ch)
{
#ifdef _WIN_ALL
  // Convert to LPARAM first to avoid a warning in 64 bit mode.
  return((int)(LPARAM)CharUpperA((LPSTR)ch));
#else
  return(toupper(ch));
#endif
}


// toupper with English only results if English input is provided.
// It avoids Turkish (small i) -> (big I with dot) conversion problem.
// We do not define 'ch' as 'int' to avoid necessity to cast all
// signed chars passed to this function to unsigned char.
unsigned char etoupper(unsigned char ch)
{
  if (ch=='i')
    return('I');
  return(toupper(ch));
}


// Unicode version of etoupper.
wchar etoupperw(wchar ch)
{
  if (ch=='i')
    return('I');
  return(toupperw(ch));
}


// We do not want to cast every signed char to unsigned when passing to
// isdigit, so we implement the replacement. Shall work for Unicode too.
// If chars are signed, conversion from char to int could generate negative
// values, resulting in undefined behavior in standard isdigit.
bool IsDigit(int ch)
{
  return(ch>='0' && ch<='9');
}


// We do not want to cast every signed char to unsigned when passing to
// isspace, so we implement the replacement. Shall work for Unicode too.
// If chars are signed, conversion from char to int could generate negative
// values, resulting in undefined behavior in standard isspace.
bool IsSpace(int ch)
{
  return(ch==' ' || ch=='\t');
}


// We do not want to cast every signed char to unsigned when passing to
// isalpha, so we implement the replacement. Shall work for Unicode too.
// If chars are signed, conversion from char to int could generate negative
// values, resulting in undefined behavior in standard function.
bool IsAlpha(int ch)
{
  return(ch>='A' && ch<='Z' || ch>='a' && ch<='z');
}




#ifndef SFX_MODULE
uint GetDigits(uint Number)
{
  uint Digits=1;
  while (Number>=10)
  {
    Number/=10;
    Digits++;
  }
  return(Digits);
}
#endif


bool LowAscii(const char *Str)
{
  for (int I=0;Str[I]!=0;I++)
    if ((byte)Str[I]<32 || (byte)Str[I]>127)
      return(false);
  return(true);
}


bool LowAscii(const wchar *Str)
{
  for (int I=0;Str[I]!=0;I++)
  {
    // We convert wchar_t to uint just in case if some compiler
    // uses the signed wchar_t.
    if ((uint)Str[I]<32 || (uint)Str[I]>127)
      return(false);
  }
  return(true);
}




int stricompc(const char *Str1,const char *Str2)
{
#if defined(_UNIX)
  return(strcmp(Str1,Str2));
#else
  return(stricomp(Str1,Str2));
#endif
}


#ifndef SFX_MODULE
int wcsicompc(const wchar *Str1,const wchar *Str2)
{
#if defined(_UNIX)
  return(wcscmp(Str1,Str2));
#else
  return(wcsicomp(Str1,Str2));
#endif
}
#endif


// safe strncpy: copies maxlen-1 max and always returns zero terminated dest
char* strncpyz(char *dest, const char *src, size_t maxlen)
{
  if (maxlen>0)
  {
    strncpy(dest,src,maxlen-1);
    dest[maxlen-1]=0;
  }
  return(dest);
}


// Safe wcsncpy: copies maxlen-1 max and always returns zero terminated dest.
wchar* wcsncpyz(wchar *dest, const wchar *src, size_t maxlen)
{
  if (maxlen>0)
  {
    wcsncpy(dest,src,maxlen-1);
    dest[maxlen-1]=0;
  }
  return(dest);
}


// Safe strncat: resulting dest length cannot exceed maxlen and dest 
// is always zero terminated. Note that 'maxlen' parameter defines the entire
// dest buffer size and is not compatible with standard strncat.
char* strncatz(char* dest, const char* src, size_t maxlen)
{
  size_t Length = strlen(dest);
  if (Length + 1 < maxlen)
    strncat(dest, src, maxlen - Length - 1);
  return dest;
}


// Safe wcsncat: resulting dest length cannot exceed maxlen and dest 
// is always zero terminated. Note that 'maxlen' parameter defines the entire
// dest buffer size and is not compatible with standard wcsncat.
wchar* wcsncatz(wchar* dest, const wchar* src, size_t maxlen)
{
  size_t Length = wcslen(dest);
  if (Length + 1 < maxlen)
    wcsncat(dest, src, maxlen - Length - 1);
  return dest;
}


void itoa(int64 n,char *Str)
{
  char NumStr[50];
  size_t Pos=0;

  do
  {
    NumStr[Pos++]=char(n%10)+'0';
    n=n/10;
  } while (n!=0);

  for (size_t I=0;I<Pos;I++)
    Str[I]=NumStr[Pos-I-1];
  Str[Pos]=0;
}



int64 atoil(const char *Str)
{
  int64 n=0;
  while (*Str>='0' && *Str<='9')
  {
    n=n*10+*Str-'0';
    Str++;
  }
  return(n);
}


void itoa(int64 n,wchar *Str)
{
  wchar NumStr[50];
  size_t Pos=0;

  do
  {
    NumStr[Pos++]=wchar(n%10)+'0';
    n=n/10;
  } while (n!=0);

  for (size_t I=0;I<Pos;I++)
    Str[I]=NumStr[Pos-I-1];
  Str[Pos]=0;
}


int64 atoil(const wchar *Str)
{
  int64 n=0;
  while (*Str>='0' && *Str<='9')
  {
    n=n*10+*Str-'0';
    Str++;
  }
  return(n);
}


const wchar* GetWide(const char *Src)
{
  const size_t MaxLength=NM;
  static wchar StrTable[4][MaxLength];
  static uint StrNum=0;
  if (++StrNum >= ASIZE(StrTable))
    StrNum=0;
  wchar *Str=StrTable[StrNum];
  CharToWide(Src,Str,MaxLength);
  Str[MaxLength-1]=0;
  return(Str);
}


const wchar* GetWide(const char *Src,const wchar *SrcW)
{
  if (SrcW!=NULL && *SrcW!=0)
    return SrcW;
  return GetWide(Src);
}


#ifdef _WIN_ALL
// Parse string containing parameters separated with spaces.
// Support quote marks. Param can be NULL to return the pointer to next
// parameter, which can be used to estimate the buffer size for Param.
const wchar* GetCmdParam(const wchar *CmdLine,wchar *Param,size_t MaxSize)
{
  while (IsSpace(*CmdLine))
    CmdLine++;
  if (*CmdLine==0)
    return NULL;

  size_t ParamSize=0;
  bool Quote=false;
  while (*CmdLine!=0 && (Quote || !IsSpace(*CmdLine)))
  {
    if (*CmdLine=='\"')
    {
      if (CmdLine[1]=='\"')
      {
        // Insert the quote character instead of two adjoining quote characters.
        if (Param!=NULL && ParamSize<MaxSize-1)
          Param[ParamSize++]='\"';
        CmdLine++;
      }
      else
        Quote=!Quote;
    }
    else
      if (Param!=NULL && ParamSize<MaxSize-1)
        Param[ParamSize++]=*CmdLine;
    CmdLine++;
  }
  if (Param!=NULL)
    Param[ParamSize]=0;
  return CmdLine;
}
#endif
