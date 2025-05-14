from microwave2.utils.utils import Arch, run_command_better
import os 
import subprocess
#!/usr/bin/env python3
import re
import sys

from microwave2.utils.log import log, warn, error, debug, info

from microwave2.results.result import Result, ProcResult

# class BuildError(Exception):
#     """Represents an error trying to build the Linux kernel."""
#     def __init__(self, message, stdout=None, stderr=None):
#         super().__init__(message)
#         self.stdout = stdout
#         self.stderr = stderr


# TODO expand to support full kernel comands (clean, config, etc), for now only does modules
# TODO maybe make a specific ProcResult subclass MakeResult?
class LinuxMakeCommand:
    def __init__(self, kernel_dir: str, exec_arch: Arch, jobs: int=None, output_dir: str=None, default_verbose: bool = False):
        """- kernel_dir is the directory of the compiled kernel
           - output_dir is the directory where the output of the build will be placed
           
           """
        self.kernel_dir = kernel_dir
        self.arch = exec_arch
        self.cross_compile = None
        if self.arch != Arch.from_platform:
            if self.arch == Arch.ARM:
                self.cross_compile = "aarch64-linux-gnu-"
            elif self.arch == Arch.X86:
                self.cross_compile = ""#"x86_64-linux-gnu-"
            else:
                raise ValueError("Unexpected architecture: {}".format(self.arch))
            
        if jobs is not None:
            self.jobs = jobs
        else:
            self.jobs = os.cpu_count()

        self.output_dir = output_dir
        self.default_verbose = default_verbose

    # def run_command(self, command, verbose:bool) -> ProcResult:
    #     try:
    #         proc = subprocess.Popen(command,
    #                     stderr=subprocess.STDOUT,
    #                     stdout=subprocess.STDERR,
    #                     text=True,
    #                     bufsize=1)
            
    #         stdout, stderr = proc.communicate()
    #         stdout_decoded = stdout.decode()
    #         stderr_decoded = stderr.decode()
    #         # if proc.returncode != 0:
    #         #     raise BuildError('Make failed with return code {}'.format(proc.returncode),
    #         #                     stdout=stdout_decoded, stderr=stderr_decoded)
    #         if stderr_decoded:  # likely only due to build warnings
    #             normal("WARNINGs: ", stderr_decoded)
            
    #         result = ProcResult(returncode=proc.returncode, stdout=stdout_decoded, stderr=stderr_decoded)
    #         return result
    #     except OSError as e:
    #         info("Failed to run command: {}".format(self.str_command(command)))
    #         info("Error: ", e)
    #         return ProcResult(returncode=-1, stdout="", stderr="", error=e, message="Failed to run command: {}".format(self.str_command(command)))

    def run_command(self, command, verbose:bool = None) -> ProcResult:

        if verbose is None:
            verbose = self.default_verbose
        print("[LinuxMakeCommand][run_command] running command")
        result = run_command_better(command, verbose=verbose)
        # If result is a failure, print stdout as debug and stderr as error
        if result.is_failure():
            debug("STDOUT:\n" + result.get_stdout())
            error("STDERR:\n" + result.get_stderr())

        return result

    def str_command(self, command):
        return " ".join(command)

    def base_command(self, skip_output: bool = False) -> list:
        command = ["make", "ARCH=" + self.arch.linux_make_str()]

        if self.output_dir is not None:
            command.extend(["O=" + self.output_dir])

        if self.cross_compile is not None:
            command.append("CROSS_COMPILE=" + self.cross_compile)

        if self.jobs > 1:
            command.extend(["-j", str(self.jobs)])

        return command

    def make_olddefconfig(self) -> ProcResult:
        command = self.base_command()
        command.extend(["-C", self.kernel_dir])
        command.append("olddefconfig")
        # # if defconfig is not None:
        # command.append(defconfig)
    
        info("Running command:", self.str_command(command))
        return self.run_command(command)

    def make_defconfig(self, defconfig_prefix:str=None) -> ProcResult:
        command = self.base_command()
        command.extend(["-C", self.kernel_dir])
        if defconfig_prefix is not None:
            defconfig_chunk = f"{defconfig_prefix}_defconfig"
            command.append(defconfig_chunk)
        else:
            command.append("defconfig")
        # command.append("defconfig")
        # if defconfig is not None:
        #     command.append(defconfig)
        # else:
        #     command.append("defconfig")
        info("Running command:", self.str_command(command))
        return self.run_command(command)
    
    def make_localmodconfig(self) -> ProcResult:
        command = self.base_command()
        command.extend(["-C", self.kernel_dir])
        command.append("localmodconfig")
        # info("Running command:", self.str_command(command))
        info("[LinuxMakeCommand] [make_localmodconfig] Running localmodconfig command")
        # TODO Prepend localmodconfig command with yes piped into it
        
        return self.run_command(command)

    def make(self, verbose:bool = None) -> ProcResult:
        command = self.base_command()
        command.extend(["-C", self.kernel_dir])
        # Only required for gcc 15 I think
        command.append("CC=gcc -std=gnu11")
        # command.append("KCFLAGS=-Wno-error")
        # command.extend(["KCFLAGS=-Wno-error"]) # TODO make this configurable
        info("Running command:", self.str_command(command))
        return self.run_command(command, verbose=verbose)


    def make_install(self, install_path: str=None) -> ProcResult:
        """- install_path defines where updated kernel will be placed, by default /boot """
        command = self.base_command()
        command.extend(["-C", self.kernel_dir])

        if install_path is not None:
            command.extend(["INSTALL_PATH=" + install_path])
        else:
            # Print error and return failure
            error("[LinuxMakeCommand] [make_install] No install path specified")
            return ProcResult(returncode=-1, stdout="", stderr="", error="No install path specified", message="No install path specified")

        command.append("install")
        info("Running command:", self.str_command(command))
        return self.run_command(command)

    def make_headers_install(self, install_hdr_path: str=None) -> ProcResult:
        """- install_hdr_path defines where headers will be placed, by default /usr """

        command = self.base_command()
        command.extend(["-C", self.kernel_dir])

        if install_hdr_path is not None:
            command.extend(["INSTALL_HDR_PATH=" + install_hdr_path])

        command.append("headers_install")
        info("Running command:", self.str_command(command))
        return self.run_command(command)
    

    def make_mrproper(self) -> ProcResult:
        command = self.base_command()
        command.extend(["-C", self.kernel_dir])
        command.append("mrproper")
        info("Running command:", self.str_command(command))
        return self.run_command(command)
    
    def make_clean(self) -> ProcResult:
        command = self.base_command()
        command.extend(["-C", self.kernel_dir])
        command.append("clean")
        info("Running command:", self.str_command(command))
        return self.run_command(command)

    def make_modules_prepare(self) -> ProcResult:
        command = self.base_command()
        command.extend(["-C", self.kernel_dir])
        command.append("modules_prepare")
        info("Running command:", self.str_command(command))
        return self.run_command(command)
    
    def make_module(self, module_dir: str, module_out_dir: str=None, extra_cflags: str=None) -> ProcResult:
        """- module_dir is the source directory (i.e. where kbuild is, M=)
           - module_out_dir is the output directory (i.e. where the built module will be placed, MO=)
           - self.kernel_dir is where make will be run frome, should be at compiled kernel_dir (-C)
        """
        command = self.base_command(skip_output=True)
        command.extend(["-C", self.kernel_dir, "M=" + module_dir])

        if module_out_dir is not None:
            command.extend(["MO=" + module_out_dir])

        command.append("modules")

        if extra_cflags is not None:
            command.extend(["EXTRA_CFLAGS=" + extra_cflags])

        info("Running command:", self.str_command(command))
        return self.run_command(command)
    
    # Internal modules by default installed to /lib/modules/$(KERNELRELEASE)/kernel/
    # External modules by default installed to /lib/modules/$(KERNELRELEASE)/extra/
    def make_modules_install(self, module_dir: str=None, install_mod_path: str=None, install_mod_dir: str=None) -> ProcResult:
        """Modules are installed to <install_mod_path>/lib/modules/$(KERNELRELEASE)/<install_mod_dir>
           - module_dir is the module source directory (i.e. where kbuild is, M=). If None, installs kernel internal modules
           - install_mod_path specifies a prefix for the install location, by default / (root)
           - install_mod_dir specifies a subdirectory of the default install location (e.g. replaces \"extra\")
            - if install_mod_dir is None, the default install location is used (kernel or extra)
        """
        command = self.base_command()
        command.extend(["-C", self.kernel_dir])

        if module_dir is not None:
            command.extend(["M=" + module_dir])

        if install_mod_path is not None:
            command.extend(["INSTALL_MOD_PATH=" + install_mod_path])

        if install_mod_dir is not None:
            command.extend(["INSTALL_MOD_DIR=" + install_mod_dir])

        command.append("modules_install")
        info("Running command:", self.str_command(command))
        return self.run_command(command)
    
