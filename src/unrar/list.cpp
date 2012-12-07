#include "rar.hpp"

static void ListFileHeader(FileHeader &hd,bool Verbose,bool Technical,bool &TitleShown,bool Bare);
static void ListSymLink(Archive &Arc);
static void ListFileAttr(uint A,int HostOS);
static void ListOldSubHeader(Archive &Arc);
static void ListNewSubHeader(CommandData *Cmd,Archive &Arc,bool Technical);

void ListArchive(CommandData *Cmd)
{
  int64 SumPackSize=0,SumUnpSize=0;
  uint ArcCount=0,SumFileCount=0;
  bool Technical=(Cmd->Command[1]=='T');
  bool Bare=(Cmd->Command[1]=='B');
  bool Verbose=(*Cmd->Command=='V');

  char ArcName[NM];
  wchar ArcNameW[NM];

  while (Cmd->GetArcName(ArcName,ArcNameW,sizeof(ArcName)))
  {
    Archive Arc(Cmd);
#ifdef _WIN_ALL
    Arc.RemoveSequentialFlag();
#endif
    if (!Arc.WOpen(ArcName,ArcNameW))
      continue;
    bool FileMatched=true;
    while (1)
    {
      int64 TotalPackSize=0,TotalUnpSize=0;
      uint FileCount=0;
      if (Arc.IsArchive(true))
      {
//        if (!Arc.IsOpened())
//          break;
        bool TitleShown=false;
        if (!Bare)
        {
          Arc.ViewComment();
          mprintf("\n");
          if (Arc.Solid)
            mprintf(St(MListSolid));
          if (Arc.SFXSize>0)
            mprintf(St(MListSFX));
          if (Arc.Volume)
            if (Arc.Solid)
              mprintf(St(MListVol1));
            else
              mprintf(St(MListVol2));
          else
            if (Arc.Solid)
              mprintf(St(MListArc1));
            else
              mprintf(St(MListArc2));
          mprintf(" %s\n",Arc.FileName);
          if (Technical)
          {
            if (Arc.Protected)
              mprintf(St(MListRecRec));
            if (Arc.Locked)
              mprintf(St(MListLock));
          }
        }
        while(Arc.ReadHeader()>0)
        {
          int HeaderType=Arc.GetHeaderType();
          if (HeaderType==ENDARC_HEAD)
            break;
          switch(HeaderType)
          {
            case FILE_HEAD:
              IntToExt(Arc.NewLhd.FileName,Arc.NewLhd.FileName);
              FileMatched=Cmd->IsProcessFile(Arc.NewLhd)!=0;
              if (FileMatched)
              {
                ListFileHeader(Arc.NewLhd,Verbose,Technical,TitleShown,Bare);
                if (!(Arc.NewLhd.Flags & LHD_SPLIT_BEFORE))
                {
                  TotalUnpSize+=Arc.NewLhd.FullUnpSize;
                  FileCount++;
                }
                TotalPackSize+=Arc.NewLhd.FullPackSize;
                if (Technical)
                  ListSymLink(Arc);
#ifndef SFX_MODULE
                if (Verbose)
                  Arc.ViewFileComment();
#endif
              }
              break;
#ifndef SFX_MODULE
            case SUB_HEAD:
              if (Technical && FileMatched && !Bare)
                ListOldSubHeader(Arc);
              break;
#endif
            case NEWSUB_HEAD:
              if (FileMatched && !Bare)
              {
                if (Technical)
                  ListFileHeader(Arc.SubHead,Verbose,true,TitleShown,false);
                ListNewSubHeader(Cmd,Arc,Technical);
              }
              break;
          }
          Arc.SeekToNext();
        }
        if (!Bare)
          if (TitleShown)
          {
            mprintf("\n");
            for (int I=0;I<79;I++)
              mprintf("-");
            char UnpSizeText[20];
            itoa(TotalUnpSize,UnpSizeText);
        
            char PackSizeText[20];
            itoa(TotalPackSize,PackSizeText);
        
            mprintf("\n%5lu %16s %8s %3d%%",FileCount,UnpSizeText,
                    PackSizeText,ToPercentUnlim(TotalPackSize,TotalUnpSize));
            SumFileCount+=FileCount;
            SumUnpSize+=TotalUnpSize;
            SumPackSize+=TotalPackSize;
#ifndef SFX_MODULE
            if (Arc.EndArcHead.Flags & EARC_VOLNUMBER)
            {
              mprintf("       ");
              mprintf(St(MVolumeNumber),Arc.EndArcHead.VolNumber+1);
            }
#endif
            mprintf("\n");
          }
          else
            mprintf(St(MListNoFiles));

        ArcCount++;

#ifndef NOVOLUME
        if (Cmd->VolSize!=0 && ((Arc.NewLhd.Flags & LHD_SPLIT_AFTER) ||
            Arc.GetHeaderType()==ENDARC_HEAD &&
            (Arc.EndArcHead.Flags & EARC_NEXT_VOLUME)!=0) &&
            MergeArchive(Arc,NULL,false,*Cmd->Command))
        {
          Arc.Seek(0,SEEK_SET);
        }
        else
#endif
          break;
      }
      else
      {
        if (Cmd->ArcNames->ItemsCount()<2 && !Bare)
          mprintf(St(MNotRAR),Arc.FileName);
        break;
      }
    }
  }
  if (ArcCount>1 && !Bare)
  {
    char UnpSizeText[20],PackSizeText[20];
    itoa(SumUnpSize,UnpSizeText);
    itoa(SumPackSize,PackSizeText);
    mprintf("\n%5lu %16s %8s %3d%%\n",SumFileCount,UnpSizeText,
            PackSizeText,ToPercentUnlim(SumPackSize,SumUnpSize));
  }
}


void ListFileHeader(FileHeader &hd,bool Verbose,bool Technical,bool &TitleShown,bool Bare)
{
  if (!Bare)
  {
    if (!TitleShown)
    {
      if (Verbose)
        mprintf(St(MListPathComm));
      else
        mprintf(St(MListName));
      mprintf(St(MListTitle));
      if (Technical)
        mprintf(St(MListTechTitle));
      for (int I=0;I<79;I++)
        mprintf("-");
      TitleShown=true;
    }

    if (hd.HeadType==NEWSUB_HEAD)
      mprintf(St(MSubHeadType),hd.FileName);

    mprintf("\n%c",(hd.Flags & LHD_PASSWORD) ? '*' : ' ');
  }

  char *Name=hd.FileName;

#ifdef UNICODE_SUPPORTED
  char ConvertedName[NM];
  if ((hd.Flags & LHD_UNICODE)!=0 && *hd.FileNameW!=0 && UnicodeEnabled())
  {
    if (WideToChar(hd.FileNameW,ConvertedName) && *ConvertedName!=0)
      Name=ConvertedName;
  }
#endif

  if (Bare)
  {
    mprintf("%s\n",Verbose ? Name:PointToName(Name));
    return;
  }

  if (Verbose)
    mprintf("%s\n%12s ",Name,"");
  else
    mprintf("%-12s",PointToName(Name));

  char UnpSizeText[20],PackSizeText[20];
  if (hd.FullUnpSize==INT64NDF)
    strcpy(UnpSizeText,"?");
  else
    itoa(hd.FullUnpSize,UnpSizeText);
  itoa(hd.FullPackSize,PackSizeText);

  mprintf(" %8s %8s ",UnpSizeText,PackSizeText);

  if ((hd.Flags & LHD_SPLIT_BEFORE) && (hd.Flags & LHD_SPLIT_AFTER))
    mprintf(" <->");
  else
    if (hd.Flags & LHD_SPLIT_BEFORE)
      mprintf(" <--");
    else
      if (hd.Flags & LHD_SPLIT_AFTER)
        mprintf(" -->");
      else
        mprintf("%3d%%",ToPercentUnlim(hd.FullPackSize,hd.FullUnpSize));

  char DateStr[50];
  hd.mtime.GetText(DateStr,false);
  mprintf(" %s ",DateStr);

  if (hd.HeadType==NEWSUB_HEAD)
    mprintf("  %c....B  ",(hd.SubFlags & SUBHEAD_FLAGS_INHERITED) ? 'I' : '.');
  else
    ListFileAttr(hd.FileAttr,hd.HostOS);

  mprintf(" %8.8X",hd.FileCRC);
  mprintf(" m%d",hd.Method-0x30);
  if ((hd.Flags & LHD_WINDOWMASK)<=6*32)
    mprintf("%c",((hd.Flags&LHD_WINDOWMASK)>>5)+'a');
  else
    mprintf(" ");
  mprintf(" %d.%d",hd.UnpVer/10,hd.UnpVer%10);

  static const char *RarOS[]={
    "DOS","OS/2","Windows","Unix","Mac OS","BeOS","WinCE","","",""
  };

  if (Technical)
    mprintf("\n%22s %8s %4s",
            (hd.HostOS<ASIZE(RarOS) ? RarOS[hd.HostOS]:""),
            (hd.Flags & LHD_SOLID) ? St(MYes):St(MNo),
            (hd.Flags & LHD_VERSION) ? St(MYes):St(MNo));
}


void ListSymLink(Archive &Arc)
{
  if (Arc.NewLhd.HostOS==HOST_UNIX && (Arc.NewLhd.FileAttr & 0xF000)==0xA000)
    if ((Arc.NewLhd.Flags & LHD_PASSWORD)==0)
    {
      char FileName[NM];
      int DataSize=Min(Arc.NewLhd.PackSize,sizeof(FileName)-1);
      Arc.Read(FileName,DataSize);
      FileName[DataSize]=0;
      mprintf("\n%22s %s","-->",FileName);
    }
    else
    {
      // Link data are encrypted. We would need to ask for password
      // and initialize decryption routine to display the link target.
      mprintf("\n%22s %s","-->","*<-?->");
    }
}


void ListFileAttr(uint A,int HostOS)
{
  switch(HostOS)
  {
    case HOST_MSDOS:
    case HOST_OS2:
    case HOST_WIN32:
    case HOST_MACOS:
      mprintf(" %c%c%c%c%c%c%c  ",
              (A & 0x08) ? 'V' : '.',
              (A & 0x10) ? 'D' : '.',
              (A & 0x01) ? 'R' : '.',
              (A & 0x02) ? 'H' : '.',
              (A & 0x04) ? 'S' : '.',
              (A & 0x20) ? 'A' : '.',
              (A & 0x800) ? 'C' : '.');
      break;
    case HOST_UNIX:
    case HOST_BEOS:
      switch (A & 0xF000)
      {
        case 0x4000:
          mprintf("d");
          break;
        case 0xA000:
          mprintf("l");
          break;
        default:
          mprintf("-");
          break;
      }
      mprintf("%c%c%c%c%c%c%c%c%c",
              (A & 0x0100) ? 'r' : '-',
              (A & 0x0080) ? 'w' : '-',
              (A & 0x0040) ? ((A & 0x0800) ? 's':'x'):((A & 0x0800) ? 'S':'-'),
              (A & 0x0020) ? 'r' : '-',
              (A & 0x0010) ? 'w' : '-',
              (A & 0x0008) ? ((A & 0x0400) ? 's':'x'):((A & 0x0400) ? 'S':'-'),
              (A & 0x0004) ? 'r' : '-',
              (A & 0x0002) ? 'w' : '-',
              (A & 0x0001) ? 'x' : '-');
      break;
  }
}


#ifndef SFX_MODULE
void ListOldSubHeader(Archive &Arc)
{
  switch(Arc.SubBlockHead.SubType)
  {
    case EA_HEAD:
      mprintf(St(MListEAHead));
      break;
    case UO_HEAD:
      mprintf(St(MListUOHead),Arc.UOHead.OwnerName,Arc.UOHead.GroupName);
      break;
    case MAC_HEAD:
      mprintf(St(MListMACHead1),Arc.MACHead.fileType>>24,Arc.MACHead.fileType>>16,Arc.MACHead.fileType>>8,Arc.MACHead.fileType);
      mprintf(St(MListMACHead2),Arc.MACHead.fileCreator>>24,Arc.MACHead.fileCreator>>16,Arc.MACHead.fileCreator>>8,Arc.MACHead.fileCreator);
      break;
    case BEEA_HEAD:
      mprintf(St(MListBeEAHead));
      break;
    case NTACL_HEAD:
      mprintf(St(MListNTACLHead));
      break;
    case STREAM_HEAD:
      mprintf(St(MListStrmHead),Arc.StreamHead.StreamName);
      break;
    default:
      mprintf(St(MListUnkHead),Arc.SubBlockHead.SubType);
      break;
  }
}
#endif


void ListNewSubHeader(CommandData *Cmd,Archive &Arc,bool Technical)
{
  if (Arc.SubHead.CmpName(SUBHEAD_TYPE_CMT) &&
      (Arc.SubHead.Flags & LHD_SPLIT_BEFORE)==0 && !Cmd->DisableComment)
  {
    Array<byte> CmtData;
    size_t ReadSize=Arc.ReadCommentData(&CmtData,NULL);
    if (ReadSize!=0)
    {
      mprintf(St(MFileComment));
      OutComment((char *)&CmtData[0],ReadSize);
    }
  }
  if (Arc.SubHead.CmpName(SUBHEAD_TYPE_STREAM) &&
      (Arc.SubHead.Flags & LHD_SPLIT_BEFORE)==0)
  {
    size_t DestSize=Arc.SubHead.SubData.Size()/2;
    wchar DestNameW[NM];
    char DestName[NM];
    if (DestSize<sizeof(DestName))
    {
      RawToWide(&Arc.SubHead.SubData[0],DestNameW,DestSize);
      DestNameW[DestSize]=0;
      WideToChar(DestNameW,DestName);
      mprintf("\n %s",DestName);
    }
  }
}
