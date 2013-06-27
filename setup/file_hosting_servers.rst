Provisioning a file hosting server
====================================

Create the ssh authorized keys file.

Edit /etc/ssh/sshd_config and change PermitRootLogin to without-password.
Restart sshd.

apt-get install vim nginx zsh python-lxml python-mechanize iotop htop smartmontools
chsh -s /bin/zsh

mkdir -p /root/staging /root/work/vim /srv/download /srv/manual

scp .zshrc .vimrc  server:
scp -r ~/work/vim/zsh-syntax-highlighting server:work/vim

If the server has a backup hard-disk, mount it at /mnt/backup and edit /etc/fstab so that it is auto-mounted.
Then, add the following to crontab
@daily     /usr/bin/rsync -ha /srv /mnt/backup
@daily     /usr/bin/rsync -ha /etc /mnt/backup

Nginx
------

Copy over /etc/nginx/sites-available/default from another file server. When
copying, remember to use cat instead of cp to preserve hardlinks (the file is a
hardlink to /etc/nginx/sites-enabled/default)

rsync /srv from another file server

service nginx start

