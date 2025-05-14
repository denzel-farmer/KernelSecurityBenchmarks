from microwave2.remote import GitConfig, GitRemoteCode, RemoteCode
from microwave2.utils.utils import dynamic_script_load, Arch, makedirs
from microwave2.local_storage import local_paths, rel_path
from dataclasses import dataclass

from microwave2.images.disk_image import DiskImage

from microwave2.results.result import Result


import os

class TargetConfig:
    """Config information about a target"""
    def __init__(self, target_name: str, exec_arch: Arch, worker_arch: Arch, git_config: GitConfig, target_subdir: str = None, sparse_download: bool = False):
        self.target_name = target_name
        self.exec_arch = exec_arch
        self.worker_arch = worker_arch
        self.git_config = git_config
        self.target_subdir = target_subdir
        self.sparse_download = sparse_download

    @classmethod
    def from_json(cls, json_config: dict):
        """Create a TargetConfig from a JSON config"""
        target_name = json_config["target_name"]
        exec_arch = Arch.from_string(json_config["exec_arch"])
        worker_arch = Arch.from_string(json_config["worker_arch"])
        git_config = GitConfig.from_json(json_config["git_config"])
        target_subdir = json_config.get("target_subdir", None)
        sparse_download = json_config.get("sparse_download", False)

        return cls(target_name=target_name, exec_arch=exec_arch, worker_arch=worker_arch, git_config=git_config, target_subdir=target_subdir, sparse_download=sparse_download)

    def to_json(self) -> dict:
        """Convert TargetConfig to JSON"""
        return {
            "target_name": self.target_name,
            "exec_arch": str(self.exec_arch),
            "worker_arch": str(self.worker_arch),
            "git_config": self.git_config.to_json(),
            "target_subdir": self.target_subdir,
            "sparse_download": self.sparse_download
        }


    def __str__(self):
        return (f"TargetConfig(target_name={self.target_name}, exec_arch={self.exec_arch}, "
                f"worker_arch={self.worker_arch}, git_config={self.git_config}, "
                f"target_subdir={self.target_subdir}, sparse_download={self.sparse_download})")
    

"""
Test that runner executes on a target
"""
# TODO maybe test code isn't in Git? Maybe inherit from RemoteCode?
# TODO add more specific Test classes that require a more specific format, and e.x. do building for you 
class Target(GitRemoteCode):
    def __init__(self, target_config: TargetConfig):
        print("Target config: ", target_config)
        # if (target_config.target_subdir is not None):
        #     rel_path = target_config.target_subdir
        # else:
        #     rel_path = "."#target_config.target_name
        # TODO move this folder in a repo logic one step higher, share between test and target

        # Absolute path to the target repo
        self.repo_local_path = os.path.join(local_paths.get_targets_dir(), target_config.git_config.repo_name)
        
        # Absolute path to the target folder, which is within the repo
        if (target_config.target_subdir is not None):
            self.target_local_path = os.path.join(self.repo_local_path, target_config.target_subdir)
            # Relative path from repo root to target folder
            self.target_subdir = target_config.target_subdir
        else:
            self.target_local_path = self.repo_local_path
            self.target_subdir = "."
        
        # General idea is that in any spot, the specific target is pointed to by the target local path, which can be
        # 'swapped out' with the target name for a shorter path
        self.target_name = target_config.target_name

        super().__init__(local_path=self.repo_local_path, remote_rel_path=self.target_subdir, git_config=target_config.git_config)

        self.target_config = target_config
        self.build_dir = os.path.join(local_paths.get_targets_build_dir(), target_config.target_name)
        self.temp_dir = os.path.join(local_paths.get_temp_dir(), target_config.target_name)
        makedirs(self.build_dir)
    
    def get_build_dir(self):
        return self.build_dir

    def get_target_name(self):
        return self.target_name
    
    def get_target_common_path(self):
        """Get the path 'targets/common'"""
        return os.path.join(local_paths.get_targets_dir(), "common")
    
    def download(self):
        """Download target code from remote"""
        try:
            self.setup_repo()
        except Exception as e:
            print(f"[Test] Failed to setup repo: {str(e)}")
            print(f"Exception type: {type(e).__name__}")
            print(f"Exception args: {e.args}")
            return Result.failure("Failed to setup repo")

        return self.update_local(sparse=self.target_config.sparse_download)
    
    def build(self, rebuild=False, build_callback=None) -> Result:
        """Should be overridden by specific target types"""
        raise NotImplementedError("Build not implemented (should be overridden by specific target types")
    
    def install(self, test_image: DiskImage):
        """Install target code into the image"""
        raise NotImplementedError("Install not implemented (should be overridden by specific target types)")
    
    def get_build_dir(self):
        return self.build_dir