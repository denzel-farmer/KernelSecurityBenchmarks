# Test that implements new test interface

from microwave2.tests.test import Test, TestConfig
from microwave2.remote import GitConfig, GitRemoteCode, RemoteCode
from microwave2.targets.target import Target
from microwave2.results.result import Result
from microwave2.utils.utils import dynamic_script_load, Arch, makedirs
from microwave2.images.disk_image import DiskImage


from microwave2.utils.rsync import RsyncCommand
import os

class StaticTestConfig(TestConfig):
    """Config information about a test"""
    def __init__(self, test_name: str, module_name: str, run_method_name: str, arch: str, git_config: GitConfig, test_subdir: str = None, sparse_download: bool = False, build_entrypoint: str = None, target_mod_entrypoint: str = None):
        super().__init__(test_name, module_name, arch, arch, git_config, test_subdir, sparse_download, build_entrypoint, target_mod_entrypoint)
        # Method within test module to run test
        self.run_method_name = run_method_name

class StaticTest(Test):
    def __init__(self, test_config: StaticTestConfig):
        super().__init__(test_config)

    # Override install do nothing
    def install(self, disk_image: DiskImage, target:Target) -> Result:
        """Install test code into disk image by copying into image and setting launch script"""
        print("[StaticTest] No installation needed for static test")
        return Result.success()
    
    def run_test(self, disk_image: DiskImage, target: Target) -> Result:
        """Run the static test on the target"""
        print("[StaticTest] Running test")
        # Run the test

        # Load and execute run entrypoint
        run_method = dynamic_script_load(self.module_path, self.test_config.run_method_name)
        if (run_method is None):
            print(f"[StaticTest] Failed to load run method {self.test_config.run_method_name} from {self.module_path}")
            return Result.failure("Failed to load build method")
        
        run_result = run_method(target=target, disk_image=disk_image)

        self.latest_run = run_result
        return run_result
