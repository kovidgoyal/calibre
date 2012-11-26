#ifndef _RAR_CRYPT_
#define _RAR_CRYPT_

enum { OLD_DECODE=0,OLD_ENCODE=1,NEW_CRYPT=2 };


struct CryptKeyCacheItem
{
#ifndef _SFX_RTL_
  CryptKeyCacheItem()
  {
    Password.Set(L"");
  }

  ~CryptKeyCacheItem()
  {
    memset(AESKey,0,sizeof(AESKey));
    memset(AESInit,0,sizeof(AESInit));
    memset(&Password,0,sizeof(Password));
  }
#endif
  byte AESKey[16],AESInit[16];
  SecPassword Password;
  bool SaltPresent;
  byte Salt[SALT_SIZE];
  bool HandsOffHash;
};

class CryptData
{
  private:
    void Encode13(byte *Data,uint Count);
    void Decode13(byte *Data,uint Count);
    void Crypt15(byte *Data,uint Count);
    void UpdKeys(byte *Buf);
    void Swap(byte *Ch1,byte *Ch2);
    void SetOldKeys(const char *Password);

    Rijndael rin;
    
    byte SubstTable[256];
    uint Key[4];
    ushort OldKey[4];
    byte PN1,PN2,PN3;

    byte AESKey[16],AESInit[16];

    static CryptKeyCacheItem Cache[4];
    static int CachePos;
  public:
    void SetCryptKeys(SecPassword *Password,const byte *Salt,bool Encrypt,bool OldOnly,bool HandsOffHash);
    void SetAV15Encryption();
    void SetCmt13Encryption();
    void EncryptBlock20(byte *Buf);
    void DecryptBlock20(byte *Buf);
    void EncryptBlock(byte *Buf,size_t Size);
    void DecryptBlock(byte *Buf,size_t Size);
    void Crypt(byte *Data,uint Count,int Method);
    static void SetSalt(byte *Salt,int SaltSize);
};

#endif
