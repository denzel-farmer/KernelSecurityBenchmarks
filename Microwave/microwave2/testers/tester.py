"""
Main controller -- Tester that executes Tests on Targets with Runner
"""
from typing import Dict

import os

from microwave2.results.result import Result, TestResult

from microwave2.runners.construct import select_runner
from microwave2.targets.target import Target, TargetConfig
from microwave2.targets.kernel_module_target import KernelModuleTarget
from microwave2.tests.test import Test, TestConfig
from microwave2.utils.utils import dynamic_script_load, Arch, BuildConfig, makedirs, debug_pause

from microwave2.runners.runner import Runner, RunnerConfig
from microwave2.runners.kernel_log_runner import KernelLogRunner

from microwave2.images.disk_image import DiskImage


from microwave2.utils.log import log, warn, error, debug, info
from microwave2.utils.utils import timed

from dataclasses import dataclass


@dataclass
class TesterConfig:
    """Config information about for a tester"""
    test_config: TestConfig
    target_config: TargetConfig
    extra_args: str = None # TODO move to the right spot
    
    def get_run_name(self):
    # Concatenate test and target name
        return self.test_config.target_name + "-" + self.target_config.test_name
    
    @classmethod
    def from_json(cls, json_config: Dict):
        """Create a TesterConfig from a JSON config"""
        test_config = TestConfig.from_json(json_config["test"])
        target_config = TargetConfig.from_json(json_config["target"])
        
        return cls(test_config=test_config, target_config=target_config)

    def to_json(self) -> Dict:
        """Convert TesterConfig to JSON"""
        return {
            "test": self.test_config.to_json(),
            "target": self.target_config.to_json()
        }

class Tester:
    """Tester that executes Tests on Targets with Runner"""
    def __init__(self, config: TesterConfig):
        self.config = config
        # Components should be initialized by subclasses
        self.test = None
        self.target = None
        self.test_image = None
        self.runner = None

    def download_test(self) -> Result:
        """Download the test code"""
        if (self.test is None):
            return Result.success()
        
        result = self.test.download()
        if (result.is_failure()):
            info("[Tester] Test download failed")
            return result
        return result
    
    def download_target(self) -> Result:
        """Download the target code"""
        if (self.target is None):
            return Result.success()
        
        result = self.target.download()
        if (result.is_failure()):
            info("[Tester] Target download failed")
            return result
        return result

    def download(self) -> Result:
        """Download the test code, target code, and testing image"""


        result = self.download_test()
        if (result.is_failure()):
            info("[Tester] Test download failed")
            return result
        
        result = self.download_target()
        if (result.is_failure()):
            info("[Tester] Target download failed")
            return result
        
        result = self.test_image.download()
        if (result.is_failure()):
            info("[Tester] Test image download failed")
            return result
        return result
    


    def build_test_code(self) -> Result:
        """Build test and target code"""
        if (self.test is None):
            return Result.success()
        
        result = self.test.build()
        if (result.is_failure()):
            info("[Tester] Test build failed")
            return result
        return result

    def build_target_code(self) -> Result:
        """Build target code"""
        if (self.target is None):
            return Result.success()
        
        result = self.target.build()
        if (result.is_failure()):
            info("[Tester] Target build failed")
            return result
        
        return Result.success()

    
    def install_test(self, interactive) -> Result:
        """Install test code into the test image"""
        if (self.test is None):
            return Result.success()
        
        result = self.test.install(self.test_image, self.target, interactive)
        if (result.is_failure()):
            info("[Tester] Test install failed")
            return result
        
        return Result.success()
    
    def install_target(self, interactive) -> Result:
        """Install target code into the test image"""
        if (self.target is None):
            return Result.success()
        
        result = self.target.install(self.test_image)
        if (result.is_failure()):
            info("[Tester] Target install failed")
            return result
        
        return Result.success()
    
    # More generic replacement for build() function, should eventually replace it (requires tests and targets to implement install)
    @timed
    def build(self, rebuild=False, interactive=False) -> Result:
        """Build test and target code, and install in a constructed test image"""
        debug_pause("[Tester] DISK BUILDING PHASE: START, now building test and target code")

        result = self.build_test_code()
        if (result.is_failure()):
            return result
        
        result = self.build_target_code()
        if (result.is_failure()):
            return result

        # return Result.failure("build() not implemented for this tester")
        # Construct the base test image 
        debug_pause("[Tester] DISK BUILDING PHASE: IMAGE, now creating image and installing test and target artifacts")
        result = self.test_image.construct(rebuild=rebuild, editable=True)
        if (result.is_failure()):
            info("Failed to construct test image")
            return result

        # Install test and target code into the image
        result = self.install_test(interactive)
        if (result.is_failure()):
            return result
        
        result = self.install_target(interactive)
        if (result.is_failure()):
            return result

        # Mark the image as finished editing (for UbuntuDiskImage, unmounts)
        self.test_image.finish_edit()

        debug_pause("[Tester] FINISHED BUILD PHASE")
        return Result.success()

    # Class method to clear all artifacts, will delete .working directory
    @classmethod
    def clean_all(cls):
        """Clean all artifacts"""
        # TODO implement
        raise NotImplementedError("clean_all not implemented")
        pass

    # Class method to clear shared disk artifacts (including all target and test artifacts)
    @classmethod
    def clear_shared_artifacts(cls):
        """Clear shared artifacts"""
        # TODO implement
        raise NotImplementedError("clear_shared_artifacts not implemented")
        pass

    # Clear all artifacts associated with specific target
    @classmethod
    def clear_target_artifacts(cls, target_name: str):
        """Clear artifacts associated with target"""
        # TODO implement
        raise NotImplementedError("clear_target_artifacts not implemented")
        pass

    # # TODO this really is specific to Linux, maybe move down a level so FloppyBootTester isn't overriding so much?
    # # Would make a LinuxTester that builds tests into an Ubuntu disk image and a FloppyBootTester that builds tests into a raw disk image
    # # Or replace with build_image function above
    # def build(self, rebuild=False, interactive=False) -> Result:
    #     """Build test code and target code into the test image"""
        
    #     self.test_image.create_output_image(rebuild=rebuild)
    #     img_root_dir = self.test_image.mount_image()
    #     info(f"Mounted image at {img_root_dir}")
    #     if (img_root_dir is None):
    #         info("Failed to mount image")
    #         return Result.failure("Failed to mount image")
        
    #     # TODO add rebuild flag to this 
    #     test_build_result = self.test.build(root_dir=img_root_dir, product_dir="test")
    
    #     if (test_build_result.is_failure()):
    #         info("[Test] Test build failed, skipping target build step")
    #         self.test_image.unmount_image()
    #         return test_build_result
        
        
    #     self.test_image.set_launch_script(os.path.join("/test/", self.test.get_launch_script_rel_path()), autoshutdown=not interactive, autorun=not interactive)

    #     test_callback = self.test.modify_target
    #     target_build_result = self.target.build(build_callback=test_callback, root_dir=img_root_dir, product_dir="target")

    #     if (target_build_result.is_failure()):
    #         info("[Target] Target build failed")
    #         self.test_image.unmount_image()
    #         return target_build_result
        
    #     self.test_image.unmount_image()
    #     return target_build_result
    
    # TODO move to kernel / module testers?
    def run_interactive(self) -> Result:
        result = self.test_image.boot_interactive(extra_args=self.config.extra_args)
        return result

    def run(self) -> TestResult:
        """Use the runner to launch the test on the target"""
        info("Running test placeholder")
        # TODO check that build was successful before running
        test_result = self.runner.run()
        return test_result
