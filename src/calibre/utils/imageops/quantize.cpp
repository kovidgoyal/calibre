/*
 * quantize.cpp
 * Copyright (C) 2016 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * octree based image quantization. 
 * Based on https://www.microsoft.com/msj/archive/S3F1.aspx
 *
 * Distributed under terms of the GPL3 license.
 */

#include <algorithm>
#include <cmath>
#include <stdio.h>
#include <QVector>
#include "imageops.h"

#ifdef _MSC_VER
typedef unsigned __int64 uint64_t;
typedef __int64 int64_t;
typedef unsigned __int32 uint32_t;
#define UINT64_MAX _UI64_MAX
#ifndef log2
static inline double log2(double x) { return log(x) / log((double)2) ; }
#endif
#else
#include <stdint.h>
#endif
#define MAX_DEPTH 8
#define MAX_COLORS 256
#define MAX(x, y) ((x) > (y)) ? (x) : (y)
#define MIN(x, y) ((x) < (y)) ? (x) : (y)
static const unsigned char BIT_MASK[8] = { 1 << 7, 1 << 6, 1 << 5, 1 << 4, 1 << 3, 1 << 2, 1 << 1, 1 };
static inline size_t get_index(const uint32_t r, const uint32_t g, const uint32_t b, const size_t level) {
    return ((((r & BIT_MASK[level]) >> (7 - level)) << 2) | (((g & BIT_MASK[level]) >> (7 - level)) << 1) | ((b & BIT_MASK[level]) >> (7 - level)));
}
template <typename T> static inline T euclidean_distance(T r1, T g1, T b1, T r2, T g2, T b2) {
    return r1 * r1 + r2 * r2 + g1 * g1 + g2 * g2 + b1 * b1 + b2 * b2 - 2 * (r1 * r2 + g1 * g2 + b1 * b2);
}
struct DoublePixel { double red; double green; double blue; };

template <class T> class Pool {  // {{{
private:
    QVector<T> nodes;
    T *first_available;

public:
    Pool<T>(size_t size) : nodes(size), first_available(nodes.data()) {
        for (size_t i = 0; i < size - 1; i++) this->nodes[i].next_available_in_pool = &this->nodes[i+1];
    }

    T* checkout() {
        T *ans = this->first_available;
        if (ans == NULL) throw std::out_of_range("Something bad happened: ran out of nodes in the pool");
        this->first_available = ans->next_available_in_pool;
        if (this->first_available == NULL) {
            // Grow the pool
            int size = this->nodes.size();
            this->nodes.resize(2*size);
            this->first_available = &this->nodes[size];
            for (int i = size; i < 2*size - 1; i++) this->nodes[i].next_available_in_pool = &this->nodes[i+1];
        }
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
    uint64_t red_sum;
    uint64_t green_sum;
    uint64_t blue_sum;
    unsigned char red_avg;
    unsigned char green_avg;
    unsigned char blue_avg;
    Node* next_reducible_node;
    Node *next_available_in_pool;
    Node* children[MAX_DEPTH];

public:
#ifdef _MSC_VER
// Disable the new behavior warning caused by children() below
#pragma warning( push )
#pragma warning (disable: 4351)
    Node() : is_leaf(false), index(0), pixel_count(0), red_sum(0), green_sum(0), blue_sum(0), red_avg(0), green_avg(0), blue_avg(0), next_reducible_node(NULL), next_available_in_pool(NULL), children() {}
#pragma warning ( pop )
#endif

    void reset() {
        this->is_leaf = false;
        this->pixel_count = 0;
        this->red_sum = 0;
        this->green_sum = 0;
        this->blue_sum = 0;
        this->next_reducible_node = NULL;
        for (size_t i = 0; i < MAX_DEPTH; i++) this->children[i] = NULL;
    }

    void check_compiler() {
        if (this->children[0] != NULL) throw std::runtime_error("Compiler failed to default initialize children");
    }

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

    void add_color(const uint32_t r, const uint32_t g, const uint32_t b, const size_t depth, const size_t level, unsigned int *leaf_count, Node **reducible_nodes, Pool<Node> &node_pool) {
        if (this->is_leaf) {
            this->pixel_count++;
            this->red_sum += r;
            this->green_sum += g;
            this->blue_sum += b;
        } else {
            size_t index = get_index(r, g, b, level);
            if (this->children[index] == NULL) this->children[index] = this->create_child(level, depth, leaf_count, reducible_nodes, node_pool);
            this->children[index]->add_color(r, g, b, depth, level + 1, leaf_count, reducible_nodes, node_pool);
        }
    }

    void reduce(const size_t depth, unsigned int *leaf_count, Node **reducible_nodes, Pool<Node> &node_pool) {
        size_t i = 0;
        Node *node = NULL;

        // Find the deepest level containing at least one reducible node
        for (i=depth - 1; i > 0 && reducible_nodes[i] == NULL; i--);

        // Reduce the node most recently added to the list at level i
        // Could make this smarter by walking the linked list and choosing a
        // node that has the least number of pixels or by storing error info
        // on the nodes and using that
        node = reducible_nodes[i];
        reducible_nodes[i] = node->next_reducible_node;

        for (i = 0; i < MAX_DEPTH; i++) {
            if (node->children[i] != NULL) {
                node->red_sum += node->children[i]->red_sum;
                node->green_sum += node->children[i]->green_sum;
                node->blue_sum += node->children[i]->blue_sum;
                node->pixel_count += node->children[i]->pixel_count;
                node_pool.relinquish(node->children[i]); node->children[i] = NULL;
                (*leaf_count)--;
            }
        }
        node->is_leaf = true; *leaf_count += 1;
    }

    void set_palette_colors(QRgb *color_table, unsigned char *index, bool compute_parent_averages) {
        int i;
        Node *child;
        if (this->is_leaf) {
#define AVG_COLOR(x) ((unsigned char) ((double)this->x / (double)this->pixel_count))
            this->red_avg = AVG_COLOR(red_sum); this->green_avg = AVG_COLOR(green_sum); this->blue_avg = AVG_COLOR(blue_sum);
            color_table[*index] = qRgb(this->red_avg, this->green_avg, this->blue_avg); 
            this->index = (*index)++;
        } else {
            for (i = 0; i < MAX_DEPTH; i++) {
                child = this->children[i];
                if (child != NULL) {
                    child->set_palette_colors(color_table, index, compute_parent_averages);
                    if (compute_parent_averages) {
                        this->pixel_count += child->pixel_count;
                        this->red_sum     += child->pixel_count * child->red_avg; 
                        this->green_sum   += child->pixel_count * child->green_avg;
                        this->blue_sum    += child->pixel_count * child->blue_avg;
                    }
                }
            }
            if (compute_parent_averages) {
                this->red_avg = AVG_COLOR(red_sum); this->green_avg = AVG_COLOR(green_sum); this->blue_avg = AVG_COLOR(blue_sum);
            }
        }
    }

    unsigned char index_for_color(const uint32_t r, const uint32_t g, const uint32_t b, const size_t level) const {
        if (this->is_leaf) return this->index;
        size_t index = get_index(r, g, b, level);
        if (this->children[index] == NULL) throw std::out_of_range("Something bad happened: could not follow tree for color");
        return this->children[index]->index_for_color(r, g, b, level + 1);
    }

    unsigned char index_for_nearest_color(const uint32_t r, const uint32_t g, const uint32_t b, const size_t level) {
        if (this->is_leaf) return this->index;
        size_t index = get_index(r, g, b, level);
        if (this->children[index] == NULL) {
            uint64_t min_distance = UINT64_MAX, distance;
            for(size_t i = 0; i < MAX_DEPTH; i++) {
                Node *child = this->children[i];
                if (child != NULL) {
                    distance = euclidean_distance<uint64_t>(r, g, b, child->red_avg, child->green_avg, child->blue_avg);
                    if (distance < min_distance) { min_distance = distance; index = i; }
                }
            }
        }
        return this->children[index]->index_for_nearest_color(r, g, b, level + 1);
    }

};

static inline void propagate_error(QVector<DoublePixel> &error_line, int c, unsigned char mult, DoublePixel &error) {
    error_line[c].red   = error.red * mult;
    error_line[c].green = error.green * mult;
    error_line[c].blue  = error.blue * mult;
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

static void dither_image(const QImage &img, QImage &ans, QVector<QRgb> &color_table, Node &root) {
    const QRgb *line = NULL;
    QRgb pixel = 0, new_pixel = 0;
    unsigned char *bits = NULL, index = 0;
    int iheight = img.height(), iwidth = img.width(), r = 0, c = 0;
    bool is_odd = false;
    int start = 0, delta = 0;
    DoublePixel error = {0, 0, 0};
    const DoublePixel zero = {0, 0, 0};
    QVector<DoublePixel> err1(iwidth), err2(iwidth), *line1 = NULL, *line2 = NULL;

    for (r = 0; r < iheight; r++) {
        line = reinterpret_cast<const QRgb*>(img.constScanLine(r));
        bits = ans.scanLine(r);
        is_odd = r & 1;
        start = is_odd ? iwidth - 1 : 0;
        delta = is_odd ? -1 : 1;
        line1 = is_odd ? &err2 : &err1;
        line2 = is_odd ? &err1 : &err2;
        line2->fill(zero);
        for (c = start; 0 < (is_odd ? c : iwidth - c); c += delta) {
            pixel = *(line + c);
            new_pixel = apply_error(pixel, (*line1)[c]);
            index = root.index_for_nearest_color(qRed(new_pixel), qGreen(new_pixel), qBlue(new_pixel), 0);
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

QImage quantize(const QImage &image, unsigned int maximum_colors, bool dither) {
    ScopedGILRelease PyGILRelease;
    size_t depth = 0;
    int iwidth = image.width(), iheight = image.height(), r, c;
    QImage img(image), ans(iwidth, iheight, QImage::Format_Indexed8);
    unsigned int leaf_count = 0;
    unsigned char index = 0, *bits;
    Node* reducible_nodes[MAX_DEPTH + 1] = {0};
    Node root = Node();
    QVector<QRgb> color_table = QVector<QRgb>(MAX_COLORS);
    const QRgb* line = NULL;

    root.check_compiler();

    maximum_colors = MAX(2, MIN(MAX_COLORS, maximum_colors));
    if (img.colorCount() > 0 && (size_t)img.colorCount() <= maximum_colors) return img; // Image is already quantized
    if (img.hasAlphaChannel()) throw std::out_of_range("Cannot quantize image with transparency");
    // TODO: Handle indexed image with colors > maximum_colors more efficiently
    // by iterating over the color table rather than the pixels
    if (img.format() != QImage::Format_RGB32) img = img.convertToFormat(QImage::Format_RGB32);
    if (img.isNull()) throw std::bad_alloc();
    // There can be at-most 8*(maximum_colors + 1) nodes, since we reduce the
    // tree after each color is added Use an extra eight node just in case
    // there is an off-by-one error somewhere :)
    Pool<Node> node_pool((2 + maximum_colors) * 8);  

    depth = (size_t)log2(maximum_colors);
    depth = MAX(2, MIN(depth, MAX_DEPTH));

    for (r = 0; r < iheight; r++) {
        line = reinterpret_cast<const QRgb*>(img.constScanLine(r));
        for (c = 0; c < iwidth; c++) {
            const QRgb pixel = *(line + c);
            root.add_color(qRed(pixel), qGreen(pixel), qBlue(pixel), depth, 0, &leaf_count, reducible_nodes, node_pool);
            while (leaf_count > maximum_colors)
                root.reduce(depth, &leaf_count, reducible_nodes, node_pool);
        }
    }

    if (leaf_count > maximum_colors) throw std::out_of_range("Leaf count > max colors, something bad happened");
    color_table.resize(leaf_count);
    root.set_palette_colors(color_table.data(), &index, dither);
    ans.setColorTable(color_table);

    if (dither) {
        dither_image(img, ans, color_table, root);
    } else {
        for (r = 0; r < iheight; r++) {
            line = reinterpret_cast<const QRgb*>(img.constScanLine(r));
            bits = ans.scanLine(r);
            for (c = 0; c < iwidth; c++) {
                const QRgb pixel = *(line + c);
                *(bits + c) = root.index_for_color(qRed(pixel), qGreen(pixel), qBlue(pixel), 0);
            }
        }
    }

    return ans;
}
