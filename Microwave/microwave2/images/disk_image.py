import os

# from tempfile import NamedTemporaryFile
# import tarfile 
import shutil
import shlex

import subprocess
# import atexit
import time

from microwave2.results.result import Result


from microwave2.utils.utils import Arch, get_arch_string_ubuntu_url, download_url, run_command, mount_device, umount, debug_pause
from microwave2.utils.qemu import QemuDrive, QemuCommand, qemu_nbd_connect, qemu_nbd_disconnect
from microwave2.local_storage import local_paths
from microwave2.images.ubuntu_resources import get_userdata,METADATA,CLOUD_IMG_URL_X86,CLOUD_IMG_URL_ARM,build_bash_profile
import tempfile
import platform

# TODO make a generic DiskImage class 
# Provide functions: 
# - init 
# - download (download dependencies if they exist)
# - construct (maybe wrapped by generator?)
# - finish_edit 
class DiskImage:
    # Temp_dir is a directory to store intermediate files (like a template image, seed ISO, or mountpoint)
    # output_dir is the directory to place constructed images 
    def __init__(self,
                 arch: Arch, 
                 image_name: str,
                 temp_dir: str=None,
                 output_dir: str=None):
        
        self.arch = arch
        self.image_name = image_name
        self.temp_workdir = local_paths.get_temp_dir() if temp_dir is None else temp_dir
        self.output_dir = local_paths.get_workdir() if output_dir is None else output_dir

        # Used to make sure the image is only modified once, and not booted while being modified
        self.edit_mode = False


    def get_image_name(self):
        return self.image_name
    
    def output_image_path(self):
        """Path to the local image file"""
        return os.path.join(self.output_dir, self.image_name)

    def is_editable(self):
        return self.edit_mode

    def download(self):
        """Pre-download any dependencies require to construct the image"""
        raise NotImplementedError("download method should be overridden in a subclass")
    
    def construct(self, rebuild=False, editable=False) -> Result:
        """Construct the image, placing in the output directory
        - rebuild: Reconstruct image from scratch
        - editable: Leave image in 'editable' state, must call finish_edit() before booting
        - should be overriden, but called to manage edit mode
        """
        # If 'editable' is set, mark the image as being edited
        if (editable):
            self.edit_mode = True

        return Result.success()
    
    def finish_edit(self):
        """Finish editing the image, and prepare for booting, should be overriden but called"""
        if (not self.edit_mode):
            print("[DiskImage] Image is not in edit mode")
            return Result.failure("Image is not in edit mode")
        
        self.edit_mode = False

        return Result.success()
       
