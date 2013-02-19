#include "rar.hpp"

MKDIR_CODE MakeDir(const char *Name,const wchar *NameW,bool SetAttr,uint Attr)
{
#ifdef _WIN_ALL
  BOOL RetCode;
    if (WinNT() && NameW!=NULL && *NameW!=0)
      RetCode=CreateDirectoryW(NameW,NULL);
    else
      if (Name!=NULL)
        RetCode=CreateDirectoryA(Name,NULL);
      else
        return(MKDIR_BADPATH);
  if (RetCode!=0) // Non-zero return code means success for CreateDirectory.
  {
    if (SetAttr)
      SetFileAttr(Name,NameW,Attr);
    return(MKDIR_SUCCESS);
  }
  int ErrCode=GetLastError();
  if (ErrCode==ERROR_FILE_NOT_FOUND || ErrCode==ERROR_PATH_NOT_FOUND)
    return(MKDIR_BADPATH);
  return(MKDIR_ERROR);
#else

  // No Unicode in the rest of function, so Name must be not NULL.
  if (Name==NULL)
    return(MKDIR_BADPATH);
#endif

#ifdef _EMX
  #ifdef _DJGPP
    if (mkdir(Name,(Attr & FA_RDONLY) ? 0:S_IWUSR)==0)
  #else
    if (__mkdir(Name)==0)
  #endif
    {
      if (SetAttr)
        SetFileAttr(Name,NameW,Attr);
      return(MKDIR_SUCCESS);
    }
    return(errno==ENOENT ? MKDIR_BADPATH:MKDIR_ERROR);
#endif

#ifdef _UNIX
  mode_t uattr=SetAttr ? (mode_t)Attr:0777;
  int ErrCode=mkdir(Name,uattr);
  if (ErrCode==-1)
    return(errno==ENOENT ? MKDIR_BADPATH:MKDIR_ERROR);
  return(MKDIR_SUCCESS);
#endif
}


bool CreatePath(const char *Path,bool SkipLastName)
{
  if (Path==NULL || *Path==0)
    return(false);

#if defined(_WIN_ALL) || defined(_EMX)
  uint DirAttr=0;
#else
  uint DirAttr=0777;
#endif
  
  bool Success=true;

  for (const char *s=Path;*s!=0;s=charnext(s))
  {
    if (s-Path>=NM)
      break;

    // Process all kinds of path separators, so user can enter Unix style
    // path in Windows or Windows in Unix.
    if (IsPathDiv(*s))
    {
      char DirName[NM];
      strncpy(DirName,Path,s-Path);
      DirName[s-Path]=0;

      if (MakeDir(DirName,NULL,true,DirAttr)==MKDIR_SUCCESS)
      {
#ifndef GUI
        mprintf(St(MCreatDir),DirName);
        mprintf(" %s",St(MOk));
#endif
      }
      else
        Success=false;
    }
  }
  if (!SkipLastName)
    if (!IsPathDiv(*PointToLastChar(Path)))
      if (MakeDir(Path,NULL,true,DirAttr)!=MKDIR_SUCCESS)
        Success=false;
  return(Success);
}


bool CreatePath(const wchar *Path,bool SkipLastName)
{
  if (Path==NULL || *Path==0)
    return(false);

#if defined(_WIN_ALL) || defined(_EMX)
  uint DirAttr=0;
#else
  uint DirAttr=0777;
#endif
  
  bool Success=true;

  for (const wchar *s=Path;*s!=0;s++)
  {
    if (s-Path>=NM)
      break;

    // Process all kinds of path separators, so user can enter Unix style
    // path in Windows or Windows in Unix.
    if (IsPathDiv(*s))
    {
      wchar DirName[NM];
      wcsncpy(DirName,Path,s-Path);
      DirName[s-Path]=0;

      if (MakeDir(NULL,DirName,true,DirAttr)==MKDIR_SUCCESS)
      {
#ifndef GUI
        char DirNameA[NM];
        WideToChar(DirName,DirNameA,ASIZE(DirNameA));
        DirNameA[ASIZE(DirNameA)-1]=0;
        mprintf(St(MCreatDir),DirNameA);
        mprintf(" %s",St(MOk));
#endif
      }
      else
        Success=false;
    }
  }
  if (!SkipLastName)
    if (!IsPathDiv(*PointToLastChar(Path)))
      if (MakeDir(NULL,Path,true,DirAttr)!=MKDIR_SUCCESS)
        Success=false;
  return(Success);
}


bool CreatePath(const char *Path,const wchar *PathW,bool SkipLastName)
{
#ifdef _WIN_ALL
  // If we are in Windows, let's try Unicode path first. In Unix we do not
  // need it (Unix MakeDir will fails with Unicode only name).
  if (PathW!=NULL && *PathW!=0)
    return(CreatePath(PathW,SkipLastName));
#endif
  if (Path!=NULL && *Path!=0)
    return(CreatePath(Path,SkipLastName));
  return(false);
}


void SetDirTime(const char *Name,const wchar *NameW,RarTime *ftm,RarTime *ftc,RarTime *fta)
{
#ifdef _WIN_ALL
  if (!WinNT())
    return;

  bool sm=ftm!=NULL && ftm->IsSet();
  bool sc=ftc!=NULL && ftc->IsSet();
  bool sa=fta!=NULL && fta->IsSet();

  unsigned int DirAttr=GetFileAttr(Name,NameW);
  bool ResetAttr=(DirAttr!=0xffffffff && (DirAttr & FA_RDONLY)!=0);
  if (ResetAttr)
    SetFileAttr(Name,NameW,0);

  wchar DirNameW[NM];
  GetWideName(Name,NameW,DirNameW,ASIZE(DirNameW));
  HANDLE hFile=CreateFileW(DirNameW,GENERIC_WRITE,FILE_SHARE_READ|FILE_SHARE_WRITE,
                          NULL,OPEN_EXISTING,FILE_FLAG_BACKUP_SEMANTICS,NULL);
  if (hFile==INVALID_HANDLE_VALUE)
    return;
  FILETIME fm,fc,fa;
  if (sm)
    ftm->GetWin32(&fm);
  if (sc)
    ftc->GetWin32(&fc);
  if (sa)
    fta->GetWin32(&fa);
  SetFileTime(hFile,sc ? &fc:NULL,sa ? &fa:NULL,sm ? &fm:NULL);
  CloseHandle(hFile);
  if (ResetAttr)
    SetFileAttr(Name,NameW,DirAttr);
#endif
#if defined(_UNIX) || defined(_EMX)
  File::SetCloseFileTimeByName(Name,ftm,fta);
#endif
}


bool IsRemovable(const char *Name)
{
#ifdef _WIN_ALL
  char Root[NM];
  GetPathRoot(Name,Root);
  int Type=GetDriveTypeA(*Root!=0 ? Root:NULL);
  return(Type==DRIVE_REMOVABLE || Type==DRIVE_CDROM);
#elif defined(_EMX)
  char Drive=etoupper(Name[0]);
  return((Drive=='A' || Drive=='B') && Name[1]==':');
#else
  return(false);
#endif
}




#ifndef SFX_MODULE
int64 GetFreeDisk(const char *Name)
{
#ifdef _WIN_ALL
  char Root[NM];
  GetPathRoot(Name,Root);

  typedef BOOL (WINAPI *GETDISKFREESPACEEX)(
    LPCSTR,PULARGE_INTEGER,PULARGE_INTEGER,PULARGE_INTEGER
   );
  static GETDISKFREESPACEEX pGetDiskFreeSpaceEx=NULL;

  if (pGetDiskFreeSpaceEx==NULL)
  {
    HMODULE hKernel=GetModuleHandleW(L"kernel32.dll");
    if (hKernel!=NULL)
      pGetDiskFreeSpaceEx=(GETDISKFREESPACEEX)GetProcAddress(hKernel,"GetDiskFreeSpaceExA");
  }
  if (pGetDiskFreeSpaceEx!=NULL)
  {
    GetFilePath(Name,Root,ASIZE(Root));
    ULARGE_INTEGER uiTotalSize,uiTotalFree,uiUserFree;
    uiUserFree.u.LowPart=uiUserFree.u.HighPart=0;
    if (pGetDiskFreeSpaceEx(*Root ? Root:NULL,&uiUserFree,&uiTotalSize,&uiTotalFree) &&
        uiUserFree.u.HighPart<=uiTotalFree.u.HighPart)
      return(INT32TO64(uiUserFree.u.HighPart,uiUserFree.u.LowPart));
  }

  // We are here if we failed to load GetDiskFreeSpaceExA.
  DWORD SectorsPerCluster,BytesPerSector,FreeClusters,TotalClusters;
  if (!GetDiskFreeSpaceA(*Root ? Root:NULL,&SectorsPerCluster,&BytesPerSector,&FreeClusters,&TotalClusters))
    return(1457664);
  int64 FreeSize=SectorsPerCluster*BytesPerSector;
  FreeSize=FreeSize*FreeClusters;
  return(FreeSize);
#elif defined(_BEOS)
  char Root[NM];
  GetFilePath(Name,Root,ASIZE(Root));
  dev_t Dev=dev_for_path(*Root ? Root:".");
  if (Dev<0)
    return(1457664);
  fs_info Info;
  if (fs_stat_dev(Dev,&Info)!=0)
    return(1457664);
  int64 FreeSize=Info.block_size;
  FreeSize=FreeSize*Info.free_blocks;
  return(FreeSize);
#elif defined(_UNIX)
  return(1457664);
#elif defined(_EMX)
  int Drive=IsDiskLetter(Name) ? etoupper(Name[0])-'A'+1:0;
#ifndef _DJGPP
  if (_osmode == OS2_MODE)
  {
    FSALLOCATE fsa;
    if (DosQueryFSInfo(Drive,1,&fsa,sizeof(fsa))!=0)
      return(1457664);
    int64 FreeSize=fsa.cSectorUnit*fsa.cbSector;
    FreeSize=FreeSize*fsa.cUnitAvail;
    return(FreeSize);
  }
  else
#endif
  {
    union REGS regs,outregs;
    memset(&regs,0,sizeof(regs));
    regs.h.ah=0x36;
    regs.h.dl=Drive;
#ifdef _DJGPP
    int86 (0x21,&regs,&outregs);
#else
    _int86 (0x21,&regs,&outregs);
#endif
    if (outregs.x.ax==0xffff)
      return(1457664);
    int64 FreeSize=outregs.x.ax*outregs.x.cx;
    FreeSize=FreeSize*outregs.x.bx;
    return(FreeSize);
  }
#else
  #define DISABLEAUTODETECT
  return(1457664);
#endif
}
#endif





bool FileExist(const char *Name,const wchar *NameW)
{
#ifdef _WIN_ALL
    if (WinNT() && NameW!=NULL && *NameW!=0)
      return(GetFileAttributesW(NameW)!=0xffffffff);
    else
      return(Name!=NULL && GetFileAttributesA(Name)!=0xffffffff);
#elif defined(ENABLE_ACCESS)
  return(access(Name,0)==0);
#else
  FindData FD;
  return(FindFile::FastFind(Name,NameW,&FD));
#endif
}


bool FileExist(const wchar *Name)
{
  return FileExist(NULL,Name);
}
 

bool WildFileExist(const char *Name,const wchar *NameW)
{
  if (IsWildcard(Name,NameW))
  {
    FindFile Find;
    Find.SetMask(Name);
    Find.SetMaskW(NameW);
    FindData fd;
    return(Find.Next(&fd));
  }
  return(FileExist(Name,NameW));
}


bool IsDir(uint Attr)
{
#if defined (_WIN_ALL) || defined(_EMX)
  return(Attr!=0xffffffff && (Attr & 0x10)!=0);
#endif
#if defined(_UNIX)
  return((Attr & 0xF000)==0x4000);
#endif
}


bool IsUnreadable(uint Attr)
{
#if defined(_UNIX) && defined(S_ISFIFO) && defined(S_ISSOCK) && defined(S_ISCHR)
  return(S_ISFIFO(Attr) || S_ISSOCK(Attr) || S_ISCHR(Attr));
#endif
  return(false);
}


bool IsLabel(uint Attr)
{
#if defined (_WIN_ALL) || defined(_EMX)
  return((Attr & 8)!=0);
#else
  return(false);
#endif
}


bool IsLink(uint Attr)
{
#ifdef _UNIX
  return((Attr & 0xF000)==0xA000);
#else
  return(false);
#endif
}






bool IsDeleteAllowed(uint FileAttr)
{
#if defined(_WIN_ALL) || defined(_EMX)
  return((FileAttr & (FA_RDONLY|FA_SYSTEM|FA_HIDDEN))==0);
#else
  return((FileAttr & (S_IRUSR|S_IWUSR))==(S_IRUSR|S_IWUSR));
#endif
}


void PrepareToDelete(const char *Name,const wchar *NameW)
{
#if defined(_WIN_ALL) || defined(_EMX)
  SetFileAttr(Name,NameW,0);
#endif
#ifdef _UNIX
  if (Name!=NULL)
    chmod(Name,S_IRUSR|S_IWUSR|S_IXUSR);
#endif
}


uint GetFileAttr(const char *Name,const wchar *NameW)
{
#ifdef _WIN_ALL
    if (WinNT() && NameW!=NULL && *NameW!=0)
      return(GetFileAttributesW(NameW));
    else
      return(GetFileAttributesA(Name));
#elif defined(_DJGPP)
  return(_chmod(Name,0));
#else
  struct stat st;
  if (stat(Name,&st)!=0)
    return(0);
#ifdef _EMX
  return(st.st_attr);
#else
  return(st.st_mode);
#endif
#endif
}


bool SetFileAttr(const char *Name,const wchar *NameW,uint Attr)
{
  bool Success;
#ifdef _WIN_ALL
    if (WinNT() && NameW!=NULL && *NameW!=0)
      Success=SetFileAttributesW(NameW,Attr)!=0;
    else
      if (Name!=NULL)
        Success=SetFileAttributesA(Name,Attr)!=0;
      else
        Success=false;
#elif defined(_DJGPP)
  Success=_chmod(Name,1,Attr)!=-1;
#elif defined(_EMX)
  Success=__chmod(Name,1,Attr)!=-1;
#elif defined(_UNIX)
  Success=chmod(Name,(mode_t)Attr)==0;
#else
  Success=false;
#endif
  return(Success);
}




#ifndef SFX_MODULE
uint CalcFileCRC(File *SrcFile,int64 Size,CALCCRC_SHOWMODE ShowMode)
{
  SaveFilePos SavePos(*SrcFile);
  const size_t BufSize=0x10000;
  Array<byte> Data(BufSize);
  int64 BlockCount=0;
  uint DataCRC=0xffffffff;

#if !defined(SILENT) && !defined(_WIN_CE)
  int64 FileLength=SrcFile->FileLength();
  if (ShowMode!=CALCCRC_SHOWNONE)
  {
    mprintf(St(MCalcCRC));
    mprintf("     ");
  }

#endif

  SrcFile->Seek(0,SEEK_SET);
  while (true)
  {
    size_t SizeToRead;
    if (Size==INT64NDF)   // If we process the entire file.
      SizeToRead=BufSize; // Then always attempt to read the entire buffer.
    else
      SizeToRead=(size_t)Min((int64)BufSize,Size);
    int ReadSize=SrcFile->Read(&Data[0],SizeToRead);
    if (ReadSize==0)
      break;

    ++BlockCount;
    if ((BlockCount & 15)==0)
    {
#if !defined(SILENT) && !defined(_WIN_CE)
      if (ShowMode==CALCCRC_SHOWALL)
        mprintf("\b\b\b\b%3d%%",ToPercent(BlockCount*int64(BufSize),FileLength));
#endif
      Wait();
    }
    DataCRC=CRC(DataCRC,&Data[0],ReadSize);
    if (Size!=INT64NDF)
      Size-=ReadSize;
  }
#if !defined(SILENT) && !defined(_WIN_CE)
  if (ShowMode==CALCCRC_SHOWALL)
    mprintf("\b\b\b\b    ");
#endif
  return(DataCRC^0xffffffff);
}
#endif


bool RenameFile(const char *SrcName,const wchar *SrcNameW,const char *DestName,const wchar *DestNameW)
{
  return(rename(SrcName,DestName)==0);
}


bool DelFile(const char *Name)
{
  return(DelFile(Name,NULL));
}




bool DelFile(const char *Name,const wchar *NameW)
{
  return(Name!=NULL && remove(Name)==0);
}








#if defined(_WIN_ALL) && !defined(_WIN_CE) && !defined(SFX_MODULE)
bool SetFileCompression(char *Name,wchar *NameW,bool State)
{
  wchar FileNameW[NM];
  GetWideName(Name,NameW,FileNameW,ASIZE(FileNameW));
  HANDLE hFile=CreateFileW(FileNameW,FILE_READ_DATA|FILE_WRITE_DATA,
                 FILE_SHARE_READ|FILE_SHARE_WRITE,NULL,OPEN_EXISTING,
                 FILE_FLAG_BACKUP_SEMANTICS|FILE_FLAG_SEQUENTIAL_SCAN,NULL);
  if (hFile==INVALID_HANDLE_VALUE)
    return(false);
  SHORT NewState=State ? COMPRESSION_FORMAT_DEFAULT:COMPRESSION_FORMAT_NONE;
  DWORD Result;
  int RetCode=DeviceIoControl(hFile,FSCTL_SET_COMPRESSION,&NewState,
                              sizeof(NewState),NULL,0,&Result,NULL);
  CloseHandle(hFile);
  return(RetCode!=0);
}
#endif









