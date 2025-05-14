from microwave2.runners.runner import Runner
from microwave2.images.ubuntu_image import UbuntuDiskImage

from microwave2.results.result import Result, TestResult
from microwave2.results.kernel_log import KernelLog, RawKernelLogResult

from typing import List
from dataclasses import dataclass
import re

import threading
from microwave2.utils.qemu import QemuCommand, QemuKernel
from microwave2.utils.utils import debug_pause
import os

# TODO add more functionality to runner like:
#   - booting multiple times? Checkpointing between boots? 
#   - getting logs other ways than stdout 
#   - getting logs from other places than kernel logs
class KernelLogRunner:
    """Runner that takes in a disk image, runs it, and retrieves/parses kernel logs"""
    def __init__(self, disk_image: UbuntuDiskImage, timeout: float = 600, extra_args: str = None):
        self.disk_image = disk_image
        self.kernel_log = None
        self.timeout = timeout
        self.extra_args = extra_args

    def start_timeout_thread(self, timeout: float, process):
        """Enforce the timeout in a background thread."""
        def _wait_proc() -> None:
            try:
                process.wait(timeout=timeout)
            except Exception as e:
                print(e)
                print("Error: Process likely hanging, terminating")
                process.kill()
                # process.wait()
        waiter = threading.Thread(target=_wait_proc)
        waiter.start()

    def boot(self, timeout: float = 600, extra_args:str=None):
        """Run the target code"""
        print("Running target code")

        if self.kernel_log is not None:
            raise Exception("Kernel log already exists, cannot run again")
        
        self.kernel_log = KernelLog(test_marker=self.disk_image.get_launch_marker())
        
        # For now, just use directory of this file plus aux_logfile.txt
        aux_logfile_path = os.path.join(os.path.dirname(__file__), "aux_logfile.txt")

        print("Booting image")
        process = self.disk_image.boot_image(memory_mb=4096, cores=4, interactive=False, aux_logfile_path=aux_logfile_path, extra_args=extra_args)
        self.start_timeout_thread(timeout, process)

        print("Reading kernel log")
        for line in process.stdout:
            self.kernel_log.add_line(line)
            print(line, end="")

        print("Waiting for process to finish")
        process.wait()

        # IF aux logfile is not None, read it and append to kernel log
        if aux_logfile_path is not None:
            self.kernel_log.add_line("Aux log file:")
            print("Aux log file:")
            with open(aux_logfile_path, "r") as f:
                for line in f:
                    self.kernel_log.add_line(line)
                    print(line, end="")

        # Check process exit code
        if process.returncode != 0:
            print("Error: Process exited with code", process.returncode)
            return Result.failure("Process exited with code " + str(process.returncode))
        else:
            print("Process exited successfully")
            return Result.success()
        
    def run(self) -> TestResult:
        """Run the target code"""
        self.boot(timeout=self.timeout, extra_args=self.extra_args)

        kernel_result = RawKernelLogResult(self.kernel_log)

        return kernel_result

    def get_kernel_log_result(self):
        return self.kernel_log