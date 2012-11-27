#ifndef _RAR_UNPACK_
#define _RAR_UNPACK_

enum BLOCK_TYPES {BLOCK_LZ,BLOCK_PPM};

// Maximum allowed number of compressed bits processed in quick mode.
#define MAX_QUICK_DECODE_BITS 10

// Maximum number of filters per entire data block.
#define MAX_FILTERS 1024

// Decode compressed bit fields to alphabet numbers.
struct DecodeTable
{
  // Real size of DecodeNum table.
  uint MaxNum;

  // Left aligned start and upper limit codes defining code space 
  // ranges for bit lengths. DecodeLen[BitLength-1] defines the start of
  // range for bit length and DecodeLen[BitLength] defines next code
  // after the end of range or in other words the upper limit code
  // for specified bit length.
  uint DecodeLen[16]; 

  // Every item of this array contains the sum of all preceding items.
  // So it contains the start position in code list for every bit length. 
  uint DecodePos[16];

  // Number of compressed bits processed in quick mode.
  // Must not exceed MAX_QUICK_DECODE_BITS.
  uint QuickBits;

  // Translates compressed bits (up to QuickBits length)
  // to bit length in quick mode.
  byte QuickLen[1<<MAX_QUICK_DECODE_BITS];

  // Translates compressed bits (up to QuickBits length)
  // to position in alphabet in quick mode.
  // 'ushort' saves some memory and even provides a little speed gain
  // comparting to 'uint' here.
  ushort QuickNum[1<<MAX_QUICK_DECODE_BITS];

  // Translate the position in code list to position in alphabet.
  // We do not allocate it dynamically to avoid performance overhead
  // introduced by pointer, so we use the largest possible table size
  // as array dimension. Real size of this array is defined in MaxNum.
  // We use this array if compressed bit field is too lengthy
  // for QuickLen based translation.
  // 'ushort' saves some memory and even provides a little speed gain
  // comparting to 'uint' here.
  ushort DecodeNum[LARGEST_TABLE_SIZE];
};

struct UnpackFilter
{
  unsigned int BlockStart;
  unsigned int BlockLength;
  unsigned int ExecCount;
  bool NextWindow;

  // position of parent filter in Filters array used as prototype for filter
  // in PrgStack array. Not defined for filters in Filters array.
  unsigned int ParentFilter;

  VM_PreparedProgram Prg;
};


struct AudioVariables // For RAR 2.0 archives only.
{
  int K1,K2,K3,K4,K5;
  int D1,D2,D3,D4;
  int LastDelta;
  unsigned int Dif[11];
  unsigned int ByteCount;
  int LastChar;
};


class Unpack:private BitInput
{
  private:

    void Unpack29(bool Solid);
    bool UnpReadBuf();
    void UnpWriteBuf();
    void ExecuteCode(VM_PreparedProgram *Prg);
    void UnpWriteArea(unsigned int StartPtr,unsigned int EndPtr);
    void UnpWriteData(byte *Data,size_t Size);
    bool ReadTables();
    void MakeDecodeTables(byte *LengthTable,DecodeTable *Dec,uint Size);
    _forceinline uint DecodeNumber(DecodeTable *Dec);
    inline int SafePPMDecodeChar();
    void CopyString();
    inline void InsertOldDist(unsigned int Distance);
    void UnpInitData(int Solid);
    _forceinline void CopyString(uint Length,uint Distance);
    bool ReadEndOfBlock();
    bool ReadVMCode();
    bool ReadVMCodePPM();
    bool AddVMCode(unsigned int FirstByte,byte *Code,int CodeSize);
    void InitFilters();

    ComprDataIO *UnpIO;
    ModelPPM PPM;
    int PPMEscChar;

    // Virtual machine to execute filters code.
    RarVM VM;
  
    // Buffer to read VM filters code. We moved it here from AddVMCode
    // function to reduce time spent in BitInput constructor.
    BitInput VMCodeInp;

    // Filters code, one entry per filter.
    Array<UnpackFilter*> Filters;

    // Filters stack, several entrances of same filter are possible.
    Array<UnpackFilter*> PrgStack;

    // Lengths of preceding data blocks, one length of one last block
    // for every filter. Used to reduce the size required to write
    // the data block length if lengths are repeating.
    Array<int> OldFilterLengths;

    int LastFilter;

    bool TablesRead;

    DecodeTable LD;  // Decode literals.
    DecodeTable DD;  // Decode distances.
    DecodeTable LDD; // Decode lower bits of distances.
    DecodeTable RD;  // Decode repeating distances.
    DecodeTable BD;  // Decode bit lengths in Huffman table.

    unsigned int OldDist[4],OldDistPtr;
    unsigned int LastLength;

    // LastDist is necessary only for RAR2 and older with circular OldDist
    // array. In RAR3 last distance is always stored in OldDist[0].
    unsigned int LastDist;

    unsigned int UnpPtr,WrPtr;
    
    // Top border of read packed data.
    int ReadTop; 

    // Border to call UnpReadBuf. We use it instead of (ReadTop-C)
    // for optimization reasons. Ensures that we have C bytes in buffer
    // unless we are at the end of file.
    int ReadBorder;

    byte UnpOldTable[HUFF_TABLE_SIZE];

    int UnpBlockType;

    byte *Window;


    int64 DestUnpSize;

    bool Suspended;
    bool UnpAllBuf;
    bool UnpSomeRead;
    int64 WrittenFileSize;
    bool FileExtracted;

    int PrevLowDist,LowDistRepCount;

/***************************** Unpack v 1.5 *********************************/
    void Unpack15(bool Solid);
    void ShortLZ();
    void LongLZ();
    void HuffDecode();
    void GetFlagsBuf();
    void OldUnpInitData(int Solid);
    void InitHuff();
    void CorrHuff(ushort *CharSet,byte *NumToPlace);
    void OldCopyString(unsigned int Distance,unsigned int Length);
    uint DecodeNum(uint Num,uint StartPos,uint *DecTab,uint *PosTab);
    void OldUnpWriteBuf();

    ushort ChSet[256],ChSetA[256],ChSetB[256],ChSetC[256];
    byte NToPl[256],NToPlB[256],NToPlC[256];
    unsigned int FlagBuf,AvrPlc,AvrPlcB,AvrLn1,AvrLn2,AvrLn3;
    int Buf60,NumHuf,StMode,LCount,FlagsCnt;
    unsigned int Nhfb,Nlzb,MaxDist3;
/***************************** Unpack v 1.5 *********************************/

/***************************** Unpack v 2.0 *********************************/
    void Unpack20(bool Solid);

    DecodeTable MD[4]; // Decode multimedia data, up to 4 channels.

    unsigned char UnpOldTable20[MC20*4];
    int UnpAudioBlock,UnpChannels,UnpCurChannel,UnpChannelDelta;
    void CopyString20(unsigned int Length,unsigned int Distance);
    bool ReadTables20();
    void UnpInitData20(int Solid);
    void ReadLastTables();
    byte DecodeAudio(int Delta);
    struct AudioVariables AudV[4];
/***************************** Unpack v 2.0 *********************************/

  public:
    Unpack(ComprDataIO *DataIO);
    ~Unpack();
    void Init();
    void DoUnpack(int Method,bool Solid);
    bool IsFileExtracted() {return(FileExtracted);}
    void SetDestSize(int64 DestSize) {DestUnpSize=DestSize;FileExtracted=false;}
    void SetSuspended(bool Suspended) {Unpack::Suspended=Suspended;}

    unsigned int GetChar()
    {
      if (InAddr>BitInput::MAX_SIZE-30)
        UnpReadBuf();
      return(InBuf[InAddr++]);
    }
};

#endif
