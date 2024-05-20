/*
 * quantize.cpp
 * Copyright (C) 2016 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * octree based image quantization.
 * See https://www.microsoft.com/msj/archive/S3F1.aspx for a simple to follow
 * writeup on this algorithm
 *
 * The implementation below is more sophisticated than the writeup. In particular, it tracks
 * total error on each leaf node and uses a memory pool to improve performance.
 *
 * Distributed under terms of the GPL3 license.
 */

#include "imageops.h"
#include <stdexcept>
#include <cmath>
#include <stdio.h>
#include <QVector>
#include <QStringList>

// Increasing this number improves quality but also increases running time and memory consumption
static const size_t MAX_LEAVES = 2000;

#if defined _MSC_VER && _MSC_VER < 1700
typedef unsigned __int64 uint64_t;
typedef __int64 int64_t;
#define UINT64_MAX _UI64_MAX
static inline double log2(double x) { return log(x) / log((double)2) ; }
#else
#include <stdint.h>
#ifndef UINT64_MAX
#define UINT64_MAX 18446744073709551615ULL
#endif
#endif
#define MAX_DEPTH 8
#define MAX_COLORS 256
#define MAX(x, y) ((x) > (y)) ? (x) : (y)
#define MIN(x, y) ((x) < (y)) ? (x) : (y)
static const unsigned char BIT_MASK[8] = { 1 << 7, 1 << 6, 1 << 5, 1 << 4, 1 << 3, 1 << 2, 1 << 1, 1 };
static inline unsigned char get_index(const unsigned char r, const unsigned char g, const unsigned char b, const size_t level) {
    return ((((r & BIT_MASK[level]) >> (7 - level)) << 2) | (((g & BIT_MASK[level]) >> (7 - level)) << 1) | ((b & BIT_MASK[level]) >> (7 - level)));
}
template <typename T> static inline T euclidean_distance(T r1, T g1, T b1, T r2, T g2, T b2) {
    return (r1 * r1) + (r2 * r2) + (g1 * g1) + (g2 * g2) + (b1 * b1) + (b2 * b2) - 2 * (r1 * r2 + g1 * g2 + b1 * b2);
}
struct SumPixel { uint64_t red; uint64_t green; uint64_t blue; };
struct DoublePixel { double red; double green; double blue; };
template <typename T> static inline void iadd(T &self, T &other) { self.red += other.red; self.green += other.green; self.blue += other.blue; }

template <class T> class Pool {  // {{{
private:
    QVector<T> nodes;
    T *first_available;

public:
    Pool(int size) : nodes(size), first_available(nodes.data()) {
        for (int i = 0; i < size - 1; i++) this->nodes[i].next_available_in_pool = &this->nodes[i+1];
    }

    T* checkout() {
        T *ans = this->first_available;
        if (ans == NULL) throw std::out_of_range("Something bad happened: ran out of nodes in the pool");
        this->first_available = ans->next_available_in_pool;
        if (this->first_available == NULL) throw std::out_of_range("Memory Pool is exhausted, this should never happen");
        return ans;
    }

    void relinquish(T *node) {
        node->reset();
        node->next_available_in_pool = this->first_available;
        this->first_available = node;
    }
}; // }}}

class Node {
    friend class Pool<Node>;
private:
    bool is_leaf;
    unsigned char index;
    uint64_t pixel_count;
    SumPixel sum;
    DoublePixel avg;
    SumPixel error_sum;
    Node *next_reducible_node;
    Node *next_available_in_pool;
    Node *children[MAX_DEPTH];

public:
#ifdef _MSC_VER
// Disable the new behavior warning caused by children() below
#pragma warning( push )
#pragma warning (disable: 4351)
    Node() : is_leaf(false), index(0), pixel_count(0), sum(), avg(), error_sum(), next_reducible_node(NULL), next_available_in_pool(NULL), children() {}
#pragma warning ( pop )
#endif

    void reset() {
        this->is_leaf = false;
        this->pixel_count = 0;
        this->sum.red = 0; this->sum.green = 0; this->sum.blue = 0;
        this->avg.red = 0; this->avg.green = 0; this->avg.blue = 0;
        this->error_sum.red = 0; this->error_sum.green = 0; this->error_sum.blue = 0;
        this->next_reducible_node = NULL;
        for (size_t i = 0; i < MAX_DEPTH; i++) this->children[i] = NULL;
    }

    void check_compiler() {
        if (this->children[0] != NULL) throw std::runtime_error("Compiler failed to default initialize children");
        if (this->sum.red != 0) throw std::runtime_error("Compiler failed to default initialize sum");
        if (this->avg.red != 0) throw std::runtime_error("Compiler failed to default initialize avg");
    }

    // Adding colors to the tree {{{

    inline Node* create_child(const size_t level, const size_t depth, unsigned int *leaf_count, Node **reducible_nodes, Pool<Node> &node_pool) {
        Node *c = node_pool.checkout();
        if (level == depth) {
            c->is_leaf = true;
            (*leaf_count)++;
        } else {
            c->next_reducible_node = reducible_nodes[level];
            reducible_nodes[level] = c;
        }
        return c;
    }

    inline void update_average() {
        this->avg.red = (double)this->sum.red / (double)this->pixel_count;
        this->avg.green = (double)this->sum.green / (double)this->pixel_count;
        this->avg.blue = (double)this->sum.blue / (double)this->pixel_count;
    }

    void add_color(const unsigned char r, const unsigned char g, const unsigned char b, const size_t depth, const size_t level, unsigned int *leaf_count, Node **reducible_nodes, Pool<Node> &node_pool) {
        if (this->is_leaf) {
            this->pixel_count++;
            this->sum.red += r;
            this->sum.green += g;
            this->sum.blue += b;
            this->update_average();
            this->error_sum.red   += (r > this->avg.red) ? r - this->avg.red : this->avg.red - r;
            this->error_sum.green += (g > this->avg.green) ? g - this->avg.green : this->avg.green - g;
            this->error_sum.blue  += (b > this->avg.blue) ? b - this->avg.blue : this->avg.blue - b;
        } else {
            unsigned char index = get_index(r, g, b, level);
            if (this->children[index] == NULL) this->children[index] = this->create_child(level, depth, leaf_count, reducible_nodes, node_pool);
            this->children[index]->add_color(r, g, b, depth, level + 1, leaf_count, reducible_nodes, node_pool);
        }
    }
    // }}}

    // Tree reduction {{{

    inline uint64_t total_error() const {
        Node *child = NULL;
        uint64_t ans = 0;
        for (int i = 0; i < MAX_DEPTH; i++) {
            if ((child = this->children[i]) != NULL)
                ans += child->error_sum.red + child->error_sum.green + child->error_sum.blue;
        }
        return ans;
    }

    inline Node* find_best_reducible_node(Node *head) {
        uint64_t err = UINT64_MAX,e = 0;
        Node *q = head, *ans = head;
        while (q != NULL) {
            if ((e = q->total_error()) < err) { ans = q; err = e; }
            q = q->next_reducible_node;
        }
        return ans;
    }

    inline unsigned int merge(Pool<Node> &node_pool) {
        unsigned int num = 0, i;
        Node *child = NULL;
        for (i = 0; i < MAX_DEPTH; i++) {
            if ((child = this->children[i]) != NULL) {
                iadd<SumPixel>(this->sum, child->sum);
                iadd<SumPixel>(this->error_sum, child->error_sum);
                this->pixel_count += this->children[i]->pixel_count;
                node_pool.relinquish(this->children[i]); this->children[i] = NULL;
                num ++;
            }
        }
        this->update_average();
        this->is_leaf = true;
        return num;
    }

    void reduce(const size_t depth, unsigned int *leaf_count, Node **reducible_nodes, Pool<Node> &node_pool) {
        size_t i = 0;
        Node *node = NULL, *q = NULL;

        // Find the deepest level containing at least one reducible node
        for (i=depth - 1; i > 0 && reducible_nodes[i] == NULL; i--);
        // Find the reducible node at this level that has the least total error
        node = find_best_reducible_node(reducible_nodes[i]);
        // Remove the found node from the linked list
        if (node == reducible_nodes[i]) reducible_nodes[i] = node->next_reducible_node;
        else {
            q = reducible_nodes[i];
            while (q != NULL) {
                if (q->next_reducible_node == node) { q->next_reducible_node = node->next_reducible_node; break; }
                q = q->next_reducible_node;
            }
        }
        *leaf_count -= node->merge(node_pool) - 1;
    }

    // }}}

    void set_palette_colors(QRgb *color_table, unsigned char *index, bool compute_parent_averages) {  // {{{
        /* Create the color palette based on all existing leaf nodes. */
        int i;
        Node *child;
        if (this->is_leaf) {
            color_table[*index] = qRgb(this->avg.red, this->avg.green, this->avg.blue);
            this->index = (*index)++;
        } else {
            for (i = 0; i < MAX_DEPTH; i++) {
                child = this->children[i];
                if (child != NULL) {
                    child->set_palette_colors(color_table, index, compute_parent_averages);
                    if (compute_parent_averages) {
                        this->pixel_count += child->pixel_count;
                        this->sum.red     += child->pixel_count * child->avg.red;
                        this->sum.green   += child->pixel_count * child->avg.green;
                        this->sum.blue    += child->pixel_count * child->avg.blue;
                    }
                }
            }
            if (compute_parent_averages) this->update_average();
        }
    } // }}}

    unsigned char index_for_nearest_color(const unsigned char r, const unsigned char g, const unsigned char b, const size_t level) { // {{{
        /* Returns the color palette index for the nearest color to (r, g, b) */
        Node *child;
        if (this->is_leaf) return this->index;
        unsigned char index = get_index(r, g, b, level);
        if (this->children[index] == NULL) {
            uint64_t min_distance = UINT64_MAX, distance;
            for(unsigned char i = 0; i < MAX_DEPTH; i++) {
                if ((child = this->children[i]) != NULL) {
                    distance = euclidean_distance<uint64_t>(r, g, b, child->avg.red, child->avg.green, child->avg.blue);
                    if (distance < min_distance) { min_distance = distance; index = i; }
                }
            }
        }
        return this->children[index]->index_for_nearest_color(r, g, b, level + 1);
    } // }}}

};

// Image Dithering  {{{
static inline void propagate_error(QVector<DoublePixel> &error_line, int c, unsigned char mult, DoublePixel &error) {
    error_line[c].red   += error.red * mult;
    error_line[c].green += error.green * mult;
    error_line[c].blue  += error.blue * mult;
}

static inline QRgb apply_error(QRgb pixel, DoublePixel &error) {
#define AERR(w, i) MAX(0, MIN((int)(w(pixel) + error.i), 255))
    return qRgb(AERR(qRed, red), AERR(qGreen, green), AERR(qBlue, blue));
}

static inline void calculate_error(QRgb new_pixel, QRgb old_pixel, DoublePixel &error) {
#define CERR(w) ((double)(w(old_pixel) - w(new_pixel)))/16.0
    error.red = CERR(qRed);
    error.green = CERR(qGreen);
    error.blue = CERR(qBlue);
}

static void dither_image(const QImage &img, QImage &ans, QVector<QRgb> &color_table, Node &root, bool src_is_indexed) {
    const QRgb *line = NULL;
    QRgb pixel = 0, err_pixel = 0;
    unsigned char *bits = NULL, index = 0;
    int iheight = img.height(), iwidth = img.width(), r = 0, c = 0;
    bool is_odd = false;
    int start = 0, delta = 0;
    DoublePixel error = {0, 0, 0};
    const DoublePixel zero = {0, 0, 0};
    QVector<DoublePixel> err1(iwidth), err2(iwidth), *line1 = NULL, *line2 = NULL;
    const QVector<QRgb> src_color_table = img.colorTable();

    for (r = 0; r < iheight; r++) {
        line = reinterpret_cast<const QRgb*>(img.constScanLine(r));
        const unsigned char *src_line = img.constScanLine(r);
        bits = ans.scanLine(r);
        is_odd = r & 1;
        if (is_odd) { start = iwidth - 1; delta = -1; line1 = &err2; line2 = &err1; }
        else { start = 0; delta = 1; line1 = &err1; line2 = &err2; }
        line2->fill(zero);
        for (c = start; 0 < (is_odd ? c + 1 : iwidth - c); c += delta) {
            pixel = src_is_indexed ? src_color_table.at(*(src_line + c)) : *(line + c);
            err_pixel = apply_error(pixel, (*line1)[c]);
            index = root.index_for_nearest_color(qRed(err_pixel), qGreen(err_pixel), qBlue(err_pixel), 0);
            *(bits + c) = index;
            calculate_error(color_table[index], pixel, error);
            if (0 < (is_odd ? c : iwidth - c - 1)) {
                propagate_error(*line1, c + delta, 7, error);
                propagate_error(*line2, c + delta, 1, error);
            }
            propagate_error(*line2, c, 5, error);
            if (0 < (is_odd ? iwidth - c - 1 : c)) propagate_error(*line2, c - delta, 3, error);
        }
    }
}
// }}}

inline unsigned int read_colors(const QImage &img, Node &root, size_t depth, Node **reducible_nodes, Pool<Node> &node_pool) {
    int iwidth = img.width(), iheight = img.height(), r, c;
    unsigned int leaf_count = 0;
    const QRgb* line = NULL;
    for (r = 0; r < iheight; r++) {
        line = reinterpret_cast<const QRgb*>(img.constScanLine(r));
        for (c = 0; c < iwidth; c++) {
            const QRgb pixel = *(line + c);
            root.add_color(qRed(pixel), qGreen(pixel), qBlue(pixel), depth, 0, &leaf_count, reducible_nodes, node_pool);
            while (leaf_count > MAX_LEAVES)
                root.reduce(depth, &leaf_count, reducible_nodes, node_pool);
        }
    }
    return leaf_count;
}

inline unsigned int read_colors(const QVector<QRgb> &color_table, Node &root, size_t depth, Node **reducible_nodes, Pool<Node> &node_pool) {
    unsigned int leaf_count = 0;
    for (int i = 0; i < color_table.size(); i++) {
        const QRgb pixel = color_table[i];
        root.add_color(qRed(pixel), qGreen(pixel), qBlue(pixel), depth, 0, &leaf_count, reducible_nodes, node_pool);
        while (leaf_count > MAX_LEAVES)
            root.reduce(depth, &leaf_count, reducible_nodes, node_pool);
    }
    return leaf_count;
}

inline void reduce_tree(Node &root, size_t depth, unsigned int *leaf_count, unsigned int maximum_colors, Node **reducible_nodes, Pool<Node> &node_pool) {
    while (*leaf_count > maximum_colors)
        root.reduce(depth, leaf_count, reducible_nodes, node_pool);
}

static void write_image(const QImage &img, QImage &ans, Node &root, bool src_is_indexed) {
    int iheight = img.height(), iwidth = img.width(), r = 0, c = 0;
    QVector<QRgb> src_color_table = img.colorTable();

    for (r = 0; r < iheight; r++) {
        const QRgb *line = reinterpret_cast<const QRgb*>(img.constScanLine(r));
        const unsigned char *src_line = img.constScanLine(r);
        unsigned char *bits = ans.scanLine(r);
        for (c = 0; c < iwidth; c++) {
            const QRgb pixel = src_is_indexed ? src_color_table.at(*(src_line + c)) : *(line + c);
            *(bits + c) = root.index_for_nearest_color(qRed(pixel), qGreen(pixel), qBlue(pixel), 0);
        }
    }
}

QImage quantize(const QImage &image, unsigned int maximum_colors, bool dither, const QVector<QRgb> &palette) {
    ScopedGILRelease PyGILRelease;
    size_t depth = MAX_DEPTH;
    int iwidth = image.width(), iheight = image.height();
    QImage img(image), ans(iwidth, iheight, QImage::Format_Indexed8);
    unsigned int leaf_count = 0;
    unsigned char index = 0;
    Node* reducible_nodes[MAX_DEPTH + 1] = {0};
    Node root = Node();
    QVector<QRgb> color_table = QVector<QRgb>(MAX_COLORS);
    QImage::Format fmt = img.format();

    root.check_compiler();

    maximum_colors = MAX(2, MIN(MAX_COLORS, maximum_colors));
    if (img.hasAlphaChannel()) throw std::out_of_range("Cannot quantize image with transparency");
    if (fmt != QImage::Format_RGB32 && fmt != QImage::Format_Indexed8) {
        img = img.convertToFormat(QImage::Format_RGB32);
        if (img.isNull()) throw std::bad_alloc();
    }
    // There can be no more than MAX_LEAVES * 8 nodes. Add 1 in case there is an off by 1 error somewhere.
    Pool<Node> node_pool((MAX_LEAVES + 1) * 8);
    if (palette.size() > 0) {
        // Quantizing to fixed palette
        leaf_count = read_colors(palette, root, depth, reducible_nodes, node_pool);
        maximum_colors = MAX(2, MIN(MAX_COLORS, leaf_count));
    } else if (img.format() == QImage::Format_RGB32) {
        depth = (size_t)log2(maximum_colors);
        depth = MAX(2, MIN(depth, MAX_DEPTH));
        leaf_count = read_colors(img, root, depth, reducible_nodes, node_pool);
    } else {
        leaf_count = read_colors(img.colorTable(), root, depth, reducible_nodes, node_pool);
    }

    reduce_tree(root, depth, &leaf_count, maximum_colors, reducible_nodes, node_pool);
    color_table.resize(leaf_count);
    root.set_palette_colors(color_table.data(), &index, dither);
    ans.setColorTable(color_table);

    if (dither) dither_image(img, ans, color_table, root, img.format() != QImage::Format_RGB32);
    else write_image(img, ans, root, img.format() != QImage::Format_RGB32);

    return ans;
}
