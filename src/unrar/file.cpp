#include "rar.hpp"

static File *CreatedFiles[256];
static int RemoveCreatedActive=0;

File::File()
{
  hFile=BAD_HANDLE;
  *FileName=0;
  *FileNameW=0;
  NewFile=false;
  LastWrite=false;
  HandleType=FILE_HANDLENORMAL;
  SkipClose=false;
  IgnoreReadErrors=false;
  ErrorType=FILE_SUCCESS;
  OpenShared=false;
  AllowDelete=true;
  CloseCount=0;
  AllowExceptions=true;
#ifdef _WIN_ALL
  NoSequentialRead=false;
  CreateMode=FMF_UNDEFINED;
#endif
}


File::~File()
{
  if (hFile!=BAD_HANDLE && !SkipClose)
    if (NewFile)
      Delete();
    else
      Close();
}


void File::operator = (File &SrcFile)
{
  hFile=SrcFile.hFile;
  strcpy(FileName,SrcFile.FileName);
  NewFile=SrcFile.NewFile;
  LastWrite=SrcFile.LastWrite;
  HandleType=SrcFile.HandleType;
  SrcFile.SkipClose=true;
}


bool File::Open(const char *Name,const wchar *NameW,uint Mode)
{
  ErrorType=FILE_SUCCESS;
  FileHandle hNewFile;
  bool OpenShared=File::OpenShared || (Mode & FMF_OPENSHARED)!=0;
  bool UpdateMode=(Mode & FMF_UPDATE)!=0;
  bool WriteMode=(Mode & FMF_WRITE)!=0;
#ifdef _WIN_ALL
  uint Access=WriteMode ? GENERIC_WRITE:GENERIC_READ;
  if (UpdateMode)
    Access|=GENERIC_WRITE;
  uint ShareMode=FILE_SHARE_READ;
  if (OpenShared)
    ShareMode|=FILE_SHARE_WRITE;
  uint Flags=NoSequentialRead ? 0:FILE_FLAG_SEQUENTIAL_SCAN;
  if (WinNT() && NameW!=NULL && *NameW!=0)
    hNewFile=CreateFileW(NameW,Access,ShareMode,NULL,OPEN_EXISTING,Flags,NULL);
  else
    hNewFile=CreateFileA(Name,Access,ShareMode,NULL,OPEN_EXISTING,Flags,NULL);

  if (hNewFile==BAD_HANDLE && GetLastError()==ERROR_FILE_NOT_FOUND)
    ErrorType=FILE_NOTFOUND;
#else
  int flags=UpdateMode ? O_RDWR:(WriteMode ? O_WRONLY:O_RDONLY);
#ifdef O_BINARY
  flags|=O_BINARY;
#if defined(_AIX) && defined(_LARGE_FILE_API)
  flags|=O_LARGEFILE;
#endif
#endif
#if defined(_EMX) && !defined(_DJGPP)
  int sflags=OpenShared ? SH_DENYNO:SH_DENYWR;
  int handle=sopen(Name,flags,sflags);
#else
  int handle=open(Name,flags);
#ifdef LOCK_EX

#ifdef _OSF_SOURCE
  extern "C" int flock(int, int);
#endif

  if (!OpenShared && UpdateMode && handle>=0 && flock(handle,LOCK_EX|LOCK_NB)==-1)
  {
    close(handle);
    return(false);
  }
#endif
#endif
  hNewFile=handle==-1 ? BAD_HANDLE:fdopen(handle,UpdateMode ? UPDATEBINARY:READBINARY);
  if (hNewFile==BAD_HANDLE && errno==ENOENT)
    ErrorType=FILE_NOTFOUND;
#endif
  NewFile=false;
  HandleType=FILE_HANDLENORMAL;
  SkipClose=false;
  bool Success=hNewFile!=BAD_HANDLE;
  if (Success)
  {
    hFile=hNewFile;

    // We use memove instead of strcpy and wcscpy to avoid problems
    // with overlapped buffers. While we do not call this function with
    // really overlapped buffers yet, we do call it with Name equal to
    // FileName like Arc.Open(Arc.FileName,Arc.FileNameW,...).
    if (NameW!=NULL)
      memmove(FileNameW,NameW,(wcslen(NameW)+1)*sizeof(*NameW));
    else
      *FileNameW=0;
    if (Name!=NULL)
      memmove(FileName,Name,strlen(Name)+1);
    else
      WideToChar(NameW,FileName);
    AddFileToList(hFile);
  }
  return(Success);
}


#if !defined(SHELL_EXT) && !defined(SFX_MODULE)
void File::TOpen(const char *Name,const wchar *NameW)
{
  if (!WOpen(Name,NameW))
    ErrHandler.Exit(RARX_OPEN);
}
#endif


bool File::WOpen(const char *Name,const wchar *NameW)
{
  if (Open(Name,NameW))
    return(true);
  ErrHandler.OpenErrorMsg(Name,NameW);
  return(false);
}


bool File::Create(const char *Name,const wchar *NameW,uint Mode)
{
  // OpenIndiana based NAS and CIFS shares fail to set the file time if file
  // was created in read+write mode and some data was written and not flushed
  // before SetFileTime call. So we should use the write only mode if we plan
  // SetFileTime call and do not need to read from file.
  bool WriteMode=(Mode & FMF_WRITE)!=0;
  bool ShareRead=(Mode & FMF_SHAREREAD)!=0 || File::OpenShared;
#ifdef _WIN_ALL
  CreateMode=Mode;
  uint Access=WriteMode ? GENERIC_WRITE:GENERIC_READ|GENERIC_WRITE;
  DWORD ShareMode=ShareRead ? FILE_SHARE_READ:0;
  if (WinNT() && NameW!=NULL && *NameW!=0)
    hFile=CreateFileW(NameW,Access,ShareMode,NULL,CREATE_ALWAYS,0,NULL);
  else
    hFile=CreateFileA(Name,Access,ShareMode,NULL,CREATE_ALWAYS,0,NULL);
#else
  hFile=fopen(Name,WriteMode ? WRITEBINARY:CREATEBINARY);
#endif
  NewFile=true;
  HandleType=FILE_HANDLENORMAL;
  SkipClose=false;
  if (NameW!=NULL)
    wcscpy(FileNameW,NameW);
  else
    *FileNameW=0;
  if (Name!=NULL)
    strcpy(FileName,Name);
  else
    WideToChar(NameW,FileName);
  AddFileToList(hFile);
  return(hFile!=BAD_HANDLE);
}


void File::AddFileToList(FileHandle hFile)
{
  if (hFile!=BAD_HANDLE)
    for (int I=0;I<sizeof(CreatedFiles)/sizeof(CreatedFiles[0]);I++)
      if (CreatedFiles[I]==NULL)
      {
        CreatedFiles[I]=this;
        break;
      }
}


#if !defined(SHELL_EXT) && !defined(SFX_MODULE)
void File::TCreate(const char *Name,const wchar *NameW,uint Mode)
{
  if (!WCreate(Name,NameW,Mode))
    ErrHandler.Exit(RARX_FATAL);
}
#endif


bool File::WCreate(const char *Name,const wchar *NameW,uint Mode)
{
  if (Create(Name,NameW,Mode))
    return(true);
  ErrHandler.SetErrorCode(RARX_CREATE);
  ErrHandler.CreateErrorMsg(Name,NameW);
  return(false);
}


bool File::Close()
{
  bool Success=true;
  if (HandleType!=FILE_HANDLENORMAL)
    HandleType=FILE_HANDLENORMAL;
  else
    if (hFile!=BAD_HANDLE)
    {
      if (!SkipClose)
      {
#ifdef _WIN_ALL
        Success=CloseHandle(hFile)==TRUE;
#else
        Success=fclose(hFile)!=EOF;
#endif
        if (Success || !RemoveCreatedActive)
          for (int I=0;I<sizeof(CreatedFiles)/sizeof(CreatedFiles[0]);I++)
            if (CreatedFiles[I]==this)
            {
              CreatedFiles[I]=NULL;
              break;
            }
      }
      hFile=BAD_HANDLE;
      if (!Success && AllowExceptions)
        ErrHandler.CloseError(FileName,FileNameW);
    }
  CloseCount++;
  return(Success);
}


void File::Flush()
{
#ifdef _WIN_ALL
  FlushFileBuffers(hFile);
#else
  fflush(hFile);
#endif
}


bool File::Delete()
{
  if (HandleType!=FILE_HANDLENORMAL)
    return(false);
  if (hFile!=BAD_HANDLE)
    Close();
  if (!AllowDelete)
    return(false);
  return(DelFile(FileName,FileNameW));
}


bool File::Rename(const char *NewName,const wchar *NewNameW)
{
  // we do not need to rename if names are already same
  bool Success=strcmp(FileName,NewName)==0;
  if (Success && *FileNameW!=0 && *NullToEmpty(NewNameW)!=0)
    Success=wcscmp(FileNameW,NewNameW)==0;

  if (!Success)
    Success=RenameFile(FileName,FileNameW,NewName,NewNameW);

  if (Success)
  {
    // renamed successfully, storing the new name
    strcpy(FileName,NewName);
    wcscpy(FileNameW,NullToEmpty(NewNameW));
  }
  return(Success);
}


void File::Write(const void *Data,size_t Size)
{
  if (Size==0)
    return;
#ifndef _WIN_CE
  if (HandleType!=FILE_HANDLENORMAL)
    switch(HandleType)
    {
      case FILE_HANDLESTD:
#ifdef _WIN_ALL
        hFile=GetStdHandle(STD_OUTPUT_HANDLE);
#else
        hFile=stdout;
#endif
        break;
      case FILE_HANDLEERR:
#ifdef _WIN_ALL
        hFile=GetStdHandle(STD_ERROR_HANDLE);
#else
        hFile=stderr;
#endif
        break;
    }
#endif
  while (1)
  {
    bool Success=false;
#ifdef _WIN_ALL
    DWORD Written=0;
    if (HandleType!=FILE_HANDLENORMAL)
    {
      // writing to stdout can fail in old Windows if data block is too large
      const size_t MaxSize=0x4000;
      for (size_t I=0;I<Size;I+=MaxSize)
      {
        Success=WriteFile(hFile,(byte *)Data+I,(DWORD)Min(Size-I,MaxSize),&Written,NULL)==TRUE;
        if (!Success)
          break;
      }
    }
    else
      Success=WriteFile(hFile,Data,(DWORD)Size,&Written,NULL)==TRUE;
#else
    int Written=fwrite(Data,1,Size,hFile);
    Success=Written==Size && !ferror(hFile);
#endif
    if (!Success && AllowExceptions && HandleType==FILE_HANDLENORMAL)
    {
#if defined(_WIN_ALL) && !defined(SFX_MODULE) && !defined(RARDLL)
      int ErrCode=GetLastError();
      int64 FilePos=Tell();
      uint64 FreeSize=GetFreeDisk(FileName);
      SetLastError(ErrCode);
      if (FreeSize>Size && FilePos-Size<=0xffffffff && FilePos+Size>0xffffffff)
        ErrHandler.WriteErrorFAT(FileName,FileNameW);
#endif
      if (ErrHandler.AskRepeatWrite(FileName,FileNameW,false))
      {
#ifndef _WIN_ALL
        clearerr(hFile);
#endif
        if (Written<Size && Written>0)
          Seek(Tell()-Written,SEEK_SET);
        continue;
      }
      ErrHandler.WriteError(NULL,NULL,FileName,FileNameW);
    }
    break;
  }
  LastWrite=true;
}


int File::Read(void *Data,size_t Size)
{
  int64 FilePos=0; // Initialized only to suppress some compilers warning.

  if (IgnoreReadErrors)
    FilePos=Tell();
  int ReadSize;
  while (true)
  {
    ReadSize=DirectRead(Data,Size);
    if (ReadSize==-1)
    {
      ErrorType=FILE_READERROR;
      if (AllowExceptions)
        if (IgnoreReadErrors)
        {
          ReadSize=0;
          for (size_t I=0;I<Size;I+=512)
          {
            Seek(FilePos+I,SEEK_SET);
            size_t SizeToRead=Min(Size-I,512);
            int ReadCode=DirectRead(Data,SizeToRead);
            ReadSize+=(ReadCode==-1) ? 512:ReadCode;
          }
        }
        else
        {
          if (HandleType==FILE_HANDLENORMAL && ErrHandler.AskRepeatRead(FileName,FileNameW))
            continue;
          ErrHandler.ReadError(FileName,FileNameW);
        }
    }
    break;
  }
  return(ReadSize);
}


// Returns -1 in case of error.
int File::DirectRead(void *Data,size_t Size)
{
#ifdef _WIN_ALL
  const size_t MaxDeviceRead=20000;
#endif
#ifndef _WIN_CE
  if (HandleType==FILE_HANDLESTD)
  {
#ifdef _WIN_ALL
    if (Size>MaxDeviceRead)
      Size=MaxDeviceRead;
    hFile=GetStdHandle(STD_INPUT_HANDLE);
#else
    hFile=stdin;
#endif
  }
#endif
#ifdef _WIN_ALL
  DWORD Read;
  if (!ReadFile(hFile,Data,(DWORD)Size,&Read,NULL))
  {
    if (IsDevice() && Size>MaxDeviceRead)
      return(DirectRead(Data,MaxDeviceRead));
    if (HandleType==FILE_HANDLESTD && GetLastError()==ERROR_BROKEN_PIPE)
      return(0);
    return(-1);
  }
  return(Read);
#else
  if (LastWrite)
  {
    fflush(hFile);
    LastWrite=false;
  }
  clearerr(hFile);
  size_t ReadSize=fread(Data,1,Size,hFile);
  if (ferror(hFile))
    return(-1);
  return((int)ReadSize);
#endif
}


void File::Seek(int64 Offset,int Method)
{
  if (!RawSeek(Offset,Method) && AllowExceptions)
    ErrHandler.SeekError(FileName,FileNameW);
}


bool File::RawSeek(int64 Offset,int Method)
{
  if (hFile==BAD_HANDLE)
    return(true);
  if (Offset<0 && Method!=SEEK_SET)
  {
    Offset=(Method==SEEK_CUR ? Tell():FileLength())+Offset;
    Method=SEEK_SET;
  }
#ifdef _WIN_ALL
  LONG HighDist=(LONG)(Offset>>32);
  if (SetFilePointer(hFile,(LONG)Offset,&HighDist,Method)==0xffffffff &&
      GetLastError()!=NO_ERROR)
    return(false);
#else
  LastWrite=false;
#if defined(_LARGEFILE_SOURCE) && !defined(_OSF_SOURCE) && !defined(__VMS)
  if (fseeko(hFile,Offset,Method)!=0)
#else
  if (fseek(hFile,(long)Offset,Method)!=0)
#endif
    return(false);
#endif
  return(true);
}


int64 File::Tell()
{
  if (hFile==BAD_HANDLE)
    if (AllowExceptions)
      ErrHandler.SeekError(FileName,FileNameW);
    else
      return(-1);
#ifdef _WIN_ALL
  LONG HighDist=0;
  uint LowDist=SetFilePointer(hFile,0,&HighDist,FILE_CURRENT);
  if (LowDist==0xffffffff && GetLastError()!=NO_ERROR)
    if (AllowExceptions)
      ErrHandler.SeekError(FileName,FileNameW);
    else
      return(-1);
  return(INT32TO64(HighDist,LowDist));
#else
#if defined(_LARGEFILE_SOURCE) && !defined(_OSF_SOURCE)
  return(ftello(hFile));
#else
  return(ftell(hFile));
#endif
#endif
}


void File::Prealloc(int64 Size)
{
#ifdef _WIN_ALL
  if (RawSeek(Size,SEEK_SET))
  {
    Truncate();
    Seek(0,SEEK_SET);
  }
#endif

#if defined(_UNIX) && defined(USE_FALLOCATE)
  // fallocate is rather new call. Only latest kernels support it.
  // So we are not using it by default yet.
  int fd = fileno(hFile);
  if (fd >= 0)
    fallocate(fd, 0, 0, Size);
#endif
}


byte File::GetByte()
{
  byte Byte=0;
  Read(&Byte,1);
  return(Byte);
}


void File::PutByte(byte Byte)
{
  Write(&Byte,1);
}


bool File::Truncate()
{
#ifdef _WIN_ALL
  return(SetEndOfFile(hFile)==TRUE);
#else
  return(false);
#endif
}


void File::SetOpenFileTime(RarTime *ftm,RarTime *ftc,RarTime *fta)
{
#ifdef _WIN_ALL
  // Workaround for OpenIndiana NAS time bug. If we cannot create a file
  // in write only mode, we need to flush the write buffer before calling
  // SetFileTime or file time will not be changed.
  if (CreateMode!=FMF_UNDEFINED && (CreateMode & FMF_WRITE)==0)
    FlushFileBuffers(hFile);

  bool sm=ftm!=NULL && ftm->IsSet();
  bool sc=ftc!=NULL && ftc->IsSet();
  bool sa=fta!=NULL && fta->IsSet();
  FILETIME fm,fc,fa;
  if (sm)
    ftm->GetWin32(&fm);
  if (sc)
    ftc->GetWin32(&fc);
  if (sa)
    fta->GetWin32(&fa);
  SetFileTime(hFile,sc ? &fc:NULL,sa ? &fa:NULL,sm ? &fm:NULL);
#endif
}


void File::SetCloseFileTime(RarTime *ftm,RarTime *fta)
{
#if defined(_UNIX) || defined(_EMX)
  SetCloseFileTimeByName(FileName,ftm,fta);
#endif
}


void File::SetCloseFileTimeByName(const char *Name,RarTime *ftm,RarTime *fta)
{
#if defined(_UNIX) || defined(_EMX)
  bool setm=ftm!=NULL && ftm->IsSet();
  bool seta=fta!=NULL && fta->IsSet();
  if (setm || seta)
  {
    utimbuf ut;
    if (setm)
      ut.modtime=ftm->GetUnix();
    else
      ut.modtime=fta->GetUnix();
    if (seta)
      ut.actime=fta->GetUnix();
    else
      ut.actime=ut.modtime;
    utime(Name,&ut);
  }
#endif
}


void File::GetOpenFileTime(RarTime *ft)
{
#ifdef _WIN_ALL
  FILETIME FileTime;
  GetFileTime(hFile,NULL,NULL,&FileTime);
  *ft=FileTime;
#endif
#if defined(_UNIX) || defined(_EMX)
  struct stat st;
  fstat(fileno(hFile),&st);
  *ft=st.st_mtime;
#endif
}


int64 File::FileLength()
{
  SaveFilePos SavePos(*this);
  Seek(0,SEEK_END);
  return(Tell());
}


void File::SetHandleType(FILE_HANDLETYPE Type)
{
  HandleType=Type;
}


bool File::IsDevice()
{
  if (hFile==BAD_HANDLE)
    return(false);
#ifdef _WIN_ALL
  uint Type=GetFileType(hFile);
  return(Type==FILE_TYPE_CHAR || Type==FILE_TYPE_PIPE);
#else
  return(isatty(fileno(hFile)));
#endif
}


#ifndef SFX_MODULE
void File::fprintf(const char *fmt,...)
{
  va_list argptr;
  va_start(argptr,fmt);
  safebuf char Msg[2*NM+1024],OutMsg[2*NM+1024];
  vsprintf(Msg,fmt,argptr);
#ifdef _WIN_ALL
  for (int Src=0,Dest=0;;Src++)
  {
    char CurChar=Msg[Src];
    if (CurChar=='\n')
      OutMsg[Dest++]='\r';
    OutMsg[Dest++]=CurChar;
    if (CurChar==0)
      break;
  }
#else
  strcpy(OutMsg,Msg);
#endif
  Write(OutMsg,strlen(OutMsg));
  va_end(argptr);
}
#endif


bool File::RemoveCreated()
{
  RemoveCreatedActive++;
  bool RetCode=true;
  for (int I=0;I<sizeof(CreatedFiles)/sizeof(CreatedFiles[0]);I++)
    if (CreatedFiles[I]!=NULL)
    {
      CreatedFiles[I]->SetExceptions(false);
      bool Success;
      if (CreatedFiles[I]->NewFile)
        Success=CreatedFiles[I]->Delete();
      else
        Success=CreatedFiles[I]->Close();
      if (Success)
        CreatedFiles[I]=NULL;
      else
        RetCode=false;
    }
  RemoveCreatedActive--;
  return(RetCode);
}


#ifndef SFX_MODULE
int64 File::Copy(File &Dest,int64 Length)
{
  Array<char> Buffer(0x10000);
  int64 CopySize=0;
  bool CopyAll=(Length==INT64NDF);

  while (CopyAll || Length>0)
  {
    Wait();
    size_t SizeToRead=(!CopyAll && Length<(int64)Buffer.Size()) ? (size_t)Length:Buffer.Size();
    int ReadSize=Read(&Buffer[0],SizeToRead);
    if (ReadSize==0)
      break;
    Dest.Write(&Buffer[0],ReadSize);
    CopySize+=ReadSize;
    if (!CopyAll)
      Length-=ReadSize;
  }
  return(CopySize);
}
#endif
