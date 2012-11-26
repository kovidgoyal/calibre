#ifndef _RAR_DATAIO_
#define _RAR_DATAIO_

class CmdAdd;
class Unpack;


class ComprDataIO
{
  private:
    void ShowUnpRead(int64 ArcPos,int64 ArcSize);
    void ShowUnpWrite();


    bool UnpackFromMemory;
    size_t UnpackFromMemorySize;
    byte *UnpackFromMemoryAddr;

    bool UnpackToMemory;
    size_t UnpackToMemorySize;
    byte *UnpackToMemoryAddr;

    size_t UnpWrSize;
    byte *UnpWrAddr;

    int64 UnpPackedSize;

    bool ShowProgress;
    bool TestMode;
    bool SkipUnpCRC;

    File *SrcFile;
    File *DestFile;

    CmdAdd *Command;

    FileHeader *SubHead;
    int64 *SubHeadPos;

#ifndef RAR_NOCRYPT
    CryptData Crypt;
    CryptData Decrypt;
#endif


    int LastPercent;

    char CurrentCommand;

  public:
    ComprDataIO();
    void Init();
    int UnpRead(byte *Addr,size_t Count);
    void UnpWrite(byte *Addr,size_t Count);
    void EnableShowProgress(bool Show) {ShowProgress=Show;}
    void GetUnpackedData(byte **Data,size_t *Size);
    void SetPackedSizeToRead(int64 Size) {UnpPackedSize=Size;}
    void SetTestMode(bool Mode) {TestMode=Mode;}
    void SetSkipUnpCRC(bool Skip) {SkipUnpCRC=Skip;}
    void SetFiles(File *SrcFile,File *DestFile);
    void SetCommand(CmdAdd *Cmd) {Command=Cmd;}
    void SetSubHeader(FileHeader *hd,int64 *Pos) {SubHead=hd;SubHeadPos=Pos;}
    void SetEncryption(int Method,SecPassword *Password,const byte *Salt,bool Encrypt,bool HandsOffHash);
    void SetAV15Encryption();
    void SetCmt13Encryption();
    void SetUnpackToMemory(byte *Addr,uint Size);
    void SetCurrentCommand(char Cmd) {CurrentCommand=Cmd;}

    bool PackVolume;
    bool UnpVolume;
    bool NextVolumeMissing;
    int64 TotalPackRead;
    int64 UnpArcSize;
    int64 CurPackRead,CurPackWrite,CurUnpRead,CurUnpWrite;

    // Size of already processed archives.
    // Used to calculate the total operation progress.
    int64 ProcessedArcSize;

    int64 TotalArcSize;

    uint PackFileCRC,UnpFileCRC,PackedCRC;

    int Encryption;
    int Decryption;
};

#endif
