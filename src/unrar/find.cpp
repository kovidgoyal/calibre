#include "rar.hpp"

FindFile::FindFile()
{
  *FindMask=0;
  *FindMaskW=0;
  FirstCall=true;
#ifdef _WIN_ALL
  hFind=INVALID_HANDLE_VALUE;
#else
  dirp=NULL;
#endif
}


FindFile::~FindFile()
{
#ifdef _WIN_ALL
  if (hFind!=INVALID_HANDLE_VALUE)
    FindClose(hFind);
#else
  if (dirp!=NULL)
    closedir(dirp);
#endif
}


void FindFile::SetMask(const char *FindMask)
{
  strcpy(FindFile::FindMask,NullToEmpty(FindMask));
  if (*FindMaskW==0)
    CharToWide(FindMask,FindMaskW);
  FirstCall=true;
}


void FindFile::SetMaskW(const wchar *FindMaskW)
{
  if (FindMaskW==NULL)
    return;
  wcscpy(FindFile::FindMaskW,FindMaskW);
  if (*FindMask==0)
    WideToChar(FindMaskW,FindMask);
  FirstCall=true;
}


bool FindFile::Next(struct FindData *fd,bool GetSymLink)
{
  fd->Error=false;
  if (*FindMask==0)
    return(false);
#ifdef _WIN_ALL
  if (FirstCall)
  {
    if ((hFind=Win32Find(INVALID_HANDLE_VALUE,FindMask,FindMaskW,fd))==INVALID_HANDLE_VALUE)
      return(false);
  }
  else
    if (Win32Find(hFind,FindMask,FindMaskW,fd)==INVALID_HANDLE_VALUE)
      return(false);
#else
  if (FirstCall)
  {
    char DirName[NM];
    strcpy(DirName,FindMask);
    RemoveNameFromPath(DirName);
    if (*DirName==0)
      strcpy(DirName,".");
    if ((dirp=opendir(DirName))==NULL)
    {
      fd->Error=(errno!=ENOENT);
      return(false);
    }
  }
  while (1)
  {
    struct dirent *ent=readdir(dirp);
    if (ent==NULL)
      return(false);
    if (strcmp(ent->d_name,".")==0 || strcmp(ent->d_name,"..")==0)
      continue;
    if (CmpName(FindMask,ent->d_name,MATCH_NAMES))
    {
      char FullName[NM];
      strcpy(FullName,FindMask);
      *PointToName(FullName)=0;
      if (strlen(FullName)+strlen(ent->d_name)>=ASIZE(FullName)-1)
      {
#ifndef SILENT
        Log(NULL,"\n%s%s",FullName,ent->d_name);
        Log(NULL,St(MPathTooLong));
#endif
        return(false);
      }
      strcat(FullName,ent->d_name);
      if (!FastFind(FullName,NULL,fd,GetSymLink))
      {
        ErrHandler.OpenErrorMsg(FullName);
        continue;
      }
      strcpy(fd->Name,FullName);
      break;
    }
  }
  *fd->NameW=0;
#ifdef _APPLE
  if (!LowAscii(fd->Name))
    UtfToWide(fd->Name,fd->NameW,sizeof(fd->NameW));
#elif defined(UNICODE_SUPPORTED)
  if (!LowAscii(fd->Name) && UnicodeEnabled())
    CharToWide(fd->Name,fd->NameW);
#endif
#endif
  fd->Flags=0;
  fd->IsDir=IsDir(fd->FileAttr);
  FirstCall=false;
  char *Name=PointToName(fd->Name);
  if (strcmp(Name,".")==0 || strcmp(Name,"..")==0)
    return(Next(fd));
  return(true);
}


bool FindFile::FastFind(const char *FindMask,const wchar *FindMaskW,FindData *fd,bool GetSymLink)
{
  fd->Error=false;
#ifndef _UNIX
  if (IsWildcard(FindMask,FindMaskW))
    return(false);
#endif    
#ifdef _WIN_ALL
  HANDLE hFind=Win32Find(INVALID_HANDLE_VALUE,FindMask,FindMaskW,fd);
  if (hFind==INVALID_HANDLE_VALUE)
    return(false);
  FindClose(hFind);
#else
  struct stat st;
  if (GetSymLink)
  {
#ifdef SAVE_LINKS
    if (lstat(FindMask,&st)!=0)
#else
    if (stat(FindMask,&st)!=0)
#endif
    {
      fd->Error=(errno!=ENOENT);
      return(false);
    }
  }
  else
    if (stat(FindMask,&st)!=0)
    {
      fd->Error=(errno!=ENOENT);
      return(false);
    }
#ifdef _DJGPP
  fd->FileAttr=_chmod(FindMask,0);
#elif defined(_EMX)
  fd->FileAttr=st.st_attr;
#else
  fd->FileAttr=st.st_mode;
#endif
  fd->IsDir=IsDir(st.st_mode);
  fd->Size=st.st_size;
  fd->mtime=st.st_mtime;
  fd->atime=st.st_atime;
  fd->ctime=st.st_ctime;
  fd->FileTime=fd->mtime.GetDos();
  strcpy(fd->Name,FindMask);

  *fd->NameW=0;
#ifdef _APPLE
  if (!LowAscii(fd->Name))
    UtfToWide(fd->Name,fd->NameW,sizeof(fd->NameW));
#elif defined(UNICODE_SUPPORTED)
  if (!LowAscii(fd->Name) && UnicodeEnabled())
    CharToWide(fd->Name,fd->NameW);
#endif
#endif
  fd->Flags=0;
  fd->IsDir=IsDir(fd->FileAttr);
  return(true);
}


#ifdef _WIN_ALL
HANDLE FindFile::Win32Find(HANDLE hFind,const char *Mask,const wchar *MaskW,FindData *fd)
{
#ifndef _WIN_CE
  if (WinNT())
#endif
  {
    wchar WideMask[NM];
    if (MaskW!=NULL && *MaskW!=0)
      wcscpy(WideMask,MaskW);
    else
      CharToWide(Mask,WideMask);

    WIN32_FIND_DATAW FindData;
    if (hFind==INVALID_HANDLE_VALUE)
    {
      hFind=FindFirstFileW(WideMask,&FindData);
      if (hFind==INVALID_HANDLE_VALUE)
      {
        int SysErr=GetLastError();
        fd->Error=(SysErr!=ERROR_FILE_NOT_FOUND &&
                   SysErr!=ERROR_PATH_NOT_FOUND &&
                   SysErr!=ERROR_NO_MORE_FILES);
      }
    }
    else
      if (!FindNextFileW(hFind,&FindData))
      {
        hFind=INVALID_HANDLE_VALUE;
        fd->Error=GetLastError()!=ERROR_NO_MORE_FILES;
      }

    if (hFind!=INVALID_HANDLE_VALUE)
    {
      wcscpy(fd->NameW,WideMask);
      wcscpy(PointToName(fd->NameW),FindData.cFileName);
      WideToChar(fd->NameW,fd->Name);
      fd->Size=INT32TO64(FindData.nFileSizeHigh,FindData.nFileSizeLow);
      fd->FileAttr=FindData.dwFileAttributes;
      wcscpy(fd->ShortName,FindData.cAlternateFileName);
      fd->ftCreationTime=FindData.ftCreationTime;
      fd->ftLastAccessTime=FindData.ftLastAccessTime;
      fd->ftLastWriteTime=FindData.ftLastWriteTime;
      fd->mtime=FindData.ftLastWriteTime;
      fd->ctime=FindData.ftCreationTime;
      fd->atime=FindData.ftLastAccessTime;
      fd->FileTime=fd->mtime.GetDos();

#ifndef _WIN_CE
//      if (LowAscii(fd->NameW))
//        *fd->NameW=0;
#endif
    }
  }
#ifndef _WIN_CE
  else
  {
    char CharMask[NM];
    if (Mask!=NULL && *Mask!=0)
      strcpy(CharMask,Mask);
    else
      WideToChar(MaskW,CharMask);

    WIN32_FIND_DATAA FindData;
    if (hFind==INVALID_HANDLE_VALUE)
    {
      hFind=FindFirstFileA(CharMask,&FindData);
      if (hFind==INVALID_HANDLE_VALUE)
      {
        int SysErr=GetLastError();
        fd->Error=SysErr!=ERROR_FILE_NOT_FOUND && SysErr!=ERROR_PATH_NOT_FOUND;
      }
    }
    else
      if (!FindNextFileA(hFind,&FindData))
      {
        hFind=INVALID_HANDLE_VALUE;
        fd->Error=GetLastError()!=ERROR_NO_MORE_FILES;
      }

    if (hFind!=INVALID_HANDLE_VALUE)
    {
      strcpy(fd->Name,CharMask);
      strcpy(PointToName(fd->Name),FindData.cFileName);
      CharToWide(fd->Name,fd->NameW);
      fd->Size=INT32TO64(FindData.nFileSizeHigh,FindData.nFileSizeLow);
      fd->FileAttr=FindData.dwFileAttributes;
      CharToWide(FindData.cAlternateFileName,fd->ShortName);
      fd->ftCreationTime=FindData.ftCreationTime;
      fd->ftLastAccessTime=FindData.ftLastAccessTime;
      fd->ftLastWriteTime=FindData.ftLastWriteTime;
      fd->mtime=FindData.ftLastWriteTime;
      fd->ctime=FindData.ftCreationTime;
      fd->atime=FindData.ftLastAccessTime;
      fd->FileTime=fd->mtime.GetDos();
//      if (LowAscii(fd->Name))
//        *fd->NameW=0;
    }
  }
#endif
  fd->Flags=0;
  return(hFind);
}
#endif

