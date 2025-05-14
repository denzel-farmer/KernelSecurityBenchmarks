# TODO implement
from microwave2.testers.tester import Tester
from microwave2.testers.tester import Tester, TesterConfig

from microwave2.images.raw_image import RawDiskImage
from microwave2.utils.utils import Arch

from microwave2.tests.linux_test import LinuxTest
from microwave2.targets.raw_os_target import RawOSTarget
from microwave2.runners.mem_dump_runner import MemDumpRunner

from microwave2.remote import GitConfig, GitAuthInfo

class RawOSTesterConfig(TesterConfig):
    """Config information about for a tester"""
    def __init__(self, target_config: GitConfig):


        super().__init__(test_config=None, target_config=target_config)
        self.runner_config = None

# Tests where the target is a Floppy Disk Image, and the output is the booted VGA screen
# test_image: RawDiskImage downloads nothing, is a raw image that can be objcopy'ed into
# test: NullTest downloads nothing, builds nothing, runs nothing
# target: BiosTarget downloads target, builds into ELF file and objcopy's into raw image
# runner: QemuRunner runs the raw image, produces VGA output representation that can be queried for strings
class RawOSTester(Tester):
    def __init__(self, config: TesterConfig):
        super().__init__(config)

        exec_arch = config.target_config.exec_arch
        # Warn if exec arch not x86
        if (exec_arch != Arch.X86):
            print("[RawOSTester] Warning: Exec arch is not x86, forcing to x86")
            exec_arch = Arch.X86

        image_name = config.target_config.target_name + ".flp"
        self.test_image = RawDiskImage(arch=exec_arch, image_name=image_name)

        self.test = None # TODO replace with a null class?
        self.target = RawOSTarget(config.target_config)

        self.runner = MemDumpRunner(self.test_image)