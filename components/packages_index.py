import os
import re
import json

from .change import Change
from .config import Config


class PackagesIndex:
    def __init__(self, packages_path):
        self.packages_path = packages_path
        self.__nolatest = False
        self.dict = self.__create_dict()
        self.config_pkgs = 'hello'

    def __create_dict(self):
        dicts = []
        json_path = []
        for path, dir_list, file_list in os.walk(self.packages_path):
            for file_name in file_list:
                if file_name == "package.json":
                    json_path.append(path)
        for path in json_path:
            with open(os.path.join(path, 'package.json'), 'rb') as f:
                data = json.load(f)
            if 'name' in data and 'enable' in data and 'site' in data:
                dict = {'name': data['name'],
                        'enable': data['enable'],
                        'author': data['author'],
                        'repository': data['repository']}
                ver_dict = []
                for ver in data['site']:
                    if not os.access(os.path.join(path, 'Kconfig'), os.R_OK):
                        print(os.path.join(path, 'Kconfig') + "  No files!!")
                        break
                    f = open(os.path.join(path, 'Kconfig'))
                    text = f.read()
                    f.close()
                    version = ver['version']
                    pattern_str = ('(?<=(config ))' +
                                   '(((?!(config|default|bool)).)*?)' +
                                   '(?=(\n)(((?!(config|default|bool)).)*?)' +
                                   f'((default|bool)([^a-z]*?)({version})))')
                    pattern = re.compile(pattern_str, re.M | re.S)
                    if not (pattern.search(text) is None) and 'version' in ver:
                        site = {'version': ver['version'],
                                'enable': pattern.search(text).group()}
                        if ver['URL'][-4:] == '.git':
                            site.setdefault('URL', ver['URL'])
                            site.setdefault('VER_SHA', ver['VER_SHA'])
                        ver_dict.append(site)
                dict.setdefault('pkg', ver_dict)
                dicts.append(dict)
        return dicts

    def __get_config_pkgs(self, pkgs):
        pkgs_list = []
        if type(pkgs) is str:
            pkgs_list.append(pkgs)
        else:
            pkgs_list = list(pkgs)
        pkgs_return = []
        for data in self.dict:
            for pkg in pkgs_list:
                pattern = re.compile('(.*)(?=:)')
                pkg_copy = pkg
                if (':' in pkg and not (pattern.search(pkg) is None)):
                    pkg_copy = pattern.search(pkg).group()
                if 'name' in data and data['name'] == pkg_copy:
                    part = data.copy()
                    pkg_vers = []
                    if ':' in pkg:
                        for pkg_ver in part['pkg']:
                            if pkg_ver['version'] in pkg:
                                pkg_vers.append(pkg_ver)
                    else:
                        for pkg_ver in part['pkg']:
                            if (not self.__nolatest) or \
                                    ((self.__nolatest) and
                                     (not pkg_ver['version'] == 'latest')):
                                pkg_vers.append(pkg_ver)
                    if pkg_vers:
                        part['pkg'] = pkg_vers
                        pkgs_return.append(part)
                    pkgs_list.remove(pkg)
                    if not pkgs_list:
                        return pkgs_return
        return pkgs_return

    def repository_seek(self, repository):
        pkgs = []
        repository_name = repository.split("/")[1]
        if repository_name == 'packages':
            change = Change(os.path.join(
                Config().get_path('env'), "packages/packages"))
            return self.name_seek(change.get_change_pkg_name())
        for pkg in self.dict:
            if repository_name.lower() in pkg['repository'].lower():
                pkgs.append(pkg)
        if len(pkgs) > 1:
            pkgs_copy = list(pkgs)
            for pkg in pkgs_copy:
                if repository_name not in pkg['repository']:
                    pkgs_copy.remove(pkg)
            if pkgs_copy:
                pkgs = pkgs_copy

        if not pkgs:
            print('You may have changed the warehouse name while forking!!!')
            return []

        for pkg in pkgs[0]['pkg']:
            if 'URL' in pkg:
                pkg['URL'] = 'https://github.com/' + repository + '.git'

        return pkgs

    def name_seek(self, pkgs='all'):
        if pkgs == 'all':
            config_dict = self.dict
        else:
            config_dict = self.__get_config_pkgs(pkgs)
        print(config_dict)
        return config_dict

    def nolatest(self, value=True):
        self.__nolatest = value
