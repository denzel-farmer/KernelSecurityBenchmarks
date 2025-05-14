from microwave2.remote import GitConfig, GitRemoteCode, RemoteCode
from microwave2.utils.utils import dynamic_script_load, Arch, makedirs
from microwave2.utils.rsync import RsyncCommand
from microwave2.local_storage import local_paths, rel_path
from dataclasses import dataclass
from microwave2.utils.log import log, warn, error, debug, info
from microwave2.utils.utils import debug_pause

from microwave2.targets.target import Target
from microwave2.results.result import Result

from microwave2.images.disk_image import DiskImage

import os
import subprocess
# TODO support using local repo as source
class TestConfig:
    def __init__(self, 
                 test_name: str, # Name of test within testing framework
                 module_name: str, # Python module name containing test
                 exec_arch: str, # Architecture the test code should be executed on
                 worker_arch: str, # Architecture the test code should be built on
                 git_config: GitConfig, # Git configuration for test code
                 test_subdir: str = None, # Relative path from repo root to relevant test folder
                 sparse_download: bool = False, # Whether to download only test_subdir when cloning test directory
                 build_entrypoint: str = None, # Name of method to call within test module to build test
                 target_mod_entrypoint: str = None # Name of method to call within test module just before target is built
                 ):
        self.test_name = test_name
        self.module_name = module_name
        self.exec_arch = exec_arch
        self.worker_arch = worker_arch
        self.git_config = git_config
        self.test_subdir = test_subdir
        self.sparse_download = sparse_download
        self.build_entrypoint = build_entrypoint
        self.target_mod_entrypoint = target_mod_entrypoint

    @classmethod
    def from_json(cls, json_config: dict):
        """Create a TestConfig from a JSON config"""
        test_name = json_config["test_name"]
        module_name = json_config["module_name"]
        exec_arch = Arch.from_string(json_config["exec_arch"])
        worker_arch = Arch.from_string(json_config["worker_arch"])
        git_config = GitConfig.from_json(json_config["git_config"])
        test_subdir = json_config.get("test_subdir", None)
        sparse_download = json_config.get("sparse_download", False)
        build_entrypoint = json_config.get("build_entrypoint", None)
        target_mod_entrypoint = json_config.get("target_mod_entrypoint", None)

        return cls(test_name=test_name, module_name=module_name, exec_arch=exec_arch, worker_arch=worker_arch, git_config=git_config, test_subdir=test_subdir, sparse_download=sparse_download, build_entrypoint=build_entrypoint, target_mod_entrypoint=target_mod_entrypoint)

    def to_json(self) -> dict:
        """Convert TestConfig to JSON"""
        return {
            "test_name": self.test_name,
            "module_name": self.module_name,
            "exec_arch": self.exec_arch.to_string(),
            "worker_arch": self.worker_arch.to_string(),
            "git_config": self.git_config.to_json(),
            "test_subdir": self.test_subdir,
            "sparse_download": self.sparse_download,
            "build_entrypoint": self.build_entrypoint,
            "target_mod_entrypoint": self.target_mod_entrypoint
        }



class DynamicTestConfig(TestConfig):
    """Config information about a test"""
    def __init__(self, test_name: str, module_name: str, launch_script: str, exec_arch: str, worker_arch: str, git_config: GitConfig, test_subdir: str = None, sparse_download: bool = False, build_entrypoint: str = None, target_mod_entrypoint: str = None):
        super().__init__(test_name, module_name, exec_arch, worker_arch, git_config, test_subdir, sparse_download, build_entrypoint, target_mod_entrypoint)
        # Launch script is name of script to run test within image
        self.launch_script = launch_script

@dataclass
class BuildConfig:
    source_dir: str
    product_dir: str
    exec_arch: Arch # Architecture the test will run on
    worker_arch: Arch # Architecture that the test code will be built on


"""
Test that runner executes on a target
"""
# TODO maybe test code isn't in Git? Maybe inherit from RemoteCode?
# TODO add more specific Test classes that require a more specific format, and e.x. do building for you 
class Test(GitRemoteCode):
    """Generic Test class with standard interface:
    - download (download remote code)
    - build (build test code into build directory, by calling into test code itself)
    - install (install test code into disk image) (abstract)  
    - modify_target (callback to modify target before it is built)
    """
    def __init__(self, test_config: TestConfig):
        # Tests are store remotely in some Git repo, at the relative path 'test_config.test_dir' from repo root
        # Tests are store locally in tests_dir/<repo_name>/<relative path>/
        # Tests are placed in disk image at /tests/<relative path>/

        # Built tests are placed in <test build dir>/<repo_name>/<relative path>

        if (test_config.test_subdir is not None):
            rel_path = test_config.test_subdir
        else:
            # TODO just propogate None rather than adding dots
            rel_path = "."
        
        # rel_path is path to test code directory relative to repo root 
        self.rel_path = rel_path

        # repo_local_path is absolute path to local copy of repo 
        self.repo_local_path = os.path.join(local_paths.get_tests_dir(), test_config.git_config.repo_name)

        # test_local_path is absolute path to local copy of test code (within repo_local_path)
        self.test_local_path = os.path.join(self.repo_local_path, rel_path)
        print("[Test] Local path: " + self.test_local_path)

        # build_path is absolute path to build directory for test code
        # which is <test build dir>/<repo_name>/<relative path>
        self.build_path = os.path.join(local_paths.get_test_build_dir(), test_config.git_config.repo_name, rel_path)
        makedirs(self.build_path)

        super().__init__(local_path=self.repo_local_path, remote_rel_path=rel_path, git_config=test_config.git_config)

        self.test_config = test_config
        # TODO decide on either bash or python runner but not both
        if self.test_config.module_name is not None:
            self.module_path = os.path.join(self.test_local_path, self.test_config.module_name)
        else:
            self.module_path = None

    # API method    
    def download(self) -> Result:
        """Download test code from remote"""

        # Try to setup repo
        try:
            self.setup_repo()
        except Exception as e:
            print(f"[Test] Failed to setup repo: {str(e)}")
            print(f"Exception type: {type(e).__name__}")
            print(f"Exception args: {e.args}")
            return Result.failure("Failed to setup repo")


        return self.update_local(sparse=self.test_config.sparse_download)
    
    # TODO add rebuild support
    def default_build(self) -> Result:
        """Default build just copies test code to build directory"""
        # TODO should this copy the entire repo? Or just the test code?
        print("[Test] Default build method: copying test code to build directory")
        print(f"[Test] Copying {self.test_local_path} to {self.build_path}")
        
        rsync_command = RsyncCommand(source=self.test_local_path, destination=self.build_path, archive=True, verbose=True, force_copy_contents=True)
        success = rsync_command.sync()
        if (not success):
            print(f"[Test] Failed to copy test code to {self.build_path}")
            return Result.failure("Failed to copy test code")
        print("[Test] Successfully copied test code to build directory")
        return Result.success()

    # API method
    # TODO make rebuild=False actually work
    def build(self, rebuild:bool =False) -> Result:
        """Build test code into build directory by calling build entrypoint (if it exists)"""
        
        # Check if there is a build entrypoint in downloaded code
        if (self.test_config.build_entrypoint is None):
            print("[Test] No build entrypoint specified, using default 'build'")
            return self.default_build()
        
        # Load and execute build entrypoint
        build_method = dynamic_script_load(self.module_path, self.test_config.build_entrypoint)
        if (build_method is None):
            print(f"[Test] Failed to load build method from {self.module_path} for entrypoint {self.test_config.build_entrypoint}")
            return Result.failure("Failed to load build method")
        
        print(f"[Test] Loaded build method {build_method}, running")
        debug_pause(f"[Test] Build method: {build_method}", 25)
        config = BuildConfig(source_dir=self.test_local_path,
                                product_dir=self.build_path, 
                                exec_arch=self.test_config.exec_arch,
                                worker_arch=self.test_config.worker_arch)
        
        build_result = build_method(config)
        debug_pause(f"[Test] Build result: {build_result}", 25)
        # TODO why did I save latest build result? Maybe for rebuild?
        self.latest_build = build_result
        # print(build_result)
        return build_result


    # API method (abstract)
    def install(self, disk_image: DiskImage, target:Target, interactive:bool =False) -> Result:
        """Install test code into disk image (specific to test/image type, so must be overridden)"""
        raise NotImplementedError("The install method must be overridden in subclasses")


    # # Outdated method 
    # def build_old(self, root_dir:str, product_dir: str) -> Result:
    #     """Build test code by calling build entrypoint within downloaded test code"""

    #     if (self.test_config.build_entrypoint is None):
    #         print("[Test] No build entrypoint specified, just copying test code")
    #         # Copy local path to root_dir/product_dir
    #         try:
    #             self.copy_local(os.path.join(root_dir, product_dir))
    #         except Exception as e:
    #             print(f"[Test] Failed to copy test code to {product_dir}, {e}")
    #             return Result.failure("Failed to copy test code")
    #         return Result.success()

    #     full_product_dir = os.path.join(root_dir, product_dir)
        
    #     build_method = dynamic_script_load(self.module_path, self.test_config.build_entrypoint)

    #     if (build_method is None):
    #         print(f"[Test] Failed to load build method from {self.module_path} for entrypoint {self.test_config.build_entrypoint}")
    #         return Result.failure("Failed to load build method")
    #     print(build_method)

    #     config = BuildConfig(source_dir=self.test_local_path,
    #                          product_dir=full_product_dir, 
    #                          exec_arch=self.test_config.exec_arch,
    #                          worker_arch=self.test_config.worker_arch)

    #     build_result = build_method(config)

    #     self.latest_build = build_result
    #     return build_result
    
    # API method
    def modify_target(self, target: Target) -> Result:
        """Callback to modify target before it is built"""
        if (self.test_config.target_mod_entrypoint is None):
            print("[Test] No target modification entrypoint specified, skipping target modification step")
            return Result.success()
        

        print(f"[Test] Modifying target {target} with entrypoint {self.test_config.target_mod_entrypoint}")
        mod_method = dynamic_script_load(self.module_path, self.test_config.target_mod_entrypoint)

        build_dir = target.get_build_dir()
        mod_result = mod_method(target, build_dir)
        self.latest_mod = mod_result

        # TODO implement target hash or checkpoint so can rebuild even with modifications 

        return mod_result

    # # TODO move to LinuxTest
    # # TODO need a LinuxTestConfig class? Ugh
    # def get_launch_script_rel_path(self):
    #     relative_base = os.path.relpath(self.test_local_path, local_paths.get_tests_dir())

    #     return os.path.join(relative_base, self.test_config.launch_script)



# class KernelModuleTest(Test):
#     """Test that requires a kernel module"""
#     def __init__(self, test_config: TestConfig, git_config: GitConfig):
#         super().__init__(test_config, git_config)

#     def build(self):
#         # TODO build module for correct architecture 
#         raise NotImplementedError



# TODO test that modifies student kernel? One that adds KUNIT test? 
# All possible with generic Test, but could add support to make it easier

"""
StaticTest - Test to be run on source code, without executing target code
"""


"""
Result of a Test run on a Target (JSON serializable)
"""