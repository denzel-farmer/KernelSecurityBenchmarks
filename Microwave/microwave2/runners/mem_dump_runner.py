from microwave2.runners.runner import Runner
from microwave2.images.raw_image import RawDiskImage

from microwave2.results.result import Result, TestResult, ProcResult
from microwave2.results.kernel_log import KernelLog, RawKernelLogResult

from typing import List
from dataclasses import dataclass
import re, os, time

import json

import threading
from microwave2.utils.qemu import QemuCommand, QemuKernel
from microwave2.utils.utils import debug_pause, run_command_better
from microwave2.local_storage import local_paths

import string as str_lib

# Wrapper around VGA memory dump 

@dataclass
class VGAString:
    string: str
    # list of tuples of (color, start index)
    colors: list[int,int]
    start_pos: int

    def __str__(self):
        return f"String: \"{self.string}\", Colors: {self.colors}, Start Index: {self.start_pos}"
    
    def __repr__(self):
        return self.__str__()

    def add_char(self, char: str, color: int):
        self.string += char

        # if color is different from last color, add new color
        if color != self.colors[-1][0]:
            color_tuple = (color, len(self.string) - 1)
            self.colors.append(color_tuple)
    
    def get_string(self):
        return self.string
    
    def get_start_pos(self):
        return self.start_pos
    
    def get_colors(self):
        return self.colors

    def get_used_colors(self):
        return set([color for color, _ in self.colors])
    
 

class VGAMemoryDump(TestResult):
    def __init__(self, start_address: int, end_address: int, data: bytes):
        self.start_address = start_address
        self.end_address = end_address
        self.data = data

        super().__init__(sub_results=[])

    def to_json(self):
        return {
            "start_address": self.start_address,
            "end_address": self.end_address,
            "data": self.get_hexdump()
        }

    def to_json_file(self, file_path: str):
        print("[VGAMemoryDump] Writing memory dump to file: ", file_path)
        with open(file_path, "w") as f:
            json.dump(self.to_json(), f)

    @classmethod
    def from_json_file(cls, file_path: str):
        with open(file_path, "r") as f:
            data = json.load(f)
            start_address = data["start_address"]
            end_address = data["end_address"]
            hexdump = bytes.fromhex(data["data"])
            return cls(start_address, end_address, hexdump)


    def is_success(self) -> bool:
        subtest_success = super().is_success()
        if not subtest_success:
            return False
        
        # Also check that data length is correct
        return len(self.data) == (self.end_address - self.start_address)


    def get_start_address(self):
        return self.start_address

    def get_end_address(self):
        return self.end_address

    def get_data(self):
        return self.data
    
    def __str__(self):
        return f"VGAMemoryDump(start_address={self.start_address}, end_address={self.end_address}, data={self.get_hexdump()})"

    def get_hexdump(self, sep: str = " ") -> str:
        return self.data.hex(sep)

    # string of all printable characters except for space
    VGA_ALPHABET = str_lib.printable.replace(" ", "")

    # Extract all strings from vga hex file 
    def extract_strings(self, alphabet=VGA_ALPHABET) -> List[VGAString]:        
        alphabet_bytes = bytes(alphabet, "utf-8")

        all_strings = []

        curr_string = None
        index = 0
        # iterate over each byte 
        while index < len(self.data)-1:
            # attempt to convert byte to untf 8
            byte = self.data[index:index + 1]
            
            if byte in alphabet_bytes:
                char = byte.decode("utf-8")

                # print("Saw char: ", char)
                # print("Byte: ", byte)
                # if byte is in alphabet and we are not in a string, start a new string and read color byte
                if curr_string is None:
                    init_colors = [(self.data[index + 1], 0)]
                    curr_string = VGAString(string=char, colors=init_colors, start_pos=index // 2)
                    # curr_string = {"string": char, "color": set([self.data[index + 1]]), "start_pos": index // 2}
                # if byte is in alphabet and we are in a string, add byte to string and read color byte
                else:
                    curr_string.add_char(char, self.data[index + 1])
                    # curr_string["string"] += char
                    # curr_string["color"].add(self.data[index + 1])
                
                index += 2 # skip color byte
            else:
                # if byte is not in alphabet and we are in a string, add string to list and reset string
                if curr_string is not None:
                    # print("Found string: ", curr_string)
                    all_strings.append(curr_string)
                    curr_string = None
                # Otherwise, just move on
                index += 1

        # add last string   
        if curr_string is not None:
            all_strings.append(curr_string)

        self.all_strings = all_strings
        return all_strings


# TODO add more functionality to runner like:
#   - booting multiple times? Checkpointing between boots? 
#   - getting logs other ways than stdout 
#   - getting logs from other places than kernel logs
class MemDumpRunner:
    """Runner that takes in a disk image, runs it, and dumps memory"""
    def __init__(self, disk_image: RawDiskImage, timeout: float = 30):
        self.disk_image = disk_image
        self.mem_dump = None
        self.timeout = timeout

        self.mem_dump_path = os.path.join(local_paths.get_temp_dir(), f"{disk_image.get_image_name()}.memdump")

    def start_timeout_thread(self, timeout: float, process):
        """Enforce the timeout in a background thread."""
        def _wait_proc() -> None:
            try:
                process.wait(timeout=timeout)
            except Exception as e:
                print(e)
                print("Error: Process likely hanging, terminating")
                process.terminate()
                process.wait()
        waiter = threading.Thread(target=_wait_proc)
        waiter.start()

    # Call GDB to dump memory
    def dump_memory(self, start_address: int, end_address:int, gdb_port: int = 1234) -> ProcResult:
        command = ["gdb-multiarch", "-batch"]
        command += ["-ex", f"target remote :{gdb_port}"]
        command += ["-ex", f"dump memory {self.mem_dump_path} {hex(start_address)} {hex(end_address)}"]
        command += ["-ex", "kill"]

        print("[MemDumpRunner] Dumping memory")
        print("[MemDumpRunner] Command: ", command)
        debug_pause("About to dump to file {}".format(self.mem_dump_path))
        result = run_command_better(command)
        print("[MemDumpRunner] Memory dump complete")
        if result.is_failure():
            print("[MemDumpRunner] Error dumping memory: ", result)
            return result
        # Wait for memory dump to finish (TODO find better way to do this)
        time.sleep(2)
        # debug_pause("Press enter to read memory dump")
        # Load the memory dump
        mem_data = open(self.mem_dump_path, "rb").read()
        # print("[MemDumpRunner] Memory dump data: ", mem_data)
        self.mem_dump = VGAMemoryDump(start_address, end_address, mem_data)
        print("[MemDumpRunner] Memory dump loaded, printing strings")
        # Print all strings
        strings = self.mem_dump.extract_strings()
        for string in strings:
            print(string)

        print("[MemDumpRunner] Strings printed")
        return result

    def get_mem_dump(self):
        return self.mem_dump
    
    def boot(self, timeout: float = 600) -> ProcResult:
        """Run the target code"""
        print("Running target code")

        if self.mem_dump is not None:
            return Result.failure("Memory dump already exists, cannot run again")

        print("[MemDumpRunner] Booting image")
        gdb_port = 1234
        gdb_str = f"tcp::{gdb_port}"
        process = self.disk_image.boot_image(gdb_str=gdb_str)
        debug_pause("Launched image, press enter to start timeout thread")
        self.start_timeout_thread(timeout, process)

        print("[MemDumpRunner] Dumping memory")
        start_addr, end_addr = self.disk_image.get_vga_memory_range()
        result = self.dump_memory(start_addr, end_addr, gdb_port)
        if result.is_failure():
            return result
        print("[MemDumpRunner] Memory dump complete")

        # Wait on process
        process.wait()

        # Make a ProcResult to return
        return ProcResult(returncode=process.returncode, stdout="", stderr="")

        
    def run(self) -> TestResult:
        """Run the target code"""
        result = self.boot(timeout=self.timeout)
        if result.is_failure():
            return result
        
        return self.mem_dump
