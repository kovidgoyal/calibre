/* string replacement list class */
#ifndef _REPLIST_HXX_
#define _REPLIST_HXX_

#include "hunvisapi.h"

#include "w_char.hxx"

class LIBHUNSPELL_DLL_EXPORTED RepList
{
protected:
    replentry ** dat;
    int size;
    int pos;

public:
    RepList(int n);
    ~RepList();

    int get_pos();
    int add(char * pat1, char * pat2);
    replentry * item(int n);
    int near(const char * word);
    int match(const char * word, int n);
    int conv(const char * word, char * dest);
};
#endif
