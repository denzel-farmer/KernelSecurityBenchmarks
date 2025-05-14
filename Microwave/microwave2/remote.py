from dataclasses import dataclass
from git import Repo
import os
import shutil

from microwave2.local_storage import local_paths, rel_path
from microwave2.results.result import Result


from microwave2.utils.log import log, warn, error, debug, info

from git.exc import InvalidGitRepositoryError

# TODO change name of this file ?

class RemoteCode:
    """
    Represents a chunk of code backed by a remote target
    """

    def __init__(self, local_path: str, remote_rel_path: str = None):
        self.local_path = local_path
        self.remote_rel_path = remote_rel_path
        self.setup_local()

    def setup_local(self):
        """Setup local disk for code, but down update"""
        # Create local path if it doesn't exist
        os.makedirs(self.local_path, exist_ok=True)

 
    def update_local(self):
        """Update local copy of code from remote, without overwriting local changes (fails on conflicts)"""
        raise NotImplementedError
      
    def reset_local(self):
        """Reset local to match remote, overwriting local changes"""
        raise NotImplementedError

    # Delete the local copy of the code entirely
    def delete_local(self):
        if self.check_local_exists():
            print("[RemoteCode] Deleting local copy of code at ", rel_path(self.local_path))
            shutil.rmtree(self.local_path)
        else:
            print("[RemoteCode] No local copy of code to delete at ", rel_path(self.local_path))


    # Build the code 
    def build(self):
        raise NotImplementedError


@dataclass
class GitAuthInfo:
    """Authentication information for a git repository"""
    user: str
    token: str

    @classmethod
    def from_dict(cls, auth: dict):
        return cls.from_json(auth)
        # return cls(
        #     user=auth["username"],
        #     token=auth["token"]
        # )
    
    def to_json(self):
        return {
            "username": self.user,
            "token": self.token
        }
    
    @classmethod
    def from_json(cls, json_auth: dict):
        return cls(
            user=json_auth["username"],
            token=json_auth["token"]
        )

    def get_auth_http_str(self):
        return f"{self.user}:{self.token}"


@dataclass
class GitConfig:
    """Config information for a git repository (currently only GitHub)"""
    auth: GitAuthInfo
    base_url: str
    org: str
    repo_name: str
    branch: str # TODO allow branches other than 'main'
    tag: str = None

    @classmethod
    def from_dict(cls, config: dict):
        return cls.from_json(config)
        # return cls(
        #     auth=GitAuthInfo.from_dict(config["auth"]),
        #     base_url=config["base_url"],
        #     org=config["org"],
        #     repo_name=config["repo_name"],
        #     branch=config["branch"]
        # )

    @classmethod
    def from_json(cls, json_config: dict):
        return cls(
            auth=GitAuthInfo.from_json(json_config["auth"]),
            base_url=json_config["base_url"],
            org=json_config["org"],
            repo_name=json_config["repo_name"],
            branch=json_config["branch"]
        )

    def to_json(self):
        return {
            "auth": {
                "username": self.auth.user,
                "token": self.auth.token
            },
            "base_url": self.base_url,
            "org": self.org,
            "repo_name": self.repo_name,
            "branch": self.branch
        }


    # TODO better way to assemble remote?
    def get_remote_url(self):
        return self.get_remote_url_http()
    
    def get_remote_url_http(self):

        nonuser_url = f"{self.base_url}/{self.org}/{self.repo_name}.git"

        return f"https://{self.auth.get_auth_http_str()}@{nonuser_url}"
        # if self.user is not None and self.token is not None:
        #     return f"https://{self.user}:{self.token}@{nonuser_url}"
        # elif self.user is not None:
        #     return f"https://{self.user}@{nonuser_url}"
        # else:
        #     assert(self.token is None)
        #     return f"https://{nonuser_url}"

        # return f"https://{self.user}:{self.token}@{self.base_url}/{self.org}/{self.repo_name}.git"

# Config for a folder within a git repo
class GitFolderConfig(GitConfig):
    def __init__ (self, auth: GitAuthInfo, base_url: str, org: str, repo_name: str, branch: str, folder_path: str):
        super().__init__(auth, base_url, org, repo_name, branch)
        self.folder_path = folder_path


class GitRemoteCode(RemoteCode):
    """
    Represents a git repository
    """

    def __init__(self, local_path: str, remote_rel_path: str, git_config: GitConfig):
        super().__init__(local_path, remote_rel_path)
        self.git_config = git_config

    def setup_repo(self):
        """Set up repo on disk and in memory, but do not clone/pull/fetch"""
        super().setup_local()
        
        print("[GitRemote] Setting up repo at", self.local_path)
        try:
            self.local_repo = Repo(self.local_path)
        except InvalidGitRepositoryError:
            self.local_repo = None
            # init repo if it doesn't exist
            self.local_repo = Repo.init(self.local_path)

        # Set up remote origin if it does not already exist   
        if 'origin' not in self.local_repo.remotes:
            self.origin = self.local_repo.create_remote('origin', self.git_config.get_remote_url())
        else:
            print("[GitRemote] Remote 'origin' already exists")
            self.origin = self.local_repo.remotes.origin
        
        print("[GitRemote] Remote Set Up, URL:", self.origin.url)


    def update_local(self, sparse: bool = False) -> Result:
        # return Result.success("Update local not implemented yet")
        """Update local copy of code from remote. Sparse only updates with the latest
           version and only the requested remote path"""
        
        # Check out tag if it exists
        if (self.git_config.tag is not None):
            print("[GitRemote] Checking out tag", self.git_config.tag)
            try:
                self.local_repo.git.fetch(tags=True)
                # Brennan used this when checkout failed due to untracked files
                # self.local_repo.git.clean("-xdf")
                self.local_repo.git.checkout(self.git_config.tag)
            except Exception as e:
                print(f"[GitRemote] Checkout Tag Error: {e}")
                return Result.failure("Failed to checkout tag", e)
            
            return Result.success("Checked out tag successfully")
        
        try:
            # print("[GitRemote] Pulling latest from", self.remote_url)
            print("[GitRemote] Pulling to", rel_path(self.local_path))

            if sparse:
                raise NotImplementedError("Sparse pull not implemented yet")
            else:
                self.origin.fetch()
                # Checkout to the branch
                self.local_repo.git.checkout(self.git_config.branch)
                self.local_repo.git.pull('origin', self.git_config.branch)
        except Exception as e:
            print(f"[GitRemote] Pull Repo Error: {e}")
            return Result.failure("Failed to pull repo", e)
        
            
        info("[GitRemote] Pulled repo successfully")
        return Result.success("Pulled repo successfully")

    def reset_local(self):    
        self.repo.git.reset('--hard')
        self.repo.git.clean('-d', '-f')

    def build():
        pass