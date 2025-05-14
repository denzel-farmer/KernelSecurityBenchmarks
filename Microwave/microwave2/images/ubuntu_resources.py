from microwave2.utils.utils import Arch

# This cloud-init config creates a user with the username "ubuntu" and password "password",
# and sets up autologin for the root user on ttyS0.

import os


def get_userdata(arch: Arch) -> str:

    if arch == Arch.ARM:
        cloud_init_tty = "ttyAMA0"
        boot_tty = "ttyS0"
    elif arch == Arch.X86:
        boot_tty = "ttyS0"
        cloud_init_tty = "ttyS0"
    else:
        raise ValueError("Unexpected architecture: {}".format(arch))

    return f"""
#cloud-config
disable_root: false

users:
  - name: ubuntu
    gecos: "Ubuntu User"
    groups: [sudo]
    shell: /bin/bash
    lock_passwd: false
    sudo: ["ALL=(ALL) NOPASSWD:ALL"]

chpasswd:
  list: "ubuntu:password\nroot:rootpassword"
  expire: false

write_files:
  - path: /etc/systemd/system/serial-getty@{boot_tty}.service.d/autologin.conf
    owner: root:root
    permissions: '0644'
    content: |
      [Service]
      ExecStart=
      ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
  - path: /etc/systemd/system/serial-getty@{cloud_init_tty}.service.d/autologin.conf
    owner: root:root
    permissions: '0644'
    content: |
      [Service]
      ExecStart=
      ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
  - path: /etc/sysctl.d/99-console-loglevel.conf
    content: |
      kernel.printk = 7 7 1 7

runcmd:
  - sudo passwd -d root
  - apt-get update
  - apt-get -y upgrade
  - apt-get -y install git python3 python3-pip
  - systemctl daemon-reload
  - systemctl restart serial-getty@{cloud_init_tty}.service
  - systemctl restart serial-getty@{boot_tty}.service
  - sed -i -E '/^GRUB_CMDLINE_LINUX_DEFAULT="/ s/console={boot_tty}(,115200)?/console={boot_tty},115200 earlyprintk=serial,{boot_tty},115200 ignore_loglevel root=\/dev\/vda1/' /etc/default/grub.d/50-cloudimg-settings.cfg
  - update-grub
  - growpart /dev/vda 1
  - resize2fs /dev/vda1
  - df -h


power_state:
    mode: poweroff
    message: Bye Bye
    timeout: 30
    condition: True
"""

def get_kernel_cmdline(disable_cloud_init:bool=False) -> str:
    cmdline = "console=ttyS0,115200 earlyprintk=serial,ttyS0,115200 ignore_loglevel root=/dev/vda1"
    if disable_cloud_init:
        cmdline += " cloud-init=disabled"
    return cmdline

# def get_kernel_cmdline(arch: Arch) -> str:
#     if arch == Arch.ARM:
#         return "console=ttyAMA0,115200 earlyprintk=serial,ttyAMA0,115200 ignore_loglevel"
#     elif arch == Arch.X86:
#         return "console=ttyS0,115200 earlyprintk=serial,ttyS0,115200 ignore_loglevel"
#     else:
#         raise ValueError("Unexpected architecture: {}".format(arch))

def build_bash_profile(launch_script_path, target_dir, test_dir, marker=None, autoshutdown=False, dmesg_redirect=False,
                       noop_exec=False) -> str:
    script_lines = [
        "#!/bin/bash",
        "set +x", # Probably don't want this always
        f"export TARGET_DIR={target_dir}",
        f"export TEST_DIR={test_dir}",
        f"export LAUNCH_SCRIPT={launch_script_path}"]
    

    # Construct marker line
    if marker is not None:
        marker_line = f"echo \"{marker}\""
        if dmesg_redirect:
            marker_line = f"{marker_line} > /dev/kmsg"

    execute_line = f"source $LAUNCH_SCRIPT"
    if dmesg_redirect:
        # Redirect all output of the launch script to /dev/kmsg
        execute_line = f"source $LAUNCH_SCRIPT > /dev/kmsg"


    if noop_exec:
        # Do not execute the launch script, just print it
        execute_line = f"echo \"LAUNCH COMMAND: {execute_line}\""

    script_lines.append(marker_line)
    script_lines.append(execute_line)
    script_lines.append(marker_line)

    if autoshutdown:
        script_lines.append("shutdown now")

    
    return "\n".join(script_lines) + "\n"
    


METADATA = """
instance_id: ubuntu-testing
local-hostname: ubuntu-testing
"""


RELEASE = "noble"
RELEASE_NUMBER = "24.04"
IMAGE_BASE_NAME = f"{RELEASE}-server-cloudimg-"

CLOUD_BASE_URL = f"https://cloud-images.ubuntu.com/{RELEASE}/current/"
CLOUD_IMG_URL_X86 = f"{CLOUD_BASE_URL}{IMAGE_BASE_NAME}amd64.img"
CLOUD_IMG_URL_ARM = f"{CLOUD_BASE_URL}{IMAGE_BASE_NAME}arm64.img"

MINIMAL_BASE_NAME = f"ubuntu-{RELEASE_NUMBER}-minimal-cloudimg-"
CLOUD_MINIMAL_BASE_URL = f"https://cloud-images.ubuntu.com/minimal/releases/{RELEASE}/release/"
CLOUD_MINIMAL_IMG_URL_X86 = f"{CLOUD_MINIMAL_BASE_URL}{MINIMAL_BASE_NAME}amd64.img"
CLOUD_MINIMAL_IMG_URL_ARM = f"{CLOUD_MINIMAL_BASE_URL}{MINIMAL_BASE_NAME}arm64.img"

# https://cloud-images.ubuntu.com/minimal/releases/noble/release/ubuntu-24.04-minimal-cloudimg-amd64.img