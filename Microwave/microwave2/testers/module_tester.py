from microwave2.testers.tester import Tester, TesterConfig

from microwave2.images.ubuntu_image import UbuntuDiskImage

from microwave2.tests.linux_test import LinuxTest
from microwave2.targets.kernel_module_target import KernelModuleTarget
from microwave2.runners.kernel_log_runner import KernelLogRunner

from microwave2.remote import GitConfig, GitAuthInfo

                       

# Tests where the target is a Kernel Module, and the test runs on an Ubuntu image
class KernelModuleTester(Tester):
    def __init__(self, config: TesterConfig):
        super().__init__(config)

        exec_arch = config.test_config.exec_arch
        image_name = config.test_config.test_name + "-" + config.target_config.target_name + ".img"
        self.test_image = UbuntuDiskImage(arch=exec_arch, image_name=image_name)

        # TODO make custom test for Kernel Modules?
        self.test = LinuxTest(config.test_config)
        self.target = KernelModuleTarget(config.target_config)

        self.runner = KernelLogRunner(self.test_image)
