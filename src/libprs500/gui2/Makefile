all : main_ui.py images_rc.py

main_ui.py : main.ui
	pyuic4 main.ui > main_ui.py

images_rc.py : images.qrc images
	pyrcc4 images.qrc > images_rc.py

clean :
	rm main_ui.py images_rc.py

test : all
	python main.py
