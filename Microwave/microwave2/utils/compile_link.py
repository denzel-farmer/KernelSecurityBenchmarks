from microwave2.utils.utils import Arch, run_command_better
import os 
import subprocess
#!/usr/bin/env python3
import re
import sys

from microwave2.results.result import Result, ProcResult


# Simple wrapper around ld 
# TODO could make a lot more complex if needed
class LdCommand:
    def __init__(self, exec_arch: Arch, input_files: list, output_file: str, link_script: str = None, verbose: bool = False):
        self.arch = exec_arch
        
        # if input_files is a string, convert to list
        if isinstance(input_files, str):
            input_files = [input_files]

        self.input_files = input_files
        self.output_file = output_file
        self.verbose = verbose
        self.link_script = link_script

    def run(self, workdir=None) -> ProcResult:
        # First, enter the workdir
        old_cwd = os.getcwd()
        if workdir is not None:
            os.chdir(workdir)

        # Build the command
        command = ["ld"]
        if self.arch == Arch.i386:
            command += ["-m", "elf_i386"]

        command += ["-o", self.output_file]
        
        if self.link_script is not None:
            command += ["-T", self.link_script]

        command += self.input_files

        # Run the command
        result = run_command_better(command, verbose=self.verbose)

        # Return to the old workdir
        if workdir is not None:
            os.chdir(old_cwd)

        return result

# Simple wrapper around gcc
class GCCCommand:
    def __init__(self, exec_arch: Arch, input_files: list, output_file: str, std_version: str=None, compile_only: bool=False, extra_params: list=[], verbose: bool = False):
        self.arch = exec_arch

        # if input_files is a string, convert to list
        if isinstance(input_files, str):
            input_files = [input_files]

        self.input_files = input_files
        self.output_file = output_file
        self.verbose = verbose
        self.compile_only = compile_only
        self.std_version = std_version
        self.extra_params = extra_params
        

    def run(self, workdir=None) -> ProcResult:
        # First, enter the workdir
        old_cwd = os.getcwd()
        if workdir is not None:
            os.chdir(workdir)

        # Build the command
        command = ["gcc"]
        if self.arch == Arch.i386: 
            command += ["-m16"] #TODO more general

        if self.std_version is not None:
            command += ["-std=" + self.std_version]
        
        if self.compile_only:
            command += ["-c"]
        
        # Add extra params
        command += self.extra_params

        command += ["-o", self.output_file]
        command += self.input_files

        # Run the command
        result = run_command_better(command, verbose=self.verbose)

        # Return to the old workdir
        if workdir is not None:
            os.chdir(old_cwd)

        return result


class ASCommand:
    def __init__(self, exec_arch: Arch, input_files: list, output_file: str, extra_params: list=[], verbose: bool = False):
        self.arch = exec_arch

        # if input_files is a string, convert to list
        if isinstance(input_files, str):
            input_files = [input_files]

        self.input_files = input_files
        self.output_file = output_file
        self.verbose = verbose
        self.extra_params = extra_params

    def run(self, workdir=None) -> ProcResult:
        # First, enter the workdir
        old_cwd = os.getcwd()
        if workdir is not None:
            os.chdir(workdir)

        # Build the command
        command = ["as"]
        if self.arch == Arch.i386: 
            command += ["--32"] #TODO more general

        # Add extra params
        command += self.extra_params
        
        command += ["-o", self.output_file]
        command += self.input_files

        # Run the command
        result = run_command_better(command, verbose=self.verbose)

        # Return to the old workdir
        if workdir is not None:
            os.chdir(old_cwd)

        return result


"""
ENTRY(mystart)
SECTIONS
{
  . = 0x7c00;
  .text : {
    entry.o(.text)
    *(.text)
    *(.data)
    *(.rodata)
    __bss_start = .;
    /* COMMON vs BSS: https://stackoverflow.com/questions/16835716/bss-vs-common-what-goes-where */
    *(.bss)
    *(COMMON)
    __bss_end = .;
  }
  /* https://stackoverflow.com/questions/53584666/why-does-gnu-ld-include-a-section-that-does-not-appear-in-the-linker-script */
  .sig : AT(ADDR(.text) + 512 - 2)
  {
      SHORT(0xaa55);
  }
  /DISCARD/ : {
    *(.eh_frame)
  }
  __stack_bottom = .;
  . = . + 0x1000;
  __stack_top = .;
}

"""