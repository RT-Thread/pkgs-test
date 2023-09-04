import os
import re
import json
import pytz
import shutil
import requests
from datetime import datetime
from dominate.tags import (div, head, style, html, body, details, summary,
                           p, a, h1, h2, script, ul, li, span,)


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
        self.pkg_res_version = 'v0.2.0'
        self.category_dict = {}
        self.pkgs_availability_level_dict = {}

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

        def get_pkg_res(pkg, rtt_list, bsp_list):
            res = {}
            res['pkg'] = pkg['name']
            res['repository'] = pkg['repository']
            res['versions'] = {}
            res['category'] = pkg['category']
            pkg_res = res['versions']
            version_list = []
            for pkg_version in pkg['pkg']:
                version_list.append(pkg_version['version'])

            for version in version_list:
                version_res = {}
                version_res['rtt_res'] = {}
                for rtt in rtt_list:
                    rtt_res = {}
                    rtt_res['bsp_res'] = {}
                    for bsp in bsp_list:
                        bsp_res = {}
                        log_file = get_log_file(
                            version, rtt, bsp, pkg['name'])
                        bsp_res['log_file'] = log_file
                        bsp_res['res'] = check_logfile(log_file)
                        rtt_res['bsp_res'][bsp] = bsp_res
                    version_res['rtt_res'][rtt] = rtt_res
                pkg_res[version] = version_res

            pkg_availability_level = 0
            level_num = [0, 0, 0]
            for version in version_list:
                version_res = pkg_res[version]
                version_availability_level = 0
                rtt_err_num = 0
                for rtt in rtt_list:
                    rtt_res = version_res['rtt_res'][rtt]
                    bsp_err_num = 0
                    rtt_availability_level = 0
                    for bsp in bsp_list:
                        bsp_res = rtt_res['bsp_res'][bsp]
                        if bsp_res['res'] == 'Failure':
                            bsp_err_num = bsp_err_num + 1
                    if bsp_err_num == 0:
                        rtt_availability_level = 0  # all bsps pass
                    elif bsp_err_num < len(bsp_list):
                        rtt_availability_level = 1  # part of bsps pass
                        rtt_err_num = rtt_err_num + 1
                    else:
                        rtt_availability_level = 2  # none bsp pass
                        rtt_err_num = rtt_err_num + 1
                    rtt_res['rtt_availability_level'] = rtt_availability_level
                if rtt_err_num == 0:
                    version_availability_level = 0  # all rtt pass
                    level_num[0] = level_num[0] + 1
                elif ('master' in version_res and
                      version_res['master']['rtt_availability_level'] == 0):
                    version_availability_level = 1  # master pass
                    level_num[1] = level_num[1] + 1
                else:
                    version_availability_level = 2  # master not pass
                    level_num[2] = level_num[2] + 1
                version_res['version_availability_level'] = \
                    version_availability_level

            if level_num[0] == len(version_list):
                pkg_availability_level = 0  # all version pass
            elif (level_num[0] + level_num[1] == len(version_list) or
                  ('latest' in version_list and (
                      pkg_res['latest']['version_availability_level'] == 0 or
                      pkg_res['latest']['version_availability_level'] == 1))):
                pkg_availability_level = 1  # master latest pass
            else:
                pkg_availability_level = 2  # master or latest not pass
            res['pkg_availability_level'] = pkg_availability_level
            return res

        if append_res:
            pkgs_res = download_old_res()
            if not (('version' in pkgs_res) and
                    (pkgs_res['version'] == self.pkg_res_version)):
                print("Download an old version pkgs_res.json !")
                pkgs_res = {}

        else:
            pkgs_res = {}
        pkgs_res['version'] = self.pkg_res_version
        if 'pkgs_res' not in pkgs_res:
            pkgs_res['pkgs_res'] = {}

        rtt_list = []
        for rtthread in self.config_data['rtthread']:
            rtt_list.append(rtthread['name'])
        bsp_list = []
        for bsp in self.config_data['bsps']:
            bsp_list.append(bsp['name'])
        for pkg in self.pkgs_index:
            pkgs_res['pkgs_res'][pkg['name']] = \
                get_pkg_res(pkg, rtt_list, bsp_list)

        timezone = pytz.timezone('Asia/Shanghai')
        localized_time = timezone.localize(datetime.now())
        pkgs_res['last_run_time'] = localized_time.strftime(
            '%Y-%m-%d %H:%M:%S %Z%z')
        return pkgs_res

    def __html_report(self):
        style_applied = '''
            .hidden { display: none; }
            .expandable::before {
                content: '➔';
                display: inline-block;
                transform: rotate(0deg);
                transition: transform 0.3s;
            }
            .expanded::before {
                transform: rotate(90deg);
            }
        '''
        script_applied = '''
            function toggleVisibility(id, trigger) {
                const element = document.getElementById(id);
                if (element.classList.contains('hidden')) {
                    element.classList.remove('hidden');
                    trigger.classList.add('expanded');
                } else {
                    element.classList.add('hidden');
                    trigger.classList.remove('expanded');
                }
            }
        '''

        def get_category_dict():
            category_dict = {}
            for __, pkg_res in self.pkgs_res['pkgs_res'].items():
                pkg = pkg_res['pkg']
                category = pkg_res['category']
                if category not in category_dict:
                    category_dict[category] = []
                category_dict[category].append(pkg)
            sorted_keys = sorted(category_dict.keys())
            sorted_category_dict = {}
            for key in sorted_keys:
                category_dict[key].sort()
                sorted_category_dict[key] = category_dict[key]
            return sorted_category_dict

        def get_pkgs_availability_level_dict():
            dict = {0: [], 1: [], 2: []}
            for pkg, pkg_res in self.pkgs_res['pkgs_res'].items():
                dict[pkg_res['pkg_availability_level']].append(pkg)
            return dict

        def get_bsp_li(bsp, bsp_res):
            title = bsp
            if bsp_res['res'] == 'Failure':
                title = '🔴 ' + title
            elif bsp_res['res'] == 'Success':
                title = '🟢 ' + title
            elif bsp_res['res'] == 'Invalid':
                title = '⚪ ' + title
            bsp_li = li(a(title, href=bsp_res['log_file']))
            return bsp_li

        def get_rtt_li(pkg, ver, rtt, rtt_res):
            title = rtt
            if rtt_res['rtt_availability_level'] == 0:
                title = '🟢 ' + title
            elif rtt_res['rtt_availability_level'] == 1:
                title = '🟠 ' + title
            elif rtt_res['rtt_availability_level'] == 2:
                title = '🔴 ' + title
            rtt_li = li(title)
            item_id = pkg + '_' + ver + '_' + rtt
            rtt_li += span(_class='expandable expanded',
                           onclick=f"toggleVisibility('{item_id}', this)")
            rtt_ul = ul(id=item_id)
            for bsp, bsp_res in rtt_res['bsp_res'].items():
                rtt_ul += get_bsp_li(bsp, bsp_res)
            rtt_li += rtt_ul
            return rtt_li

        def get_version_li(pkg, ver, ver_res):

            title = ver
            if ver_res['version_availability_level'] == 0:
                title = '🟢 ' + title
            elif ver_res['version_availability_level'] == 1:
                title = '🟠 ' + title
            elif ver_res['version_availability_level'] == 2:
                title = '🔴 ' + title
            version_li = li(title)
            item_id = pkg + '_' + ver
            version_li += span(_class='expandable expanded',
                               onclick=f"toggleVisibility('{item_id}', this)")
            version_ul = ul(_class='expanded', id=item_id)

            for rtt, rtt_res in ver_res['rtt_res'].items():
                version_ul += get_rtt_li(pkg, ver, rtt, rtt_res)

            version_li += version_ul
            return version_li

        def generate_doc():
            doc_div = div(id='pkgs_test_result')
            doc_div += h1('RT-Thread Packages Test Result')
            doc_div += p('Last run at: ' + self.pkgs_res['last_run_time'])

            doc_div += h2('Instructions')
            desc = details()
            desc += summary("Symbol Description")
            desc += p("Package availability level:")
            desc += p("🟢: All versions pass.")
            desc += p("🟠: Master(RT-Thread) latest(package) pass.")
            desc += p("🔴: Master(RT-Thread) latest(package) not pass.")

            desc += p("Package Version availability level:")
            desc += p("🟢: All RT-Thread versions pass.")
            desc += p("🟠: Master(RT-Thread) pass.")
            desc += p("🔴: Master(RT-Thread) not pass.")

            desc += p("RT-Thread availability level:")
            desc += p("🟢: All bsps pass.")
            desc += p("🟠: Part of bsps pass.")
            desc += p("🔴: None bsp pass.")

            desc += p("Test result:")
            desc += p("🟢: Success")
            desc += p("🔴: Failure")
            desc += p("⚪: Invalid")

            doc_div += desc

            doc_div += h2('Summary')

            pkgs_num = 0
            level_num = {}
            for level, pkg_list in self.pkgs_availability_level_dict.items():
                level_num[level] = len(pkg_list)
                pkgs_num += level_num[level]
            doc_div += p(f"Tested {pkgs_num} packages.")
            for level, num in level_num.items():
                d = details()
                if level == 0:
                    d += summary(f"🟢: ({num}/{pkgs_num}) All versions pass.")
                elif level == 1:
                    d += summary(f"🟠: ({num}/{pkgs_num}) " +
                                 "Master(RT-Thread) latest(package) pass.")
                elif level == 2:
                    d += summary(f"🔴: ({num}/{pkgs_num}) " +
                                 "Master(RT-Thread) latest(package) not pass.")
                pkgs_text = ''
                for pkg in self.pkgs_availability_level_dict[level]:
                    pkgs_text += pkg
                    pkgs_text += ', '
                d += p(pkgs_text)
                doc_div += d

            doc_div += h2('Detailed test results:')
            pkgs_ul = ul()
            pkgs_res = self.pkgs_res['pkgs_res']
            for category, pkg_list in self.category_dict.items():
                category_li = li(category)
                category_li += span(_class='expandable',
                                    onclick=("toggleVisibility('" +
                                             category +
                                             "', this)"))
                category_ul = ul(_class='hidden', id=category)
                for pkg in pkg_list:
                    pkg_res = pkgs_res[pkg]
                    title = pkg
                    if pkg_res['pkg_availability_level'] == 0:
                        title = '🟢 ' + title
                    elif pkg_res['pkg_availability_level'] == 1:
                        title = '🟠 ' + title
                    elif pkg_res['pkg_availability_level'] == 2:
                        title = '🔴 ' + title
                    pkg_li = li(a(title, href=pkgs_res[pkg]['repository']))
                    pkg_li += span(_class='expandable',
                                   onclick=f"toggleVisibility('{pkg}', this)")
                    pkg_ul = ul(_class='hidden', id=pkg)

                    for ver, ver_res in pkg_res['versions'].items():
                        pkg_ul += get_version_li(pkg, ver, ver_res)
                    pkg_li += pkg_ul
                    category_ul += pkg_li

                pkgs_ul += category_li
                category_li += category_ul

            doc_div += pkgs_ul
            return doc_div

        self.category_dict = get_category_dict()
        self.pkgs_availability_level_dict = get_pkgs_availability_level_dict()

        html_root = html()
        html_root += head(style(style_applied, type='text/css'))
        html_root += body(generate_doc())
        html_root += script(script_applied)

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
