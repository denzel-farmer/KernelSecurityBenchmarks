#!/bin/bash

# Boot x86 image directly with a kernel image. Note that this doesn't require
# any EFI/bios, because qemu directly loads from the -kernel file. 

# TODO move all this into python

IMAGE_PATH=$1
KERNEL_PATH=$2
KERNEL_ARGS=$3

# Set so commands echo
set -x

# Check both required arguments are provided
if [ -z "$IMAGE_PATH" ] || [ -z "$KERNEL_PATH" ]; then
    echo "Usage: $0 <path_to_image> <path_to_kernel> <kernel_args>"
    exit 1
fi

# If kernel args not provided, set to default
if [ -z "$KERNEL_ARGS" ]; then
    KERNEL_ARGS="console=ttyS0 root=/dev/vda1"
fi

# # Add nokaslr to kernel args
# KERNEL_ARGS="$KERNEL_ARGS nokaslr"

# Uses -device and -blockdev combo rather than -drive to be more explicit
# -device is what guest sees, -blockdev is how qemu processes data 


echo "Booting image $IMAGE_PATH (with kernel at $KERNEL_PATH)..."
qemu-system-x86_64 \
    -enable-kvm \
    -nodefaults \
    -nographic \
    -m 8192 \
    -smp 8 \
    -kernel $KERNEL_PATH \
    -append "$KERNEL_ARGS" \
    -device virtio-blk-pci,drive=hd0 \
    -blockdev driver=file,node-name=hd_file,filename="$IMAGE_PATH" \
    -blockdev driver=qcow2,node-name=hd0,file=hd_file \
    -device virtio-net-pci,netdev=net1 \
    -netdev user,id=net1 \
    -serial stdio \
    -s