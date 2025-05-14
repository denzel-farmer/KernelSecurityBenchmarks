# Test that implements new test interface

from microwave2.tests.test import Test, TestConfig, DynamicTestConfig
from microwave2.targets.target import Target
from microwave2.results.result import Result
from microwave2.images.ubuntu_image import UbuntuDiskImage

from microwave2.utils.rsync import RsyncCommand
import os

class LinuxTest(Test):
    def __init__(self, test_config: DynamicTestConfig):
        super().__init__(test_config)

    # Doesn't override download or build 
    def install_launch_script(self, dest_dir:str, disk_image: UbuntuDiskImage, interactive:bool, target_name: str) -> Result:

        launch_script_rel_path = self.test_config.launch_script
        launch_script_path = os.path.join(dest_dir, launch_script_rel_path)

        try:
            disk_image.set_launch_script(launch_script_path, target_name, autoshutdown=not interactive, autorun=not interactive)
        except Exception as e:
            print(f"Failed to set launch script: {e}")
            return Result.failure("Failed to set launch script")
        return Result.success()

    # Override install to install on disk image
    def install(self, disk_image: UbuntuDiskImage, target:Target, interactive:bool) -> Result:
        """Install test code into disk image by copying into image and setting launch script"""
        print("[LinuxTest] Installing test code into disk image")

        dest_dir = "test" # TODO this actually has to be hardcoded, for launch script to work (very dumb)

        # Copy test code into image
        result = disk_image.sync_folder(self.build_path, dest_dir)
        if (result.is_failure()):
            print("[LinuxTest] Failed to copy test code into image")
            return result
        # rsync_command = RsyncCommand(source=self.build_path, destination=self.build_path, archive=True, verbose=True)
        # rsync_command.sync()


        # Set launch script
        return self.install_launch_script(dest_dir, disk_image, interactive, target.get_target_name())