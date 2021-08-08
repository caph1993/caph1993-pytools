from __future__ import annotations
import abc, sys, os
import subprocess
from ports import find_free_port
from pathlib import Path
from sqlitedict import SqliteDict
from appdirs import AppDirs
import setproctitle
import psutil


def stop_process(pid, timeout=0.25):
    '''
    Terminate the process pid and all its descendants using
    signal 15, or 9 after a timeout. Wait for termination.
    '''
    desc: list[psutil.Process]
    alive: list[psutil.Process]

    p = psutil.Process(pid)
    desc = [p, *p.children(recursive=True)]
    for p in desc:
        p.terminate()
    _, alive = psutil.wait_procs(desc, timeout=timeout)
    while alive:
        for p in alive:
            p.kill()
        _, alive = psutil.wait_procs(alive, timeout=timeout)
    return


class abcService(abc.ABC):

    name: str
    author: str
    version: str
    preferred_port: int | None = None
    host = 'localhost'

    def __init__(self):
        for att in ['name', 'author', 'version']:
            assert hasattr(self, att), f'Missing attribute {att}'

        self.dirs = AppDirs(
            appname=self.name,
            appauthor=self.author,
            version=self.version,
        )
        self.site_config_dir = Path(self.dirs.site_config_dir)
        os.makedirs(self.site_config_dir, exist_ok=True)

        self.db_service = SqliteDict(
            filename=self.site_config_dir / 'service.db',
            autocommit=True,
        )
        curr_pid = self.db_service.get('pid', -1)
        curr_port = self.db_service.get('port', self.preferred_port)
        self.db_service['pid'] = curr_pid
        self.db_service['port'] = curr_port

    @property
    def pid(self) -> int:
        return self.db_service['pid']

    @property
    def port(self) -> int | None:
        return self.db_service['port']

    def alive(self, check=True):
        alive = (self.pid > 0)
        if check and alive and not self._alive():
            self.db_service['pid'] = -1
            self.db_service['port'] = None
            alive = False
        return alive

    def _alive(self):
        return psutil.pid_exists(self.pid)

    def stop(self):
        if self.alive():
            stop_process(self.pid)
        else:
            print('(already stopped)')
        print(self)

    @abc.abstractmethod
    def start(self):
        raise NotImplementedError

    def cli_start(self):
        if not self.alive():
            setproctitle.setproctitle(self.name)  # just fancy
            self.db_service['pid'] = pid = os.getpid()
            self.db_service['port'] = find_free_port(self.port)
            try:
                self.start()
                procs = psutil.Process().children()
                psutil.wait_procs(procs)
            finally:
                self.db_service['pid'] = -1
                self.db_service['port'] = None
                stop_process(pid)
        else:
            print('(already active)')
        print(self)
        return

    def __repr__(self):
        out = [
            f'alive: {self.alive()}',
            f'  pid: {self.pid}',
            f' port: {self.port}',
            f'  url: http://{self.host}:{self.port}',
        ]
        return '\n'.join(out) if self.alive() else out[0]


def load_service(service_py: str) -> abcService:
    import importlib.util
    spec = importlib.util.spec_from_file_location('_irrelevant_', service_py)
    module = importlib.util.module_from_spec(spec)  # type:ignore
    spec.loader.exec_module(module)  # type:ignore
    try:
        Service = module.Service  # type:ignore
    except:
        raise Exception(f'File {service_py} must provide a Service class')
    return Service()  # type: ignore


def webConsoleService(service_py: str):
    '''
    Create a wrapping service for starting another service in a
    web console. (Needs pip3 install butterfly) 
    '''

    service = load_service(service_py)

    sh = os.getenv('SHELL')
    script = os.path.abspath(f'{sys.argv[0]}.sh')
    spawn_sh = f'''
    #!{sh}
    rm {script}
    cd {os.getcwd()}
    {sys.executable} {sys.argv[0]} {service_py} start --wait
    exit
    '''.replace('\n    ', '\n').strip()

    class WebConsoleService(abcService):
        name = f'webconsole_{service.name}'
        author = service.author
        version = service.version

        def start(self):
            with open(script, 'w') as f:
                f.write(spawn_sh)
            Path(script).chmod(0o0777)
            subprocess.run([
                'butterfly.server.py',
                f'--port={self.port}',
                '--unsecure',
                '--one-shot',
                f'--cmd={sh} {script}',
            ], check=True)
            return

    return WebConsoleService()


if __name__ == '__main__':

    the_help = '\n'.join([
        f'     Syntax: {sys.argv[0]} <service_py> <command> (*optional)',
        f'  <command>: status start stop',
        f'(*optional): --wait --webconsole',
    ])

    try:
        _, service_py, cmd, *args = sys.argv
        assert cmd in ['status', 'start', 'stop'], f'Unknown command {cmd}'
        for arg in args:
            assert arg in ['--wait', '--webconsole'], f'Unknown argument {arg}'
        webconsole = cmd != 'status' and '--webconsole' in args
        wait = cmd == 'status' or '--wait' in args
    except:
        sys.exit(the_help)

    if not wait:
        subprocess.Popen([sys.executable, *sys.argv, '--wait'])
    else:
        service: abcService
        if webconsole:
            service = webConsoleService(service_py)
        else:
            service = load_service(service_py)
        if cmd == 'start':
            service.cli_start()
        elif cmd == 'stop':
            service.stop()
        elif cmd == 'status':
            print(service)
