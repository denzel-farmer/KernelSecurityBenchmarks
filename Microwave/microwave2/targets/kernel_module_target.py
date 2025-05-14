from microwave2.remote import GitConfig, GitRemoteCode, RemoteCode, GitFolderConfig
from microwave2.utils.utils import dynamic_script_load, Arch, BuildConfig, makedirs, debug_pause, timed
from microwave2.local_storage import local_paths, rel_path
from dataclasses import dataclass
from microwave2.utils.rsync import RsyncCommand
from enum import Enum

from microwave2.utils.log import log, warn, error, debug, info

from microwave2.utils.kernel_config import Kconfig, generate_kconfig

from microwave2.targets.target import Target, TargetConfig
from microwave2.targets.kernel_target import KernelTarget
from microwave2.results.result import Result
from microwave2.images.ubuntu_image import UbuntuDiskImage

from microwave2.utils.linux_kernel import LinuxKernel

import os

from microwave2.utils.linux_make import LinuxMakeCommand

# Kernel module can get ref kernel from two places:

# 1. Target repo itself (at ref_kernel_subdir)
# 2. Remote repo, cloned to common folder (with git_config)

# Reference kernel options:
# - remote repo or within target repo
# - cloned, built in common folders or target-specific (only for remote repo)
# - subdir where linux is in whichever repo

# enum for ref kernel source

# Cannot be IN_TARGET and COMMON


class RefKernelType(Enum):
    """Options for reference kernels """
    FROM_TARGET = "from_target"         # Ref kernel source in existing target repo (only required info is subdir), does not clone
    # Will be built as a part of target
    # Ref kernel source is from a remote repo (requires git config and subdir)
    COMMON = "common"
    # Will be cloned to and built in common built as a shared item


class RefKernelConfig:
    def __init__(self, location_type: RefKernelType, git_config: GitConfig = None, subdir: str = None, kconfig: Kconfig = None, extra_kconfgs: str = None, extra_kernel_params: str = None):
        self.location_type = location_type
        self.git_config = git_config
        # Subdir within repo (either common or target) where linux kernel actually is (e.g. "linux")
        self.subdir = subdir
        self.kconfig = kconfig
        self.extra_kconfgs = extra_kconfgs # TODO implement this -- currently unused
        self.extra_kernel_params = extra_kernel_params # TODO implement this -- currently unused

        self.validate()

    # TODO validate kernel config here?
    def validate(self) -> bool:
        # Error if location type is FROM_TARGET but no subdir
        if (self.location_type == RefKernelType.FROM_TARGET and self.subdir is None):
            error("[KernelModuleTarget] Ref kernel location type is FROM_TARGET but no subdir specified, something is probably misconfigured")
            return False
        # Error if location type is COMMON but no git config
        if (self.location_type == RefKernelType.COMMON and self.git_config is None):
            error("[KernelModuleTarget] Ref kernel location type is COMMON but no git config specified, where will I get the kernel from?")
            return False
        # Warn if location type is FROM_TARGET and git config is not none
        if (self.location_type == RefKernelType.FROM_TARGET and self.git_config is not None):
            warn("[KernelModuleTarget] Ref kernel location type is FROM_TARGET but git config is specified, this will be ignored")
            return True

        return True


class KernelModuleTargetConfig(TargetConfig):
    def __init__(self,
                 target_name: str,
                 exec_arch: Arch,
                 worker_arch: Arch,
                 git_config: GitConfig,
                 reference_kernel_config: RefKernelConfig,  # Reference kernel config
                 target_subdir: str = None,
                 sparse_download: bool = False,
                 #  ref_kernel_subdir: str = "linux",                      # The subdir within target repo or external repo of reference linux kernel source
                 #  external_ref_kernel_git_config: GitConfig = None       # Git config for a reference kernel to be shared between targets, if None uses kernel already in target
                 ):

        super().__init__(target_name=target_name, exec_arch=exec_arch, worker_arch=worker_arch,
                         git_config=git_config, target_subdir=target_subdir, sparse_download=sparse_download)

        self.reference_kernel_config = reference_kernel_config
        self.reference_kernel_config.validate()

        # self.ref_kernel_subdir = ref_kernel_subdir
        # self.external_ref_kernel_git_config = external_ref_kernel_git_config


class KernelModuleTarget(Target):
    """Target that is a kernel module"""

    def __init__(self, target_config: KernelModuleTargetConfig):
        super().__init__(target_config)

        # If reference kernel is coming from remote, do some setup
        self.ref_kernel_remote = None
        if (target_config.reference_kernel_config.location_type == RefKernelType.COMMON):
            ref_kernel_base_path = os.path.join(self.get_target_common_path(), "ref_kernel", target_config.reference_kernel_config.git_config.repo_name)
            
            ref_kernel_build_path  = os.path.join(ref_kernel_base_path, "build", target_config.exec_arch.to_str())

            ref_kernel_repo_path = os.path.join(ref_kernel_base_path, "src")
            ref_kernel_source_path = os.path.join(ref_kernel_repo_path, target_config.reference_kernel_config.subdir)

            self.ref_kernel_remote = GitRemoteCode(
                git_config=target_config.reference_kernel_config.git_config,
                local_path=ref_kernel_repo_path,
                remote_rel_path=target_config.reference_kernel_config.subdir)

            self.ref_kernel_remote.setup_repo()
        else:
            ref_kernel_source_path = os.path.join(self.repo_local_path, target_config.reference_kernel_config.subdir)
            # TODO this doesn't really make sense--should restructure all directories better at some point
            ref_kernel_build_path = os.path.join(self.build_dir, "ref_kernel", target_config.exec_arch.to_str())        

        debug("[KernelModuleTarget] Ref kernel source path: ", ref_kernel_source_path)
        debug("[KernelModuleTarget] Ref kernel build path: ", ref_kernel_build_path)


        self.ref_kernel = LinuxKernel(source_dir=ref_kernel_source_path,
                                      build_dir=ref_kernel_build_path,
                                      target_arch=target_config.exec_arch,
                                      kconfig=target_config.reference_kernel_config.kconfig)

        debug_pause("KernelModuleTarget init finished", 2)

        # # Set up reference kernel:
        # # - if external_ref_kernel_git_config is not None, we are using a remote

        # # Set up reference kernel repo
        # if (target_config.external_ref_kernel_git_config is not None):
            
        #     ref_kernel_source_path = os.path.join(self.get_target_common_path(),
        #                                         "ref_kernel", "src", 
        #                                         target_config.external_ref_kernel_git_config.repo_name)

        #     # Set up remote repo (but don't clone yet)
        #     self.ref_kernel_remote = GitRemoteCode(git_config=target_config.external_ref_kernel_git_config,
        #                                            local_path=ref_kernel_source_path, remote_rel_path=target_config.ref_kernel_subdir)
        #     self.ref_kernel_remote.setup_repo()

        # else:
        #     # Just using subdir of our own repo
        #     ref_kernel_repo_path = self.repo_local_path
        #     self.ref_kernel_remote = None

        # # Set ref kernel path, subdir of ref kernel with ref kernel repo (e.g. "linux")
        # if (target_config.ref_kernel_subdir is not None):
        #     # Use subdir of external repo
        #     self.ref_kernel_path = os.path.join(
        #         ref_kernel_repo_path, target_config.ref_kernel_subdir)
        # else:
        #     self.ref_kernel_path = ref_kernel_repo_path

        # self.ref_kernel_build_path = os.path.join(self.build_dir, "ref_kernel")
        # self.ref_kernel = None  # None until cloned

    @timed
    def download(self) -> Result:
        # Setup repo by calling parent
        result = super().download()
        if (result.is_failure()):
            info("[KernelModuleTarget] Failed to download target code")
            return result

        # Download reference kernel
        if (self.ref_kernel_remote is not None):
            result = self.ref_kernel_remote.update_local()
            if (result.is_failure()):
                info("[KernelModuleTarget] Failed to update reference kernel")
                return result

        # # Get target arch by checking armpls in repo local path
        # armpls_path = os.path.join(self.repo_local_path, ".armpls")
        # exec_arch = Arch.X86
        # if (os.path.exists(armpls_path)):
        #     exec_arch = Arch.ARM
        #     # just die
        #     exit(0)
        #     raise Exception("KernelModuleTarget: armpls file found, but not implemented yet")
        # self.target_config.exec_arch = exec_arch # TODO shouldn't be overwriting this, and should make sure this doesn't affect arch dependent tests
        # info(f"[KernelModuleTarget] Target arch: {exec_arch}")

        # self.ref_kernel = LinuxKernel(source_dir=self.ref_kernel_path,
        #                               build_dir=self.ref_kernel_build_path,
        #                               target_arch=self.target_config.exec_arch)

        return result

    def copy_local(self, dest_dir: str):
        """Copy target code to a directory"""
        rsync_command = RsyncCommand(
            source=self.target_local_path, destination=dest_dir, archive=True, verbose=True)
        success = rsync_command.sync(sudo=True)
        if (not success):
            info(f"[Target] Failed to copy target code to {dest_dir}")
            return Result.failure("Failed to copy target code")
        return Result.success()

    @timed
    def build(self, rebuild=False, build_callback=None) -> Result:
        """Build kernel module for correct architecture, using reference kernel headers"""
        info("[KernelModuleTarget] Building kernel module")

        info("[KernelModuleTarget] Building reference kernel")
        result = self.ref_kernel.build(force_rebuild=rebuild)
        if (result.is_failure()):
            info("[KernelModuleTarget] Failed to build reference kernel")
            return result

        # Run build callback
        if (build_callback is not None):
            # Callback in case tester wants to modify target before building
            result = build_callback(self)
            info(f"[KernelModuleTarget] Build callback result: {result}")
            if (result.is_failure()):
                return result

        # Build module against reference kernel (TODO maybe make a class for modules)
        result = self.ref_kernel.build_module(
            module_dir=self.target_local_path, module_out_dir=self.build_dir)
        if (result.is_failure()):
            info("[KernelModuleTarget] Failed to build module")
            return result

        debug_pause("KernelModuleTarget build finished")
        return result

    @timed
    def install(self, disk_image: UbuntuDiskImage) -> Result:
        """Install kernel module into disk image: install ref kernel, build products, and target source"""

        info("[KernelModuleTarget] Installing kernel module into disk image")

        # Install reference kernel to disk image
        install_dir = os.path.join(self.temp_dir, "install")
        makedirs(install_dir, delete=True)

        self.ref_kernel.install(install_dir=install_dir)

        info("[KernelModuleTarget] Installing reference kernel to disk image")

        boot_dir = self.ref_kernel.get_install_boot_dir(install_dir)
        result = disk_image.override_kernel(boot_dir)
        if (result.is_failure()):
            info("[KernelTarget] Failed to install kernel to image")
            return result

        usr_dir = self.ref_kernel.get_install_usr_dir(install_dir)
        result = disk_image.sync_folder(usr_dir, "/usr")
        if (result.is_failure()):
            info("[KernelTarget] Failed to install to image")
            return result

        lib_dir = self.ref_kernel.get_install_lib_dir(install_dir)
        result = disk_image.sync_folder(lib_dir, "/lib")
        if (result.is_failure()):
            info("[KernelTarget] Failed to install to image")
            return result

        # Copy build products and source both to /target/<target_name>
        target_img_dir = os.path.join("/target", self.target_name)

        info("Installing kernel module build products into disk image")
        result = disk_image.sync_folder(self.build_dir, target_img_dir)
        if (result.is_failure()):
            info("[KernelModuleTarget] Failed to install build products")
            return result

        info("Installing kernel module into disk image, syncing to /target")
        result = disk_image.sync_folder(self.target_local_path, target_img_dir)

        if (result.is_failure()):
            info("[KernelModuleTarget] Failed to install target source")

        return result
