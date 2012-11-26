#include "rar.hpp"
#include "dll.hpp"

static int RarErrorToDll(RAR_EXIT ErrCode);

struct DataSet
{
  CommandData Cmd;
  CmdExtract Extract;
  Archive Arc;
  int OpenMode;
  int HeaderSize;

  DataSet():Arc(&Cmd) {};
};


HANDLE PASCAL RAROpenArchive(struct RAROpenArchiveData *r)
{
  RAROpenArchiveDataEx rx;
  memset(&rx,0,sizeof(rx));
  rx.ArcName=r->ArcName;
  rx.OpenMode=r->OpenMode;
  rx.CmtBuf=r->CmtBuf;
  rx.CmtBufSize=r->CmtBufSize;
  HANDLE hArc=RAROpenArchiveEx(&rx);
  r->OpenResult=rx.OpenResult;
  r->CmtSize=rx.CmtSize;
  r->CmtState=rx.CmtState;
  return(hArc);
}


HANDLE PASCAL RAROpenArchiveEx(struct RAROpenArchiveDataEx *r)
{
  DataSet *Data=NULL;
  try
  {
    r->OpenResult=0;
    Data=new DataSet;
    Data->Cmd.DllError=0;
    Data->OpenMode=r->OpenMode;
    Data->Cmd.FileArgs->AddString("*");

    char an[NM];
    if (r->ArcName==NULL && r->ArcNameW!=NULL)
    {
      WideToChar(r->ArcNameW,an,NM);
      r->ArcName=an;
    }

    Data->Cmd.AddArcName(r->ArcName,r->ArcNameW);
    Data->Cmd.Overwrite=OVERWRITE_ALL;
    Data->Cmd.VersionControl=1;

    Data->Cmd.Callback=r->Callback;
    Data->Cmd.UserData=r->UserData;

    if (!Data->Arc.Open(r->ArcName,r->ArcNameW,0))
    {
      r->OpenResult=ERAR_EOPEN;
      delete Data;
      return(NULL);
    }
    if (!Data->Arc.IsArchive(false))
    {
      r->OpenResult=Data->Cmd.DllError!=0 ? Data->Cmd.DllError:ERAR_BAD_ARCHIVE;
      delete Data;
      return(NULL);
    }
    r->Flags=Data->Arc.NewMhd.Flags;
    Array<byte> CmtData;
    if (r->CmtBufSize!=0 && Data->Arc.GetComment(&CmtData,NULL))
    {
      r->Flags|=2;
      size_t Size=CmtData.Size()+1;
      r->CmtState=Size>r->CmtBufSize ? ERAR_SMALL_BUF:1;
      r->CmtSize=(uint)Min(Size,r->CmtBufSize);
      memcpy(r->CmtBuf,&CmtData[0],r->CmtSize-1);
      if (Size<=r->CmtBufSize)
        r->CmtBuf[r->CmtSize-1]=0;
    }
    else
      r->CmtState=r->CmtSize=0;
    if (Data->Arc.Signed)
      r->Flags|=0x20;
    Data->Extract.ExtractArchiveInit(&Data->Cmd,Data->Arc);
    return((HANDLE)Data);
  }
  catch (RAR_EXIT ErrCode)
  {
    if (Data!=NULL && Data->Cmd.DllError!=0)
      r->OpenResult=Data->Cmd.DllError;
    else
      r->OpenResult=RarErrorToDll(ErrCode);
    if (Data != NULL)
      delete Data;
    return(NULL);
  }
  catch (std::bad_alloc) // Catch 'new' exception.
  {
    r->OpenResult=ERAR_NO_MEMORY;
    if (Data != NULL)
      delete Data;
  }
}


int PASCAL RARCloseArchive(HANDLE hArcData)
{
  DataSet *Data=(DataSet *)hArcData;
  bool Success=Data==NULL ? false:Data->Arc.Close();
  delete Data;
  return(Success ? 0:ERAR_ECLOSE);
}


int PASCAL RARReadHeader(HANDLE hArcData,struct RARHeaderData *D)
{
  struct RARHeaderDataEx X;
  memset(&X,0,sizeof(X));

  int Code=RARReadHeaderEx(hArcData,&X);

  strncpyz(D->ArcName,X.ArcName,ASIZE(D->ArcName));
  strncpyz(D->FileName,X.FileName,ASIZE(D->FileName));
  D->Flags=X.Flags;
  D->PackSize=X.PackSize;
  D->UnpSize=X.UnpSize;
  D->HostOS=X.HostOS;
  D->FileCRC=X.FileCRC;
  D->FileTime=X.FileTime;
  D->UnpVer=X.UnpVer;
  D->Method=X.Method;
  D->FileAttr=X.FileAttr;
  D->CmtSize=0;
  D->CmtState=0;

  return Code;
}


int PASCAL RARReadHeaderEx(HANDLE hArcData,struct RARHeaderDataEx *D)
{
  DataSet *Data=(DataSet *)hArcData;
  try
  {
    if ((Data->HeaderSize=(int)Data->Arc.SearchBlock(FILE_HEAD))<=0)
    {
      if (Data->Arc.Volume && Data->Arc.GetHeaderType()==ENDARC_HEAD &&
          (Data->Arc.EndArcHead.Flags & EARC_NEXT_VOLUME))
        if (MergeArchive(Data->Arc,NULL,false,'L'))
        {
          Data->Extract.SignatureFound=false;
          Data->Arc.Seek(Data->Arc.CurBlockPos,SEEK_SET);
          return(RARReadHeaderEx(hArcData,D));
        }
        else
          return(ERAR_EOPEN);
      return(Data->Arc.BrokenFileHeader ? ERAR_BAD_DATA:ERAR_END_ARCHIVE);
    }
    if (Data->OpenMode==RAR_OM_LIST && (Data->Arc.NewLhd.Flags & LHD_SPLIT_BEFORE)!=0)
    {
      int Code=RARProcessFile(hArcData,RAR_SKIP,NULL,NULL);
      if (Code==0)
        return(RARReadHeaderEx(hArcData,D));
      else
        return(Code);
    }
    strncpyz(D->ArcName,Data->Arc.FileName,ASIZE(D->ArcName));
    if (*Data->Arc.FileNameW)
      wcsncpy(D->ArcNameW,Data->Arc.FileNameW,ASIZE(D->ArcNameW));
    else
      CharToWide(Data->Arc.FileName,D->ArcNameW);
    strncpyz(D->FileName,Data->Arc.NewLhd.FileName,ASIZE(D->FileName));
    if (*Data->Arc.NewLhd.FileNameW)
      wcsncpy(D->FileNameW,Data->Arc.NewLhd.FileNameW,ASIZE(D->FileNameW));
    else
    {
#ifdef _WIN_ALL
      char AnsiName[NM];
      OemToCharA(Data->Arc.NewLhd.FileName,AnsiName);
      if (!CharToWide(AnsiName,D->FileNameW,ASIZE(D->FileNameW)))
        *D->FileNameW=0;
#else
      if (!CharToWide(Data->Arc.NewLhd.FileName,D->FileNameW,ASIZE(D->FileNameW)))
        *D->FileNameW=0;
#endif
    }
    D->Flags=Data->Arc.NewLhd.Flags;
    D->PackSize=Data->Arc.NewLhd.PackSize;
    D->PackSizeHigh=Data->Arc.NewLhd.HighPackSize;
    D->UnpSize=Data->Arc.NewLhd.UnpSize;
    D->UnpSizeHigh=Data->Arc.NewLhd.HighUnpSize;
    D->HostOS=Data->Arc.NewLhd.HostOS;
    D->FileCRC=Data->Arc.NewLhd.FileCRC;
    D->FileTime=Data->Arc.NewLhd.FileTime;
    D->UnpVer=Data->Arc.NewLhd.UnpVer;
    D->Method=Data->Arc.NewLhd.Method;
    D->FileAttr=Data->Arc.NewLhd.FileAttr;
    D->CmtSize=0;
    D->CmtState=0;
  }
  catch (RAR_EXIT ErrCode)
  {
    return(Data->Cmd.DllError!=0 ? Data->Cmd.DllError:RarErrorToDll(ErrCode));
  }
  return(0);
}


int PASCAL ProcessFile(HANDLE hArcData,int Operation,char *DestPath,char *DestName,wchar *DestPathW,wchar *DestNameW)
{
  DataSet *Data=(DataSet *)hArcData;
  try
  {
    Data->Cmd.DllError=0;
    if (Data->OpenMode==RAR_OM_LIST || Data->OpenMode==RAR_OM_LIST_INCSPLIT ||
        Operation==RAR_SKIP && !Data->Arc.Solid)
    {
      if (Data->Arc.Volume &&
          Data->Arc.GetHeaderType()==FILE_HEAD &&
          (Data->Arc.NewLhd.Flags & LHD_SPLIT_AFTER)!=0)
        if (MergeArchive(Data->Arc,NULL,false,'L'))
        {
          Data->Extract.SignatureFound=false;
          Data->Arc.Seek(Data->Arc.CurBlockPos,SEEK_SET);
          return(0);
        }
        else
          return(ERAR_EOPEN);
      Data->Arc.SeekToNext();
    }
    else
    {
      Data->Cmd.DllOpMode=Operation;

      if (DestPath!=NULL || DestName!=NULL)
      {
#ifdef _WIN_ALL
        OemToCharA(NullToEmpty(DestPath),Data->Cmd.ExtrPath);
#else
        strcpy(Data->Cmd.ExtrPath,NullToEmpty(DestPath));
#endif
        AddEndSlash(Data->Cmd.ExtrPath);
#ifdef _WIN_ALL
        OemToCharA(NullToEmpty(DestName),Data->Cmd.DllDestName);
#else
        strcpy(Data->Cmd.DllDestName,NullToEmpty(DestName));
#endif
      }
      else
      {
        *Data->Cmd.ExtrPath=0;
        *Data->Cmd.DllDestName=0;
      }

      if (DestPathW!=NULL || DestNameW!=NULL)
      {
        wcsncpy(Data->Cmd.ExtrPathW,NullToEmpty(DestPathW),NM-2);
        AddEndSlash(Data->Cmd.ExtrPathW);
        wcsncpy(Data->Cmd.DllDestNameW,NullToEmpty(DestNameW),NM-1);

        if (*Data->Cmd.DllDestNameW!=0 && *Data->Cmd.DllDestName==0)
          WideToChar(Data->Cmd.DllDestNameW,Data->Cmd.DllDestName);
      }
      else
      {
        *Data->Cmd.ExtrPathW=0;
        *Data->Cmd.DllDestNameW=0;
      }

      strcpy(Data->Cmd.Command,Operation==RAR_EXTRACT ? "X":"T");
      Data->Cmd.Test=Operation!=RAR_EXTRACT;
      bool Repeat=false;
      Data->Extract.ExtractCurrentFile(&Data->Cmd,Data->Arc,Data->HeaderSize,Repeat);

      // Now we process extra file information if any.
      //
      // Archive can be closed if we process volumes, next volume is missing
      // and current one is already removed or deleted. So we need to check
      // if archive is still open to avoid calling file operations on
      // the invalid file handle. Some of our file operations like Seek()
      // process such invalid handle correctly, some not.
      while (Data->Arc.IsOpened() && Data->Arc.ReadHeader()!=0 && 
             Data->Arc.GetHeaderType()==NEWSUB_HEAD)
      {
        Data->Extract.ExtractCurrentFile(&Data->Cmd,Data->Arc,Data->HeaderSize,Repeat);
        Data->Arc.SeekToNext();
      }
      Data->Arc.Seek(Data->Arc.CurBlockPos,SEEK_SET);
    }
  }
  catch (RAR_EXIT ErrCode)
  {
    return(Data->Cmd.DllError!=0 ? Data->Cmd.DllError:RarErrorToDll(ErrCode));
  }
  return(Data->Cmd.DllError);
}


int PASCAL RARProcessFile(HANDLE hArcData,int Operation,char *DestPath,char *DestName)
{
  return(ProcessFile(hArcData,Operation,DestPath,DestName,NULL,NULL));
}


int PASCAL RARProcessFileW(HANDLE hArcData,int Operation,wchar *DestPath,wchar *DestName)
{
  return(ProcessFile(hArcData,Operation,NULL,NULL,DestPath,DestName));
}


void PASCAL RARSetChangeVolProc(HANDLE hArcData,CHANGEVOLPROC ChangeVolProc)
{
  DataSet *Data=(DataSet *)hArcData;
  Data->Cmd.ChangeVolProc=ChangeVolProc;
}


void PASCAL RARSetCallback(HANDLE hArcData,UNRARCALLBACK Callback,LPARAM UserData)
{
  DataSet *Data=(DataSet *)hArcData;
  Data->Cmd.Callback=Callback;
  Data->Cmd.UserData=UserData;
}


void PASCAL RARSetProcessDataProc(HANDLE hArcData,PROCESSDATAPROC ProcessDataProc)
{
  DataSet *Data=(DataSet *)hArcData;
  Data->Cmd.ProcessDataProc=ProcessDataProc;
}


#ifndef RAR_NOCRYPT
void PASCAL RARSetPassword(HANDLE hArcData,char *Password)
{
  DataSet *Data=(DataSet *)hArcData;
  wchar PasswordW[MAXPASSWORD];
  GetWideName(Password,NULL,PasswordW,ASIZE(PasswordW));
  Data->Cmd.Password.Set(PasswordW);
  cleandata(PasswordW,sizeof(PasswordW));
}
#endif


int PASCAL RARGetDllVersion()
{
  return(RAR_DLL_VERSION);
}


static int RarErrorToDll(RAR_EXIT ErrCode)
{
  switch(ErrCode)
  {
    case RARX_FATAL:
      return(ERAR_EREAD);
    case RARX_CRC:
      return(ERAR_BAD_DATA);
    case RARX_WRITE:
      return(ERAR_EWRITE);
    case RARX_OPEN:
      return(ERAR_EOPEN);
    case RARX_CREATE:
      return(ERAR_ECREATE);
    case RARX_MEMORY:
      return(ERAR_NO_MEMORY);
    case RARX_SUCCESS:
      return(0);
    default:
      return(ERAR_UNKNOWN);
  }
}
