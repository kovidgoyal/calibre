/*
 Copyright (C) 2007, 2010 Canonical Ltd

 This program is free software; you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 2 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program; if not, write to the Free Software
 Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA

 Function equate_lines based on bdiff.c from Mercurial.
   Copyright (C) 2005, 2006 Matt Mackall <mpm@selenic.com>

 Functions unique_lcs/recurse_matches based on _patiencediff_py.py.
   Copyright (C) 2005 Bram Cohen, Copyright (C) 2005, 2006 Canonical Ltd
*/


#include <Python.h>
#include <stdlib.h>
#include <string.h>

/* #include "python-compat.h" Commented out by Kovid as nothing defined in it is needed for this module */


#if defined(__GNUC__)
#   define inline __inline__
#elif defined(_MSC_VER)
#   define inline __inline
#else
#   define inline
#endif


#define MIN(a, b) (((a) > (b)) ? (b) : (a))
#define MAX(a, b) (((a) > (b)) ? (a) : (b))


#define SENTINEL -1


/* malloc returns NULL on some platforms if you try to allocate nothing,
 * causing <https://bugs.launchpad.net/bzr/+bug/511267> and
 * <https://bugs.launchpad.net/bzr/+bug/331095>.  On glibc it passes, but
 * let's make it fail to aid testing. */
static inline void* guarded_malloc(size_t x) { return x ? malloc(x) : NULL; }

enum {
    OP_EQUAL = 0,
    OP_INSERT,
    OP_DELETE,
    OP_REPLACE
};


/* values from this array need to correspont to the order of the enum above */
static char *opcode_names[] = {
    "equal",
    "insert",
    "delete",
    "replace",
};


struct line {
    long hash;         /* hash code of the string/object */
    Py_ssize_t next;   /* next line from the same equivalence class */
    Py_ssize_t equiv;  /* equivalence class */
    PyObject *data;
};


struct bucket {
    Py_ssize_t a_head;  /* first item in `a` from this equivalence class */
    Py_ssize_t a_count;
    Py_ssize_t b_head;  /* first item in `b` from this equivalence class */
    Py_ssize_t b_count;
    Py_ssize_t a_pos;
    Py_ssize_t b_pos;
};


struct hashtable {
    Py_ssize_t last_a_pos;
    Py_ssize_t last_b_pos;
    Py_ssize_t size;
    struct bucket *table;
};

struct matching_line {
    Py_ssize_t a;     /* index of the line in `a` */
    Py_ssize_t b;     /* index of the line in `b` */
};


struct matching_block {
    Py_ssize_t a;     /* index of the first line in `a` */
    Py_ssize_t b;     /* index of the first line in `b` */
    Py_ssize_t len;   /* length of the block */
};


struct matching_blocks {
    struct matching_block *matches;
    Py_ssize_t count;
};


struct opcode {
    int tag;
    Py_ssize_t i1;
    Py_ssize_t i2;
    Py_ssize_t j1;
    Py_ssize_t j2;
};


typedef struct {
    PyObject_HEAD
    Py_ssize_t asize;
    Py_ssize_t bsize;
    struct line *a;
    struct line *b;
    struct hashtable hashtable;
    Py_ssize_t *backpointers;
} PatienceSequenceMatcher;


static inline Py_ssize_t
bisect_left(Py_ssize_t *list, Py_ssize_t item, Py_ssize_t lo, Py_ssize_t hi)
{
    while (lo < hi) {
        Py_ssize_t mid = lo / 2 + hi / 2 + (lo % 2 + hi % 2) / 2;
        if (list[mid] < item)
            lo = mid + 1;
        else
            hi = mid;
    }
    return lo;
}


static inline int
compare_lines(struct line *a, struct line *b)
{
    return ((a->hash != b->hash)
            || PyObject_RichCompareBool(a->data, b->data, Py_NE));
}


static inline int
find_equivalence_class(struct bucket *hashtable, Py_ssize_t hsize,
                       struct line *lines, struct line *ref_lines,
                       Py_ssize_t i)
{
    Py_ssize_t j;
    for (j = lines[i].hash & hsize; hashtable[j].b_head != SENTINEL; j = (j + 1) & hsize) {
        if (!compare_lines(lines + i, ref_lines + hashtable[j].b_head)) {
            break;
        }
    }
    return j;
}


static int
equate_lines(struct hashtable *result,
             struct line *lines_a, struct line *lines_b,
             Py_ssize_t asize, Py_ssize_t bsize)
{
    Py_ssize_t i, j, hsize;
    struct bucket *hashtable;

    /* check for overflow, we need the table to be at least bsize+1 */
    if (bsize == PY_SSIZE_T_MAX) {
        PyErr_SetNone(PyExc_OverflowError);
        return 0;
    }

    /* build a hash table of the next highest power of 2 */
    hsize = 1;
    while (hsize < bsize + 1)
        hsize *= 2;

    /* can't be 0 */
    hashtable = (struct bucket *) guarded_malloc(sizeof(struct bucket) * hsize);
    if (hashtable == NULL) {
        PyErr_NoMemory();
        return 0;
    }

    /* initialise the hashtable */
    for (i = 0; i < hsize; i++) {
        hashtable[i].a_count = 0;
        hashtable[i].b_count = 0;
        hashtable[i].a_head = SENTINEL;
        hashtable[i].b_head = SENTINEL;
    }
    hsize--;

    /* add lines from lines_b to the hash table chains. iterating
       backwards so the matching lines are sorted to the linked list
       by the line number (because we are adding new lines to the
       head of the list) */
    for (i = bsize - 1; i >= 0; i--) {
        /* find the first hashtable entry, which is either empty or contains
           the same line as lines_b[i] */
        j = find_equivalence_class(hashtable, hsize, lines_b, lines_b, i);

        /* set the equivalence class */
        lines_b[i].equiv = j;

        /* add to the head of the equivalence class */
        lines_b[i].next = hashtable[j].b_head;
        hashtable[j].b_head = i;
        hashtable[j].b_count++;
    }

    /* match items from lines_a to their equivalence class in lines_b.
       again, iterating backwards for the right order of the linked lists */
    for (i = asize - 1; i >= 0; i--) {
        /* find the first hash entry, which is either empty or contains
           the same line as lines_a[i] */
        j = find_equivalence_class(hashtable, hsize, lines_a, lines_b, i);

        /* set the equivalence class, even if we are not interested in this
           line, because the values are not pre-filled */
        lines_a[i].equiv = j;

        /* we are not interested in lines which are not also in lines_b */
        if (hashtable[j].b_head == SENTINEL)
            continue;

        /* add to the head of the equivalence class */
        lines_a[i].next = hashtable[j].a_head;
        hashtable[j].a_head = i;
        hashtable[j].a_count++;
    }

    result->last_a_pos = -1;
    result->last_b_pos = -1;
    result->size = hsize + 1;
    result->table = hashtable;

    return 1;
}



/* Finds longest common subsequence of unique lines in a[alo:ahi] and
   b[blo:bhi].
   Parameter backpointers must have allocated memory for at least
   4 * (bhi - blo) ints. */
Py_ssize_t
unique_lcs(struct matching_line *answer,
           struct hashtable *hashtable, Py_ssize_t *backpointers,
           struct line *lines_a, struct line *lines_b,
           Py_ssize_t alo, Py_ssize_t blo, Py_ssize_t ahi, Py_ssize_t bhi)
{
    Py_ssize_t i, k, equiv, apos, bpos, norm_apos, norm_bpos, bsize, stacksize;
    Py_ssize_t *stacks, *lasts, *btoa;
    struct bucket *h;

    k = 0;
    stacksize = 0;
    bsize = bhi - blo;
    h = hashtable->table;

    /* "unpack" the allocated memory */
    stacks = backpointers + bsize;
    lasts = stacks + bsize;
    btoa = lasts + bsize;

    /* initialise the backpointers */
    for (i = 0; i < bsize; i++)
        backpointers[i] = SENTINEL;

    if (hashtable->last_a_pos == -1 || hashtable->last_a_pos > alo)
        for (i = 0; i < hashtable->size; i++)
            h[i].a_pos = h[i].a_head;
    hashtable->last_a_pos = alo;

    if (hashtable->last_b_pos == -1 || hashtable->last_b_pos > blo)
        for (i = 0; i < hashtable->size; i++)
            h[i].b_pos = h[i].b_head;
    hashtable->last_b_pos = blo;

    for (bpos = blo; bpos < bhi; bpos++) {
        equiv = lines_b[bpos].equiv;

        /* no lines in a or b  */
        if (h[equiv].a_count == 0 || h[equiv].b_count == 0)
            continue;

        /* find an unique line in lines_a that matches lines_b[bpos]
           if we find more than one line within the range alo:ahi,
           jump to the next line from lines_b immediately */
        apos = SENTINEL;
        /* loop through all lines in the linked list */
        for (i = h[equiv].a_pos; i != SENTINEL; i = lines_a[i].next) {
            /* the index is lower than alo, continue to the next line */
            if (i < alo) {
                h[equiv].a_pos = i;
                continue;
            }
            /* the index is higher than ahi, stop searching */
            if (i >= ahi)
                break;
            /* if the line is within our range, check if it's a duplicate */
            if (apos != SENTINEL)
                goto nextb;
            /* save index to the line */
            apos = i;
        }
        /* this line has no equivalent in lines_a[alo:ahi] */
        if (apos == SENTINEL)
            goto nextb;

        /* check for duplicates of this line in lines_b[blo:bhi] */
        /* loop through all lines in the linked list */
        for (i = h[equiv].b_pos; i != SENTINEL; i = lines_b[i].next) {
            /* the index is lower than blo, continue to the next line */
            if (i < blo) {
                h[equiv].b_pos = i;
                continue;
            }
            /* the index is higher than bhi, stop searching */
            if (i >= bhi)
                break;
            /* if this isn't the line with started with and it's within
               our range, it's a duplicate */
            if (i != bpos)
                goto nextb;
        }

        /* use normalised indexes ([0,ahi-alo) instead of [alo,ahi))
           for the patience sorting algorithm */
        norm_bpos = bpos - blo;
        norm_apos = apos - alo;
        btoa[norm_bpos] = norm_apos;

        /*
        Ok, how does this work...

        We have a list of matching lines from two lists, a and b. These
        matches are stored in variable `btoa`. As we are iterating over this
        table by bpos, the lines from b already form an increasing sequence.
        We need to "sort" also the lines from a using the patience sorting
        algorithm, ignoring the lines which would need to be swapped.

          http://en.wikipedia.org/wiki/Patience_sorting

        For each pair of lines, we need to place the line from a on either
        an existing pile that has higher value on the top or create a new
        pile. Variable `stacks` represents the tops of these piles and in
        variable `lasts` we store the lines from b, that correspond to the
        lines from a in `stacks`.

        Whenever we place a new line on top of a pile, we store a
        backpointer to the line (b) from top of the previous pile. This means
        that after the loop, variable `backpointers` will contain an index
        to the previous matching lines that forms an increasing sequence
        (over both indexes a and b) with the current matching lines. If
        either index a or b of the previous matching lines would be higher
        than indexes of the current one or if the indexes of the current
        one are 0, it will contain SENTINEL.

        To construct the LCS, we will just need to follow these backpointers
        from the top of the last pile and stop when we reach SENTINEL.
        */

        /* as an optimization, check if the next line comes at the end,
           because it usually does */
        if (stacksize && stacks[stacksize - 1] < norm_apos)
            k = stacksize;
        /* as an optimization, check if the next line comes right after
           the previous line, because usually it does */
        else if (stacksize && (stacks[k] < norm_apos) &&
                 (k == stacksize - 1 || stacks[k + 1] > norm_apos))
            k += 1;
        else
            k = bisect_left(stacks, norm_apos, 0, stacksize);

        if (k > 0)
            backpointers[norm_bpos] = lasts[k - 1];

        if (k < stacksize) {
            stacks[k] = norm_apos;
            lasts[k] = norm_bpos;
        }
        else {
            stacks[stacksize] = norm_apos;
            lasts[stacksize] = norm_bpos;
            stacksize += 1;
        }


nextb:
        ;
    }

    if (stacksize == 0)
        return 0;

    /* backtrace the structures to find the LCS */
    i = 0;
    k = lasts[stacksize - 1];
    while (k != SENTINEL) {
        answer[i].a = btoa[k];
        answer[i].b = k;
        k = backpointers[k];
        i++;
    }

    return i;
}

/* Adds a new line to the list of matching blocks, either extending the
   current block or adding a new one. */
static inline void
add_matching_line(struct matching_blocks *answer, Py_ssize_t a, Py_ssize_t b)
{
    Py_ssize_t last_index = answer->count - 1;
    if ((last_index >= 0) &&
        (a == answer->matches[last_index].a +
              answer->matches[last_index].len) &&
        (b == answer->matches[last_index].b +
              answer->matches[last_index].len)) {
        /* enlarge the last block */
        answer->matches[last_index].len++;
    }
    else {
        /* create a new block */
        last_index++;
        answer->matches[last_index].a = a;
        answer->matches[last_index].b = b;
        answer->matches[last_index].len = 1;
        answer->count++;
    }
}


static int
recurse_matches(struct matching_blocks *answer, struct hashtable *hashtable,
                Py_ssize_t *backpointers, struct line *a, struct line *b,
                Py_ssize_t alo, Py_ssize_t blo, Py_ssize_t ahi, Py_ssize_t bhi,
                int maxrecursion)
{
    int res;
    Py_ssize_t new, last_a_pos, last_b_pos, lcs_size, nahi, nbhi, i, apos, bpos;
    struct matching_line *lcs;

    if (maxrecursion < 0)
        return 1;

    if (alo == ahi || blo == bhi)
        return 1;

    new = 0;
    last_a_pos = alo - 1;
    last_b_pos = blo - 1;

    lcs = (struct matching_line *)guarded_malloc(sizeof(struct matching_line) * (bhi - blo));
    if (lcs == NULL)
        return 0;

    lcs_size = unique_lcs(lcs, hashtable, backpointers, a, b, alo, blo, ahi, bhi);

    /* recurse between lines which are unique in each file and match */
    for (i = lcs_size - 1; i >= 0; i--) {
        apos = alo + lcs[i].a;
        bpos = blo + lcs[i].b;
        if (last_a_pos + 1 != apos || last_b_pos + 1 != bpos) {
            res = recurse_matches(answer, hashtable,
                                  backpointers, a, b,
                                  last_a_pos + 1, last_b_pos + 1,
                                  apos, bpos, maxrecursion - 1);
            if (!res)
                goto error;
        }
        last_a_pos = apos;
        last_b_pos = bpos;
        add_matching_line(answer, apos, bpos);
        new = 1;
    }

    free(lcs);
    lcs = NULL;

    /* find matches between the last match and the end */
    if (new > 0) {
        res = recurse_matches(answer, hashtable,
                              backpointers, a, b,
                              last_a_pos + 1, last_b_pos + 1,
                              ahi, bhi, maxrecursion - 1);
        if (!res)
            goto error;
    }


    /* find matching lines at the very beginning */
    else if (a[alo].equiv == b[blo].equiv) {
        while (alo < ahi && blo < bhi && a[alo].equiv == b[blo].equiv)
            add_matching_line(answer, alo++, blo++);
        res = recurse_matches(answer, hashtable,
                              backpointers, a, b,
                              alo, blo, ahi, bhi, maxrecursion - 1);
        if (!res)
            goto error;
    }

    /* find matching lines at the very end */
    else if (a[ahi - 1].equiv == b[bhi - 1].equiv) {
        nahi = ahi - 1;
        nbhi = bhi - 1;
        while (nahi > alo && nbhi > blo && a[nahi - 1].equiv == b[nbhi - 1].equiv) {
            nahi--;
            nbhi--;
        }
        res = recurse_matches(answer, hashtable,
                              backpointers, a, b,
                              last_a_pos + 1, last_b_pos + 1,
                              nahi, nbhi, maxrecursion - 1);
        if (!res)
            goto error;
        for (i = 0; i < ahi - nahi; i++)
            add_matching_line(answer, nahi + i, nbhi + i);
    }

    return 1;

error:
    free(lcs);
    return 0;
}


static void
delete_lines(struct line *lines, Py_ssize_t size)
{
    struct line *line = lines;
    while (size-- > 0) {
        Py_XDECREF(line->data);
        line++;
    }
    free(lines);
}


static Py_ssize_t
load_lines(PyObject *orig, struct line **lines)
{
    Py_ssize_t size, i;
    struct line *line;
    PyObject *seq, *item;

    seq = PySequence_Fast(orig, "sequence expected");
    if (seq == NULL) {
        return -1;
    }

    size = PySequence_Fast_GET_SIZE(seq);
    if (size == 0) {
        Py_DECREF(seq);
        return 0;
    }

    /* Allocate a memory block for line data, initialized to 0 */
    line = *lines = (struct line *)calloc(size, sizeof(struct line));
    if (line == NULL) {
        PyErr_NoMemory();
        Py_DECREF(seq);
        return -1;
    }

    for (i = 0; i < size; i++) {
        item = PySequence_Fast_GET_ITEM(seq, i);
        Py_INCREF(item);
        line->data = item;
        line->hash = PyObject_Hash(item);
        if (line->hash == (-1)) {
            /* Propogate the hash exception */
            size = -1;
            goto cleanup;
        }
        line->next = SENTINEL;
        line++;
    }

    cleanup:
    Py_DECREF(seq);
    if (size == -1) {
        /* Error -- cleanup unused object references */
        delete_lines(*lines, i);
        *lines = NULL;
    }
    return size;
}


static PyObject *
py_unique_lcs(PyObject *self, PyObject *args)
{
    PyObject *aseq, *bseq, *res, *item;
    Py_ssize_t asize, bsize, i, nmatches, *backpointers = NULL;
    struct line *a = NULL, *b = NULL;
    struct matching_line *matches = NULL;
    struct hashtable hashtable;

    if (!PyArg_ParseTuple(args, "OO", &aseq, &bseq))
        return NULL;

    hashtable.table = NULL;

    asize = load_lines(aseq, &a);
    bsize = load_lines(bseq, &b);
    if (asize == -1 || bsize == -1)
        goto error;

    if (!equate_lines(&hashtable, a, b, asize, bsize))
        goto error;

    if (bsize > 0) {
        matches = (struct matching_line *)guarded_malloc(sizeof(struct matching_line) * bsize);
        if (matches == NULL)
            goto error;

        backpointers = (Py_ssize_t *)guarded_malloc(sizeof(Py_ssize_t) * bsize * 4);
        if (backpointers == NULL)
            goto error;
    }

    nmatches = unique_lcs(matches, &hashtable, backpointers, a, b, 0, 0, asize, bsize);

    res = PyList_New(nmatches);
    for (i = 0; i < nmatches; i++) {
#if PY_VERSION_HEX < 0x02050000
        item = Py_BuildValue("ii", matches[nmatches - i - 1].a, matches[nmatches - i - 1].b);
#else
        item = Py_BuildValue("nn", matches[nmatches - i - 1].a, matches[nmatches - i - 1].b);
#endif
        if (item == NULL)
            goto error;
        if (PyList_SetItem(res, i, item) != 0)
            goto error;
    }

    free(backpointers);
    free(matches);
    free(hashtable.table);
    delete_lines(b, bsize);
    delete_lines(a, asize);
    return res;

error:
    free(backpointers);
    free(matches);
    free(hashtable.table);
    delete_lines(b, bsize);
    delete_lines(a, asize);
    return NULL;
}


static PyObject *
py_recurse_matches(PyObject *self, PyObject *args)
{
    PyObject *aseq, *bseq, *item, *answer;
    int maxrecursion, res;
    Py_ssize_t i, j, asize, bsize, alo, blo, ahi, bhi;
    Py_ssize_t *backpointers = NULL;
    struct line *a = NULL, *b = NULL;
    struct hashtable hashtable;
    struct matching_blocks matches;

#if PY_VERSION_HEX < 0x02050000
    if (!PyArg_ParseTuple(args, "OOiiiiOi", &aseq, &bseq, &alo, &blo,
                          &ahi, &bhi, &answer, &maxrecursion))
#else
    if (!PyArg_ParseTuple(args, "OOnnnnOi", &aseq, &bseq, &alo, &blo,
                          &ahi, &bhi, &answer, &maxrecursion))
#endif
        return NULL;

    hashtable.table = NULL;
    matches.matches = NULL;

    asize = load_lines(aseq, &a);
    bsize = load_lines(bseq, &b);
    if (asize == -1 || bsize == -1)
        goto error;

    if (!equate_lines(&hashtable, a, b, asize, bsize))
        goto error;

    matches.count = 0;

    if (bsize > 0) {
        matches.matches = (struct matching_block *)guarded_malloc(sizeof(struct matching_block) * bsize);
        if (matches.matches == NULL)
            goto error;

        backpointers = (Py_ssize_t *)guarded_malloc(sizeof(Py_ssize_t) * bsize * 4);
        if (backpointers == NULL)
            goto error;
    } else {
        matches.matches = NULL;
        backpointers = NULL;
    }

    res = recurse_matches(&matches, &hashtable, backpointers,
                          a, b, alo, blo, ahi, bhi, maxrecursion);
    if (!res)
        goto error;

    for (i = 0; i < matches.count; i++) {
        for (j = 0; j < matches.matches[i].len; j++) {
#if PY_VERSION_HEX < 0x02050000
            item = Py_BuildValue("ii", matches.matches[i].a + j,
                                 matches.matches[i].b + j);
#else
            item = Py_BuildValue("nn", matches.matches[i].a + j,
                                 matches.matches[i].b + j);
#endif
            if (item == NULL)
                goto error;
            if (PyList_Append(answer, item) != 0)
                goto error;
        }
    }

    free(backpointers);
    free(matches.matches);
    free(hashtable.table);
    delete_lines(b, bsize);
    delete_lines(a, asize);
    Py_RETURN_NONE;

error:
    free(backpointers);
    free(matches.matches);
    free(hashtable.table);
    delete_lines(b, bsize);
    delete_lines(a, asize);
    return NULL;
}


static PyObject *
PatienceSequenceMatcher_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PyObject *junk, *a, *b;
    PatienceSequenceMatcher *self;

    self = (PatienceSequenceMatcher *)type->tp_alloc(type, 0);
    if (self != NULL) {

        if (!PyArg_ParseTuple(args, "OOO", &junk, &a, &b)) {
            Py_DECREF(self);
            return NULL;
        }

        self->asize = load_lines(a, &(self->a));
        self->bsize = load_lines(b, &(self->b));

        if (self->asize == -1 || self->bsize == -1) {
            Py_DECREF(self);
            return NULL;
        }

        if (!equate_lines(&self->hashtable, self->a, self->b, self->asize, self->bsize)) {
            Py_DECREF(self);
            return NULL;
        }

        if (self->bsize > 0) {
            self->backpointers = (Py_ssize_t *)guarded_malloc(sizeof(Py_ssize_t) * self->bsize * 4);
            if (self->backpointers == NULL) {
                Py_DECREF(self);
                PyErr_NoMemory();
                return NULL;
            }
        } else {
            self->backpointers = NULL;
        }

    }

    return (PyObject *)self;
}


static void
PatienceSequenceMatcher_dealloc(PatienceSequenceMatcher* self)
{
    free(self->backpointers);
    free(self->hashtable.table);
    delete_lines(self->b, self->bsize);
    delete_lines(self->a, self->asize);
    Py_TYPE(self)->tp_free((PyObject *)self);
}


static char PatienceSequenceMatcher_get_matching_blocks_doc[] =
    "Return list of triples describing matching subsequences.\n"
    "\n"
    "Each triple is of the form (i, j, n), and means that\n"
    "a[i:i+n] == b[j:j+n].  The triples are monotonically increasing in\n"
    "i and in j.\n"
    "\n"
    "The last triple is a dummy, (len(a), len(b), 0), and is the only\n"
    "triple with n==0.\n"
    "\n"
    ">>> s = PatienceSequenceMatcher(None, \"abxcd\", \"abcd\")\n"
    ">>> s.get_matching_blocks()\n"
    "[(0, 0, 2), (3, 2, 2), (5, 4, 0)]\n";

static PyObject *
PatienceSequenceMatcher_get_matching_blocks(PatienceSequenceMatcher* self)
{
    PyObject *answer, *item;
    int res;
    Py_ssize_t i;
    struct matching_blocks matches;

    matches.count = 0;
    if (self->bsize > 0) {
        matches.matches = (struct matching_block *)
            guarded_malloc(sizeof(struct matching_block) * self->bsize);
        if (matches.matches == NULL)
            return PyErr_NoMemory();
    } else
        matches.matches = NULL;

    res = recurse_matches(&matches, &self->hashtable, self->backpointers,
                          self->a, self->b, 0, 0,
                          self->asize, self->bsize, 10);
    if (!res) {
        free(matches.matches);
        return PyErr_NoMemory();
    }

    answer = PyList_New(matches.count + 1);
    if (answer == NULL) {
        free(matches.matches);
        return NULL;
    }

    for (i = 0; i < matches.count; i++) {
#if PY_VERSION_HEX < 0x02050000
        item = Py_BuildValue("iii", matches.matches[i].a,
                             matches.matches[i].b, matches.matches[i].len);
#else
        item = Py_BuildValue("nnn", matches.matches[i].a,
                             matches.matches[i].b, matches.matches[i].len);
#endif
        if (item == NULL)
            goto error;
        if (PyList_SetItem(answer, i, item) != 0)
            goto error;
    }
#if PY_VERSION_HEX < 0x02050000
    item = Py_BuildValue("iii", self->asize, self->bsize, 0);
#else
    item = Py_BuildValue("nnn", self->asize, self->bsize, 0);
#endif
    if (item == NULL)
        goto error;
    if (PyList_SetItem(answer, i, item) != 0)
        goto error;

    free(matches.matches);
    return answer;

error:
    free(matches.matches);
    Py_DECREF(answer);
    return NULL;
}


static char PatienceSequenceMatcher_get_opcodes_doc[] =
    "Return list of 5-tuples describing how to turn a into b.\n"
    "\n"
    "Each tuple is of the form (tag, i1, i2, j1, j2).  The first tuple\n"
    "has i1 == j1 == 0, and remaining tuples have i1 == the i2 from the\n"
    "tuple preceding it, and likewise for j1 == the previous j2.\n"
    "\n"
    "The tags are strings, with these meanings:\n"
    "\n"
    "'replace':  a[i1:i2] should be replaced by b[j1:j2]\n"
    "'delete':   a[i1:i2] should be deleted.\n"
    "               Note that j1==j2 in this case.\n"
    "'insert':   b[j1:j2] should be inserted at a[i1:i1].\n"
    "               Note that i1==i2 in this case.\n"
    "'equal':    a[i1:i2] == b[j1:j2]\n"
    "\n"
    ">>> a = \"qabxcd\"\n"
    ">>> b = \"abycdf\"\n"
    ">>> s = PatienceSequenceMatcher(None, a, b)\n"
    ">>> for tag, i1, i2, j1, j2 in s.get_opcodes():\n"
    "...    print (\"%7s a[%d:%d] (%s) b[%d:%d] (%s)\" %\n"
    "...           (tag, i1, i2, a[i1:i2], j1, j2, b[j1:j2]))\n"
    " delete a[0:1] (q) b[0:0] ()\n"
    "  equal a[1:3] (ab) b[0:2] (ab)\n"
    "replace a[3:4] (x) b[2:3] (y)\n"
    "  equal a[4:6] (cd) b[3:5] (cd)\n"
    " insert a[6:6] () b[5:6] (f)\n";

static PyObject *
PatienceSequenceMatcher_get_opcodes(PatienceSequenceMatcher* self)
{
    PyObject *answer, *item;
    Py_ssize_t i, j, k, ai, bj;
    int tag, res;
    struct matching_blocks matches;

    matches.count = 0;
    matches.matches = (struct matching_block *)guarded_malloc(sizeof(struct matching_block) * (self->bsize + 1));
    if (matches.matches == NULL)
        return PyErr_NoMemory();

    res = recurse_matches(&matches, &self->hashtable, self->backpointers,
                          self->a, self->b, 0, 0,
                          self->asize, self->bsize, 10);
    if (!res) {
        free(matches.matches);
        return PyErr_NoMemory();
    }

    matches.matches[matches.count].a = self->asize;
    matches.matches[matches.count].b = self->bsize;
    matches.matches[matches.count].len = 0;
    matches.count++;

    answer = PyList_New(0);
    if (answer == NULL) {
        free(matches.matches);
        return NULL;
    }

    i = j = 0;
    for (k = 0; k < matches.count; k++) {
        ai = matches.matches[k].a;
        bj = matches.matches[k].b;

        tag = -1;
        if (i < ai && j < bj)
            tag = OP_REPLACE;
        else if (i < ai)
            tag = OP_DELETE;
        else if (j < bj)
            tag = OP_INSERT;

        if (tag != -1) {
#if PY_VERSION_HEX < 0x02050000
            item = Py_BuildValue("siiii", opcode_names[tag], i, ai, j, bj);
#else
            item = Py_BuildValue("snnnn", opcode_names[tag], i, ai, j, bj);
#endif
            if (item == NULL)
                goto error;
            if (PyList_Append(answer, item) != 0)
                goto error;
        }

        i = ai + matches.matches[k].len;
        j = bj + matches.matches[k].len;

        if (matches.matches[k].len > 0) {
#if PY_VERSION_HEX < 0x02050000
            item = Py_BuildValue("siiii", opcode_names[OP_EQUAL], ai, i, bj, j);
#else
            item = Py_BuildValue("snnnn", opcode_names[OP_EQUAL], ai, i, bj, j);
#endif
            if (item == NULL)
                goto error;
            if (PyList_Append(answer, item) != 0)
                goto error;
        }
    }

    free(matches.matches);
    return answer;

error:
    free(matches.matches);
    Py_DECREF(answer);
    return NULL;
}


static char PatienceSequenceMatcher_get_grouped_opcodes_doc[] =
    "Isolate change clusters by eliminating ranges with no changes.\n"
    "\n"
    "Return a list of groups with up to n lines of context.\n"
    "Each group is in the same format as returned by get_opcodes().\n"
    "\n"
    ">>> from pprint import pprint\n"
    ">>> a = map(str, range(1,40))\n"
    ">>> b = a[:]\n"
    ">>> b[8:8] = ['i']     # Make an insertion\n"
    ">>> b[20] += 'x'       # Make a replacement\n"
    ">>> b[23:28] = []      # Make a deletion\n"
    ">>> b[30] += 'y'       # Make another replacement\n"
    ">>> pprint(PatienceSequenceMatcher(None,a,b).get_grouped_opcodes())\n"
    "[[('equal', 5, 8, 5, 8), ('insert', 8, 8, 8, 9), ('equal', 8, 11, 9, 12)],\n"
    " [('equal', 16, 19, 17, 20),\n"
    "  ('replace', 19, 20, 20, 21),\n"
    "  ('equal', 20, 22, 21, 23),\n"
    "  ('delete', 22, 27, 23, 23),\n"
    "  ('equal', 27, 30, 23, 26)],\n"
    " [('equal', 31, 34, 27, 30),\n"
    "  ('replace', 34, 35, 30, 31),\n"
    "  ('equal', 35, 38, 31, 34)]]\n";

static PyObject *
PatienceSequenceMatcher_get_grouped_opcodes(PatienceSequenceMatcher* self,
                                            PyObject *args)
{
    PyObject *answer, *group, *item;
    Py_ssize_t i, j, k, ai, bj, size, ncodes, tag;
    Py_ssize_t i1, i2, j1, j2;
    int n = 3, nn, res;
    struct matching_blocks matches;
    struct opcode *codes;

    if (!PyArg_ParseTuple(args, "|i", &n))
        return NULL;

    matches.count = 0;
    matches.matches = (struct matching_block *)guarded_malloc(sizeof(struct matching_block) * (self->bsize + 1));
    if (matches.matches == NULL)
        return PyErr_NoMemory();

    res = recurse_matches(&matches, &self->hashtable, self->backpointers,
                          self->a, self->b, 0, 0,
                          self->asize, self->bsize, 10);
    if (!res) {
        free(matches.matches);
        return PyErr_NoMemory();
    }

    matches.matches[matches.count].a = self->asize;
    matches.matches[matches.count].b = self->bsize;
    matches.matches[matches.count].len = 0;
    matches.count++;

    ncodes = 0;
    codes = (struct opcode *)guarded_malloc(sizeof(struct opcode) * matches.count * 2);
    if (codes == NULL) {
        free(matches.matches);
        return PyErr_NoMemory();
    }

    i = j = 0;
    for (k = 0; k < matches.count; k++) {
        ai = matches.matches[k].a;
        bj = matches.matches[k].b;

        tag = -1;
        if (i < ai && j < bj)
            tag = OP_REPLACE;
        else if (i < ai)
            tag = OP_DELETE;
        else if (j < bj)
            tag = OP_INSERT;

        if (tag != -1) {
            codes[ncodes].tag = tag;
            codes[ncodes].i1 = i;
            codes[ncodes].i2 = ai;
            codes[ncodes].j1 = j;
            codes[ncodes].j2 = bj;
            ncodes++;
        }

        i = ai + matches.matches[k].len;
        j = bj + matches.matches[k].len;

        if (matches.matches[k].len > 0) {
            codes[ncodes].tag = OP_EQUAL;
            codes[ncodes].i1 = ai;
            codes[ncodes].i2 = i;
            codes[ncodes].j1 = bj;
            codes[ncodes].j2 = j;
            ncodes++;
        }
    }

    if (ncodes == 0) {
        codes[ncodes].tag = OP_EQUAL;
        codes[ncodes].i1 = 0;
        codes[ncodes].i2 = 1;
        codes[ncodes].j1 = 0;
        codes[ncodes].j2 = 1;
        ncodes++;
    }

    /* fixup leading and trailing groups if they show no changes. */
    if (codes[0].tag == OP_EQUAL) {
        codes[0].i1 = MAX(codes[0].i1, codes[0].i2 - n);
        codes[0].j1 = MAX(codes[0].j1, codes[0].j2 - n);
    }
    if (codes[ncodes - 1].tag == OP_EQUAL) {
        codes[ncodes - 1].i2 = MIN(codes[ncodes - 1].i2,
                                   codes[ncodes - 1].i1 + n);
        codes[ncodes - 1].j2 = MIN(codes[ncodes - 1].j2,
                                   codes[ncodes - 1].j1 + n);
    }

    group = NULL;

    answer = PyList_New(0);
    if (answer == NULL)
        goto error;

    group = PyList_New(0);
    if (group == NULL)
        goto error;

    nn = n + n;
    tag = -1;
    for (i = 0; i < ncodes; i++) {
        tag = codes[i].tag;
        i1 = codes[i].i1;
        i2 = codes[i].i2;
        j1 = codes[i].j1;
        j2 = codes[i].j2;
        /* end the current group and start a new one whenever
           there is a large range with no changes. */
        if (tag == OP_EQUAL && i2 - i1 > nn) {
#if PY_VERSION_HEX < 0x02050000
            item = Py_BuildValue("siiii", opcode_names[tag],
                                  i1, MIN(i2, i1 + n), j1, MIN(j2, j1 + n));
#else
            item = Py_BuildValue("snnnn", opcode_names[tag],
                                  i1, MIN(i2, i1 + n), j1, MIN(j2, j1 + n));
#endif
            if (item == NULL)
                goto error;
            if (PyList_Append(group, item) != 0)
                goto error;
            if (PyList_Append(answer, group) != 0)
                goto error;
            group = PyList_New(0);
            if (group == NULL)
                goto error;
            i1 = MAX(i1, i2 - n);
            j1 = MAX(j1, j2 - n);
        }
#if PY_VERSION_HEX < 0x02050000
        item = Py_BuildValue("siiii", opcode_names[tag], i1, i2, j1 ,j2);
#else
        item = Py_BuildValue("snnnn", opcode_names[tag], i1, i2, j1 ,j2);
#endif
        if (item == NULL)
            goto error;
        if (PyList_Append(group, item) != 0)
            goto error;
    }
    size = PyList_Size(group);
    if (size > 0 && !(size == 1 && tag == OP_EQUAL)) {
        if (PyList_Append(answer, group) != 0)
            goto error;
    }
    else
        Py_DECREF(group);

    free(codes);
    free(matches.matches);
    return answer;

error:
    free(codes);
    free(matches.matches);
    Py_DECREF(group);
    Py_DECREF(answer);
    return NULL;
}


static PyMethodDef PatienceSequenceMatcher_methods[] = {
    {"get_matching_blocks",
     (PyCFunction)PatienceSequenceMatcher_get_matching_blocks,
     METH_NOARGS,
     PatienceSequenceMatcher_get_matching_blocks_doc},
    {"get_opcodes",
     (PyCFunction)PatienceSequenceMatcher_get_opcodes,
     METH_NOARGS,
     PatienceSequenceMatcher_get_opcodes_doc},
    {"get_grouped_opcodes",
     (PyCFunction)PatienceSequenceMatcher_get_grouped_opcodes,
     METH_VARARGS,
     PatienceSequenceMatcher_get_grouped_opcodes_doc},
    {NULL}
};


static char PatienceSequenceMatcher_doc[] =
    "C implementation of PatienceSequenceMatcher";


static PyTypeObject PatienceSequenceMatcherType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    /* tp_name           */ "PatienceSequenceMatcher",
    /* tp_basicsize      */ sizeof(PatienceSequenceMatcher),
    /* tp_itemsize       */ 0,
    /* tp_dealloc        */ (destructor)PatienceSequenceMatcher_dealloc,
    /* tp_print          */ 0,
    /* tp_getattr        */ 0,
    /* tp_setattr        */ 0,
    /* tp_compare        */ 0,
    /* tp_repr           */ 0,
    /* tp_as_number      */ 0,
    /* tp_as_sequence    */ 0,
    /* tp_as_mapping     */ 0,
    /* tp_hash           */ 0,
    /* tp_call           */ 0,
    /* tp_str            */ 0,
    /* tp_getattro       */ 0,
    /* tp_setattro       */ 0,
    /* tp_as_buffer      */ 0,
    /* tp_flags          */ Py_TPFLAGS_DEFAULT,
    /* tp_doc            */ PatienceSequenceMatcher_doc,
    /* tp_traverse       */ 0,
    /* tp_clear          */ 0,
    /* tp_richcompare    */ 0,
    /* tp_weaklistoffset */ 0,
    /* tp_iter           */ 0,
    /* tp_iternext       */ 0,
    /* tp_methods        */ PatienceSequenceMatcher_methods,
    /* tp_members        */ 0,
    /* tp_getset         */ 0,
    /* tp_base           */ 0,
    /* tp_dict           */ 0,
    /* tp_descr_get      */ 0,
    /* tp_descr_set      */ 0,
    /* tp_dictoffset     */ 0,
    /* tp_init           */ 0,
    /* tp_alloc          */ 0,
    /* tp_new            */ PatienceSequenceMatcher_new,
};

static PyMethodDef _patiencediff_c_methods[] = {
    {"unique_lcs_c", py_unique_lcs, METH_VARARGS},
    {"recurse_matches_c", py_recurse_matches, METH_VARARGS},
    {NULL, NULL, 0, NULL}
};

static int
exec_module(PyObject *mod) {
    if (PyType_Ready(&PatienceSequenceMatcherType) < 0)
        return -1;
    Py_INCREF(&PatienceSequenceMatcherType);
    PyModule_AddObject(mod, "PatienceSequenceMatcher_c",
                       (PyObject *)&PatienceSequenceMatcherType);
    return 0;

}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {
    .m_base     = PyModuleDef_HEAD_INIT,
    .m_name     = "_patiencediff_c",
    .m_doc      = "C implementation of PatienceSequenceMatcher.",
    .m_methods  = _patiencediff_c_methods,
    .m_slots    = slots,
};

CALIBRE_MODINIT_FUNC PyInit__patiencediff_c(void) { return PyModuleDef_Init(&module_def); }
