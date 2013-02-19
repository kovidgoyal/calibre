#include "rar.hpp"

#include "coder.cpp"
#include "suballoc.cpp"
#include "model.cpp"
#ifndef SFX_MODULE
#include "unpack15.cpp"
#include "unpack20.cpp"
#endif

Unpack::Unpack(ComprDataIO *DataIO)
{
  UnpIO=DataIO;
  Window=NULL;
  Suspended=false;
  UnpAllBuf=false;
  UnpSomeRead=false;
}


Unpack::~Unpack()
{
  delete[] Window;
  InitFilters();
}


void Unpack::Init()
{
  Window=new byte[MAXWINSIZE];

#ifndef ALLOW_EXCEPTIONS
  if (Window==NULL)
    ErrHandler.MemoryError();
#endif

  // Clean the window to generate the same output when unpacking corrupt
  // RAR files, which may access to unused areas of sliding dictionary.
  memset(Window,0,MAXWINSIZE);

  UnpInitData(false);

#ifndef SFX_MODULE
  // RAR 1.5 decompression initialization
  OldUnpInitData(false);
  InitHuff();
#endif
}


void Unpack::DoUnpack(int Method,bool Solid)
{
  switch(Method)
  {
#ifndef SFX_MODULE
    case 15: // rar 1.5 compression
      Unpack15(Solid);
      break;
    case 20: // rar 2.x compression
    case 26: // files larger than 2GB
      Unpack20(Solid);
      break;
#endif
    case 29: // rar 3.x compression
    case 36: // alternative hash
      Unpack29(Solid);
      break;
  }
}


inline void Unpack::InsertOldDist(unsigned int Distance)
{
  OldDist[3]=OldDist[2];
  OldDist[2]=OldDist[1];
  OldDist[1]=OldDist[0];
  OldDist[0]=Distance;
}


_forceinline void Unpack::CopyString(uint Length,uint Distance)
{
  uint SrcPtr=UnpPtr-Distance;
  if (SrcPtr<MAXWINSIZE-MAX_LZ_MATCH && UnpPtr<MAXWINSIZE-MAX_LZ_MATCH)
  {
    // If we are not close to end of window, we do not need to waste time
    // to "& MAXWINMASK" pointer protection.

    byte *Src=Window+SrcPtr;
    byte *Dest=Window+UnpPtr;
    UnpPtr+=Length;

    while (Length>=8)
    {
      // Unroll the loop for 8 byte and longer strings.
      Dest[0]=Src[0];
      Dest[1]=Src[1];
      Dest[2]=Src[2];
      Dest[3]=Src[3];
      Dest[4]=Src[4];
      Dest[5]=Src[5];
      Dest[6]=Src[6];
      Dest[7]=Src[7];
      Src+=8;
      Dest+=8;
      Length-=8;
    }

    // Unroll the loop for 0 - 7 bytes left. Note that we use nested "if"s.
    if (Length>0) { Dest[0]=Src[0];
    if (Length>1) { Dest[1]=Src[1];
    if (Length>2) { Dest[2]=Src[2];
    if (Length>3) { Dest[3]=Src[3];
    if (Length>4) { Dest[4]=Src[4];
    if (Length>5) { Dest[5]=Src[5];
    if (Length>6) { Dest[6]=Src[6]; } } } } } } } // Close all nested "if"s.
  }
  else
    while (Length--) // Slow copying with all possible precautions.
    {
      Window[UnpPtr]=Window[SrcPtr++ & MAXWINMASK];
      UnpPtr=(UnpPtr+1) & MAXWINMASK;
    }
}


_forceinline uint Unpack::DecodeNumber(DecodeTable *Dec)
{
  // Left aligned 15 bit length raw bit field.
  uint BitField=getbits() & 0xfffe;

  if (BitField<Dec->DecodeLen[Dec->QuickBits])
  {
    uint Code=BitField>>(16-Dec->QuickBits);
    addbits(Dec->QuickLen[Code]);
    return Dec->QuickNum[Code];
  }

  // Detect the real bit length for current code.
  uint Bits=15;
  for (uint I=Dec->QuickBits+1;I<15;I++)
    if (BitField<Dec->DecodeLen[I])
    {
      Bits=I;
      break;
    }

  addbits(Bits);
  
  // Calculate the distance from the start code for current bit length.
  uint Dist=BitField-Dec->DecodeLen[Bits-1];

  // Start codes are left aligned, but we need the normal right aligned
  // number. So we shift the distance to the right.
  Dist>>=(16-Bits);

  // Now we can calculate the position in the code list. It is the sum
  // of first position for current bit length and right aligned distance
  // between our bit field and start code for current bit length.
  uint Pos=Dec->DecodePos[Bits]+Dist;

  // Out of bounds safety check required for damaged archives.
  if (Pos>=Dec->MaxNum)
    Pos=0;

  // Convert the position in the code list to position in alphabet
  // and return it.
  return(Dec->DecodeNum[Pos]);
}


// We use it instead of direct PPM.DecodeChar call to be sure that
// we reset PPM structures in case of corrupt data. It is important,
// because these structures can be invalid after PPM.DecodeChar returned -1.
inline int Unpack::SafePPMDecodeChar()
{
  int Ch=PPM.DecodeChar();
  if (Ch==-1)              // Corrupt PPM data found.
  {
    PPM.CleanUp();         // Reset possibly corrupt PPM data structures.
    UnpBlockType=BLOCK_LZ; // Set faster and more fail proof LZ mode.
  }
  return(Ch);
}


void Unpack::Unpack29(bool Solid)
{
  static unsigned char LDecode[]={0,1,2,3,4,5,6,7,8,10,12,14,16,20,24,28,32,40,48,56,64,80,96,112,128,160,192,224};
  static unsigned char LBits[]=  {0,0,0,0,0,0,0,0,1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4,  4,  5,  5,  5,  5};
  static int DDecode[DC];
  static byte DBits[DC];
  static int DBitLengthCounts[]= {4,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,14,0,12};
  static unsigned char SDDecode[]={0,4,8,16,32,64,128,192};
  static unsigned char SDBits[]=  {2,2,3, 4, 5, 6,  6,  6};
  unsigned int Bits;

  if (DDecode[1]==0)
  {
    int Dist=0,BitLength=0,Slot=0;
    for (int I=0;I<ASIZE(DBitLengthCounts);I++,BitLength++)
      for (int J=0;J<DBitLengthCounts[I];J++,Slot++,Dist+=(1<<BitLength))
      {
        DDecode[Slot]=Dist;
        DBits[Slot]=BitLength;
      }
  }

  FileExtracted=true;

  if (!Suspended)
  {
    UnpInitData(Solid);
    if (!UnpReadBuf())
      return;
    if ((!Solid || !TablesRead) && !ReadTables())
      return;
  }

  while (true)
  {
    UnpPtr&=MAXWINMASK;

    if (InAddr>ReadBorder)
    {
      if (!UnpReadBuf())
        break;
    }
    if (((WrPtr-UnpPtr) & MAXWINMASK)<260 && WrPtr!=UnpPtr)
    {
      UnpWriteBuf();
      if (WrittenFileSize>DestUnpSize)
        return;
      if (Suspended)
      {
        FileExtracted=false;
        return;
      }
    }
    if (UnpBlockType==BLOCK_PPM)
    {
      // Here speed is critical, so we do not use SafePPMDecodeChar,
      // because sometimes even the inline function can introduce
      // some additional penalty.
      int Ch=PPM.DecodeChar();
      if (Ch==-1)              // Corrupt PPM data found.
      {
        PPM.CleanUp();         // Reset possibly corrupt PPM data structures.
        UnpBlockType=BLOCK_LZ; // Set faster and more fail proof LZ mode.
        break;
      }
      if (Ch==PPMEscChar)
      {
        int NextCh=SafePPMDecodeChar();
        if (NextCh==0)  // End of PPM encoding.
        {
          if (!ReadTables())
            break;
          continue;
        }
        if (NextCh==-1) // Corrupt PPM data found.
          break;
        if (NextCh==2)  // End of file in PPM mode.
          break;
        if (NextCh==3)  // Read VM code.
        {
          if (!ReadVMCodePPM())
            break;
          continue;
        }
        if (NextCh==4) // LZ inside of PPM.
        {
          unsigned int Distance=0,Length;
          bool Failed=false;
          for (int I=0;I<4 && !Failed;I++)
          {
            int Ch=SafePPMDecodeChar();
            if (Ch==-1)
              Failed=true;
            else
              if (I==3)
                Length=(byte)Ch;
              else
                Distance=(Distance<<8)+(byte)Ch;
          }
          if (Failed)
            break;

          CopyString(Length+32,Distance+2);
          continue;
        }
        if (NextCh==5) // One byte distance match (RLE) inside of PPM.
        {
          int Length=SafePPMDecodeChar();
          if (Length==-1)
            break;
          CopyString(Length+4,1);
          continue;
        }
        // If we are here, NextCh must be 1, what means that current byte
        // is equal to our 'escape' byte, so we just store it to Window.
      }
      Window[UnpPtr++]=Ch;
      continue;
    }

    int Number=DecodeNumber(&LD);
    if (Number<256)
    {
      Window[UnpPtr++]=(byte)Number;
      continue;
    }
    if (Number>=271)
    {
      int Length=LDecode[Number-=271]+3;
      if ((Bits=LBits[Number])>0)
      {
        Length+=getbits()>>(16-Bits);
        addbits(Bits);
      }

      int DistNumber=DecodeNumber(&DD);
      unsigned int Distance=DDecode[DistNumber]+1;
      if ((Bits=DBits[DistNumber])>0)
      {
        if (DistNumber>9)
        {
          if (Bits>4)
          {
            Distance+=((getbits()>>(20-Bits))<<4);
            addbits(Bits-4);
          }
          if (LowDistRepCount>0)
          {
            LowDistRepCount--;
            Distance+=PrevLowDist;
          }
          else
          {
            int LowDist=DecodeNumber(&LDD);
            if (LowDist==16)
            {
              LowDistRepCount=LOW_DIST_REP_COUNT-1;
              Distance+=PrevLowDist;
            }
            else
            {
              Distance+=LowDist;
              PrevLowDist=LowDist;
            }
          }
        }
        else
        {
          Distance+=getbits()>>(16-Bits);
          addbits(Bits);
        }
      }

      if (Distance>=0x2000)
      {
        Length++;
        if (Distance>=0x40000L)
          Length++;
      }

      InsertOldDist(Distance);
      LastLength=Length;
      CopyString(Length,Distance);
      continue;
    }
    if (Number==256)
    {
      if (!ReadEndOfBlock())
        break;
      continue;
    }
    if (Number==257)
    {
      if (!ReadVMCode())
        break;
      continue;
    }
    if (Number==258)
    {
      if (LastLength!=0)
        CopyString(LastLength,OldDist[0]);
      continue;
    }
    if (Number<263)
    {
      int DistNum=Number-259;
      unsigned int Distance=OldDist[DistNum];
      for (int I=DistNum;I>0;I--)
        OldDist[I]=OldDist[I-1];
      OldDist[0]=Distance;

      int LengthNumber=DecodeNumber(&RD);
      int Length=LDecode[LengthNumber]+2;
      if ((Bits=LBits[LengthNumber])>0)
      {
        Length+=getbits()>>(16-Bits);
        addbits(Bits);
      }
      LastLength=Length;
      CopyString(Length,Distance);
      continue;
    }
    if (Number<272)
    {
      unsigned int Distance=SDDecode[Number-=263]+1;
      if ((Bits=SDBits[Number])>0)
      {
        Distance+=getbits()>>(16-Bits);
        addbits(Bits);
      }
      InsertOldDist(Distance);
      LastLength=2;
      CopyString(2,Distance);
      continue;
    }
  }
  UnpWriteBuf();
}


// Return 'false' to quit unpacking the current file or 'true' to continue.
bool Unpack::ReadEndOfBlock()
{
  unsigned int BitField=getbits();
  bool NewTable,NewFile=false;

  // "1"  - no new file, new table just here.
  // "00" - new file,    no new table.
  // "01" - new file,    new table (in beginning of next file).
  
  if ((BitField & 0x8000)!=0)
  {
    NewTable=true;
    addbits(1);
  }
  else
  {
    NewFile=true;
    NewTable=(BitField & 0x4000)!=0;
    addbits(2);
  }
  TablesRead=!NewTable;

  // Quit immediately if "new file" flag is set. If "new table" flag
  // is present, we'll read the table in beginning of next file
  // based on 'TablesRead' 'false' value.
  if (NewFile)
    return false;
  return ReadTables(); // Quit only if we failed to read tables.
}


bool Unpack::ReadVMCode()
{
  // Entire VM code is guaranteed to fully present in block defined 
  // by current Huffman table. Compressor checks that VM code does not cross
  // Huffman block boundaries.
  unsigned int FirstByte=getbits()>>8;
  addbits(8);
  int Length=(FirstByte & 7)+1;
  if (Length==7)
  {
    Length=(getbits()>>8)+7;
    addbits(8);
  }
  else
    if (Length==8)
    {
      Length=getbits();
      addbits(16);
    }
  Array<byte> VMCode(Length);
  for (int I=0;I<Length;I++)
  {
    // Try to read the new buffer if only one byte is left.
    // But if we read all bytes except the last, one byte is enough.
    if (InAddr>=ReadTop-1 && !UnpReadBuf() && I<Length-1)
      return(false);
    VMCode[I]=getbits()>>8;
    addbits(8);
  }
  return(AddVMCode(FirstByte,&VMCode[0],Length));
}


bool Unpack::ReadVMCodePPM()
{
  unsigned int FirstByte=SafePPMDecodeChar();
  if ((int)FirstByte==-1)
    return(false);
  int Length=(FirstByte & 7)+1;
  if (Length==7)
  {
    int B1=SafePPMDecodeChar();
    if (B1==-1)
      return(false);
    Length=B1+7;
  }
  else
    if (Length==8)
    {
      int B1=SafePPMDecodeChar();
      if (B1==-1)
        return(false);
      int B2=SafePPMDecodeChar();
      if (B2==-1)
        return(false);
      Length=B1*256+B2;
    }
  Array<byte> VMCode(Length);
  for (int I=0;I<Length;I++)
  {
    int Ch=SafePPMDecodeChar();
    if (Ch==-1)
      return(false);
    VMCode[I]=Ch;
  }
  return(AddVMCode(FirstByte,&VMCode[0],Length));
}


bool Unpack::AddVMCode(unsigned int FirstByte,byte *Code,int CodeSize)
{
  VMCodeInp.InitBitInput();
  memcpy(VMCodeInp.InBuf,Code,Min(BitInput::MAX_SIZE,CodeSize));
  VM.Init();

  uint FiltPos;
  if (FirstByte & 0x80)
  {
    FiltPos=RarVM::ReadData(VMCodeInp);
    if (FiltPos==0)
      InitFilters();
    else
      FiltPos--;
  }
  else
    FiltPos=LastFilter; // Use the same filter as last time.

  if (FiltPos>Filters.Size() || FiltPos>OldFilterLengths.Size())
    return(false);
  LastFilter=FiltPos;
  bool NewFilter=(FiltPos==Filters.Size());

  UnpackFilter *StackFilter=new UnpackFilter; // New filter for PrgStack.

  UnpackFilter *Filter;
  if (NewFilter) // New filter code, never used before since VM reset.
  {
    // Too many different filters, corrupt archive.
    if (FiltPos>MAX_FILTERS)
    {
      delete StackFilter;
      return false;
    }

    Filters.Add(1);
    Filters[Filters.Size()-1]=Filter=new UnpackFilter;
    StackFilter->ParentFilter=(uint)(Filters.Size()-1);

    // Reserve one item, where we store the data block length of our new
    // filter entry. We'll set it to real block length below, after reading
    // it. But we need to initialize it now, because when processing corrupt
    // data, we can access this item even before we set it to real value.
    OldFilterLengths.Push(0);
    Filter->ExecCount=0;
  }
  else  // Filter was used in the past.
  {
    Filter=Filters[FiltPos];
    StackFilter->ParentFilter=FiltPos;
    Filter->ExecCount++;
  }

  int EmptyCount=0;
  for (uint I=0;I<PrgStack.Size();I++)
  {
    PrgStack[I-EmptyCount]=PrgStack[I];
    if (PrgStack[I]==NULL)
      EmptyCount++;
    if (EmptyCount>0)
      PrgStack[I]=NULL;
  }
  if (EmptyCount==0)
  {
    PrgStack.Add(1);
    EmptyCount=1;
  }
  int StackPos=(int)(PrgStack.Size()-EmptyCount);
  PrgStack[StackPos]=StackFilter;
  StackFilter->ExecCount=Filter->ExecCount;
 
  uint BlockStart=RarVM::ReadData(VMCodeInp);
  if (FirstByte & 0x40)
    BlockStart+=258;
  StackFilter->BlockStart=(BlockStart+UnpPtr)&MAXWINMASK;
  if (FirstByte & 0x20)
  {
    StackFilter->BlockLength=RarVM::ReadData(VMCodeInp);

    // Store the last data block length for current filter.
    OldFilterLengths[FiltPos]=StackFilter->BlockLength;
  }
  else
  {
    // Set the data block size to same value as the previous block size
    // for same filter. It is possible on corrupt data to access here a new 
    // and not filled yet item of OldFilterLengths array. This is why above
    // we set new OldFilterLengths items to zero.
    StackFilter->BlockLength=FiltPos<OldFilterLengths.Size() ? OldFilterLengths[FiltPos]:0;
  }

  StackFilter->NextWindow=WrPtr!=UnpPtr && ((WrPtr-UnpPtr)&MAXWINMASK)<=BlockStart;

//  DebugLog("\nNextWindow: UnpPtr=%08x WrPtr=%08x BlockStart=%08x",UnpPtr,WrPtr,BlockStart);

  memset(StackFilter->Prg.InitR,0,sizeof(StackFilter->Prg.InitR));
  StackFilter->Prg.InitR[3]=VM_GLOBALMEMADDR;
  StackFilter->Prg.InitR[4]=StackFilter->BlockLength;
  StackFilter->Prg.InitR[5]=StackFilter->ExecCount;

  if (FirstByte & 0x10)   // set registers to optional parameters if any
  {
    unsigned int InitMask=VMCodeInp.fgetbits()>>9;
    VMCodeInp.faddbits(7);
    for (int I=0;I<7;I++)
      if (InitMask & (1<<I))
        StackFilter->Prg.InitR[I]=RarVM::ReadData(VMCodeInp);
  }

  if (NewFilter)
  {
    uint VMCodeSize=RarVM::ReadData(VMCodeInp);
    if (VMCodeSize>=0x10000 || VMCodeSize==0)
      return(false);
    Array<byte> VMCode(VMCodeSize);
    for (uint I=0;I<VMCodeSize;I++)
    {
      if (VMCodeInp.Overflow(3))
        return(false);
      VMCode[I]=VMCodeInp.fgetbits()>>8;
      VMCodeInp.faddbits(8);
    }
    VM.Prepare(&VMCode[0],VMCodeSize,&Filter->Prg);
  }
  StackFilter->Prg.AltCmd=&Filter->Prg.Cmd[0];
  StackFilter->Prg.CmdCount=Filter->Prg.CmdCount;

  size_t StaticDataSize=Filter->Prg.StaticData.Size();
  if (StaticDataSize>0 && StaticDataSize<VM_GLOBALMEMSIZE)
  {
    // read statically defined data contained in DB commands
    StackFilter->Prg.StaticData.Add(StaticDataSize);
    memcpy(&StackFilter->Prg.StaticData[0],&Filter->Prg.StaticData[0],StaticDataSize);
  }

  if (StackFilter->Prg.GlobalData.Size()<VM_FIXEDGLOBALSIZE)
  {
    StackFilter->Prg.GlobalData.Reset();
    StackFilter->Prg.GlobalData.Add(VM_FIXEDGLOBALSIZE);
  }
  byte *GlobalData=&StackFilter->Prg.GlobalData[0];
  for (int I=0;I<7;I++)
    VM.SetLowEndianValue((uint *)&GlobalData[I*4],StackFilter->Prg.InitR[I]);
  VM.SetLowEndianValue((uint *)&GlobalData[0x1c],StackFilter->BlockLength);
  VM.SetLowEndianValue((uint *)&GlobalData[0x20],0);
  VM.SetLowEndianValue((uint *)&GlobalData[0x2c],StackFilter->ExecCount);
  memset(&GlobalData[0x30],0,16);

  if (FirstByte & 8) // Put the data block passed as parameter if any.
  {
    if (VMCodeInp.Overflow(3))
      return(false);
    uint DataSize=RarVM::ReadData(VMCodeInp);
    if (DataSize>VM_GLOBALMEMSIZE-VM_FIXEDGLOBALSIZE)
      return(false);
    size_t CurSize=StackFilter->Prg.GlobalData.Size();
    if (CurSize<DataSize+VM_FIXEDGLOBALSIZE)
      StackFilter->Prg.GlobalData.Add(DataSize+VM_FIXEDGLOBALSIZE-CurSize);
    byte *GlobalData=&StackFilter->Prg.GlobalData[VM_FIXEDGLOBALSIZE];
    for (uint I=0;I<DataSize;I++)
    {
      if (VMCodeInp.Overflow(3))
        return(false);
      GlobalData[I]=VMCodeInp.fgetbits()>>8;
      VMCodeInp.faddbits(8);
    }
  }
  return(true);
}


bool Unpack::UnpReadBuf()
{
  int DataSize=ReadTop-InAddr; // Data left to process.
  if (DataSize<0)
    return(false);
  if (InAddr>BitInput::MAX_SIZE/2)
  {
    // If we already processed more than half of buffer, let's move
    // remaining data into beginning to free more space for new data.
    if (DataSize>0)
      memmove(InBuf,InBuf+InAddr,DataSize);
    InAddr=0;
    ReadTop=DataSize;
  }
  else
    DataSize=ReadTop;
  int ReadCode=UnpIO->UnpRead(InBuf+DataSize,(BitInput::MAX_SIZE-DataSize)&~0xf);
  if (ReadCode>0)
    ReadTop+=ReadCode;
  ReadBorder=ReadTop-30;
  return(ReadCode!=-1);
}


void Unpack::UnpWriteBuf()
{
  unsigned int WrittenBorder=WrPtr;
  unsigned int WriteSize=(UnpPtr-WrittenBorder)&MAXWINMASK;
  for (size_t I=0;I<PrgStack.Size();I++)
  {
    // Here we apply filters to data which we need to write.
    // We always copy data to virtual machine memory before processing.
    // We cannot process them just in place in Window buffer, because
    // these data can be used for future string matches, so we must
    // preserve them in original form.

    UnpackFilter *flt=PrgStack[I];
    if (flt==NULL)
      continue;
    if (flt->NextWindow)
    {
      flt->NextWindow=false;
      continue;
    }
    unsigned int BlockStart=flt->BlockStart;
    unsigned int BlockLength=flt->BlockLength;
    if (((BlockStart-WrittenBorder)&MAXWINMASK)<WriteSize)
    {
      if (WrittenBorder!=BlockStart)
      {
        UnpWriteArea(WrittenBorder,BlockStart);
        WrittenBorder=BlockStart;
        WriteSize=(UnpPtr-WrittenBorder)&MAXWINMASK;
      }
      if (BlockLength<=WriteSize)
      {
        unsigned int BlockEnd=(BlockStart+BlockLength)&MAXWINMASK;
        if (BlockStart<BlockEnd || BlockEnd==0)
          VM.SetMemory(0,Window+BlockStart,BlockLength);
        else
        {
          unsigned int FirstPartLength=MAXWINSIZE-BlockStart;
          VM.SetMemory(0,Window+BlockStart,FirstPartLength);
          VM.SetMemory(FirstPartLength,Window,BlockEnd);
        }

        VM_PreparedProgram *ParentPrg=&Filters[flt->ParentFilter]->Prg;
        VM_PreparedProgram *Prg=&flt->Prg;

        if (ParentPrg->GlobalData.Size()>VM_FIXEDGLOBALSIZE)
        {
          // Copy global data from previous script execution if any.
          Prg->GlobalData.Alloc(ParentPrg->GlobalData.Size());
          memcpy(&Prg->GlobalData[VM_FIXEDGLOBALSIZE],&ParentPrg->GlobalData[VM_FIXEDGLOBALSIZE],ParentPrg->GlobalData.Size()-VM_FIXEDGLOBALSIZE);
        }

        ExecuteCode(Prg);

        if (Prg->GlobalData.Size()>VM_FIXEDGLOBALSIZE)
        {
          // Save global data for next script execution.
          if (ParentPrg->GlobalData.Size()<Prg->GlobalData.Size())
            ParentPrg->GlobalData.Alloc(Prg->GlobalData.Size());
          memcpy(&ParentPrg->GlobalData[VM_FIXEDGLOBALSIZE],&Prg->GlobalData[VM_FIXEDGLOBALSIZE],Prg->GlobalData.Size()-VM_FIXEDGLOBALSIZE);
        }
        else
          ParentPrg->GlobalData.Reset();

        byte *FilteredData=Prg->FilteredData;
        unsigned int FilteredDataSize=Prg->FilteredDataSize;

        delete PrgStack[I];
        PrgStack[I]=NULL;
        while (I+1<PrgStack.Size())
        {
          UnpackFilter *NextFilter=PrgStack[I+1];
          if (NextFilter==NULL || NextFilter->BlockStart!=BlockStart ||
              NextFilter->BlockLength!=FilteredDataSize || NextFilter->NextWindow)
            break;

          // Apply several filters to same data block.

          VM.SetMemory(0,FilteredData,FilteredDataSize);

          VM_PreparedProgram *ParentPrg=&Filters[NextFilter->ParentFilter]->Prg;
          VM_PreparedProgram *NextPrg=&NextFilter->Prg;

          if (ParentPrg->GlobalData.Size()>VM_FIXEDGLOBALSIZE)
          {
            // Copy global data from previous script execution if any.
            NextPrg->GlobalData.Alloc(ParentPrg->GlobalData.Size());
            memcpy(&NextPrg->GlobalData[VM_FIXEDGLOBALSIZE],&ParentPrg->GlobalData[VM_FIXEDGLOBALSIZE],ParentPrg->GlobalData.Size()-VM_FIXEDGLOBALSIZE);
          }

          ExecuteCode(NextPrg);

          if (NextPrg->GlobalData.Size()>VM_FIXEDGLOBALSIZE)
          {
            // Save global data for next script execution.
            if (ParentPrg->GlobalData.Size()<NextPrg->GlobalData.Size())
              ParentPrg->GlobalData.Alloc(NextPrg->GlobalData.Size());
            memcpy(&ParentPrg->GlobalData[VM_FIXEDGLOBALSIZE],&NextPrg->GlobalData[VM_FIXEDGLOBALSIZE],NextPrg->GlobalData.Size()-VM_FIXEDGLOBALSIZE);
          }
          else
            ParentPrg->GlobalData.Reset();

          FilteredData=NextPrg->FilteredData;
          FilteredDataSize=NextPrg->FilteredDataSize;
          I++;
          delete PrgStack[I];
          PrgStack[I]=NULL;
        }
        UnpIO->UnpWrite(FilteredData,FilteredDataSize);
        UnpSomeRead=true;
        WrittenFileSize+=FilteredDataSize;
        WrittenBorder=BlockEnd;
        WriteSize=(UnpPtr-WrittenBorder)&MAXWINMASK;
      }
      else
      {
        // Current filter intersects the window write border, so we adjust
        // the window border to process this filter next time, not now.
        for (size_t J=I;J<PrgStack.Size();J++)
        {
          UnpackFilter *flt=PrgStack[J];
          if (flt!=NULL && flt->NextWindow)
            flt->NextWindow=false;
        }
        WrPtr=WrittenBorder;
        return;
      }
    }
  }
      
  UnpWriteArea(WrittenBorder,UnpPtr);
  WrPtr=UnpPtr;
}


void Unpack::ExecuteCode(VM_PreparedProgram *Prg)
{
  if (Prg->GlobalData.Size()>0)
  {
    Prg->InitR[6]=(uint)WrittenFileSize;
    VM.SetLowEndianValue((uint *)&Prg->GlobalData[0x24],(uint)WrittenFileSize);
    VM.SetLowEndianValue((uint *)&Prg->GlobalData[0x28],(uint)(WrittenFileSize>>32));
    VM.Execute(Prg);
  }
}


void Unpack::UnpWriteArea(unsigned int StartPtr,unsigned int EndPtr)
{
  if (EndPtr!=StartPtr)
    UnpSomeRead=true;
  if (EndPtr<StartPtr)
  {
    UnpWriteData(&Window[StartPtr],-(int)StartPtr & MAXWINMASK);
    UnpWriteData(Window,EndPtr);
    UnpAllBuf=true;
  }
  else
    UnpWriteData(&Window[StartPtr],EndPtr-StartPtr);
}


void Unpack::UnpWriteData(byte *Data,size_t Size)
{
  if (WrittenFileSize>=DestUnpSize)
    return;
  size_t WriteSize=Size;
  int64 LeftToWrite=DestUnpSize-WrittenFileSize;
  if ((int64)WriteSize>LeftToWrite)
    WriteSize=(size_t)LeftToWrite;
  UnpIO->UnpWrite(Data,WriteSize);
  WrittenFileSize+=Size;
}


bool Unpack::ReadTables()
{
  byte BitLength[BC];
  byte Table[HUFF_TABLE_SIZE];
  if (InAddr>ReadTop-25)
    if (!UnpReadBuf())
      return(false);
  faddbits((8-InBit)&7);
  uint BitField=fgetbits();
  if (BitField & 0x8000)
  {
    UnpBlockType=BLOCK_PPM;
    return(PPM.DecodeInit(this,PPMEscChar));
  }
  UnpBlockType=BLOCK_LZ;
  
  PrevLowDist=0;
  LowDistRepCount=0;

  if (!(BitField & 0x4000))
    memset(UnpOldTable,0,sizeof(UnpOldTable));
  faddbits(2);

  for (int I=0;I<BC;I++)
  {
    int Length=(byte)(fgetbits() >> 12);
    faddbits(4);
    if (Length==15)
    {
      int ZeroCount=(byte)(fgetbits() >> 12);
      faddbits(4);
      if (ZeroCount==0)
        BitLength[I]=15;
      else
      {
        ZeroCount+=2;
        while (ZeroCount-- > 0 && I<sizeof(BitLength)/sizeof(BitLength[0]))
          BitLength[I++]=0;
        I--;
      }
    }
    else
      BitLength[I]=Length;
  }
  MakeDecodeTables(BitLength,&BD,BC);

  const int TableSize=HUFF_TABLE_SIZE;
  for (int I=0;I<TableSize;)
  {
    if (InAddr>ReadTop-5)
      if (!UnpReadBuf())
        return(false);
    int Number=DecodeNumber(&BD);
    if (Number<16)
    {
      Table[I]=(Number+UnpOldTable[I]) & 0xf;
      I++;
    }
    else
      if (Number<18)
      {
        int N;
        if (Number==16)
        {
          N=(fgetbits() >> 13)+3;
          faddbits(3);
        }
        else
        {
          N=(fgetbits() >> 9)+11;
          faddbits(7);
        }
        while (N-- > 0 && I<TableSize)
        {
          Table[I]=Table[I-1];
          I++;
        }
      }
      else
      {
        int N;
        if (Number==18)
        {
          N=(fgetbits() >> 13)+3;
          faddbits(3);
        }
        else
        {
          N=(fgetbits() >> 9)+11;
          faddbits(7);
        }
        while (N-- > 0 && I<TableSize)
          Table[I++]=0;
      }
  }
  TablesRead=true;
  if (InAddr>ReadTop)
    return(false);
  MakeDecodeTables(&Table[0],&LD,NC);
  MakeDecodeTables(&Table[NC],&DD,DC);
  MakeDecodeTables(&Table[NC+DC],&LDD,LDC);
  MakeDecodeTables(&Table[NC+DC+LDC],&RD,RC);
  memcpy(UnpOldTable,Table,sizeof(UnpOldTable));
  return(true);
}


void Unpack::UnpInitData(int Solid)
{
  if (!Solid)
  {
    TablesRead=false;
    memset(OldDist,0,sizeof(OldDist));
    OldDistPtr=0;
    LastDist=LastLength=0;
//    memset(Window,0,MAXWINSIZE);
    memset(UnpOldTable,0,sizeof(UnpOldTable));
    memset(&LD,0,sizeof(LD));
    memset(&DD,0,sizeof(DD));
    memset(&LDD,0,sizeof(LDD));
    memset(&RD,0,sizeof(RD));
    memset(&BD,0,sizeof(BD));
    UnpPtr=WrPtr=0;
    PPMEscChar=2;
    UnpBlockType=BLOCK_LZ;

    InitFilters();
  }
  InitBitInput();
  WrittenFileSize=0;
  ReadTop=0;
  ReadBorder=0;
#ifndef SFX_MODULE
  UnpInitData20(Solid);
#endif
}


void Unpack::InitFilters()
{
  OldFilterLengths.Reset();
  LastFilter=0;

  for (size_t I=0;I<Filters.Size();I++)
    delete Filters[I];
  Filters.Reset();
  for (size_t I=0;I<PrgStack.Size();I++)
    delete PrgStack[I];
  PrgStack.Reset();
}


// LengthTable contains the length in bits for every element of alphabet.
// Dec is the structure to decode Huffman code/
// Size is size of length table and DecodeNum field in Dec structure,
void Unpack::MakeDecodeTables(byte *LengthTable,DecodeTable *Dec,uint Size)
{
  // Size of alphabet and DecodePos array.
  Dec->MaxNum=Size;

  // Calculate how many entries for every bit length in LengthTable we have.
  uint LengthCount[16];
  memset(LengthCount,0,sizeof(LengthCount));
  for (size_t I=0;I<Size;I++)
    LengthCount[LengthTable[I] & 0xf]++;

  // We must not calculate the number of zero length codes.
  LengthCount[0]=0;

  // Set the entire DecodeNum to zero.
  memset(Dec->DecodeNum,0,Size*sizeof(*Dec->DecodeNum));

  // Initialize not really used entry for zero length code.
  Dec->DecodePos[0]=0;

  // Start code for bit length 1 is 0.
  Dec->DecodeLen[0]=0;

  // Right aligned upper limit code for current bit length.
  uint UpperLimit=0;

  for (size_t I=1;I<16;I++)
  {
    // Adjust the upper limit code.
    UpperLimit+=LengthCount[I];

    // Left aligned upper limit code.
    uint LeftAligned=UpperLimit<<(16-I);

    // Prepare the upper limit code for next bit length.
    UpperLimit*=2;

    // Store the left aligned upper limit code.
    Dec->DecodeLen[I]=(uint)LeftAligned;

    // Every item of this array contains the sum of all preceding items.
    // So it contains the start position in code list for every bit length. 
    Dec->DecodePos[I]=Dec->DecodePos[I-1]+LengthCount[I-1];
  }

  // Prepare the copy of DecodePos. We'll modify this copy below,
  // so we cannot use the original DecodePos.
  uint CopyDecodePos[16];
  memcpy(CopyDecodePos,Dec->DecodePos,sizeof(CopyDecodePos));

  // For every bit length in the bit length table and so for every item
  // of alphabet.
  for (uint I=0;I<Size;I++)
  {
    // Get the current bit length.
    byte CurBitLength=LengthTable[I] & 0xf;

    if (CurBitLength!=0)
    {
      // Last position in code list for current bit length.
      uint LastPos=CopyDecodePos[CurBitLength];

      // Prepare the decode table, so this position in code list will be
      // decoded to current alphabet item number.
      Dec->DecodeNum[LastPos]=(ushort)I;

      // We'll use next position number for this bit length next time.
      // So we pass through the entire range of positions available
      // for every bit length.
      CopyDecodePos[CurBitLength]++;
    }
  }

  // Define the number of bits to process in quick mode. We use more bits
  // for larger alphabets. More bits means that more codes will be processed
  // in quick mode, but also that more time will be spent to preparation
  // of tables for quick decode.
  switch (Size)
  {
    case NC:
    case NC20:
      Dec->QuickBits=MAX_QUICK_DECODE_BITS;
      break;
    default:
      Dec->QuickBits=MAX_QUICK_DECODE_BITS-3;
      break;
  }

  // Size of tables for quick mode.
  uint QuickDataSize=1<<Dec->QuickBits;

  // Bit length for current code, start from 1 bit codes. It is important
  // to use 1 bit instead of 0 for minimum code length, so we are moving
  // forward even when processing a corrupt archive.
  uint CurBitLength=1;

  // For every right aligned bit string which supports the quick decoding.
  for (uint Code=0;Code<QuickDataSize;Code++)
  {
    // Left align the current code, so it will be in usual bit field format.
    uint BitField=Code<<(16-Dec->QuickBits);

    // Prepare the table for quick decoding of bit lengths.
  
    // Find the upper limit for current bit field and adjust the bit length
    // accordingly if necessary.
    while (BitField>=Dec->DecodeLen[CurBitLength] && CurBitLength<ASIZE(Dec->DecodeLen))
      CurBitLength++;

    // Translation of right aligned bit string to bit length.
    Dec->QuickLen[Code]=CurBitLength;

    // Prepare the table for quick translation of position in code list
    // to position in alphabet.

    // Calculate the distance from the start code for current bit length.
    uint Dist=BitField-Dec->DecodeLen[CurBitLength-1];

    // Right align the distance.
    Dist>>=(16-CurBitLength);

    // Now we can calculate the position in the code list. It is the sum
    // of first position for current bit length and right aligned distance
    // between our bit field and start code for current bit length.
    uint Pos=Dec->DecodePos[CurBitLength]+Dist;

    if (Pos<Size) // Safety check for damaged archives.
    {
      // Define the code to alphabet number translation.
      Dec->QuickNum[Code]=Dec->DecodeNum[Pos];
    }
    else
      Dec->QuickNum[Code]=0;
  }
}
