/*
 * Copyright 2011 Google Inc. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "sfntly/tag.h"
#include "sfntly/port/endian.h"

// Use a macro instead of GenerateTag() because gcc 4.4.3 creates static
// initializers in that case.
#define TAG(a, b, c, d) ((a << 24) | (b << 16) | (c << 8) | d);

namespace sfntly {

const int32_t Tag::ttcf = TAG('t', 't', 'c', 'f');
const int32_t Tag::cmap = TAG('c', 'm', 'a', 'p');
const int32_t Tag::head = TAG('h', 'e', 'a', 'd');
const int32_t Tag::hhea = TAG('h', 'h', 'e', 'a');
const int32_t Tag::hmtx = TAG('h', 'm', 't', 'x');
const int32_t Tag::maxp = TAG('m', 'a', 'x', 'p');
const int32_t Tag::name = TAG('n', 'a', 'm', 'e');
const int32_t Tag::OS_2 = TAG('O', 'S', '/', '2');
const int32_t Tag::post = TAG('p', 'o', 's', 't');
const int32_t Tag::cvt  = TAG('c', 'v', 't', ' ');
const int32_t Tag::fpgm = TAG('f', 'p', 'g', 'm');
const int32_t Tag::glyf = TAG('g', 'l', 'y', 'f');
const int32_t Tag::loca = TAG('l', 'o', 'c', 'a');
const int32_t Tag::prep = TAG('p', 'r', 'e', 'p');
const int32_t Tag::CFF  = TAG('C', 'F', 'F', ' ');
const int32_t Tag::VORG = TAG('V', 'O', 'R', 'G');
const int32_t Tag::EBDT = TAG('E', 'B', 'D', 'T');
const int32_t Tag::EBLC = TAG('E', 'B', 'L', 'C');
const int32_t Tag::EBSC = TAG('E', 'B', 'S', 'C');
const int32_t Tag::BASE = TAG('B', 'A', 'S', 'E');
const int32_t Tag::GDEF = TAG('G', 'D', 'E', 'F');
const int32_t Tag::GPOS = TAG('G', 'P', 'O', 'S');
const int32_t Tag::GSUB = TAG('G', 'S', 'U', 'B');
const int32_t Tag::JSTF = TAG('J', 'S', 'T', 'F');
const int32_t Tag::DSIG = TAG('D', 'S', 'I', 'G');
const int32_t Tag::gasp = TAG('g', 'a', 's', 'p');
const int32_t Tag::hdmx = TAG('h', 'd', 'm', 'x');
const int32_t Tag::kern = TAG('k', 'e', 'r', 'n');
const int32_t Tag::LTSH = TAG('L', 'T', 'S', 'H');
const int32_t Tag::PCLT = TAG('P', 'C', 'L', 'T');
const int32_t Tag::VDMX = TAG('V', 'D', 'M', 'X');
const int32_t Tag::vhea = TAG('v', 'h', 'e', 'a');
const int32_t Tag::vmtx = TAG('v', 'm', 't', 'x');
const int32_t Tag::bsln = TAG('b', 's', 'l', 'n');
const int32_t Tag::feat = TAG('f', 'e', 'a', 't');
const int32_t Tag::lcar = TAG('l', 'c', 'a', 'r');
const int32_t Tag::morx = TAG('m', 'o', 'r', 'x');
const int32_t Tag::opbd = TAG('o', 'p', 'b', 'd');
const int32_t Tag::prop = TAG('p', 'r', 'o', 'p');
const int32_t Tag::Feat = TAG('F', 'e', 'a', 't');
const int32_t Tag::Glat = TAG('G', 'l', 'a', 't');
const int32_t Tag::Gloc = TAG('G', 'l', 'o', 'c');
const int32_t Tag::Sile = TAG('S', 'i', 'l', 'e');
const int32_t Tag::Silf = TAG('S', 'i', 'l', 'f');
const int32_t Tag::bhed = TAG('b', 'h', 'e', 'd');
const int32_t Tag::bdat = TAG('b', 'd', 'a', 't');
const int32_t Tag::bloc = TAG('b', 'l', 'o', 'c');

const int32_t CFF_TABLE_ORDERING[] = {
    Tag::head,
    Tag::hhea,
    Tag::maxp,
    Tag::OS_2,
    Tag::name,
    Tag::cmap,
    Tag::post,
    Tag::CFF };
const size_t CFF_TABLE_ORDERING_SIZE =
    sizeof(CFF_TABLE_ORDERING) / sizeof(int32_t);

const int32_t TRUE_TYPE_TABLE_ORDERING[] = {
    Tag::head,
    Tag::hhea,
    Tag::maxp,
    Tag::OS_2,
    Tag::hmtx,
    Tag::LTSH,
    Tag::VDMX,
    Tag::hdmx,
    Tag::cmap,
    Tag::fpgm,
    Tag::prep,
    Tag::cvt,
    Tag::loca,
    Tag::glyf,
    Tag::kern,
    Tag::name,
    Tag::post,
    Tag::gasp,
    Tag::PCLT,
    Tag::DSIG };
const size_t TRUE_TYPE_TABLE_ORDERING_SIZE =
    sizeof(TRUE_TYPE_TABLE_ORDERING) / sizeof(int32_t);

}  // namespace sfntly
