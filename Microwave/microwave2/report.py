from typing import Union 
import json
import os

# Basic report with a name, and a dictonary of key:str -> (result: Union[bool, int, float], comments: str)
class Report:
    def __init__(self, name: str):
        self.name = name
        self.results = {}
    
    def add_result(self, key: str, result: Union[bool, int, float], comments: str=""):
        self.results[key] = (result, comments)

    def add_subreport(self, subreport):
        self.results[subreport.name] = subreport.results

    def get_filename(self):
        return self.name + ".json"

    # Convert dict to json
    def get_json(self, indent=4):

        # Convert results to json
        json_results = json.dumps(self.results, indent=indent)

        return json_results

    # Write json to file
    def write_json(self, dir_path: str):
      
        full_path = os.path.join(dir_path, self.name + ".json")

        with open(full_path, 'w') as json_file:
            json_file.write(self.get_json())
        
        return full_path

