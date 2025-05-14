import os 
import subprocess
#!/usr/bin/env python3
import re
import sys

# class BuildError(Exception):
#     """Represents an error trying to build the Linux kernel."""
#     def __init__(self, message, stdout=None, stderr=None):
#         super().__init__(message)
#         self.stdout = stdout
#         self.stderr = stderr

# This regex looks for the literal word "echo" followed by whitespace,
# then a single quote, then captures everything until the next single quote.
pattern = re.compile(r"echo\s+'([^']+)'")

def process_file(filename):
    with open(filename, 'r') as f:
        for line in f:
            match = pattern.search(line)
            if match:
                # Extract the contents inside the single quotes
                content = match.group(1)
                # Split the content on any whitespace
                tokens = content.split()
                # Print out the tokens
                print(tokens)

def parse_outfile(outfile):
    # Open the file in read mode
    with open(outfile, 'r') as f:
        for line in f:
            # Search for the pattern in the line
            match = pattern.search(line)
            if match:
                # Extract the contents inside the single quotes
                content = match.group(1)
                # Split the content on any whitespace
                tokens = content.split()
                # Print out the tokens
                print(tokens)
                # Print first 100 characters of the line
                print(line[:100])