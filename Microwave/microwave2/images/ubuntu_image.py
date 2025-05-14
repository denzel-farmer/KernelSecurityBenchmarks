import os

# from tempfile import NamedTemporaryFile
# import tarfile 
import shutil
import shlex

import subprocess
# import atexit
import time

from microwave2.results.result import Result, ProcResult
from microwave2.utils.log import log, warn, error, debug, info

from typing import List, Optional

from microwave2.utils.utils import Arch, get_arch_string_ubuntu_url, download_url, run_command, mount_device, umount, debug_pause, makedirs, mount_by_label, bind_mount, run_chroot_command
from microwave2.utils.qemu import launch_kernel_raw, QemuDrive, SimpleQemuParam, QemuCommand, QemuResources, QemuKernel, qemu_nbd_connect, qemu_nbd_disconnect, qemu_img_resize
from microwave2.local_storage import local_paths
from microwave2.images.ubuntu_resources import get_userdata,METADATA,CLOUD_MINIMAL_IMG_URL_ARM,CLOUD_MINIMAL_IMG_URL_X86,CLOUD_IMG_URL_X86,CLOUD_IMG_URL_ARM,build_bash_profile, get_kernel_cmdline
import tempfile
import platform

from microwave2.utils.rsync import RsyncCommand

from microwave2.images.disk_image import DiskImage


FRAMEWORK_TAG = "MICROWAVE FRAMEWORK TESTER"
BOOT_LABEL = "BOOT"

# TODO First priority: make this child of DiskImage
# TODO maybe split TemplateDiskImage from UbuntuDiskImage and TestDiskImage?
# TODO alternative: Make a DiskImageGenerator and simplify DiskImage to just represent a single image
# - Note currently UbuntuDiskImage confusingly isn't a child of DiskImage -- should eventually be
class UbuntuDiskImage(DiskImage):
    """Image for testing, can be built from scratch. Really three copies:
    - base image, unmodified and downloaded from ubuntu
    - template image, modified with cloud-init -- modifications to this are shared for all tests on the machine
    - final image, a copy of the working image that will be modified per test"""
    def __init__(
            self,
            arch: Arch,
            image_name: str,
            temp_dir: str=None,
            output_dir: str=None,
            base_url: str=None,
            size_gb: int=25) -> None:
        
        # Call parent constructor
        super().__init__(arch=arch, image_name=image_name, temp_dir=temp_dir, output_dir=output_dir)

        # self.arch = arch
        
        # if image_name is None:
        #     self.image_name = f"ubuntu-{arch.ubuntu_url_str()}.qcow2"
        # else:
        #     self.image_name = image_name
        # self.image_name = image_name

        self.launch_marker = FRAMEWORK_TAG
        self.size_gb = size_gb
        assert(self.size_gb > 3)
        
        
        # self.temp_workdir = local_paths.get_temp_dir() if temp_dir is None else temp_dir
        # self.output_dir = local_paths.get_workdir() if output_dir is None else output_dir

        self.seed_iso_path = os.path.join(self.temp_workdir, "seed.iso")

        if base_url is None:
            # self.base_url = CLOUD_IMG_URL_X86 if arch == Arch.X86 else CLOUD_IMG_URL_ARM
            self.base_url = CLOUD_MINIMAL_IMG_URL_X86 if arch == Arch.X86 else CLOUD_MINIMAL_IMG_URL_ARM
        else:
            self.base_url = base_url
        
        # self.is_mounted = False
        self.mountpoint = os.path.join(self.temp_workdir, "mountpoint")
        self.boot_partition_mountpoint = os.path.join(self.mountpoint, "boot")
        self.devname = "/dev/nbd2" # TODO make this configurable

        self.use_override_kernel = False
        self.installed_kernel_dir = None

    def base_image_path(self):
        """Path to the base image file"""
        return os.path.join(self.temp_workdir, f"base-ubuntu-{self.arch.ubuntu_url_str()}.qcow2")

    def template_image_path(self):
        """Path to the template image file"""
        return os.path.join(self.temp_workdir, f"template-ubuntu-{self.arch.ubuntu_url_str()}.qcow2")
    
    def download_base_image(self):
        """Unconditionally download the base image from the cloud to temp dir"""

        info("Downloading base image from", self.base_url)

        try:
            download_url(self.base_url, self.base_image_path())
        except Exception as e:
            print(f"Failed to download the image: {e}")
            return Result.failure("Failed to download the image", e)
        return Result.success()
    
    # API method override
    def download(self, redownload=False):
        # Check if already downloaded, and if so, skip
        if (not redownload and os.path.exists(self.base_image_path())):
            info("Base image already downloaded, skipping...")
            return Result.success()
        else:
            return self.download_base_image()

        # TODO check checksum
    
    def override_kernel(self, installed_kernel_dir: str) -> Result:
        """Save the intalled kernel dir path to be used by -kernel parameter to override kernel on boot.
        Also replaces boot partition but for reference only, does not actually boot from /boot. """
        
        # Locate first file beginning with vmlinuz
        # TODO make this more robust
        # Find the first file beginning with vmlinuz in the installed kernel directory
        kernel_files = []
        if os.path.exists(installed_kernel_dir):
            kernel_files = [f for f in os.listdir(installed_kernel_dir) if f.startswith("vmlinuz")]
            
        if not kernel_files:
            error(f"No kernel file found in {installed_kernel_dir}")
            return Result.failure(f"No kernel file (vmlinuz*) found in {installed_kernel_dir}")

        # Get the first kernel file
        kernel_file = kernel_files[0]
        self.installed_kernel_path = os.path.join(installed_kernel_dir, kernel_file)
        debug(f"Found kernel file: {self.installed_kernel_path}")
        self.use_override_kernel = True
        print("Kernel override set to", installed_kernel_dir)

        return Result.success()
        # return self.replace_boot_partition(installed_kernel_dir)

    def replace_boot_partition(self, partition_contents: str) -> Result:
        """Replace contents of the boot partition with the specified folder. Does not fix up grub or efi."""
         
        # Check in edit mode
        if (not self.is_editable()):
            print("Image is not in edit mode, can't replace boot partition")
            return Result.failure("Image is not in edit mode")
        

        # Mount the boot partition
        boot_mountpoint = self.mount_boot_partition()
        if boot_mountpoint is None:
            print("Failed to mount boot partition")
            return Result.failure("Failed to mount boot partition")

        # Delete only files in boot partition, keeping all folders
        # TODO make this more robust--right now delete everything because selecting our kernel
        # in grub is annoying, but totally possible to just set ours as default without deleting others
        try:
            # List all items in boot_mountpoint
            items = os.listdir(boot_mountpoint)
            debug("[UbuntuDiskImage] Items in boot partition:", items)
            
            # Delete only files, skip all directories
            for item in items:
                item_path = os.path.join(boot_mountpoint, item)
                if os.path.isfile(item_path):
                    debug(f"Removing file: {item_path}")
                    run_command(["sudo", "rm", "-f", item_path])
                
            info("[UbuntuDiskImage] Deleted all files in boot partition, kept all folders")
            info("[UbuntuDiskImage] New empty boot partition:", os.listdir(boot_mountpoint))
        except Exception as e:
            error(f"[UbuntuDiskImage] Failed to delete files in boot partition: {e}")
            return Result.failure("Failed to delete files in boot partition", e)


        # Sync the new kernel to the boot partition
        relative_boot_mountpoint = os.path.relpath(boot_mountpoint, self.mountpoint)
        print("Relative boot mountpoint:", relative_boot_mountpoint)
        result = self.sync_folder(partition_contents, relative_boot_mountpoint, delete_contents=False)
        if result.is_failure():
            print("Failed to sync kernel to boot partition")
        return result




    # TODO make this work for arm
    # TODO may just be best to write grub.cfg manually and fully trash /boot
    # Note that this could be avoided by using qemu's -kernel parameter but I'm a masochist (and have trust issues) 
    def replace_kernel(self, installed_kernel_dir: str) -> Result:
        """Replace kernel in the image with the kernel in the specified directory, by:
        1. Mounting the boot partition
        2. Deleting the existing kernel, replacing it with the new kernel
        3. Updating grub
        4. Unmounting the boot partition"""
       
        # Check in edit mode
        if (not self.is_editable()):
            print("Image is not in edit mode, can't replace kernel")
            return Result.failure("Image is not in edit mode")
        

        # Mount the boot partition
        boot_mountpoint = self.mount_boot_partition()
        if boot_mountpoint is None:
            print("Failed to mount boot partition")
            return Result.failure("Failed to mount boot partition")

        # Delete only files in boot partition, keeping all folders
        # TODO make this more robust--right now delete everything because selecting our kernel
        # in grub is annoying, but totally possible to just set ours as default without deleting others
        try:
            # List all items in boot_mountpoint
            items = os.listdir(boot_mountpoint)
            debug("[UbuntuDiskImage] Items in boot partition:", items)
            
            # Delete only files, skip all directories
            for item in items:
                item_path = os.path.join(boot_mountpoint, item)
                if os.path.isfile(item_path):
                    debug(f"Removing file: {item_path}")
                    run_command(["sudo", "rm", "-f", item_path])
                
            info("[UbuntuDiskImage] Deleted all files in boot partition, kept all folders")
            info("[UbuntuDiskImage] New empty boot partition:", os.listdir(boot_mountpoint))
        except Exception as e:
            error(f"[UbuntuDiskImage] Failed to delete files in boot partition: {e}")
            return Result.failure("Failed to delete files in boot partition", e)


        # Sync the new kernel to the boot partition
        relative_boot_mountpoint = os.path.relpath(boot_mountpoint, self.mountpoint)
        print("Relative boot mountpoint:", relative_boot_mountpoint)
        result = self.sync_folder(installed_kernel_dir, relative_boot_mountpoint, delete_contents=False)
        if result.is_failure():
            print("Failed to sync kernel to boot partition")
            return result


        # Hacky way to fix root= problem: add root=

        # Prepare to enter chroot (todo put this into a single chroot manager/wrapper?)
        self.bind_mounts(dev=True, proc=True, sys=True, tmp=True)
        # Enter chroot and update grub
        result = run_chroot_command(self.mountpoint, "update-grub")

        # Exit chroot
        self.bind_umounts()
        self.unmount_boot_partition()

        if result.is_failure():
            print("[UbuntuDiskImage] Failed to update grub")
        else:
            print("[UbuntuDiskImage] Kernel replaced successfully")
        return result

    # API method specific to UbuntuDiskImage
    def sync_folder(self, source: str, dest: str, delete_contents:bool = False) -> Result:
        """Sync the source folder from local disk to the destination folder in the image (must be in edit mode)
        - source: path to local folder on disk
        - dest: path to folder in image, absolute from root
        - delete_contents: delete files in dest before syncing
        """
        print("[ubuntu image] Syncing folder")
        print("Source:", source)
        print("Dest:", dest)
        
        # Check in edit mode
        if (not self.is_editable()):
            print("Image is not in edit mode, can't sync folder")
            return Result.failure("Image is not in edit mode")
        
        # Remove leading slash from dest
        if dest.startswith("/"):
            dest = dest[1:]

        # Construct full destination path
        dest_full = os.path.join(self.mountpoint, dest)
        
        makedirs(dest_full, sudo=True, delete=False)
        print(f"Syncing folder from {source} to {dest_full}")
        print(f"Mountpoint: {self.mountpoint}")
        # Rsync source to dest
        rsync_command = RsyncCommand(source=source, destination=dest_full, archive=True, verbose=False, force_copy_contents=True, delete=delete_contents)
        success = rsync_command.sync_better(sudo=True)

        print("Sync success:", success)
        debug_pause("Folder synced")
        if not success:
            return Result.failure("Failed to sync folder")
        return Result.success()

    # API method from parent
    def construct(self, rebuild=False, editable=False) -> Result:
        """Construct image, placing it output directory"""
        print("Constructing Ubuntu image")
        # Error if already in edit mode
        if (self.is_editable()):
            print("Image is already in edit mode, can't construct")
            return Result.failure("Image is already in edit mode")
        
        # Warn the rebuild does nothiing
        if (rebuild):
            print("[ubuntu image][construct] WARNING: Rebuild flag does nothing for UbuntuDiskImage")
        
        # create output image
        self.create_output_image(rebuild=False, recopy=True)

        # If editable, mount the image
        if (editable):
            self.mount_image()

        # debug_pause("Constructed image", 20)
        # Call parent method, will set edit mode if editable
        return super().construct(rebuild=rebuild, editable=editable)

       
    # API method from parent
    def finish_edit(self):
        """Finish editing the image, and prepare for booting"""
        if (not self.is_editable()):
            print("Image is not in edit mode, can't finish edit")
            return Result.failure("Image is not in edit mode")
        
        self.unmount_image()

        # Clears 'edit mode' flag
        return super().finish_edit()

    def generate_seed_iso(self):
        """Write cloud init config to a file, and create seed ISO image with it"""

        if os.path.exists(self.seed_iso_path):
            print("Replacing existing seed ISO")
            os.remove(self.seed_iso_path)

        user_data_path = os.path.join(self.temp_workdir, "user-data")
        meta_data_path = os.path.join(self.temp_workdir, "meta-data")
 
        # Write user-data and meta-data to files
        with open(user_data_path, "w") as f:
            f.write(get_userdata(self.arch))
        
        with open(meta_data_path, "w") as f:
            f.write(METADATA)

        # Create seed ISO
        subprocess.run([
            "cloud-localds",
            self.seed_iso_path,
            user_data_path,
            meta_data_path
        ], check=True)

        print("Seed ISO created")

    # TODO add a more automatic way to install new packages on image 
    def boot_template_image(self, cloud_init_config=False):
        """Boot template image, possibly with cloud-init seed ISO, modifications will persist until a reconfiguration"""

        # Make sure template image already exists
        if not os.path.exists(self.template_image_path()):
            print("Template image does not exist, can't boot")
            return
        
        seed_iso_path = None
        if cloud_init_config:
            # Generate a seed ISO with the cloud-init config
            self.generate_seed_iso()
            seed_iso_path = self.seed_iso_path

        proc = launch_kernel_raw(
            arch = self.arch,
            image_path=self.template_image_path(),
            cdrom_path=seed_iso_path,
            kernel_path=None,
            redirect=False
        )

        proc.wait()
        return 
        main_image = QemuDrive(self.template_image_path(), format="qcow2", media="disk")
        drives = [main_image]

        if cloud_init_config:
            # Generate a seed ISO with the cloud-init config
            self.generate_seed_iso()
            seed_drive = QemuDrive(self.seed_iso_path, media="cdrom")
            drives.append(seed_drive)

        qemu_cmd = QemuCommand(
            self.arch,
            drives=drives,
            memory_mb=4096,
            cores=4,
            user_network=True,
            nographic=True)

        print(qemu_cmd.build_command())
        process = qemu_cmd.run()
        # Wait for the process to finish
        process.wait()
    
    def build_template_image(self, rebuild=False, redownload=False) -> Result:
        """Create a template image from the base image, and boot it with cloud-init"""
        
        self.download(redownload)

        # Check if template image already exists
        if os.path.exists(self.template_image_path()) and not rebuild:
            print("Template image already exists, skipping build...")
            return

        # Copy the base image to the template image
        shutil.copy(self.base_image_path(), self.template_image_path())

        # Expand underlying disk image size (TODO make size configurable)
        result = qemu_img_resize(self.template_image_path(), self.size_gb)
        if result.is_failure():
            print("Failed to resize image")
            return result

        # Boot the template image with the seed ISO
        self.boot_template_image(cloud_init_config=True)

    def create_output_image(self, rebuild=False, recopy=False):
        """Create a new output image based on template image"""
        if rebuild:
            recopy = True
        # Check if output image already exists
        if os.path.exists(self.output_image_path()) and not recopy:
            print("Output image already exists, skipping creation...")
            return

        # If necessary, download and build the template image
        self.build_template_image(rebuild=rebuild, redownload=False)

        # Copy the template image to the output image
        shutil.copy(self.template_image_path(), self.output_image_path())

    # Mount the output image to free mountpoint
    def mount_image(self):
        """Mount the output image to a free mountpoint"""
        self.unmount_image()
        
        run_command(["sudo", "modprobe", "nbd", "max_part=8"])
        dev = qemu_nbd_connect(self.devname, self.output_image_path())
        if dev is None:
            print("Failed to connect image to nbd")
            return None
        time.sleep(1)
        dev_partition = f"{self.devname}p1"
        mountpoint = mount_device(dev_partition, self.mountpoint)
        if mountpoint is None:
            print("Failed to mount image")
            return None

        assert(mountpoint == self.mountpoint)

        # Chow the mountpoint to the current user
        # run_command(["sudo", "chown", "-R", f"{os.getuid()}", self.mountpoint])
        debug_pause()
        return mountpoint

    def bind_mounts(self, dev: bool=False, proc: bool=False, sys: bool=False, tmp: bool=False):
        """Bind mount /dev, /proc, /sys, and /tmp to the image"""
        if not os.path.exists(self.mountpoint):
            print("Mountpoint does not exist, can't bind mount")
            return None

        if dev:
            dev_path = bind_mount("/dev", f"{self.mountpoint}/dev")
        if proc:
            proc_path = bind_mount("/proc", f"{self.mountpoint}/proc")
        if sys: 
            sys_path = bind_mount("/sys", f"{self.mountpoint}/sys")
        if tmp:
            tmp_path = bind_mount("/tmp", f"{self.mountpoint}/tmp")

        # If any are none, unmount all and fail
        if dev_path is None or proc_path is None or sys_path is None or tmp_path is None:
            self.bind_umounts()
            return None

    def bind_umounts(self):
        """Unmount /dev, /proc, /sys, and /tmp from the image"""
        umount(f"{self.mountpoint}/dev")
        umount(f"{self.mountpoint}/proc")
        umount(f"{self.mountpoint}/sys")
        umount(f"{self.mountpoint}/tmp")

    def mount_boot_partition(self):
        """Mount the boot partition of the image"""
        if not os.path.exists(self.mountpoint):
            print("Mountpoint does not exist, can't mount boot partition")
            return None
        
        # Mount the boot partition
        makedirs(self.boot_partition_mountpoint, sudo=True)
        boot_partition = mount_by_label(BOOT_LABEL, self.boot_partition_mountpoint)
        if not os.path.ismount(boot_partition):
            print("Failed to mount boot partition")
            return None
        
        assert(boot_partition == self.boot_partition_mountpoint)
        print("Boot partition mounted at ", self.boot_partition_mountpoint)
        return self.boot_partition_mountpoint


    def unmount_boot_partition(self):
        umount(self.boot_partition_mountpoint)


    def unmount_image(self):
        self.bind_umounts()
        self.unmount_boot_partition()
        umount(self.mountpoint)
        qemu_nbd_disconnect(self.devname)
        # self.is_mounted = False

    def get_mountpoint(self):
        return self.mountpoint
    
    def get_launch_marker(self):
        return self.launch_marker
    
    # launch_script_path is relative path from /test dir (TODO should change this)
    def set_launch_script(self, launch_script_path, target_name:str, autoshutdown=True, dmesg_redirect=True, autorun=True, script_name="microwave_init.sh"):
        """Set the launch script for the image"""
        if self.mountpoint is None:
            print("No image mounted, can't set launch script")
            return

        # Confirm launch script exists at /test/<launch_script_path>
        # If launch_script_path has leading slash, remove it
        if launch_script_path.startswith("/"):
            rel_launch_script_path = launch_script_path[1:]
        else:
            rel_launch_script_path = launch_script_path
            
        full_launch_script_path = os.path.join(self.mountpoint, rel_launch_script_path)
        image_launch_script_path = os.path.join("/", rel_launch_script_path)
        print("Mountpoint:", self.mountpoint)
        print("Full launch script path:", full_launch_script_path)
        print("Launch script path:", launch_script_path)
        print("Image launch script path:", image_launch_script_path)
        if not os.path.exists(full_launch_script_path):
            print("Launch script not found at", full_launch_script_path)
            debug_pause()
            return
        
        print("Autoshutdown:", autoshutdown)

        target_dir = os.path.join("/target", target_name)

        # TODO allow passing in arbitrary environment variables from caller (shouldn't really know about test and target here)
        init_script = build_bash_profile(image_launch_script_path, target_dir, "/test", autoshutdown=autoshutdown, dmesg_redirect=dmesg_redirect,
                                          marker=self.launch_marker)
        
        print("Constructed init script")
        print(init_script)
        debug_pause()
        # Add launch script to bash profile
        temp_bash_path = os.path.join(self.temp_workdir, f"{script_name}")
        with open(temp_bash_path, "w") as f:
            f.write(init_script)
        # Copy init script to image
        rel_init_script_path = f"root/{script_name}"
        target_init_path_mounted = os.path.join(self.mountpoint, rel_init_script_path)
        # Copy with sudo
        run_command(["sudo", "cp", temp_bash_path, target_init_path_mounted])
        # Make sure script is executable
        run_command(["sudo", "chmod", "+x", target_init_path_mounted])

        # If autorun, add to bash profile
        # autorun=True
        if autorun:
            # Add to bash profile using sudo
            bash_profile_path = os.path.join(self.mountpoint, "root", ".bash_profile")
            target_init_path_root = os.path.join("/", rel_init_script_path) 
            run_command(["sudo", "bash", "-c", f"echo 'source {target_init_path_root}' >> {bash_profile_path}"])

        print("Launch script set")


    def boot_image(self, memory_mb=4096, cores=4, user_network=True, nographic=True, interactive=False, enable_kvm=False, gdb_str: str = None, aux_logfile_path: str=None, extra_args: str=None) -> subprocess.Popen:
        """Boot the image, return subprocess of image (does not wait)"""

        redirect = True
        disable_cloud_init = False
        if interactive:
            redirect = False
            disable_cloud_init = True

        custom_kernel_path = None
        cmdline=""
        if self.use_override_kernel:
            # 
            custom_kernel_path = self.installed_kernel_path
            cmdline = get_kernel_cmdline(disable_cloud_init=disable_cloud_init)
            # # Use the kernel override
            # cmdline = get_kernel_cmdline()
            # kernel = QemuKernel(self.installed_kernel_dir, cmdline=cmdline)
            # custom_kernel = kernel
            if extra_args is not None:
                cmdline += " " + extra_args
    
        process = launch_kernel_raw(arch = self.arch,
                                    image_path=self.output_image_path(),
                                    kernel_path=custom_kernel_path,
                                    cmdline=cmdline,
                                    redirect=redirect, 
                                    aux_logfile_path=aux_logfile_path)
        return process


        main_drive = QemuDrive(self.output_image_path(), format="qcow2", media="disk")

        custom_kernel = None
        if self.use_override_kernel:
            # Use the kernel override
            cmdline = get_kernel_cmdline()
            kernel = QemuKernel(self.installed_kernel_dir, cmdline=cmdline)
            custom_kernel = kernel

        # GDB and kvm are extra simple params
        extra_params = []
        if gdb_str is not None:
            extra_params.append(SimpleQemuParam("-gdb", gdb_str))
        if enable_kvm:
            extra_params.append(SimpleQemuParam("-enable-kvm"))

        qemu_cmd = QemuCommand(
            self.arch,
            disk_image_path=self.output_image_path(),
            resources = QemuResources(memory_mb=memory_mb, cores=cores),
            kernel =custom_kernel,
            network=user_network,
            extra_params=extra_params
        )

        # qemu_cmd = QemuCommand(
        #     self.arch,
        #     drives=[main_drive],
        #     memory_mb=memory_mb,
        #     cores=cores,
        #     user_network=user_network,
        #     nographic=nographic,
        #     enable_kvm=enable_kvm,
        #     kernel=custom_kernel, 
        #     gdb_str=gdb_str)

        print(qemu_cmd.build_command())
        process = qemu_cmd.run(redirect=redirect)
        return process

    def boot_interactive(self, enable_kvm=False, extra_args: str=None):
        """Boot the image interactively"""
        process = self.boot_image(interactive=True, enable_kvm=enable_kvm, extra_args=extra_args)
        process.wait()

    def __del__(self):
        """Destructor to clean up resources"""
        self.unmount_image()
        if os.path.exists(self.output_image_path()):
            os.remove(self.output_image_path())

