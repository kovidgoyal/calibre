#include "rar.hpp"

size_t Archive::SearchBlock(int BlockType)
{
  size_t Size,Count=0;
  while ((Size=ReadHeader())!=0 &&
         (BlockType==ENDARC_HEAD || GetHeaderType()!=ENDARC_HEAD))
  {
    if ((++Count & 127)==0)
      Wait();
    if (GetHeaderType()==BlockType)
      return(Size);
    SeekToNext();
  }
  return(0);
}


size_t Archive::SearchSubBlock(const char *Type)
{
  size_t Size;
  while ((Size=ReadHeader())!=0 && GetHeaderType()!=ENDARC_HEAD)
  {
    if (GetHeaderType()==NEWSUB_HEAD && SubHead.CmpName(Type))
      return(Size);
    SeekToNext();
  }
  return(0);
}


void Archive::UnexpEndArcMsg()
{
  int64 ArcSize=FileLength();
  if (CurBlockPos>ArcSize || NextBlockPos>ArcSize)
  {
#ifndef SHELL_EXT
    Log(FileName,St(MLogUnexpEOF));
#endif
    ErrHandler.SetErrorCode(RARX_WARNING);
  }
}


size_t Archive::ReadHeader()
{
  // Once we failed to decrypt an encrypted block, there is no reason to
  // attempt to do it further. We'll never be successful and only generate
  // endless errors.
  if (FailedHeaderDecryption)
    return 0;

  CurBlockPos=Tell();

#ifndef SFX_MODULE
  if (OldFormat)
    return(ReadOldHeader());
#endif

  RawRead Raw(this);

  bool Decrypt=Encrypted && CurBlockPos>=(int64)SFXSize+SIZEOF_MARKHEAD+SIZEOF_NEWMHD;

  if (Decrypt)
  {
#if defined(SHELL_EXT) || defined(RAR_NOCRYPT)
    return(0);
#else
    if (Read(HeadersSalt,SALT_SIZE)!=SALT_SIZE)
    {
      UnexpEndArcMsg();
      return(0);
    }
    if (!Cmd->Password.IsSet())
    {
#ifdef RARDLL
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
      {
        Close();
        Cmd->DllError=ERAR_MISSING_PASSWORD;
        ErrHandler.Exit(RARX_USERBREAK);
      }
#else
      if (!GetPassword(PASSWORD_ARCHIVE,FileName,FileNameW,&Cmd->Password))
      {
        Close();
        ErrHandler.Exit(RARX_USERBREAK);
      }
#endif
    }
    HeadersCrypt.SetCryptKeys(&Cmd->Password,HeadersSalt,false,false,NewMhd.EncryptVer>=36);
    Raw.SetCrypt(&HeadersCrypt);
#endif
  }

  Raw.Read(SIZEOF_SHORTBLOCKHEAD);
  if (Raw.Size()==0)
  {
    UnexpEndArcMsg();
    return(0);
  }

  Raw.Get(ShortBlock.HeadCRC);
  byte HeadType;
  Raw.Get(HeadType);
  ShortBlock.HeadType=(HEADER_TYPE)HeadType;
  Raw.Get(ShortBlock.Flags);
  Raw.Get(ShortBlock.HeadSize);
  if (ShortBlock.HeadSize<SIZEOF_SHORTBLOCKHEAD)
  {
#ifndef SHELL_EXT
    Log(FileName,St(MLogFileHead),"???");
#endif
    BrokenFileHeader=true;
    ErrHandler.SetErrorCode(RARX_CRC);
    return(0);
  }

  if (ShortBlock.HeadType==COMM_HEAD)
  {
    // Old style (up to RAR 2.9) comment header embedded into main
    // or file header. We must not read the entire ShortBlock.HeadSize here
    // to not break the comment processing logic later.
    Raw.Read(SIZEOF_COMMHEAD-SIZEOF_SHORTBLOCKHEAD);
  }
  else
    if (ShortBlock.HeadType==MAIN_HEAD && (ShortBlock.Flags & MHD_COMMENT)!=0)
    {
      // Old style (up to RAR 2.9) main archive comment embedded into
      // the main archive header found. While we can read the entire 
      // ShortBlock.HeadSize here and remove this part of "if", it would be
      // waste of memory, because we'll read and process this comment data
      // in other function anyway and we do not need them here now.
      Raw.Read(SIZEOF_NEWMHD-SIZEOF_SHORTBLOCKHEAD);
    }
    else
      Raw.Read(ShortBlock.HeadSize-SIZEOF_SHORTBLOCKHEAD);

  NextBlockPos=CurBlockPos+ShortBlock.HeadSize;

  switch(ShortBlock.HeadType)
  {
    case MAIN_HEAD:
      *(BaseBlock *)&NewMhd=ShortBlock;
      Raw.Get(NewMhd.HighPosAV);
      Raw.Get(NewMhd.PosAV);
      if (NewMhd.Flags & MHD_ENCRYPTVER)
        Raw.Get(NewMhd.EncryptVer);
      break;
    case ENDARC_HEAD:
      *(BaseBlock *)&EndArcHead=ShortBlock;
      if (EndArcHead.Flags & EARC_DATACRC)
        Raw.Get(EndArcHead.ArcDataCRC);
      if (EndArcHead.Flags & EARC_VOLNUMBER)
        Raw.Get(EndArcHead.VolNumber);
      break;
    case FILE_HEAD:
    case NEWSUB_HEAD:
      {
        FileHeader *hd=ShortBlock.HeadType==FILE_HEAD ? &NewLhd:&SubHead;
        *(BaseBlock *)hd=ShortBlock;
        Raw.Get(hd->PackSize);
        Raw.Get(hd->UnpSize);
        Raw.Get(hd->HostOS);
        Raw.Get(hd->FileCRC);
        Raw.Get(hd->FileTime);
        Raw.Get(hd->UnpVer);
        Raw.Get(hd->Method);
        Raw.Get(hd->NameSize);
        Raw.Get(hd->FileAttr);
        if (hd->Flags & LHD_LARGE)
        {
          Raw.Get(hd->HighPackSize);
          Raw.Get(hd->HighUnpSize);
        }
        else 
        {
          hd->HighPackSize=hd->HighUnpSize=0;
          if (hd->UnpSize==0xffffffff)
          {
            // UnpSize equal to 0xffffffff without LHD_LARGE flag indicates
            // that we do not know the unpacked file size and must unpack it
            // until we find the end of file marker in compressed data.
            hd->UnpSize=(uint)(INT64NDF);
            hd->HighUnpSize=(uint)(INT64NDF>>32);
          }
        }
        hd->FullPackSize=INT32TO64(hd->HighPackSize,hd->PackSize);
        hd->FullUnpSize=INT32TO64(hd->HighUnpSize,hd->UnpSize);

        char FileName[NM*4];
        size_t NameSize=Min(hd->NameSize,sizeof(FileName)-1);
        Raw.Get((byte *)FileName,NameSize);
        FileName[NameSize]=0;

        strncpyz(hd->FileName,FileName,ASIZE(hd->FileName));

        if (hd->HeadType==NEWSUB_HEAD)
        {
          // Let's calculate the size of optional data.
          int DataSize=hd->HeadSize-hd->NameSize-SIZEOF_NEWLHD;
          if (hd->Flags & LHD_SALT)
            DataSize-=SALT_SIZE;

          if (DataSize>0)
          {
            // Here we read optional additional fields for subheaders.
            // They are stored after the file name and before salt.
            hd->SubData.Alloc(DataSize);
            Raw.Get(&hd->SubData[0],DataSize);
            if (hd->CmpName(SUBHEAD_TYPE_RR))
            {
              byte *D=&hd->SubData[8];
              RecoverySectors=D[0]+((uint)D[1]<<8)+((uint)D[2]<<16)+((uint)D[3]<<24);
            }
          }
        }
        else
          if (hd->HeadType==FILE_HEAD)
          {
            if (hd->Flags & LHD_UNICODE)
            {
              EncodeFileName NameCoder;
              size_t Length=strlen(FileName);
              if (Length==hd->NameSize)
              {
                UtfToWide(FileName,hd->FileNameW,sizeof(hd->FileNameW)/sizeof(hd->FileNameW[0])-1);
                WideToChar(hd->FileNameW,hd->FileName,sizeof(hd->FileName)/sizeof(hd->FileName[0])-1);
                ExtToInt(hd->FileName,hd->FileName);
              }
              else
              {
                Length++;
                NameCoder.Decode(FileName,(byte *)FileName+Length,
                                 hd->NameSize-Length,hd->FileNameW,
                                 sizeof(hd->FileNameW)/sizeof(hd->FileNameW[0]));
              }
              if (*hd->FileNameW==0)
                hd->Flags &= ~LHD_UNICODE;
            }
            else
              *hd->FileNameW=0;
#ifndef SFX_MODULE
            ConvertNameCase(hd->FileName);
            ConvertNameCase(hd->FileNameW);
#endif
            ConvertUnknownHeader();
          }
        if (hd->Flags & LHD_SALT)
          Raw.Get(hd->Salt,SALT_SIZE);
        hd->mtime.SetDos(hd->FileTime);
        hd->ctime.Reset();
        hd->atime.Reset();
        hd->arctime.Reset();
        if (hd->Flags & LHD_EXTTIME)
        {
          ushort Flags;
          Raw.Get(Flags);
          RarTime *tbl[4];
          tbl[0]=&NewLhd.mtime;
          tbl[1]=&NewLhd.ctime;
          tbl[2]=&NewLhd.atime;
          tbl[3]=&NewLhd.arctime;
          for (int I=0;I<4;I++)
          {
            RarTime *CurTime=tbl[I];
            uint rmode=Flags>>(3-I)*4;
            if ((rmode & 8)==0)
              continue;
            if (I!=0)
            {
              uint DosTime;
              Raw.Get(DosTime);
              CurTime->SetDos(DosTime);
            }
            RarLocalTime rlt;
            CurTime->GetLocal(&rlt);
            if (rmode & 4)
              rlt.Second++;
            rlt.Reminder=0;
            int count=rmode&3;
            for (int J=0;J<count;J++)
            {
              byte CurByte;
              Raw.Get(CurByte);
              rlt.Reminder|=(((uint)CurByte)<<((J+3-count)*8));
            }
            CurTime->SetLocal(&rlt);
          }
        }
        NextBlockPos+=hd->FullPackSize;
        bool CRCProcessedOnly=(hd->Flags & LHD_COMMENT)!=0;
        HeaderCRC=~Raw.GetCRC(CRCProcessedOnly)&0xffff;
        if (hd->HeadCRC!=HeaderCRC)
        {
          if (hd->HeadType==NEWSUB_HEAD && strlen(hd->FileName)<ASIZE(hd->FileName)-5)
            strcat(hd->FileName,"- ???");
          BrokenFileHeader=true;
          ErrHandler.SetErrorCode(RARX_WARNING);

          // If we have a broken encrypted header, we do not need to display
          // the error message here, because it will be displayed for such
          // headers later in this function. Also such headers are unlikely
          // to have anything sensible in file name field, so it is useless
          // to display the file name.
          bool EncBroken=Decrypt && ShortBlock.HeadCRC!=(~Raw.GetCRC(false)&0xffff);
          if (!EncBroken)
          {
#ifndef SHELL_EXT
            Log(Archive::FileName,St(MLogFileHead),IntNameToExt(hd->FileName));
            Alarm();
#endif
          }
        }
      }
      break;
#ifndef SFX_MODULE
    case COMM_HEAD:
      *(BaseBlock *)&CommHead=ShortBlock;
      Raw.Get(CommHead.UnpSize);
      Raw.Get(CommHead.UnpVer);
      Raw.Get(CommHead.Method);
      Raw.Get(CommHead.CommCRC);
      break;
    case SIGN_HEAD:
      *(BaseBlock *)&SignHead=ShortBlock;
      Raw.Get(SignHead.CreationTime);
      Raw.Get(SignHead.ArcNameSize);
      Raw.Get(SignHead.UserNameSize);
      break;
    case AV_HEAD:
      *(BaseBlock *)&AVHead=ShortBlock;
      Raw.Get(AVHead.UnpVer);
      Raw.Get(AVHead.Method);
      Raw.Get(AVHead.AVVer);
      Raw.Get(AVHead.AVInfoCRC);
      break;
    case PROTECT_HEAD:
      *(BaseBlock *)&ProtectHead=ShortBlock;
      Raw.Get(ProtectHead.DataSize);
      Raw.Get(ProtectHead.Version);
      Raw.Get(ProtectHead.RecSectors);
      Raw.Get(ProtectHead.TotalBlocks);
      Raw.Get(ProtectHead.Mark,8);
      NextBlockPos+=ProtectHead.DataSize;
      RecoverySectors=ProtectHead.RecSectors;
      break;
    case SUB_HEAD:
      *(BaseBlock *)&SubBlockHead=ShortBlock;
      Raw.Get(SubBlockHead.DataSize);
      NextBlockPos+=SubBlockHead.DataSize;
      Raw.Get(SubBlockHead.SubType);
      Raw.Get(SubBlockHead.Level);
      switch(SubBlockHead.SubType)
      {
        case UO_HEAD:
          *(SubBlockHeader *)&UOHead=SubBlockHead;
          Raw.Get(UOHead.OwnerNameSize);
          Raw.Get(UOHead.GroupNameSize);
          if (UOHead.OwnerNameSize>NM-1)
            UOHead.OwnerNameSize=NM-1;
          if (UOHead.GroupNameSize>NM-1)
            UOHead.GroupNameSize=NM-1;
          Raw.Get((byte *)UOHead.OwnerName,UOHead.OwnerNameSize);
          Raw.Get((byte *)UOHead.GroupName,UOHead.GroupNameSize);
          UOHead.OwnerName[UOHead.OwnerNameSize]=0;
          UOHead.GroupName[UOHead.GroupNameSize]=0;
          break;
        case MAC_HEAD:
          *(SubBlockHeader *)&MACHead=SubBlockHead;
          Raw.Get(MACHead.fileType);
          Raw.Get(MACHead.fileCreator);
          break;
        case EA_HEAD:
        case BEEA_HEAD:
        case NTACL_HEAD:
          *(SubBlockHeader *)&EAHead=SubBlockHead;
          Raw.Get(EAHead.UnpSize);
          Raw.Get(EAHead.UnpVer);
          Raw.Get(EAHead.Method);
          Raw.Get(EAHead.EACRC);
          break;
        case STREAM_HEAD:
          *(SubBlockHeader *)&StreamHead=SubBlockHead;
          Raw.Get(StreamHead.UnpSize);
          Raw.Get(StreamHead.UnpVer);
          Raw.Get(StreamHead.Method);
          Raw.Get(StreamHead.StreamCRC);
          Raw.Get(StreamHead.StreamNameSize);
          if (StreamHead.StreamNameSize>NM-1)
            StreamHead.StreamNameSize=NM-1;
          Raw.Get((byte *)StreamHead.StreamName,StreamHead.StreamNameSize);
          StreamHead.StreamName[StreamHead.StreamNameSize]=0;
          break;
      }
      break;
#endif
    default:
      if (ShortBlock.Flags & LONG_BLOCK)
      {
        uint DataSize;
        Raw.Get(DataSize);
        NextBlockPos+=DataSize;
      }
      break;
  }
  HeaderCRC=~Raw.GetCRC(false)&0xffff;
  CurHeaderType=ShortBlock.HeadType;
  if (Decrypt)
  {
    NextBlockPos+=Raw.PaddedSize()+SALT_SIZE;

    if (ShortBlock.HeadCRC!=HeaderCRC)
    {
      bool Recovered=false;
      if (ShortBlock.HeadType==ENDARC_HEAD && (EndArcHead.Flags & EARC_REVSPACE)!=0)
      {
        // Last 7 bytes of recovered volume can contain zeroes, because
        // REV files store its own information (volume number, etc.) here.
        SaveFilePos SavePos(*this);
        int64 Length=Tell();
        Seek(Length-7,SEEK_SET);
        Recovered=true;
        for (int J=0;J<7;J++)
          if (GetByte()!=0)
            Recovered=false;
      }
      if (!Recovered)
      {
#ifndef SILENT
        Log(FileName,St(MEncrBadCRC),FileName);
#endif
//        Close();
        FailedHeaderDecryption=true;
        BrokenFileHeader=true;

        ErrHandler.SetErrorCode(RARX_CRC);
        return(0);
      }
    }
  }

  if (NextBlockPos<=CurBlockPos)
  {
#ifndef SHELL_EXT
    Log(FileName,St(MLogFileHead),"???");
#endif
    BrokenFileHeader=true;
    ErrHandler.SetErrorCode(RARX_CRC);
    return(0);
  }
  return(Raw.Size());
}


#ifndef SFX_MODULE
size_t Archive::ReadOldHeader()
{
  RawRead Raw(this);
  if (CurBlockPos<=(int64)SFXSize)
  {
    Raw.Read(SIZEOF_OLDMHD);
    Raw.Get(OldMhd.Mark,4);
    Raw.Get(OldMhd.HeadSize);
    Raw.Get(OldMhd.Flags);
    NextBlockPos=CurBlockPos+OldMhd.HeadSize;
    CurHeaderType=MAIN_HEAD;
  }
  else
  {
    OldFileHeader OldLhd;
    Raw.Read(SIZEOF_OLDLHD);
    NewLhd.HeadType=FILE_HEAD;
    Raw.Get(NewLhd.PackSize);
    Raw.Get(NewLhd.UnpSize);
    Raw.Get(OldLhd.FileCRC);
    Raw.Get(NewLhd.HeadSize);
    Raw.Get(NewLhd.FileTime);
    Raw.Get(OldLhd.FileAttr);
    Raw.Get(OldLhd.Flags);
    Raw.Get(OldLhd.UnpVer);
    Raw.Get(OldLhd.NameSize);
    Raw.Get(OldLhd.Method);

    NewLhd.Flags=OldLhd.Flags|LONG_BLOCK;
    NewLhd.UnpVer=(OldLhd.UnpVer==2) ? 13 : 10;
    NewLhd.Method=OldLhd.Method+0x30;
    NewLhd.NameSize=OldLhd.NameSize;
    NewLhd.FileAttr=OldLhd.FileAttr;
    NewLhd.FileCRC=OldLhd.FileCRC;
    NewLhd.FullPackSize=NewLhd.PackSize;
    NewLhd.FullUnpSize=NewLhd.UnpSize;

    NewLhd.mtime.SetDos(NewLhd.FileTime);
    NewLhd.ctime.Reset();
    NewLhd.atime.Reset();
    NewLhd.arctime.Reset();

    Raw.Read(OldLhd.NameSize);
    Raw.Get((byte *)NewLhd.FileName,OldLhd.NameSize);
    NewLhd.FileName[OldLhd.NameSize]=0;
    ConvertNameCase(NewLhd.FileName);
    *NewLhd.FileNameW=0;

    if (Raw.Size()!=0)
      NextBlockPos=CurBlockPos+NewLhd.HeadSize+NewLhd.PackSize;
    CurHeaderType=FILE_HEAD;
  }
  return(NextBlockPos>CurBlockPos ? Raw.Size():0);
}
#endif


void Archive::ConvertNameCase(char *Name)
{
  if (Cmd->ConvertNames==NAMES_UPPERCASE)
  {
    IntToExt(Name,Name);
    strupper(Name);
    ExtToInt(Name,Name);
  }
  if (Cmd->ConvertNames==NAMES_LOWERCASE)
  {
    IntToExt(Name,Name);
    strlower(Name);
    ExtToInt(Name,Name);
  }
}


#ifndef SFX_MODULE
void Archive::ConvertNameCase(wchar *Name)
{
  if (Cmd->ConvertNames==NAMES_UPPERCASE)
    wcsupper(Name);
  if (Cmd->ConvertNames==NAMES_LOWERCASE)
    wcslower(Name);
}
#endif


bool Archive::IsArcDir()
{
  return((NewLhd.Flags & LHD_WINDOWMASK)==LHD_DIRECTORY);
}


bool Archive::IsArcLabel()
{
  return(NewLhd.HostOS<=HOST_WIN32 && (NewLhd.FileAttr & 8));
}


void Archive::ConvertAttributes()
{
#if defined(_WIN_ALL) || defined(_EMX)
  switch(NewLhd.HostOS)
  {
    case HOST_MSDOS:
    case HOST_OS2:
    case HOST_WIN32:
      break;
    case HOST_UNIX:
    case HOST_BEOS:
      if ((NewLhd.Flags & LHD_WINDOWMASK)==LHD_DIRECTORY)
        NewLhd.FileAttr=0x10;
      else
        NewLhd.FileAttr=0x20;
      break;
    default:
      if ((NewLhd.Flags & LHD_WINDOWMASK)==LHD_DIRECTORY)
        NewLhd.FileAttr=0x10;
      else
        NewLhd.FileAttr=0x20;
      break;
  }
#endif
#ifdef _UNIX
  // umask defines which permission bits must not be set by default
  // when creating a file or directory. The typical default value
  // for the process umask is S_IWGRP | S_IWOTH (octal 022),
  // resulting in 0644 mode for new files.
  static mode_t mask = (mode_t) -1;

  if (mask == (mode_t) -1)
  {
    // umask call returns the current umask value. Argument (022) is not 
    // really important here.
    mask = umask(022);

    // Restore the original umask value, which was changed to 022 above.
    umask(mask);
  }

  switch(NewLhd.HostOS)
  {
    case HOST_MSDOS:
    case HOST_OS2:
    case HOST_WIN32:
      {
        // Mapping MSDOS, OS/2 and Windows file attributes to Unix.

        if (NewLhd.FileAttr & 0x10) // FILE_ATTRIBUTE_DIRECTORY
        {
          // For directories we use 0777 mask.
          NewLhd.FileAttr=0777 & ~mask;
        }
        else
          if (NewLhd.FileAttr & 1)  // FILE_ATTRIBUTE_READONLY
          {
            // For read only files we use 0444 mask with 'w' bits turned off.
            NewLhd.FileAttr=0444 & ~mask;
          }
          else
          {
            // umask does not set +x for regular files, so we use 0666
            // instead of 0777 as for directories.
            NewLhd.FileAttr=0666 & ~mask;
          }
      }
      break;
    case HOST_UNIX:
    case HOST_BEOS:
      break;
    default:
      if ((NewLhd.Flags & LHD_WINDOWMASK)==LHD_DIRECTORY)
        NewLhd.FileAttr=0x41ff & ~mask;
      else
        NewLhd.FileAttr=0x81b6 & ~mask;
      break;
  }
#endif
}


void Archive::ConvertUnknownHeader()
{
  if (NewLhd.UnpVer<20 && (NewLhd.FileAttr & 0x10))
    NewLhd.Flags|=LHD_DIRECTORY;
  if (NewLhd.HostOS>=HOST_MAX)
  {
    if ((NewLhd.Flags & LHD_WINDOWMASK)==LHD_DIRECTORY)
      NewLhd.FileAttr=0x10;
    else
      NewLhd.FileAttr=0x20;
  }
  for (char *s=NewLhd.FileName;*s!=0;s=charnext(s))
  {
    if (*s=='/' || *s=='\\')
      *s=CPATHDIVIDER;
#if defined(_APPLE) && !defined(UNICODE_SUPPORTED)
    if ((byte)*s<32 || (byte)*s>127)
      *s='_';
#endif

#if defined(_WIN_ALL) || defined(_EMX)
    // ':' in file names is allowed in Unix, but not in Windows.
    // Even worse, file data will be written to NTFS stream on NTFS,
    // so automatic name correction on file create error in extraction 
    // routine does not work. In Windows and DOS versions we better 
    // replace ':' now.
    if (*s==':')
      *s='_';
#endif

  }

  for (wchar *s=NewLhd.FileNameW;*s!=0;s++)
  {
    if (*s=='/' || *s=='\\')
      *s=CPATHDIVIDER;

#if defined(_WIN_ALL) || defined(_EMX)
    // ':' in file names is allowed in Unix, but not in Windows.
    // Even worse, file data will be written to NTFS stream on NTFS,
    // so automatic name correction on file create error in extraction 
    // routine does not work. In Windows and DOS versions we better 
    // replace ':' now.
    if (*s==':')
      *s='_';
#endif
  }
}


#ifndef SHELL_EXT
bool Archive::ReadSubData(Array<byte> *UnpData,File *DestFile)
{
  if (HeaderCRC!=SubHead.HeadCRC)
  {
#ifndef SHELL_EXT
    Log(FileName,St(MSubHeadCorrupt));
#endif
    ErrHandler.SetErrorCode(RARX_CRC);
    return(false);
  }
  if (SubHead.Method<0x30 || SubHead.Method>0x35 || SubHead.UnpVer>/*PACK_VER*/36)
  {
#ifndef SHELL_EXT
    Log(FileName,St(MSubHeadUnknown));
#endif
    return(false);
  }

  if (SubHead.PackSize==0 && (SubHead.Flags & LHD_SPLIT_AFTER)==0)
    return(true);

  SubDataIO.Init();
  Unpack Unpack(&SubDataIO);
  Unpack.Init();

  if (DestFile==NULL)
  {
    UnpData->Alloc(SubHead.UnpSize);
    SubDataIO.SetUnpackToMemory(&(*UnpData)[0],SubHead.UnpSize);
  }
  if (SubHead.Flags & LHD_PASSWORD)
    if (Cmd->Password.IsSet())
      SubDataIO.SetEncryption(SubHead.UnpVer,&Cmd->Password,
             (SubHead.Flags & LHD_SALT) ? SubHead.Salt:NULL,false,
             SubHead.UnpVer>=36);
    else
      return(false);
  SubDataIO.SetPackedSizeToRead(SubHead.PackSize);
  SubDataIO.EnableShowProgress(false);
  SubDataIO.SetFiles(this,DestFile);
  SubDataIO.UnpVolume=(SubHead.Flags & LHD_SPLIT_AFTER)!=0;
  SubDataIO.SetSubHeader(&SubHead,NULL);
  Unpack.SetDestSize(SubHead.UnpSize);
  if (SubHead.Method==0x30)
    CmdExtract::UnstoreFile(SubDataIO,SubHead.UnpSize);
  else
    Unpack.DoUnpack(SubHead.UnpVer,false);

  if (SubHead.FileCRC!=~SubDataIO.UnpFileCRC)
  {
#ifndef SHELL_EXT
    Log(FileName,St(MSubHeadDataCRC),SubHead.FileName);
#endif
    ErrHandler.SetErrorCode(RARX_CRC);
    if (UnpData!=NULL)
      UnpData->Reset();
    return(false);
  }
  return(true);
}
#endif
