#ifndef _RAR_UNICODE_
#define _RAR_UNICODE_

#ifndef _EMX
#define MBFUNCTIONS
#endif

#if defined(MBFUNCTIONS) || defined(_WIN_ALL) || defined(_EMX) && !defined(_DJGPP)
#define UNICODE_SUPPORTED
#endif

#if !defined(SFX_MODULE) && (defined(_MSC_VER) || defined(__BORLANDC__))
// If C_UNICODE_RTL is defined, we can use library Unicode functions like
// wcscpy. Otherwise, for compatibility with old compilers or for removing
// RTL to reduce SFX module size, we need need to use our own implementations.
#define C_UNICODE_RTL
#endif

#ifdef _WIN_ALL
#define DBCS_SUPPORTED
#endif

#ifdef _EMX
int uni_init(int codepage);
int uni_done();
#endif

#ifdef __BORLANDC__
// Borland C++ Builder 5 uses the old style swprintf without the buffer size,
// so we replace it with snwprintf in our custom sprintfw definition.
#define sprintfw snwprintf
#elif defined (__OpenBSD__)
#define sprintfw(s,...) *(s)=0
#else
#define sprintfw swprintf
#endif

bool WideToChar(const wchar *Src,char *Dest,size_t DestSize=0x1000000);
bool CharToWide(const char *Src,wchar *Dest,size_t DestSize=0x1000000);
byte* WideToRaw(const wchar *Src,byte *Dest,size_t SrcSize=0x1000000);
wchar* RawToWide(const byte *Src,wchar *Dest,size_t DestSize=0x1000000);
void WideToUtf(const wchar *Src,char *Dest,size_t DestSize);
bool UtfToWide(const char *Src,wchar *Dest,size_t DestSize);
bool UnicodeEnabled();

int wcsicomp(const wchar *s1,const wchar *s2);
int wcsnicomp(const wchar *s1,const wchar *s2,size_t n);
wchar* wcslower(wchar *Str);
wchar* wcsupper(wchar *Str);
int toupperw(int ch);
int tolowerw(int ch);
int atoiw(const wchar *s);

#ifdef DBCS_SUPPORTED
class SupportDBCS
{
  public:
    SupportDBCS();
    void Init();

    char* charnext(const char *s);
    size_t strlend(const char *s);
    char *strchrd(const char *s, int c);
    char *strrchrd(const char *s, int c);
    void copychrd(char *dest,const char *src);

    bool IsLeadByte[256];
    bool DBCSMode;
};

extern SupportDBCS gdbcs;

inline char* charnext(const char *s) {return (char *)(gdbcs.DBCSMode ? gdbcs.charnext(s):s+1);}
inline size_t strlend(const char *s) {return (uint)(gdbcs.DBCSMode ? gdbcs.strlend(s):strlen(s));}
inline char* strchrd(const char *s, int c) {return (char *)(gdbcs.DBCSMode ? gdbcs.strchrd(s,c):strchr(s,c));}
inline char* strrchrd(const char *s, int c) {return (char *)(gdbcs.DBCSMode ? gdbcs.strrchrd(s,c):strrchr(s,c));}
inline void copychrd(char *dest,const char *src) {if (gdbcs.DBCSMode) gdbcs.copychrd(dest,src); else *dest=*src;}
inline bool IsDBCSMode() {return(gdbcs.DBCSMode);}
inline void InitDBCS() {gdbcs.Init();}

#else
#define charnext(s) ((s)+1)
#define strlend strlen
#define strchrd strchr
#define strrchrd strrchr
#define IsDBCSMode() (true)
inline void copychrd(char *dest,const char *src) {*dest=*src;}
#endif

#endif
