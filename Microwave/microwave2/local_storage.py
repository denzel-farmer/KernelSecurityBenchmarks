
import os

class LocalPathManager:
    """Class to manage directories used by Microwave 2.0"""
    def __init__(self, workdir: str=None):
        # Main directory where working files are stored

        cur_dir = os.path.dirname(__file__)

        # Path to the root directory of the python project ('microwave-2.0')
        self.project_dir = os.path.abspath(os.path.join(cur_dir, '..'))
        
        self.workdir = workdir
        if self.workdir is None:
            self.workdir = os.path.join(self.project_dir, ".working")

        # Create the working directory and subdirectores if they don't exist
        os.makedirs(self.workdir, exist_ok=True)
        os.makedirs(self.get_tests_dir(), exist_ok=True)
        os.makedirs(self.get_targets_dir(), exist_ok=True)
        os.makedirs(self.get_manifests_dir(), exist_ok=True)
        os.makedirs(self.get_results_dir(), exist_ok=True)
        os.makedirs(self.get_temp_dir(), exist_ok=True)

        os.makedirs(self.get_build_dir(), exist_ok=True)
        os.makedirs(self.get_test_build_dir(), exist_ok=True)
        os.makedirs(self.get_targets_build_dir(), exist_ok=True)


    def get_workdir(self):
        """Path to directory for storing working files"""
        return self.workdir

    def get_build_dir(self):
        """Path to directory for storing build files"""
        return os.path.join(self.workdir, "build")
    
    def get_test_build_dir(self):
        """Path to directory for storing test build files"""
        return os.path.join(self.get_build_dir(), "tests")

    def get_tests_dir(self):
        """Path to directory for storing local copies of test files"""
        return os.path.join(self.workdir, "tests")
    
    def get_targets_build_dir(self):
        """Path to directory for storing build files for targets"""
        return os.path.join(self.get_build_dir(), "targets")

    def get_targets_dir(self):
        """Path to directory for storing local copies of target files"""
        return os.path.join(self.workdir, "targets")
    
    def get_manifests_dir(self):
        """Path to directory for storing work manifest files"""
        return os.path.join(self.workdir, "manifests")

    def get_results_dir(self):
        """Path to directory for storing results"""
        return os.path.join(self.workdir, "results")
    
    def get_temp_dir(self):
        """Path to directory for storing temporary files"""
        return os.path.join(self.workdir, "temp")
    
    def get_relative_path(self, path: str):
        """Get the relative path to a file or directory"""
        return os.path.relpath(path, self.workdir)


# Global storage manager
local_paths = LocalPathManager()

def rel_path(path: str):
    """Shrink a path to the minimum length required to identify it"""
    return local_paths.get_relative_path(path)

# class LocalFolder:
#     """Class representing a local folder path split into three parts: base, subpath, and name"""
#     def __init__(self, name: str, subpath: str, base: str=None):
#         self.subpath = subpath
#         self.name = name

#         if base is None:
#             self.base = local_paths.get_workdir()


#     def get_path(self):
#         """Get the full path to the folder"""
#         return os.path.join(self.base, self.subpath, self.name)
    
#     def __str__(self):
#         """Return the subpath and name as a string"""
#         return f"Subpath: {self.subpath}, Folder: {self.name}"
