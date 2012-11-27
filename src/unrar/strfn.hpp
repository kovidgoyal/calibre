#ifndef _RAR_STRFN_
#define _RAR_STRFN_

const char* NullToEmpty(const char *Str);
const wchar* NullToEmpty(const wchar *Str);
char* IntNameToExt(const char *Name);
void ExtToInt(const char *Src,char *Dest);
void IntToExt(const char *Src,char *Dest);
char* strlower(char *Str);
char* strupper(char *Str);
int stricomp(const char *Str1,const char *Str2);
int strnicomp(const char *Str1,const char *Str2,size_t N);
char* RemoveEOL(char *Str);
char* RemoveLF(char *Str);
wchar* RemoveLF(wchar *Str);
unsigned char loctolower(unsigned char ch);
unsigned char loctoupper(unsigned char ch);

char* strncpyz(char *dest, const char *src, size_t maxlen);
wchar* wcsncpyz(wchar *dest, const wchar *src, size_t maxlen);
char* strncatz(char* dest, const char* src, size_t maxlen);
wchar* wcsncatz(wchar* dest, const wchar* src, size_t maxlen);

unsigned char etoupper(unsigned char ch);
wchar etoupperw(wchar ch);

bool IsDigit(int ch);
bool IsSpace(int ch);
bool IsAlpha(int ch);


#ifndef SFX_MODULE
uint GetDigits(uint Number);
#endif

bool LowAscii(const char *Str);
bool LowAscii(const wchar *Str);


int stricompc(const char *Str1,const char *Str2);
#ifndef SFX_MODULE
int wcsicompc(const wchar *Str1,const wchar *Str2);
#endif

void itoa(int64 n,char *Str);
int64 atoil(const char *Str);
void itoa(int64 n,wchar *Str);
int64 atoil(const wchar *Str);
const wchar* GetWide(const char *Src);
const wchar* GetWide(const char *Src,const wchar *SrcW);
const wchar* GetCmdParam(const wchar *CmdLine,wchar *Param,size_t MaxSize);

#endif
