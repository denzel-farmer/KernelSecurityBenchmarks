#!/bin/bash

# Boot arm image directly with a kernel image. Note that this doesn't require
# any EFI, because qemu directly loads from the -kernel file. It does require
# a separate chardev because as of right now arm images are configured to
# use ttyS0 rather than ttyAMA0.  

# TODO move all this into python

IMAGE_PATH=$1
CDROM_PATH=$2

SCRIPT_DIR="$(dirname "$(realpath "$0")")"
QEMU_EFI_PATH="$SCRIPT_DIR/QEMU_EFI.fd"



# Check both required arguments are provided
if [ -z "$IMAGE_PATH" ]; then
    echo "Usage: $0 <path_to_image> <cdrom_path (optional)>"
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

# Similarly, uses -pflash rather than -bios 

echo "Booting image $IMAGE_PATH..."
qemu-system-aarch64 \
    -nodefaults \
    -nographic \
    -machine virt \
    -cpu cortex-a57 \
    -m 4096 \
    -smp 4 \
    -bios "$QEMU_EFI_PATH" \
    -device virtio-blk-pci,drive=hd0 \
    -blockdev driver=file,node-name=hd_file,filename="$IMAGE_PATH" \
    -blockdev driver=qcow2,node-name=hd0,file=hd_file \
    -device virtio-net-pci,netdev=net1 \
    -netdev user,id=net1 \
    -serial stdio $CDROM_ARGS
