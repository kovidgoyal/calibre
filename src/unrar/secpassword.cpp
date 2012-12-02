#include "rar.hpp"

#ifdef _WIN_ALL
typedef BOOL (WINAPI *CRYPTPROTECTMEMORY)(LPVOID pData,DWORD cbData,DWORD dwFlags);
typedef BOOL (WINAPI *CRYPTUNPROTECTMEMORY)(LPVOID pData,DWORD cbData,DWORD dwFlags);

#ifndef CRYPTPROTECTMEMORY_BLOCK_SIZE
#define CRYPTPROTECTMEMORY_BLOCK_SIZE           16
#define CRYPTPROTECTMEMORY_SAME_PROCESS         0x00
#endif

class CryptLoader
{
  private:
    HMODULE hCrypt;
    bool LoadCalled;
  public:
    CryptLoader() 
    {
      hCrypt=NULL;
      pCryptProtectMemory=NULL;
      pCryptUnprotectMemory=NULL;
      LoadCalled=false;
    }
    ~CryptLoader()
    {
      if (hCrypt!=NULL)
        FreeLibrary(hCrypt);
      hCrypt=NULL;
      pCryptProtectMemory=NULL;
      pCryptUnprotectMemory=NULL;
    };
    void Load()
    {
      if (!LoadCalled)
      {
        hCrypt = LoadLibraryW(L"Crypt32.dll");
        if (hCrypt != NULL)
        {
          pCryptProtectMemory = (CRYPTPROTECTMEMORY)GetProcAddress(hCrypt, "CryptProtectMemory");
          pCryptUnprotectMemory = (CRYPTUNPROTECTMEMORY)GetProcAddress(hCrypt, "CryptUnprotectMemory");
        }
        LoadCalled=true;
      }
    }

    CRYPTPROTECTMEMORY pCryptProtectMemory;
    CRYPTUNPROTECTMEMORY pCryptUnprotectMemory;
};

// We want to call FreeLibrary when RAR is exiting.
CryptLoader GlobalCryptLoader;
#endif

SecPassword::SecPassword()
{
  Set(L"");
}


SecPassword::~SecPassword()
{
  Clean();
}


void SecPassword::Clean()
{
  PasswordSet=false;
  cleandata(Password,sizeof(Password));
}
 

// When we call memset in end of function to clean local variables
// for security reason, compiler optimizer can remove such call.
// So we use our own function for this purpose.
void cleandata(void *data,size_t size)
{
#if defined(_WIN_ALL) && defined(_MSC_VER)
  SecureZeroMemory(data,size);
#else
  // 'volatile' is required. Otherwise optimizers can remove this function
  // if cleaning local variables, which are not used after that.
  volatile byte *d = (volatile byte *)data;
  for (size_t i=0;i<size;i++)
    d[i]=0;
#endif
}


// We got a complain from user that it is possible to create WinRAR dump
// with "Create dump file" command in Windows Task Manager and then easily
// locate Unicode password string in the dump. It is unsecure if several
// people share the same computer and somebody left WinRAR copy with entered
// password. So we decided to obfuscate the password to make it more difficult
// to find it in dump.
void SecPassword::Process(const wchar *Src,wchar *Dst,size_t MaxSize,bool Encode)
{
#ifdef _WIN_ALL
  // Try to utilize the secure Crypt[Un]ProtectMemory if possible.
  if (GlobalCryptLoader.pCryptProtectMemory==NULL)
    GlobalCryptLoader.Load();
  if (Encode)
  {
    if (GlobalCryptLoader.pCryptProtectMemory!=NULL && 
        MaxSize%CRYPTPROTECTMEMORY_BLOCK_SIZE==0)
    {
      memcpy(Dst,Src,MaxSize*sizeof(*Dst));
      if (!GlobalCryptLoader.pCryptProtectMemory(Dst,DWORD(MaxSize*sizeof(*Dst)),
          CRYPTPROTECTMEMORY_SAME_PROCESS))
      {
        ErrHandler.GeneralErrMsg("CryptProtectMemory failed");
        ErrHandler.SysErrMsg();
        ErrHandler.Exit(RARX_FATAL);
      }
      return;
    }
  }
  else
  {
    if (GlobalCryptLoader.pCryptUnprotectMemory!=NULL && 
        MaxSize%CRYPTPROTECTMEMORY_BLOCK_SIZE==0)
    {
      memcpy(Dst,Src,MaxSize*sizeof(*Dst));
      if (!GlobalCryptLoader.pCryptUnprotectMemory(Dst,DWORD(MaxSize*sizeof(*Dst)),
          CRYPTPROTECTMEMORY_SAME_PROCESS))
      {
        ErrHandler.GeneralErrMsg("CryptUnprotectMemory failed");
        ErrHandler.SysErrMsg();
        ErrHandler.Exit(RARX_FATAL);
      }
      return;
    }
  }
#endif
  
  // CryptProtectMemory is not available, so only slightly obfuscate data.
  uint Key;
#ifdef _WIN_ALL
  Key=GetCurrentProcessId();
#elif defined(_UNIX)
  Key=getpid();
#else
  Key=10203040; // Just an arbitrary value.
#endif

  for (size_t I=0;I<MaxSize;I++)
    Dst[I]=wchar(Src[I]^(Key+I+75));
}


void SecPassword::Get(wchar *Psw,size_t MaxSize)
{
  if (PasswordSet)
  {
    Process(Password,Psw,MaxSize,false);
    Psw[MaxSize-1]=0;
  }
  else
    *Psw=0;
}


void SecPassword::Set(const wchar *Psw)
{
  if (*Psw==0)
  {
    PasswordSet=false;
    memset(Password,0,sizeof(Password));
  }
  else
  {
    PasswordSet=true;
    Process(Psw,Password,ASIZE(Password),true);
  }
}


size_t SecPassword::Length()
{
  wchar Plain[MAXPASSWORD];
  Get(Plain,ASIZE(Plain));
  size_t Length=wcslen(Plain);
  cleandata(Plain,ASIZE(Plain));
  return Length;
}


bool SecPassword::operator == (SecPassword &psw)
{
  // We cannot compare encoded data directly, because there is no guarantee
  // than encryption function will always produce the same result for same
  // data (salt?) and because we do not clean the rest of password buffer
  // after trailing zero before encoding password. So we decode first.
  wchar Plain1[MAXPASSWORD],Plain2[MAXPASSWORD];
  Get(Plain1,ASIZE(Plain1));
  psw.Get(Plain2,ASIZE(Plain2));
  bool Result=wcscmp(Plain1,Plain2)==0;
  cleandata(Plain1,ASIZE(Plain1));
  cleandata(Plain2,ASIZE(Plain2));
  return Result;
}

