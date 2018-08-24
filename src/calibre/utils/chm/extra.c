/*
 * extra.c - full-text search support for pychm
 *
 * Copyright (C) 2004 Rubens Ramos <rubensr@users.sourceforge.net>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330,
 * Boston, MA 02111-1307, USA.
 *
 * Author: Rubens Ramos <rubensr@users.sourceforge.net>
 *
 * Heavily based on work done by:
 * Pabs <pabs@zip.to> - chmdeco
 * Razvan Cojocaru <razvanco@gmx.net> - xCHM
 *
 */

#include "chm_lib.h"
#ifdef __PYTHON__
#include "Python.h"
#else
#include <stdio.h>
#define PyObject void
#endif

typedef struct {
  PyObject_HEAD
  void *ptr;
  void *ty;
  int own;
  PyObject *next;
#ifdef SWIGPYTHON_BUILTIN
  PyObject *dict;
#endif
} SwigPyObject;

#include <stdlib.h>

#if defined(_WIN32) || defined(__WIN32__)
#       if defined(_MSC_VER)
#               if defined(STATIC_LINKED)
#                       define MODEXPORT(a) a
#                       define MODIMPORT(a) extern a
#               else
#                       define MODEXPORT(a) __declspec(dllexport) a
#                       define MODIMPORT(a) extern a
#               endif
#define uint64_t unsigned long long
#define uint32_t unsigned int
#define uint16_t unsigned short
#define uint8_t  unsigned char
#define size_t   int
#define strcasecmp _stricmp
#define strncasecmp _strnicmp
#       else
#               if defined(__BORLANDC__)
#                       define MODEXPORT(a) a _export
#                       define MODIMPORT(a) a _export
#               else
#                       define MODEXPORT(a) a
#                       define MODIMPORT(a) a
#               endif
#       endif
#else
#       define MODEXPORT(a) a
#       define MODIMPORT(a) a
#include <inttypes.h>
#include <strings.h>
#endif

#define false 0
#define true 1

#define FTS_HEADER_LEN 0x32
#define TOPICS_ENTRY_LEN 16
#define COMMON_BUF_LEN 1025

#define FREE(x) free (x); x = NULL

static uint16_t
get_uint16 (uint8_t* b) {
  return b[0] |
    b[1]<<8;
}

static uint32_t
get_uint32 (uint8_t* b) {
  return b[0] |
    b[1]<<8   |
    b[2]<<16  |
    b[3]<<24;
}

static uint64_t
be_encint (unsigned char *buffer, size_t *length)
{
  uint64_t result = 0;
  int shift=0;
  *length = 0;

  do {
    result |= ((*buffer) & 0x7f) << shift;
    shift += 7;
    *length = *length + 1;

  } while (*(buffer++) & 0x80);

  return result;
}

/*
  Finds the first unset bit in memory. Returns the number of set bits found.
  Returns -1 if the buffer runs out before we find an unset bit.
*/
static int
ffus (unsigned char* byte, int* bit, size_t *length) {
  int bits = 0;
  *length = 0;

  while(*byte & (1 << *bit)){
    if(*bit)
      --(*bit);
    else {
      ++byte;
      ++(*length);
      *bit = 7;
    }
    ++bits;
  }

  if(*bit)
    --(*bit);
  else {
    ++(*length);
    *bit = 7;
  }

  return bits;
}


static uint64_t
sr_int(unsigned char* byte, int* bit,
       unsigned char s, unsigned char r, size_t *length)
{
  uint64_t ret;
  unsigned char mask;
  int n, n_bits, num_bits, base, count;
  size_t fflen;

  *length = 0;

  if(!bit || *bit > 7 || s != 2)
    return ~(uint64_t)0;
  ret = 0;

  count = ffus(byte, bit, &fflen);
  *length += fflen;
  byte += *length;

  n_bits = n = r + (count ? count-1 : 0) ;

  while (n > 0) {
    num_bits = n > *bit ? *bit : n-1;
    base = n > *bit ? 0 : *bit - (n-1);

    switch (num_bits){
    case 0:
      mask = 1;
      break;
    case 1:
      mask = 3;
      break;
    case 2:
      mask = 7;
      break;
    case 3:
      mask = 0xf;
      break;
    case 4:
      mask = 0x1f;
      break;
    case 5:
      mask = 0x3f;
      break;
    case 6:
      mask = 0x7f;
      break;
    case 7:
      mask = 0xff;
      break;
    default:
      mask = 0xff;
      break;
    }

    mask <<= base;
    ret = (ret << (num_bits+1)) |
      (uint64_t)((*byte & mask) >> base);

    if( n > *bit ){
      ++byte;
      ++(*length);
      n -= *bit+1;
      *bit = 7;
    } else {
      *bit -= n;
      n = 0;
    }
  }

  if(count)
    ret |= (uint64_t)1 << n_bits;

  return ret;
}


static uint32_t
get_leaf_node_offset(struct chmFile *chmfile,
                     const char *text,
                     uint32_t initial_offset,
                     uint32_t buff_size,
                     uint16_t tree_depth,
                     struct chmUnitInfo *ui)
{
  unsigned char word_len;
  unsigned char pos;
  uint16_t free_space;
  char *wrd_buf;
  char *word = NULL;
  uint32_t test_offset = 0;
  uint32_t i = sizeof(uint16_t);
  unsigned char *buffer = malloc (buff_size);

  if (NULL == buffer)
    return 0;

  while (--tree_depth) {
    if (initial_offset == test_offset) {
      FREE(buffer);
      return 0;
    }

    test_offset = initial_offset;
    if (chm_retrieve_object (chmfile, ui, buffer,
                             initial_offset, buff_size) == 0) {
      FREE(buffer);
      return 0;
    }

    free_space = get_uint16 (buffer);

    while (i < buff_size - free_space) {

      word_len = *(buffer + i);
      pos = *(buffer + i + 1);

      wrd_buf = malloc (word_len);
      memcpy (wrd_buf, buffer + i + 2, word_len - 1);
      wrd_buf[word_len - 1] = 0;

      if (pos == 0) {
        FREE (word);
        word = (char *) strdup (wrd_buf);
      } else {
        word = realloc (word, word_len + pos + 1);
        strcpy (word + pos, wrd_buf);
      }

      FREE(wrd_buf);

      if (strcasecmp (text, word) <= 0) {
        initial_offset = get_uint32 (buffer + i + word_len + 1);
        break;
      }

      i += word_len + sizeof (unsigned char) + sizeof(uint32_t) +
        sizeof(uint16_t);
    }
  }

  if(initial_offset == test_offset)
    initial_offset = 0;

  FREE(word);
  FREE(buffer);

  return initial_offset;
}

static int
pychm_process_wlc (struct chmFile *chmfile,
                   uint64_t wlc_count, uint64_t wlc_size,
                   uint32_t wlc_offset, unsigned char ds,
                   unsigned char dr, unsigned char cs,
                   unsigned char cr, unsigned char ls,
                   unsigned char lr, struct chmUnitInfo *uimain,
                   struct chmUnitInfo* uitbl,
                   struct chmUnitInfo *uistrings,
                   struct chmUnitInfo* topics,
                   struct chmUnitInfo *urlstr,
                   PyObject *dict)
{
  uint32_t stroff, urloff;
  uint64_t i, j, count;
  size_t length;
  int wlc_bit = 7;
  size_t off = 0;
  uint64_t index = 0;
  unsigned char entry[TOPICS_ENTRY_LEN];
  unsigned char combuf[COMMON_BUF_LEN];
  unsigned char *buffer = malloc (wlc_size);
  char *url = NULL;
  char *topic = NULL;

  if (chm_retrieve_object(chmfile, uimain, buffer,
                          wlc_offset, wlc_size) == 0) {
    FREE(buffer);
    return false;
  }

  for (i = 0; i < wlc_count; ++i) {

    if(wlc_bit != 7) {
      ++off;
      wlc_bit = 7;
    }

    index += sr_int(buffer + off, &wlc_bit, ds, dr, &length);
    off += length;

    if(chm_retrieve_object(chmfile, topics, entry,
                           index * 16, TOPICS_ENTRY_LEN) == 0) {
      FREE(topic);
      FREE(url);
      FREE(buffer);
      return false;
    }

    combuf[COMMON_BUF_LEN - 1] = 0;
    stroff = get_uint32 (entry + 4);

    FREE (topic);
    if (chm_retrieve_object (chmfile, uistrings, combuf,
                             stroff, COMMON_BUF_LEN - 1) == 0) {
      topic = strdup ("Untitled in index");

    } else {
      combuf[COMMON_BUF_LEN - 1] = 0;

      topic = strdup ((char *)combuf);
    }

    urloff = get_uint32 (entry + 8);

    if(chm_retrieve_object (chmfile, uitbl, combuf,
                            urloff, 12) == 0) {
      FREE(buffer);
      return false;
    }

    urloff = get_uint32 (combuf + 8);

    if (chm_retrieve_object (chmfile, urlstr, combuf,
                             urloff + 8, COMMON_BUF_LEN - 1) == 0) {
      FREE(topic);
      FREE(url);
      FREE(buffer);
      return false;
    }

    combuf[COMMON_BUF_LEN - 1] = 0;

    FREE (url);
    url = strdup ((char *)combuf);

    if (url && topic) {
#ifdef __PYTHON__
      PyDict_SetItem(dict, 
#if PY_MAJOR_VERSION >= 3
                     PyBytes_FromStringAndSize(topic, strlen(topic)),
                     PyBytes_FromStringAndSize(url, strlen(url))
#else
                     PyString_FromString (topic),
                     PyString_FromString (url)
#endif
      );
#else
      printf ("%s ==> %s\n", url, topic);
#endif
    }

    count = sr_int (buffer + off, &wlc_bit, cs, cr, &length);
    off += length;

    for (j = 0; j < count; ++j) {
      sr_int (buffer + off, &wlc_bit, ls, lr, &length);
      off += length;
    }
  }

  FREE(topic);
  FREE(url);
  FREE(buffer);

  return true;
}

static int
chm_search (struct chmFile *chmfile,
            const char *text, int whole_words,
            int titles_only, PyObject *dict)
{
  unsigned char header[FTS_HEADER_LEN];
  unsigned char doc_index_s;
  unsigned char doc_index_r;
  unsigned char code_count_s;
  unsigned char code_count_r;
  unsigned char loc_codes_s;
  unsigned char loc_codes_r;
  unsigned char word_len, pos;
  unsigned char *buffer;
  char *word = NULL;
  uint32_t node_offset;
  uint32_t node_len;
  uint16_t tree_depth;
  uint32_t i;
  uint16_t free_space;
  uint64_t wlc_count, wlc_size;
  uint32_t wlc_offset;
  char *wrd_buf;
  unsigned char title;
  size_t encsz;
  struct chmUnitInfo ui, uitopics, uiurltbl, uistrings, uiurlstr;
  int partial = false;

  if (NULL == text)
    return -1;

  if (chm_resolve_object (chmfile, "/$FIftiMain", &ui) !=
      CHM_RESOLVE_SUCCESS ||
      chm_resolve_object (chmfile, "/#TOPICS", &uitopics) !=
      CHM_RESOLVE_SUCCESS ||
      chm_resolve_object (chmfile, "/#STRINGS", &uistrings) !=
      CHM_RESOLVE_SUCCESS ||
      chm_resolve_object (chmfile, "/#URLTBL", &uiurltbl) !=
      CHM_RESOLVE_SUCCESS ||
      chm_resolve_object (chmfile, "/#URLSTR", &uiurlstr) !=
      CHM_RESOLVE_SUCCESS)
    return false;

  if(chm_retrieve_object(chmfile, &ui, header, 0, FTS_HEADER_LEN) == 0)
    return false;

  doc_index_s = header[0x1E];
  doc_index_r = header[0x1F];
  code_count_s = header[0x20];
  code_count_r = header[0x21];
  loc_codes_s = header[0x22];
  loc_codes_r = header[0x23];

  if(doc_index_s != 2 || code_count_s != 2 || loc_codes_s != 2) {
    return false;
  }

  node_offset = get_uint32 (header + 0x14);
  node_len = get_uint32 (header + 0x2e);
  tree_depth = get_uint16 (header + 0x18);

  i = sizeof(uint16_t);

  buffer = malloc (node_len);

  node_offset = get_leaf_node_offset (chmfile, text, node_offset, node_len,
                                      tree_depth, &ui);

  if (!node_offset) {
    FREE(buffer);
    return false;
  }

  do {

    if (chm_retrieve_object (chmfile, &ui, buffer,
                             node_offset, node_len) == 0) {
      FREE(word);
      FREE(buffer);
      return false;
    }

    free_space = get_uint16 (buffer + 6);

    i = sizeof(uint32_t) + sizeof(uint16_t) + sizeof(uint16_t);

    encsz = 0;

    while (i < node_len - free_space) {
      word_len = *(buffer + i);
      pos = *(buffer + i + 1);

      wrd_buf = malloc (word_len);
      memcpy (wrd_buf, buffer + i + 2, word_len - 1);
      wrd_buf[word_len - 1] = 0;

      if (pos == 0) {
        FREE(word);
        word = (char *) strdup (wrd_buf);
      } else {
        word = realloc (word, word_len + pos + 1);
        strcpy (word + pos, wrd_buf);
      }

      FREE(wrd_buf);

      i += 2 + word_len;
      title = *(buffer + i - 1);

      wlc_count = be_encint (buffer + i, &encsz);
      i += encsz;

      wlc_offset = get_uint32 (buffer + i);

      i += sizeof(uint32_t) + sizeof(uint16_t);
      wlc_size =  be_encint (buffer + i, &encsz);
      i += encsz;

      node_offset = get_uint32 (buffer);

      if (!title && titles_only)
        continue;

      if (whole_words && !strcasecmp(text, word)) {
        partial = pychm_process_wlc (chmfile, wlc_count, wlc_size,
                                     wlc_offset, doc_index_s,
                                     doc_index_r,code_count_s,
                                     code_count_r, loc_codes_s,
                                     loc_codes_r, &ui, &uiurltbl,
                                     &uistrings, &uitopics,
                                     &uiurlstr, dict);
        FREE(word);
        FREE(buffer);
        return partial;
      }

      if (!whole_words) {
        if (!strncasecmp (word, text, strlen(text))) {
          partial = true;
          pychm_process_wlc (chmfile, wlc_count, wlc_size,
                             wlc_offset, doc_index_s,
                             doc_index_r,code_count_s,
                             code_count_r, loc_codes_s,
                             loc_codes_r, &ui, &uiurltbl,
                             &uistrings, &uitopics,
                             &uiurlstr, dict);

        } else if (strncasecmp (text, word, strlen(text)) < -1)
          break;
      }

    }
  } while (!whole_words &&
           !strncmp (word, text, strlen(text)) &&
           node_offset);

  FREE(word);
  FREE(buffer);

  return partial;
}

typedef struct {
  const char *file;
  int offset;
} Langrec;

static Langrec lang_files[] = {
  {"/$FIftiMain",               0x7E},
  {"$WWKeywordLinks/BTree",     0x34},
  {"$WWAssociativeLinks/BTree", 0x34}
};

#define LANG_FILES_SIZE (sizeof(lang_files)/sizeof(Langrec))

static int
chm_get_lcid (struct chmFile *chmfile) {
  struct chmUnitInfo ui;
  uint32_t lang;
  int i;

  for (i=0; i<LANG_FILES_SIZE; i++) {

    if (chm_resolve_object (chmfile, lang_files[i].file, &ui) ==
        CHM_RESOLVE_SUCCESS) {

      if (chm_retrieve_object (chmfile, &ui, (unsigned char *) &lang,
                               lang_files[i].offset, sizeof(uint32_t)) != 0)
        return lang;
    }
  }

  return -1;
}

#ifdef __PYTHON__

static PyObject *
is_searchable (PyObject *self, PyObject *args) {
  struct chmFile *file;
  PyObject *obj0;
  struct chmUnitInfo ui;

  if (PyArg_ParseTuple (args, "O:is_searchable", &obj0)) {

      file = (struct chmFile *) ((SwigPyObject*)(obj0))->ptr;

    if (chm_resolve_object (file, "/$FIftiMain", &ui) !=
        CHM_RESOLVE_SUCCESS ||
        chm_resolve_object (file, "/#TOPICS", &ui) !=
        CHM_RESOLVE_SUCCESS ||
        chm_resolve_object (file, "/#STRINGS", &ui) !=
        CHM_RESOLVE_SUCCESS ||
        chm_resolve_object (file, "/#URLTBL", &ui) !=
        CHM_RESOLVE_SUCCESS ||
        chm_resolve_object (file, "/#URLSTR", &ui) !=
        CHM_RESOLVE_SUCCESS)
      return Py_BuildValue ("i", 0);
    else
      return Py_BuildValue ("i", 1);
  } else {
    PyErr_SetString(PyExc_TypeError, "Expected chmfile (not CHMFile!)");
    return NULL;
  }
}

static PyObject *
search (PyObject *self, PyObject *args) {
  char *text;
  int whole_words = 0;
  int titles_only = 0;
  int partial;
  struct chmFile *file;
  PyObject *obj0;
  PyObject *dict;

#if PY_MAJOR_VERSION >= 3
  PyObject *obj1;
  if (PyArg_ParseTuple (args, "OSii:search", &obj0, &obj1,
#else
  if (PyArg_ParseTuple (args, "Osii:search", &obj0, &text,
#endif
                        &whole_words, &titles_only)) {
      
#if PY_MAJOR_VERSION >= 3
      text = PyBytes_AsString(obj1);
#endif
    dict = PyDict_New();

    if (dict) {
      file = (struct chmFile *) ((SwigPyObject*)(obj0))->ptr;

      partial = chm_search (file,
                            text, whole_words, titles_only, dict);
      return Py_BuildValue ("(iO)", partial, dict);

    } else {
      PyErr_NoMemory();
      return NULL;
    }
  } else {
    PyErr_SetString(PyExc_TypeError,
                    "Expected chmfile (not CHMFile!), string, int, int");
    return NULL;
  }
}

static PyObject *
get_lcid (PyObject *self, PyObject *args) {
  int code;
  struct chmFile *file;
  PyObject *obj0;

  if (PyArg_ParseTuple (args, "O:get_lcid", &obj0)) {

      file = (struct chmFile *) ((SwigPyObject*)(obj0))->ptr;

      code = chm_get_lcid (file);

      if (code != -1)
        return Py_BuildValue ("i", code);
      else
        Py_INCREF(Py_None);
      return Py_None;
  } else {
    PyErr_SetString(PyExc_TypeError,"Expected a chmfile (not a CHMFile!)");
    return NULL;
  }
}

static PyMethodDef
IndexMethods[] = {
  {"get_lcid", get_lcid, METH_VARARGS,
   "Returns LCID (Locale ID) for archive."},
  {"search", search, METH_VARARGS,
   "Perform Full-Text search."},
  {"is_searchable", is_searchable, METH_VARARGS,
   "Return 1 if it is possible to search the archive, 0 otherwise."},
  {NULL, NULL, 0, NULL}
};


#if PY_MAJOR_VERSION >= 3
static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "extra",
        NULL,
        -1,
        IndexMethods,
        NULL,
        NULL,
        NULL,
        NULL
};

#define INITERROR return NULL

#else /* python < 3 */

#define INITERROR return

#endif /* python 3/2 */


#if PY_MAJOR_VERSION >= 3
PyObject* PyInit_extra(void)
#else
void initextra (void)
#endif
{
    PyObject *module;
#if PY_MAJOR_VERSION >= 3
    module = PyModule_Create(&moduledef);
#else
    module = Py_InitModule ("extra", IndexMethods);
#endif
    if (module == NULL)
        INITERROR;

#if PY_MAJOR_VERSION >= 3
    return module;
#endif
}

#else

int
main (int argc, char **argv) {
  struct chmFile *file;
  char text[255];
  int whole_words, titles_only;
  int partial;

  if (argc == 2) {
    file = chm_open (argv[1]);

    if (file) {
      printf ("\nLCID= %d (%08X)\n", chm_get_lcid(file), chm_get_lcid(file));
      while (1) {
        printf ("\n<whole_words> <titles_only> <string>\n");
        printf ("> ");
        if (scanf ("%d %d %s", &whole_words, &titles_only, text))
          partial = chm_search (file,
                                text, whole_words, titles_only, NULL);
        else
          break;

        printf ("Partial = %d\n", partial);
      }

      chm_close (file);
      return 0;
    }

    return -1;

  } else {
    printf ("\n%s <filename>\n", argv[0]);
    return 0;
  }
}

#endif
