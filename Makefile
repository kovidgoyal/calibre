APIDOCS=/var/www/libprs500.kovidgoyal.net/htdocs/apidocs
targets:
	@echo Targets are: installer doc

installer:
	@scp dist/libprs500-*.exe castalia:/var/www/vhosts/kovidgoyal.net/subdomains/libprs500/httpdocs/downloads/
	@ssh castalia chmod a+r /var/www/vhosts/kovidgoyal.net/subdomains/libprs500/httpdocs/downloads/\*
	@echo Update link on the libprs500 wiki

doc:
	epydoc --config epydoc.conf
	cp -r docs/html ${APIDOCS}/
	epydoc -v --config epydoc-pdf.conf
	cp docs/pdf/api.pdf ${APIDOCS}/
