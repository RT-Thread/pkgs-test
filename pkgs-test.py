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
from HTMLTable import HTMLTable
import html

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
                    dict = {'name': data['name'], 'enable': data['enable'], 'author': data['author'], 'repository': data['repository']}
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
                            ver_dict.append({'version': ver['version'], 'enable': pattern.search(text).group()})
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
        repository_name = os.path.basename(repository)
        for pkg in self.dict:
            if repository_name.lower() in pkg['repository'].lower():
                pkgs.append(pkg)
        if not pkgs:
            print('You may have changed the warehouse name while forking!!!')
        elif len(pkgs) > 1:
            pkgs_copy = list(pkgs)
            for pkg in pkgs_copy:
                if not repository_name in pkg['repository']:
                    pkgs_copy.remove(pkg)
            if pkgs_copy:
                pkgs = pkgs_copy
        return pkgs

    def name_seek(self, pkgs='all'):
        if pkgs == 'all':
            config_dict = self.dict
        else:
            config_dict = self.__get_config_pkgs(pkgs)
        return config_dict

    def nolatest(self, value=True):
        self.__nolatest = value


class Config:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config_data = self.__analysis()
        self.root = os.getcwd()
        self.resources = [['rtthread',self.__unzip],['toolchains',self.__bz2]]

    def __analysis(self):
        with open(self.config_file, 'rb') as f:
            data = json.load(f)
            return data;

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
        archive = tarfile.open(bz2_src)
        archive.debug = 1
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
                resource[1](self.__download(ver['url'], 'download'), ver['path'])

    def __get_env(self):
        env = self.config_data['env']
        env_resources = [['packages','packages/packages'],['env','tools/scripts']]
        if 'url' in env and not os.path.isdir(env['path']):
            for url in env['url']:
                for name in env_resources:
                    if name[0] in url:
                        path = os.path.join(env['path'],name[1])
                        self.__unzip(self.__download(url, 'download', name[0]), path)
        with open(os.path.join(env['path'], 'packages/Kconfig'), 'w') as f:
            f.write('source "$PKGS_DIR/packages/Kconfig"')
        path = os.path.join(env['path'], 'local_pkgs')
        if not os.path.exists(path):
            os.makedirs(path)
    
    def get_resources(self):
        for resource in self.resources:
            self.__get_resource(resource)
        self.__get_env()
    
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

    def __clear_logs_path(self):
        if os.path.isdir(self.logs_path):
            shutil.rmtree(self.logs_path)
        os.makedirs(self.logs_path)

    def __single_pkg_table(self, versions, rtthread_name, bsp_name, pkg_name):
        pkg_table = HTMLTable()
        pkg_rows = list()
        error_flag = ''
        for version in versions:
            link = ''
            log_file = os.path.join('log', rtthread_name, bsp_name, pkg_name + '-' + version['version'])
            (log_path, log_filename) = os.path.split(log_file)
            if os.path.isdir(os.path.join(self.logs_path,log_path)):
                for filename in os.listdir(os.path.join(self.logs_path,log_path)):
                    if log_filename in filename:
                        log_file = os.path.join(log_path,filename)
                pattern = re.compile('Failure|Invalid|Success')
                if not os.path.isfile(os.path.join(self.logs_path,log_file)):
                    link = ''
                elif not (pattern.search(log_file) is None):
                    link = '<a href="' + log_file + '">' + pattern.search(log_file).group() + '</a>'
                else:
                    link = '<a href="' + log_file + '">Incomplete</a>'
            pkg_rows.append([version['version'],link])
            if (('latest' in version['version']) and len(versions)==1) or \
            (('Failure' in log_file) and (not 'latest' in version['version'])):
                error_flag = 'error'
        pkg_table.append_data_rows((pkg_rows))
        if error_flag == 'error':
            if ('master' in rtthread_name and self.master_is_tab) or (not 'master' in rtthread_name):
                pkg_table.set_style({'background-color': '#f00',})
        return html.unescape(pkg_table.to_html())

    def __table(self):
        logs = []
        data = self.config_data
        pkgs_rows = ['']
        for pkg in self.pkgs_index:
            pkgs_rows.append(pkg['name'])
        for rtthread in data['rtthread']:
            table = HTMLTable(caption=rtthread['name'])
            table.append_header_rows((pkgs_rows,))
            for bsp in data['bsps']:
                data_rows = list()
                for pkg in self.pkgs_index:
                    data_rows.append(self.__single_pkg_table(pkg['pkg'], rtthread['name'], bsp['name'],pkg['name']))
                data_rows.insert(0,bsp['name'])
                table.append_data_rows((data_rows,))
            logs.append(html.unescape(table.to_html()))
        return logs

    def master_tab(self, tab=True):
        self.master_is_tab = tab

    def logs(self):
        logs_html = self.__table()
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

    def __build_pyconfig(self, bsp_path, pkg_name, pkg_ver, log_path):
        print('build', bsp_path, pkg_name, pkg_ver)
        f = open(os.path.join(bsp_path, '.config'),'a')
        f.write('\nCONFIG_' + pkg_name + '=y\nCONFIG_' + pkg_ver + '=y\n')
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

    def __build_pkgs_update(self, bsp_path, pkg_name, pkg_ver, log_path, flag):
        f = open(os.path.join(bsp_path, '.config'))
        text = f.read()
        f.close()
        if (re.compile(pkg_name + '=').search(text) is None) or (re.compile(pkg_ver + '=').search(text) is None):
            flag = 'Invalid'
        if flag == 'Success':
            command = '(cd ' + bsp_path + ' && python ' + os.path.join(self.config.get_path('env'), 'tools/scripts/env.py') + ' package --update)'
            print(command)
            ret = os.system(command + ' >> ' + log_path + ' 2>&1')
            if ret == 0:
                flag = 'Success'
            else:
                flag = 'Failure'
        pkg_path = ''
        if flag == 'Success':
            flag = 'Failure'
            for name in os.listdir(os.path.join(bsp_path,'packages')):
                if name in bsp_path:
                    flag = 'Success'
                    pkg_path = name
                    break
        return (flag, pkg_path)

    def __build_scons(self, bsp_path, tools, log_path, flag):
        if flag == 'Success':
            if 'stm32' in bsp_path:
                self.sem_stm32.acquire()
            os.environ['RTT_CC'] = 'gcc'
            os.environ['RTT_EXEC_PATH'] = tools
            command = 'scons -j16'
            print(bsp_path + ' ' + command)
            ret = os.system(command + ' -C ' + bsp_path + ' >> ' + log_path + ' 2>&1')
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
        if os.path.isdir(os.path.join(bsp_path,'packages',pkg)):
            shutil.rmtree(os.path.join(bsp_path,'packages',pkg))
        if os.path.isdir(os.path.join('local_pkgs',pkg)):
            shutil.copytree(os.path.join('local_pkgs',pkg), os.path.join(bsp_path,'packages',pkg))
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
        file = open('verify.json','w')
        file.write(json.dumps(verify, indent=2, ensure_ascii=False))
        file.close()
        if not os.path.isdir('local_pkgs'):
            os.makedirs('local_pkgs')
        if not os.path.isdir(os.path.join('local_pkgs',name)):
            shutil.copytree(os.path.join(bsp_path,'packages',name), os.path.join('local_pkgs',name))

    def __build(self, bsp_path, pkg_name, pkg_ver, tools, log_path):
        flag = 'Success'
        logs = []
        if not os.path.isdir(bsp_path):
            print(bsp_path, 'No path !!!')
            return

        flag = self.__build_pyconfig(bsp_path, pkg_name, pkg_ver, log_path)
        (flag, pkg_path) = self.__build_pkgs_update(bsp_path, pkg_name, pkg_ver, log_path, flag)
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
                bsp_path = os.path.join(rtthread_ver['path'], 'bsp', bsp['name'])
                if not os.path.isdir(bsp_path):
                    continue
                for pkg in self.pkgs_index:
                    for pkg_ver in pkg['pkg']:
                        bsp_path_new = bsp_path + '-' + pkg['name'] + '-' + pkg_ver['version']
                        log_path = os.path.join('artifacts_export/log', rtthread_ver['name'], bsp['name'], pkg['name'] + '-' + pkg_ver['version'])
                        if os.path.exists(bsp_path_new):
                            shutil.rmtree(bsp_path_new)
                        shutil.copytree(bsp_path, bsp_path_new)
                        t = threading.Thread(target=self.__build, args=(bsp_path_new, pkg['enable'], pkg_ver['enable'], self.config.get_path(bsp['toolchain']),log_path))
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
                self.__build_failure(err['name'], err['bsp'], err['tool'], err['log'])
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
                        
    parser.add_argument('-j', action='store',type=int,
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

    args = parser.parse_args()

    time_old=datetime.now() 

    config = Config(args.config)
    pkgs_name = config.get_pkgs_name(args.pkg)
    if not pkgs_name:
        print("pkgs field is None!")
        exit(0)
    print(pkgs_name)
    config.get_resources()

    packages_index = PackagesIndex(os.path.join(config.get_path('env'),'packages/packages'))
    packages_index.nolatest(args.nolatest)
    pkgs_config_dict = packages_index.name_seek(pkgs_name)
    print(pkgs_config_dict)

    logs = Logs('artifacts_export', config.get_config_data(), pkgs_config_dict)
    build = Build(config, pkgs_config_dict, logs, args.j)

    build.debug(args.debug)
    if args.verify:
        build.build_failures('verify.json')
    else:
        build.clean_bsps('verify.json')
        build.all()

    time_new=datetime.now() 
    print(time_new-time_old)
    print('Please via browser open ' + os.path.join(os.getcwd(),'artifacts_export/index.html') + ' view results!!')
