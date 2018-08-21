# -*- coding: utf-8 -*-
import sys
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
mvn_accelerate = '-am -T 1C -U -Dmaven.test.skip=true -Dmaven.compile.fork=true'
max_bak_file = 30


def test(module, branch, profile=g, is_pack='true'):
    deploy('test', module, profile, branch, is_pack)


def stage(module, branch, profile=g, is_pack='true'):
    deploy('stage', module, profile, branch, is_pack)


def prod(module, branch, profile=g, is_pack='true'):
    deploy('prod', module, profile, branch, is_pack)


def rollback(runmode, module, v, profile=g):
    cf = _load_config(profile, module)
    pack_cf = _load_package_config(cf)
    prj = pack_cf.get(module)
    if not prj:
        _error(u'不存在"{}" 此项目'.format(module))

    mode = prj.get(runmode)
    host_list = mode.get('hosts')

    if not host_list:
        _error(u'无效的hosts')

    if not isinstance(host_list, (types.ListType, types.TupleType)):
        host_list = [host_list]

    project_port = mode.get('port')
    if not project_port:
        _error(u'无效的port')

    extension = prj.get('extension')
    mode_extension = mode.get('extension')
    if mode_extension:
        if extension:
            extension = '{} {}'.format(extension, mode_extension)
        else:
            extension = mode_extension

    env.hosts = host_list
    env.user = cf.username
    env.password = cf.password
    env.project_port = project_port
    env.cf = cf
    env.runmode = runmode
    env.extension = extension
    env.status = prj.get('status')
    env.is_rollback = True
    env.bak_version = v
    env.is_pack = "false"
    v_split = v.split('_')
    if len(v_split) > 1:
        env.branch = v_split[0]
    else:
        env.branch = 'Unknown'


def deploy(runmode, module, section, branch, is_pack):
    cf = _load_config(section, module)
    if not os.path.exists(cf.source_path):
        local('mkdir -p {}'.format(cf.source_path))

    if not os.path.exists(cf.source_project_path):
        with lcd(cf.source_path):
            local('git clone {}'.format(cf.git_address))

    with lcd(cf.source_project_path):
        if is_pack == 'true':
            s = local('git fetch;git checkout {};git pull'.format(branch))
            print red(s)
        pack_cf = _load_package_config(cf)
        m = pack_cf.get(module)
        if not m:
            _error(u'不存在"{}" 此项目'.format(module))

        mode = m.get(runmode)
        host_list = mode.get('hosts')

        if not host_list:
            _error(u'无效的hosts')

        if not isinstance(host_list, (types.ListType, types.TupleType)):
            host_list = [host_list]

        project_port = mode.get('port')
        if not project_port:
            _error(u'无效的port')

        extension = m.get('extension')
        mode_extension = mode.get('extension')
        if mode_extension:
            if extension:
                extension = '{} {}'.format(extension, mode_extension)
            else:
                extension = mode_extension

        if is_pack == 'true':
            local('mvn clean install -pl {0} -P{1} {2}'.format(module, runmode, mvn_accelerate))

        print cyan('hosts: {}'.format(host_list))
        env.hosts = host_list
        env.user = cf.username
        env.password = cf.password
        env.project_port = project_port
        env.cf = cf
        env.runmode = runmode
        env.extension = extension
        env.status = m.get('status')
        env.is_rollback = False
        env.branch = branch
        env.is_pack = is_pack


def start():
    cf = env.cf
    put_remote_path = '{}/{}'.format(cf.remote_path, cf.app_name)
    if not env.is_rollback:
        app_tar_name = '{}-deploy.tar.gz'.format(cf.app_name)
        put_source_path = '{}/target/{}'.format(cf.module_path, app_tar_name)
        bak_name = '{}/bak/{}'.format(put_remote_path, _get_name_version())

        if int(run('[ -e "{}/bak" ] && echo 1 || echo 0'.format(put_remote_path))) == 0:
            run('mkdir -p {}/bak'.format(put_remote_path))

        result = put(put_source_path, bak_name)
        if result.succeeded:
            bak_file_count = int(run('ls %s/bak -l | grep -c ^-' % put_remote_path))
            if bak_file_count > max_bak_file:
                r_count = bak_file_count - max_bak_file
                r_bak_name_list_str = run("ls {0}/bak -rt|head -{1}".format(put_remote_path, r_count))
                r_bak_name_list = r_bak_name_list_str.split('\r\n')
                with cd("%s/bak" % put_remote_path):
                    run('rm -rf %s' % ' '.join(r_bak_name_list))
            _run(bak_name, put_remote_path)
    else:
        bak_name = '{}/bak/{}'.format(put_remote_path, env.bak_version)
        if int(run('[ -e "{}" ] && echo 1 || echo 0'.format(bak_name))) == 0:
            _error('不存在此版本 %s')
        _run(bak_name, put_remote_path)


def _run(bak_name, put_remote_path):
    cf = env.cf
    run("tar -xvzf {0} -C {1}".format(bak_name, put_remote_path))
    print(cyan("unpack path:%s" % put_remote_path))

    docker_name = '{0}-{1}'.format(cf.app_name, env.runmode)

    docker_id = run("docker ps|grep %s |awk '{print $1}'" % docker_name)
    if docker_id:
        print cyan("docker kill {}".format(docker_id))
        run("docker kill {}".format(docker_id))

    run("docker build -t {0} {1}".format(docker_name, put_remote_path))

    v_log = '-e LOG_PATH=/logs -v {}/logs:/logs'.format(put_remote_path)
    extension = env.extension if env.extension else ''

    docker_run_command = "docker run -e APP_NAME={0} -e RUN_MODE={1} -e PORT={2} -p {2}:{2} --expose={2} {3} {4} -d {5}" \
        .format(cf.app_name, env.runmode, env.project_port, v_log, extension, docker_name)
    run(docker_run_command, pty=False, warn_only=True, stdout=sys.stdout, stderr=sys.stdout)

    if run("docker ps -a | grep 'Exited' | awk '{print $1 }'|xargs"):
        run("docker ps -a | grep 'Exited' | awk '{print $1 }'|xargs docker stop")

    if run("docker ps -a | grep 'Exited' | awk '{print $1 }'|xargs"):
        run("docker ps -a | grep 'Exited' | awk '{print $1 }'|xargs docker rm")

    if run("docker images|grep none|awk '{print $3 }'|xargs"):
        run("docker images|grep none|awk '{print $3 }'|xargs docker rmi")

    run(
        'echo "runmode={0}\nmodule={1}\nbranch={2}\nis_rollback={3}\nproject_port={4}\nstatus={5}\nnginx_path={6}\nextension={7}\nversion={8}" > {9}/deploy.info'
            .format(env.runmode, cf.app_name, env.branch, env.is_rollback, env.project_port, env.status, cf.nginx_path,
                    extension, env.bak_version, put_remote_path))

    print green(u'部署成功！！！')
    #     restart_command = r"""
    # #!/bin/bash
    # id=$(docker ps|grep %s |awk '{print $1}')
    # if [ "$id" ] ; then
    #     docker kill $id
    #     echo $(%s)
    # fi
    #     """ % (docker_name, docker_run_command)
    #
    #
    #     run('echo -e "{0}" -> {1}/restart.sh'.format(restart_command, put_remote_path))
    #     run('chmod 777 {}/restart.sh'.format(put_remote_path))

    if env.status:
        print cyan(u'开始检查项目是否启动完成:')
        start_time = int(round(time.time() * 1000))
        time.sleep(1)
        _http_check()
        end_time = int(round(time.time() * 1000))
        print green(u'项目启动完成 耗时: %s秒' % round((end_time - start_time) / 1000, 2))

    if not cf.nginx_path:
        return
    if int(run('[ -e "{}/nginx" ] && echo 1 || echo 0'.format(put_remote_path))) == 0:
        return
    if int(run('[ -e "{0}/nginx/{1}.conf" ] && echo 1 || echo 0'.format(put_remote_path, env.runmode))) == 0:
        return

    if int(run('[ -e "{0}/conf/app" ] && echo 1 || echo 0'.format(cf.nginx_path))) == 0:
        run('mkdir -p {0}/conf/app'.format(cf.nginx_path))

    if int(run('[ -e "{0}/nginx/cert" ] && echo 1 || echo 0'.format(put_remote_path))) == 1:
        if int(run('[ -e "{0}/conf/cert" ] && echo 1 || echo 0'.format(cf.nginx_path))) == 0:
            run('mkdir -p {0}/conf/cert'.format(cf.nginx_path))

        run('cp -rf {0}/nginx/cert/* {1}/conf/cert/'.format(put_remote_path, cf.nginx_path))

    run('cp -rf {0}/nginx/{1}.conf {2}/conf/app/{3}-{1}.conf'.format(put_remote_path, env.runmode, cf.nginx_path,
                                                                     cf.app_name))
    run('%s/sbin/nginx -s reload' % cf.nginx_path)
    print green('nginx reload success!!')


def _http_check():
    url = 'http://{0}:{1}{2}'.format(env.host, env.project_port, env.status)
    try:
        print 'request GET: %s ...' % url
        urllib2.urlopen(url)
    except Exception:
        time.sleep(1)
        _http_check()


def _get_name_version():
    if 'bak_version' in env:
        return env.bak_version
    now = datetime.now()
    env.bak_version = '{0}_{1}.tar.gz'.format(env.branch, now.strftime('%Y%m%d%H%M%S')[2:])
    return env.bak_version


def _load_package_config(cf):
    p1 = '{}/packages.yml'.format(cf.source_project_path)
    p2 = '{}/packages.yaml'.format(cf.source_project_path)
    if os.path.exists(p1):
        print cyan('loaded: {}'.format(p1))
        return _load_yaml(p1)
    elif os.path.exists(p2):
        print cyan('loaded {}'.format(p2))
        return _load_yaml(p2)
    else:
        _error(u'packages.yaml 不存在')


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


def _load_yaml(path):
    with file(path, 'r') as file_stream:
        return yaml.load(file_stream)


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
