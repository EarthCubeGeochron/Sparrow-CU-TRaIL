#!/usr/bin/env bash
# Temporary script to restart the Sparrow GDrive mount.

mountpt=/projects/Sparrow-gdrive
sudo rm -rf $mountpt # Requires password
mkdir $mountpt
chmod 775 $mountpt
rclone mount Sparrow_gdrive: $mountpt --allow-other --daemon

