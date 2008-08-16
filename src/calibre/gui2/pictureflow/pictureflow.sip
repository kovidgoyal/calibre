//Define the SIP wrapper to the pictureflow widget
//Author - Kovid Goyal <kovid@kovidgoyal.net>

%Module pictureflow 1

%Import QtCore/QtCoremod.sip
%Import QtGui/QtGuimod.sip

class FlowImages : QObject {

%TypeHeaderCode
#include <pictureflow.h>
%End

public:
  virtual int count();
  virtual QImage image(int index);
  virtual QString caption(int index);
};


class PictureFlow : QWidget  {

%TypeHeaderCode
#include <pictureflow.h>
%End


public :
    
  PictureFlow(QWidget *parent /TransferThis/ = 0, int queueLength = 3);

  void setImages(FlowImages *images);
  
  QSize slideSize() const;

  void setSlideSize(QSize size);

  void setZoomFactor(int zoom);

  int zoomFactor() const;

  void clearCaches();

  virtual QImage slide(int index) const;

  int currentSlide() const;

public slots:

  void setCurrentSlide(int index);

  void render();

  void showPrevious();

  void showNext();

  void showSlide(int index);
  
  void dataChanged();

signals:
  void itemActivated(int index);
  void inputReceived();
  void currentChanged(int index);
  void stop();

protected:
  void paintEvent(QPaintEvent *event);
  void keyPressEvent(QKeyEvent* event);
  void mouseMoveEvent(QMouseEvent* event);
  void mousePressEvent(QMouseEvent* event);
  void mouseReleaseEvent(QMouseEvent* event);
  void resizeEvent(QResizeEvent* event);
  void timerEvent(QTimerEvent* event);
};

