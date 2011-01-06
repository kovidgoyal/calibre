/**
 * Copyright 2009 Kovid Goyal <kovid@kovidgoyal.net>
 * License: GNU GPL v2+
 */


#pragma once
#include <string>
#include <sstream>

using namespace std;

namespace calibre_reflow {

    class ReflowException : public exception {
        const char *msg;
        public:
            ReflowException(const char *m) : msg(m) {}
            virtual const char* what() const throw() { return msg; }
    };

inline string encode_for_xml(const string &sSrc )
{
    ostringstream sRet;

    for( string::const_iterator iter = sSrc.begin(); iter!=sSrc.end(); iter++ )
    {
        unsigned char c = (unsigned char)*iter;

        switch( c )
        {
            case '&': sRet << "&amp;"; break;
            case '<': sRet << "&lt;"; break;
            case '>': sRet << "&gt;"; break;
            case '"': sRet << "&quot;"; break;

            default: sRet << c;
        }
    }

    return sRet.str();
}


}
