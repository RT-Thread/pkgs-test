import os
import re
import json
import logging


class Change:
    def __init__(self, packages_path,
                 packages_repo='https://github.com/RT-Thread/packages',
                 packages_branch='master'):
        self.root = os.getcwd()
        self.packages_path = packages_path
        self.packages_repo = packages_repo
        self.packages_branch = packages_branch

    def duplicate_removal(self, arr):
        return list(set(arr))

    def get_change_pkg_name(self):
        shell = 'cd ' + self.packages_path + ' && '
        try:
            os.system(shell +
                      'git remote add packages_repo {}'.format(
                          self.packages_repo))
        except Exception as e:
            logging.error(e)
        try:
            branch = 'packages_repo/{}'.format(self.packages_branch)
            os.system(shell + 'git fetch packages_repo')
            os.system(shell + 'git merge {} '.format(branch) +
                      '--allow-unrelated-histories')
            os.system(shell + 'git reset {} '.format(branch) +
                      '--soft')
            os.system(shell + 'git status | tee git.txt')
            os.system(shell + 'git diff --staged | cat')
        except Exception as e:
            logging.error(e)
            return None
        try:
            with open(os.path.join(self.packages_path, 'git.txt'), 'r') as f:
                file_lines = f.read()
                pattern = re.compile(
                    '(?:modified:|new file:|->)' +
                    '(?:\\s*?)(\\S*?)(?:Kconfig|package.json)', re.I)
                print(pattern.findall(file_lines))
                pkgs = list()
                for path in pattern.findall(file_lines):
                    package_path = os.path.join(
                        self.packages_path, path, 'package.json')
                    if os.access(package_path, os.R_OK):
                        with open(package_path, 'rb') as f:
                            data = json.load(f)
                            if 'name' in data:
                                pkgs.append(data['name'])
                return self.duplicate_removal(pkgs)
        except Exception as e:
            logging.error(e)
            return None
