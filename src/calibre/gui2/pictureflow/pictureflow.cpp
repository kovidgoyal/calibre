/*
  PictureFlow - animated image show widget
  http://pictureflow.googlecode.com

  Copyright (C) 2008 Ariya Hidayat (ariya@kde.org)
  Copyright (C) 2007 Ariya Hidayat (ariya@kde.org)

  Permission is hereby granted, a of charge, to any person obtaining a copy
  of this software and associated documentation files (the "Software"), to deal
  in the Software without restriction, including without limitation the rights
  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
  copies of the Software, and to permit persons to whom the Software is
  furnished to do so, subject to the following conditions:

  The above copyright notice and this permission notice shall be included in
  all copies or substantial portions of the Software.

  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
  THE SOFTWARE.
*/

#include "pictureflow.h"

#include <deque>
using namespace std;


#include <QApplication>
#include <QCache>
#include <QHash>
#include <QKeyEvent>
#include <QPainter>
#include <QTimer>
#include <QVector>
#include <QWidget>

#define qMax(x,y) ((x) > (y)) ? (x) : (y)
#define qMin(x,y) ((x) < (y)) ? (x) : (y)
#define qAbs(x,y) ((x) > (y)) ? (x)-(y) : (y)-(x)


// for fixed-point arithmetic, we need minimum 32-bit long
// long long (64-bit) might be useful for multiplication and division
typedef long PFreal;
#define PFREAL_SHIFT 10
#define PFREAL_ONE (1 << PFREAL_SHIFT)

#define IANGLE_MAX 1024
#define IANGLE_MASK 1023

inline PFreal fmul(PFreal a, PFreal b)
{
  return ((long long)(a))*((long long)(b)) >> PFREAL_SHIFT;
}

inline PFreal fdiv(PFreal num, PFreal den)
{
  long long p = (long long)(num) << (PFREAL_SHIFT*2);
  long long q = p / (long long)den;
  long long r = q >> PFREAL_SHIFT;

  return r;
}

inline PFreal fsin(int iangle)
{
  // warning: regenerate the table if IANGLE_MAX and PFREAL_SHIFT are changed!
  static const PFreal tab[] = {
     3,    103,    202,    300,    394,    485,    571,    652,
   726,    793,    853,    904,    947,    980,   1004,   1019,
  1023,   1018,   1003,    978,    944,    901,    849,    789,
   721,    647,    566,    479,    388,    294,    196,     97,
    -4,   -104,   -203,   -301,   -395,   -486,   -572,   -653,
  -727,   -794,   -854,   -905,   -948,   -981,  -1005,  -1020,
 -1024,  -1019,  -1004,   -979,   -945,   -902,   -850,   -790,
  -722,   -648,   -567,   -480,   -389,   -295,   -197,    -98,
  3
  };

  while(iangle < 0)
    iangle += IANGLE_MAX;
  iangle &= IANGLE_MASK;

  int i = (iangle >> 4);
  PFreal p = tab[i];
  PFreal q = tab[(i+1)];
  PFreal g = (q - p);
  return p + g * (iangle-i*16)/16;
}

inline PFreal fcos(int iangle)
{
  return fsin(iangle + (IANGLE_MAX >> 2));
}

/* ----------------------------------------------------------

PictureFlowState stores the state of all slides, i.e. all the necessary
information to be able to render them.

PictureFlowAnimator is responsible to move the slides during the
transition between slides, to achieve the effect similar to Cover Flow,
by changing the state.

PictureFlowSoftwareRenderer (or PictureFlowOpenGLRenderer) is
the actual 3-d renderer. It should render all slides given the state
(an instance of PictureFlowState).

Instances of all the above three classes are stored in
PictureFlowPrivate.

------------------------------------------------------- */

struct SlideInfo
{
  int slideIndex;
  int angle;
  PFreal cx;
  PFreal cy;
  int blend;
};

class PictureFlowState
{
public:
  PictureFlowState();
  ~PictureFlowState();

  void reposition();
  void reset();

  QRgb backgroundColor;
  int slideWidth;
  int slideHeight;
  PictureFlow::ReflectionEffect reflectionEffect;
  QVector<AbstractDelayedImage*> slideImages;

  int angle;
  int spacing;
  PFreal offsetX;
  PFreal offsetY;

  SlideInfo centerSlide;
  QVector<SlideInfo> leftSlides;
  QVector<SlideInfo> rightSlides;
  int centerIndex;
  deque<int> toLoad;
};

class PictureFlowAnimator
{
public:
  PictureFlowAnimator();
  PictureFlowState* state;

  void start(int slide);
  void stop(int slide);
  void update();

  int target;
  int step;
  int frame;
  QTimer animateTimer;
};

class PictureFlowAbstractRenderer
{
public:
  PictureFlowAbstractRenderer(): state(0), dirty(false), widget(0) {}
  virtual ~PictureFlowAbstractRenderer() {}

  PictureFlowState* state;
  bool dirty;
  QWidget* widget;

  virtual void init() = 0;
  virtual void paint() = 0;
};

class PictureFlowSoftwareRenderer: public PictureFlowAbstractRenderer
{
public:
  PictureFlowSoftwareRenderer();
  ~PictureFlowSoftwareRenderer();

  virtual void init();
  virtual void paint();

private:
  QSize size;
  QRgb bgcolor;
  int effect;
  QImage buffer;
  QVector<PFreal> rays;
  QImage* blankSurface;
  QCache<int,QImage> surfaceCache;
  QHash<int,QImage*> imageHash;

  void render();
  void renderSlides();
  QRect renderSlide(const SlideInfo &slide, int col1 = -1, int col2 = -1);
  QImage* surface(int slideIndex);
};

// ------------- PictureFlowState ---------------------------------------

PictureFlowState::PictureFlowState():
backgroundColor(0), slideWidth(150), slideHeight(200),
reflectionEffect(PictureFlow::BlurredReflection), centerIndex(0)
{
}

PictureFlowState::~PictureFlowState()
{
  for(int i = 0; i < (int)slideImages.count(); i++)
    delete slideImages[i];
}

// readjust the settings, call this when slide dimension is changed
void PictureFlowState::reposition()
{
  angle = 70 * IANGLE_MAX / 360;  // approx. 70 degrees tilted

  offsetX = slideWidth/2 * (PFREAL_ONE-fcos(angle));
  offsetY = slideWidth/2 * fsin(angle);
  offsetX += slideWidth * PFREAL_ONE;
  offsetY += slideWidth * PFREAL_ONE / 4;
  spacing = 40;
}

// adjust slides so that they are in "steady state" position
void PictureFlowState::reset()
{
  centerSlide.angle = 0;
  centerSlide.cx = 0;
  centerSlide.cy = 0;
  centerSlide.slideIndex = centerIndex;
  centerSlide.blend = 256;

  leftSlides.resize(6);
  for(int i = 0; i < (int)leftSlides.count(); i++)
  {
    SlideInfo& si = leftSlides[i];
    si.angle = angle;
    si.cx = -(offsetX + spacing*i*PFREAL_ONE);
    si.cy = offsetY;
    si.slideIndex = centerIndex-1-i;
    si.blend = 256;
    if(i == (int)leftSlides.count()-2)
      si.blend = 128;
    if(i == (int)leftSlides.count()-1)
      si.blend = 0;
  }

  rightSlides.resize(6);
  for(int i = 0; i < (int)rightSlides.count(); i++)
  {
    SlideInfo& si = rightSlides[i];
    si.angle = -angle;
    si.cx = offsetX + spacing*i*PFREAL_ONE;
    si.cy = offsetY;
    si.slideIndex = centerIndex+1+i;
    si.blend = 256;
    if(i == (int)rightSlides.count()-2)
      si.blend = 128;
    if(i == (int)rightSlides.count()-1)
      si.blend = 0;
  }
}

// ------------- PictureFlowAnimator  ---------------------------------------

PictureFlowAnimator::PictureFlowAnimator():
state(0), target(0), step(0), frame(0)
{
}

void PictureFlowAnimator::start(int slide)
{
  target = slide;
  if(!animateTimer.isActive() && state)
  {
    step = (target < state->centerSlide.slideIndex) ? -1 : 1;
    animateTimer.start(30);
  }
}

void PictureFlowAnimator::stop(int slide)
{
  step = 0;
  target = slide;
  frame = slide << 16;
  animateTimer.stop();
}

void PictureFlowAnimator::update()
{
  if(!animateTimer.isActive())
    return;
  if(step == 0)
    return;
  if(!state)
    return;

  int speed = 16384/4;


  // deaccelerate when approaching the target
  const int max = 2 * 65536;

  int fi = frame;
  fi -= (target << 16);
  if(fi < 0)
    fi = -fi;
  fi = qMin(fi, max);

  int ia = IANGLE_MAX * (fi-max/2) / (max*2);
  speed = 512 + 16384 * (PFREAL_ONE+fsin(ia))/PFREAL_ONE;


  frame += speed*step;

  int index = frame >> 16;
  int pos = frame & 0xffff;
  int neg = 65536 - pos;
  int tick = (step < 0) ? neg : pos;
  PFreal ftick = (tick * PFREAL_ONE) >> 16;

  if(step < 0)
    index++;

  if(state->centerIndex != index)
  {
    state->centerIndex = index;
    frame = index << 16;
    state->centerSlide.slideIndex = state->centerIndex;
    for(int i = 0; i < (int)state->leftSlides.count(); i++)
      state->leftSlides[i].slideIndex = state->centerIndex-1-i;
    for(int i = 0; i < (int)state->rightSlides.count(); i++)
      state->rightSlides[i].slideIndex = state->centerIndex+1+i;
  }

  state->centerSlide.angle = (step * tick * state->angle) >> 16;
  state->centerSlide.cx = -step * fmul(state->offsetX, ftick);
  state->centerSlide.cy = fmul(state->offsetY, ftick);

  if(state->centerIndex == target)
  {
    stop(target);
    state->reset();
    return;
  }

  for(int i = 0; i < (int)state->leftSlides.count(); i++)
  {
    SlideInfo& si = state->leftSlides[i];
    si.angle = state->angle;
    si.cx = -(state->offsetX + state->spacing*i*PFREAL_ONE + step*state->spacing*ftick);
    si.cy = state->offsetY;
  }

  for(int i = 0; i < (int)state->rightSlides.count(); i++)
  {
    SlideInfo& si = state->rightSlides[i];
    si.angle = -state->angle;
    si.cx = state->offsetX + state->spacing*i*PFREAL_ONE - step*state->spacing*ftick;
    si.cy = state->offsetY;
  }

  if(step > 0)
  {
    PFreal ftick = (neg * PFREAL_ONE) >> 16;
    state->rightSlides[0].angle = -(neg * state->angle) >> 16;
    state->rightSlides[0].cx = fmul(state->offsetX, ftick);
    state->rightSlides[0].cy = fmul(state->offsetY, ftick);
  }
  else
  {
    PFreal ftick = (pos * PFREAL_ONE) >> 16;
    state->leftSlides[0].angle = (pos * state->angle) >> 16;
    state->leftSlides[0].cx = -fmul(state->offsetX, ftick);
    state->leftSlides[0].cy = fmul(state->offsetY, ftick);
  }

  // must change direction ?
  if(target < index) if(step > 0)
    step = -1;
  if(target > index) if(step < 0)
    step = 1;

  // the first and last slide must fade in/fade out
  int nleft = state->leftSlides.count();
  int nright = state->rightSlides.count();
  int fade = pos / 256;

  for(int index = 0; index < nleft; index++)
  {
    int blend = 256;
    if(index == nleft-1)
      blend = (step > 0) ? 0 : 128-fade/2;
    if(index == nleft-2)
      blend = (step > 0) ? 128-fade/2 : 256-fade/2;
    if(index == nleft-3)
      blend = (step > 0) ? 256-fade/2 : 256;
    state->leftSlides[index].blend = blend;
  }
  for(int index = 0; index < nright; index++)
  {
    int blend = (index < nright-2) ? 256 : 128;
    if(index == nright-1)
      blend = (step > 0) ? fade/2 : 0;
    if(index == nright-2)
      blend = (step > 0) ? 128+fade/2 : fade/2;
    if(index == nright-3)
      blend = (step > 0) ? 256 : 128+fade/2;
    state->rightSlides[index].blend = blend;
  }

}

// ------------- PictureFlowSoftwareRenderer ---------------------------------------

PictureFlowSoftwareRenderer::PictureFlowSoftwareRenderer():
PictureFlowAbstractRenderer(), size(0,0), bgcolor(0), effect(-1), blankSurface(0)
{
}

PictureFlowSoftwareRenderer::~PictureFlowSoftwareRenderer()
{
  surfaceCache.clear();
  buffer = QImage();
  delete blankSurface;
}

void PictureFlowSoftwareRenderer::paint()
{
  if(!widget)
    return;

  if(widget->size() != size)
    init();

  if(state->backgroundColor != bgcolor)
  {
    bgcolor = state->backgroundColor;
    surfaceCache.clear();
  }

  if((int)(state->reflectionEffect) != effect)
  {
    effect = (int)state->reflectionEffect;
    surfaceCache.clear();
  }

  if(dirty)
    render();

  QPainter painter(widget);
  painter.drawImage(QPoint(0,0), buffer);
}

void PictureFlowSoftwareRenderer::init()
{
  if(!widget)
    return;

  surfaceCache.clear();
  blankSurface = 0;

  size = widget->size();
  int ww = size.width();
  int wh = size.height();
  int w = (ww+1)/2;
  int h = (wh+1)/2;


  buffer = QImage(ww, wh, QImage::Format_RGB32);
  buffer.fill(bgcolor);

  rays.resize(w*2);
  for(int i = 0; i < w; i++)
  {
    PFreal gg = ((PFREAL_ONE >> 1) + i * PFREAL_ONE) / (2*h);
    rays[w-i-1] = -gg;
    rays[w+i] = gg;
  }

  dirty = true;
}

// TODO: optimize this with lookup tables
static QRgb blendColor(QRgb c1, QRgb c2, int blend)
{
  int r = qRed(c1) * blend/256 + qRed(c2)*(256-blend)/256;
  int g = qGreen(c1) * blend/256 + qGreen(c2)*(256-blend)/256;
  int b = qBlue(c1) * blend/256 + qBlue(c2)*(256-blend)/256;
  return qRgb(r, g, b);
}


static QImage* prepareSurface(const QImage* slideImage, int w, int h, QRgb bgcolor,
PictureFlow::ReflectionEffect reflectionEffect)
{
  Qt::TransformationMode mode = Qt::SmoothTransformation;
  QImage img = slideImage->scaled(w, h, Qt::IgnoreAspectRatio, mode);

  // slightly larger, to accomodate for the reflection
  int hs = h * 2;
  int hofs = h / 3;

  // offscreen buffer: black is sweet
  QImage* result = new QImage(hs, w, QImage::Format_RGB32);
  result->fill(bgcolor);

  // transpose the image, this is to speed-up the rendering
  // because we process one column at a time
  // (and much better and faster to work row-wise, i.e in one scanline)
  for(int x = 0; x < w; x++)
    for(int y = 0; y < h; y++)
      result->setPixel(hofs + y, x, img.pixel(x, y));

  if(reflectionEffect != PictureFlow::NoReflection)
  {
    // create the reflection
    int ht = hs - h - hofs;
    int hte = ht;
    for(int x = 0; x < w; x++)
      for(int y = 0; y < ht; y++)
      {
        QRgb color = img.pixel(x, img.height()-y-1);
        result->setPixel(h+hofs+y, x, blendColor(color,bgcolor,128*(hte-y)/hte));
      }

    if(reflectionEffect == PictureFlow::BlurredReflection)
    {
      // blur the reflection everything first
      // Based on exponential blur algorithm by Jani Huhtanen
      QRect rect(hs/2, 0, hs/2, w);
      rect &= result->rect();

      int r1 = rect.top();
      int r2 = rect.bottom();
      int c1 = rect.left();
      int c2 = rect.right();

      int bpl = result->bytesPerLine();
      int rgba[4];
      unsigned char* p;

      // how many times blur is applied?
      // for low-end system, limit this to only 1 loop
      for(int loop = 0; loop < 2; loop++)
      {
        for(int col = c1; col <= c2; col++)
        {
          p = result->scanLine(r1) + col*4;
          for(int i = 0; i < 3; i++)
            rgba[i] = p[i] << 4;

          p += bpl;
          for(int j = r1; j < r2; j++, p += bpl)
            for(int i = 0; i < 3; i++)
              p[i] = (rgba[i] += (((p[i]<<4)-rgba[i])) >> 1) >> 4;
        }

        for(int row = r1; row <= r2; row++)
        {
          p = result->scanLine(row) + c1*4;
          for(int i = 0; i < 3; i++)
            rgba[i] = p[i] << 4;

          p += 4;
          for(int j = c1; j < c2; j++, p+=4)
            for(int i = 0; i < 3; i++)
              p[i] = (rgba[i] += (((p[i]<<4)-rgba[i])) >> 1) >> 4;
        }

        for(int col = c1; col <= c2; col++)
        {
          p = result->scanLine(r2) + col*4;
          for(int i = 0; i < 3; i++)
            rgba[i] = p[i] << 4;

          p -= bpl;
          for(int j = r1; j < r2; j++, p -= bpl)
            for(int i = 0; i < 3; i++)
              p[i] = (rgba[i] += (((p[i]<<4)-rgba[i])) >> 1) >> 4;
        }

        for(int row = r1; row <= r2; row++)
        {
          p = result->scanLine(row) + c2*4;
          for(int i = 0; i < 3; i++)
            rgba[i] = p[i] << 4;

          p -= 4;
          for(int j = c1; j < c2; j++, p-=4)
            for(int i = 0; i < 3; i++)
              p[i] = (rgba[i] += (((p[i]<<4)-rgba[i])) >> 1) >> 4;
        }
      }

      // overdraw to leave only the reflection blurred (but not the actual image)
      for(int x = 0; x < w; x++)
        for(int y = 0; y < h; y++)
          result->setPixel(hofs + y, x, img.pixel(x, y));
    }
  }

  return result;
}

QImage* PictureFlowSoftwareRenderer::surface(int slideIndex)
{
  if(!state)
    return 0;
  if(slideIndex < 0)
    return 0;
  if(slideIndex >= (int)state->slideImages.count())
    return 0;

  int key = slideIndex;
  AbstractDelayedImage *cimg = state->slideImages.at(slideIndex);
  if (not cimg->isLoaded()) cimg->load();
  QImage* img = cimg->image();
  bool empty = img ? img->isNull() : true;
  if(empty)
  {
    surfaceCache.remove(key);
    imageHash.remove(slideIndex);
    if(!blankSurface)
    {
      int sw = state->slideWidth;
      int sh = state->slideHeight;

      QImage img = QImage(sw, sh, QImage::Format_RGB32);

      QPainter painter(&img);
      QPoint p1(sw*4/10, 0);
      QPoint p2(sw*6/10, sh);
      QLinearGradient linearGrad(p1, p2);
      linearGrad.setColorAt(0, Qt::black);
      linearGrad.setColorAt(1, Qt::white);
      painter.setBrush(linearGrad);
      painter.fillRect(0, 0, sw, sh, QBrush(linearGrad));

      painter.setPen(QPen(QColor(64,64,64), 4));
      painter.setBrush(QBrush());
      painter.drawRect(2, 2, sw-3, sh-3);
      painter.end();

      blankSurface = prepareSurface(&img, sw, sh, bgcolor, state->reflectionEffect);
    }
    return blankSurface;
  }

  bool exist = imageHash.contains(slideIndex);
  if(exist)
  if(img == imageHash.find(slideIndex).value())
    if(surfaceCache.contains(key))
        return surfaceCache[key];

  QImage* sr = prepareSurface(img, state->slideWidth, state->slideHeight, bgcolor, state->reflectionEffect);
  surfaceCache.insert(key, sr);
  imageHash.insert(slideIndex, img);

  return sr;
}

// Renders a slide to offscreen buffer. Returns a rect of the rendered area.
// col1 and col2 limit the column for rendering.
QRect PictureFlowSoftwareRenderer::renderSlide(const SlideInfo &slide, int col1, int col2)
{
  int blend = slide.blend;
  if(!blend)
    return QRect();

  QImage* src = surface(slide.slideIndex);
  if(!src)
    return QRect();

  QRect rect(0, 0, 0, 0);

  int sw = src->height();
  int sh = src->width();
  int h = buffer.height();
  int w = buffer.width();

  if(col1 > col2)
  {
    int c = col2;
    col2 = col1;
    col1 = c;
  }

  col1 = (col1 >= 0) ? col1 : 0;
  col2 = (col2 >= 0) ? col2 : w-1;
  col1 = qMin(col1, w-1);
  col2 = qMin(col2, w-1);

  int zoom = 100;
  int distance = h * 100 / zoom;
  PFreal sdx = fcos(slide.angle);
  PFreal sdy = fsin(slide.angle);
  PFreal xs = slide.cx - state->slideWidth * sdx/2;
  PFreal ys = slide.cy - state->slideWidth * sdy/2;
  PFreal dist = distance * PFREAL_ONE;

  int xi = qMax((PFreal)0, (w*PFREAL_ONE/2) + fdiv(xs*h, dist+ys) >> PFREAL_SHIFT);
  if(xi >= w)
    return rect;

  bool flag = false;
  rect.setLeft(xi);
  for(int x = qMax(xi, col1); x <= col2; x++)
  {
    PFreal hity = 0;
    PFreal fk = rays[x];
    if(sdy)
    {
      fk = fk - fdiv(sdx,sdy);
      hity = -fdiv((rays[x]*distance - slide.cx + slide.cy*sdx/sdy), fk);
    }

    dist = distance*PFREAL_ONE + hity;
    if(dist < 0)
      continue;

    PFreal hitx = fmul(dist, rays[x]);
    PFreal hitdist = fdiv(hitx - slide.cx, sdx);

    int column = sw/2 + (hitdist >> PFREAL_SHIFT);
    if(column >= sw)
      break;
    if(column < 0)
      continue;

    rect.setRight(x);
    if(!flag)
      rect.setLeft(x);
    flag = true;

    int y1 = h/2;
    int y2 = y1+ 1;
    QRgb* pixel1 = (QRgb*)(buffer.scanLine(y1)) + x;
    QRgb* pixel2 = (QRgb*)(buffer.scanLine(y2)) + x;
    QRgb pixelstep = pixel2 - pixel1;

    int center = (sh/2);
    int dy = dist / h;
    int p1 = center*PFREAL_ONE - dy/2;
    int p2 = center*PFREAL_ONE + dy/2;

    const QRgb *ptr = (const QRgb*)(src->scanLine(column));
    if(blend == 256)
      while((y1 >= 0) && (y2 < h) && (p1 >= 0))
      {
        *pixel1 = ptr[p1 >> PFREAL_SHIFT];
        *pixel2 = ptr[p2 >> PFREAL_SHIFT];
        p1 -= dy;
        p2 += dy;
        y1--;
        y2++;
        pixel1 -= pixelstep;
        pixel2 += pixelstep;
      }
    else
      while((y1 >= 0) && (y2 < h) && (p1 >= 0))
      {
        QRgb c1 = ptr[p1 >> PFREAL_SHIFT];
        QRgb c2 = ptr[p2 >> PFREAL_SHIFT];
        *pixel1 = blendColor(c1, bgcolor, blend);
        *pixel2 = blendColor(c2, bgcolor, blend);
        p1 -= dy;
        p2 += dy;
        y1--;
        y2++;
        pixel1 -= pixelstep;
        pixel2 += pixelstep;
     }
   }

   rect.setTop(0);
   rect.setBottom(h-1);
   return rect;
}

void PictureFlowSoftwareRenderer::renderSlides()
{
  int nleft = state->leftSlides.count();
  int nright = state->rightSlides.count();

  QRect r = renderSlide(state->centerSlide);
  int c1 = r.left();
  int c2 = r.right();

  for(int index = 0; index < nleft; index++)
  {
    QRect rs = renderSlide(state->leftSlides[index], 0, c1-1);
    if(!rs.isEmpty())
      c1 = rs.left();
  }
  for(int index = 0; index < nright; index++)
  {
    QRect rs = renderSlide(state->rightSlides[index], c2+1, buffer.width());
    if(!rs.isEmpty())
      c2 = rs.right();
  }
}

// Render the slides. Updates only the offscreen buffer.
void PictureFlowSoftwareRenderer::render()
{
  buffer.fill(state->backgroundColor);
  renderSlides();
  dirty = false;
}

// -----------------------------------------

class PictureFlowPrivate
{
public:
  PictureFlowState* state;
  PictureFlowAnimator* animator;
  PictureFlowAbstractRenderer* renderer;
  QTimer triggerTimer;
  QTimer loadTimer;
  int loadBuffer;
};


PictureFlow::PictureFlow(QWidget* parent, const int loadBuffer): QWidget(parent)
{
  d = new PictureFlowPrivate;

  d->loadBuffer = loadBuffer;

  d->state = new PictureFlowState;
  d->state->reset();
  d->state->reposition();

  d->renderer = new PictureFlowSoftwareRenderer;
  d->renderer->state = d->state;
  d->renderer->widget = this;
  d->renderer->init();

  d->animator = new PictureFlowAnimator;
  d->animator->state = d->state;
  QObject::connect(&d->animator->animateTimer, SIGNAL(timeout()), this, SLOT(updateAnimation()));

  QObject::connect(&d->triggerTimer, SIGNAL(timeout()), this, SLOT(render()));

  QObject::connect(&d->loadTimer, SIGNAL(timeout()), this, SLOT(load()));
  d->loadTimer.start(10);

  setAttribute(Qt::WA_StaticContents, true);
  setAttribute(Qt::WA_OpaquePaintEvent, true);
  setAttribute(Qt::WA_NoSystemBackground, true);
}

PictureFlow::~PictureFlow()
{
  delete d->renderer;
  delete d->animator;
  delete d->state;
  delete d;
}

int PictureFlow::slideCount() const
{
  return d->state->slideImages.count();
}

QColor PictureFlow::backgroundColor() const
{
  return QColor(d->state->backgroundColor);
}

void PictureFlow::setBackgroundColor(const QColor& c)
{
  d->state->backgroundColor = c.rgb();
  triggerRender();
}

QSize PictureFlow::slideSize() const
{
  return QSize(d->state->slideWidth, d->state->slideHeight);
}

void PictureFlow::setSlideSize(QSize size)
{
  d->state->slideWidth = size.width();
  d->state->slideHeight = size.height();
  d->state->reposition();
  triggerRender();
}

PictureFlow::ReflectionEffect PictureFlow::reflectionEffect() const
{
  return d->state->reflectionEffect;
}

void PictureFlow::setReflectionEffect(ReflectionEffect effect)
{
  d->state->reflectionEffect = effect;
  triggerRender();
}

AbstractDelayedImage PictureFlow::slide(int index) const
{
  if((index >= 0) && (index < slideCount()) && d->state->slideImages[index])
    return *d->state->slideImages[index];
  return AbstractDelayedImage();
}

void PictureFlow::addSlide(AbstractDelayedImage *image)
{
  int c = d->state->slideImages.count();
  d->state->slideImages.resize(c+1);
  d->state->slideImages[c] = image;
  if (qAbs(d->state->centerIndex, c) <= d->loadBuffer)
    d->state->toLoad.push_back(c);
  triggerRender();
}

void PictureFlow::setSlide(int index, AbstractDelayedImage *image)
{
  if((index >= 0) && (index < slideCount()))
  {
    delete d->state->slideImages[index];
    d->state->slideImages[index] = image;
    if (qAbs(d->state->centerIndex, index) <= d->loadBuffer)
      d->state->toLoad.push_back(index);
    triggerRender();
  }
}

int PictureFlow::centerIndex() const
{
  return d->state->centerIndex;
}

void PictureFlow::updateBuffer(int old_center, int new_center)
{
  int c;
  for (c = qMax(new_center - d->loadBuffer, 0); c <= qMin(new_center+ d->loadBuffer, slideCount()-1); c++) {
    if (not d->state->slideImages[c]->isLoaded()) d->state->toLoad.push_back(c);
  }
  for (c = qMax(old_center - d->loadBuffer, 0); c <= qMin(old_center + d->loadBuffer, slideCount()-1); c++) {
    if ((c < qMax(new_center - d->loadBuffer, 0) or c > qMin(new_center + d->loadBuffer, slideCount()-1)) and d->state->slideImages[c]->isLoaded()) {
      d->state->slideImages[c]->unload();
    }
  }
}

void PictureFlow::setCenterIndex(int index)
{
  index = qMin(index, slideCount()-1);
  index = qMax(index, 0);
  updateBuffer(d->state->centerIndex, index);
  d->state->centerIndex = index;
  d->state->reset();
  d->animator->stop(index);
  triggerRender();
}

void PictureFlow::clear()
{
  int c = d->state->slideImages.count();
  for(int i = 0; i < c; i++)
    delete d->state->slideImages[i];
  d->state->slideImages.resize(0);

  d->state->reset();
  triggerRender();
}

void PictureFlow::render()
{
  d->renderer->dirty = true;
  update();
}

void PictureFlow::load()
{
  int index;
  if (not d->state->toLoad.empty()) {
    index = d->state->toLoad.front();
    d->state->toLoad.pop_front();
    if (index > 0 and index < d->state->slideImages.count() and not d->state->slideImages[index]->isLoaded()) {
      d->state->slideImages[index]->load(); triggerRender();
    }
  }
}

void PictureFlow::triggerRender()
{
  d->triggerTimer.setSingleShot(true);
  d->triggerTimer.start(0);
}

void PictureFlow::showPrevious()
{
  int step = d->animator->step;
  int center = d->state->centerIndex;

  if(step > 0)
    d->animator->start(center);

  if(step == 0)
    if(center > 0)
      d->animator->start(center - 1);

  if(step < 0)
    d->animator->target = qMax(0, center - 2);
}

void PictureFlow::showNext()
{
  int step = d->animator->step;
  int center = d->state->centerIndex;

  if(step < 0)
    d->animator->start(center);

  if(step == 0)
    if(center < slideCount()-1)
      d->animator->start(center + 1);

  if(step > 0)
    d->animator->target = qMin(center + 2, slideCount()-1);
}

void PictureFlow::showSlide(int index)
{
  index = qMax(index, 0);
  index = qMin(slideCount()-1, index);
  if(index == d->state->centerSlide.slideIndex)
    return;

  d->animator->start(index);
}

void PictureFlow::keyPressEvent(QKeyEvent* event)
{
  if(event->key() == Qt::Key_Left)
  {
    if(event->modifiers() == Qt::ControlModifier)
      showSlide(centerIndex()-10);
    else
      showPrevious();
    event->accept();
    return;
  }

  if(event->key() == Qt::Key_Right)
  {
    if(event->modifiers() == Qt::ControlModifier)
      showSlide(centerIndex()+10);
    else
      showNext();
    event->accept();
    return;
  }

  event->ignore();
}

void PictureFlow::mousePressEvent(QMouseEvent* event)
{
  if(event->x() > width()/2)
    showNext();
  else
    showPrevious();
}

void PictureFlow::paintEvent(QPaintEvent* event)
{
  Q_UNUSED(event);
  d->renderer->paint();
}

void PictureFlow::resizeEvent(QResizeEvent* event)
{
  triggerRender();
  QWidget::resizeEvent(event);
}

void PictureFlow::updateAnimation()
{
  int old_center = d->state->centerIndex;
  d->animator->update();
  triggerRender();
  if(d->state->centerIndex != old_center) {
    updateBuffer(old_center, d->state->centerIndex);
    emit centerIndexChanged(d->state->centerIndex);
  }
}

//-------------Delayed Images------------------------------------------------

bool AbstractDelayedImage::load() { return bool(0); }
void AbstractDelayedImage::unload() {if (imageptr != 0) {delete imageptr; imageptr = 0;}}
void AbstractDelayedImage::free() { unload(); }
bool AbstractDelayedImage::isLoaded() { return imageptr != 0; }
QImage* AbstractDelayedImage::image() { return imageptr; }
bool FileDelayedImage::load() { imageptr = new QImage(file_path); return not imageptr->isNull(); }
PreLoadedImage::PreLoadedImage(const QImage& image) { memory = new QImage(image); }
PreLoadedImage::PreLoadedImage(const QPixmap& image) { memory = new QImage(image.toImage()); }
bool PreLoadedImage::load() { imageptr = new QImage(*memory); return not imageptr->isNull(); }
void PreLoadedImage::free() { unload(); if (memory != 0) {delete memory; memory = 0;} }
