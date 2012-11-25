#ifndef _RAR_STRLIST_
#define _RAR_STRLIST_

class StringList
{
  private:
    Array<char> StringData;
    size_t CurPos;

    Array<wchar> StringDataW;
    size_t CurPosW;

    uint StringsCount;

    size_t SaveCurPos[16],SaveCurPosW[16],SavePosNumber;
  public:
    StringList();
    void Reset();
    void AddString(const char *Str);
    void AddString(const wchar *Str);
    void AddString(const char *Str,const wchar *StrW);
    bool GetString(char *Str,size_t MaxLength);
    bool GetString(wchar *Str,size_t MaxLength);
    bool GetString(char *Str,wchar *StrW,size_t MaxLength);
    bool GetString(char *Str,wchar *StrW,size_t MaxLength,int StringNum);
    char* GetString();
    wchar* GetStringW();
    bool GetString(char **Str,wchar **StrW);
    void Rewind();
    uint ItemsCount() {return(StringsCount);};
    size_t GetCharCount();
    bool Search(char *Str,wchar *StrW,bool CaseSensitive);
    void SavePosition();
    void RestorePosition();
};

#endif
