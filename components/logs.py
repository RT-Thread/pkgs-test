import os
import re
import json
import pytz
import shutil
import requests
from datetime import datetime
from dominate.tags import (div, head, style, html, body,
                           p, tr, th, table, td, a, h1,
                           h2, h3, details, summary)


class Logs:
    def __init__(self, logs_path, config_data, pkgs_index):
        self.logs_path = logs_path
        self.config_data = config_data
        self.pkgs_index = pkgs_index
        self.master_is_tab = False
        self.__clear_logs_path()
        self.pkgs_res = {}
        self.append_res = False
        self.pages_url = 'http://rt-thread.github.io/packages/'

    def __clear_logs_path(self):
        if os.path.isdir(self.logs_path):
            shutil.rmtree(self.logs_path)
        os.makedirs(self.logs_path)

    def __build_res(self, append_res=False):
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
                version = pkg_version['version']
                res = {}
                res['version'] = version
                res['log_file'] = get_log_file(
                    version, rtthread_name, bsp_name, pkg['name'])
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

        if append_res:
            pkgs_res = download_old_res()
        else:
            pkgs_res = {}
        print(pkgs_res)
        for rtthread in self.config_data['rtthread']:
            if 'pkgs_res' not in pkgs_res:
                pkgs_res['pkgs_res'] = {}
            for rtthread in self.config_data['rtthread']:
                rtt_name = rtthread['name']
                if rtt_name not in pkgs_res['pkgs_res']:
                    pkgs_res['pkgs_res'][rtt_name] = {}
                for bsp in self.config_data['bsps']:
                    bsp_name = bsp['name']
                    if bsp_name not in pkgs_res['pkgs_res'][rtt_name]:
                        pkgs_res['pkgs_res'][rtt_name][bsp_name] = {}
                    for pkg in self.pkgs_index:
                        pkg_name = pkg['name']
                        pkgs_res['pkgs_res'][rtt_name][bsp_name][pkg_name] = \
                            get_pkg_res(pkg, rtt_name, bsp_name)

        timezone = pytz.timezone('Asia/Shanghai')
        localized_time = timezone.localize(datetime.now())
        pkgs_res['last_run_time'] = localized_time.strftime(
            '%Y-%m-%d %H:%M:%S %Z%z')
        return pkgs_res

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
                    pkg_version_tr += \
                        td(a(version['res'], href=version['log_file']),
                           cls='successed')
                elif version['res'] == 'Failure':
                    pkg_version_tr += \
                        td(a(version['res'], href=version['log_file']),
                           cls='failed')
                else:
                    pkg_version_tr += \
                        td(a(version['res'], href=version['log_file']),
                           cls='warning')
                pkg_result_table.add(pkg_version_tr)
            return pkg_result_table

        def get_success_pkg_num(pkgs):
            success_pkg_num = 0
            for __, pkg_res in pkgs.items():
                for version in pkg_res['versions']:
                    if version['version'] == 'latest' and \
                            version['res'] == 'Success':
                        success_pkg_num = success_pkg_num + 1
            return success_pkg_num

        def generate_result_table():
            result_div = div(id='pkgs_test_result')
            result_div.add(h1('Packages Test Result'))
            result_div.add(
                p('Last run at: ' + self.pkgs_res['last_run_time']))
            for rtthread_name, rtthread_res in \
                    self.pkgs_res['pkgs_res'].items():
                result_div = div(id='pkgs_test_result_' + rtthread_name)
                result_div.add(
                    h2('RT-Thread Version: ' + rtthread_name))
                for bsp_name, bsp_res in rtthread_res.items():
                    result_div.add(h3("bsp: {bsp}".format(bsp=bsp_name)))
                    pkgs_num = len(bsp_res)
                    success_num = get_success_pkg_num(bsp_res)
                    result_div.add(
                        p(f'{pkgs_num} packages in total, ' +
                          f'{success_num} packages pass the test. ' +
                          f'({success_num}/{pkgs_num})'))
                    d = details()
                    d.add(summary("problem packages: "))
                    for pkg_name, pkg_res in bsp_res.items():
                        for version in pkg_res['versions']:
                            if version['version'] == 'latest' and \
                                    version['res'] != 'Success':
                                d.add(
                                    p(a(pkg_name, href=pkg_res['repository'])))
                    result_div.add(d)

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
        pkgs_res_single = self.__build_res(False)
        pkgs_res_single_path = os.path.join(self.logs_path,
                                            'pkgs_res_single.json')
        with open(pkgs_res_single_path, 'w') as f:
            json.dump(pkgs_res_single, f)

        self.pkgs_res = self.__build_res(self.append_res)
        pkgs_res_path = os.path.join(self.logs_path, 'pkgs_res.json')
        with open(pkgs_res_path, 'w') as f:
            json.dump(self.pkgs_res, f)

        logs_html = self.__html_report()
        logs_html_path = os.path.join(self.logs_path, 'index.html')
        with open(logs_html_path, 'w') as f:
            for log in logs_html:
                f.write(log)

    def path(self):
        return self.logs_path
