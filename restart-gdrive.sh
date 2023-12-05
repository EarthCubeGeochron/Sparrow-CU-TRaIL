#!/usr/bin/env bash
# Temporary script to restart the Sparrow GDrive mount.

mountpt=/projects/Sparrow-gdrive
#sudo rm -rf $mountpt # Requires password

if [ ! -d $mountpt ]; then
	mkdir $mountpt
	chmod 775 $mountpt
fi

# --allow-other: allows other users to connect to this mountpoint (a must)
# fusermount: option allow_other only allowed if 'user_allow_other' is set in /etc/fuse.conf

# Clear existing mount configuration, if any
fusermount -uz $mountpt

# Run the mount daemon
rclone mount Sparrow_gdrive: $mountpt --allow-other --daemon

