/*
 * coretext_fontdatabase.mm
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */


#include <QtGlobal>
#if (QT_VERSION >= QT_VERSION_CHECK(5, 12, 0))
#include "coretext_fontdatabase-new.mm"
#else
#include "coretext_fontdatabase-old.mm"
#endif
