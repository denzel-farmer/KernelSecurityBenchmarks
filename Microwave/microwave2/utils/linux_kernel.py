from microwave2.remote import GitConfig, GitRemoteCode, RemoteCode
from microwave2.utils.utils import dynamic_script_load, Arch, BuildConfig, makedirs, debug_pause, timed
from microwave2.local_storage import local_paths, rel_path
from dataclasses import dataclass
from microwave2.utils.rsync import RsyncCommand
from microwave2.utils.log import log, warn, error, debug, info
from microwave2.utils.kernel_config import Kconfig, generate_kconfig, parse_file


import shutil
from microwave2.targets.target import Target, TargetConfig

from microwave2.images.disk_image import DiskImage
from microwave2.images.ubuntu_image import UbuntuDiskImage

from microwave2.results.result import Result, ProcResult

import os

from microwave2.utils.linux_make import LinuxMakeCommand

# farfetch+0x195/0xf80

# Parent directory of current file 
CONFIGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "linux-configs")
# DEFCONFIG_NAME = "manual_minimized"
# DEFCONFIG_NAME = "def_localmod"
# DEFCONFIG_NAME = "prove_lock"
# DEFCONFIG_NAME = "ebpf_localmod"
# X86_MIN_DEFCONFIG = os.path.join(CONFIGS_DIR, "more_minimal_x86.defconfig")
# ARM64_MIN_DEFCONFIG = os.path.join(CONFIGS_DIR, "more_minimal_arm64.defconfig")

DEFAULT_DEFCONFIG = "def_localmod"

# TODO add more functionality, particularly for configuring
class LinuxKernel():
    """Manages a cloned linux kernel"""
    def __init__(self, source_dir: str, build_dir: str, target_arch: Arch, kconfig: Kconfig=None):      
        self.source_dir = source_dir


        if (kconfig is None):
            kconfig = generate_kconfig(target_arch, defconfig_names=[DEFAULT_DEFCONFIG])
        # if (defconfig_name is None):
        #     # TODO make this a default defconfig
        #     defconfig_name = "def_localmod"
        self.kconfig = kconfig
        self.build_dir =  os.path.join(build_dir, kconfig.get_label())
        self.arch = target_arch
        # self.defconfig_name = defconfig_name

        self.config_path = os.path.join(self.build_dir, ".config")
        self.old_config_path = os.path.join(self.build_dir, ".last.config")

        # Make command for repeat use
        self.make_command = LinuxMakeCommand(kernel_dir=self.source_dir,
                                             exec_arch=target_arch,
                                             output_dir=self.build_dir,
                                             default_verbose=True)
        
        # makedirs(self.source_dir)
        makedirs(self.build_dir)

    def get_source_dir(self):
        return self.source_dir

    def get_build_dir(self):
        return self.build_dir
    
    def kconfig_changed(self) -> bool:

        # If the old config doesn't exist, then we need to build a new one
        if not os.path.exists(self.old_config_path):
            return True

        old_kconfig = parse_file(self.old_config_path)
        return old_kconfig != self.kconfig
    
    def validate_config(self) -> bool:
        validated_kconfig = parse_file(self.config_path)
        if self.kconfig.is_subset_of(validated_kconfig):
            return True
        missing = set(self.kconfig.as_entries()) - set(validated_kconfig.as_entries())
        message = 'Not all Kconfig options selected in kunitconfig were in the generated .config.\n' \
                'This is probably due to unsatisfied dependencies.\n' \
                'Missing: ' + ', '.join(str(e) for e in missing)

        error("[LinuxKernel] " + message)
        return False


    def build_config(self) -> Result:
    
        self.kconfig.write_to_file(self.config_path)
        result = self.make_command.make_olddefconfig()
        if result.is_failure():
            error("[LinuxKernel] Failed to run make olddefconfig")
            return Result.failure(message="Failed to run make olddefconfig")
        
        if not self.validate_config():
            error("[LinuxKernel] Failed to validate config")
            return Result.failure(message="Failed to validate config")

       
        if os.path.exists(self.old_config_path):
            os.remove(self.old_config_path)  # write_to_file appends to the file
        self.kconfig.write_to_file(self.old_config_path)
        return Result.success()

    def build_reconfig(self) -> Result:
        """Creates a new .config if it is not a subset of the .kunitconfig."""
        # kconfig_path = get_kconfig_path(build_dir)
        if not os.path.exists(self.config_path):
            print('Generating .config ...')
            return self.build_config()

        existing_kconfig = parse_file(self.config_path)
        # self._kconfig = self._ops.make_arch_config(self._kconfig)

        if self.kconfig.is_subset_of(existing_kconfig) and not self.kconfig_changed():
            return Result.success()
        print('Regenerating .config ...')
        os.remove(self.config_path)
        return self.build_config()



    @timed
    def configure(self, force_reconfig:bool=False) -> Result:
        # If force reconfig, remove config and build new one
        if (force_reconfig):
            info("[LinuxKernel] Cleaning kernel source")
            os.remove(self.config_path)
            return self.build_config()
        
        # Otherwise, just call bulid_reconfig
        return self.build_reconfig()

    @timed
    def old_configure(self, force_reconfig:bool=False) -> Result:



        # If force reconfig, run make mrproper
        if (force_reconfig):
            info("[LinuxKernel] Cleaning kernel source")
            result = self.make_command.make_mrproper()
            if (result.is_failure()):
                info("[LinuxKernel] Failed to clean kernel source")
                return result

        # # For now, copy minimized config from same dir as current file
        # current_dir = os.path.dirname(os.path.abspath(__file__))
        # config_path = os.path.join(current_dir, "minimized_x86.config")
        # info("[LinuxKernel] Copying minimized config")
        # shutil.copy(config_path, os.path.join(self.build_dir, ".config"))
        # return Result.success()

        # Copy defconfig into arch folder
        defconfig_prefix = f"microwave_{self.defconfig_name}"
        arch_str = self.arch.linux_make_config_str()
        target_defconfig_path = os.path.join(self.source_dir, "arch", arch_str, "configs", f"{defconfig_prefix}_defconfig")
        info("[LinuxKernel] Copying defconfig")

        template_defconfig_path = os.path.join(CONFIGS_DIR, arch_str, f"{self.defconfig_name}_defconfig")
        print(f"template defconfig path: {template_defconfig_path}")
        print(f"target defconfig path: {target_defconfig_path}")
        shutil.copy(template_defconfig_path, target_defconfig_path)

        # if self.arch == Arch.ARM:
        #     shutil.copy(ARM64_MIN_DEFCONFIG, target_defconfig_path)
        # elif self.arch == Arch.X86:
        #     shutil.copy(X86_MIN_DEFCONFIG, target_defconfig_path)
        
        # TODO add more configurability, for now just make defconfig for specified architecture
        info("[LinuxKernel] Configuring kernel")

        result = self.make_command.make_defconfig(defconfig_prefix)
        if (result.is_failure()):
            info("[LinuxKernel] Failed to configure kernel")
            info(result)

        # # Make localmodconfig
        # info("Running localmodconfig")
        # result = self.make_command.make_localmodconfig()
        # info("Done running localmodconfig")
        # if (result.is_failure()):
        #     info("[LinuxKernel] Failed to run localmodconfig")
        #     return result
        info("[LinuxKernel] Kernel configured successfully")
        
        return result
    
    def build_for_module(self) -> Result:
        result = self.configure()
        if (result.is_failure()):
            info("[LinuxKernel] Failed to configure kernel")
            return result
        
        info("[LinuxKernel] Preparing kernel for module build")
        result = self.make_command.make_modules_prepare()
        if (result.is_failure()):
            info("[LinuxKernel] Failed to prepare kernel for module build")
            return result
        
        info("[LinuxKernel] Kernel prepared for module build")
        return result
            
    @timed
    def build(self, force_rebuild=False, force_reconfigure=False) -> Result:
        # TODO build kernel for correct architecture
        # TODO make rebuild flag actually do something

        # Configure kernel
        result = self.configure(force_reconfigure)
        if (result.is_failure()):
            info("[LinuxKernel] Failed to configure kernel")
            return result
        
        # Clean kernel if force_rebuild
        if (force_rebuild):
            info("[LinuxKernel] Cleaning kernel tree")
            result = self.make_command.make_clean()
            if (result.is_failure()):
                info("[LinuxKernel] Failed to clean kernel tree")
                return result

        # Build kernel
        info("[LinuxKernel] Building kernel")
        result = self.make_command.make()
        if (result.is_failure()):
            info("[LinuxKernel] Failed to build kernel")
        else: 
            info("[LinuxKernel] Kernel built successfully")

        debug_pause("LinuxKernel build finished", level=4)
        return result


    @timed
    def build_module(self, module_dir: str, module_out_dir: str=None) -> Result:
        """Build a kernel module"""

        # Make for module
        result = self.build_for_module()
        if (result.is_failure()):
            info("[LinuxKernel] Failed to prepare kernel for module build")
            return result

        info("[LinuxKernel] Building kernel module")
        result = self.make_command.make_module(module_dir=module_dir, module_out_dir=module_out_dir, extra_cflags="-Wno-error")
        if (result.is_failure()):
            info("[LinuxKernel] Failed to build kernel module")
            return result
        
        return result


    def get_install_boot_dir(self, install_dir:str) -> str:
        """Get the boot directory for the kernel"""
        return os.path.join(install_dir, "boot")
    
    def get_install_usr_dir(self, install_dir:str) -> str:
        """Get the usr directory for the kernel"""
        return os.path.join(install_dir, "usr")
    
    def get_install_lib_dir(self, install_dir:str) -> str:
        """Get the lib directory for the kernel"""
        return os.path.join(install_dir, "lib")
    
    @timed
    def install(self, install_dir: str) -> Result:
        """Install into the specified directory, which is then ready to be installecd into an image. Will clobber the directory if it exists."""

        # TODO could filter unneeded products (e.g. like arch's PKGBUILD)

        # Make install directory, clobbing if it exists
        makedirs(install_dir, delete=True)

        # Install kernel to install_dir/boot 
        # TODO this doesn't actually work, because /boot gets mounted from partition 16 (at least for x86), overwriting the kernel
        # TODO need to update grub to point to new kernel
        temp_boot_dir = self.get_install_boot_dir(install_dir)
        makedirs(temp_boot_dir)
        result = self.make_command.make_install(install_path=temp_boot_dir)
        if (result.is_failure()):
            info("[LinuxKernel] Failed to install kernel")
            return result

        # Install headers to install_dir/usr
        temp_usr_dir = self.get_install_usr_dir(install_dir)
        makedirs(temp_usr_dir)
        result = self.make_command.make_headers_install(install_hdr_path=temp_usr_dir)
        if (result.is_failure()):
            info("[LinuxKernel] Failed to install headers")
            return result

        # Install modules to install_dir/lib/modules/$(KERNELRELEASE)/kernel/
        # temp_lib_modules_dir = os.path.join(install_dir, "lib", "modules")
        result = self.make_command.make_modules_install(install_mod_path=install_dir)
        if (result.is_failure()):
            info("[LinuxKernel] Failed to install modules")
            return result
        
        debug_pause("[LinuxKernel] successfully installed to temporary directory")

        return Result.success()
