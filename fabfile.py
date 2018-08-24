# -*- coding: utf-8 -*-
import random
import sys
import threading
import time
import types
import os
import urllib2

import yaml
from datetime import datetime
from fabric.api import run, env
from fabric.operations import local, put
from fabric.context_managers import lcd, cd
from fabric.colors import green, red, cyan
import ConfigParser

g = 'g'

def task(number):
    commands = []
    number = int(number)
    for i in range(number):
        commands.append(raw_input("command: "))

    yn = raw_input("确认执行吗? [Y/N]: ")
    if yn in ["Y", "y"]:
        threads = []
        for command in commands:
            t = threading.Thread(target=excute_command, args=(command,))
            t.setDaemon(True)
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        print green("All Task Completed!")
        os._exit(0)

def excute_command(command):
    time.sleep((random.randint(0, 3000)) / float(100))
    os.system(command)

def test(module, branch, profile=g):
    deploy('test', branch, module, profile)


def stage(module, branch, profile=g):
    deploy('stage', branch, module, profile)


def prod(module, branch, profile=g):
    deploy('prod', branch, module, profile)


def go():
    _run_go()
    print cyan(u'发布完成! 耗时: %s 毫秒' % (int(round(time.time() * 1000)) - int(env.start_time)))


def ngo():
    _run_go(True)
    print cyan(u'发布完成! 耗时: %s 毫秒' % (int(round(time.time() * 1000)) - int(env.start_time)))


def n():
    _run_nginx()
    print cyan(u'发布完成! 耗时: %s 毫秒' % (int(round(time.time() * 1000)) - int(env.start_time)))


def front():
    cf = env.cf

    with lcd(cf.module_path):
        local('cnpm install')
        local('npm run %s' % env.runmode)
        local('tar czvf dist.tar.gz dist')

        put_remote_path = '{0}/front/{1}'.format(cf.remote_path, cf.app_name)
        put_remote_file = '{0}/dist.tar.gz'.format(put_remote_path)
        put_source_path = '{0}/dist.tar.gz'.format(cf.module_path)

        if int(run('[ -e "{}" ] && echo 1 || echo 0'.format(put_remote_path))) == 0:
            run('mkdir -p {}'.format(put_remote_path))

        result = put(put_source_path, put_remote_file)
        if result.succeeded:
            print green(u'put success: {} -> {}'.format(put_source_path, put_remote_path))

            run("tar -xvzf {0} -C {1}".format(put_remote_file, put_remote_path))

            if int(run('[ -e "{0}/html/{1}" ] && echo 1 || echo 0'.format(cf.nginx_path, cf.app_name))) == 0:
                run('mkdir -p {0}/html/{1}'.format(cf.nginx_path, cf.app_name))

            run('cp -rf {0}/dist/* {1}/html/{2}'.format(put_remote_path, cf.nginx_path, cf.app_name))
            _n()

        print cyan(u'发布完成! 耗时: %s 毫秒' % (int(round(time.time() * 1000)) - int(env.start_time)))


def deploy(runmode, branch, module, section):
    env.start_time = int(round(time.time() * 1000))
    cf = _load_config(section, module)
    if not os.path.exists(cf.source_path):
        local('mkdir -p {}'.format(cf.source_path))

    if not os.path.exists(cf.source_project_path):
        with lcd(cf.source_path):
            local('git clone {}'.format(cf.git_address))

    with lcd(cf.source_project_path + "/" + module):
        local('git fetch;git checkout {};git pull'.format(branch))
        pack_cf = _load_package_config(cf)
        m = pack_cf.get(module)

        if not m:
            _error(u'不存在"{}" 此项目'.format(module))

        host_list = m.get(runmode)
        if not isinstance(host_list, (types.ListType, types.TupleType)):
            host_list = [host_list]

        if not host_list:
            _error(u'无效的hosts')

        env.hosts = ['localhost']
        env.user = cf.username
        env.password = cf.password
        env.cf = cf
        env.runmode = runmode
        env.branch = branch


def _run_go(n=False):
    cf = env.cf
    with lcd(cf.module_path):
        local('vgo clean && CC=gcc vgo build')
        local('tar czvf {0}.tar.gz {0} conf'.format(cf.app_name))

        put_remote_path = '{0}/{1}'.format(cf.remote_path, cf.app_name)
        put_remote_file = '{0}/{1}.tar.gz'.format(put_remote_path, cf.app_name)
        put_source_path = '{}/{}.tar.gz'.format(cf.module_path, cf.app_name)

        log_remote_path = '{0}/logs/mp'.format(cf.remote_path)

        if int(run('[ -e "{}" ] && echo 1 || echo 0'.format(put_remote_path))) == 0:
            run('mkdir -p {}'.format(put_remote_path))

        if int(run('[ -e "{}" ] && echo 1 || echo 0'.format(log_remote_path))) == 0:
            run('mkdir -p {}'.format(log_remote_path))

        result = put(put_source_path, put_remote_file)
        if result.succeeded:
            print green(u'put success: {} -> {}'.format(put_source_path, put_remote_path))
            run("tar -xvzf {0} -C {1}".format(put_remote_file, put_remote_path))
            r = run("ps -ef|grep %s/%s |grep -v 'grep' |awk '{print $2}'" % (put_remote_path, cf.app_name))
            if r:
                r = r.replace('\r', '')
                r = r.replace('\n', ' ')
                run('kill -USR2 %s' % r)
            else:
                # rcommand = "{0}/{1} -conf={0}/conf/{2}.yaml -log={3} &".format(put_remote_path, cf.app_name,env.runmode,log_remote_path)
                # start_sh = "{}/start.sh".format(put_remote_path)
                # run('echo "{0}" > {1}'.format(rcommand,start_sh))
                # run("set -m; sh {}".format(start_sh) , pty=False, warn_only=True, stdout=sys.stdout, stderr=sys.stdout)

                # screen - d - m
                run("nohup {0}/{1} -conf={0}/conf/{2}.yaml -log={3} &> /dev/null &".format(put_remote_path, cf.app_name,
                                                                                           env.runmode, log_remote_path)
                    , pty=False, warn_only=True, stdout=sys.stdout, stderr=sys.stdout)

            print green(u'deploy success')

        if n:
            _n()


def _run_nginx():
    cf = env.cf
    with lcd(cf.module_path):
        local('tar czvf {0}-nginx.tar.gz conf/nginx'.format(cf.app_name))

        put_remote_path = '{0}/{1}'.format(cf.remote_path, cf.app_name)
        put_remote_file = '{0}/{1}-nginx.tar.gz'.format(put_remote_path, cf.app_name)
        put_source_path = '{0}/{1}-nginx.tar.gz'.format(cf.module_path, cf.app_name)

        if int(run('[ -e "{}" ] && echo 1 || echo 0'.format(put_remote_path))) == 0:
            run('mkdir -p {}'.format(put_remote_path))

        result = put(put_source_path, put_remote_file)
        if result.succeeded:
            print green(u'put success: {} -> {}'.format(put_source_path, put_remote_path))
            run("tar -xvzf {0} -C {1}".format(put_remote_file, put_remote_path))
            _n()


def _n():
    cf = env.cf
    if not cf.nginx_path:
        return
    if int(run('[ -e "{}/conf/nginx" ] && echo 1 || echo 0'.format(cf.module_path))) == 0:
        return
    if int(run('[ -e "{0}/conf/nginx/{1}.conf" ] && echo 1 || echo 0'.format(cf.module_path, env.runmode))) == 0:
        return

    if int(run('[ -e "{0}/conf/nginx/nginx.conf" ] && echo 1 || echo 0'.format(cf.module_path))) == 1:
        run('cp -rf {0}/conf/nginx/nginx.conf {1}/conf/nginx.conf'.format(cf.module_path, cf.nginx_path))
    elif int(run('[ -e "{0}/nginx.conf" ] && echo 1 || echo 0'.format(cf.source_project_path))) == 1:
        run('cp -rf {0}/nginx.conf {1}/conf/nginx.conf'.format(cf.source_project_path, cf.nginx_path))

    if int(run('[ -e "{0}/conf/app" ] && echo 1 || echo 0'.format(cf.nginx_path))) == 0:
        run('mkdir -p {0}/conf/app'.format(cf.nginx_path))

    if int(run('[ -e "{0}/conf/nginx/cert" ] && echo 1 || echo 0'.format(cf.module_path))) == 1:
        if int(run('[ -e "{0}/conf/cert" ] && echo 1 || echo 0'.format(cf.nginx_path))) == 0:
            run('mkdir -p {0}/conf/cert'.format(cf.nginx_path))
        run('cp -rf {0}/conf/nginx/cert/* {1}/conf/cert/'.format(cf.module_path, cf.nginx_path))

    run('cp -rf {0}/conf/nginx/{1}.conf {2}/conf/app/{3}-{4}-{1}.conf'.format(cf.module_path, env.runmode, cf.nginx_path,
                                                                          cf.git_root_name,cf.app_name))
    run('%s/sbin/nginx -s reload' % cf.nginx_path)
    print green('nginx reload success!!')


def _load_config(section, project):
    current_dir = os.path.dirname(__file__)
    cf = ConfigParser.ConfigParser()
    with open(os.path.join(current_dir, u"fab.conf"), "r") as cfgfile:
        cf.readfp(cfgfile)
    cfgfile.close()

    if not cf.has_section(section):
        _error(u'无效的配置文件:%s' % section)

    config = Config()

    if cf.has_option(section, 'git'):
        config.git_address = cf.get(section, 'git')
    elif cf.has_option(g, 'git'):
        config.git_address = cf.get(g, 'git')
    else:
        _error(u'git地址不能为空')

    if cf.has_option(section, 'source_path'):
        config.source_path = cf.get(section, 'source_path')
    elif cf.has_option(g, 'source_path'):
        config.source_path = cf.get(g, 'source_path')
    else:
        _error(u'source地址不能为空')

    if cf.has_option(section, 'remote_path'):
        config.remote_path = cf.get(section, 'remote_path')
    elif cf.has_option(g, 'remote_path'):
        config.remote_path = cf.get(g, 'remote_path')
    else:
        _error(u'remote地址不能为空')

    if cf.has_option(section, 'username'):
        config.username = cf.get(section, 'username')
    elif cf.has_option(g, 'username'):
        config.username = cf.get(g, 'username')
    else:
        _error(u'username不能为空')

    if cf.has_option(section, 'password'):
        config.password = cf.get(section, 'password')
    elif cf.has_option(g, 'password'):
        config.password = cf.get(g, 'password')
    else:
        _error(u'password不能为空')

    if cf.has_option(section, 'nginx'):
        config.nginx_path = cf.get(section, 'nginx')
    elif cf.has_option(g, 'nginx'):
        config.nginx_path = cf.get(g, 'nginx')

    config.git_root_name = config.git_address[config.git_address.rindex('/') + 1:config.git_address.rindex('.git')]
    config.source_project_path = '{}/{}'.format(config.source_path, config.git_root_name)
    config.module_path = '{}/{}'.format(config.source_project_path, project)
    config.app_name = project
    return config


def _load_package_config(cf):
    p1 = '{}/fabgo.yml'.format(cf.source_project_path)
    p2 = '{}/fabgo.yaml'.format(cf.source_project_path)
    if os.path.exists(p1):
        print cyan('loaded: {}'.format(p1))
        return _load_yaml(p1)
    elif os.path.exists(p2):
        print cyan('loaded {}'.format(p2))
        return _load_yaml(p2)
    else:
        _error(u'fabgo.yaml 不存在')


def _load_yaml(path):
    with file(path, 'r') as file_stream:
        return yaml.load(file_stream)


def _get_name_version(app_name):
    if 'bak_version' in env:
        return env.bak_version
    now = datetime.now()
    env.bak_version = '{0}_{1}_{2}.tar.gz'.format(app_name, env.branch, now.strftime('%Y%m%d%H%M%S')[2:])
    return env.bak_version


def _error(msg):
    print red(u'_error: {}'.format(msg))
    os._exit(0)


class Config:
    app_name = None,
    git_root_name = None
    git_address = None
    git_root = None
    username = None
    password = None
    source_path = None
    source_project_path = None
    remote_path = None
    nginx_path = None
    module_path = None
    port = 22
