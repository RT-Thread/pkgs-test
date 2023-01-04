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
import fcntl

# pip install scons requests tqdm wget html-table
def create_pkgs_dict(pkgs_path):
    dicts = []
    json_path = []
    for path, dir_list, file_list in os.walk(pkgs_path):
        for file_name in file_list:
            if file_name == "package.json":
                json_path.append(path)
    for path in json_path:
        with open(os.path.join(path, 'package.json'), 'rb') as f:
            data = json.load(f)
            if 'name' in data and 'enable' in data and 'site' in data:
                dict = {'name': data['name'], 'enable': data['enable']}
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


def download(url, path):
    if not os.path.exists(path):
        os.makedirs(path)
    fname = os.path.join(path, os.path.basename(url))
    if os.path.isfile(fname):
        print(fname + " Already exists!!")
    else:
        print('wget download ' + fname)
        wget.download(url, fname)
    return fname


def unzip_file(zip_src, dst_dir):
    with zipfile.ZipFile(zip_src) as zf:
        for member in tqdm(zf.infolist(), desc=zip_src + ' Extracting '):
            try:
                zf.extract(member, dst_dir)
            except zipfile.error as e:
                pass
    if len(os.listdir(dst_dir)) == 1:
        root = os.path.join(dst_dir, os.listdir(dst_dir)[0])
        for dir_path in os.listdir(root):
            shutil.move(os.path.join(root, dir_path), dst_dir)
        os.rmdir(root)


def bz2_file(bz2_src, dst_dir):
    archive = tarfile.open(bz2_src)
    archive.debug = 1
    for tarinfo in archive:
        archive.extract(tarinfo, dst_dir)
    archive.close()
    if len(os.listdir(dst_dir)) == 1:
        root = os.path.join(dst_dir, os.listdir(dst_dir)[0])
        for dir_path in os.listdir(root):
            shutil.move(os.path.join(root, dir_path), dst_dir)
        os.rmdir(root)


def get_rtthread(config):
    for ver in config:
        if 'url' in ver and not os.path.isdir(ver['path']):
            unzip_file(download(ver['url'], 'download'), ver['path'])


def get_toolchains(config):
    for toolchain in config:
        if 'url' in toolchain and not os.path.isdir(toolchain['path']):
            bz2_file(download(toolchain['url'], 'download'), toolchain['path'])


def get_toolchain_path(toolchain_name, toolchains):
    for toolchain in toolchains:
        if toolchain['name'] == toolchain_name:
            return os.path.join(toolchain['path'], 'bin')

def get_env(rtt_path):
    os.chdir(rtt_path)
    os.system('python3 -c "import tools.menuconfig; tools.menuconfig.touch_env()"')
    os.chdir(root_path)

def get_resources(config):
    data = config
    if 'rtthread' in data:
        get_rtthread(data['rtthread'])
    if 'toolchains' in data:
        get_toolchains(data['toolchains'])
    get_env(data['rtthread'][0]['path'])


def get_pkgs(dict, pkgs):
    nolatest = args.nolatest
    pkgs_list = []
    if type(pkgs) is str:
        pkgs_list.append(pkgs)
    else:
        pkgs_list = list(pkgs)
    pkgs_return = []
    for data in dict:
        for pkg in pkgs_list:
            pattern = re.compile('(.*)(?=:)')
            pkg_copy = pkg
            if (':' in pkg and not (pattern.search(pkg) is None)):
                pkg_copy = pattern.search(pkg).group()
            if 'name' in data and (data['name'] == pkg_copy or pkg_copy == 'all'):
                part = data.copy()
                pkg_vers = []
                if ':' in pkg:
                    for pkg_ver in part['pkg']:
                        if pkg_ver['version'] in pkg:
                            pkg_vers.append(pkg_ver)
                else:
                    for pkg_ver in part['pkg']:
                        if (not nolatest) or ((nolatest) and (not pkg_ver['version'] == 'latest')):
                            pkg_vers.append(pkg_ver)
                if pkg_vers:
                    part['pkg'] = pkg_vers
                    pkgs_return.append(part)
                if not pkg_copy == 'all':
                    pkgs_list.remove(pkg)
                if not pkgs_list:
                    return pkgs_return
    return pkgs_return


def logs():
    logs_html = table(config_json, pkgs_config_dict)
    with open('artifacts_export/index.html', 'w') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        for log in logs_html:
            f.write(log)

def build(bsp_path, pkg_name, pkg_ver, tools, log_path):
    # 0 Initial 1 Success 2 Failure 3 Invalid
    flag = 'Success'
    logs = []
    if not os.path.isdir(bsp_path):
        print(bsp_path, 'No path !!!')
        return
    print('build', bsp_path, pkg_name, pkg_ver, tools)
    cwd = os.getcwd()
    f = open(os.path.join(bsp_path, '.config'),'a')
    f.write('\nCONFIG_' + pkg_name + '=y\nCONFIG_' + pkg_ver + '=y\n')
    f.close()
    
    if not os.path.exists(os.path.dirname(log_path)):
        os.makedirs(os.path.dirname(log_path))

    command = '(cd ' + bsp_path + ' && scons --pyconfig-silent)'
    print(command)
    ret = os.system(command + ' > ' + log_path + ' 2>&1')
    if ret == 0:
        flag = 'Success'
    else:
        flag = 'Failure'

    f = open(os.path.join(bsp_path, '.config'))
    text = f.read()
    f.close()
    if (re.compile(pkg_name + '=').search(text) is None) or (re.compile(pkg_ver + '=').search(text) is None):
        flag = 'Invalid'
    if flag == 'Success':
        command = '(cd ' + bsp_path + ' && ~/.env/tools/scripts/pkgs --update)'
        print(command)
        ret = os.system(command + ' >> ' + log_path + ' 2>&1')
        if ret == 0:
            flag = 'Success'
        else:
            flag = 'Failure'

    if flag == 'Success':
        os.environ['RTT_CC'] = 'gcc'
        os.environ['RTT_EXEC_PATH'] = os.path.join(cwd, tools)
        command = 'scons -j16'
        print(bsp_path + ' ' + command)

        ret = os.system(command + ' -C ' + bsp_path + ' >> ' + log_path + ' 2>&1')
        if ret == 0:
            flag = 'Success'
        else:
            flag = 'Failure'
    
    file = open(log_path,'a+')
    file.write('\n\n')
    for log in logs:
        file.write(log + '\n')
    file.close()
    os.rename(log_path, log_path + '-' + flag + '.txt')
    print('mv ' + log_path + ' ' + log_path + '-' + flag + '.txt')
    shutil.rmtree(bsp_path)
    sem.release()

def build_all(config, pkgs):
    count = 0
    threads = []
    data = config
    if os.path.exists('artifacts_export/log'):
        shutil.rmtree('artifacts_export/log')
    for rtthread_ver in data['rtthread']:
        for bsp in data['bsps']:
            bsp_path = os.path.join(rtthread_ver['path'], 'bsp', bsp['name'])
            if not os.path.isdir(bsp_path):
                continue
            for pkg in pkgs:
                for pkg_ver in pkg['pkg']:
                    bsp_path_new = bsp_path + '-' + pkg['name'] + '-' + pkg_ver['version']
                    log_path = os.path.join('artifacts_export/log', rtthread_ver['name'], bsp['name'], pkg['name'] + '-' + pkg_ver['version'])
                    if os.path.exists(bsp_path_new):
                        shutil.rmtree(bsp_path_new)
                    shutil.copytree(bsp_path, bsp_path_new)
                    t = threading.Thread(target=build, args=(bsp_path_new, pkg['enable'], pkg_ver['enable'], get_toolchain_path(bsp['toolchain'], data['toolchains']),log_path))
                    threads.append(t)
                    sem.acquire()
                    t.start()
                    count += 1
                    if count >= 16:
                        count = 0
                        logs()
    for t in threads:
        t.join()
    logs()


def get_config(config):
    with open(config, 'rb') as f:
        data = json.load(f)
        return data;

def table(config, pkgs):
    logs = []
    data = config
    pkgs_rows = ['']
    for pkg in pkgs:
        pkgs_rows.append(pkg['name'])
    for rtthread_ver in data['rtthread']:
        table = HTMLTable(caption=rtthread_ver['name'])
        table.append_header_rows((pkgs_rows,))
        for bsp in data['bsps']:
            data_rows = list()
            for pkg in pkgs:
                pkg_table = HTMLTable()
                pkg_rows = list()
                for pkg_ver in pkg['pkg']:
                    link = ''
                    log_file = os.path.join('log', rtthread_ver['name'], bsp['name'], pkg['name'] + '-' + pkg_ver['version'])
                    (log_path, log_filename) = os.path.split(log_file)
                    if os.path.isdir(os.path.join('artifacts_export',log_path)):
                        for filename in os.listdir(os.path.join('artifacts_export',log_path)):
                            if log_filename in filename:
                                log_file = os.path.join(log_path,filename)
                        pattern = re.compile('Failure|Invalid|Success')
                        if not os.path.isfile(os.path.join('artifacts_export',log_file)):
                            link = ''
                        elif not (pattern.search(log_file) is None):
                            link = '<a href="' + log_file + '">' + pattern.search(log_file).group() + '</a>'
                        else:
                            link = '<a href="' + log_file + '">Incomplete</a>'
                    pkg_rows.append([pkg_ver['version'],link])
                pkg_table.append_data_rows((pkg_rows))
                data_rows.append(html.unescape(pkg_table.to_html()))
            data_rows.insert(0,bsp['name'])
            table.append_data_rows((data_rows,))
        logs.append(html.unescape(table.to_html()))
    return logs

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


    args = parser.parse_args()

    sem=threading.Semaphore(args.j)

    root_path = os.getcwd()
    time_old=datetime.now() 
    config_json = get_config(args.config)

    get_resources(config_json)

    if args.pkg:
        pkgs_name = args.pkg
    else:
        if config_json['pkgs'] == None:
            print("pkgs field is None!")
            exit(0)
        pkgs_name = list(config_json['pkgs'])

    if sys.platform != 'win32':
        home_dir = os.environ['HOME']
    else:
        home_dir = os.environ['USERPROFILE']

    pkgs_all_dict = create_pkgs_dict(os.path.join(home_dir, '.env/packages/packages'))

    pkgs_config_dict = get_pkgs(pkgs_all_dict, pkgs_name)
    print(pkgs_config_dict)

    build_all(config_json, pkgs_config_dict)

    time_new=datetime.now() 
    print(time_new-time_old)
    print('Please via browser open ' + os.path.join(os.getcwd(),'artifacts_export/index.html') + ' view results!!')
