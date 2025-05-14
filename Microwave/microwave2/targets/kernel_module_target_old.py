from microwave2.remote import GitConfig, GitRemoteCode, RemoteCode
from microwave2.utils.utils import dynamic_script_load, Arch, BuildConfig, makedirs, debug_pause, timed
from microwave2.local_storage import local_paths, rel_path
from dataclasses import dataclass
from microwave2.utils.rsync import RsyncCommand

from microwave2.targets.target import Target, TargetConfig
from microwave2.targets.kernel_target import KernelTarget
from microwave2.results.result import Result
from microwave2.images.ubuntu_image import UbuntuDiskImage

import os

from microwave2.utils.linux_make import LinuxMakeCommand

class KernelModuleTargetConfig(TargetConfig):
    DEFAULT_KERNEL_SUBDIR = "linux"
    REF_TARGET_NAME = "ref_kernel"
    # Include git config for reference kernel, and linux subidr
    def __init__(self, target_name: str, exec_arch: Arch, worker_arch: Arch, git_config: GitConfig, target_subdir: str = None, sparse_download: bool = False, ref_kernel_git_config: GitConfig = None, ref_kernel_subdir: str = None):
        super().__init__(target_name=target_name, exec_arch=exec_arch, worker_arch=worker_arch, git_config=git_config, target_subdir=target_subdir, sparse_download=sparse_download)
        
        if (ref_kernel_subdir is None):
            ref_kernel_subdir = self.DEFAULT_KERNEL_SUBDIR

        # Use self as reference kernel if none is provided
        if (ref_kernel_git_config is None):
            ref_kernel_git_config = git_config

        self.ref_target_config = TargetConfig(target_name=self.REF_TARGET_NAME,
                                                exec_arch=exec_arch,
                                                worker_arch=worker_arch,
                                                git_config=ref_kernel_git_config,
                                                target_subdir=ref_kernel_subdir)

    def get_ref_target_config(self) -> TargetConfig:
        return self.ref_target_config


class KernelModuleTarget(Target):
    """Target that is a kernel module"""
    def __init__(self, target_config: KernelModuleTargetConfig):
        super().__init__(target_config)

        self.reference_kernel = KernelTarget(target_config=target_config.ref_target_config)

    @timed
    def download(self) -> Result:
        # Setup repo by calling parent
        result = super().download()
        if (result.is_failure()):
            print("[KernelModuleTarget] Failed to download target code")
            return result
        
        # Download reference kernel
        return self.reference_kernel.download()

    
    def copy_local(self, dest_dir: str):
        """Copy test code to a directory"""
        rsync_command = RsyncCommand(source=self.target_local_path, destination=dest_dir, archive=True, verbose=True)
        success = rsync_command.sync(sudo=True)
        if (not success):
            print(f"[Target] Failed to copy target code to {dest_dir}")
            return Result.failure("Failed to copy target code")
        return Result.success()

    @timed
    def build(self, rebuild=False, build_callback=None) -> Result:
        """Build kernel module for correct architecture, using reference kernel headers"""
        print("[KernelModuleTarget] Building kernel module")
        # Try to prepare reference kernel
        print("[KernelModuleTarget] Building reference kernel")
        result = self.reference_kernel.build(mod_prep=True)
        if (result.is_failure()):
            print("[KernelModuleTarget] Failed to build reference kernel")
    
        # Run build callback
        if (build_callback is not None):
            # Callback in case tester wants to modify target before building
            result = build_callback(self)
            print(f"[KernelModuleTarget] Build callback result: {result}")
            if (result.is_failure()):
                return result
        
        # Build module against reference kernel
        compiled_kernel_dir = self.reference_kernel.get_build_dir()
        make_command = LinuxMakeCommand(kernel_dir=compiled_kernel_dir,
                                        exec_arch=self.target_config.exec_arch,
                                        output_dir=None, # TODO figure out if this should be something
                                        default_verbose=True)
        
        print("[KernelModuleTarget] Building module")
        result = make_command.make_module(module_dir=self.target_local_path, module_out_dir=self.build_dir)
        if (result.is_failure()):
            print("[KernelModuleTarget] Failed to build module")
        else:
            print("[KernelModuleTarget] Module built successfully")

        debug_pause("KernelModuleTarget build finished")
        return result

        # # Use the most up to date kernel version of those found in the directory <root> / lib / modules
        # #TODO should know the kernel version of the target
        # mods_dir = os.path.join(root_dir, "lib", "modules")
        # kernel_version = os.listdir(mods_dir)

        # # Warn if multiple kernel versions are found
        # if (len(kernel_version) > 1):
        #     print(f"Warning: Multiple kernel versions found: {kernel_version}")
        
        # # Use the first kernel version found
        # kernel_version = kernel_version[0]

        # kernel_dir = os.path.join(mods_dir, kernel_version, "build")

        # header_dir = os.path.join(root_dir, "usr", "src", "linux-headers-" + kernel_version)

        # # Copy code to build directory
        # result = self.copy_local(self.build_dir)
        # if (result.is_failure()):
        #     print("[KernelModuleTarget] Failed to copy target code to build directory")
        #     return result

     
        # build_dir = header_dir
        # kernel_dir = self.reference_kernel.get_kernel_dir()
        # make_command = LinuxMakeCommand(kernel_dir=kernel_dir,
        #                                 exec_arch=self.target_config.exec_arch,
        #                                 build_arch=self.target_config.worker_arch,
        #                                 output_dir=self.build_dir)
        
        # try:
        #     make_command.make_module(module_dir=self.target_local_path)
        #     debug_pause()
        # except BuildError as e:
        #     print(f"Build failed: {e}")
        #     print(f"stdout: {e.stdout}")
        #     print(f"stderr: {e.stderr}")
        #     debug_pause()
        #     return Result.failure(f"Build failed: {e}")
        
        # print("Build successful, placed module in directory: " + self.build_dir)
        # return Result.success()
    
        # print("Build successful, copying module to output directory")
        # # Copy everything in self.target_local_dir output directory
        # output_dir = os.path.join(root_dir, product_dir)
        # makedirs(output_dir)    
        # return self.copy_local(self.build_dir)
    @timed
    def install(self, disk_image: UbuntuDiskImage) -> Result:
        """Install kernel module into disk image: install ref kernel, build products, and target source"""

        # Install reference kernel to disk image
        result = self.reference_kernel.install(disk_image, copy_source=False)
        if (result.is_failure()):
            print("[KernelModuleTarget] Failed to install reference kernel")
            return result

        # Copy build products and source both to /target/<target_name>
        target_img_dir = os.path.join("/target", self.target_name)


        print("Installing kernel module build products into disk image")
        result = disk_image.sync_folder(self.build_dir, target_img_dir)
        if (result.is_failure()):
            print("[KernelModuleTarget] Failed to install build products")
            return result
        
        print("Installing kernel module into disk image, syncing to /target")
        result = disk_image.sync_folder(self.target_local_path, target_img_dir)

        if (result.is_failure()):
            print("[KernelModuleTarget] Failed to install target source")

        return result


    # old build function
    # def build(self, root_dir:str, product_dir:str, build_callback=None) -> Result:
    #     """Build kernel module for correct architecture"""

    #     # TODO figure out a better method than this
    #     # Currently, builds against /usr/src/linux-headers-<version> from mounted 
    #     # image, but this breaks symlinks and requires sudo. Maybe copy all target 
    #     # files and chroot in? Or copy out the headers?

    #     # Better method: create a LinuxKernel path that can download a specific kernel version
    #     # (will be necessary for kernel target later anyways) and install headers to a temp directory

    #     # Callback in case tester wants to modify target before building 
    #     if (build_callback is not None):
    #         result = build_callback(self)
    #         print(f"Build callback result: {build_callback}")
    #         if (result.is_failure()):
    #             return result

    #     # Use the most up to date kernel version of those found in the directory <root> / lib / modules
    #     #TODO should know the kernel version of the target
    #     mods_dir = os.path.join(root_dir, "lib", "modules")
    #     kernel_version = os.listdir(mods_dir)

    #     # Warn if multiple kernel versions are found
    #     if (len(kernel_version) > 1):
    #         print(f"Warning: Multiple kernel versions found: {kernel_version}")
        
    #     # Use the first kernel version found
    #     kernel_version = kernel_version[0]

    #     kernel_dir = os.path.join(mods_dir, kernel_version, "build")

    #     header_dir = os.path.join(root_dir, "usr", "src", "linux-headers-" + kernel_version)

    #     build_dir = header_dir
    
    #     make_command = LinuxMakeCommand(kernel_dir=build_dir,
    #                                     exec_arch=self.target_config.exec_arch,
    #                                     build_arch=self.target_config.worker_arch)
        
    #     try:
    #         make_command.make_module(module_dir=self.target_local_path)
    #         debug_pause()
    #     except BuildError as e:
    #         print(f"Build failed: {e}")
    #         print(f"stdout: {e.stdout}")
    #         print(f"stderr: {e.stderr}")
    #         debug_pause()
    #         return Result.failure(f"Build failed: {e}")
    
    #     print("Build successful, copying module to output directory")
    #     # Copy everything in self.target_local_dir output directory
    #     output_dir = os.path.join(root_dir, product_dir)
    #     makedirs(output_dir)    
    #     return self.copy_local(output_dir)
