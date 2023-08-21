import os
import json


class Check:
    def __init__(self, res_path='pkgs_res.json'):
        self.res_path = res_path
        self.artifacts_path = os.path.join(os.getcwd(),
                                           os.path.dirname(res_path))
        self.pkgs_res_dict = self.__get_pkgs_res_dict()

    def __get_pkgs_res_dict(self):
        pkgs_res_dict = {}
        with open(self.res_path, 'rb') as f:
            pkgs_res_dict = json.load(f)
        return pkgs_res_dict

    def check_errors(self):
        error_num = 0
        if 'master' not in self.pkgs_res_dict['pkgs_res']:
            print('[error] can not find rt-thread master version.')
            error_num = 1
        else:
            master_res = self.pkgs_res_dict['pkgs_res']['master']
            for bsp_name, bsp_res in master_res.items():
                for pkg_name, pkg_res in bsp_res.items():
                    check_counter = 0
                    for version_res in pkg_res['versions']:
                        if version_res['version'] == 'latest':
                            check_counter = check_counter + 1
                            pkg = pkg_name
                            ver = version_res['version']
                            bsp = bsp_name
                            print(f"check {pkg} {ver} on {bsp}.")
                            if version_res['res'] == 'Failure':
                                error_num = error_num + 1
                                print('[error] compile failure.')
                                log_file = (self.artifacts_path + '/' +
                                            version_res['log_file'])
                                try:
                                    with open(log_file, 'r') as file:
                                        context = file.read()
                                        desc = f"master/{bsp}/{pkg}/{ver}"
                                        print("::group::" + desc)
                                        print(context)
                                        print('::endgroup::')
                                except Exception as e:
                                    print(e)
                            else:
                                print('compile success.')
                        else:
                            print('check {pkg} {version} on {bsp}.'.format(
                                pkg=pkg_name,
                                version=version_res['version'],
                                bsp=bsp_name), end=' ')
                            print('but not is latest, pass.')
                    if check_counter == 0:
                        error_num = error_num + 1
                        print('[error] can not find latest version.')
        return error_num
