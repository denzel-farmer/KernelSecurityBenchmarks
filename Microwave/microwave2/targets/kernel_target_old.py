from microwave2.remote import GitConfig, GitRemoteCode, RemoteCode
from microwave2.utils.utils import dynamic_script_load, Arch, BuildConfig, makedirs, debug_pause, timed
from microwave2.local_storage import local_paths, rel_path
from dataclasses import dataclass
from microwave2.utils.rsync import RsyncCommand


from microwave2.targets.target import Target, TargetConfig

from microwave2.images.disk_image import DiskImage
from microwave2.images.ubuntu_image import UbuntuDiskImage

from microwave2.results.result import Result, ProcResult

import os

from microwave2.utils.linux_make import LinuxMakeCommand
from microwave2.utils.linux_kernel import LinuxKernel

class KernelTarget(Target):
    """Target that is a full kernel"""
    def __init__(self, target_config: TargetConfig):

        super().__init__(target_config)
        
       # # Assumes kernel directory is target_local_path/linux_subdir
        # if (linux_subdir is not None):
        #     self.kernel_dir = os.path.join(self.target_local_path, linux_subdir)
        # else:
        self.kernel_dir = self.target_local_path

        # Make command for repeat use
        self.make_command = LinuxMakeCommand(kernel_dir=self.kernel_dir,
                                             exec_arch=self.target_config.exec_arch,
                                             build_arch=self.target_config.worker_arch,
                                             output_dir=self.build_dir,
                                             default_verbose=True)

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

        return self.update_local(sparse=self.target_config.sparse_download)

    @timed
    def configure(self) -> Result:
        # TODO add more configurability, for now just make defconfig for specified architecture
        print("[KernelTarget] Configuring kernel")
        result = self.make_command.make_defconfig()
        if (result.is_failure()):
            print("[KernelTarget] Failed to configure kernel")
            print(result)
        
        return result

    # def modules_prepare(self) -> Result:
    #     # Prepare kernel for module build: make configure, modules_prepare
    #     print("[KernelTarget] Preparing kernel for module build")
    #     result = self.configure()
    #     if (result.is_failure()):
    #         return result
        
    #     result = self.make_command.make_modules_prepare()
    #     if (result.is_failure()):
    #         print("[KernelTarget] Failed to prepare kernel for module build")
    #         print(result)
        
    #     return result
    #     # except BuildError as e:
    #     #     print(f"Failed to prepare kernel for module build: {e}")
    #     #     return Result.failure(f"Failed to prepare kernel for module build: {e}")
    #     # return Result.success()
        
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

        # Configure kernel
        result = self.configure()
        if (result.is_failure()):
            print("[KernelTarget] Failed to configure kernel")
            return result
        
        if mod_prep:
            # Prepare kernel for module build
            print("[KernelTarget] Preparing kernel for module build")
            result = self.make_command.make_modules_prepare()
            if (result.is_failure()):
                print("[KernelTarget] Failed to prepare kernel for module build")
                return result



        # Build kernel
        print("[KernelTarget] Building kernel")
        result = self.make_command.make()
        if (result.is_failure()):
            print("[KernelTarget] Failed to build kernel")
        else: 
            print("[KernelTarget] Kernel built successfully")

        debug_pause("KernelTarget build finished")
        return result
    
    # @timed
    # def header_install(self, output_dir: str):
    #     "Install kernel headers to an output directory (will place in output_dir/include)"
    #     # Install headers to output directory
    #     makedirs(output_dir)
    #     print(f"Installing headers to {output_dir}")
    #     # try:
    #     result = self.make_command.make_headers_install(output_dir)
    #     if (result.is_failure()):
    #         print("[KernelTarget] Failed to install headers")
    #         print(result)
    #     else:
    #         print("[KernelTarget] Headers installed successfully")
    #     return result
    #     # except BuildError as e:
    #     #     print(f"Failed to install headers: {e}")
    #     #     return Result.failure(f"Failed to install headers: {e}")
        
    #     # print("[KernelTarget] Headers installed successfully")
    #     # return Result.success()

    @timed
    def install(self, test_image: UbuntuDiskImage, copy_source:bool=True) -> Result:
        """Install into disk image. Could mount and directly set install location to mounted image, but 
        to let DiskImage manage itself instead we install in a tmp directory and then rsync it to the image"""

        # Make temp install directory, deleting previous install if it exists
        install_dir = os.path.join(self.temp_dir, "install")
        makedirs(install_dir, delete=True)

        # First phase: install products to install_dir

        # Install kernel to install_dir/boot 
        # TODO this doesn't actually work, because /boot gets mounted from partition 16 (at least for x86), overwriting the kernel
        # TODO need to update grub to point to new kernel
        temp_boot_dir = os.path.join(install_dir, "boot")
        makedirs(temp_boot_dir)
        result = self.make_command.make_install(install_path=temp_boot_dir)
        if (result.is_failure()):
            print("[KernelTarget] Failed to install kernel")
            return result

        # Install headers to install_dir/usr
        temp_usr_dir = os.path.join(install_dir, "usr")
        makedirs(temp_usr_dir)
        result = self.make_command.make_headers_install(install_hdr_path=temp_usr_dir)
        if (result.is_failure()):
            print("[KernelTarget] Failed to install headers")
            return result

        # Install modules to install_dir/lib/modules/$(KERNELRELEASE)/kernel/
        # temp_lib_modules_dir = os.path.join(install_dir, "lib", "modules")
        result = self.make_command.make_modules_install(install_mod_path=install_dir)
        if (result.is_failure()):
            print("[KernelTarget] Failed to install modules")
            return result
        
        debug_pause("[KernelTarget] successfully installed to temporary directory")

        # Second phase: install compiled products to image (could do all at once in single rsync?)
        # TODO don't need to delete other contents, but would need to update grub
        # result = test_image.sync_folder(temp_boot_dir, "/boot", delete_contents=True)
        # if (result.is_failure()):
        #     print("[KernelTarget] Failed to install to image")
        #     return result

        result = test_image.replace_kernel(temp_boot_dir)
        if (result.is_failure()):
            print("[KernelTarget] Failed to install kernel to image")
            return result
        
        result = test_image.sync_folder(temp_usr_dir, "/usr")
        if (result.is_failure()):
            print("[KernelTarget] Failed to install to image")
            return result
        
        temp_lib_dir = os.path.join(install_dir, "lib")
        result = test_image.sync_folder(temp_lib_dir, "/lib")
        if (result.is_failure()):
            print("[KernelTarget] Failed to install to image")
            return result

        # Final phase: Copy all source code and build products to image
        
        target_img_dir = os.path.join("/target", self.target_config.target_name)

        # Copy all target source (not just kernel)
        if (copy_source):
            result = test_image.sync_folder(self.target_local_path, target_img_dir)
            if (result.is_failure()):
                print("[KernelTarget] Failed to install target source")
                return result

        # Copy all build products to /target/build
        target_img_build_dir = os.path.join(target_img_dir, "build")
        result = test_image.sync_folder(self.build_dir, target_img_build_dir)
        if (result.is_failure()):
            print("[KernelTarget] Failed to install build products")
            return result

        debug_pause("[KernelTarget] successfully installed to image")
        return Result.success()
