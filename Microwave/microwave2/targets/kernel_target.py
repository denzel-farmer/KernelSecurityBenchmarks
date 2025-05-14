from microwave2.remote import GitConfig, GitRemoteCode, RemoteCode
from microwave2.utils.utils import dynamic_script_load, Arch, BuildConfig, makedirs, debug_pause, timed
from microwave2.local_storage import local_paths, rel_path
from dataclasses import dataclass

from microwave2.utils.log import log, warn, error, debug, info
from microwave2.utils.rsync import RsyncCommand

from microwave2.utils.kernel_config import Kconfig, generate_kconfig



from microwave2.targets.target import Target, TargetConfig

from microwave2.images.disk_image import DiskImage
from microwave2.images.ubuntu_image import UbuntuDiskImage

from microwave2.results.result import Result, ProcResult

import os

from microwave2.utils.linux_make import LinuxMakeCommand
from microwave2.utils.linux_kernel import LinuxKernel


class KernelTargetConfig(TargetConfig):
    """Configuration for kernel target"""
    def __init__(self, target_name: str, exec_arch: Arch, worker_arch: Arch, git_config: GitConfig, kconfig: Kconfig, target_subdir: str = None, sparse_download: bool = False):
        super().__init__(target_name=target_name, exec_arch=exec_arch, worker_arch=worker_arch, git_config=git_config, target_subdir=target_subdir, sparse_download=sparse_download)
        self.kconfig = kconfig



class KernelTarget(Target):
    """Target that is a full kernel"""
    def __init__(self, target_config: KernelTargetConfig):

        super().__init__(target_config)
        
       # # Assumes kernel directory is target_local_path/linux_subdir
        # if (linux_subdir is not None):
        #     self.kernel_dir = os.path.join(self.target_local_path, linux_subdir)
        # else:
        self.kernel_dir = self.target_local_path
        self.kconfig = target_config.kconfig

        self.linux_kernel = None # empty until after clone
    def get_kernel_dir(self):
        return self.kernel_dir
    
    @timed
    def download(self):
        """Download target code from remote"""
        try:
            self.setup_repo()
        except Exception as e:
            print(f"[Test] Failed to setup repo: {str(e)}")
            print(f"Exception type: {type(e).__name__}")
            print(f"Exception args: {e.args}")
            return Result.failure("Failed to setup repo")

        result = self.update_local(sparse=self.target_config.sparse_download)
        if (result.is_failure()):
            print("[KernelTarget] Failed to update local repo")
            return result
    
    #   # Get target arch by checking armpls in repo local path
    #     armpls_path = os.path.join(self.repo_local_path, ".armpls")
    #     exec_arch = Arch.ARM
    #     if (os.path.exists(armpls_path)):
    #         exec_arch = Arch.ARM
    #         # just die
    #     #     warn("[KernelModuleTarget] armpls file found, but not implemented yet")
    #     #    exit(0)
    #     #    raise Exception("KernelModuleTarget: armpls file found, but not implemented yet")
        # self.target_config.exec_arch = exec_arch # TODO shouldn't be overwriting this, and should make sure this doesn't affect arch dependent tests
        # info(f"[KernelModuleTarget] Target arch: {exec_arch}")
        

        self.linux_kernel = LinuxKernel(source_dir=self.kernel_dir, build_dir=self.build_dir, target_arch=self.target_config.exec_arch, kconfig=self.kconfig)

        return result
   
    @timed
    def build(self, rebuild=False, build_callback=None, mod_prep:bool=True) -> Result:
        # TODO build kernel for correct architecture
        # TODO make rebuild flag actually do something
    
        if (build_callback is not None):
            # Callback in case tester wants to modify target before building, should modify self.build_dir
            result = build_callback(self)
            print(f"[KernelTarget] Build callback result: {build_callback}")
            if (result.is_failure()):
                return result

        # TODO this feels weird, why do we do this?
        if (mod_prep):
            # Prepare kernel for module build
            print("[KernelTarget] Preparing kernel for module build")
            result = self.linux_kernel.build_for_module()
            if (result.is_failure()):
                print("[KernelTarget] Failed to prepare kernel for module build")
                return result
            
        # Build kernel
        result = self.linux_kernel.build(force_rebuild=rebuild)
        if (result.is_failure()):
            print("[KernelTarget] Failed to build kernel")
            return result

        debug_pause("[KernelTarget] kernel build finished")
        return result
    
    @timed
    def install(self, test_image: UbuntuDiskImage, copy_source:bool=False) -> Result:
        """Install into disk image. Could mount and directly set install location to mounted image, but 
        to let DiskImage manage itself instead we install in a tmp directory and then rsync it to the image"""

        # Make temp install directory, deleting previous install if it exists
        install_dir = os.path.join(self.temp_dir, "install")
        makedirs(install_dir, delete=True)

        result = self.linux_kernel.install(install_dir)
        if (result.is_failure()):
            print("[KernelTarget] Failed to install kernel")
            return result

        # Second phase: install compiled products to image (could do all at once in single rsync?)
        # TODO don't need to delete other contents, but would need to update grub
        # result = test_image.sync_folder(temp_boot_dir, "/boot", delete_contents=True)
        # if (result.is_failure()):
        #     print("[KernelTarget] Failed to install to image")
        #     return result

        boot_dir = self.linux_kernel.get_install_boot_dir(install_dir)
        result = test_image.override_kernel(boot_dir)
        if (result.is_failure()):
            print("[KernelTarget] Failed to install kernel to image")
            return result
        
        usr_dir = self.linux_kernel.get_install_usr_dir(install_dir)
        result = test_image.sync_folder(usr_dir, "/usr")
        if (result.is_failure()):
            print("[KernelTarget] Failed to install to image")
            return result
        
        lib_dir = self.linux_kernel.get_install_lib_dir(install_dir)
        result = test_image.sync_folder(lib_dir, "/lib")
        if (result.is_failure()):
            print("[KernelTarget] Failed to install to image")
            return result

        # Final phase: Copy all source code and build products to image
        
        # target_img_dir = os.path.join("/target", self.target_config.target_name)

        # Copy all target source (not just kernel)
      #  if (copy_source):
      #      result = test_image.sync_folder(self.target_local_path, target_img_dir)
      #      if (result.is_failure()):
      #          print("[KernelTarget] Failed to install target source")
      #          return result

      # Copy all build products to /target/build
        # target_img_build_dir = os.path.join(target_img_dir, "build")
        # result = test_image.sync_folder(self.build_dir, target_img_build_dir)
        # if (result.is_failure()):
        #     print("[KernelTarget] Failed to install build products")
        #     return result
        
        # # Clean up temp install directory
        # makedirs(self.temp_dir, delete=True)

        debug_pause("[KernelTarget] successfully installed to image")
        return Result.success()
