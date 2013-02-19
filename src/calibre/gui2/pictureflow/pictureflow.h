/****************************************************************************
**
* (C) Copyright 2007 Trolltech ASA  
*  All rights reserved.
**
* This is version of the Pictureflow animated image show widget modified by Trolltech ASA.
*
*
* Redistribution and use in source and binary forms, with or without
* modification, are permitted provided that the following conditions are met:
*     * Redistributions of source code must retain the above copyright
*       notice, this list of conditions and the following disclaimer.
*     * Redistributions in binary form must reproduce the above copyright
*       notice, this list of conditions and the following disclaimer in the
*       documentation and/or other materials provided with the distribution.
*     * Neither the name of the <organization> nor the
*       names of its contributors may be used to endorse or promote products
*       derived from this software without specific prior written permission.
*
* THIS SOFTWARE IS PROVIDED BY TROLLTECH ASA ``AS IS'' AND ANY
* EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
* WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
* DISCLAIMED. IN NO EVENT SHALL <copyright holder> BE LIABLE FOR ANY
* DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
* (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
* LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
* ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
* (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
* SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

****************************************************************************/
/*
  ORIGINAL COPYRIGHT HEADER
  PictureFlow - animated image show widget
  http://pictureflow.googlecode.com

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

#pragma once

#include <QWidget>

class FlowImages : public QObject
{
Q_OBJECT

public:
	virtual int count();
	virtual QImage image(int index);
	virtual QString caption(int index);
    virtual QString subtitle(int index);

signals:
	void dataChanged();

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

  Q_PROPERTY(int currentSlide READ currentSlide WRITE setCurrentSlide)
  Q_PROPERTY(QSize slideSize READ slideSize WRITE setSlideSize)
  Q_PROPERTY(QFont subtitleFont READ subtitleFont WRITE setSubtitleFont)

public:
  /*!
    Creates a new PictureFlow widget.
  */  
  PictureFlow(QWidget* parent = 0, int queueLength = 3);

  /*!
    Destroys the widget.
  */
  ~PictureFlow();

  /*!
    Set the images to be displayed by this widget.
  */
  void setImages(FlowImages *images);
  
  /*!
    Returns the dimension of each slide (in pixels).
  */  
  QSize slideSize() const;

  /*!
    Sets the dimension of each slide (in pixels). Do not use this method directly
    instead use resize which automatically sets an appropriate slide size.
  */  
  void setSlideSize(QSize size);

  /*!
    Turn the reflections on/off.
  */  
  void setShowReflections(bool show);
  bool showReflections() const;

  /*!
    Returns the font used to render subtitles
  */  
  QFont subtitleFont() const;

  /*!
    Sets the font used to render subtitles
  */  
  void setSubtitleFont(QFont font);


  /*!
    Clears any caches held to free up memory
  */
  void clearCaches();

  /*!
    Returns QImage of specified slide.
    This function will be called only whenever necessary, e.g. the 100th slide
    will not be retrived when only the first few slides are visible.
  */  
  virtual QImage slide(int index) const;

  /*!
    Returns the index of slide currently shown in the middle of the viewport.
  */  
  int currentSlide() const;

public slots:

  /*!
    Sets slide to be shown in the middle of the viewport. No animation 
    effect will be produced, unlike using showSlide.
  */  
  void setCurrentSlide(int index);

  /*!
    Rerender the widget. Normally this function will be automatically invoked
    whenever necessary, e.g. during the transition animation.
  */
  void render();

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
    Clear all caches and redraw
  */
  void dataChanged();
  
  void emitcurrentChanged(int index);

signals:
  void itemActivated(int index);
  void inputReceived();
  void currentChanged(int index);
  void stop(); //Emitted when the user presses the Esc key

protected:
  void paintEvent(QPaintEvent *event);
  void keyPressEvent(QKeyEvent* event);
  void mouseMoveEvent(QMouseEvent* event);
  void mousePressEvent(QMouseEvent* event);
  void mouseReleaseEvent(QMouseEvent* event);
  void resizeEvent(QResizeEvent* event);
  void timerEvent(QTimerEvent* event);

private:
  PictureFlowPrivate* d;
};

