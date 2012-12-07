#include "rar.hpp"




#if defined(RARDLL) && defined(_MSC_VER) && !defined(_WIN_64)
// Disable the run time stack check for unrar.dll, so we can manipulate
// with ChangeVolProc call type below. Run time check would intercept
// a wrong ESP before we restore it.
#pragma runtime_checks( "s", off )
#endif

bool MergeArchive(Archive &Arc,ComprDataIO *DataIO,bool ShowFileName,char Command)
{
  RAROptions *Cmd=Arc.GetRAROptions();

  int HeaderType=Arc.GetHeaderType();
  FileHeader *hd=HeaderType==NEWSUB_HEAD ? &Arc.SubHead:&Arc.NewLhd;
  bool SplitHeader=(HeaderType==FILE_HEAD || HeaderType==NEWSUB_HEAD) &&
                   (hd->Flags & LHD_SPLIT_AFTER)!=0;

  if (DataIO!=NULL && SplitHeader && hd->UnpVer>=20 &&
      hd->FileCRC!=0xffffffff && DataIO->PackedCRC!=~hd->FileCRC)
  {
    Log(Arc.FileName,St(MDataBadCRC),hd->FileName,Arc.FileName);
  }

  int64 PosBeforeClose=Arc.Tell();

  if (DataIO!=NULL)
    DataIO->ProcessedArcSize+=Arc.FileLength();

  Arc.Close();

  char NextName[NM];
  wchar NextNameW[NM];
  strcpy(NextName,Arc.FileName);
  wcscpy(NextNameW,Arc.FileNameW);
  NextVolumeName(NextName,NextNameW,ASIZE(NextName),(Arc.NewMhd.Flags & MHD_NEWNUMBERING)==0 || Arc.OldFormat);

#if !defined(SFX_MODULE) && !defined(RARDLL)
  bool RecoveryDone=false;
#endif
  bool FailedOpen=false,OldSchemeTested=false;

#if !defined(GUI) && !defined(SILENT)
  // In -vp mode we force the pause before next volume even if it is present
  // and even if we are on the hard disk. It is important when user does not
  // want to process partially downloaded volumes preliminary.
  if (Cmd->VolumePause && !AskNextVol(NextName,NextNameW))
    FailedOpen=true;
#endif

  if (!FailedOpen)
    while (!Arc.Open(NextName,NextNameW,0))
    {
      // We need to open a new volume which size was not calculated
      // in total size before, so we cannot calculate the total progress
      // anymore. Let's reset the total size to zero and stop 
      // the total progress.
      if (DataIO!=NULL)
        DataIO->TotalArcSize=0;

      if (!OldSchemeTested)
      {
        // Checking for new style volumes renamed by user to old style
        // name format. Some users did it for unknown reason.
        char AltNextName[NM];
        wchar AltNextNameW[NM];
        strcpy(AltNextName,Arc.FileName);
        wcscpy(AltNextNameW,Arc.FileNameW);
        NextVolumeName(AltNextName,AltNextNameW,ASIZE(AltNextName),true);
        OldSchemeTested=true;
        if (Arc.Open(AltNextName,AltNextNameW,0))
        {
          strcpy(NextName,AltNextName);
          wcscpy(NextNameW,AltNextNameW);
          break;
        }
      }
#ifdef RARDLL
      bool DllVolChanged=false;

      if (Cmd->Callback!=NULL)
      {
        GetWideName(NextName,NextNameW,NextNameW,ASIZE(NextNameW));
        char CurName[ASIZE(NextName)];
        strcpy(CurName,NextName);
        wchar CurNameW[ASIZE(NextNameW)];
        wcscpy(CurNameW,NextNameW);
        if (Cmd->Callback(UCM_CHANGEVOLUMEW,Cmd->UserData,(LPARAM)NextNameW,RAR_VOL_ASK)!=-1 &&
            wcscmp(CurNameW,NextNameW)!=0)
        {
          *NextName=0;
          DllVolChanged=true;
        }
        else
          if (Cmd->Callback(UCM_CHANGEVOLUME,Cmd->UserData,(LPARAM)NextName,RAR_VOL_ASK)!=-1 &&
              strcmp(CurName,NextName)!=0)
          {
            *NextNameW=0;
            DllVolChanged=true;
          }
      }
      if (!DllVolChanged && Cmd->ChangeVolProc!=NULL)
      {
        // Here we preserve ESP value. It is necessary for those developers,
        // who still define ChangeVolProc callback as "C" type function,
        // even though in year 2001 we announced in unrar.dll whatsnew.txt
        // that it will be PASCAL type (for compatibility with Visual Basic).
#if defined(_MSC_VER)
#ifndef _WIN_64
        __asm mov ebx,esp
#endif
#elif defined(_WIN_ALL) && defined(__BORLANDC__)
        _EBX=_ESP;
#endif
        int RetCode=Cmd->ChangeVolProc(NextName,RAR_VOL_ASK);

        // Restore ESP after ChangeVolProc with wrongly defined calling
        // convention broken it.
#if defined(_MSC_VER)
#ifndef _WIN_64
      __asm mov esp,ebx
#endif
#elif defined(_WIN_ALL) && defined(__BORLANDC__)
      _ESP=_EBX;
#endif
      if (RetCode!=0)
      {
        *NextNameW=0;
        DllVolChanged=true;
      }
    }
    if (!DllVolChanged)
    {
      Cmd->DllError=ERAR_EOPEN;
      FailedOpen=true;
      break;
    }
#else // !RARDLL

#if !defined(SFX_MODULE) && !defined(_WIN_CE)
      if (!RecoveryDone)
      {
        RecVolumes RecVol;
        RecVol.Restore(Cmd,Arc.FileName,Arc.FileNameW,true);
        RecoveryDone=true;
        continue;
      }
#endif

#ifndef GUI
      if (!Cmd->VolumePause && !IsRemovable(NextName))
      {
        FailedOpen=true;
        break;
      }
#endif
#ifndef SILENT
      if (Cmd->AllYes || !AskNextVol(NextName,NextNameW))
#endif
      {
        FailedOpen=true;
        break;
      }

#endif // RARDLL
    }
  
  if (FailedOpen)
  {
#if !defined(SILENT) && !defined(_WIN_CE)
      Log(Arc.FileName,St(MAbsNextVol),NextName);
#endif
    Arc.Open(Arc.FileName,Arc.FileNameW,0);
    Arc.Seek(PosBeforeClose,SEEK_SET);
    return(false);
  }
  Arc.CheckArc(true);
#ifdef RARDLL
  if (Cmd->Callback!=NULL)
  {
    GetWideName(NextName,NextNameW,NextNameW,ASIZE(NextNameW));
    if (Cmd->Callback(UCM_CHANGEVOLUMEW,Cmd->UserData,(LPARAM)NextNameW,RAR_VOL_NOTIFY)==-1)
      return(false);
    if (Cmd->Callback(UCM_CHANGEVOLUME,Cmd->UserData,(LPARAM)NextName,RAR_VOL_NOTIFY)==-1)
      return(false);
  }
  if (Cmd->ChangeVolProc!=NULL)
  {
#if defined(_WIN_ALL) && !defined(_MSC_VER) && !defined(__MINGW32__)
    _EBX=_ESP;
#endif
    int RetCode=Cmd->ChangeVolProc(NextName,RAR_VOL_NOTIFY);
#if defined(_WIN_ALL) && !defined(_MSC_VER) && !defined(__MINGW32__)
    _ESP=_EBX;
#endif
    if (RetCode==0)
      return(false);
  }
#endif

  if (Command=='T' || Command=='X' || Command=='E')
    mprintf(St(Command=='T' ? MTestVol:MExtrVol),Arc.FileName);


  if (SplitHeader)
    Arc.SearchBlock(HeaderType);
  else
    Arc.ReadHeader();
  if (Arc.GetHeaderType()==FILE_HEAD)
  {
    Arc.ConvertAttributes();
    Arc.Seek(Arc.NextBlockPos-Arc.NewLhd.FullPackSize,SEEK_SET);
  }
#ifndef GUI
  if (ShowFileName)
  {
    char OutName[NM];
    IntToExt(Arc.NewLhd.FileName,OutName);
#ifdef UNICODE_SUPPORTED
    bool WideName=(Arc.NewLhd.Flags & LHD_UNICODE) && UnicodeEnabled();
    if (WideName)
    {
      wchar NameW[NM];
      ConvertPath(Arc.NewLhd.FileNameW,NameW);
      char Name[NM];
      if (WideToChar(NameW,Name) && IsNameUsable(Name))
        strcpy(OutName,Name);
    }
#endif
    mprintf(St(MExtrPoints),OutName);
    if (!Cmd->DisablePercentage)
      mprintf("     ");
  }
#endif
  if (DataIO!=NULL)
  {
    if (HeaderType==ENDARC_HEAD)
      DataIO->UnpVolume=false;
    else
    {
      DataIO->UnpVolume=(hd->Flags & LHD_SPLIT_AFTER)!=0;
      DataIO->SetPackedSizeToRead(hd->FullPackSize);
    }
#ifdef SFX_MODULE
    DataIO->UnpArcSize=Arc.FileLength();
#endif
    
    // Reset the size of packed data read from current volume. It is used
    // to display the total progress and preceding volumes are already
    // compensated with ProcessedArcSize, so we need to reset this variable.
    DataIO->CurUnpRead=0;

    DataIO->PackedCRC=0xffffffff;
//    DataIO->SetFiles(&Arc,NULL);
  }
  return(true);
}

#if defined(RARDLL) && defined(_MSC_VER) && !defined(_WIN_64)
// Restore the run time stack check for unrar.dll.
#pragma runtime_checks( "s", restore )
#endif






#ifndef SILENT
bool AskNextVol(char *ArcName,wchar *ArcNameW)
{
  eprintf(St(MAskNextVol),ArcName);
  if (Ask(St(MContinueQuit))==2)
    return(false);
  return(true);
}
#endif
