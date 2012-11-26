#include "rar.hpp"

static bool IsUnicode(byte *Data,int Size);

bool ReadTextFile(
  const char *Name,
  const wchar *NameW,
  StringList *List,
  bool Config,
  bool AbortOnError,
  RAR_CHARSET SrcCharset,
  bool Unquote,
  bool SkipComments,
  bool ExpandEnvStr)
{
  char FileName[NM];
  *FileName=0;
  if (Name!=NULL)
    if (Config)
      GetConfigName(Name,FileName,true);
    else
      strcpy(FileName,Name);

  wchar FileNameW[NM];
  *FileNameW=0;

#ifdef _WIN_ALL
  if (NameW!=NULL)
    if (Config)
      GetConfigName(NameW,FileNameW,true);
    else
      wcscpy(FileNameW,NameW);
#endif

  File SrcFile;
  if (FileName!=NULL && *FileName!=0 || FileNameW!=NULL && *FileNameW!=0)
  {
    bool OpenCode=AbortOnError ? SrcFile.WOpen(FileName,FileNameW):SrcFile.Open(FileName,FileNameW,0);

    if (!OpenCode)
    {
      if (AbortOnError)
        ErrHandler.Exit(RARX_OPEN);
      return(false);
    }
  }
  else
    SrcFile.SetHandleType(FILE_HANDLESTD);

  unsigned int DataSize=0,ReadSize;
  const int ReadBlock=1024;
  Array<char> Data(ReadBlock+5);
  while ((ReadSize=SrcFile.Read(&Data[DataSize],ReadBlock))!=0)
  {
    DataSize+=ReadSize;
    Data.Add(ReadSize);
  }

  memset(&Data[DataSize],0,5);

  if (SrcCharset==RCH_UNICODE ||
      SrcCharset==RCH_DEFAULT && IsUnicode((byte *)&Data[0],DataSize))
  {
    // Unicode in native system format, can be more than 2 bytes per character.
    Array<wchar> DataW(Data.Size()/2+1);
    for (size_t I=2;I<Data.Size()-1;I+=2)
    {
      // Need to convert Data to (byte) first to prevent the sign extension
      // to higher bytes.
      DataW[(I-2)/2]=(wchar)((byte)Data[I])+(wchar)((byte)Data[I+1])*256;
    }

    wchar *CurStr=&DataW[0];
    Array<char> AnsiName;

    while (*CurStr!=0)
    {
      wchar *NextStr=CurStr,*CmtPtr=NULL;
      while (*NextStr!='\r' && *NextStr!='\n' && *NextStr!=0)
      {
        if (SkipComments && NextStr[0]=='/' && NextStr[1]=='/')
        {
          *NextStr=0;
          CmtPtr=NextStr;
        }
        NextStr++;
      }
      *NextStr=0;
      for (wchar *SpacePtr=(CmtPtr ? CmtPtr:NextStr)-1;SpacePtr>=CurStr;SpacePtr--)
      {
        if (*SpacePtr!=' ' && *SpacePtr!='\t')
          break;
        *SpacePtr=0;
      }
      if (*CurStr)
      {
        // Length and AddSize must be defined as signed, because AddSize
        // can be negative.
        int Length=(int)wcslen(CurStr);
        int AddSize=4*(Length-(int)AnsiName.Size()+1);

        if (AddSize>0)
          AnsiName.Add(AddSize);
        if (Unquote && *CurStr=='\"' && CurStr[Length-1]=='\"')
        {
          CurStr[Length-1]=0;
          CurStr++;
        }
        WideToChar(CurStr,&AnsiName[0],AnsiName.Size());

        bool Expanded=false;
#if defined(_WIN_ALL) && !defined(_WIN_CE)
        if (ExpandEnvStr && *CurStr=='%')
        {
          // Expanding environment variables in Windows version.

          char ExpName[NM];
          wchar ExpNameW[NM];
          *ExpNameW=0;
          int ret,retw=1;
          ret=ExpandEnvironmentStringsA(&AnsiName[0],ExpName,ASIZE(ExpName));
          if (ret!=0 && WinNT())
            retw=ExpandEnvironmentStringsW(CurStr,ExpNameW,ASIZE(ExpNameW));
          Expanded=ret!=0 && ret<ASIZE(ExpName) &&
                   retw!=0 && retw<ASIZE(ExpNameW);
          if (Expanded)
            List->AddString(ExpName,ExpNameW);
        }
#endif
        if (!Expanded)
          List->AddString(&AnsiName[0],CurStr);
      }
      CurStr=NextStr+1;
      while (*CurStr=='\r' || *CurStr=='\n')
        CurStr++;
    }
  }
  else
  {
    char *CurStr=&Data[0];
    while (*CurStr!=0)
    {
      char *NextStr=CurStr,*CmtPtr=NULL;
      while (*NextStr!='\r' && *NextStr!='\n' && *NextStr!=0)
      {
        if (SkipComments && NextStr[0]=='/' && NextStr[1]=='/')
        {
          *NextStr=0;
          CmtPtr=NextStr;
        }
        NextStr++;
      }
      *NextStr=0;
      for (char *SpacePtr=(CmtPtr ? CmtPtr:NextStr)-1;SpacePtr>=CurStr;SpacePtr--)
      {
        if (*SpacePtr!=' ' && *SpacePtr!='\t')
          break;
        *SpacePtr=0;
      }
      if (*CurStr)
      {
        if (Unquote && *CurStr=='\"')
        {
          size_t Length=strlen(CurStr);
          if (CurStr[Length-1]=='\"')
          {
            CurStr[Length-1]=0;
            CurStr++;
          }
        }
#if defined(_WIN_ALL)
        if (SrcCharset==RCH_OEM)
          OemToCharA(CurStr,CurStr);
#endif

        bool Expanded=false;
#if defined(_WIN_ALL) && !defined(_WIN_CE)
        if (ExpandEnvStr && *CurStr=='%')
        {
          // Expanding environment variables in Windows version.
          char ExpName[NM];
          int ret=ExpandEnvironmentStringsA(CurStr,ExpName,ASIZE(ExpName));
          Expanded=ret!=0 && ret<ASIZE(ExpName);
          if (Expanded)
            List->AddString(ExpName);
        }
#endif
        if (!Expanded)
          List->AddString(CurStr);
      }
      CurStr=NextStr+1;
      while (*CurStr=='\r' || *CurStr=='\n')
        CurStr++;
    }
  }
  return(true);
}


bool IsUnicode(byte *Data,int Size)
{
  if (Size<4 || Data[0]!=0xff || Data[1]!=0xfe)
    return(false);
  for (int I=2;I<Size;I++)
    if (Data[I]<32 && Data[I]!='\r' && Data[I]!='\n')
      return(true);
  return(false);
}
