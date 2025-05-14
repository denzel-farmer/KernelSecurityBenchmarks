import os

from tempfile import NamedTemporaryFile
import tarfile 
import shutil
import shlex

import subprocess
import atexit
import time


# TODO incorperate into config (this is really an attribute of the disk image, must be preprogrammed in)
STARTUP_SCRIPT_NAME = "start_guest_script.sh"
STARTUP_SCRIPT_NAME_SHUTDOWN = "start_guest_script_shutdown.sh"

RESOURCES_DIR = "resources"
# Excluding .tar.gz
# TODO make image generation automated, or at least write good scripts for it 
BASE_IMAGE_NAME_X86 = "base-debian.img"
BASE_IMAGE_NAME_ARM = "base-arm-ubuntu.qcow2"
IMAGE_FORMAT = "qcow2"



class DiskImage(object):
    def __init__(self, arch:Architecture, config: dict) -> None:
        self.arch = arch
        devnum = config.get("temp_nbd_dev")
        if (devnum is None):
            devnum = 0

        self.devname = f"/dev/nbd{int(devnum)}"
        
        self.resource_dir =  os.path.join(os.path.dirname(os.path.abspath(__file__)), RESOURCES_DIR)
        if (self.arch == Architecture.X86):
            self.imagepath = os.path.join(self.resource_dir, BASE_IMAGE_NAME_X86)
        elif (self.arch == Architecture.ARM):
            self.imagepath = os.path.join(self.resource_dir, BASE_IMAGE_NAME_ARM)

        self.mountpoint = config.get("mountpoint")
        if (self.mountpoint is None):
            self.mountpoint = os.path.join(self.resource_dir, "mountpoint")
            os.makedirs(self.mountpoint, exist_ok=True)
               

        self.tempfile = None
        atexit.register(self.cleanup)


    # TODO document that this requires archive and image to have the same name
    def extract_image(self):
        compressed_path = self.imagepath + ".tar.gz"
        
        print("Attempting to extract from:", compressed_path)
        if (not os.path.isfile(compressed_path)):
            print("Couldn't find compressed image")
        else:
            outdir = os.path.dirname(compressed_path)
            compressed = tarfile.open(compressed_path)
            compressed.extractall(path=outdir) # TODO return new output path? 
            compressed.close # TODO will this error on existing files in directory?
            print("Extraction complete")

    def construct_tempfile(self) -> NamedTemporaryFile:
        print("Checking Disk Image:", self.imagepath)
        if (not os.path.isfile(self.imagepath)):
            self.extract_image()
        if (not os.path.isfile(self.imagepath)):
            print("No disk image found")
            return None
        
        print("Found Disk Image File")
        self.tempfile = NamedTemporaryFile()
        
        print("Created temp file", self.tempfile.name)
        print("Copying disk image to temp file...")
        shutil.copy2(self.imagepath, self.tempfile.name)

        return self.tempfile

    def load_nbd(self):
        proc = subprocess.Popen(["sudo", "modprobe", "nbd"])
        proc.wait()

    # TODO handle when commands fail, don't keep going?
    # TODO make this more configurable--different devices?
    # TODO single call to sudo? su root, maybe? or ask at the very beginning?
    def unmount_disconnect(self):
        umnt_cmd_list = ["sudo", "umount", self.mountpoint]
        print("[Command]", shlex.join(umnt_cmd_list))
        umount = subprocess.run(umnt_cmd_list)

        qnbd_cmd_list = ["sudo", "qemu-nbd", "--disconnect", self.devname]
        print("[Command]", shlex.join(qnbd_cmd_list))
        qemu_nbd = subprocess.run(qnbd_cmd_list)

    
    
    def connect_mount(self):
        os.makedirs(self.mountpoint, exist_ok=True)

        self.unmount_disconnect()
        qnbd_cmd_list = ["sudo", "qemu-nbd", f"--connect={self.devname}", self.tempfile.name]
        print("[Command]", shlex.join(qnbd_cmd_list))
        qemu_nbd = subprocess.run(qnbd_cmd_list)
        # sleep 1?
        time.sleep(1)
        mnt_cmd_list = ["sudo", "mount", f"{self.devname}p1", self.mountpoint]
        print("[Command]", shlex.join(mnt_cmd_list))
        mount = subprocess.run(mnt_cmd_list)

    def copy_priv_script(self, source, dest):
        
        copy_cmd = shlex.split(f"sudo cp \"{source}\" \"{dest}\"")
        subprocess.run(copy_cmd)

        chmod_cmd = shlex.split(f"sudo chmod +x \"{dest}\"")
        subprocess.run(chmod_cmd)

    def rsync_dirs(self, source, target, contents_only=True, copy_links=False):
        params = "-rptgoD"
        if (copy_links):
            params += "L"
        else:
            params += "l"


        if (contents_only):
            sync_cmd = shlex.split(f"sudo rsync {params} \"{source}\"/ \"{target}\"")
        else:
            sync_cmd = shlex.split(f"sudo rsync {params} \"{source}\" \"{target}\"")
        print("[Command]", shlex.join(sync_cmd))
        subprocess.run(sync_cmd)
    
    def copy_contents(self, product_dir:str, home_dir_contents: list[str]):
        self.rsync_dirs(os.path.join(product_dir, "lib"),
                        os.path.join(self.mountpoint, "lib"))
        
        self.rsync_dirs(os.path.join(product_dir, "usr"),
                        os.path.join(self.mountpoint, "usr"))
        
        self.rsync_dirs(os.path.join(product_dir, "boot"),
                        os.path.join(self.mountpoint, "boot2"))
        
        for dest_name, source_dir in home_dir_contents:

            copy_links = False
            # TODO pass this in as part of dest, not hardcoded
            if (dest_name == "tests"):
                copy_links = True

            print(f"Copying {source_dir} to {dest_name}")
            print(f"Copy links: {copy_links}")

            self.rsync_dirs(source_dir, os.path.join(self.mountpoint, "root", dest_name), copy_links=copy_links)
            
            # self.rsync_dirs(home_dir, os.path.join(self.mountpoint, "root", "user"))
            # self.rsync_dirs(tests_dir, os.path.join(self.mountpoint, "root", "tests"))
        
    # TODO should probably just remove from disk image
    def delete_start_script(self):
        # TODO figure out how to not use sudo for all of this
        print("Deleting start script")
        start_script_path = os.path.join(self.mountpoint, "root", STARTUP_SCRIPT_NAME)
        print("Deleting", start_script_path)
        delete_cmd = shlex.split(f"sudo rm \"{start_script_path}\"")
        subprocess.run(delete_cmd)


    def copy_start_script(self, auto_shutdown: bool):
        if (auto_shutdown): 
            startup_script_path = os.path.join(self.resource_dir, STARTUP_SCRIPT_NAME_SHUTDOWN)
        else:
            startup_script_path = os.path.join(self.resource_dir, STARTUP_SCRIPT_NAME)
        
        self.copy_priv_script(startup_script_path, os.path.join(self.mountpoint, "root", STARTUP_SCRIPT_NAME))

    def construct(self, product_dir: str, home_dir_contents: list[str], run_script_path: str, auto_shutdown: bool):
        # TODO clean this up
      #  input("Press any key to construct")
        if run_script_path is not None:
            run_script_name = os.path.basename(run_script_path)
            if (run_script_name != "run_tests.sh"):
                raise NotImplementedError(f"Only run_tests.sh is supported at this time (got {run_script_name})")

        if (self.construct_tempfile() is None):
            print("Failed to construct temp file")
            return None
       
        print("Constructed Tempfile")
        
        self.load_nbd()
        self.connect_mount()
        print(f"Product Directory: {product_dir}")
       # print(f"Tests Directory: {tests_dir}")
        print(f"Home Directory Folders: {home_dir_contents}")
     #   input("Press any key to copy")
        self.copy_contents(product_dir, home_dir_contents)
        if run_script_path is not None:
            self.copy_start_script(auto_shutdown)
        else:
            self.delete_start_script()
            print("Running without startup script")

     #   input("Copy done")
        # # For debugging, write full directory tree to a file
        # with open(os.path.join(self.resource_dir, "debug-tree.txt"), "w") as f:
        #     subprocess.run(["sudo", "tree", self.mountpoint], stdout=f)

       # input("Press any key to unmount")
        self.unmount_disconnect()

    def get_path(self) -> str:
        if (self.tempfile is None):
            print("DiskImage not yet constructed")
            return None
        return self.tempfile.name
        
    def get_format(self) -> str:
        return IMAGE_FORMAT

    def cleanup(self):
        # Don't need to worry about tempfile, it cleans itself up
        self.unmount_disconnect() 
    
    def destroy(self):
        self.cleanup()
        if (self.tempfile is not None):
            self.tempfile.close()
        if os.path.exists(self.tempfile.name):
            os.remove(self.tempfile.name)
        
        self.tempfile = None

        
