import argparse
import os
import json
import sys
import zipfile
import shutil
from tqdm import tqdm
import threading
import tarfile
import wget
from datetime import datetime
import re
import pytz
import requests
from dominate.tags import div, head, style, html, body, p, tr, th, table, td, a, h1, h2, h3


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
                dict = {'name': data['name'], 'enable': data['enable'],
                        'author': data['author'], 'repository': data['repository']}
                ver_dict = []
                for ver in data['site']:
                    if not os.access(os.path.join(path, 'Kconfig'), os.R_OK):
                        print(os.path.join(path, 'Kconfig') + "  No files!!")
                        break
                    f = open(os.path.join(path, 'Kconfig'))
                    text = f.read()
                    f.close()
                    pattern = re.compile('(?<=(config ))(((?!(config|default|bool)).)*?)(?=(\n)(((?!('
                                         'config|default|bool)).)*?)((default|bool)([^a-z]*?)(' + ver[
                                             'version'] + ')))', re.M | re.S)
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
                            if (not self.__nolatest) or ((self.__nolatest) and (not pkg_ver['version'] == 'latest')):
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
                if not repository_name in pkg['repository']:
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


class Config:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config_data = self.__analysis()
        self.root = os.getcwd()
        self.resources = [['rtthread', self.__unzip],
                          ['toolchains', self.__bz2]]

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
                except zipfile.error as e:
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
                resource[1](self.__download(
                    ver['url'], 'download'), ver['path'])

    def __get_env(self):
        env = self.config_data['env']
        env_resources = [['packages', 'packages/packages'],
                         ['env', 'tools/scripts']]
        if 'url' in env:
            for url in env['url']:
                for name in env_resources:
                    path = os.path.join(env['path'], name[1])
                    if name[0] in url and not os.path.isdir(path):
                        self.__unzip(self.__download(
                            url, 'download', name[0]), path)
        with open(os.path.join(env['path'], 'packages/Kconfig'), 'w') as f:
            f.write('source "$PKGS_DIR/packages/Kconfig"')
        path = os.path.join(env['path'], 'local_pkgs')
        if not os.path.exists(path):
            os.makedirs(path)

    def get_resources(self):
        for resource in self.resources:
            self.__get_resource(resource)
        self.__get_env()

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
            "url": "https://codeload.github.com/RT-Thread/rt-thread/zip/refs/heads/master"})
        versions = self.__get_all_rtthread_versions()
        for version in versions:
            self.config_data['rtthread'].append({
                "name": version,
                "path": "rtthread/" + version,
                "url": "https://codeload.github.com/RT-Thread/rt-thread/zip/refs/tags/" + version})
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
                    "url": "https://codeload.github.com/RT-Thread/rt-thread/zip/refs/heads/" + version})
            elif 'tag:' in version:
                version = version.replace("tag:", "")
                self.config_data['rtthread'].append({
                    "name": version,
                    "path": "rtthread/" + version,
                    "url": "https://codeload.github.com/RT-Thread/rt-thread/zip/refs/tags/" + version})
            else:
                self.config_data['rtthread'].append({
                    "name": version,
                    "path": "rtthread/" + version,
                    "url": "https://codeload.github.com/RT-Thread/rt-thread/zip/refs/tags/" + version})
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
        elif not (self.config_data['pkgs'] == None or self.config_data['pkgs'] == []):
            return list(self.config_data['pkgs'])
        return []

    def get_config_data(self):
        return self.config_data


class Logs:
    def __init__(self, logs_path, config_data, pkgs_index):
        self.logs_path = logs_path
        self.config_data = config_data
        self.pkgs_index = pkgs_index
        self.master_is_tab = False
        self.__clear_logs_path()
        self.pkgs_res_dict = {}
        self.append_res = False
        self.pages_url = 'http://rt-thread.github.io/packages/'

    def __clear_logs_path(self):
        if os.path.isdir(self.logs_path):
            shutil.rmtree(self.logs_path)
        os.makedirs(self.logs_path)

    def __build_res(self):
        def download_old_res():
            res_old_url = self.pages_url + 'pkgs_res.json'
            try:
                response = requests.get(res_old_url)
                res_old_dict = response.json()
                return res_old_dict
            except Exception as e:
                print(e)
            return {}

        def check_logfile(log_file):
            pattern = re.compile('Failure|Invalid|Success')
            if not (pattern.search(log_file) is None):
                res = pattern.search(log_file).group()
            else:
                res = 'Incomplete'
            return res

        def get_log_file(version, rtthread_name, bsp_name, pkg_name):
            log_file = os.path.join('log', rtthread_name,
                                    bsp_name, pkg_name + '-' + version)
            (log_path, log_filename) = os.path.split(log_file)
            if os.path.isdir(os.path.join(self.logs_path, log_path)):
                for filename in os.listdir(
                        os.path.join(self.logs_path, log_path)):
                    if log_filename in filename:
                        log_file = os.path.join(log_path, filename)
                        return log_file
            return ''

        def get_pkg_res(pkg, rtthread_name, bsp_name):
            pkg_res = {}
            pkg_res['pkg'] = pkg['name']
            pkg_res['repository'] = pkg['repository']
            pkg_res['versions'] = []
            for pkg_version in pkg['pkg']:
                res = {}
                res['version'] = pkg_version['version']
                res['log_file'] = get_log_file(
                    pkg_version['version'], rtthread_name, bsp_name, pkg['name'])
                res['res'] = check_logfile(res['log_file'])
                pkg_res['versions'].append(res)

            error_flag = False
            if len(pkg['pkg']) == 1 and pkg['pkg'][0]['version'] == 'latest':
                error_flag = True
            for res in pkg_res['versions']:
                if 'Failure' == res['res'] and 'latest' != res['version']:
                    error_flag = True
            if error_flag and (('master' == rtthread_name
                                and self.master_is_tab)
                               or 'master' != rtthread_name):
                pkg_res['error'] = True
            else:
                pkg_res['error'] = False
            return pkg_res

        if self.append_res:
            pkgs_res_dict = download_old_res()
        else:
            pkgs_res_dict = {}
        print(pkgs_res_dict)
        for rtthread in self.config_data['rtthread']:
            if 'pkgs_res' not in pkgs_res_dict:
                pkgs_res_dict['pkgs_res'] = {}
            for rtthread in self.config_data['rtthread']:
                if rtthread['name'] not in pkgs_res_dict['pkgs_res']:
                    pkgs_res_dict['pkgs_res'][rtthread['name']] = {}
                for bsp in self.config_data['bsps']:
                    if bsp['name'] not in pkgs_res_dict['pkgs_res'][rtthread['name']]:
                        pkgs_res_dict['pkgs_res'][rtthread['name']
                                                  ][bsp['name']] = {}
                    for pkg in self.pkgs_index:
                        pkgs_res_dict['pkgs_res'][rtthread['name']][bsp['name']][pkg['name']] = get_pkg_res(
                            pkg, rtthread['name'], bsp['name'])

        timezone = pytz.timezone('Asia/Shanghai')
        localized_time = timezone.localize(datetime.now())
        pkgs_res_dict['last_run_time'] = localized_time.strftime(
            '%Y-%m-%d %H:%M:%S %Z%z')

        return pkgs_res_dict

    def __html_report(self):
        style_applied = '''
            body{
                font-family: verdana,arial,sans-serif;
                font-size:11px;
            }
            table.gridtable {
                color: #333333;
                border-width: 1px;
                border-color: #666666;
                border-collapse: collapse;
                font-size:11px;
            }
            table.gridtable th {
                border-width: 1px;
                padding: 8px;
                border-style: solid;
                border-color: #666666;
                background-color: #DDEBF7;
            }
            table.gridtable td {
                border-width: 1px;
                padding: 8px;
                border-style: solid;
                border-color: #666666;
                background-color: #eeeeee;
                text-align:center;
            }
            table.gridtable td.failed {
                color: red;
            }
            table.gridtable td.successed {
                color: green;
            }
            table.gridtable td.warning {
                color: yellow;
            }
            table.gridtable th.error {
                background-color: red;
            }
            li {
                margin-top: 5px;
            }
            div{
                margin-top: 10px;
            }
        '''

        def generate_pkg_result_table(pkg):
            pkg_result_table = table(cls='gridtable')
            link_pkg = a(pkg['pkg'], href=pkg['repository'])
            if pkg['error']:
                pkg_result_table.add(th(link_pkg, colspan='2', cls='error'))
            else:
                pkg_result_table.add(th(link_pkg, colspan='2'))
            for version in pkg['versions']:
                pkg_version_tr = tr()
                pkg_version_tr += td(version['version'])
                if version['res'] == 'Success':
                    pkg_version_tr += td(a(version['res'],
                                         href=version['log_file']), cls='successed')
                elif version['res'] == 'Failure':
                    pkg_version_tr += td(a(version['res'],
                                         href=version['log_file']), cls='failed')
                else:
                    pkg_version_tr += td(a(version['res'],
                                         href=version['log_file']), cls='warning')
                pkg_result_table.add(pkg_version_tr)
            return pkg_result_table

        def get_success_pkg_num(pkgs):
            success_pkg_num = 0
            for pkg_name, pkg_res in pkgs.items():
                for version in pkg_res['versions']:
                    if version['version'] == 'latest' and version['res'] == 'Success':
                        success_pkg_num = success_pkg_num + 1
            return success_pkg_num

        def generate_result_table():
            result_div = div(id='pkgs_test_result')
            result_div.add(h1('Packages Test Result'))
            result_div.add(
                p('Last run at: ' + self.pkgs_res_dict['last_run_time']))
            for rtthread_name, rtthread_res in self.pkgs_res_dict['pkgs_res'].items():
                result_div = div(id='pkgs_test_result_' + rtthread_name)
                result_div.add(
                    h2('RT-Thread Version: ' + rtthread_name))
                for bsp_name, bsp_res in rtthread_res.items():
                    result_div.add(h3("bsp: {bsp}".format(bsp=bsp_name)))
                    pkgs_num = len(bsp_res)
                    success_num = get_success_pkg_num(bsp_res)
                    result_div.add(
                        p("{pkgs_num} packages in total, {success_num} packages pass the test. ({success_num}/{pkgs_num})".format(
                            pkgs_num=pkgs_num,
                            success_num=success_num)))
                    result_div.add(p("problem packages: "))
                    for pkg_name, pkg_res in bsp_res.items():
                        for version in pkg_res['versions']:
                            if version['version'] == 'latest' and version['res'] != 'Success':
                                result_div.add(
                                    p(a(pkg_name, href=pkg_res['repository'])))

                rtthread_result_table = table(cls='gridtable')
                for bsp_name, bsp_res in rtthread_res.items():
                    bsp_tr = tr()
                    bsp_tr += td(bsp_name)
                    for pkg_name, pkg_res in bsp_res.items():
                        bsp_tr += td(generate_pkg_result_table(pkg_res))
                    rtthread_result_table.add(bsp_tr)

        html_root = html()
        with html_root.add(head()):
            style(style_applied, type='text/css')
        with html_root.add(body()):
            generate_result_table()
        return html_root.render()

    def master_tab(self, tab=True):
        self.master_is_tab = tab

    def logs(self):
        self.pkgs_res_dict = self.__build_res()
        with open(os.path.join(self.logs_path, 'pkgs_res.json'), 'w') as f:
            json.dump(self.pkgs_res_dict, f)

        logs_html = self.__html_report()
        with open(os.path.join(self.logs_path, 'index.html'), 'w') as f:
            for log in logs_html:
                f.write(log)

    def path(self):
        return self.logs_path


class Build:
    def __init__(self, config, pkgs_index, logs, sem=16):
        self.sem_total = threading.Semaphore(sem)
        self.sem_stm32 = threading.Semaphore(1)
        self.config = config
        self.config_data = config.get_config_data()
        self.pkgs_index = pkgs_index
        self.logs = logs.logs
        self.logs_path = logs.path()
        self.root = os.getcwd()
        self.__debug = False

    def __build_pyconfig(self, bsp_path, pkg, pkg_ver, log_path):
        print(pkg)
        print('build', bsp_path, pkg['name'], pkg_ver['version'])
        f = open(os.path.join(bsp_path, '.config'), 'a')
        f.write('\nCONFIG_' + pkg['enable'] +
                '=y\nCONFIG_' + pkg_ver['enable'] + '=y\n')
        # f.write('CONFIG_PKG_USING_MBEDTLS_USE_ALL_CERTS=y\nCONFIG_PKG_USING_MBEDTLS_AMAZON_ROOT_CA\nCONFIG_PKG_USING_MBEDTLS_EXAMPLE=y')
        f.close()
        if not os.path.exists(os.path.dirname(log_path)):
            os.makedirs(os.path.dirname(log_path))
        os.environ['ENV_ROOT'] = self.config.get_path('env')
        command = '(cd ' + bsp_path + ' && scons --pyconfig-silent)'
        print(command)
        ret = os.system(command + ' > ' + log_path + ' 2>&1')
        if ret == 0:
            return 'Success'
        else:
            return 'Failure'

    def __build_pkgs_update(self, bsp_path, pkg, pkg_ver, log_path, flag):
        f = open(os.path.join(bsp_path, '.config'))
        text = f.read()
        f.close()
        if (re.compile(pkg['enable'] + '=').search(text) is None) or (re.compile(pkg_ver['enable'] + '=').search(text) is None):
            flag = 'Invalid'
        if flag == 'Success':
            command = '(cd ' + bsp_path + ' && python ' + os.path.join(
                self.config.get_path('env'), 'tools/scripts/env.py') + ' package --update)'
            print(command)
            ret = os.system(command + ' >> ' + log_path + ' 2>&1')
            if ret == 0:
                flag = 'Success'
            else:
                flag = 'Failure'
        pkg_path = ''
        if flag == 'Success':
            flag = 'Failure'
            for name in os.listdir(os.path.join(bsp_path, 'packages')):
                if name in bsp_path:
                    flag = 'Success'
                    pkg_path = name
                    break
        if pkg_path and 'VER_SHA' in pkg_ver and 'URL' in pkg_ver:
            path = os.path.join(bsp_path, 'packages', pkg_path)
            shutil.rmtree(path)
            clone_cmd = '(git clone ' + pkg_ver['URL'] + ' ' + path + ')'
            command = '(echo "' + clone_cmd + '" && ' + clone_cmd + ')'
            ret = os.system(command + ' >> ' + log_path + ' 2>&1')
            git_check_cmd = '(cd ' + path + \
                ' && git checkout ' + pkg_ver['VER_SHA'] + ')'
            command = '(echo "' + git_check_cmd + '" && ' + git_check_cmd + ')'
            ret = os.system(command + ' >> ' + log_path + ' 2>&1')
        return (flag, pkg_path)

    def __build_scons(self, bsp_path, tools, log_path, flag):
        if flag == 'Success':
            if 'stm32' in bsp_path:
                self.sem_stm32.acquire()
            os.environ['RTT_CC'] = 'gcc'
            os.environ['RTT_EXEC_PATH'] = tools
            command = 'scons -j16'
            print(bsp_path + ' ' + command)
            ret = os.system(command + ' -C ' + bsp_path +
                            ' >> ' + log_path + ' 2>&1')
            if 'stm32' in bsp_path:
                self.sem_stm32.release()
            if ret == 0:
                flag = 'Success'
            else:
                flag = 'Failure'
        return flag

    def __build_failure(self, pkg, bsp_path, tools, log_path):
        flag = 'Success'
        if not os.path.isdir(bsp_path):
            print(bsp_path, 'No path !!!')
            return
        if not os.path.isdir(os.path.dirname(log_path)):
            os.makedirs(os.path.dirname(log_path))
        pkg_log = os.path.basename(log_path)
        for name in os.listdir(os.path.dirname(log_path)):
            if pkg_log in name:
                os.remove(os.path.join(os.path.dirname(log_path), name))
                break
        if os.path.isdir(os.path.join(bsp_path, 'packages', pkg)):
            shutil.rmtree(os.path.join(bsp_path, 'packages', pkg))
        if os.path.isdir(os.path.join('local_pkgs', pkg)):
            shutil.copytree(os.path.join('local_pkgs', pkg),
                            os.path.join(bsp_path, 'packages', pkg))
        flag = self.__build_scons(bsp_path, tools, log_path, flag)
        os.rename(log_path, log_path + '-' + flag + '.txt')
        print('mv ' + log_path + ' ' + log_path + '-' + flag + '.txt')

    def __verify_pkg(self, name, bsp_path, tools, log_path):
        verify = []
        if os.path.isfile('verify.json'):
            with open('verify.json', 'rb') as f:
                verify = json.load(f)
        dict = {}
        dict.setdefault('name', name)
        dict.setdefault('bsp', bsp_path)
        dict.setdefault('tool', tools)
        dict.setdefault('log', log_path)
        verify.append(dict)
        file = open('verify.json', 'w')
        file.write(json.dumps(verify, indent=2, ensure_ascii=False))
        file.close()
        if not os.path.isdir('local_pkgs'):
            os.makedirs('local_pkgs')
        if not os.path.isdir(os.path.join('local_pkgs', name)):
            shutil.copytree(os.path.join(bsp_path, 'packages',
                            name), os.path.join('local_pkgs', name))

    def __build(self, bsp_path, pkg, pkg_ver, tools, log_path):
        flag = 'Success'
        logs = []
        if not os.path.isdir(bsp_path):
            print(bsp_path, 'No path !!!')
            return

        flag = self.__build_pyconfig(bsp_path, pkg, pkg_ver, log_path)
        (flag, pkg_path) = self.__build_pkgs_update(
            bsp_path, pkg, pkg_ver, log_path, flag)
        flag = self.__build_scons(bsp_path, tools, log_path, flag)
        os.rename(log_path, log_path + '-' + flag + '.txt')
        print('mv ' + log_path + ' ' + log_path + '-' + flag + '.txt')

        if not self.__debug:
            shutil.rmtree(bsp_path)
        elif pkg_path:
            self.__verify_pkg(pkg_path, bsp_path, tools, log_path)
        self.sem_total.release()

    def debug(self, value=True):
        self.__debug = value

    def all(self):
        count = 0
        threads = []
        data = self.config_data
        if os.path.isfile('verify.json'):
            os.remove('verify.json')
        for rtthread_ver in data['rtthread']:
            for bsp in data['bsps']:
                bsp_path = os.path.join(
                    rtthread_ver['path'], 'bsp', bsp['name'])
                if not os.path.isdir(bsp_path):
                    continue
                for pkg in self.pkgs_index:
                    for pkg_ver in pkg['pkg']:
                        bsp_path_new = bsp_path + '-' + \
                            pkg['name'] + '-' + pkg_ver['version']
                        log_path = os.path.join(
                            'artifacts_export/log', rtthread_ver['name'], bsp['name'], pkg['name'] + '-' + pkg_ver['version'])
                        if os.path.exists(bsp_path_new):
                            shutil.rmtree(bsp_path_new)
                        shutil.copytree(bsp_path, bsp_path_new)
                        t = threading.Thread(target=self.__build, args=(
                            bsp_path_new, pkg, pkg_ver, self.config.get_path(bsp['toolchain']), log_path))
                        threads.append(t)
                        self.sem_total.acquire()
                        t.start()
                        count += 1
                        if count >= 16:
                            count = 0
                            self.logs()
        for t in threads:
            t.join()
        self.logs()

    def build_failures(self, verify):
        if os.path.isfile(verify):
            data = []
            with open(verify, 'rb') as f:
                data = json.load(f)
            for err in data:
                self.__build_failure(
                    err['name'], err['bsp'], err['tool'], err['log'])
        logs.logs()

    def clean_bsps(self, verify):
        if os.path.isfile(verify):
            data = []
            with open(verify, 'rb') as f:
                data = json.load(f)
            for err in data:
                if os.path.isdir(err['bsp']):
                    shutil.rmtree(err['bsp'])
            os.remove(verify)


class Change:
    def __init__(self, packages_path, rtt_repo='https://github.com/RT-Thread/packages', rtt_branch='master'):
        self.root = os.getcwd()
        self.packages_path = packages_path
        self.rtt_repo = rtt_repo
        self.rtt_branch = rtt_branch

    def duplicate_removal(self, arr):
        return list(set(arr))

    def get_change_pkg_name(self):
        shell = 'cd ' + self.packages_path + ' && '
        try:
            os.system(shell + 'git remote add rtt_repo {}'.format(self.rtt_repo))
        except Exception as e:
            logging.error(e)
        try:
            os.system(shell + 'git fetch rtt_repo')
            os.system(
                shell + 'git merge rtt_repo/{} --allow-unrelated-histories'.format(self.rtt_branch))
            os.system(
                shell + 'git reset rtt_repo/{} --soft'.format(self.rtt_branch))
            os.system(shell + 'git status | tee git.txt')
            os.system(shell + 'git diff --staged | cat')
        except Exception as e:
            logging.error(e)
            return None
        try:
            with open(os.path.join(self.packages_path, 'git.txt'), 'r') as f:
                file_lines = f.read()
                pattern = re.compile(
                    '(?:modified:|new file:|->)(?:\s*?)(\S*?)(?:Kconfig|package.json)', re.I)
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


class Check:
    def __init__(self):
        pass

    def check_errors(self, res_json_path='pkgs_res.json'):
        pkgs_res = {}
        with open(res_json_path, 'rb') as f:
            pkgs_res = json.load(f)

        for rtthread_name, rtthread_res in pkgs_res['pkgs_res'].items():
            for bsp_name, bsp_res in rtthread_res.items():
                for pkg_name, pkg_res in bsp_res.items():
                    if pkg_res['error']:
                        return True
        return False


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('--version', '-v', action='version',
                        version='%(prog)s version : v0.0.1', help='show the version')
    parser.add_argument('--config', action='store',
                        help='Specify the configuration path',
                        default='config.json')
    parser.add_argument('--pkg', '-p', action='store',
                        help='Specify Package Name',
                        default=[])

    parser.add_argument('-j', action='store', type=int,
                        help='Allow N jobs at once, default 16',
                        default=16)

    parser.add_argument('--nolatest', action='store_true',
                        help='Whether to test nolatest, default False',
                        default=False)

    parser.add_argument('--debug', '-d', action='store_true',
                        help='Debug mode, which does not delete the generated compiled bsp!!',
                        default=False)

    parser.add_argument('--verify', action='store_true',
                        help='Test verify, If it is not used, it will not affect; if it is used, it will only test the wrong!!',
                        default=False)
    parser.add_argument('--repository', action='store',
                        help='Repository name to seek.',
                        default='')
    parser.add_argument('--append_res', action='store_true',
                        help='Append test tes to old res from githubpage.',
                        default=False)
    parser.add_argument('--pages_url', action='store',
                        help='Pkgs test res github pages url.',
                        default='')

    subparsers = parser.add_subparsers(dest='command')

    parser_check = subparsers.add_parser(name='check',
                                         help='Check the test res.')
    parser_check.add_argument('-f', '--file',
                              help='Input file pkgs_res.json path.',
                              default='artifacts_export/pkgs_res.json')

    parser_config = subparsers.add_parser(name='config',
                                          help='Config the config.json.')
    parser_config.add_argument('-f', '--file',
                               help='Input file config.json path.',
                               default='config.json')
    parser_config.add_argument('-r', '--rtthread',
                               help='config the RT-Thread version (separated by spaces).',
                               default='')
    parser_config.add_argument('-b', '--bsps',
                               help='config the bsps (separated by spaces).',
                               default='')
    parser_download = subparsers.add_parser(name='download',
                                            help='Download resources by config.json.')
    parser_download.add_argument('-f', '--file',
                                 help='Input file config.json path.',
                                 default='config.json')
    args = parser.parse_args()

    if args.command == 'check':
        check = Check()
        error_num = check.check_errors(args.file)
        if error_num > 0:
            print('pkgs test has {error_num} error.'.format(
                error_num=error_num))
            sys.exit(1)
        else:
            print('pkgs test has {error_num} error.'.format(
                error_num=error_num))
            sys.exit(0)
    elif args.command == 'config':
        config = Config(args.file)
        if args.rtthread:
            config.config_rtthread(args.rtthread)
        if args.bsps:
            config.config_bsps(args.bsps)
    elif args.command == 'download':
        config = Config(args.file)
        config.get_resources()
    else:
        time_old = datetime.now()

        config = Config(args.config)
        pkgs_name = config.get_pkgs_name(args.pkg)
        if not pkgs_name:
            print("pkgs field is None!")
            exit(0)
        print(pkgs_name)
        config.get_resources()

        packages_index = PackagesIndex(os.path.join(
            config.get_path('env'), 'packages/packages'))
        packages_index.nolatest(args.nolatest)

        if args.repository:
            pkgs_config_dict = packages_index.repository_seek(args.repository)
        else:
            pkgs_config_dict = packages_index.name_seek(pkgs_name)

        print(pkgs_config_dict)

        logs = Logs('artifacts_export',
                    config.get_config_data(), pkgs_config_dict)
        if args.append_res:
            if args.pages_url:
                logs.pages_url = args.pages_url
            logs.append_res = True

        build = Build(config, pkgs_config_dict, logs, args.j)

        build.debug(args.debug)
        if args.verify:
            build.build_failures('verify.json')
        else:
            build.clean_bsps('verify.json')
            build.all()

        time_new = datetime.now()
        print(time_new-time_old)
        print('Please via browser open ' + os.path.join(os.getcwd(),
                                                        'artifacts_export/index.html') + ' view results!!')
