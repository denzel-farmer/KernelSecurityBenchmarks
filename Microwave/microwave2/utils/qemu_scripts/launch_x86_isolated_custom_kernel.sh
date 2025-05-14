#!/bin/bash

# Boot x86 image directly with a kernel image. Note that this doesn't require
# any EFI/bios, because qemu directly loads from the -kernel file. 

# TODO move all this into python

IMAGE_PATH=$1
KERNEL_PATH=$2
LOG_PATH=$3
# TODO pass these properly
# KERNEL_ARGS='console=ttyS0,115200 earlyprintk=serial,ttyS0,115200 ignore_loglevel root=/dev/vda1'
KERNEL_ARGS="${*:4}"

echo "IMAGE_PATH: $IMAGE_PATH"
echo "KERNEL_PATH: $KERNEL_PATH"
echo "LOG_PATH: $LOG_PATH"
echo "KERNEL_ARGS: $KERNEL_ARGS"

# exit 0

# Set so commands echo
set -x

# Check both required arguments are provided
if [ -z "$IMAGE_PATH" ] || [ -z "$KERNEL_PATH" ]; then
    echo "Usage: $0 <path_to_image> <path_to_kernel> <kernel_args>"
    exit 1
fi

# # If kernel args wrapped in double or single quotes, remove them
# if [[ "$KERNEL_ARGS" == \"*\" ]]; then
#     KERNEL_ARGS="${KERNEL_ARGS:1:-1}"
# elif [[ "$KERNEL_ARGS" == \'*\" ]]; then
#     KERNEL_ARGS="${KERNEL_ARGS:1:-1}"
# fi


# # If kernel args not provided, set to default
# if [ -z "$KERNEL_ARGS" ]; then
#     KERNEL_ARGS="console=ttyS0 root=/dev/vda1"
# fi

# # Add nokaslr to kernel args
# KERNEL_ARGS="$KERNEL_ARGS nokaslr"

# Uses -device and -blockdev combo rather than -drive to be more explicit
# -device is what guest sees, -blockdev is how qemu processes data 
CORESET="2,3,4,5"


echo "Booting image $IMAGE_PATH (with kernel at $KERNEL_PATH)..."
taskset -c $CORESET qemu-system-x86_64 \
    -enable-kvm \
    -nodefaults \
    -nographic \
    -m 8192 -mem-prealloc \
    -cpu host \
    -smp 8,sockets=1,cores=8,threads=1 \
    -kernel $KERNEL_PATH \
    -append "$KERNEL_ARGS" \
    -device virtio-blk-pci,drive=hd0 \
    -blockdev driver=file,node-name=hd_file,filename="$IMAGE_PATH" \
    -blockdev driver=qcow2,node-name=hd0,file=hd_file \
    -device virtio-net-pci,netdev=net1 \
    -netdev user,id=net1,hostfwd=tcp::2223-:22 \
    -serial stdio \
    -s \
    -chardev file,id=log0,path=$LOG_PATH \
    -device virtio-serial-pci,id=virtio-serial0 \
    -device virtserialport,chardev=log0,name=host-port,bus=virtio-serial0.0
