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
        pkgs_res = self.pkgs_res_dict['pkgs_res']
        for pkg, pkg_res in pkgs_res.items():
            vers_res = pkg_res['versions']
            if 'latest' not in vers_res:
                print(f'[error] {pkg} can not find latest version.')
                error_num += 1
            for ver, ver_res in vers_res.items():
                rtts_res = ver_res['rtt_res']
                if 'master' not in rtts_res:
                    print(f'[error] {pkg} {ver}' +
                          ' can not find rt-thread master version.')
                    error_num += 1
                for rtt, rtt_res in rtts_res.items():
                    bsps_res = rtt_res['bsp_res']
                    for bsp, bsp_res in bsps_res.items():
                        if bsp_res['res'] == 'Failure':
                            if rtt == 'master' and ver == 'latest':
                                print('[error] compile failure.')
                                error_num += 1
                            else:
                                print('[warning] compile failure. ' +
                                      ' But not master(rtt) and latest(pkg).')
                            log_file = (self.artifacts_path + '/' +
                                        bsp_res['log_file'])
                            try:
                                with open(log_file, 'r') as file:
                                    context = file.read()
                                    desc = f"{pkg}:{ver} {rtt} {bsp}"
                                    print("::group::" + desc)
                                    print(context)
                                    print('::endgroup::')
                            except Exception as e:
                                print(e)
                        elif bsp_res['res'] == 'Invalid':
                            print(f"Invalid. ({pkg}:{ver}  {rtt} {bsp}) ")
                        elif bsp_res['res'] == 'Success':
                            print(f"Success. ({pkg}:{ver} {rtt} {bsp}) ")
        return error_num
