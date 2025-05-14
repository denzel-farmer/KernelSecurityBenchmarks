#!/bin/bash

# Boot x86 via SeaBIOS

# TODO move all this into python

IMAGE_PATH=$1
CDROM_PATH=$2

# Check both required arguments are provided
if [ -z "$IMAGE_PATH" || -z "$CDROM_PATH" ]; then
    echo "Usage: $0 <path_to_image> <path_to_cdrom>"
    exit 1
fi

# Uses -device and -blockdev combo rather than -drive to be more explicit
# -device is what guest sees, -blockdev is how qemu processes data 


echo "Booting image $IMAGE_PATH..."
qemu-system-x86_64 \
    -nodefaults \
    -nographic \
    -m 4096 \
    -smp 4 \
    -drive file=$IMAGE_PATH,format=qcow2,media=disk \
    -device virtio-net-pci,netdev=net1 \
    -netdev user,id=net1 \
    -drive file=$CDROM_PATH,media=cdrom \
    -serial stdio