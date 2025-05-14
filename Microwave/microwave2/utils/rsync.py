import subprocess
import shlex

from microwave2.utils.utils import run_command_better
from microwave2.results.result import ProcResult
from microwave2.utils.log import log, warn, error, debug, info

class RsyncCommand:
    def __init__(
        self,
        source,
        destination,
        delete=False,
        archive=True,
        verbose=False,
        copy_links=False,
        force_copy_contents=False):
        self.source = source
        self.destination = destination
        self.delete = delete
        self.archive = archive
        self.verbose = verbose
        self.copy_links = copy_links

        # If force_copy_contents is set, we want to copy the contents of the source, so we need to append a trailing slash
        # if it doesn't already exist 
        if force_copy_contents:
            if not self.source.endswith("/"):
                self.source += "/"

    # TODO switch to run_command_better
    def sync_better(self, sudo=False) -> ProcResult:
        cmd = ["rsync"]
        if sudo:
            cmd.insert(0, "sudo")
        if self.archive:
            cmd.append("-a")
        if self.verbose:
            cmd.append("-v")
        if self.delete:
            cmd.append("--delete")
        if self.copy_links:
            cmd.append("--copy-links")
        cmd.extend([self.source, self.destination])
        info("[Command]", shlex.join(cmd))
        
        return run_command_better(cmd)
    
    def sync(self, sudo=False):
        cmd = ["rsync"]
        if sudo:
            cmd.insert(0, "sudo")
        if self.archive:
            cmd.append("-a")
        if self.verbose:
            cmd.append("-v")
        if self.delete:
            cmd.append("--delete")
        if self.copy_links:
            cmd.append("--copy-links")
        cmd.extend([self.source, self.destination])
        info("[Command]", shlex.join(cmd))
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError as e:
            error(f"Error syncing: {e}")
            return False
        return True