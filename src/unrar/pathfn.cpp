#include "rar.hpp"

char* PointToName(const char *Path)
{
  const char *Found=NULL;
  for (const char *s=Path;*s!=0;s=charnext(s))
    if (IsPathDiv(*s))
      Found=(char*)(s+1);
  if (Found!=NULL)
    return((char*)Found);
  return (char*)((*Path && IsDriveDiv(Path[1]) && charnext(Path)==Path+1) ? Path+2:Path);
}


wchar* PointToName(const wchar *Path)
{
  for (int I=(int)wcslen(Path)-1;I>=0;I--)
    if (IsPathDiv(Path[I]))
      return (wchar*)&Path[I+1];
  return (wchar*)((*Path && IsDriveDiv(Path[1])) ? Path+2:Path);
}


char* PointToLastChar(const char *Path)
{
  for (const char *s=Path,*p=Path;;p=s,s=charnext(s))
    if (*s==0)
      return((char *)p);
}


wchar* PointToLastChar(const wchar *Path)
{
  size_t Length=wcslen(Path);
  return((wchar*)(Length>0 ? Path+Length-1:Path));
}


char* ConvertPath(const char *SrcPath,char *DestPath)
{
  const char *DestPtr=SrcPath;

  // Prevent \..\ in any part of path string.
  for (const char *s=DestPtr;*s!=0;s++)
    if (IsPathDiv(s[0]) && s[1]=='.' && s[2]=='.' && IsPathDiv(s[3]))
      DestPtr=s+4;

  // Remove <d>:\ and any sequence of . and \ in the beginning of path string.
  while (*DestPtr!=0)
  {
    const char *s=DestPtr;
    if (s[0] && IsDriveDiv(s[1]))
      s+=2;
    else
      if (s[0]=='\\' && s[1]=='\\')
      {
        const char *Slash=strchr(s+2,'\\');
        if (Slash!=NULL && (Slash=strchr(Slash+1,'\\'))!=NULL)
          s=Slash+1;
      }
    for (const char *t=s;*t!=0;t++)
      if (IsPathDiv(*t))
        s=t+1;
      else
        if (*t!='.')
          break;
    if (s==DestPtr)
      break;
    DestPtr=s;
  }

  // Code above does not remove last "..", doing here.
  if (DestPtr[0]=='.' && DestPtr[1]=='.' && DestPtr[2]==0)
    DestPtr+=2;

  if (DestPath!=NULL)
  {
    // SrcPath and DestPath can point to same memory area,
    // so we use the temporary buffer for copying.
    char TmpStr[NM];
    strncpyz(TmpStr,DestPtr,ASIZE(TmpStr));
    strcpy(DestPath,TmpStr);
  }
  return((char *)DestPtr);
}


wchar* ConvertPath(const wchar *SrcPath,wchar *DestPath)
{
  const wchar *DestPtr=SrcPath;

  // Prevent \..\ in any part of path string.
  for (const wchar *s=DestPtr;*s!=0;s++)
    if (IsPathDiv(s[0]) && s[1]=='.' && s[2]=='.' && IsPathDiv(s[3]))
      DestPtr=s+4;

  // Remove <d>:\ and any sequence of . and \ in the beginning of path string.
  while (*DestPtr!=0)
  {
    const wchar *s=DestPtr;
    if (s[0] && IsDriveDiv(s[1]))
      s+=2;
    if (s[0]=='\\' && s[1]=='\\')
    {
      const wchar *Slash=wcschr(s+2,'\\');
      if (Slash!=NULL && (Slash=wcschr(Slash+1,'\\'))!=NULL)
        s=Slash+1;
    }
    for (const wchar *t=s;*t!=0;t++)
      if (IsPathDiv(*t))
        s=t+1;
      else
        if (*t!='.')
          break;
    if (s==DestPtr)
      break;
    DestPtr=s;
  }

  // Code above does not remove last "..", doing here.
  if (DestPtr[0]=='.' && DestPtr[1]=='.' && DestPtr[2]==0)
    DestPtr+=2;
  
  if (DestPath!=NULL)
  {
    // SrcPath and DestPath can point to same memory area,
    // so we use the temporary buffer for copying.
    wchar TmpStr[NM];
    wcsncpyz(TmpStr,DestPtr,ASIZE(TmpStr));
    wcscpy(DestPath,TmpStr);
  }
  return((wchar *)DestPtr);
}


void SetExt(char *Name,const char *NewExt)
{
  char *Dot=GetExt(Name);
  if (NewExt==NULL)
  {
    if (Dot!=NULL)
      *Dot=0;
  }
  else
    if (Dot==NULL)
    {
      strcat(Name,".");
      strcat(Name,NewExt);
    }
    else
      strcpy(Dot+1,NewExt);
}


void SetExt(wchar *Name,const wchar *NewExt)
{
  if (Name==NULL || *Name==0)
    return;
  wchar *Dot=GetExt(Name);
  if (NewExt==NULL)
  {
    if (Dot!=NULL)
      *Dot=0;
  }
  else
    if (Dot==NULL)
    {
      wcscat(Name,L".");
      wcscat(Name,NewExt);
    }
    else
      wcscpy(Dot+1,NewExt);
}


#ifndef SFX_MODULE
void SetSFXExt(char *SFXName)
{
#ifdef _UNIX
  SetExt(SFXName,"sfx");
#endif

#if defined(_WIN_ALL) || defined(_EMX)
  SetExt(SFXName,"exe");
#endif
}
#endif


#ifndef SFX_MODULE
void SetSFXExt(wchar *SFXName)
{
  if (SFXName==NULL || *SFXName==0)
    return;

#ifdef _UNIX
  SetExt(SFXName,L"sfx");
#endif

#if defined(_WIN_ALL) || defined(_EMX)
  SetExt(SFXName,L"exe");
#endif
}
#endif


char *GetExt(const char *Name)
{
  return(Name==NULL ? NULL:strrchrd(PointToName(Name),'.'));
}


wchar *GetExt(const wchar *Name)
{
  return(Name==NULL ? NULL:wcsrchr(PointToName(Name),'.'));
}


// 'Ext' is an extension without the leading dot, like "rar".
bool CmpExt(const char *Name,const char *Ext)
{
  char *NameExt=GetExt(Name);
  return(NameExt!=NULL && stricomp(NameExt+1,Ext)==0);
}


// 'Ext' is an extension without the leading dot, like L"rar".
bool CmpExt(const wchar *Name,const wchar *Ext)
{
  wchar *NameExt=GetExt(Name);
  return(NameExt!=NULL && wcsicomp(NameExt+1,Ext)==0);
}


bool IsWildcard(const char *Str,const wchar *StrW)
{
  if (StrW!=NULL && *StrW!=0)
    return(wcspbrk(StrW,L"*?")!=NULL);
  return(Str==NULL ? false:strpbrk(Str,"*?")!=NULL);
}


bool IsPathDiv(int Ch)
{
#if defined(_WIN_ALL) || defined(_EMX)
  return(Ch=='\\' || Ch=='/');
#else
  return(Ch==CPATHDIVIDER);
#endif
}


bool IsDriveDiv(int Ch)
{
#ifdef _UNIX
  return(false);
#else
  return(Ch==':');
#endif
}


int GetPathDisk(const char *Path)
{
  if (IsDiskLetter(Path))
    return(etoupper(*Path)-'A');
  else
    return(-1);
}


int GetPathDisk(const wchar *Path)
{
  if (IsDiskLetter(Path))
    return(etoupperw(*Path)-'A');
  else
    return(-1);
}


void AddEndSlash(char *Path)
{
  char *LastChar=PointToLastChar(Path);
  if (*LastChar!=0 && *LastChar!=CPATHDIVIDER)
    strcat(LastChar,PATHDIVIDER);
}


void AddEndSlash(wchar *Path)
{
  size_t Length=wcslen(Path);
  if (Length>0 && Path[Length-1]!=CPATHDIVIDER)
    wcscat(Path,PATHDIVIDERW);
}


// Returns file path including the trailing path separator symbol.
void GetFilePath(const char *FullName,char *Path,int MaxLength)
{
  size_t PathLength=Min(MaxLength-1,PointToName(FullName)-FullName);
  strncpy(Path,FullName,PathLength);
  Path[PathLength]=0;
}


// Returns file path including the trailing path separator symbol.
void GetFilePath(const wchar *FullName,wchar *Path,int MaxLength)
{
  size_t PathLength=Min(MaxLength-1,PointToName(FullName)-FullName);
  wcsncpy(Path,FullName,PathLength);
  Path[PathLength]=0;
}


// Removes name and returns file path without the trailing
// path separator symbol.
void RemoveNameFromPath(char *Path)
{
  char *Name=PointToName(Path);
  if (Name>=Path+2 && (!IsDriveDiv(Path[1]) || Name>=Path+4))
    Name--;
  *Name=0;
}


// Removes name and returns file path without the trailing
// path separator symbol.
void RemoveNameFromPath(wchar *Path)
{
  wchar *Name=PointToName(Path);
  if (Name>=Path+2 && (!IsDriveDiv(Path[1]) || Name>=Path+4))
    Name--;
  *Name=0;
}


#if defined(_WIN_ALL) && !defined(_WIN_CE) && !defined(SFX_MODULE)
void GetAppDataPath(char *Path)
{
  LPMALLOC g_pMalloc;
  SHGetMalloc(&g_pMalloc);
  LPITEMIDLIST ppidl;
  *Path=0;
  bool Success=false;
  if (SHGetSpecialFolderLocation(NULL,CSIDL_APPDATA,&ppidl)==NOERROR &&
      SHGetPathFromIDListA(ppidl,Path) && *Path!=0)
  {
    AddEndSlash(Path);
    strcat(Path,"WinRAR");
    Success=FileExist(Path) || MakeDir(Path,NULL,false,0)==MKDIR_SUCCESS;
  }
  if (!Success)
  {
    GetModuleFileNameA(NULL,Path,NM);
    RemoveNameFromPath(Path);
  }
  g_pMalloc->Free(ppidl);
}
#endif


#if defined(_WIN_ALL) && !defined(_WIN_CE) && !defined(SFX_MODULE)
void GetAppDataPath(wchar *Path)
{
  LPMALLOC g_pMalloc;
  SHGetMalloc(&g_pMalloc);
  LPITEMIDLIST ppidl;
  *Path=0;
  bool Success=false;
  if (SHGetSpecialFolderLocation(NULL,CSIDL_APPDATA,&ppidl)==NOERROR &&
      SHGetPathFromIDListW(ppidl,Path) && *Path!=0)
  {
    AddEndSlash(Path);
    wcscat(Path,L"WinRAR");
    Success=FileExist(NULL,Path) || MakeDir(NULL,Path,false,0)==MKDIR_SUCCESS;
  }
  if (!Success)
  {
    GetModuleFileNameW(NULL,Path,NM);
    RemoveNameFromPath(Path);
  }
  g_pMalloc->Free(ppidl);
}
#endif


#if defined(_WIN_ALL) && !defined(_WIN_CE) && !defined(SFX_MODULE)
void GetRarDataPath(char *Path)
{
  *Path=0;

  HKEY hKey;
  if (RegOpenKeyExA(HKEY_CURRENT_USER,"Software\\WinRAR\\Paths",0,
                   KEY_QUERY_VALUE,&hKey)==ERROR_SUCCESS)
  {
    DWORD DataSize=NM,Type;
    RegQueryValueExA(hKey,"AppData",0,&Type,(BYTE *)Path,&DataSize);
    RegCloseKey(hKey);
  }

  if (*Path==0 || !FileExist(Path))
    GetAppDataPath(Path);
}
#endif


#if defined(_WIN_ALL) && !defined(_WIN_CE) && !defined(SFX_MODULE)
void GetRarDataPath(wchar *Path)
{
  *Path=0;

  HKEY hKey;
  if (RegOpenKeyExW(HKEY_CURRENT_USER,L"Software\\WinRAR\\Paths",0,
                    KEY_QUERY_VALUE,&hKey)==ERROR_SUCCESS)
  {
    DWORD DataSize=NM,Type;
    RegQueryValueExW(hKey,L"AppData",0,&Type,(BYTE *)Path,&DataSize);
    RegCloseKey(hKey);
  }

  if (*Path==0 || !FileExist(NULL,Path))
    GetAppDataPath(Path);
}
#endif


#ifndef SFX_MODULE
bool EnumConfigPaths(char *Path,int Number)
{
#ifdef _EMX
  static char RARFileName[NM];
  if (Number==-1)
    strcpy(RARFileName,Path);
  if (Number!=0)
    return(false);
#ifndef _DJGPP
  if (_osmode==OS2_MODE)
  {
    PTIB ptib;
    PPIB ppib;
    DosGetInfoBlocks(&ptib, &ppib);
    DosQueryModuleName(ppib->pib_hmte,NM,Path);
  }
  else
#endif
    strcpy(Path,RARFileName);
  RemoveNameFromPath(Path);
  return(true);
#elif defined(_UNIX)
  static const char *AltPath[]={
    "/etc","/etc/rar","/usr/lib","/usr/local/lib","/usr/local/etc"
  };
  if (Number==0)
  {
    char *EnvStr=getenv("HOME");
    strncpy(Path, (EnvStr==NULL) ? AltPath[0] : EnvStr, NM-1);
    Path[NM-1]=0;
    return(true);
  }
  Number--;
  if (Number<0 || Number>=sizeof(AltPath)/sizeof(AltPath[0]))
    return(false);
  strcpy(Path,AltPath[Number]);
  return(true);
#elif defined(_WIN_ALL)

  if (Number<0 || Number>1)
    return(false);
  if (Number==0)
    GetRarDataPath(Path);
  else
  {
    GetModuleFileNameA(NULL,Path,NM);
    RemoveNameFromPath(Path);
  }
  return(true);

#else
  return(false);
#endif
}
#endif


#if defined(_WIN_ALL) && !defined(SFX_MODULE)
bool EnumConfigPaths(wchar *Path,int Number)
{
  if (Number<0 || Number>1)
    return(false);
  if (Number==0)
    GetRarDataPath(Path);
  else
  {
    GetModuleFileNameW(NULL,Path,NM);
    RemoveNameFromPath(Path);
  }
  return(true);
}
#endif


#ifndef SFX_MODULE
void GetConfigName(const char *Name,char *FullName,bool CheckExist)
{
  *FullName=0;
  for (int I=0;EnumConfigPaths(FullName,I);I++)
  {
    AddEndSlash(FullName);
    strcat(FullName,Name);
    if (!CheckExist || WildFileExist(FullName))
      break;
  }
}
#endif


#if defined(_WIN_ALL) && !defined(SFX_MODULE)
void GetConfigName(const wchar *Name,wchar *FullName,bool CheckExist)
{
  *FullName=0;
  for (int I=0;EnumConfigPaths(FullName,I);I++)
  {
    AddEndSlash(FullName);
    wcscat(FullName,Name);
    if (!CheckExist || WildFileExist(NULL,FullName))
      break;
  }
}
#endif


// Returns a pointer to rightmost digit of volume number.
char* GetVolNumPart(char *ArcName)
{
  // Pointing to last name character.
  char *ChPtr=ArcName+strlen(ArcName)-1;

  // Skipping the archive extension.
  while (!IsDigit(*ChPtr) && ChPtr>ArcName)
    ChPtr--;

  // Skipping the numeric part of name.
  char *NumPtr=ChPtr;
  while (IsDigit(*NumPtr) && NumPtr>ArcName)
    NumPtr--;

  // Searching for first numeric part in names like name.part##of##.rar.
  // Stop search on the first dot.
  while (NumPtr>ArcName && *NumPtr!='.')
  {
    if (IsDigit(*NumPtr))
    {
      // Validate the first numeric part only if it has a dot somewhere 
      // before it.
      char *Dot=strchrd(PointToName(ArcName),'.');
      if (Dot!=NULL && Dot<NumPtr)
        ChPtr=NumPtr;
      break;
    }
    NumPtr--;
  }
  return(ChPtr);
}


// Returns a pointer to rightmost digit of volume number.
wchar* GetVolNumPart(wchar *ArcName)
{
  // Pointing to last name character.
  wchar *ChPtr=ArcName+wcslen(ArcName)-1;

  // Skipping the archive extension.
  while (!IsDigit(*ChPtr) && ChPtr>ArcName)
    ChPtr--;

  // Skipping the numeric part of name.
  wchar *NumPtr=ChPtr;
  while (IsDigit(*NumPtr) && NumPtr>ArcName)
    NumPtr--;

  // Searching for first numeric part in names like name.part##of##.rar.
  // Stop search on the first dot.
  while (NumPtr>ArcName && *NumPtr!='.')
  {
    if (IsDigit(*NumPtr))
    {
      // Validate the first numeric part only if it has a dot somewhere 
      // before it.
      wchar *Dot=wcschr(PointToName(ArcName),'.');
      if (Dot!=NULL && Dot<NumPtr)
        ChPtr=NumPtr;
      break;
    }
    NumPtr--;
  }
  return(ChPtr);
}


void NextVolumeName(char *ArcName,wchar *ArcNameW,uint MaxLength,bool OldNumbering)
{
  if (ArcName!=NULL && *ArcName!=0)
  {
    char *ChPtr;
    if ((ChPtr=GetExt(ArcName))==NULL)
    {
      strncatz(ArcName,".rar",MaxLength);
      ChPtr=GetExt(ArcName);
    }
    else
      if (ChPtr[1]==0 && strlen(ArcName)<MaxLength-3 || stricomp(ChPtr+1,"exe")==0 || stricomp(ChPtr+1,"sfx")==0)
        strcpy(ChPtr+1,"rar");
    if (!OldNumbering)
    {
      ChPtr=GetVolNumPart(ArcName);

      while ((++(*ChPtr))=='9'+1)
      {
        *ChPtr='0';
        ChPtr--;
        if (ChPtr<ArcName || !IsDigit(*ChPtr))
        {
          for (char *EndPtr=ArcName+strlen(ArcName);EndPtr!=ChPtr;EndPtr--)
            *(EndPtr+1)=*EndPtr;
          *(ChPtr+1)='1';
          break;
        }
      }
    }
    else
      if (!IsDigit(*(ChPtr+2)) || !IsDigit(*(ChPtr+3)))
        strcpy(ChPtr+2,"00");
      else
      {
        ChPtr+=3;
        while ((++(*ChPtr))=='9'+1)
          if (*(ChPtr-1)=='.')
          {
            *ChPtr='A';
            break;
          }
          else
          {
            *ChPtr='0';
            ChPtr--;
          }
      }
  }

  if (ArcNameW!=NULL && *ArcNameW!=0)
  {
    wchar *ChPtr;
    if ((ChPtr=GetExt(ArcNameW))==NULL)
    {
      wcsncatz(ArcNameW,L".rar",MaxLength);
      ChPtr=GetExt(ArcNameW);
    }
    else
      if (ChPtr[1]==0 && wcslen(ArcNameW)<MaxLength-3 || wcsicomp(ChPtr+1,L"exe")==0 || wcsicomp(ChPtr+1,L"sfx")==0)
        wcscpy(ChPtr+1,L"rar");
    if (!OldNumbering)
    {
      ChPtr=GetVolNumPart(ArcNameW);

      while ((++(*ChPtr))=='9'+1)
      {
        *ChPtr='0';
        ChPtr--;
        if (ChPtr<ArcNameW || !IsDigit(*ChPtr))
        {
          for (wchar *EndPtr=ArcNameW+wcslen(ArcNameW);EndPtr!=ChPtr;EndPtr--)
            *(EndPtr+1)=*EndPtr;
          *(ChPtr+1)='1';
          break;
        }
      }
    }
    else
      if (!IsDigit(*(ChPtr+2)) || !IsDigit(*(ChPtr+3)))
        wcscpy(ChPtr+2,L"00");
      else
      {
        ChPtr+=3;
        while ((++(*ChPtr))=='9'+1)
          if (*(ChPtr-1)=='.')
          {
            *ChPtr='A';
            break;
          }
          else
          {
            *ChPtr='0';
            ChPtr--;
          }
      }
  }
}


bool IsNameUsable(const char *Name)
{
#ifndef _UNIX
  if (Name[0] && Name[1] && strchr(Name+2,':')!=NULL)
    return(false);
  for (const char *s=Name;*s!=0;s=charnext(s))
  {
    if ((byte)*s<32)
      return(false);
    if (*s==' ' && IsPathDiv(s[1]))
      return(false);
  }
#endif
#ifdef _WIN_ALL
  // In Windows we need to check if all file name characters are defined
  // in current code page. For example, in Korean CP949 a lot of high ASCII
  // characters are not defined, cannot be used in file names, but cannot be
  // detected by other checks in this function.
  if (MultiByteToWideChar(CP_ACP,MB_ERR_INVALID_CHARS,Name,-1,NULL,0)==0 &&
      GetLastError()==ERROR_NO_UNICODE_TRANSLATION)
    return false;
#endif
  return(*Name!=0 && strpbrk(Name,"?*<>|\"")==NULL);
}


bool IsNameUsable(const wchar *Name)
{
#ifndef _UNIX
  if (Name[0] && Name[1] && wcschr(Name+2,':')!=NULL)
    return(false);
  for (const wchar *s=Name;*s!=0;s++)
  {
    if ((uint)*s<32)
      return(false);
    if (*s==' ' && IsPathDiv(s[1]))
      return(false);
  }
#endif
  return(*Name!=0 && wcspbrk(Name,L"?*<>|\"")==NULL);
}


void MakeNameUsable(char *Name,bool Extended)
{
#ifdef _WIN_ALL
  // In Windows we also need to convert characters not defined in current
  // code page. This double conversion changes them to '?', which is
  // catched by code below.
  size_t NameLength=strlen(Name);
  wchar NameW[NM];
  CharToWide(Name,NameW,ASIZE(NameW));
  WideToChar(NameW,Name,NameLength+1);
  Name[NameLength]=0;
#endif
  for (char *s=Name;*s!=0;s=charnext(s))
  {
    if (strchr(Extended ? "?*<>|\"":"?*",*s)!=NULL || Extended && (byte)*s<32)
      *s='_';
#ifdef _EMX
    if (*s=='=')
      *s='_';
#endif
#ifndef _UNIX
    if (s-Name>1 && *s==':')
      *s='_';
    if (*s==' ' && IsPathDiv(s[1]))
      *s='_';
#endif
  }
}


void MakeNameUsable(wchar *Name,bool Extended)
{
  for (wchar *s=Name;*s!=0;s++)
  {
    if (wcschr(Extended ? L"?*<>|\"":L"?*",*s)!=NULL || Extended && (uint)*s<32)
      *s='_';
#ifndef _UNIX
    if (s-Name>1 && *s==':')
      *s='_';
    if (*s==' ' && IsPathDiv(s[1]))
      *s='_';
#endif
  }
}


char* UnixSlashToDos(char *SrcName,char *DestName,uint MaxLength)
{
  if (DestName!=NULL && DestName!=SrcName)
    if (strlen(SrcName)>=MaxLength)
    {
      *DestName=0;
      return(DestName);
    }
    else
      strcpy(DestName,SrcName);
  for (char *s=SrcName;*s!=0;s=charnext(s))
  {
    if (*s=='/')
      if (DestName==NULL)
        *s='\\';
      else
        DestName[s-SrcName]='\\';
  }
  return(DestName==NULL ? SrcName:DestName);
}


char* DosSlashToUnix(char *SrcName,char *DestName,uint MaxLength)
{
  if (DestName!=NULL && DestName!=SrcName)
    if (strlen(SrcName)>=MaxLength)
    {
      *DestName=0;
      return(DestName);
    }
    else
      strcpy(DestName,SrcName);
  for (char *s=SrcName;*s!=0;s=charnext(s))
  {
    if (*s=='\\')
      if (DestName==NULL)
        *s='/';
      else
        DestName[s-SrcName]='/';
  }
  return(DestName==NULL ? SrcName:DestName);
}


wchar* UnixSlashToDos(wchar *SrcName,wchar *DestName,uint MaxLength)
{
  if (DestName!=NULL && DestName!=SrcName)
    if (wcslen(SrcName)>=MaxLength)
    {
      *DestName=0;
      return(DestName);
    }
    else
      wcscpy(DestName,SrcName);
  for (wchar *s=SrcName;*s!=0;s++)
  {
    if (*s=='/')
      if (DestName==NULL)
        *s='\\';
      else
        DestName[s-SrcName]='\\';
  }
  return(DestName==NULL ? SrcName:DestName);
}


wchar* DosSlashToUnix(wchar *SrcName,wchar *DestName,uint MaxLength)
{
  if (DestName!=NULL && DestName!=SrcName)
    if (wcslen(SrcName)>=MaxLength)
    {
      *DestName=0;
      return(DestName);
    }
    else
      wcscpy(DestName,SrcName);
  for (wchar *s=SrcName;*s!=0;s++)
  {
    if (*s=='\\')
      if (DestName==NULL)
        *s='/';
      else
        DestName[s-SrcName]='/';
  }
  return(DestName==NULL ? SrcName:DestName);
}


void ConvertNameToFull(const char *Src,char *Dest)
{
#ifdef _WIN_ALL
#ifndef _WIN_CE
  char FullName[NM],*NamePtr;
  DWORD Code=GetFullPathNameA(Src,ASIZE(FullName),FullName,&NamePtr);
  if (Code!=0 && Code<ASIZE(FullName))
    strcpy(Dest,FullName);
  else
#endif
    if (Src!=Dest)
      strcpy(Dest,Src);
#else
  char FullName[NM];
  if (IsPathDiv(*Src) || IsDiskLetter(Src))
    strcpy(FullName,Src);
  else
  {
    if (getcwd(FullName,sizeof(FullName))==NULL)
      *FullName=0;
    else
      AddEndSlash(FullName);
    strcat(FullName,Src);
  }
  strcpy(Dest,FullName);
#endif
}


void ConvertNameToFull(const wchar *Src,wchar *Dest)
{
  if (Src==NULL || *Src==0)
  {
    *Dest=0;
    return;
  }
#ifdef _WIN_ALL
#ifndef _WIN_CE
  if (WinNT())
#endif
  {
#ifndef _WIN_CE
    wchar FullName[NM],*NamePtr;
    DWORD Code=GetFullPathNameW(Src,ASIZE(FullName),FullName,&NamePtr);
    if (Code!=0 && Code<ASIZE(FullName))
      wcscpy(Dest,FullName);
    else
#endif
      if (Src!=Dest)
        wcscpy(Dest,Src);
  }
#ifndef _WIN_CE
  else
  {
    char AnsiName[NM];
    WideToChar(Src,AnsiName);
    ConvertNameToFull(AnsiName,AnsiName);
    CharToWide(AnsiName,Dest);
  }
#endif
#else
  char AnsiName[NM];
  WideToChar(Src,AnsiName);
  ConvertNameToFull(AnsiName,AnsiName);
  CharToWide(AnsiName,Dest);
#endif
}


bool IsFullPath(const char *Path)
{
  char PathOnly[NM];
  GetFilePath(Path,PathOnly,ASIZE(PathOnly));
  if (IsWildcard(PathOnly,NULL))
    return(true);
#if defined(_WIN_ALL) || defined(_EMX)
  return(Path[0]=='\\' && Path[1]=='\\' ||
         IsDiskLetter(Path) && IsPathDiv(Path[2]));
#else
  return(IsPathDiv(Path[0]));
#endif
}


bool IsFullPath(const wchar *Path)
{
  wchar PathOnly[NM];
  GetFilePath(Path,PathOnly,ASIZE(PathOnly));
  if (IsWildcard(NULL,PathOnly))
    return(true);
#if defined(_WIN_ALL) || defined(_EMX)
  return(Path[0]=='\\' && Path[1]=='\\' ||
         IsDiskLetter(Path) && IsPathDiv(Path[2]));
#else
  return(IsPathDiv(Path[0]));
#endif
}


bool IsDiskLetter(const char *Path)
{
  char Letter=etoupper(Path[0]);
  return(Letter>='A' && Letter<='Z' && IsDriveDiv(Path[1]));
}


bool IsDiskLetter(const wchar *Path)
{
  wchar Letter=etoupperw(Path[0]);
  return(Letter>='A' && Letter<='Z' && IsDriveDiv(Path[1]));
}


void GetPathRoot(const char *Path,char *Root)
{
  *Root=0;
  if (IsDiskLetter(Path))
    sprintf(Root,"%c:\\",*Path);
  else
    if (Path[0]=='\\' && Path[1]=='\\')
    {
      const char *Slash=strchr(Path+2,'\\');
      if (Slash!=NULL)
      {
        size_t Length;
        if ((Slash=strchr(Slash+1,'\\'))!=NULL)
          Length=Slash-Path+1;
        else
          Length=strlen(Path);
        strncpy(Root,Path,Length);
        Root[Length]=0;
      }
    }
}


void GetPathRoot(const wchar *Path,wchar *Root)
{
  *Root=0;
  if (IsDiskLetter(Path))
    sprintfw(Root,4,L"%c:\\",*Path);
  else
    if (Path[0]=='\\' && Path[1]=='\\')
    {
      const wchar *Slash=wcschr(Path+2,'\\');
      if (Slash!=NULL)
      {
        size_t Length;
        if ((Slash=wcschr(Slash+1,'\\'))!=NULL)
          Length=Slash-Path+1;
        else
          Length=wcslen(Path);
        wcsncpy(Root,Path,Length);
        Root[Length]=0;
      }
    }
}


int ParseVersionFileName(char *Name,wchar *NameW,bool Truncate)
{
  int Version=0;
  char *VerText=strrchrd(Name,';');
  if (VerText!=NULL)
  {
    Version=atoi(VerText+1);
    if (Truncate)
      *VerText=0;
  }
  if (NameW!=NULL)
  {
    wchar *VerTextW=wcsrchr(NameW,';');
    if (VerTextW!=NULL)
    {
      if (Version==0)
        Version=atoiw(VerTextW+1);
      if (Truncate)
        *VerTextW=0;
    }
  }
  return(Version);
}


#if !defined(SFX_MODULE) && !defined(SETUP)
// Get the name of first volume. Return the leftmost digit of volume number.
char* VolNameToFirstName(const char *VolName,char *FirstName,bool NewNumbering)
{
  if (FirstName!=VolName)
    strcpy(FirstName,VolName);
  char *VolNumStart=FirstName;
  if (NewNumbering)
  {
    char N='1';

    // From the rightmost digit of volume number to the left.
    for (char *ChPtr=GetVolNumPart(FirstName);ChPtr>FirstName;ChPtr--)
      if (IsDigit(*ChPtr))
      {
        *ChPtr=N; // Set the rightmost digit to '1' and others to '0'.
        N='0';
      }
      else
        if (N=='0')
        {
          VolNumStart=ChPtr+1; // Store the position of leftmost digit in volume number.
          break;
        }
  }
  else
  {
    // Old volume numbering scheme. Just set the extension to ".rar".
    SetExt(FirstName,"rar");
    VolNumStart=GetExt(FirstName);
  }
  if (!FileExist(FirstName))
  {
    // If the first volume, which name we just generated, is not exist,
    // check if volume with same name and any other extension is available.
    // It can help in case of *.exe or *.sfx first volume.
    char Mask[NM];
    strcpy(Mask,FirstName);
    SetExt(Mask,"*");
    FindFile Find;
    Find.SetMask(Mask);
    FindData FD;
    while (Find.Next(&FD))
    {
      Archive Arc;
      if (Arc.Open(FD.Name,FD.NameW,0) && Arc.IsArchive(true) && !Arc.NotFirstVolume)
      {
        strcpy(FirstName,FD.Name);
        break;
      }
    }
  }
  return(VolNumStart);
}
#endif


#if !defined(SFX_MODULE) && !defined(SETUP)
// Get the name of first volume. Return the leftmost digit of volume number.
wchar* VolNameToFirstName(const wchar *VolName,wchar *FirstName,bool NewNumbering)
{
  if (FirstName!=VolName)
    wcscpy(FirstName,VolName);
  wchar *VolNumStart=FirstName;
  if (NewNumbering)
  {
    wchar N='1';

    // From the rightmost digit of volume number to the left.
    for (wchar *ChPtr=GetVolNumPart(FirstName);ChPtr>FirstName;ChPtr--)
      if (IsDigit(*ChPtr))
      {
        *ChPtr=N; // Set the rightmost digit to '1' and others to '0'.
        N='0';
      }
      else
        if (N=='0')
        {
          VolNumStart=ChPtr+1; // Store the position of leftmost digit in volume number.
          break;
        }
  }
  else
  {
    // Old volume numbering scheme. Just set the extension to ".rar".
    SetExt(FirstName,L"rar");
    VolNumStart=GetExt(FirstName);
  }
  if (!FileExist(NULL,FirstName))
  {
    // If the first volume, which name we just generated, is not exist,
    // check if volume with same name and any other extension is available.
    // It can help in case of *.exe or *.sfx first volume.
    wchar Mask[NM];
    wcscpy(Mask,FirstName);
    SetExt(Mask,L"*");
    FindFile Find;
    Find.SetMaskW(Mask);
    FindData FD;
    while (Find.Next(&FD))
    {
      Archive Arc;
      if (Arc.Open(FD.Name,FD.NameW,0) && Arc.IsArchive(true) && !Arc.NotFirstVolume)
      {
        wcscpy(FirstName,FD.NameW);
        break;
      }
    }
  }
  return(VolNumStart);
}
#endif


#ifndef SFX_MODULE
static void GenArcName(char *ArcName,wchar *ArcNameW,char *GenerateMask,
                       uint ArcNumber,bool &ArcNumPresent);

void GenerateArchiveName(char *ArcName,wchar *ArcNameW,size_t MaxSize,
                         char *GenerateMask,bool Archiving)
{
  // Must be enough space for archive name plus all stuff in mask plus
  // extra overhead produced by mask 'N' (archive number) characters.
  // One 'N' character can result in several numbers if we process more
  // than 9 archives.
  char NewName[NM+MAX_GENERATE_MASK+20];
  wchar NewNameW[NM+MAX_GENERATE_MASK+20];

  uint ArcNumber=1;
  while (true) // Loop for 'N' (archive number) processing.
  {
    strncpyz(NewName,NullToEmpty(ArcName),ASIZE(NewName));
    wcsncpyz(NewNameW,NullToEmpty(ArcNameW),ASIZE(NewNameW));
    
    bool ArcNumPresent=false;

    GenArcName(NewName,NewNameW,GenerateMask,ArcNumber,ArcNumPresent);
    
    if (!ArcNumPresent)
      break;
    if (!FileExist(NewName,NewNameW))
    {
      if (!Archiving && ArcNumber>1)
      {
        // If we perform non-archiving operation, we need to use the last
        // existing archive before the first unused name. So we generate
        // the name for (ArcNumber-1) below.
        strncpyz(NewName,NullToEmpty(ArcName),ASIZE(NewName));
        wcsncpyz(NewNameW,NullToEmpty(ArcNameW),ASIZE(NewNameW));
        GenArcName(NewName,NewNameW,GenerateMask,ArcNumber-1,ArcNumPresent);
      }
      break;
    }
    ArcNumber++;
  }
  if (ArcName!=NULL && *ArcName!=0)
    strncpyz(ArcName,NewName,MaxSize);
  if (ArcNameW!=NULL && *ArcNameW!=0)
    wcsncpyz(ArcNameW,NewNameW,MaxSize);
}


void GenArcName(char *ArcName,wchar *ArcNameW,char *GenerateMask,
                uint ArcNumber,bool &ArcNumPresent)
{
  bool Prefix=false;
  if (*GenerateMask=='+')
  {
    Prefix=true;    // Add the time string before the archive name.
    GenerateMask++; // Skip '+' in the beginning of time mask.
  }

  char Mask[MAX_GENERATE_MASK];
  strncpyz(Mask,*GenerateMask ? GenerateMask:"yyyymmddhhmmss",ASIZE(Mask));

  bool QuoteMode=false,Hours=false;
  for (uint I=0;Mask[I]!=0;I++)
  {
    if (Mask[I]=='{' || Mask[I]=='}')
    {
      QuoteMode=(Mask[I]=='{');
      continue;
    }
    if (QuoteMode)
      continue;
    int CurChar=etoupper(Mask[I]);
    if (CurChar=='H')
      Hours=true;

    if (Hours && CurChar=='M')
    {
      // Replace minutes with 'I'. We use 'M' both for months and minutes,
      // so we treat as minutes only those 'M' which are found after hours.
      Mask[I]='I';
    }
    if (CurChar=='N')
    {
      uint Digits=GetDigits(ArcNumber);
      uint NCount=0;
      while (etoupper(Mask[I+NCount])=='N')
        NCount++;

      // Here we ensure that we have enough 'N' characters to fit all digits
      // of archive number. We'll replace them by actual number later
      // in this function.
      if (NCount<Digits)
      {
        memmove(Mask+I+Digits,Mask+I+NCount,strlen(Mask+I+NCount)+1);
        memset(Mask+I,'N',Digits);
      }
      I+=Max(Digits,NCount)-1;
      ArcNumPresent=true;
      continue;
    }
  }

  RarTime CurTime;
  CurTime.SetCurrentTime();
  RarLocalTime rlt;
  CurTime.GetLocal(&rlt);

  char Ext[NM];
  *Ext=0;
  if (ArcName!=NULL && *ArcName!=0)
  {
    char *Dot;
    if ((Dot=GetExt(ArcName))==NULL)
      strcpy(Ext,*PointToName(ArcName)==0 ? ".rar":"");
    else
    {
      strcpy(Ext,Dot);
      *Dot=0;
    }
  }

  wchar ExtW[NM];
  *ExtW=0;
  if (ArcNameW!=NULL && *ArcNameW!=0)
  {
    wchar *DotW;
    if ((DotW=GetExt(ArcNameW))==NULL)
      wcscpy(ExtW,*PointToName(ArcNameW)==0 ? L".rar":L"");
    else
    {
      wcscpy(ExtW,DotW);
      *DotW=0;
    }
  }

  int WeekDay=rlt.wDay==0 ? 6:rlt.wDay-1;
  int StartWeekDay=rlt.yDay-WeekDay;
  if (StartWeekDay<0)
    if (StartWeekDay<=-4)
      StartWeekDay+=IsLeapYear(rlt.Year-1) ? 366:365;
    else
      StartWeekDay=0;
  int CurWeek=StartWeekDay/7+1;
  if (StartWeekDay%7>=4)
    CurWeek++;

  char Field[10][6];

  sprintf(Field[0],"%04d",rlt.Year);
  sprintf(Field[1],"%02d",rlt.Month);
  sprintf(Field[2],"%02d",rlt.Day);
  sprintf(Field[3],"%02d",rlt.Hour);
  sprintf(Field[4],"%02d",rlt.Minute);
  sprintf(Field[5],"%02d",rlt.Second);
  sprintf(Field[6],"%02d",CurWeek);
  sprintf(Field[7],"%d",WeekDay+1);
  sprintf(Field[8],"%03d",rlt.yDay+1);
  sprintf(Field[9],"%05d",ArcNumber);

  const char *MaskChars="YMDHISWAEN";

  int CField[sizeof(Field)/sizeof(Field[0])];
  memset(CField,0,sizeof(CField));
  QuoteMode=false;
  for (int I=0;Mask[I]!=0;I++)
  {
    if (Mask[I]=='{' || Mask[I]=='}')
    {
      QuoteMode=(Mask[I]=='{');
      continue;
    }
    if (QuoteMode)
      continue;
    const char *Ch=strchr(MaskChars,etoupper(Mask[I]));
    if (Ch!=NULL)
      CField[Ch-MaskChars]++;
   }

  char DateText[MAX_GENERATE_MASK];
  *DateText=0;
  QuoteMode=false;
  for (size_t I=0,J=0;Mask[I]!=0 && J<ASIZE(DateText)-1;I++)
  {
    if (Mask[I]=='{' || Mask[I]=='}')
    {
      QuoteMode=(Mask[I]=='{');
      continue;
    }
    const char *Ch=strchr(MaskChars,etoupper(Mask[I]));
    if (Ch==NULL || QuoteMode)
      DateText[J]=Mask[I];
    else
    {
      size_t FieldPos=Ch-MaskChars;
      int CharPos=(int)strlen(Field[FieldPos])-CField[FieldPos]--;
      if (FieldPos==1 && etoupper(Mask[I+1])=='M' && etoupper(Mask[I+2])=='M')
      {
        strncpyz(DateText+J,GetMonthName(rlt.Month-1),ASIZE(DateText)-J);
        J=strlen(DateText);
        I+=2;
        continue;
      }
      if (CharPos<0)
        DateText[J]=Mask[I];
      else
        DateText[J]=Field[FieldPos][CharPos];
    }
    DateText[++J]=0;
  }

  wchar DateTextW[ASIZE(DateText)];
  CharToWide(DateText,DateTextW);

  if (Prefix)
  {
    if (ArcName!=NULL && *ArcName!=0)
    {
      char NewName[NM];
      GetFilePath(ArcName,NewName,ASIZE(NewName));
      AddEndSlash(NewName);
      strcat(NewName,DateText);
      strcat(NewName,PointToName(ArcName));
      strcpy(ArcName,NewName);
    }
    if (ArcNameW!=NULL && *ArcNameW!=0)
    {
      wchar NewNameW[NM];
      GetFilePath(ArcNameW,NewNameW,ASIZE(NewNameW));
      AddEndSlash(NewNameW);
      wcscat(NewNameW,DateTextW);
      wcscat(NewNameW,PointToName(ArcNameW));
      wcscpy(ArcNameW,NewNameW);
    }
  }
  else
  {
    if (ArcName!=NULL && *ArcName!=0)
      strcat(ArcName,DateText);
    if (ArcNameW!=NULL && *ArcNameW!=0)
      wcscat(ArcNameW,DateTextW);
  }
  if (ArcName!=NULL && *ArcName!=0)
    strcat(ArcName,Ext);
  if (ArcNameW!=NULL && *ArcNameW!=0)
    wcscat(ArcNameW,ExtW);
}
#endif


wchar* GetWideName(const char *Name,const wchar *NameW,wchar *DestW,size_t DestSize)
{
  if (NameW!=NULL && *NameW!=0)
  {
    if (DestW!=NameW)
      wcsncpy(DestW,NameW,DestSize);
  }
  else
    if (Name!=NULL)
      CharToWide(Name,DestW,DestSize);
    else
      *DestW=0;

  // Ensure that we return a zero terminate string for security reasons.
  if (DestSize>0)
    DestW[DestSize-1]=0;

  return(DestW);
}


// Unlike WideToChar, always returns the zero terminated string,
// even if the destination buffer size is not enough.
char* GetAsciiName(const wchar *NameW,char *Name,size_t DestSize)
{
  if (DestSize>0)
  {
    WideToChar(NameW,Name,DestSize);
    Name[DestSize-1]=0;
  }
  else
    *Name=0;
  return Name;
}
