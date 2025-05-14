# Class to manage a reference linux kernel
# TODO maybe place this file somewhere else?

from microwave2.remote import GitRemoteCode, GitConfig, GitAuthInfo
from microwave2.local_storage import local_paths
import os


REF_

# TODO extend this to be a specific case of the LinuxTarget? Or somehow else merge
# with linux kernels under test 
class LinuxRef(GitRemoteCode):
    def __init__(self, git_auth: GitAuthInfo, local_path: str = None,  ):

        if local_path is None:
            local_path = os.path.join(local_paths.get_targets_build_dir(), "linux_ref")

        git_config = GitConfig(auth=git_auth, 
                               base_url="https://github.com",
                               org="torvalds",
                               repo_name="linux",
                               branch="master")


        super().__init__(local_path=local_path, remote_rel_path=None)
