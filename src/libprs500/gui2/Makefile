main_ui.py : main.ui
	pyuic4 main.ui | sed -s s/^.*Margin.*// | sed -e s/^.*boxlayout\.setObjectName.*// > main_ui.py

images_rc.py : images.qrc
	pyrcc4 images.qrc > images_rc.py

clean :
	rm main_ui.py images_rc.py
