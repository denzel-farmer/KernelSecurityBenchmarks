import os

# from tempfile import NamedTemporaryFile
# import tarfile 
import shutil
import shlex

import subprocess
# import atexit
import time

from microwave2.results.result import Result, ProcResult


from microwave2.utils.utils import Arch, get_arch_string_ubuntu_url, download_url, run_command, run_command_better, mount_device, umount, debug_pause, makedirs, mount_by_label, bind_mount, run_chroot_command
from microwave2.utils.qemu import QemuDrive, QemuCommand, QemuKernel, qemu_nbd_connect, qemu_nbd_disconnect, qemu_img_resize
from microwave2.local_storage import local_paths
import tempfile
import platform

from microwave2.utils.rsync import RsyncCommand

from microwave2.images.disk_image import DiskImage


class RawDiskImage(DiskImage):
    """Raw disk image for testing """
    def __init__(
            self,
            arch: Arch,
            image_name: str,
            temp_dir: str=None,
            output_dir: str=None,
            base_url: str=None) -> None:
        
        # Call parent constructor
        super().__init__(arch=arch, image_name=image_name, temp_dir=temp_dir, output_dir=output_dir)

    
    # API method override
    def download(self, redownload=False):
        print("[RawDiskImage] No download necessary for raw disk image")
        return Result.success()
   
    def install_elf_as_binary(self, elf_path: str) -> Result:
        """Strip ELF into raw binary and write to image"""
        # Strip the ELF into a raw binary
        bin_path = self.output_image_path()
        print("[RawDiskImage] Stripping ELF to binary")
        return run_command_better(["objcopy", "-O", "binary", elf_path, bin_path])     

    # API method from parent
    def construct(self, rebuild=False, editable=False) -> Result:
        """Construct 'image', but for now just touches a file because there is nothing to fill"""
        print("Constructing Raw image")
        # Error if already in edit mode
        if (self.is_editable()):
            print("Image is already in edit mode, can't construct")
            return Result.failure("Image is already in edit mode")

        # Touch output image 
        run_command(["touch", self.output_image_path()])
        print("Raw image constructed")

        # Call parent method, will set edit mode if editable
        return super().construct(rebuild=rebuild, editable=editable)
    

    def get_vga_memory_range(self):
        vga_con_begin = 0xb8000
        vga_con_end = vga_con_begin + 80 * 25 * 2
        return vga_con_begin, vga_con_end
        #vga_con_col = 80
        #dump_addr_begin = vga_con_begin + (9 * vga_con_col) * 2
        #dump_addr_end = dump_addr_begin + (7 * vga_con_col) * 2 - 1
        #return dump_addr_begin, dump_addr_end

    def boot_image(self, memory_mb=4096, cores=1, nographic=True, gdb_str: str = None, custom_kernel: QemuKernel=None):
        """Boot the image, return subprocess of image (does not wait)"""
        main_drive = QemuDrive(self.output_image_path(), format="raw", if_type=None, media="disk")

        qemu_cmd = QemuCommand(
            self.arch,
            drives=[main_drive],
            memory_mb=memory_mb,
            cores=cores,
            user_network=False,
            nographic=nographic,
            enable_kvm=False,
            kernel=custom_kernel, 
            gdb_str=gdb_str)

        print(qemu_cmd.build_command())
        process = qemu_cmd.run(redirect=True)
        return process


    # def boot_image(self, memory_mb=4096, cores=4, user_network=True, nographic=True, redirect=True, enable_kvm=False, custom_kernel: QemuKernel=None):
    #     """Boot the image, return subprocess of image (does not wait)"""
    #     main_drive = QemuDrive(self.output_image_path(), format="qcow2", media="disk")

    #     qemu_cmd = QemuCommand(
    #         self.arch,
    #         drives=[main_drive],
    #         memory_mb=memory_mb,
    #         cores=cores,
    #         user_network=user_network,
    #         nographic=nographic,
    #         enable_kvm=enable_kvm,
    #         kernel=custom_kernel)

    #     print(qemu_cmd.build_command())
    #     process = qemu_cmd.run(redirect=redirect)
    #     return process

    # def boot_interactive(self, enable_kvm=False):
    #     """Boot the image interactively"""
    #     process = self.boot_image(redirect=False, enable_kvm=enable_kvm)
    #     process.wait()


