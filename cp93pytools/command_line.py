'''
Small alternative to docopt and click for creating Command Line Interfaces (CLIs) out of functions:

 - Also composable as click (using CommandDict instead of MultiCommand)
 - Usage for commands in CommandDict's usage is shown by default
 - Command defaults are shown by default
 - Environment variables can be used optionally and are shown by default

Example:

from command_line import Command, Option, CommandDict, parse_port

def add_numbers(first:int, second:int):
    return first + second

def serve(port:int, host:str, dev:bool):
    print(port, host, dev)
    return

command_line = CommandDict(
    serve=Command(
        serve,
        Option('host', default='localhost'),
        Option('port', env='PORT', default='5000', parser=parse_port),
        Option('dev/prod', env='DEV', default='1'),
    ),
    add=Command(
        add_numbers,
        Option('first', positional=True, parser=int),
        Option('second', positional=True, parser=int),
    ),
)

if __name__ == '__main__':
    command_line()
'''
from __future__ import annotations
import os, sys
import abc
from typing import Any, Callable, Dict, Generic, List, Literal, Optional, Sequence, Tuple, Type, TypeVar, TypedDict, Union
import pprint


def parse_port(s: str):
    port = int(s)
    assert 1024 <= port <= 65535, (f'Port {port} out of range [1024, 65535]')
    return port


class Option:

    def __init__(
        self,
        name: str,
        positional: bool = False,
        categories: Sequence[str] = None,
        env: str = None,
        description: str = None,
        default: str = None,
        parser: Callable[[str], Any] = str,
    ):
        assert name
        assert not name.startswith('-')
        assert name.count('/') <= 1
        if '/' not in name:
            self.name = name
            self.neg = None
        else:
            self.name, self.neg = name.split('/', maxsplit=1)
            assert self.neg, f'Expected boolean format --yes/--no'
            assert parser is str, f'Parser is forced for booleans to x => bool(int(x))'
            parser = lambda s: bool(int(s))
        self.positional = positional
        self.env = env
        self.description = description
        self.default = default
        self.categories = categories
        self.parser = parser

    def parse(self, value: Optional[str] = None):
        if value == None:
            default = self.default
            if self.env:
                default = os.getenv(self.env, default)
            if default == None:
                return None
            value = str(default)
        return self.parser(value)

    def usage(self):
        default = f'[default: {self.default}]' if self.default else ''
        if self.env:
            value = os.getenv(self.env)
            value = '' if value is None else f':{value}'
            env = f'(env {self.env}{value}) '
        else:
            env = ''
        name = self.name
        if self.neg:
            name += f'/--{self.neg}'
        key = (f'--{name}' + ' ' * 30)[:15]
        description = '' if self.description is None else self.description
        return f'{key} {env}{default} {description}'

    def params(self):
        arg = f'--{self.name}'
        suffix = '' if self.positional else ' ...'
        if self.neg:
            arg += f'/--{self.neg}'
            suffix = ''
        if self.categories:
            suffix = ': ' + '/'.join(self.categories)
        if self.positional:
            return f'<{self.name}{suffix}>'
        else:
            return f'[{arg}{suffix}]'


class CommandDuck(abc.ABC):

    options: Sequence[Option]

    def __call__(self):
        script = sys.argv[0]
        out = self.call(script, *sys.argv[1:])
        if isinstance(out, str):
            print(out)
        else:
            pprint.pprint(out, compact=True)
        return

    @abc.abstractmethod
    def parse(self, prefix: str, *argv: str) -> \
        Tuple[Callable, Sequence, Dict]:
        ...

    @abc.abstractmethod
    def usage(self, prefix: str) -> str:
        ...

    def call(self, prefix: str, *argv: str):
        try:
            func, args, kwargs = self.parse(prefix, *argv)
        except AssertionError as e:
            red = lambda s: f'\033[0;31m{s}\033[00m'
            print(self.usage(prefix))
            print(red('Error: '), *map(red, e.args))
            sys.exit(1)
        return func(*args, **kwargs)

    def params(self):
        options = [opt.params() for opt in self.options]
        return ' '.join(options)


class Command(CommandDuck):

    def __init__(
        self,
        func: Callable,
        *options: Option,
        name: str = None,
        docs: str = None,
    ):
        self.func = func
        self.options = options
        self.name = func.__name__ if name is None else name
        self.docs = func.__doc__ if docs is None else docs

    def parse(self, prefix: str, *argv: str):
        options = {opt.name: opt for opt in self.options}
        positional = (opt for opt in self.options if opt.positional)
        neg_options = {opt.neg: opt for opt in self.options if opt.name}

        str_kwargs: Dict[str, Any] = {}
        it = iter(argv)
        for arg in it:
            if arg.startswith('--'):
                key = arg[2:]
                opt = options.get(key, neg_options.get(key))
                if opt and opt.neg:
                    value = '0' if key == opt.neg else '1'
                elif opt:
                    value = next(it, None)
                    assert value is not None, f'Expecting value after {arg}'
                elif arg == '--help':
                    return self.usage, [prefix], {}
                else:
                    assert False, f'Unknown option {arg}'
            else:
                value = arg
                opt = next(positional, None)
                assert opt, f'Unexpected positional value {value}'
            str_kwargs[opt.name] = value

        kwargs: Dict[str, Any] = {}
        for opt in options.values():
            value = opt.parse(str_kwargs.get(opt.name))
            assert value is not None, f'Required argument {opt.name} has no value'
            kwargs[opt.name] = value
        return self.func, [], kwargs

    def usage(self, prefix: str):
        options = '\n    '.join(opt.usage() for opt in self.options)
        docs = '' if self.docs is None else f'Docs:\n{self.docs}'
        return f'''
        Usage:
            {prefix} {self.params()}
            {prefix} --help
        
        Options:
            {options}
        {docs}
        '''.replace('\n        ', '\n').strip()


class CommandDict(Dict[str, Command], CommandDuck):

    def __init__(self, *commands: Command, **renamed_commands: Command):
        self.categories = []
        self.options = [
            Option('command', positional=True, categories=self.categories)
        ]
        self.add(*commands, **renamed_commands)

    def add(self, *commands: Command, **renamed_commands: Command):
        for command in commands:
            self[command.name] = command
            self.categories.append(command.name)
        for name, command in renamed_commands.items():
            self[name] = command
            self.categories.append(name)

    def parse(self, prefix: str, *argv: str):
        assert argv, f'Expected a command from: {list(self)}'
        first, *more = argv
        if first == '--help':
            return self.usage, [prefix], {}
        cmd = self.get(first)
        assert cmd, f'Command {first} not in {list(self)}\n'
        return cmd.call, [f'{prefix} {first}', *more], {}

    def usage(self, prefix: str):
        options = '\n'.join(
            [f'    {(k+" "*20)[:15]}{v.params()}' for k, v in self.items()])
        usages = '\n'.join([
            f'    {prefix} <command> [...command arguments]',
            f'    {prefix} <command> --help',
            f'    {prefix} --help',
        ])
        return f'Usage:\n{usages}\n\nOptions for <command>:\n{options}'
