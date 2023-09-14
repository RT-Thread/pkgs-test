import os
import re
import json
import shutil
import threading
import pexpect


class Build:
    def __init__(self, config, pkgs_index, logs, sem=16, qemu=False):
        self.sem_total = threading.Semaphore(sem)
        self.sem_stm32 = threading.Semaphore(1)
        self.config = config
        self.config_data = config.get_config_data()
        self.pkgs_index = pkgs_index
        self.logs = logs.logs
        self.logs_path = logs.path()
        self.root = os.getcwd()
        self.__debug = False
        self.qemu = qemu
        self.qemu_json_path = '../repository/.github/workflows/qemu.json'

    def __build_pyconfig(self, bsp_path, pkg, pkg_ver, log_path):
        print('build', bsp_path, pkg['name'], pkg_ver['version'])
        f = open(os.path.join(bsp_path, '.config'), 'a')
        f.write('\nCONFIG_' + pkg['enable'] +
                '=y\nCONFIG_' + pkg_ver['enable'] + '=y\n')
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
        if (re.compile(pkg['enable'] + '=').search(text) is None) or (
                re.compile(pkg_ver['enable'] + '=').search(text) is None):
            flag = 'Invalid'
        if flag == 'Success':
            command = ('(cd ' + bsp_path + ' && python ' +
                       os.path.join(self.config.get_path('env'),
                                    'tools/scripts/env.py') +
                       ' package --update)')
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
        if not os.path.isdir(bsp_path):
            print(bsp_path, 'No path !!!')
            return

        flag = self.__build_pyconfig(bsp_path, pkg, pkg_ver, log_path)
        (flag, pkg_path) = self.__build_pkgs_update(
            bsp_path, pkg, pkg_ver, log_path, flag)
        flag = self.__build_scons(bsp_path, tools, log_path, flag)
        if self.qemu and 'qemu' in bsp_path:
            flag = self.__qemu(bsp_path, log_path, flag, pkg, pkg_ver)
        os.rename(log_path, log_path + '-' + flag + '.txt')
        print('mv ' + log_path + ' ' + log_path + '-' + flag + '.txt')

        if not self.__debug:
            shutil.rmtree(bsp_path)
        elif pkg_path:
            self.__verify_pkg(pkg_path, bsp_path, tools, log_path)
        self.sem_total.release()

    def __qemu(self, bsp_path, log_path, flag, pkg, pkg_ver):
        if flag == 'Success':
            qemu_script = f'{bsp_path}/qemu-nographic.sh'
            with open(qemu_script, 'r') as file:
                content = file.read()
            content = "DIR=$(dirname \"$0\")\n" + content
            content = content.replace('"sd.bin"',
                                      '"$DIR/sd.bin"')
            content = content.replace('=sd.bin',
                                      '="$DIR/sd.bin"')
            content = content.replace('rtthread.bin',
                                      '"$DIR/rtthread.bin"')
            content = content.replace('sd.bin\n',
                                      '"$DIR/sd.bin"\n')
            with open(qemu_script, 'w') as file:
                file.write(content)
            command = f'sh {qemu_script}'
            print(command)
            qemu_app = pexpect.spawn(command)
            qemu_json_path = self.qemu_json_path
            qemu_target_input = []
            qemu_target_output = ''
            if os.path.exists(qemu_json_path):
                with open(qemu_json_path, 'r', encoding='utf-8') as file:
                    qemu_json = json.load(file)
                    name = pkg['name']
                    ver = pkg_ver['version']
                    if name in qemu_json and ver in qemu_json[name]:
                        qemu_target_input = qemu_json[name][ver]['input']
                        qemu_target_output = qemu_json[name][ver]['output']
            if qemu_target_output == '':
                qemu_target_output = 'msh />'
            print("qemu check, find: " + qemu_target_output)
            for input in qemu_target_input:
                qemu_app.sendline(input)

            qemu_exit_list = [qemu_target_output, pexpect.EOF, pexpect.TIMEOUT]
            qemu_exit_index = qemu_app.expect(qemu_exit_list)
            qemu_app.sendcontrol('a')
            qemu_app.send('x')
            qemu_output = qemu_app.before.decode('utf-8')
            if qemu_exit_index == 0:
                flag = 'Success'
                qemu_output += f'Get "{qemu_target_output}"!'
                print(f'Find "{qemu_target_output}"!')
            else:
                print(f'Not find "{qemu_target_output}"!')
                flag = 'Failure'
            with open(log_path, mode='a') as file:
                file.write(qemu_output)
        return flag

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
                            'artifacts_export/log',
                            rtthread_ver['name'],
                            bsp['name'],
                            pkg['name'] + '-' + pkg_ver['version'])
                        if os.path.exists(bsp_path_new):
                            shutil.rmtree(bsp_path_new)
                        shutil.copytree(bsp_path, bsp_path_new)
                        t = threading.Thread(target=self.__build, args=(
                            bsp_path_new, pkg, pkg_ver,
                            self.config.get_path(bsp['toolchain']), log_path))
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
        self.logs()

    def clean_bsps(self, verify):
        if os.path.isfile(verify):
            data = []
            with open(verify, 'rb') as f:
                data = json.load(f)
            for err in data:
                if os.path.isdir(err['bsp']):
                    shutil.rmtree(err['bsp'])
            os.remove(verify)
