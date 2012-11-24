#include "rar.hpp"


static bool UserBreak;

ErrorHandler::ErrorHandler()
{
  Clean();
}


void ErrorHandler::Clean()
{
  ExitCode=RARX_SUCCESS;
  ErrCount=0;
  EnableBreak=true;
  Silent=false;
  DoShutdown=false;
}


void ErrorHandler::MemoryError()
{
  MemoryErrorMsg();
  Throw(RARX_MEMORY);
}


void ErrorHandler::OpenError(const char *FileName,const wchar *FileNameW)
{
#ifndef SILENT
  OpenErrorMsg(FileName);
  Throw(RARX_OPEN);
#endif
}


void ErrorHandler::CloseError(const char *FileName,const wchar *FileNameW)
{
#ifndef SILENT
  if (!UserBreak)
  {
    ErrMsg(NULL,St(MErrFClose),FileName);
    SysErrMsg();
  }
#endif
#if !defined(SILENT) || defined(RARDLL)
  Throw(RARX_FATAL);
#endif
}


void ErrorHandler::ReadError(const char *FileName,const wchar *FileNameW)
{
#ifndef SILENT
  ReadErrorMsg(NULL,NULL,FileName,FileNameW);
#endif
#if !defined(SILENT) || defined(RARDLL)
  Throw(RARX_FATAL);
#endif
}


bool ErrorHandler::AskRepeatRead(const char *FileName,const wchar *FileNameW)
{
#if !defined(SILENT) && !defined(SFX_MODULE) && !defined(_WIN_CE)
  if (!Silent)
  {
    SysErrMsg();
    mprintf("\n");
    Log(NULL,St(MErrRead),FileName);
    return(Ask(St(MRetryAbort))==1);
  }
#endif
  return(false);
}


void ErrorHandler::WriteError(const char *ArcName,const wchar *ArcNameW,const char *FileName,const wchar *FileNameW)
{
#ifndef SILENT
  WriteErrorMsg(ArcName,ArcNameW,FileName,FileNameW);
#endif
#if !defined(SILENT) || defined(RARDLL)
  Throw(RARX_WRITE);
#endif
}


#ifdef _WIN_ALL
void ErrorHandler::WriteErrorFAT(const char *FileName,const wchar *FileNameW)
{
#if !defined(SILENT) && !defined(SFX_MODULE)
  SysErrMsg();
  ErrMsg(NULL,St(MNTFSRequired),FileName);
#endif
#if !defined(SILENT) && !defined(SFX_MODULE) || defined(RARDLL)
  Throw(RARX_WRITE);
#endif
}
#endif


bool ErrorHandler::AskRepeatWrite(const char *FileName,const wchar *FileNameW,bool DiskFull)
{
#if !defined(SILENT) && !defined(_WIN_CE)
  if (!Silent)
  {
    SysErrMsg();
    mprintf("\n");
    Log(NULL,St(DiskFull ? MNotEnoughDisk:MErrWrite),FileName);
    return(Ask(St(MRetryAbort))==1);
  }
#endif
  return(false);
}


void ErrorHandler::SeekError(const char *FileName,const wchar *FileNameW)
{
#ifndef SILENT
  if (!UserBreak)
  {
    ErrMsg(NULL,St(MErrSeek),FileName);
    SysErrMsg();
  }
#endif
#if !defined(SILENT) || defined(RARDLL)
  Throw(RARX_FATAL);
#endif
}


void ErrorHandler::GeneralErrMsg(const char *Msg)
{
#ifndef SILENT
  Log(NULL,"%s",Msg);
  SysErrMsg();
#endif
}


void ErrorHandler::MemoryErrorMsg()
{
#ifndef SILENT
  ErrMsg(NULL,St(MErrOutMem));
#endif
}


void ErrorHandler::OpenErrorMsg(const char *FileName,const wchar *FileNameW)
{
  OpenErrorMsg(NULL,NULL,FileName,FileNameW);
}


void ErrorHandler::OpenErrorMsg(const char *ArcName,const wchar *ArcNameW,const char *FileName,const wchar *FileNameW)
{
#ifndef SILENT
  if (FileName!=NULL)
    Log(ArcName,St(MCannotOpen),FileName);
  Alarm();
  SysErrMsg();
#endif
}


void ErrorHandler::CreateErrorMsg(const char *FileName,const wchar *FileNameW)
{
  CreateErrorMsg(NULL,NULL,FileName,FileNameW);
}


void ErrorHandler::CreateErrorMsg(const char *ArcName,const wchar *ArcNameW,const char *FileName,const wchar *FileNameW)
{
#ifndef SILENT
  if (FileName!=NULL)
    Log(ArcName,St(MCannotCreate),FileName);
  Alarm();

#if defined(_WIN_ALL) && !defined(_WIN_CE) && defined(MAX_PATH)
  CheckLongPathErrMsg(FileName,FileNameW);
#endif

  SysErrMsg();
#endif
}


// Check the path length and display the error message if it is too long.
void ErrorHandler::CheckLongPathErrMsg(const char *FileName,const wchar *FileNameW)
{
#if defined(_WIN_ALL) && !defined(_WIN_CE) && !defined (SILENT) && defined(MAX_PATH)
  if (GetLastError()==ERROR_PATH_NOT_FOUND)
  {
    wchar WideFileName[NM];
    GetWideName(FileName,FileNameW,WideFileName,ASIZE(WideFileName));
    size_t NameLength=wcslen(WideFileName);
    if (!IsFullPath(WideFileName))
    {
      wchar CurDir[NM];
      GetCurrentDirectoryW(ASIZE(CurDir),CurDir);
      NameLength+=wcslen(CurDir)+1;
    }
    if (NameLength>MAX_PATH)
    {
      Log(NULL,St(MMaxPathLimit),MAX_PATH);
    }
  }
#endif
}


void ErrorHandler::ReadErrorMsg(const char *ArcName,const wchar *ArcNameW,const char *FileName,const wchar *FileNameW)
{
#ifndef SILENT
  ErrMsg(ArcName,St(MErrRead),FileName);
  SysErrMsg();
#endif
}


void ErrorHandler::WriteErrorMsg(const char *ArcName,const wchar *ArcNameW,const char *FileName,const wchar *FileNameW)
{
#ifndef SILENT
  ErrMsg(ArcName,St(MErrWrite),FileName);
  SysErrMsg();
#endif
}


void ErrorHandler::Exit(RAR_EXIT ExitCode)
{
#ifndef SFX_MODULE
  Alarm();
#endif
  Throw(ExitCode);
}


#ifndef GUI
void ErrorHandler::ErrMsg(const char *ArcName,const char *fmt,...)
{
  safebuf char Msg[NM+1024];
  va_list argptr;
  va_start(argptr,fmt);
  vsprintf(Msg,fmt,argptr);
  va_end(argptr);
#ifdef _WIN_ALL
  if (UserBreak)
    Sleep(5000);
#endif
  Alarm();
  if (*Msg)
  {
    Log(ArcName,"\n%s",Msg);
    mprintf("\n%s\n",St(MProgAborted));
  }
}
#endif


void ErrorHandler::SetErrorCode(RAR_EXIT Code)
{
  switch(Code)
  {
    case RARX_WARNING:
    case RARX_USERBREAK:
      if (ExitCode==RARX_SUCCESS)
        ExitCode=Code;
      break;
    case RARX_FATAL:
      if (ExitCode==RARX_SUCCESS || ExitCode==RARX_WARNING)
        ExitCode=RARX_FATAL;
      break;
    default:
      ExitCode=Code;
      break;
  }
  ErrCount++;
}


#if !defined(GUI) && !defined(_SFX_RTL_)
#ifdef _WIN_ALL
BOOL __stdcall ProcessSignal(DWORD SigType)
#else
#if defined(__sun)
extern "C"
#endif
void _stdfunction ProcessSignal(int SigType)
#endif
{
#ifdef _WIN_ALL
  // When a console application is run as a service, this allows the service
  // to continue running after the user logs off. 
  if (SigType==CTRL_LOGOFF_EVENT)
    return(TRUE);
#endif
  UserBreak=true;
  mprintf(St(MBreak));
  for (int I=0;!File::RemoveCreated() && I<3;I++)
  {
#ifdef _WIN_ALL
    Sleep(100);
#endif
  }
#if defined(USE_RC) && !defined(SFX_MODULE) && !defined(_WIN_CE) && !defined(RARDLL)
  ExtRes.UnloadDLL();
#endif
  exit(RARX_USERBREAK);
#if defined(_WIN_ALL) && !defined(_MSC_VER)
  // never reached, just to avoid a compiler warning
  return(TRUE);
#endif
}
#endif


void ErrorHandler::SetSignalHandlers(bool Enable)
{
  EnableBreak=Enable;
#if !defined(GUI) && !defined(_SFX_RTL_)
#ifdef _WIN_ALL
  SetConsoleCtrlHandler(Enable ? ProcessSignal:NULL,TRUE);
//  signal(SIGBREAK,Enable ? ProcessSignal:SIG_IGN);
#else
  signal(SIGINT,Enable ? ProcessSignal:SIG_IGN);
  signal(SIGTERM,Enable ? ProcessSignal:SIG_IGN);
#endif
#endif
}


void ErrorHandler::Throw(RAR_EXIT Code)
{
  if (Code==RARX_USERBREAK && !EnableBreak)
    return;
  ErrHandler.SetErrorCode(Code);
#ifdef ALLOW_EXCEPTIONS
  throw Code;
#else
  File::RemoveCreated();
  exit(Code);
#endif
}


void ErrorHandler::SysErrMsg()
{
#if !defined(SFX_MODULE) && !defined(SILENT)
#ifdef _WIN_ALL
  wchar *lpMsgBuf=NULL;
  int ErrType=GetLastError();
  if (ErrType!=0 && FormatMessage(FORMAT_MESSAGE_ALLOCATE_BUFFER|FORMAT_MESSAGE_FROM_SYSTEM,
              NULL,ErrType,MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
              (LPTSTR)&lpMsgBuf,0,NULL))
  {
    wchar *CurMsg=lpMsgBuf;
    while (CurMsg!=NULL)
    {
      while (*CurMsg=='\r' || *CurMsg=='\n')
        CurMsg++;
      if (*CurMsg==0)
        break;
      wchar *EndMsg=wcschr(CurMsg,'\r');
      if (EndMsg==NULL)
        EndMsg=wcschr(CurMsg,'\n');
      if (EndMsg!=NULL)
      {
        *EndMsg=0;
        EndMsg++;
      }
      // We use ASCII for output in Windows console, so let's convert Unicode
      // message to single byte.
      size_t Length=wcslen(CurMsg)*2; // Must be enough for DBCS characters.
      char *MsgA=(char *)malloc(Length+2);
      if (MsgA!=NULL)
      {
        WideToChar(CurMsg,MsgA,Length+1);
        MsgA[Length]=0;
        Log(NULL,"\n%s",MsgA);
        free(MsgA);
      }
      CurMsg=EndMsg;
    }
  }
  LocalFree( lpMsgBuf );
#endif

#if defined(_UNIX) || defined(_EMX)
  if (errno!=0)
  {
    char *err=strerror(errno);
    if (err!=NULL)
      Log(NULL,"\n%s",err);
  }
#endif

#endif
}




