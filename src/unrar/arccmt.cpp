bool IsAnsiComment(const char *Data,int Size);

bool Archive::GetComment(Array<byte> *CmtData,Array<wchar> *CmtDataW)
{
  if (!MainComment)
    return(false);
  SaveFilePos SavePos(*this);

#ifndef SFX_MODULE
  ushort CmtLength;
  if (OldFormat)
  {
    Seek(SFXSize+SIZEOF_OLDMHD,SEEK_SET);
    CmtLength=GetByte();
    CmtLength+=(GetByte()<<8);
  }
  else
#endif
  {
    if ((NewMhd.Flags & MHD_COMMENT)!=0)
    {
      // Old style (RAR 2.9) archive comment embedded into the main 
      // archive header.
      Seek(SFXSize+SIZEOF_MARKHEAD+SIZEOF_NEWMHD,SEEK_SET);
      ReadHeader();
    }
    else
    {
      // Current (RAR 3.0+) version of archive comment.
      Seek(SFXSize+SIZEOF_MARKHEAD+NewMhd.HeadSize,SEEK_SET);
      return(SearchSubBlock(SUBHEAD_TYPE_CMT)!=0 && ReadCommentData(CmtData,CmtDataW)!=0);
    }
#ifndef SFX_MODULE
    // Old style (RAR 2.9) comment header embedded into the main 
    // archive header.
    if (CommHead.HeadCRC!=HeaderCRC)
    {
      Log(FileName,St(MLogCommHead));
      Alarm();
      return(false);
    }
    CmtLength=CommHead.HeadSize-SIZEOF_COMMHEAD;
#endif
  }
#ifndef SFX_MODULE
  if (OldFormat && (OldMhd.Flags & MHD_PACK_COMMENT)!=0 || !OldFormat && CommHead.Method!=0x30)
  {
    if (!OldFormat && (CommHead.UnpVer < 15 || CommHead.UnpVer > UNP_VER || CommHead.Method > 0x35))
      return(false);
    ComprDataIO DataIO;
    DataIO.SetTestMode(true);
    uint UnpCmtLength;
    if (OldFormat)
    {
#ifdef RAR_NOCRYPT
      return(false);
#else
      UnpCmtLength=GetByte();
      UnpCmtLength+=(GetByte()<<8);
      CmtLength-=2;
      DataIO.SetCmt13Encryption();
#endif
    }
    else
      UnpCmtLength=CommHead.UnpSize;
    DataIO.SetFiles(this,NULL);
    DataIO.EnableShowProgress(false);
    DataIO.SetPackedSizeToRead(CmtLength);

    Unpack Unpack(&DataIO);
    Unpack.Init();
    Unpack.SetDestSize(UnpCmtLength);
    Unpack.DoUnpack(CommHead.UnpVer,false);

    if (!OldFormat && ((~DataIO.UnpFileCRC)&0xffff)!=CommHead.CommCRC)
    {
      Log(FileName,St(MLogCommBrk));
      Alarm();
      return(false);
    }
    else
    {
      byte *UnpData;
      size_t UnpDataSize;
      DataIO.GetUnpackedData(&UnpData,&UnpDataSize);
      CmtData->Alloc(UnpDataSize);
      memcpy(&((*CmtData)[0]),UnpData,UnpDataSize);
    }
  }
  else
  {
    CmtData->Alloc(CmtLength);
    
    Read(&((*CmtData)[0]),CmtLength);
    if (!OldFormat && CommHead.CommCRC!=(~CRC(0xffffffff,&((*CmtData)[0]),CmtLength)&0xffff))
    {
      Log(FileName,St(MLogCommBrk));
      Alarm();
      CmtData->Reset();
      return(false);
    }
  }
#endif
#if defined(_WIN_ALL) && !defined(_WIN_CE)
  if (CmtData->Size()>0)
  {
    size_t CmtSize=CmtData->Size();
    char *DataA=(char *)CmtData->Addr();
    OemToCharBuffA(DataA,DataA,(DWORD)CmtSize);

    if (CmtDataW!=NULL)
    {
      CmtDataW->Alloc(CmtSize+1);

      // It can cause reallocation, so we should not use 'DataA' variable
      // with previosuly saved CmtData->Addr() after Push() call.
      CmtData->Push(0); 

      CharToWide((char *)CmtData->Addr(),CmtDataW->Addr(),CmtSize+1);
      CmtData->Alloc(CmtSize);
      CmtDataW->Alloc(wcslen(CmtDataW->Addr()));
    }
  }
#endif
  return(CmtData->Size()>0);
}


size_t Archive::ReadCommentData(Array<byte> *CmtData,Array<wchar> *CmtDataW)
{
  bool Unicode=SubHead.SubFlags & SUBHEAD_FLAGS_CMT_UNICODE;
  if (!ReadSubData(CmtData,NULL))
    return(0);
  size_t CmtSize=CmtData->Size();
  if (Unicode)
  {
    CmtSize/=2;
    Array<wchar> DataW(CmtSize+1);
    RawToWide(CmtData->Addr(),DataW.Addr(),CmtSize);
    DataW[CmtSize]=0;
    size_t DestSize=CmtSize*4;
    CmtData->Alloc(DestSize+1);
    WideToChar(DataW.Addr(),(char *)CmtData->Addr(),DestSize);
    (*CmtData)[DestSize]=0;
    CmtSize=strlen((char *)CmtData->Addr());
    CmtData->Alloc(CmtSize);
    if (CmtDataW!=NULL)
    {
      *CmtDataW=DataW;
      CmtDataW->Alloc(CmtSize);
    }
  }
  else
    if (CmtDataW!=NULL)
    {
      CmtData->Push(0);
      CmtDataW->Alloc(CmtSize+1);
      CharToWide((char *)CmtData->Addr(),CmtDataW->Addr(),CmtSize+1);
      CmtData->Alloc(CmtSize);
      CmtDataW->Alloc(wcslen(CmtDataW->Addr()));
    }
  return(CmtSize);
}


void Archive::ViewComment()
{
#ifndef GUI
  if (Cmd->DisableComment)
    return;
  Array<byte> CmtBuf;
  if (GetComment(&CmtBuf,NULL))
  {
    size_t CmtSize=CmtBuf.Size();
    char *ChPtr=(char *)memchr(&CmtBuf[0],0x1A,CmtSize);
    if (ChPtr!=NULL)
      CmtSize=ChPtr-(char *)&CmtBuf[0];
    mprintf("\n");
    OutComment((char *)&CmtBuf[0],CmtSize);
  }
#endif
}


#ifndef SFX_MODULE
// Used for archives created by old RAR versions up to and including RAR 2.9.
// New RAR versions store file comments in separate headers and such comments
// are displayed in ListNewSubHeader function.
void Archive::ViewFileComment()
{
  if (!(NewLhd.Flags & LHD_COMMENT) || Cmd->DisableComment || OldFormat)
    return;
#ifndef GUI
  mprintf(St(MFileComment));
#endif
  const int MaxSize=0x8000;
  Array<char> CmtBuf(MaxSize);
  SaveFilePos SavePos(*this);
  Seek(CurBlockPos+SIZEOF_NEWLHD+NewLhd.NameSize,SEEK_SET);
  int64 SaveCurBlockPos=CurBlockPos;
  int64 SaveNextBlockPos=NextBlockPos;

  size_t Size=ReadHeader();

  CurBlockPos=SaveCurBlockPos;
  NextBlockPos=SaveNextBlockPos;

  if (Size<7 || CommHead.HeadType!=COMM_HEAD)
    return;
  if (CommHead.HeadCRC!=HeaderCRC)
  {
#ifndef GUI
    Log(FileName,St(MLogCommHead));
#endif
    return;
  }
  if (CommHead.UnpVer < 15 || CommHead.UnpVer > UNP_VER ||
      CommHead.Method > 0x30 || CommHead.UnpSize > MaxSize)
    return;
  Read(&CmtBuf[0],CommHead.UnpSize);
  if (CommHead.CommCRC!=((~CRC(0xffffffff,&CmtBuf[0],CommHead.UnpSize)&0xffff)))
  {
    Log(FileName,St(MLogBrokFCmt));
  }
  else
  {
    OutComment(&CmtBuf[0],CommHead.UnpSize);
#ifndef GUI
    mprintf("\n");
#endif
  }
}
#endif


