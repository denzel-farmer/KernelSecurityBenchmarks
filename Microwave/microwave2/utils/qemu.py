
from microwave2.utils.utils import Arch, debug_pause, run_command_better
from microwave2.results.result import Result, ProcResult
import subprocess, os
from microwave2.utils.utils import run_command_better
import shlex

# Scripts dir is the same as this file plus /scripts
# TODO convert to python wrapper 
SCRIPTS_DIR= os.path.join(os.path.dirname(os.path.realpath(__file__)), "qemu_scripts")
ARM_CUSTOM_KERNEL = os.path.join(SCRIPTS_DIR, "launch_arm_custom_kernel.sh")
ARM_UNMODIFIED = os.path.join(SCRIPTS_DIR, "launch_arm_unmodified.sh")
# X86_CUSTOM_KERNEL = os.path.join(SCRIPTS_DIR, "launch_x86_custom_kernel.sh")
X86_CUSTOM_KERNEL = os.path.join(SCRIPTS_DIR, "launch_x86_isolated_custom_kernel.sh")
# X86_UNMODIFIED = os.path.join(SCRIPTS_DIR, "launch_x86_unmodified.sh")
X86_UNMODIFIED = os.path.join(SCRIPTS_DIR, "launch_x86_isolated_unmodified.sh")

# TODO add support for other architectures
def launch_kernel_raw(arch: Arch, image_path: str, kernel_path: str=None, cmdline: str="", cdrom_path: str=None, redirect=True, aux_logfile_path: str=None) -> subprocess.Popen:
    """Launch a kernel with QEMU
    Redirect=true means we capture STDOUT and STDERR, if false let stdio interact"""

    # if aux logfile path is none, use default /tmp/aux_logfile.txt
    if aux_logfile_path is None:
        aux_logfile_path = os.path.join("/tmp", "aux_logfile.txt")
        # raise ValueError("aux_logfile_path cannot be None") # Literally definition of stuppid
    
    # Delete aux logfile if it exists
    if os.path.exists(aux_logfile_path):
        os.remove(aux_logfile_path)

    if arch == Arch.ARM:
        if kernel_path is not None:
            command = [ARM_CUSTOM_KERNEL, image_path, kernel_path]
        else:
            command = [ARM_UNMODIFIED, image_path]
    elif arch == Arch.X86:
        if kernel_path is not None:
            command = [X86_CUSTOM_KERNEL, image_path, kernel_path, aux_logfile_path]
        else:
            command = [X86_UNMODIFIED, image_path, aux_logfile_path]
    else:
        raise ValueError("Unsupported architecture: " + str(arch))

    if cmdline != "":
        command.append(cmdline)

    if cdrom_path is not None:
        command.append(cdrom_path)

    print("Running command:", command)

    # Print debug command joined
    print("Running command:", shlex.join(command))


    debug_pause("Running QEMU command", level=10)

    if (redirect):
        return subprocess.Popen(command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, errors='backslashreplace')
    else:
        return subprocess.Popen(command, 
                        text=True, 
                        errors='backslashreplace')

 



# Python wrapper around QEMU command call



    
# Same directory as this file, QEMU_EFI.fd
# Note, we should probably fetch this dynamically -- on debian/ubuntu, can install qemu-efi-aarch64 package 
# and use /usr/share/qemu-efi-aarch64/QEMU_EFI.fd
# TODO pull this directly?
QEMU_EFI_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "QEMU_EFI.fd")


def qemu_img_resize(path: str, size_gb: int) -> ProcResult:
    """Resize a QEMU image to the specified size"""
    command = ["qemu-img", "resize", path, str(size_gb) + "G"]
    return run_command_better(command, verbose=True)


def qemu_nbd_disconnect(devname: str):
    """Disconnect a QEMU NBD device"""
    try:
        subprocess.run(["sudo", "qemu-nbd", "--disconnect", devname])
    except subprocess.CalledProcessError as e:
        print(f"Error disconnecting QEMU NBD device: {e}")

def qemu_nbd_connect(devname: str, path: str):
    """Connect a QEMU NBD device"""
    try:
        subprocess.run(["sudo", "qemu-nbd", f"--connect={devname}", path])
        return devname
    except subprocess.CalledProcessError as e:
        print(f"Error connecting QEMU NBD device: {e}")
        qemu_nbd_disconnect(devname)
        return None

class QemuParam:
    """Addition to a qemu command, can really include multiple params. Abstract but defines how to add to a command"""
    def __init__(self):
        pass

    def params_list(self) -> list[str]:
        """Return a list of params to add to the command"""
        return []

    def update_command(self, command: list[str]) -> list[str]:
        # Add params list 
        command.extend(self.params_list())
        return command

class SimpleQemuParam(QemuParam):
    """Simple QEMU param, just a string"""
    def __init__(self, param: str, value: str = None):
        self.param = param
        self.value = value

    def params_list(self) -> list[str]:
        """Return a list of params to add to the command"""
        if self.value is None:
            return [self.param]
        else:
            return [self.param, self.value]
        
class QemuDiskFormat:
    """Enum for QEMU disk types/formats"""
    RAW = "raw"
    QCOW2 = "qcow2"
    VDI = "vdi"
    VMDK = "vmdk"

class QemuMediaType:
    """Enum for QEMU media types"""
    DISK = "disk"
    CDROM = "cdrom"

DEVICE_KEY = "-device"

class QemuNetworkParam(QemuParam):
    NETDEV_KEY = "-netdev"
    """QEMU network param wrapper, only supports user mode networking for now"""
    def __init__(self, id: str):
        self.id = id

    def params_list(self) -> list[str]:
        netdev_id = f"nd-{self.id}"
        netdev_params = [self.NETDEV_KEY, f"id={netdev_id},type=user"]
        device_params = [DEVICE_KEY, f"driver=virtio-net-pci,netdev={netdev_id}"]
        return device_params + netdev_params
    

class QemuExplicitDrive(QemuParam):
    BLOCKDEV_KEY = "-blockdev"
    """QEMU wrapper around a block device and drive. Explicitly defines each. For now,
    only supports virtio-blk-pci, but could be extended to support other interfaces."""
    def __init__(self, path: str,
                    format: QemuDiskFormat=QemuDiskFormat.QCOW2,
                    name: str=""):
        self.path = path
        self.format = format
        self.name = name
    
    def blockdev_file_params(self) -> list[str]:
        """Return the blockdev file params"""

        file_blockdev_name = f"file-{self.name}"

        return [self.BLOCKDEV_KEY, f"filename={self.path},node-name={file_blockdev_name},driver=file"]

    def blockdev_params(self) -> list[str]:
        """Return the blockdev params"""
        file_blockdev_name = f"file-{self.name}"
        return [self.BLOCKDEV_KEY, f"node-name={self.name},driver={self.format},file={file_blockdev_name}"]


    def device_params(self) -> list[str]:
        """Return the device params"""
        return [DEVICE_KEY, f"driver=virtio-blk-pci,drive={self.name}"]
    
    def params_list(self) -> list[str]:
        """Return the params list"""
        return self.blockdev_file_params() + self.blockdev_params() + self.device_params()



class QemuInterfaceType:
    """Enum for QEMU drive interface types"""
    IDE = "ide"
    SCSI = "scsi"
    SD = "sd"
    MTD = "mtd"
    FLOPPY = "floppy"
    PFLASH = "pflash"
    VIRTIO = "virtio"
    NONE = "none"

class QemuDrive(QemuParam):
    """QEMU Drive wrapper, which defines both backend and device. It's usually better to separate these to be explicit."""
    def __init__(self, path: str, 
                 format: QemuDiskFormat, 
                 if_type: str = QemuInterfaceType.VIRTIO, 
                 media: str = QemuMediaType.DISK,
                 id: str = None,
                 index: int = None):
        
        self.path = path
        self.format = format
        self.if_type = if_type
        self.media = media
        self.id = id
        self.index = index

    def subparams_list(self, id: str=None, index: int=None):
        base_list = [
            f"file={self.path}"]
        
        if self.format is not None:
            base_list.append(f"format={str(self.format)}")

        if self.if_type is not None:
            base_list.append(f"if={str(self.if_type)}")
        
        if self.media is not None:
            base_list.append(f"media={str(self.media)}")

        if id is not None:
            base_list.append(f"id={id}")

        if index is not None:
            base_list.append(f"index={index}")

        return base_list

    def params_list(self, id: str=None, index: int=None):
        return ["-drive", ",".join(self.subparams_list(id, index))]

# class EfiDrive(QemuDrive):
#     """A special drive that will create EFI pflash file"""
#     def __init__(self, out_path: str, qemu_efi_path: str = QEMU_EFI_PATH):
#         path = out_path
#         format = QemuDiskFormat.RAW
#         if_type = QemuInterfaceType.PFLASH
#         media = QemuMediaType.DISK
#         super().__init__(path=path, format=format, if_type=if_type, media=media)
#         self.qemu_efi_path = qemu_efi_path

#         self.create_outfile()

#     # TODO error checking
#     def create_outfile(self):
#         """Create the out file if it does not exist"""
#         # Remove file
#         if os.path.exists(self.path):
#             os.remove(self.path)
#         # Create file with truncate to 64m
#         run_command_better(["truncate", "-s", "64M", self.path])

#         # Use dd to copy the qemu efi file to the out path
#         run_command_better(["dd", "if=" + self.qemu_efi_path, "of=" + self.path, "conv=notrunc"])

# class VarstoreDrive(QemuDrive):
#     """A special drive that will create EFI varstore pflash"""
#     def __init__(self, out_path: str):
#         path = out_path
#         format = QemuDiskFormat.RAW
#         if_type = QemuInterfaceType.PFLASH
#         media = QemuMediaType.DISK
# #         super().__init__(path=path, format=format, if_type=if_type, media=media)
# #         self.create_outfile()

#     def create_outfile(self):
#         """Create the out file if it does not exist"""
#         # Remove file
#         if os.path.exists(self.path):
#             os.remove(self.path)
#         # Create file with truncate to 64m
#         run_command_better(["truncate", "-s", "64M", self.path])



class QemuKernel(QemuParam):
    """A substitute kernel for Qemu to use"""
    def __init__(self, path: str, initrd: str = None, cmdline: str = None):
        self.path = path
        self.initrd = initrd
        self.cmdline = cmdline

    def params_list(self):
        params = ["-kernel", self.path]
        if self.initrd is not None:
            params.extend(["-initrd", self.initrd])
        if self.cmdline is not None:
            params.extend(["-append", self.cmdline])

        return params

class QemuResources(QemuParam):
    """QEMU resources, such as memory and CPU"""
    def __init__(self, memory_mb: int = 4096, cores: int = 4):
        self.memory_mb = memory_mb
        self.cores = cores

    def params_list(self):
        return ["-m", str(self.memory_mb), "-smp", str(self.cores)]


# class QemuOutputParams(QemuParam):
#     def __init__(self, arch: Arch, log_path: str = None):
#         self.arch = arch
#         self.log_path = log_path
#         # TODO log path not implemented

#     def params_list(self):
#         params = ["-nographic"]
#         if self.arch == Arch.X86:
#             return ["-serial", "stdio"]
#         elif self.arch == Arch.ARM:
#             return ["-serial", "stdio", "-nographic"]
#         else:
#             raise ValueError("Unsupported architecture: " + str(self.arch))


class QemuCommand:
    def __init__(self,
                 arch: Arch,
                 disk_image_path: str,
                 resources: QemuResources = QemuResources(),
                 kernel: QemuKernel = None,
                 network: bool = True,
                 extra_params: list[QemuParam] = []):
        
        self.arch = arch
        self.resources = resources
        self.disk_image_path = disk_image_path
        self.explicit_drive = QemuExplicitDrive(disk_image_path,
                                                format=QemuDiskFormat.QCOW2,
                                                name="main-img")
        self.kernel = kernel
        if network:
            self.network = QemuNetworkParam("netuser")
        else:
            self.network = None
        self.extra_params = extra_params

    def build_command(self) -> list[str]:
        command = ["qemu-system-" + self.arch.qemu_str()]

        command.extend(["-nographic", "-nodefaults"])
        # If arm and no custom kernel, will use ttyAMA0
        if self.arch == Arch.ARM and self.kernel is None:
            command.extend(["-serial", "stdio"])
        else:
            # Otherwise, add serial chardev (for ttyS0)
            command.extend(["-chardev", "stdio,id=serial0"])
            command.extend(["-device", "pci-serial,id=serial0"])

        # Resource command params
        command = self.resources.update_command(command)
        if (self.arch == Arch.ARM):
            command.extend(["-machine", "virt"])
            command.extend(["-cpu", "cortex-a57"])

        # Kernel params (TODO include detailed console management here?)
        if self.kernel is not None:
            command.extend(self.kernel.params_list())
        

        # Add disk image
        command = self.explicit_drive.update_command(command)

        # Add kernel params
        if self.kernel is not None:
            command = self.kernel.update_command(command)

        # Add network params
        if self.network:
            command = self.network.update_command(command)

        # Add extra params
        for param in self.extra_params:
            command = param.update_command(command)

        return command
                 
    def command_str(self) -> str:
        return " ".join(self.build_command())

    def run(self, redirect=False):
        """Run with subprocess"""

        # If interactive, don't redirect (just let connect to stdio)

        qemu_command = self.build_command()
        print("Running command:", self.command_str())
        debug_pause("Running QEMU command", level=15)
        if (redirect):
            return subprocess.Popen(qemu_command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True, errors='backslashreplace')
        else:
            return subprocess.Popen(qemu_command, 
                            text=True, 
                            errors='backslashreplace')

 



# ARM_UEFI_PATH = os.path.dirname(os.path.realpath(__file__)) + "/QEMU_EFI.fd"




# class QemuCommand:
#     def __init__(
#             self,
#             arch: Arch,
#             drives: list[QemuDrive],
#             memory_mb: int = 4096,
#             cores: int = 4,
#             user_network=True,
#             nographic=True,
#             enable_kvm=False,
#             kernel: QemuKernel = None,
#             gdb_str: str = None,
#             extra_params: list[QemuParam] = [],
#     ):  
#         self.arch = arch

#         if self.arch == Arch.ARM:
#             self.machine = "virt"
#             self.cpu = "cortex-a57"
#             self.bios = ARM_UEFI_PATH
#         elif self.arch == Arch.X86:
#             self.machine = None
#             self.cpu = None
#             self.bios = None

#         self.gdb_str = gdb_str

#         self.drives = drives
#         self.memory_mb = memory_mb
#         self.cores = cores
#         self.user_network = user_network
#         self.nographic = nographic
#         self.enable_kvm = enable_kvm
#         self.kernel = kernel
#         self.extra_params = extra_params

#     def build_command(self) -> str:
#         command = ["qemu-system-" + self.arch.qemu_str()]
#         command.extend(["-m", str(self.memory_mb)])
#         command.extend(["-smp", str(self.cores)])

#         if self.machine is not None:
#             command.extend(["-machine", self.machine])
        
#         if self.cpu is not None:
#             command.extend(["-cpu", self.cpu])

#         index = 0
#         for drive in self.drives:
#             drive.id = f"drive{index}"
#             drive.index = index
#             command = drive.update_command(command)
#             index += 1

#         if self.user_network:
#             command.extend(["-net", "user", "-net", "nic"])

#         if self.nographic:
#             command.extend(["-nographic"])

#         if self.enable_kvm:
#             # TODO warn if KVM is not available
#             command.extend(["-enable-kvm"])

#         if self.kernel is not None:
#             command.extend(self.kernel.params_list())
        
#         if self.bios is not None:
#             command.extend(["-bios", self.bios])

#         if self.gdb_str is not None:
#             command.extend(["-gdb", self.gdb_str])

#         # Add extra params
#         for param in self.extra_params:
#             command = param.update_command(command)

#         return command
    
#     def command_str(self) -> str:
#         return " ".join(self.build_command())

#     def run(self, redirect=False):
#         """Run with subprocess"""
#         qemu_command = self.build_command()
#         print("Running command:", self.command_str())
#         debug_pause("Running QEMU command", level=15)
#         if (redirect):
#             return subprocess.Popen(qemu_command,
#                     stdin=subprocess.PIPE,
#                     stdout=subprocess.PIPE,
#                     stderr=subprocess.STDOUT,
#                     text=True, errors='backslashreplace')
#         else:
#             return subprocess.Popen(qemu_command, 
#                             text=True, 
#                             errors='backslashreplace')




