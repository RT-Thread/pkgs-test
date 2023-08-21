import argparse
import os
import sys
from datetime import datetime

from components.build import Build
from components.check import Check
from components.config import Config
from components.logs import Logs
from components.packages_index import PackagesIndex


def init_parser():
    parser = argparse.ArgumentParser()

    parser.add_argument('--version', '-v', action='version',
                        version='%(prog)s version : v0.0.1',
                        help='show the version')
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
                        help='Debug mode, ' +
                        'which does not delete the generated compiled bsp!!',
                        default=False)
    parser.add_argument('--verify', action='store_true',
                        help='Test verify, ' +
                        'if it is not used, it will not affect;' +
                        ' if it is used, it will only test the wrong!!',
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
                               help='config the RT-Thread version. ' +
                               '(separated by spaces)',
                               default='')
    parser_config.add_argument('-b', '--bsps',
                               help='config the bsps (separated by spaces).',
                               default='')
    parser_config.add_argument('-p', '--pkgs',
                               help='config the pkgs ' +
                               '(separated by \\n or spaces).',
                               default='')
    parser_download = \
        subparsers.add_parser(name='download',
                              help='Download resources by config.json.')
    parser_download.add_argument('-f', '--file',
                                 help='Input file config.json path.',
                                 default='config.json')

    return parser


def check_run(args):
    check = Check(res_path=args.file)
    error_num = check.check_errors()
    if error_num > 0:
        print('pkgs test has {error_num} error.'.format(
            error_num=error_num))
        sys.exit(1)
    else:
        print('pkgs test has {error_num} error.'.format(
            error_num=error_num))
        sys.exit(0)


def config_run(args):
    config = Config(args.file)
    if args.rtthread:
        config.config_rtthread(args.rtthread)
    if args.bsps:
        config.config_bsps(args.bsps)
    if args.pkgs:
        config.config_pkgs(args.pkgs)


def download_run(args):
    config = Config(args.file)
    config.get_resources()


def test_run(args):
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
    html_path = os.path.join(os.getcwd(), 'artifacts_export/index.html')
    print(f'Please via browser open {html_path} view results!!')


def main():
    parser = init_parser()
    args = parser.parse_args()
    if args.command == 'check':
        check_run(args)
    elif args.command == 'config':
        config_run(args)
    elif args.command == 'download':
        download_run(args)
    else:
        test_run(args)


if __name__ == '__main__':
    main()
