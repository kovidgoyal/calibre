Provisioning a file hosting server
====================================

Create the ssh authorized keys file.

Edit /etc/ssh/sshd_config and change PermitRootLogin to without-password.
Restart sshd.

hostname whatever
Edit /etc/hosts and put in FQDN in the appropriate places, for example::
    27.0.1.1       download.calibre-ebook.com download
    46.28.49.116 download.calibre-ebook.com download

dpkg-reconfigure tzdata
set timezone to Asia/Kolkata
service cron restart

apt-get install vim nginx zsh python-lxml python-mechanize iotop htop smartmontools mosh git
chsh -s /bin/zsh

mkdir -p /root/staging /root/work/vim /srv/download /srv/manual

scp .zshrc .vimrc  server:
scp -r ~/work/vim/zsh-syntax-highlighting server:work/vim
scp -r ~/work/vim/zsh-history-substring-search server:work/vim
cd /usr/local && git clone https://github.com/kovidgoyal/calibre.git

Add the following to crontab::
    @hourly    /usr/bin/python /usr/local/calibre/setup/plugins_mirror.py

If the server has a backup hard-disk, mount it at /mnt/backup and edit /etc/fstab so that it is auto-mounted.
Then, add the following to crontab::
    @daily     /usr/bin/rsync -ha /srv /mnt/backup
    @daily     /usr/bin/rsync -ha /etc /mnt/backup

Nginx
------

Copy over /etc/nginx/sites-available/default from another file server. When
copying, remember to use cat instead of cp to preserve hardlinks (the file is a
hardlink to /etc/nginx/sites-enabled/default)

Also copy over /etc/nginx/mime.types

rsync /srv from another file server

service nginx start

Services
---------

SSH into sourceforge and downloadbestsoftware so that their host keys are
stored.

   ssh -oStrictHostKeyChecking=no kovid@mirror1.fosshub.com
   ssh -oStrictHostKeyChecking=no kovidgoyal,calibre@frs.sourceforge.net
   ssh -oStrictHostKeyChecking=no files.calibre-ebook.com (and whatever other mirrors are present)

