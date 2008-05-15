/*
  PictureFlow - animated image show widget
  http://pictureflow.googlecode.com

  Copyright (C) 2008 Ariya Hidayat (ariya@kde.org)
  Copyright (C) 2007 Ariya Hidayat (ariya@kde.org)

  Permission is hereby granted, free of charge, to any person obtaining a copy
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

#ifndef PICTUREFLOW_H
#define PICTUREFLOW_H

#include <QImage>
#include <QPixmap>
#include <QWidget>

class AbstractDelayedImage
{
public:
  AbstractDelayedImage() : imageptr(0) {};
  ~AbstractDelayedImage() { free(); }

  virtual bool load();
  virtual void unload();
  virtual void free();
  virtual bool isLoaded();
  virtual QImage* image();

protected:
  QImage *imageptr;

};

class FileDelayedImage : public AbstractDelayedImage
{
public:
  FileDelayedImage(QString path) : file_path(path) { imageptr = 0; }

  bool load();

private:
  QString file_path;
};

class PreLoadedImage : public AbstractDelayedImage
{
public:
  PreLoadedImage(const QImage& image);  
  PreLoadedImage(const QPixmap& image);

  bool load();
  void free();


private:
  QImage *memory;
};


class PictureFlowPrivate;

/*!
  Class PictureFlow implements an image show widget with animation effect
  like Apple's CoverFlow (in iTunes and iPod). Images are arranged in form
  of slides, one main slide is shown at the center with few slides on
  the left and right sides of the center slide. When the next or previous
  slide is brought to the front, the whole slides flow to the right or
  the right with smooth animation effect; until the new slide is finally
  placed at the center.

 */
class PictureFlow : public QWidget
{
Q_OBJECT

  Q_PROPERTY(QColor backgroundColor READ backgroundColor WRITE setBackgroundColor)
  Q_PROPERTY(QSize slideSize READ slideSize WRITE setSlideSize)
  Q_PROPERTY(int slideCount READ slideCount)
  Q_PROPERTY(int centerIndex READ centerIndex WRITE setCenterIndex)

public:

  enum ReflectionEffect
  {
    NoReflection,
    PlainReflection,
    BlurredReflection
  };

  /*!
    Creates a new PictureFlow widget.
  */
  PictureFlow(QWidget* parent = 0, int loadBuffer = 10);

  /*!
    Destroys the widget.
  */
  ~PictureFlow();

  /*!
    Returns the background color.
  */
  QColor backgroundColor() const;

  /*!
    Sets the background color. By default it is black.
  */
  void setBackgroundColor(const QColor& c);

  /*!
    Returns the dimension of each slide (in pixels).
  */
  QSize slideSize() const;

  /*!
    Sets the dimension of each slide (in pixels).
  */
  void setSlideSize(QSize size);

  /*!
    Returns the total number of slides.
  */
  int slideCount() const;

  /*!
    Returns AbstractDelayedImage of specified slide.
  */
  AbstractDelayedImage slide(int index) const;

  /*!
    Returns the index of slide currently shown in the middle of the viewport.
  */
  int centerIndex() const;

  /*!
    Returns the effect applied to the reflection.
  */
  ReflectionEffect reflectionEffect() const;

  /*!
    Sets the effect applied to the reflection. The default is PlainReflection.
  */
  void setReflectionEffect(ReflectionEffect effect);


public slots:

  /*!
    Adds a new slide.
  */
  void addSlide(AbstractDelayedImage *image);

  /*!
    Sets an image for specified slide. If the slide already exists,
    it will be replaced.
  */
  void setSlide(int index, AbstractDelayedImage *image);

  /*!
    Sets slide to be shown in the middle of the viewport. No animation
    effect will be produced, unlike using showSlide.
  */
  void setCenterIndex(int index);

  /*!
    Clears all slides.
  */
  void clear();

  /*!
    Shows previous slide using animation effect.
  */
  void showPrevious();

  /*!
    Shows next slide using animation effect.
  */
  void showNext();

  /*!
    Go to specified slide using animation effect.
  */
  void showSlide(int index);

  /*!
    Rerender the widget. Normally this function will be automatically invoked
    whenever necessary, e.g. during the transition animation.
  */
  void render();

  /*!
    Load and images that are in the load buffer. This function is automatically
    caled peridically.
  */
  void load();

  /*!
    Schedules a rendering update. Unlike render(), this function does not cause
    immediate rendering.
  */
  void triggerRender();

signals:
  void centerIndexChanged(int index);

protected:
  void paintEvent(QPaintEvent *event);
  void keyPressEvent(QKeyEvent* event);
  void mousePressEvent(QMouseEvent* event);
  void resizeEvent(QResizeEvent* event);

private slots:
  void updateAnimation();

private:
  PictureFlowPrivate* d;
  void updateBuffer(int old_center, int new_center);
};

#endif // PICTUREFLOW_H

