Provisioning a file hosting server
====================================

Create the ssh authorized keys file.

Edit /etc/ssh/sshd_config and change PermitRootLogin to without-password.
service ssh restart

hostname whatever
Edit /etc/hosts and put in FQDN in the appropriate places, for example::
    127.0.0.1       download.calibre-ebook.com download
    46.28.49.116    download.calibre-ebook.com download

echo "Asia/Kolkata" > /etc/timezone && dpkg-reconfigure -f noninteractive tzdata && ntpdate ntp.ubuntu.com
apt-get update
apt-get install vim nginx zsh python-lxml python-mechanize iotop htop smartmontools mosh git ntp vnstat vnstati
chsh -s /bin/zsh
mkdir -p /root/staging /root/work/vim /srv/download /srv/manual

Edit /etc/vnstat.conf and change the default interface to whatever the interface for
the server is and change the max bandwidth to 1024

service vnstat restart

export server=whatever
scp ~/.zshrc ~/.vimrc  $server:
scp -r ~/work/vim/zsh-syntax-highlighting $server:work/vim
scp -r ~/work/vim/zsh-history-substring-search $server:work/vim

cd /usr/local && git clone https://github.com/kovidgoyal/calibre.git
echo '#!/bin/sh\ncd /usr/local/calibre && git pull -q' > /usr/local/bin/update-calibre && chmod +x /usr/local/bin/update-calibre

Add the following to crontab::
    @hourly    /usr/bin/python /usr/local/calibre/setup/plugins_mirror.py
    @hourly    /usr/local/bin/update-calibre
    @hourly    /usr/bin/python /usr/local/calibre/setup/file-hosting-bw.py

If the server has a backup hard-disk, mount it at /mnt/backup and edit /etc/fstab so that it is auto-mounted.
Then, add the following to crontab::
    @daily     /usr/bin/rsync -ha /srv /mnt/backup
    @daily     /usr/bin/rsync -ha /etc /mnt/backup

Nginx
------

export server=whatever
ssh $server cat /etc/nginx/sites-available/default > /etc/nginx/sites-available/default
ssh $server cat /etc/nginx/mime.types > /etc/nginx/mime.types
rsync -avz $server:/srv/ /srv/
service nginx start


Services
---------

SSH into sourceforge and downloadbestsoftware so that their host keys are
stored.

   ssh -oStrictHostKeyChecking=no files.calibre-ebook.com echo done (and whatever other mirrors are present)
   ssh -oStrictHostKeyChecking=no kovid@mirror1.fosshub.com echo done
   ssh -oStrictHostKeyChecking=no kovidgoyal,calibre@frs.sourceforge.net

