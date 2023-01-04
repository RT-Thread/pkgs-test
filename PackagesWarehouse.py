import os
import re
import sys
import logging
import json

class PackagesWarehouse:
    def __init__(self, packages_path, rtt_repo, rtt_branch):
        self.root = os.getcwd()
        self.packages_path = packages_path
        self.rtt_repo = rtt_repo
        self.rtt_branch = rtt_branch
    
    def duplicate_removal(self, arr):
        return list(set(arr))

    def get_change_pkg_name(self):
        shell = 'cd '+ self.packages_path + ' && '
        try:
            os.system(shell + 'git remote add rtt_repo {}'.format(self.rtt_repo))
        except Exception as e:
            logging.error(e)
        try:
            os.system(shell + 'git fetch rtt_repo')
            os.system(shell + 'git merge rtt_repo/{}'.format(self.rtt_branch))
            os.system(shell + 'git reset rtt_repo/{} --soft'.format(self.rtt_branch))
            os.system(shell + 'git status > git.txt')
        except Exception as e:
            logging.error(e)
            return None
        try:
            with open(os.path.join(self.packages_path, 'git.txt'), 'r') as f:
                file_lines = f.read()
                pattern = re.compile('(?:modified:|new file:|->)(?:\s*?)(\S*?)(?:Kconfig|package.json)', re.I)
                print(pattern.findall(file_lines))
                pkgs = list()
                for path in pattern.findall(file_lines):
                    package_path = os.path.join(self.packages_path, path, 'package.json')
                    if os.access(package_path, os.R_OK):
                        with open(package_path, 'rb') as f:
                            data = json.load(f)
                            if 'name' in data:
                                pkgs.append(data['name'])
                return self.duplicate_removal(pkgs)
        except Exception as e:
            logging.error(e)
            return None
    
    def write_config(self, pkgs, config, config_new):        
        with open(config, 'rb') as f:
            data = json.load(f)
        data.setdefault('pkgs', pkgs)
        data['pkgs'] = pkgs
        print(pkgs)
        print(data)
        file = open(config_new,'w')
        file.write(json.dumps(data, indent=2, ensure_ascii=False))
        file.close()
    
if __name__ == '__main__':
    checkout=PackagesWarehouse("~/.env/packages/packages","https://github.com/RT-Thread/packages", "master");
    checkout.write_config(checkout.get_change_pkg_name(),"config.json","git_config.json");