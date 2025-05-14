#!/bin/bash

IMAGE_PATH=$1
CDROM_PATH=$2
LOG_PATH=$3

# Check both required arguments are provided
if [ -z "$IMAGE_PATH" ] ; then
    echo "Usage: $0 <path_to_image> <path_to_cdrom (optional)>"
    exit 1
fi

# If log path not provided, set to default
if [ -z "$LOG_PATH" ]; then
    LOG_PATH="/tmp/qemu_log.txt"
fi

# If cdrom path not provided, exclude it
if [ -z "$CDROM_PATH" ]; then
    CDROM_ARGS=""
else
    CDROM_ARGS="-drive file=$CDROM_PATH,media=cdrom"
fi

# Uses -device and -blockdev combo rather than -drive to be more explicit
# -device is what guest sees, -blockdev is how qemu processes data 
CORESET="2,3,4,5"

echo "Booting image $IMAGE_PATH..."
taskset -c $CORESET qemu-system-x86_64 \
    -enable-kvm \
    -nodefaults \
    -cpu host \
    -nographic \
    -m 8192 -mem-prealloc \
    -smp 8,sockets=1,cores=8,threads=1 \
    -device virtio-blk-pci,drive=hd0 \
    -blockdev driver=file,node-name=hd_file,filename="$IMAGE_PATH" \
    -blockdev driver=qcow2,node-name=hd0,file=hd_file \
    -device virtio-net-pci,netdev=net1 \
    -netdev user,id=net1,hostfwd=tcp::2222-:22 \
    -serial mon:stdio $CDROM_ARGS \
    -chardev file,id=log0,path=$LOG_PATH \
    -device virtio-serial-pci,id=virtio-serial0 \
    -device virtserialport,chardev=log0,name=host-port,bus=virtio-serial0.0
