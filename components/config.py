import os
import sys
import json
import zipfile
import shutil
import tarfile
import wget
from tqdm import tqdm


class Config:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config_data = self.__analysis()
        self.root = os.getcwd()
        self.resources = [['rtthread', self.__unzip],
                          ['toolchains', self.__bz2]]
        self.rtt_url_header = (
            'https://codeload.github.com/RT-Thread/rt-thread/zip/refs/')

    def __override_config_file(self):
        with open(self.config_file, "w") as file:
            file.write(json.dumps(self.config_data, indent=4))
            file.write('\n')

    def __analysis(self):
        with open(self.config_file, 'rb') as f:
            data = json.load(f)
            return data

    def __get_all_rtthread_versions(self):
        from github import Github
        repo = Github().get_repo("RT-Thread/rt-thread")
        tags = repo.get_tags()
        tags_name_list = []
        for tag in tags:
            tags_name_list.append(tag.name)
        return tags_name_list

    def __move(self, path):
        if len(os.listdir(path)) == 1:
            root = os.path.join(path, os.listdir(path)[0])
            for dir_path in os.listdir(root):
                shutil.move(os.path.join(root, dir_path), path)
            os.rmdir(root)

    def __unzip(self, zip_src, dst_dir):
        with zipfile.ZipFile(zip_src) as zf:
            for member in tqdm(zf.infolist(), desc=zip_src + ' Extracting '):
                try:
                    zf.extract(member, dst_dir)
                except zipfile.error:
                    pass
        self.__move(dst_dir)

    def __bz2(self, bz2_src, dst_dir):
        print('extract' + bz2_src)
        archive = tarfile.open(bz2_src)
        archive.debug = 0
        for tarinfo in archive:
            archive.extract(tarinfo, dst_dir)
        archive.close()
        self.__move(dst_dir)

    def __download(self, url, path, name=''):
        if not os.path.exists(path):
            os.makedirs(path)
        if not name:
            name = os.path.basename(url)
        fname = os.path.join(path, name)
        if os.path.isfile(fname):
            print(fname + " Already exists!!")
        else:
            print('wget download ' + fname)
            wget.download(url, fname)
        return fname

    def __get_resource(self, resource):
        for ver in self.config_data[resource[0]]:
            if 'url' in ver and not os.path.isdir(ver['path']):
                download_f = self.__download(ver['url'], 'download')
                resource[1](download_f, ver['path'])
                os.remove(download_f)

    def __get_env(self):
        env = self.config_data['env']
        env_resources = [['packages', 'packages/packages'],
                         ['env', 'tools/scripts']]
        if 'url' in env:
            for url in env['url']:
                for name in env_resources:
                    path = os.path.join(env['path'], name[1])
                    if name[0] in url and not os.path.isdir(path):
                        download_f = self.__download(url, 'download', name[0])
                        self.__unzip(download_f, path)
                        os.remove(download_f)
        with open(os.path.join(env['path'], 'packages/Kconfig'), 'w') as f:
            f.write('source "$PKGS_DIR/packages/Kconfig"')
        path = os.path.join(env['path'], 'local_pkgs')
        if not os.path.exists(path):
            os.makedirs(path)

    def __touch_env(self):
        rtt_list = self.config_data['rtthread']
        rtt_name = ''
        for rtt in rtt_list:
            if rtt['name'] == 'master':
                rtt_name = rtt['name']
                break
        if rtt_name == '' and len(rtt_list) > 0:
            rtt_name = rtt_list[0]['name']
        if rtt_name != '':
            sys.path.append(os.path.join(os.getcwd(), 'rtthread', rtt_name))
            from tools.env_utility import touch_env
            touch_env()

    def get_resources(self):
        for resource in self.resources:
            self.__get_resource(resource)
        self.__get_env()
        self.__touch_env()

    def config_pkgs(self, pkgs_str):
        lines = pkgs_str.split("\n")
        pkgs_list = []
        for line in lines:
            words = line.split(" ")
            for word in words:
                if word:
                    pkgs_list.append(word)
        print('config pkgs:')
        print(pkgs_list)
        self.config_data['pkgs'] = pkgs_list
        self.__override_config_file()

    def config_bsps(self, bsps_str):
        self.config_data['bsps'] = []
        for bsp_str in bsps_str.split():
            bsp = {}
            [bsp['name'], bsp['toolchain']] = bsp_str.split(":")
            self.config_data['bsps'].append(bsp)
        self.__override_config_file()

    def config_set_all_rtthread_versions(self):
        self.config_data['rtthread'] = []
        self.config_data['rtthread'].append({
            "name": "master",
            "path": "rtthread/master",
            "url": self.rtt_url_header + "heads/master"})
        versions = self.__get_all_rtthread_versions()
        for version in versions:
            self.config_data['rtthread'].append({
                "name": version,
                "path": "rtthread/" + version,
                "url": self.rtt_url_header + "tags/" + version})
        self.__override_config_file()

    def config_rtthread(self, rtthread_versions):
        # rtthread_versions is a string (separated by spaces).
        # branch "branch:master" tag "tag:v4.1.1"
        # e.g. "branch:master tag:v4.1.1 "
        if isinstance(rtthread_versions, str):
            versions = rtthread_versions.split()
        if isinstance(rtthread_versions, list):
            versions = rtthread_versions
        self.config_data['rtthread'] = []
        for version in versions:
            if 'branch:' in version:
                version = version.replace("branch:", "")
                self.config_data['rtthread'].append({
                    "name": version,
                    "path": "rtthread/" + version,
                    "url": self.rtt_url_header + "heads/" + version})
            elif 'tag:' in version:
                version = version.replace("tag:", "")
                self.config_data['rtthread'].append({
                    "name": version,
                    "path": "rtthread/" + version,
                    "url": self.rtt_url_header + "tags/" + version})
            else:
                self.config_data['rtthread'].append({
                    "name": version,
                    "path": "rtthread/" + version,
                    "url": self.rtt_url_header + "tags/" + version})
        self.__override_config_file()

    def get_path(self, name):
        if name in "env":
            path = self.config_data['env']['path']
        for resource in self.resources:
            for _list in self.config_data[resource[0]]:
                if _list['name'] == name:
                    path = os.path.join(_list['path'], 'bin')
        if os.path.isabs(path):
            return os.path.isabs(path)
        else:
            return os.path.join(self.root, path)

    def get_pkgs_name(self, pkg=[]):
        if pkg:
            return pkg
        elif not (self.config_data['pkgs'] is None or
                  self.config_data['pkgs'] is []):
            return list(self.config_data['pkgs'])
        return []

    def get_config_data(self):
        return self.config_data
