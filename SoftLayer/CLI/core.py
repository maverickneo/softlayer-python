"CLI utilities"
import sys
import os
import os.path
from argparse import ArgumentParser, SUPPRESS

from SoftLayer import Client, SoftLayerError
from SoftLayer.CLI.helpers import (
    Table, CLIHalt, CLIAbort, FormattedItem, listing)
from SoftLayer.CLI.environment import Environment, CLIRunnableType

from prettytable import FRAME, NONE


def format_output(data, fmt='table'):
    if isinstance(data, basestring):
        return data

    if isinstance(data, Table):
        if fmt == 'table':
            return format_prettytable(data)
        elif fmt == 'raw':
            return format_no_tty(data)

    if fmt != 'raw' and isinstance(data, FormattedItem):
        return data.formatted

    if isinstance(data, list) or isinstance(data, tuple):
        return format_output(listing(data, separator=os.linesep))

    return data


def format_prettytable(table):
    for i, row in enumerate(table.rows):
        for j, item in enumerate(row):
            table.rows[i][j] = format_output(item)
    t = table.prettytable()
    t.hrules = FRAME
    t.horizontal_char = '.'
    t.vertical_char = ':'
    t.junction_char = ':'
    return t


def format_no_tty(table):
    t = table.prettytable()
    for col in table.columns:
        t.align[col] = 'l'
    t.hrules = NONE
    t.border = False
    t.header = False
    return t


def add_config_argument(parser):
    parser.add_argument('--config', '-C', help='Config file', dest='config')


def add_fmt_argument(parser):
    fmt_default = 'raw'
    if sys.stdout.isatty():
        fmt_default = 'table'

    parser.add_argument(
        '--format',
        help='output format',
        choices=['table', 'raw'],
        default=fmt_default,
        dest='fmt')


def parse_primary_args(modules, argv):
    # Set up the primary parser. e.g. sl command
    description = 'SoftLayer Command-line Client'
    epilog = ('To use most functions of this interface, your SoftLayer '
              'username and api_key need to be configured. The easiest way to '
              'do that is to use: \'sl config setup\'')
    parser = ArgumentParser(
        description=description,
        epilog=epilog,
        add_help=False,)

    parser.add_argument(
        'module',
        help="Module name",
        choices=sorted(['help'] + modules),
        default='help',
        nargs='?')
    parser.add_argument('aux', nargs='*', help=SUPPRESS)

    args, aux_args = parser.parse_known_args(args=argv)
    module_name = args.module.lower()

    if module_name == 'help':
        parser.print_help()
        raise CLIHalt(code=0)
    return module_name, args, aux_args


def parse_module_args(module, module_name, actions, posargs, argv):
    # Set up sub-command parser. e.g. sl command action
    args = posargs + argv

    parser = ArgumentParser(
        description=module.__doc__,
        prog="%s %s" % (os.path.basename(sys.argv[0]), module_name),
    )

    action_parser = parser.add_subparsers(dest='action')

    for action_name, method in actions.iteritems():
        if action_name:
            subparser = action_parser.add_parser(
                action_name,
                help=method.__doc__,
                description=method.__doc__,
            )
            method.add_additional_args(subparser)
            add_fmt_argument(subparser)
            add_config_argument(subparser)

    if len(posargs) == 0:
        parser.print_help()
        raise CLIHalt(code=0)

    return parser.parse_args(args=args)


def main(args=sys.argv[1:], env=Environment()):
    # Parse Top-Level Arguments
    CLIRunnableType.env = env
    exit_status = 0
    try:
        module_name, parent_args, aux_args = \
            parse_primary_args(env.plugin_list(), args)

        module = env.load_module(module_name)
        actions = env.plugins[module_name]

        # Parse Module-Specific Arguments
        parsed_args = parse_module_args(
            module, module_name, actions, parent_args.aux, aux_args)
        action = parsed_args.action

        # Parse Config
        config_files = ["~/.softlayer"]

        if parsed_args.config:
            config_files.append(parsed_args.config)

        env.load_config(config_files)
        client = Client(
            username=env.config.get('username'),
            api_key=env.config.get('api_key'),
            endpoint_url=env.config.get('endpoint_url'))

        # Do the thing
        f = env.plugins[module_name][action]
        f.env = env
        data = f.execute(client, parsed_args)
        if data:
            env.out(str(format_output(data, fmt=parsed_args.fmt)))

    except KeyboardInterrupt:
        exit_status = 1
    except CLIAbort, e:
        env.out(str(e.message))
        exit_status = e.code
    except SystemExit, e:
        exit_status = e.code
    except (SoftLayerError, Exception), e:
        env.out(str(e))
        exit_status = 1

    sys.exit(exit_status)
