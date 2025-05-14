from microwave2.remote import GitConfig, GitRemoteCode, RemoteCode
from microwave2.utils.utils import dynamic_script_load, Arch, BuildConfig, makedirs, debug_pause, timed, run_command_better
from microwave2.utils.compile_link import GCCCommand, LdCommand, ASCommand
from microwave2.utils.rsync import RsyncCommand
from microwave2.local_storage import local_paths, rel_path
from dataclasses import dataclass
from microwave2.utils.rsync import RsyncCommand

import shutil

from microwave2.targets.target import Target, TargetConfig
from microwave2.targets.kernel_target import KernelTarget
from microwave2.results.result import Result
from microwave2.images.raw_image import RawDiskImage

from typing import List

import os

from microwave2.utils.linux_make import LinuxMakeCommand

class RawOSTargetConfig(TargetConfig):
    """Config information about for a raw OS target"""
    def __init__(self, target_name: str, exec_arch: Arch, worker_arch: Arch,
                 git_config: GitConfig, target_subdir: str = None,
                 sparse_download: bool = False, assembly_filename: str = "entry.S", c_filename: str = "main.c"):
        self.assembly_filename = assembly_filename
        self.c_filename = c_filename
        super().__init__(target_name, exec_arch, worker_arch, git_config, target_subdir, sparse_download)

class RawOSTarget(Target):
    ENTRY_OUTPUT_NAME = "entry.o"
    MAIN_OUTPUT_NAME = "main.o"
    LINKER_OUTPUT_NAME = "main.elf"
    LINKER_SCRIPT_NAME = "linker.ld" # TODO make this an argument
    """Target that is a kernel module"""
    def __init__(self, target_config: RawOSTargetConfig):
        super().__init__(target_config)

        self.assembly_filename = target_config.assembly_filename
        self.c_filename = target_config.c_filename


        # self.entry_output_path = os.path.join(self.build_dir, "entry.o")
        # self.main_output_name = "main.o"
        # self.linker_output_name = "main.elf"
        # self.linker_script_name = "linker.ld"
        # self.main_output_path = os.path.join(self.build_dir, "main.o")
        self.elf_output_path = os.path.join(self.build_dir, self.LINKER_OUTPUT_NAME)

    def get_cross_compile_prefix(self) -> str:
        cross_compile_prefix = ""
        # Always cross compile as X86
        if (Arch.from_platform() != Arch.X86):
            # Cross compiling for x86 (cross-compile toolchain required)
            cross_compile_prefix = "x86_64-linux-gnu-"
        return cross_compile_prefix

    # def run_build_command(self, base: str, misc_params: List[str], output_path: str, input_paths: List[str]) -> Result:
    #     """Build an object file"""

    #     # Check if input file exists
    #     for input_path in input_paths:
    #         if not os.path.exists(input_path):
    #             print(f"[RawOSTarget] Input file not found: {input_path}")
    #             return Result.failure(f"Input file not found: {input_path}")

    #     command = [self.get_cross_compile_prefix() + base] + misc_params + ["-o", output_path] + input_paths
    #     return run_command_better(command)

    # def build_entry_object(self) -> Result:
    #     """Build the entry output file"""
        
    #     base = f"as"
    #     misc_params = ["--32", "-Os"]
    #     output_path = self.entry_output_name
    #     input_paths = self.assembly_filename #[os.path.join(self.target_local_path, self.assembly_filename)]

    #     return self.run_build_command(base, misc_params, output_path, input_paths)

    
        # assembly_file_path = os.path.join(self.target_local_path, self.assembly_filename)
        # if not os.path.exists(assembly_file_path):
        #     print(f"[RawOSTarget] Assembly file not found: {assembly_file_path}")
        #     return Result.failure(f"Assembly file not found: {assembly_file_path}")
        
        # # Assemble command: as --32 -Os -o entry.o entry.s
        # assemble_command_base = f"{prefix}as"
        # misc_params =  ["--32", "-Os"]

        # entry_output_path = os.path.join(self.build_dir, self.entry_output_name) 
        # output_params = ["-o", entry_output_path] 

        # input_param = [assembly_file_path]

        # assemble_command = [assemble_command_base] + misc_params + output_params + input_param

        # return run_command_better(assemble_command)

    # def build_main_object(self) -> Result:
    #     base = "gcc"
    #     misc_params = ["-c", "-m16", "-ffreestanding", "-fno-PIE", "-nostartfiles", "-nostdlib", "-Os", "-std=c99"]
    #     output_path = self.main_output_name
    #     input_paths = [self.c_filename]

    #     return self.run_build_command(base, misc_params, output_path, input_paths)

        
    # def build_main_object(self, prefix: str) -> Result:
    #     """Build the main object file"""
        
    #     c_file_path = os.path.join(self.target_local_path, self.c_filename)
    #     if not os.path.exists(c_file_path):
    #         print(f"[RawOSTarget] C file not found: {c_file_path}")
    #         return Result.failure(f"C file not found: {c_file_path}")
        
    #     # Compile command: gcc -c -m16 -ffreestanding -fno-PIE -nostartfiles -nostdlib -Os -o main.o -std=c99 main.c
    #     compile_command_base = f"{prefix}gcc"
    #     misc_params = ["-c", "-m16", "-ffreestanding", "-fno-PIE", "-nostartfiles", "-nostdlib", "-Os", "-std=c99"]

    #     main_output_path = os.path.join(self.build_dir, self.main_output_name)
    #     output_params = ["-o", main_output_path]

    #     input_param = [c_file_path]

    #     compile_command = [compile_command_base] + misc_params + output_params + input_param

    #     return run_command_better(compile_command)

    # def link_files(self) -> Result:
        
    #     # Entry.o and main.o are hardcoded into the linker script
    #     # TODO make this more general        # shutil.copy2(linker_script_path, self.build_dir)
    #     # Link command: ld -m elf_i386 -z noexecstack -o main.elf -T linker.ld entry.o main.o

    #     # TODO make this more general

    #     base = "ld"
    #     misc_params = ["-m", "elf_i386", "-z", "noexecstack", "-T", self.linker_script_name]
    #     command = [self.get_cross_compile_prefix() + base] + misc_params 
    #     return run_command_better(command)
    
    #     return self.run_build_command(base, misc_params, output_path, input_paths)

    @timed
    def build(self, rebuild=False, build_callback=None) -> Result:
        """Build raw OS target"""
        # TODO This is super hardcoded, make a general version maybe with assembler and gcc wrappers?
        # Or maybe build linker script dynamically, or use a hardcoded one

        # Sync source into build dir
        sync_cmd = RsyncCommand(self.target_local_path, self.build_dir, delete=True, force_copy_contents=True, verbose=True)
        result = sync_cmd.sync_better()
        if (result.is_failure()):   
            print("[RawOSTarget] Failed to sync source")
            return result
        
        print("[RawOSTarget] Copied source to build dir")
        
        # Build entry object
        assembly_path = os.path.join(self.build_dir, self.assembly_filename)
        entry_o_path = os.path.join(self.build_dir, self.ENTRY_OUTPUT_NAME)
        assemble_cmd = ASCommand(Arch.i386, assembly_path, entry_o_path, extra_params=["-Os"], verbose=True)
        result = assemble_cmd.run()
        if (result.is_failure()):
            print("[RawOSTarget] Failed to build entry object")
            return result
        
        # Build main object
        c_path = os.path.join(self.build_dir, self.c_filename)
        main_o_path = os.path.join(self.build_dir, self.MAIN_OUTPUT_NAME)
        compile_cmd = GCCCommand(Arch.i386, c_path, main_o_path, compile_only=True, std_version="c99", extra_params=["-ffreestanding", "-fno-PIE", "-nostartfiles", "-nostdlib", "-Os"], verbose=True)
        result = compile_cmd.run()
        if (result.is_failure()):
            print("[RawOSTarget] Failed to build main object")
            return result
        
        # Link files
        linker_script_path = os.path.join(self.build_dir, self.LINKER_SCRIPT_NAME)
        linker_output_path = os.path.join(self.build_dir, self.LINKER_OUTPUT_NAME)
        link_cmd = LdCommand(Arch.i386, input_files = [self.ENTRY_OUTPUT_NAME, self.MAIN_OUTPUT_NAME], output_file=linker_output_path,
                             link_script=linker_script_path, verbose=True)
        result = link_cmd.run(workdir=self.build_dir)
        if (result.is_failure()):
            print("[RawOSTarget] Failed to link files")
            return result
        
        return Result.success()

        # old_pwd = os.getcwd()
        # os.chdir(self.build_dir)


        # base = self.get_cross_compile_prefix() + "as"
        # misc_params = ["--32", "-Os"]
        # command = [base] + misc_params + ["-o", self.entry_output_name] + [self.assembly_filename]
        
        # result = run_command_better(command)
        # if (result.is_failure()):
        #     print("[RawOSTarget] Failed to build entry output")
        #     os.chdir(old_pwd)
        #     return result

        # base = self.get_cross_compile_prefix() + "gcc"
        # misc_params = ["-c", "-m16", "-ffreestanding", "-fno-PIE", "-nostartfiles", "-nostdlib", "-Os", "-std=c99"]
        # command = [base] + misc_params + ["-o", self.main_output_name] + [self.c_filename]

        # result = run_command_better(command)
        # if (result.is_failure()):
        #     print("[RawOSTarget] Failed to build main output")
        #     os.chdir(old_pwd)
        #     return result
    
        # result = self.link_files()
        # if (result.is_failure()):
        #     print("[RawOSTarget] Failed to link files")
        #     os.chdir(old_pwd)
        #     return result

                # # print("[RawOSTarget] Building assembly file: " + assembly_file_path)
                # # command = command_prefix + f"as --32 -Os -o entry.o {self.assembly_file}" 
                # # result = run_command_better(command, cwd=self.source_dir)
                # # self.report.add_result("assembly_build_result", result)

                # # # Build the C file
                # # print("[RawOSTarget] Building C file: " + self.c_file)
                # # command = command_prefix + f"gcc -c -m16 -ffreestanding -fno-PIE -nostartfiles -nostdlib -Os -o main.o -std=c99 {self.c_file}"
                # # result = run_cmd(command, silent=False, cwd=self.source_dir)
                # # self.report.add_result("c_build_result", result)

                # # Link the files
                # print("[RawOSTarget] Linking files")
                # command = command_prefix + "ld -m elf_i386 -z noexecstack -o main.elf -T linker.ld entry.o main.o"
                # result = run_cmd(command, silent=False, cwd=self.source_dir)
                # self.report.add_result("link_result", result)

            
                # #TODO add error strings to report

                # print("[FloppyBuilder] Build complete")
        os.chdir(old_pwd)
        return Result.success()
    
    @timed
    def install(self, disk_image: RawDiskImage) -> Result:

        # Install elf as binary
        result = disk_image.install_elf_as_binary(self.elf_output_path)
        if (result.is_failure()):
            print("[RawOSTarget] Failed to install elf as binary")
        
        return result
        












        # print("[KernelModuleTarget] Building kernel module")
        # # Try to prepare reference kernel
        # print("[KernelModuleTarget] Building reference kernel")
        # result = self.reference_kernel.build(mod_prep=True)
        # if (result.is_failure()):
        #     print("[KernelModuleTarget] Failed to build reference kernel")
    
        # # Run build callback
        # if (build_callback is not None):
        #     # Callback in case tester wants to modify target before building
        #     result = build_callback(self)
        #     print(f"[KernelModuleTarget] Build callback result: {result}")
        #     if (result.is_failure()):
        #         return result
        
        # # Build module against reference kernel
        # compiled_kernel_dir = self.reference_kernel.get_build_dir()
        # make_command = LinuxMakeCommand(kernel_dir=compiled_kernel_dir,
        #                                 exec_arch=self.target_config.exec_arch,
        #                                 build_arch=self.target_config.worker_arch,
        #                                 output_dir=None, # TODO figure out if this should be something
        #                                 default_verbose=True)
        
        # print("[KernelModuleTarget] Building module")
        # result = make_command.make_module(module_dir=self.target_local_path, module_out_dir=self.build_dir)
        # if (result.is_failure()):
        #     print("[KernelModuleTarget] Failed to build module")
        # else:
        #     print("[KernelModuleTarget] Module built successfully")

        # debug_pause("KernelModuleTarget build finished")
        # return result

    # @timed
    # def install(self, disk_image: UbuntuDiskImage) -> Result:
    #     """Install kernel module into disk image: install ref kernel, build products, and target source"""

    #     # Install reference kernel to disk image
    #     result = self.reference_kernel.install(disk_image, copy_source=False)
    #     if (result.is_failure()):
    #         print("[KernelModuleTarget] Failed to install reference kernel")
    #         return result

    #     # Copy build products and source both to /target/<target_name>
    #     target_img_dir = os.path.join("/target", self.target_name)


    #     print("Installing kernel module build products into disk image")
    #     result = disk_image.sync_folder(self.build_dir, target_img_dir)
    #     if (result.is_failure()):
    #         print("[KernelModuleTarget] Failed to install build products")
    #         return result
        
    #     print("Installing kernel module into disk image, syncing to /target")
    #     result = disk_image.sync_folder(self.target_local_path, target_img_dir)

    #     if (result.is_failure()):
    #         print("[KernelModuleTarget] Failed to install target source")

    #     return result

