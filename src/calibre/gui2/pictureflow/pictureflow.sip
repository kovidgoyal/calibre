//Define the SIP wrapper to the pictureflow widget
//Author - Kovid Goyal <kovid@kovidgoyal.net>

%Module(name=pictureflow, version=1)

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
  virtual QString subtitle(int index);

signals:
  void dataChanged();

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

  QFont subtitleFont() const;

  void setSubtitleFont(QFont font);

  void clearCaches();

  virtual QImage slide(int index) const;

  int currentSlide() const;

  bool showReflections() const;

  void setShowReflections(bool show);

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

