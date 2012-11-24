#include "rar.hpp"

CmdExtract::CmdExtract()
{
  *ArcName=0; 
  *ArcNameW=0;

  *DestFileName=0;
  *DestFileNameW=0;

  TotalFileCount=0;
  Password.Set(L"");
  Unp=new Unpack(&DataIO);
  Unp->Init();
}


CmdExtract::~CmdExtract()
{
  delete Unp;
}


void CmdExtract::DoExtract(CommandData *Cmd)
{
  PasswordCancelled=false;
  DataIO.SetCurrentCommand(*Cmd->Command);

  FindData FD;
  while (Cmd->GetArcName(ArcName,ArcNameW,ASIZE(ArcName)))
    if (FindFile::FastFind(ArcName,ArcNameW,&FD))
      DataIO.TotalArcSize+=FD.Size;

  Cmd->ArcNames->Rewind();
  while (Cmd->GetArcName(ArcName,ArcNameW,ASIZE(ArcName)))
  {
    while (true)
    {
      SecPassword PrevCmdPassword;
      PrevCmdPassword=Cmd->Password;

      EXTRACT_ARC_CODE Code=ExtractArchive(Cmd);

      // Restore Cmd->Password, which could be changed in IsArchive() call
      // for next header encrypted archive.
      Cmd->Password=PrevCmdPassword;

      if (Code!=EXTRACT_ARC_REPEAT)
        break;
    }
    if (FindFile::FastFind(ArcName,ArcNameW,&FD))
      DataIO.ProcessedArcSize+=FD.Size;
  }

  if (TotalFileCount==0 && *Cmd->Command!='I')
  {
    if (!PasswordCancelled)
    {
      mprintf(St(MExtrNoFiles));
    }
    ErrHandler.SetErrorCode(RARX_NOFILES);
  }
#ifndef GUI
  else
    if (!Cmd->DisableDone)
      if (*Cmd->Command=='I')
        mprintf(St(MDone));
      else
        if (ErrHandler.GetErrorCount()==0)
          mprintf(St(MExtrAllOk));
        else
          mprintf(St(MExtrTotalErr),ErrHandler.GetErrorCount());
#endif
}


void CmdExtract::ExtractArchiveInit(CommandData *Cmd,Archive &Arc)
{
  DataIO.UnpArcSize=Arc.FileLength();

  FileCount=0;
  MatchedArgs=0;
#ifndef SFX_MODULE
  FirstFile=true;
#endif

  PasswordAll=(Cmd->Password.IsSet());
  if (PasswordAll)
    Password=Cmd->Password;

  DataIO.UnpVolume=false;

  PrevExtracted=false;
  SignatureFound=false;
  AllMatchesExact=true;
  ReconstructDone=false;
  AnySolidDataUnpackedWell=false;

  StartTime.SetCurrentTime();
}


EXTRACT_ARC_CODE CmdExtract::ExtractArchive(CommandData *Cmd)
{
  Archive Arc(Cmd);
  if (!Arc.WOpen(ArcName,ArcNameW))
  {
    ErrHandler.SetErrorCode(RARX_OPEN);
    return(EXTRACT_ARC_NEXT);
  }

  if (!Arc.IsArchive(true))
  {
#ifndef GUI
    mprintf(St(MNotRAR),ArcName);
#endif
    if (CmpExt(ArcName,"rar"))
      ErrHandler.SetErrorCode(RARX_WARNING);
    return(EXTRACT_ARC_NEXT);
  }

  // Archive with corrupt encrypted header can be closed in IsArchive() call.
//  if (!Arc.IsOpened())
//    return(EXTRACT_ARC_NEXT);

#ifndef SFX_MODULE
  if (Arc.Volume && Arc.NotFirstVolume)
  {
    char FirstVolName[NM];
    VolNameToFirstName(ArcName,FirstVolName,(Arc.NewMhd.Flags & MHD_NEWNUMBERING)!=0);

    // If several volume names from same volume set are specified
    // and current volume is not first in set and first volume is present
    // and specified too, let's skip the current volume.
    if (stricomp(ArcName,FirstVolName)!=0 && FileExist(FirstVolName) &&
        Cmd->ArcNames->Search(FirstVolName,NULL,false))
      return(EXTRACT_ARC_NEXT);
  }
#endif

  int64 VolumeSetSize=0; // Total size of volumes after the current volume.

  if (Arc.Volume)
  {
    // Calculate the total size of all accessible volumes.
    // This size is necessary to display the correct total progress indicator.

    char NextName[NM];
    wchar NextNameW[NM];

    strcpy(NextName,Arc.FileName);
    wcscpy(NextNameW,Arc.FileNameW);

    while (true)
    {
      // First volume is already added to DataIO.TotalArcSize 
      // in initial TotalArcSize calculation in DoExtract.
      // So we skip it and start from second volume.
      NextVolumeName(NextName,NextNameW,ASIZE(NextName),(Arc.NewMhd.Flags & MHD_NEWNUMBERING)==0 || Arc.OldFormat);
      struct FindData FD;
      if (FindFile::FastFind(NextName,NextNameW,&FD))
        VolumeSetSize+=FD.Size;
      else
        break;
    }
    DataIO.TotalArcSize+=VolumeSetSize;
  }

  ExtractArchiveInit(Cmd,Arc);

  if (*Cmd->Command=='T' || *Cmd->Command=='I')
    Cmd->Test=true;


#ifndef GUI
  if (*Cmd->Command=='I')
    Cmd->DisablePercentage=true;
  else
    if (Cmd->Test)
      mprintf(St(MExtrTest),ArcName);
    else
      mprintf(St(MExtracting),ArcName);
#endif

  Arc.ViewComment();

  // RAR can close a corrupt encrypted archive
//  if (!Arc.IsOpened())
//    return(EXTRACT_ARC_NEXT);


  while (1)
  {
    size_t Size=Arc.ReadHeader();
    bool Repeat=false;
    if (!ExtractCurrentFile(Cmd,Arc,Size,Repeat))
      if (Repeat)
      {
        // If we started extraction from not first volume and need to
        // restart it from first, we must correct DataIO.TotalArcSize
        // for correct total progress display. We subtract the size
        // of current volume and all volumes after it and add the size
        // of new (first) volume.
        FindData OldArc,NewArc;
        if (FindFile::FastFind(Arc.FileName,Arc.FileNameW,&OldArc) &&
            FindFile::FastFind(ArcName,ArcNameW,&NewArc))
          DataIO.TotalArcSize-=VolumeSetSize+OldArc.Size-NewArc.Size;
        return(EXTRACT_ARC_REPEAT);
      }
      else
        break;
  }

  return(EXTRACT_ARC_NEXT);
}


bool CmdExtract::ExtractCurrentFile(CommandData *Cmd,Archive &Arc,size_t HeaderSize,bool &Repeat)
{
  char Command=*Cmd->Command;
  if (HeaderSize==0)
    if (DataIO.UnpVolume)
    {
#ifdef NOVOLUME
      return(false);
#else
      if (!MergeArchive(Arc,&DataIO,false,Command))
      {
        ErrHandler.SetErrorCode(RARX_WARNING);
        return(false);
      }
      SignatureFound=false;
#endif
    }
    else
      return(false);
  int HeadType=Arc.GetHeaderType();
  if (HeadType!=FILE_HEAD)
  {
    if (HeadType==AV_HEAD || HeadType==SIGN_HEAD)
      SignatureFound=true;
#if !defined(SFX_MODULE) && !defined(_WIN_CE)
    if (HeadType==SUB_HEAD && PrevExtracted)
      SetExtraInfo(Cmd,Arc,DestFileName,*DestFileNameW ? DestFileNameW:NULL);
#endif
    if (HeadType==NEWSUB_HEAD)
    {
      if (Arc.SubHead.CmpName(SUBHEAD_TYPE_AV))
        SignatureFound=true;
#if !defined(NOSUBBLOCKS) && !defined(_WIN_CE)
      if (PrevExtracted)
        SetExtraInfoNew(Cmd,Arc,DestFileName,*DestFileNameW ? DestFileNameW:NULL);
#endif
    }
    if (HeadType==ENDARC_HEAD)
      if (Arc.EndArcHead.Flags & EARC_NEXT_VOLUME)
      {
#ifndef NOVOLUME
        if (!MergeArchive(Arc,&DataIO,false,Command))
        {
          ErrHandler.SetErrorCode(RARX_WARNING);
          return(false);
        }
        SignatureFound=false;
#endif
        Arc.Seek(Arc.CurBlockPos,SEEK_SET);
        return(true);
      }
      else
        return(false);
    Arc.SeekToNext();
    return(true);
  }
  PrevExtracted=false;

  if (SignatureFound ||
      !Cmd->Recurse && MatchedArgs>=Cmd->FileArgs->ItemsCount() &&
      AllMatchesExact)
    return(false);

  char ArcFileName[NM];
  IntToExt(Arc.NewLhd.FileName,Arc.NewLhd.FileName);
  strcpy(ArcFileName,Arc.NewLhd.FileName);

  wchar ArcFileNameW[NM];
  *ArcFileNameW=0;

  int MatchType=MATCH_WILDSUBPATH;

  bool EqualNames=false;
  int MatchNumber=Cmd->IsProcessFile(Arc.NewLhd,&EqualNames,MatchType);
  bool ExactMatch=MatchNumber!=0;
#if !defined(SFX_MODULE) && !defined(_WIN_CE)
  if (Cmd->ExclPath==EXCL_BASEPATH)
  {
    *Cmd->ArcPath=0;
    if (ExactMatch)
    {
      Cmd->FileArgs->Rewind();
      if (Cmd->FileArgs->GetString(Cmd->ArcPath,NULL,sizeof(Cmd->ArcPath),MatchNumber-1))
        *PointToName(Cmd->ArcPath)=0;
    }
  }
#endif
  if (ExactMatch && !EqualNames)
    AllMatchesExact=false;

#ifdef UNICODE_SUPPORTED
  bool WideName=(Arc.NewLhd.Flags & LHD_UNICODE) && UnicodeEnabled();
#else
  bool WideName=false;
#endif

#ifdef _APPLE
  if (WideName)
  {
    // Prepare UTF-8 name for OS X. Since we are sure that destination
    // is UTF-8, we can avoid calling the less reliable WideToChar function.
    WideToUtf(Arc.NewLhd.FileNameW,ArcFileName,ASIZE(ArcFileName));
    WideName=false;
  }
#endif

  wchar *DestNameW=WideName ? DestFileNameW:NULL;

#ifdef UNICODE_SUPPORTED
  if (WideName)
  {
    // Prepare the name in single byte native encoding (typically UTF-8
    // for Unix-based systems). Windows does not really need it,
    // but Unix system will use this name instead of Unicode.
    ConvertPath(Arc.NewLhd.FileNameW,ArcFileNameW);
    char Name[NM];
    if (WideToChar(ArcFileNameW,Name) && IsNameUsable(Name))
      strcpy(ArcFileName,Name);
  }
#endif

  ConvertPath(ArcFileName,ArcFileName);

  if (Arc.IsArcLabel())
    return(true);

  if (Arc.NewLhd.Flags & LHD_VERSION)
  {
    if (Cmd->VersionControl!=1 && !EqualNames)
    {
      if (Cmd->VersionControl==0)
        ExactMatch=false;
      int Version=ParseVersionFileName(ArcFileName,ArcFileNameW,false);
      if (Cmd->VersionControl-1==Version)
        ParseVersionFileName(ArcFileName,ArcFileNameW,true);
      else
        ExactMatch=false;
    }
  }
  else
    if (!Arc.IsArcDir() && Cmd->VersionControl>1)
      ExactMatch=false;

  Arc.ConvertAttributes();

#if !defined(SFX_MODULE) && !defined(RARDLL)
  if ((Arc.NewLhd.Flags & LHD_SPLIT_BEFORE)!=0 && FirstFile)
  {
    char CurVolName[NM];
    strcpy(CurVolName,ArcName);

    bool NewNumbering=(Arc.NewMhd.Flags & MHD_NEWNUMBERING)!=0;
    VolNameToFirstName(ArcName,ArcName,NewNumbering);
    if (*ArcNameW!=0)
      VolNameToFirstName(ArcNameW,ArcNameW,NewNumbering);

    if (stricomp(ArcName,CurVolName)!=0 && FileExist(ArcName,ArcNameW))
    {
      // If first volume name does not match the current name and if
      // such volume name really exists, let's unpack from this first volume.
      Repeat=true;
      return(false);
    }
#if !defined(RARDLL) && !defined(_WIN_CE)
    if (!ReconstructDone)
    {
      ReconstructDone=true;

      RecVolumes RecVol;
      if (RecVol.Restore(Cmd,Arc.FileName,Arc.FileNameW,true))
      {
        Repeat=true;
        return(false);
      }
    }
#endif
    strcpy(ArcName,CurVolName);
  }
#endif

  DataIO.UnpVolume=(Arc.NewLhd.Flags & LHD_SPLIT_AFTER)!=0;
  DataIO.NextVolumeMissing=false;

  Arc.Seek(Arc.NextBlockPos-Arc.NewLhd.FullPackSize,SEEK_SET);

  bool TestMode=false;
  bool ExtrFile=false;
  bool SkipSolid=false;

#ifndef SFX_MODULE
  if (FirstFile && (ExactMatch || Arc.Solid) && (Arc.NewLhd.Flags & (LHD_SPLIT_BEFORE/*|LHD_SOLID*/))!=0)
  {
    if (ExactMatch)
    {
      Log(Arc.FileName,St(MUnpCannotMerge),ArcFileName);
#ifdef RARDLL
      Cmd->DllError=ERAR_BAD_DATA;
#endif
      ErrHandler.SetErrorCode(RARX_OPEN);
    }
    ExactMatch=false;
  }

  FirstFile=false;
#endif

  if (ExactMatch || (SkipSolid=Arc.Solid)!=0)
  {
    if ((Arc.NewLhd.Flags & LHD_PASSWORD)!=0)
#ifndef RARDLL
      if (!Password.IsSet())
#endif
      {
#ifdef RARDLL
        if (!Cmd->Password.IsSet())
        {
          if (Cmd->Callback!=NULL)
          {
            wchar PasswordW[MAXPASSWORD];
            *PasswordW=0;
            if (Cmd->Callback(UCM_NEEDPASSWORDW,Cmd->UserData,(LPARAM)PasswordW,ASIZE(PasswordW))==-1)
              *PasswordW=0;
            if (*PasswordW==0)
            {
              char PasswordA[MAXPASSWORD];
              *PasswordA=0;
              if (Cmd->Callback(UCM_NEEDPASSWORD,Cmd->UserData,(LPARAM)PasswordA,ASIZE(PasswordA))==-1)
                *PasswordA=0;
              GetWideName(PasswordA,NULL,PasswordW,ASIZE(PasswordW));
              cleandata(PasswordA,sizeof(PasswordA));
            }
            Cmd->Password.Set(PasswordW);
            cleandata(PasswordW,sizeof(PasswordW));
          }
          if (!Cmd->Password.IsSet())
            return false;
        }
        Password=Cmd->Password;

#else
        if (!GetPassword(PASSWORD_FILE,ArcFileName,ArcFileNameW,&Password))
        {
          PasswordCancelled=true;
          return(false);
        }
#endif
      }
#if !defined(GUI) && !defined(SILENT)
      else
        if (!PasswordAll && (!Arc.Solid || Arc.NewLhd.UnpVer>=20 && (Arc.NewLhd.Flags & LHD_SOLID)==0))
        {
          eprintf(St(MUseCurPsw),ArcFileName);
          switch(Cmd->AllYes ? 1:Ask(St(MYesNoAll)))
          {
            case -1:
              ErrHandler.Exit(RARX_USERBREAK);
            case 2:
              if (!GetPassword(PASSWORD_FILE,ArcFileName,ArcFileNameW,&Password))
              {
                return(false);
              }
              break;
            case 3:
              PasswordAll=true;
              break;
          }
        }
#endif

#ifndef SFX_MODULE
    if (*Cmd->ExtrPath==0 && *Cmd->ExtrPathW!=0)
      WideToChar(Cmd->ExtrPathW,DestFileName);
    else
#endif
      strcpy(DestFileName,Cmd->ExtrPath);


#ifndef SFX_MODULE
    if (Cmd->AppendArcNameToPath)
    {
      strcat(DestFileName,PointToName(Arc.FirstVolumeName));
      SetExt(DestFileName,NULL);
      AddEndSlash(DestFileName);
    }
#endif

    char *ExtrName=ArcFileName;

    bool EmptyName=false;
#ifndef SFX_MODULE
    size_t Length=strlen(Cmd->ArcPath);
    if (Length>1 && IsPathDiv(Cmd->ArcPath[Length-1]) &&
        strlen(ArcFileName)==Length-1)
      Length--;
    if (Length>0 && strnicomp(Cmd->ArcPath,ArcFileName,Length)==0)
    {
      ExtrName+=Length;
      while (*ExtrName==CPATHDIVIDER)
        ExtrName++;
      if (*ExtrName==0)
        EmptyName=true;
    }
#endif

    // Use -ep3 only in systems, where disk letters are exist, not in Unix.
    bool AbsPaths=Cmd->ExclPath==EXCL_ABSPATH && Command=='X' && IsDriveDiv(':');

    // We do not use any user specified destination paths when extracting
    // absolute paths in -ep3 mode.
    if (AbsPaths)
      *DestFileName=0;

    if (Command=='E' || Cmd->ExclPath==EXCL_SKIPWHOLEPATH)
      strcat(DestFileName,PointToName(ExtrName));
    else
      strcat(DestFileName,ExtrName);

    char DiskLetter=etoupper(DestFileName[0]);

    if (AbsPaths)
    {
      if (DestFileName[1]=='_' && IsPathDiv(DestFileName[2]) &&
          DiskLetter>='A' && DiskLetter<='Z')
        DestFileName[1]=':';
      else
        if (DestFileName[0]=='_' && DestFileName[1]=='_')
        {
          // Convert __server\share to \\server\share.
          DestFileName[0]=CPATHDIVIDER;
          DestFileName[1]=CPATHDIVIDER;
        }
    }

#ifndef SFX_MODULE
    if (!WideName && *Cmd->ExtrPathW!=0)
    {
      DestNameW=DestFileNameW;
      WideName=true;
      CharToWide(ArcFileName,ArcFileNameW);
    }
#endif

    if (WideName)
    {
      if (*Cmd->ExtrPathW!=0)
        wcscpy(DestFileNameW,Cmd->ExtrPathW);
      else
        CharToWide(Cmd->ExtrPath,DestFileNameW);

#ifndef SFX_MODULE
      if (Cmd->AppendArcNameToPath)
      {
        wchar FileNameW[NM];
        if (*Arc.FirstVolumeNameW!=0)
          wcscpy(FileNameW,Arc.FirstVolumeNameW);
        else
          CharToWide(Arc.FirstVolumeName,FileNameW);
        wcscat(DestFileNameW,PointToName(FileNameW));
        SetExt(DestFileNameW,NULL);
        AddEndSlash(DestFileNameW);
      }
#endif
      wchar *ExtrNameW=ArcFileNameW;
#ifndef SFX_MODULE
      if (Length>0)
      {
        wchar ArcPathW[NM];
        GetWideName(Cmd->ArcPath,Cmd->ArcPathW,ArcPathW,ASIZE(ArcPathW));
        Length=wcslen(ArcPathW);
      }
      ExtrNameW+=Length;
      while (*ExtrNameW==CPATHDIVIDER)
        ExtrNameW++;
#endif

      if (AbsPaths)
        *DestFileNameW=0;

      if (Command=='E' || Cmd->ExclPath==EXCL_SKIPWHOLEPATH)
        wcscat(DestFileNameW,PointToName(ExtrNameW));
      else
        wcscat(DestFileNameW,ExtrNameW);

      if (AbsPaths && DestFileNameW[1]=='_' && IsPathDiv(DestFileNameW[2]))
        DestFileNameW[1]=':';
    }
    else
      *DestFileNameW=0;

    ExtrFile=!SkipSolid && !EmptyName && (Arc.NewLhd.Flags & LHD_SPLIT_BEFORE)==0;

    if ((Cmd->FreshFiles || Cmd->UpdateFiles) && (Command=='E' || Command=='X'))
    {
      struct FindData FD;
      if (FindFile::FastFind(DestFileName,DestNameW,&FD))
      {
        if (FD.mtime >= Arc.NewLhd.mtime)
        {
          // If directory already exists and its modification time is newer 
          // than start of extraction, it is likely it was created 
          // when creating a path to one of already extracted items. 
          // In such case we'll better update its time even if archived 
          // directory is older.

          if (!FD.IsDir || FD.mtime<StartTime)
            ExtrFile=false;
        }
      }
      else
        if (Cmd->FreshFiles)
          ExtrFile=false;
    }

    // Skip encrypted file if no password is specified.
    if ((Arc.NewLhd.Flags & LHD_PASSWORD)!=0 && !Password.IsSet())
    {
      ErrHandler.SetErrorCode(RARX_WARNING);
#ifdef RARDLL
      Cmd->DllError=ERAR_MISSING_PASSWORD;
#endif
      ExtrFile=false;
    }

#ifdef RARDLL
    if (*Cmd->DllDestName)
    {
      strncpyz(DestFileName,Cmd->DllDestName,ASIZE(DestFileName));
      *DestFileNameW=0;
      if (Cmd->DllOpMode!=RAR_EXTRACT)
        ExtrFile=false;
    }
    if (*Cmd->DllDestNameW)
    {
      wcsncpyz(DestFileNameW,Cmd->DllDestNameW,ASIZE(DestFileNameW));
      DestNameW=DestFileNameW;
      if (Cmd->DllOpMode!=RAR_EXTRACT)
        ExtrFile=false;
    }
#endif

#ifdef SFX_MODULE
    if ((Arc.NewLhd.UnpVer!=UNP_VER && Arc.NewLhd.UnpVer!=29) &&
        Arc.NewLhd.Method!=0x30)
#else
    if (Arc.NewLhd.UnpVer<13 || Arc.NewLhd.UnpVer>UNP_VER)
#endif
    {
#ifndef SILENT
      Log(Arc.FileName,St(MUnknownMeth),ArcFileName);
#ifndef SFX_MODULE
      Log(Arc.FileName,St(MVerRequired),Arc.NewLhd.UnpVer/10,Arc.NewLhd.UnpVer%10);
#endif
#endif
      ExtrFile=false;
      ErrHandler.SetErrorCode(RARX_WARNING);
#ifdef RARDLL
      Cmd->DllError=ERAR_UNKNOWN_FORMAT;
#endif
    }

    File CurFile;

    if (!IsLink(Arc.NewLhd.FileAttr))
      if (Arc.IsArcDir())
      {
        if (!ExtrFile || Command=='P' || Command=='E' || Cmd->ExclPath==EXCL_SKIPWHOLEPATH)
          return(true);
        if (SkipSolid)
        {
#ifndef GUI
          mprintf(St(MExtrSkipFile),ArcFileName);
#endif
          return(true);
        }
        TotalFileCount++;
        if (Cmd->Test)
        {
#ifndef GUI
          mprintf(St(MExtrTestFile),ArcFileName);
          mprintf(" %s",St(MOk));
#endif
          return(true);
        }
        MKDIR_CODE MDCode=MakeDir(DestFileName,DestNameW,!Cmd->IgnoreGeneralAttr,Arc.NewLhd.FileAttr);
        bool DirExist=false;
        if (MDCode!=MKDIR_SUCCESS)
        {
          DirExist=FileExist(DestFileName,DestNameW);
          if (DirExist && !IsDir(GetFileAttr(DestFileName,DestNameW)))
          {
            // File with name same as this directory exists. Propose user
            // to overwrite it.
            bool UserReject;
            FileCreate(Cmd,NULL,DestFileName,DestNameW,Cmd->Overwrite,&UserReject,Arc.NewLhd.FullUnpSize,Arc.NewLhd.FileTime);
            DirExist=false;
          }
          if (!DirExist)
          {
            CreatePath(DestFileName,DestNameW,true);
            MDCode=MakeDir(DestFileName,DestNameW,!Cmd->IgnoreGeneralAttr,Arc.NewLhd.FileAttr);
          }
        }
        if (MDCode==MKDIR_SUCCESS)
        {
#ifndef GUI
          mprintf(St(MCreatDir),DestFileName);
          mprintf(" %s",St(MOk));
#endif
          PrevExtracted=true;
        }
        else
          if (DirExist)
          {
            if (!Cmd->IgnoreGeneralAttr)
              SetFileAttr(DestFileName,DestNameW,Arc.NewLhd.FileAttr);
            PrevExtracted=true;
          }
          else
          {
            Log(Arc.FileName,St(MExtrErrMkDir),DestFileName);
            ErrHandler.CheckLongPathErrMsg(DestFileName,DestNameW);
            ErrHandler.SysErrMsg();
#ifdef RARDLL
            Cmd->DllError=ERAR_ECREATE;
#endif
            ErrHandler.SetErrorCode(RARX_CREATE);
          }
        if (PrevExtracted)
        {
#if defined(_WIN_ALL) && !defined(_WIN_CE) && !defined(SFX_MODULE)
          if (Cmd->SetCompressedAttr &&
              (Arc.NewLhd.FileAttr & FILE_ATTRIBUTE_COMPRESSED)!=0 && WinNT())
            SetFileCompression(DestFileName,DestNameW,true);
#endif
          SetDirTime(DestFileName,DestNameW,
            Cmd->xmtime==EXTTIME_NONE ? NULL:&Arc.NewLhd.mtime,
            Cmd->xctime==EXTTIME_NONE ? NULL:&Arc.NewLhd.ctime,
            Cmd->xatime==EXTTIME_NONE ? NULL:&Arc.NewLhd.atime);
        }
        return(true);
      }
      else
      {
        if (Cmd->Test && ExtrFile)
          TestMode=true;
#if !defined(GUI) && !defined(SFX_MODULE)
        if (Command=='P' && ExtrFile)
          CurFile.SetHandleType(FILE_HANDLESTD);
#endif
        if ((Command=='E' || Command=='X') && ExtrFile && !Cmd->Test)
        {
          bool UserReject;
          // Specify "write only" mode to avoid OpenIndiana NAS problems
          // with SetFileTime and read+write files.
          if (!FileCreate(Cmd,&CurFile,DestFileName,DestNameW,Cmd->Overwrite,&UserReject,Arc.NewLhd.FullUnpSize,Arc.NewLhd.FileTime,true))
          {
            ExtrFile=false;
            if (!UserReject)
            {
              ErrHandler.CreateErrorMsg(Arc.FileName,Arc.FileNameW,DestFileName,DestFileNameW);
              ErrHandler.SetErrorCode(RARX_CREATE);
#ifdef RARDLL
              Cmd->DllError=ERAR_ECREATE;
#endif
              if (!IsNameUsable(DestFileName) && (!WideName || !IsNameUsable(DestNameW)))
              {
                Log(Arc.FileName,St(MCorrectingName));
                char OrigName[ASIZE(DestFileName)];
                wchar OrigNameW[ASIZE(DestFileNameW)];
                strncpyz(OrigName,DestFileName,ASIZE(OrigName));
                wcsncpyz(OrigNameW,NullToEmpty(DestNameW),ASIZE(OrigNameW));

                MakeNameUsable(DestFileName,true);

                if (WideName)
                  MakeNameUsable(DestNameW,true);

                CreatePath(DestFileName,DestNameW,true);
                if (FileCreate(Cmd,&CurFile,DestFileName,DestNameW,Cmd->Overwrite,&UserReject,Arc.NewLhd.FullUnpSize,Arc.NewLhd.FileTime,true))
                {
#ifndef SFX_MODULE
                  Log(Arc.FileName,St(MRenaming),OrigName,DestFileName);
#endif
                  ExtrFile=true;
                }
                else
                  ErrHandler.CreateErrorMsg(Arc.FileName,Arc.FileNameW,DestFileName,DestFileNameW);
              }
            }
          }
        }
      }

    if (!ExtrFile && Arc.Solid)
    {
      SkipSolid=true;
      TestMode=true;
      ExtrFile=true;

    }
    if (ExtrFile)
    {

      if (!SkipSolid)
      {
        if (!TestMode && Command!='P' && CurFile.IsDevice())
        {
          Log(Arc.FileName,St(MInvalidName),DestFileName);
          ErrHandler.WriteError(Arc.FileName,Arc.FileNameW,DestFileName,DestFileNameW);
        }
        TotalFileCount++;
      }
      FileCount++;
#ifndef GUI
      if (Command!='I')
        if (SkipSolid)
          mprintf(St(MExtrSkipFile),ArcFileName);
        else
          switch(Cmd->Test ? 'T':Command)
          {
            case 'T':
              mprintf(St(MExtrTestFile),ArcFileName);
              break;
#ifndef SFX_MODULE
            case 'P':
              mprintf(St(MExtrPrinting),ArcFileName);
              break;
#endif
            case 'X':
            case 'E':
              mprintf(St(MExtrFile),DestFileName);
              break;
          }
      if (!Cmd->DisablePercentage)
        mprintf("     ");
#endif
      DataIO.CurUnpRead=0;
      DataIO.CurUnpWrite=0;
      DataIO.UnpFileCRC=Arc.OldFormat ? 0 : 0xffffffff;
      DataIO.PackedCRC=0xffffffff;

      SecPassword FilePassword;
#ifdef _WIN_ALL
      if (Arc.NewLhd.HostOS==HOST_MSDOS/* && Arc.NewLhd.UnpVer<=25*/)
      {
        // We need the password in OEM encoding if file was encrypted by
        // native RAR/DOS (not extender based). Let's make the conversion.
        wchar PlainPsw[MAXPASSWORD];
        Password.Get(PlainPsw,ASIZE(PlainPsw));
        char PswA[MAXPASSWORD];
        CharToOemBuffW(PlainPsw,PswA,ASIZE(PswA));
        PswA[ASIZE(PswA)-1]=0;
        CharToWide(PswA,PlainPsw,ASIZE(PlainPsw));
        PlainPsw[ASIZE(PlainPsw)-1]=0;
        FilePassword.Set(PlainPsw);
        cleandata(PlainPsw,sizeof(PlainPsw));
        cleandata(PswA,sizeof(PswA));
      }
      else
#endif
        FilePassword=Password;
      
      DataIO.SetEncryption(
        (Arc.NewLhd.Flags & LHD_PASSWORD)!=0 ? Arc.NewLhd.UnpVer:0,&FilePassword,
        (Arc.NewLhd.Flags & LHD_SALT)!=0 ? Arc.NewLhd.Salt:NULL,false,
        Arc.NewLhd.UnpVer>=36);
      DataIO.SetPackedSizeToRead(Arc.NewLhd.FullPackSize);
      DataIO.SetFiles(&Arc,&CurFile);
      DataIO.SetTestMode(TestMode);
      DataIO.SetSkipUnpCRC(SkipSolid);
#ifndef _WIN_CE
      if (!TestMode && !Arc.BrokenFileHeader &&
          (Arc.NewLhd.FullPackSize<<11)>Arc.NewLhd.FullUnpSize &&
          (Arc.NewLhd.FullUnpSize<100000000 || Arc.FileLength()>Arc.NewLhd.FullPackSize))
        CurFile.Prealloc(Arc.NewLhd.FullUnpSize);
#endif

      CurFile.SetAllowDelete(!Cmd->KeepBroken);

      bool LinkCreateMode=!Cmd->Test && !SkipSolid;
      if (ExtractLink(DataIO,Arc,DestFileName,DataIO.UnpFileCRC,LinkCreateMode))
        PrevExtracted=LinkCreateMode;
      else
        if ((Arc.NewLhd.Flags & LHD_SPLIT_BEFORE)==0)
          if (Arc.NewLhd.Method==0x30)
            UnstoreFile(DataIO,Arc.NewLhd.FullUnpSize);
          else
          {
            Unp->SetDestSize(Arc.NewLhd.FullUnpSize);
#ifndef SFX_MODULE
            if (Arc.NewLhd.UnpVer<=15)
              Unp->DoUnpack(15,FileCount>1 && Arc.Solid);
            else
#endif
              Unp->DoUnpack(Arc.NewLhd.UnpVer,(Arc.NewLhd.Flags & LHD_SOLID)!=0);
          }

//      if (Arc.IsOpened())
        Arc.SeekToNext();

      bool ValidCRC=Arc.OldFormat && GET_UINT32(DataIO.UnpFileCRC)==GET_UINT32(Arc.NewLhd.FileCRC) ||
                   !Arc.OldFormat && GET_UINT32(DataIO.UnpFileCRC)==GET_UINT32(Arc.NewLhd.FileCRC^0xffffffff);

      // We set AnySolidDataUnpackedWell to true if we found at least one
      // valid non-zero solid file in preceding solid stream. If it is true
      // and if current encrypted file is broken, we do not need to hint
      // about a wrong password and can report CRC error only.
      if ((Arc.NewLhd.Flags & LHD_SOLID)==0)
        AnySolidDataUnpackedWell=false; // Reset the flag, because non-solid file is found.
      else
        if (Arc.NewLhd.Method!=0x30 && Arc.NewLhd.FullUnpSize>0 && ValidCRC)
          AnySolidDataUnpackedWell=true;
 
      bool BrokenFile=false;
      if (!SkipSolid)
      {
        if (ValidCRC)
        {
#ifndef GUI
          if (Command!='P' && Command!='I')
            mprintf("%s%s ",Cmd->DisablePercentage ? " ":"\b\b\b\b\b ",St(MOk));
#endif
        }
        else
        {
          if ((Arc.NewLhd.Flags & LHD_PASSWORD)!=0 && !AnySolidDataUnpackedWell)
          {
            Log(Arc.FileName,St(MEncrBadCRC),ArcFileName);
          }
          else
          {
            Log(Arc.FileName,St(MCRCFailed),ArcFileName);
          }
          BrokenFile=true;
          ErrHandler.SetErrorCode(RARX_CRC);
#ifdef RARDLL
          // If we already have ERAR_EOPEN as result of missing volume,
          // we should not replace it with less precise ERAR_BAD_DATA.
          if (Cmd->DllError!=ERAR_EOPEN)
            Cmd->DllError=ERAR_BAD_DATA;
#endif
          Alarm();
        }
      }
#ifndef GUI
      else
        mprintf("\b\b\b\b\b     ");
#endif

      if (!TestMode && (Command=='X' || Command=='E') &&
          !IsLink(Arc.NewLhd.FileAttr))
      {
#if defined(_WIN_ALL) || defined(_EMX)
        if (Cmd->ClearArc)
          Arc.NewLhd.FileAttr&=~FA_ARCH;
#endif
        if (!BrokenFile || Cmd->KeepBroken)
        {
          if (BrokenFile)
            CurFile.Truncate();
          CurFile.SetOpenFileTime(
            Cmd->xmtime==EXTTIME_NONE ? NULL:&Arc.NewLhd.mtime,
            Cmd->xctime==EXTTIME_NONE ? NULL:&Arc.NewLhd.ctime,
            Cmd->xatime==EXTTIME_NONE ? NULL:&Arc.NewLhd.atime);
          CurFile.Close();
#if defined(_WIN_ALL) && !defined(_WIN_CE) && !defined(SFX_MODULE)
          if (Cmd->SetCompressedAttr &&
              (Arc.NewLhd.FileAttr & FILE_ATTRIBUTE_COMPRESSED)!=0 && WinNT())
            SetFileCompression(CurFile.FileName,CurFile.FileNameW,true);
#endif
          CurFile.SetCloseFileTime(
            Cmd->xmtime==EXTTIME_NONE ? NULL:&Arc.NewLhd.mtime,
            Cmd->xatime==EXTTIME_NONE ? NULL:&Arc.NewLhd.atime);
          if (!Cmd->IgnoreGeneralAttr)
            SetFileAttr(CurFile.FileName,CurFile.FileNameW,Arc.NewLhd.FileAttr);
          PrevExtracted=true;
        }
      }
    }
  }
  if (ExactMatch)
    MatchedArgs++;
  if (DataIO.NextVolumeMissing/* || !Arc.IsOpened()*/)
    return(false);
  if (!ExtrFile)
    if (!Arc.Solid)
      Arc.SeekToNext();
    else
      if (!SkipSolid)
        return(false);
  return(true);
}


void CmdExtract::UnstoreFile(ComprDataIO &DataIO,int64 DestUnpSize)
{
  Array<byte> Buffer(0x10000);
  while (1)
  {
    uint Code=DataIO.UnpRead(&Buffer[0],Buffer.Size());
    if (Code==0 || (int)Code==-1)
      break;
    Code=Code<DestUnpSize ? Code:(uint)DestUnpSize;
    DataIO.UnpWrite(&Buffer[0],Code);
    if (DestUnpSize>=0)
      DestUnpSize-=Code;
  }
}

