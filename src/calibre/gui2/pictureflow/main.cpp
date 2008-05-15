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

#include <qapplication.h>
#include <qdir.h>
#include <qevent.h>
#include <qfileinfo.h>
#include <qimage.h>

#if QT_VERSION >= 0x040000
#include <QTime>
#endif

#include "pictureflow.h"

QStringList findFiles(const QString& path = QString())
{
  QStringList files;

  QDir dir = QDir::current();
  if(!path.isEmpty())
    dir = QDir(path);

  dir.setFilter(QDir::Files | QDir::Hidden | QDir::NoSymLinks);
#if QT_VERSION >= 0x040000
  QFileInfoList list = dir.entryInfoList();
  for (int i = 0; i < list.size(); ++i)
  {
    QFileInfo fileInfo = list.at(i);
    files.append(dir.absoluteFilePath(fileInfo.fileName()));
  }
#else
  const QFileInfoList* list = dir.entryInfoList();
  if(list)
  {
    QFileInfoListIterator it( *list );
    QFileInfo * fi;
    while( (fi=it.current()) != 0 )
    {
      ++it;
      files.append(dir.absFilePath(fi->fileName()));
    }
  }
#endif

  return files;
}

#if QT_VERSION < 0x040000
#define modifiers state
#define AltModifier AltButton
#define setWindowTitle setCaption
#endif

#if QT_VERSION < 0x030000
#define flush flushX
#endif

class Browser: public PictureFlow
{
public:
  Browser(): PictureFlow()
  {
    setWindowTitle("PictureFlow");
  }

  void keyPressEvent(QKeyEvent* event)
  {
    if(event->key() == Qt::Key_Escape || event->key() == Qt::Key_Enter ||
      event->key() == Qt::Key_Return)
      {
        event->accept();
        close();
      }

    // checking the speed of rendering
    if(event->key() == Qt::Key_F10)
    if(event->modifiers() == Qt::AltModifier)
    {
      qDebug("benchmarking.... please wait");
      const int blit_count = 10;

      QTime stopwatch;
      stopwatch.start();
      for(int i = 0; i < blit_count; i++)
      {
        render(); repaint(); QApplication::flush(); QApplication::syncX();
        render(); repaint(); QApplication::flush(); QApplication::syncX();
        render(); repaint(); QApplication::flush(); QApplication::syncX();
        render(); repaint(); QApplication::flush(); QApplication::syncX();
        render(); repaint(); QApplication::flush(); QApplication::syncX();
        render(); repaint(); QApplication::flush(); QApplication::syncX();
        render(); repaint(); QApplication::flush(); QApplication::syncX();
        render(); repaint(); QApplication::flush(); QApplication::syncX();
        render(); repaint(); QApplication::flush(); QApplication::syncX();
        render(); repaint(); QApplication::flush(); QApplication::syncX();
      }
      QString msg;
      int elapsed = stopwatch.elapsed();
      if( elapsed > 0 )
        msg = QString("FPS: %1").arg( blit_count*10*1000.0/elapsed );
      else
        msg = QString("Too fast. Increase blit_count");
      setWindowTitle( msg );
      event->accept();
      return;
    }

    // for debugging only: Alt+F11 cycles the reflection effect
    if(event->key() == Qt::Key_F11)
    if(event->modifiers() == Qt::AltModifier)
    {
      qDebug("changing reflection effect...");
      switch(reflectionEffect())
      {
        //case NoReflection:      setReflectionEffect(PlainReflection); break;
        case PlainReflection:   setReflectionEffect(BlurredReflection); break;
        case BlurredReflection: setReflectionEffect(PlainReflection); break;
        default:                setReflectionEffect(PlainReflection); break;
      }
      event->accept();
      return;
    }

    PictureFlow::keyPressEvent(event);
  }
};

int main( int argc, char ** argv )
{
  QApplication* app = new QApplication( argc, argv );
  Browser* w = new Browser;

#if defined(_WS_QWS) || defined(Q_WS_QWS)
  w->showFullScreen();
  int ww = w->width();
  int wh = w->height();
  int dim = (ww > wh) ? wh : ww;
  dim = dim * 3 / 4;
  w->setSlideSize(QSize(3*dim/5, dim));
#else
  w->setSlideSize(QSize(3*80, 5*80));
  w->resize(750, 470);
#endif

  QStringList files = (argc > 1) ? findFiles(QString(argv[1])) : findFiles();

  for(int i = 0; i < (int)files.count(); i++)
    w->addSlide(new FileDelayedImage(files[i]));

  w->setCenterIndex(w->slideCount()/2);
  w->setBackgroundColor(Qt::white);
  w->show();

  app->connect( app, SIGNAL(lastWindowClosed()), app, SLOT(quit()) );
  int result = app->exec();

  delete w;
  delete app;

  return result;
}
