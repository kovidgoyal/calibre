#ifndef _RAR_SECURE_PASSWORD_
#define _RAR_SECURE_PASSWORD_

// Store a password securely (if data encryption is provided by OS)
// or obfuscated to make search for password in memory dump less trivial.
class SecPassword
{
  private:
    void Process(const wchar *Src,wchar *Dst,size_t MaxSize,bool Encode);

    wchar Password[MAXPASSWORD];

    // It is important to have this 'bool' value, so if our object is cleaned
    // with memset as a part of larger structure, it is handled correctly.
    bool PasswordSet;
  public:
    SecPassword();
    ~SecPassword();
    void Clean();
    void Get(wchar *Psw,size_t MaxSize);
    void Set(const wchar *Psw);
    bool IsSet() {return PasswordSet;}
    size_t Length();
    bool operator == (SecPassword &psw);
};


void cleandata(void *data,size_t size);

#endif
