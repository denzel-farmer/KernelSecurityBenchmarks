#!/bin/bash

# Boot x86 via SeaBIOS

# TODO move all this into python

IMAGE_PATH=$1
CDROM_PATH=$2

# Check both required arguments are provided
if [ -z "$IMAGE_PATH" ] ; then
    echo "Usage: $0 <path_to_image> <path_to_cdrom (optional)>"
    exit 1
fi

# If cdrom path not provided, exclude it
if [ -z "$CDROM_PATH" ]; then
    CDROM_ARGS=""
else
    CDROM_ARGS="-drive file=$CDROM_PATH,media=cdrom"
fi

# Uses -device and -blockdev combo rather than -drive to be more explicit
# -device is what guest sees, -blockdev is how qemu processes data 


echo "Booting image $IMAGE_PATH..."
qemu-system-x86_64 \
    -enable-kvm \
    -nodefaults \
    -nographic \
    -m 8192 \
    -smp 4 \
    -device virtio-blk-pci,drive=hd0 \
    -blockdev driver=file,node-name=hd_file,filename="$IMAGE_PATH" \
    -blockdev driver=qcow2,node-name=hd0,file=hd_file \
    -device virtio-net-pci,netdev=net1 \
    -netdev user,id=net1 \
    -serial mon:stdio $CDROM_ARGS

