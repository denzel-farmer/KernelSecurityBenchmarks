

import subprocess
import os
import json 
import time
from enum import Enum
import time
import shutil

import threading
import urllib.request

from microwave2.results.result import Result, ProcResult

from microwave2.utils.log import log, warn, error, debug, info

from tqdm import tqdm


from dataclasses import dataclass

import importlib.util
import sys

PAUSE_LEVEL = 30

def debug_pause(message: str = None, level: int = 5):
    
    if level > PAUSE_LEVEL:
        print("[Debug Pause] {}".format(message))
        input("[Debug Pause] Press enter to continue...")

    return

class Arch(Enum):
    ARM = "arm"
    X86 = "x86"
    i386 = "i386"
    
    @classmethod
    def from_platform(cls):
        if os.uname().machine == "aarch64":
            return cls.ARM
        elif os.uname().machine == "x86_64":
            return cls.X86
        else:
            raise ValueError("Unexpected machine architecture: {}".format(os.uname().machine))

    @classmethod
    def from_string(cls, arch_str: str):
        arm_aliases = ["arm", "arm64", "aarch64"]
        x86_aliases = ["x86", "x86_64", "amd64"]
        
        if arch_str in arm_aliases:
            return cls.ARM
        elif arch_str in x86_aliases:
            return cls.X86
        else:
            raise ValueError("Unexpected architecture string: {}".format(arch_str))

    def ubuntu_url_str(self):
        if self == Arch.ARM:
            return "arm64"
        elif self == Arch.X86:
            return "amd64"
        else:
            raise ValueError("Unexpected architecture: {}".format(self))

    def linux_make_config_str(self):
        if self == Arch.ARM:
            return "arm64"
        elif self == Arch.X86:
            return "x86"
        else:
            raise ValueError("Unexpected architecture: {}".format(self))
        
    def linux_make_str(self):
        if self == Arch.ARM:
            return "arm64"
        elif self == Arch.X86:
            return "x86_64"
        else:
            raise ValueError("Unexpected architecture: {}".format(self))

    def qemu_str(self):
        if self == Arch.ARM:
            return "aarch64"
        elif self == Arch.X86:
            return "x86_64"
        else:
            raise ValueError("Unexpected architecture: {}".format(self))

    def to_str(self):
        return self.linux_make_str()

def get_arch_string_ubuntu_url(arch: Arch) -> str:
    if arch == Arch.ARM:
        return "arm64"
    elif arch == Arch.X86:
        return "amd64"
    else:
        raise ValueError("Unexpected architecture: {}".format(arch))

@dataclass
class BuildConfig:
    source_dir: str
    product_dir: str
    exec_arch: Arch # Architecture the test will run on
    worker_arch: Arch # Architecture that the test code will be built on


def dynamic_script_load(file_path: str, method_name: str):
    
    # Module is end of file path without extension
    module_name = file_path.split("/")[-1].split(".")[0]

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None:
        return None
    module = importlib.util.module_from_spec(spec)
    if module is None:
        return None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    return getattr(module, method_name)

class DownloadProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)


def download_url(url, output_path):
    with DownloadProgressBar(unit='B', unit_scale=True,
                             miniters=1, desc=url.split('/')[-1]) as t:
        urllib.request.urlretrieve(url, filename=output_path, reporthook=t.update_to)

def makedirs(path: str, sudo: bool = False, delete: bool = False):      
    if not sudo:
        if delete:
            if os.path.exists(path):
                warn(f"Deleting {path}")
                shutil.rmtree(path)
        os.makedirs(path, exist_ok=True)
        return
    # Makedirs equivalent but with sudo
    if delete:
        raise ValueError("Delete not supported with sudo")
    run_command(["sudo", "mkdir", "-p", path])

def run_chroot_command(chroot_path: str, command: str) -> ProcResult:
    return run_command_better(["sudo", "chroot", chroot_path, command])
  
    

# TODO combine these into a mount utility class
def umount(image_path: str):
    # print(f"Unmounting image at {image_path}")
    run_command(["sudo", "umount", image_path], suppress_fail=True)

def bind_mount(source: str, dest: str):
    info(f"Bind mounting {source} to {dest}")
    os.makedirs(dest, exist_ok=True)
    succeeded = run_command(["sudo", "mount", "--bind", source, dest])
    if not succeeded:
        umount(dest)
        return None
    return dest

def mount_by_label(label: str, mount_path: str):
    info(f"Mounting device with label {label} to {mount_path}")
    os.makedirs(mount_path, exist_ok=True)
    succeeded = run_command(["sudo", "mount", f"LABEL={label}", mount_path])
    if not succeeded:
        umount(mount_path)
        return None
    return mount_path

def mount_device(device: str, mount_path: str):
    info(f"Mounting device {device} to {mount_path}")
    os.makedirs(mount_path, exist_ok=True)
    succeeded = run_command(["sudo", "mount", device, mount_path])
    if not succeeded:
        umount(mount_path)
        return None
    return mount_path

def run_command(command, cwd: str = None, shell: bool = False, suppress_fail: bool = False):
    info(f"[Command] {' '.join(command)}")
    try:
        result = subprocess.run(command, cwd=cwd, shell=shell, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as e:
        if suppress_fail:
            return False
        error(f"Command failed: {e}")
        error(f"Standard Output:\n{e.stdout}")
        error(f"Standard Error:\n{e.stderr}")
        return False
    return True



def timed(func):
    """
    Decorator that prints how long a function call takes.

    Usage:
        @timed
        def my_function(...):
            # your code
    """
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        elapsed = end_time - start_time
        print(f"[FuncTimer] {func.__qualname__} took {elapsed:.4f} seconds.")
        return result 
    return wrapper


# Emulate subprocess communicate but also print stdout and stderr live
# Assumes proc is already running
def verbose_communicate(proc: subprocess.Popen):
    
    # Function to be launched in a thread, reads from stream, prints, and returns 
    # list of lines read
    def read_stream(stream, output_list):
        while True:
            line = stream.readline()
            if not line:
                break
            debug(line, end='')
            output_list.append(line)

    stdout_lines = []
    stderr_lines = []
    debug("[verbose_communicate] Starting threads to read stdout and stderr")
    # Start threads to read stdout and stderr
    stdout_thread = threading.Thread(target=read_stream, args=(proc.stdout, stdout_lines))
    stderr_thread = threading.Thread(target=read_stream, args=(proc.stderr, stderr_lines))
    debug("[verbose_communicate] Starting threads")
    stdout_thread.start()
    stderr_thread.start()
    debug("[verbose_communicate] Waiting for threads to finish")

    # Wait for threads to finish
    stdout_thread.join()
    stderr_thread.join()
    debug("[verbose_communicate] Threads finished")
    # Convert lists to strings
    stdout = ''.join(stdout_lines)
    stderr = ''.join(stderr_lines)

    return stdout, stderr


# Takes in a command as a list of strings and runs it, returning a ProcResult
# In verbose mode, also prints stdout and stderr live
# Should merge with run_command
def run_command_better(command, verbose: bool = True, cwd :str =None) -> ProcResult:
    str_command = " ".join(command)
    if verbose:
        debug(f"[Command List]  {command}")
        info(f"[Command] {str_command}")

    # Switch to cwd if specified, save previous
    prev_cwd = os.getcwd()
    if cwd is not None:
        info(f"[Command] Changing to directory {cwd}")
        os.chdir(cwd)

    try:
        proc = subprocess.Popen(command,
                    stderr=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    text=True,
                    bufsize=1)
      
        if verbose:
            stdout, stderr = verbose_communicate(proc)
        else:
            stdout, stderr = proc.communicate()

        # Wait for process to finish (TODO necessary?)
        info("[run_command_better] Waiting for process to finish")
        proc.wait()
        info("[run_command_better] Process finished")

    except Exception as e:
        error("Failed to run command: {}".format(str_command))
        error("Error: ", e)
        os.chdir(prev_cwd)
        return ProcResult(returncode=-1, stdout="", stderr="", error=e, message="Failed to run command: {}".format(str_command))



    result = ProcResult(returncode=proc.returncode, stdout=stdout, stderr=stderr)
    os.chdir(prev_cwd)
    return result

    # return result
    # except OSError as e:
    #     print("Failed to run command: {}".format(str_command(command)))
    #     print("Error: ", e)
    #     return ProcResult(returncode=-1, stdout="", stderr="", error=e, message="Failed to run command: {}".format(str_command(command)))

