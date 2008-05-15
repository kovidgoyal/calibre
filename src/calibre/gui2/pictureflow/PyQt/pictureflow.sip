//Define the SIP wrapper to the pictureflow widget
//Author - Kovid Goyal <kovid@kovidgoyal.net>

%Module pictureflow 1

%Import QtCore/QtCoremod.sip
%Import QtGui/QtGuimod.sip

class AbstractDelayedImage {

%TypeHeaderCode
#include "../../pictureflow.h"
%End

public:
  AbstractDelayedImage();
  virtual bool load();
  virtual void unload();
  virtual void free();
  virtual bool isLoaded();
  virtual QImage* image();

};

class FileDelayedImage : AbstractDelayedImage
{

%TypeHeaderCode
#include "../../pictureflow.h"
%End

public:
  FileDelayedImage(QString path);
  bool load();
};

class PreLoadedImage : AbstractDelayedImage
{

%TypeHeaderCode
#include "../../pictureflow.h"
%End

public:

  PreLoadedImage(const QImage& image); 
  PreLoadedImage(const QPixmap& image);
  bool load();
  void free();
};

class PictureFlow : QWidget  {

%TypeHeaderCode
#include "../../pictureflow.h"
%End


public :
    
  PictureFlow(QWidget *parent /TransferThis/ = 0, int loadBuffer = 10);

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

};

