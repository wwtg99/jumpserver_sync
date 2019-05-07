import logging
import click
import yaml
from colorama import Style, Back, Fore
from hsettings import Settings
from hsettings.loaders import DictLoader, YamlLoader
from jumpserver_sync import __prog__, __version__
from jumpserver_sync.workflow import AssetsSync


@click.command()
@click.option('--version', help='show version', is_flag=True, default=False)
@click.option('--dump', help='Dump settings and exit', is_flag=True, default=False)
@click.option('-c', '--config-file', help='config file path', type=click.File('r'))
@click.option('-p', '--profile', help='profile name')
@click.option('-i', '--instance-ids', help='instance id or comma separated list')
@click.option('-e', '--provider', help='instance provider', type=click.Choice(['aws']), default='aws')
@click.option('--push/--no-push', help='push system user after add asset or not', default=False)
@click.option('--push-check/--no-push-check', help='push and check system user after add asset or not', default=False)
@click.option('--force-push/--no-force-push', help='force push system user after add asset or not', default=False)
@click.option('--test/--no-test', help='test asset alive after add asset or not', default=False)
@click.option('--check-timeout', help='timeout seconds to check results', type=int)
@click.option('--check-interval', help='interval seconds to wait between check', type=int)
@click.option('--push-max-tries', help='max tries to push system_user', type=int)
@click.option('--push-system-users', help='specify system_users to push, comma separated, default is to push all')
@click.option('--show-task-log/--no-show-task-log', help='show task output log', default=False)
def cli(version, **kwargs):
    if version:
        print('{} {}'.format(__prog__, __version__))
        return
    app = Application(args=kwargs)
    app.run()


class Application:

    default_config = {
        'jumpserver': {
            'base_url': '',
            'user': '',
            'password': '',
            'login_url': '/api/users/v1/auth/'
        },
        'cache': {
            'dir': '.jumpserver_cache',
            'ttl': 60
        },
        'log': {
            'log_level': 'INFO',
            'log_formatter': '[%(levelname)s] %(asctime)s : %(message)s',
        },
        'provider_cls': {
            'aws': 'jumpserver_sync.providers.aws.AwsAssetsProvider'
        },
        'app': {
            'push': False,
            'push_check': False,
            'test_asset': False,
            'check_timeout': 30,
            'check_interval': 3,
            'push_max_tries': 3,
            'show_task_log': False
        }
    }

    args_mapping = {
        'dump': 'app.dump',
        'provider': 'app.provider',
        'profile': 'app.profile',
        'instance_ids': 'app.instance_ids',
        'push': 'app.push',
        'push_check': 'app.push_check',
        'force_push': 'app.force_push',
        'test': 'app.test_asset',
        'check_timeout': 'app.check_timeout',
        'check_interval': 'app.check_interval',
        'push_max_tries': 'app.push_max_tries',
        'push_system_users': 'app.push_system_users',
        'show_task_log': 'app.show_task_log',
    }

    def __init__(self, args):
        self.args = args
        config_file = args['config_file'] if 'config_file' in args else None
        self._settings = self._init_setting(config_file=config_file, args=args)
        self._console_handlers = []
        self._init_logger()

    def run(self):
        if self.settings.get('app.dump', False) is True:
            print(self.settings.as_dict())
        elif self.settings.get(AssetsSync.CONF_INSTANCE_IDS_KEY):
            workflow = AssetsSync(settings=self.settings)
            workflow.run()

    def _init_logger(self):
        log_level = self._settings.get('log.log_level', 'INFO')
        log_formatter = self._settings.get('log.log_formatter')
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        logger_levels = [
            logging.ERROR,
            logging.WARNING,
            logging.INFO,
            logging.DEBUG
        ]
        for level in logger_levels:
            handler = self._create_console_level_handler(level, log_formatter)
            if handler:
                self._console_handlers.append(handler)
                root_logger.addHandler(handler)

    def _create_console_level_handler(self, level, formatter):
        level_map = {
            logging.ERROR: {
                'filter': lambda record: record.levelno >= logging.ERROR,
                'formatter': Fore.RED + formatter + Style.RESET_ALL
            },
            logging.WARNING: {
                'filter': lambda record: record.levelno == logging.WARN,
                'formatter': Fore.YELLOW + formatter + Style.RESET_ALL
            },
            logging.INFO: {
                'filter': lambda record: record.levelno == logging.INFO,
                'formatter': Fore.GREEN + formatter + Style.RESET_ALL
            },
            logging.DEBUG: {
                'filter': lambda record: record.levelno < logging.INFO,
                'formatter': Style.RESET_ALL + formatter
            }
        }
        if level in level_map:
            handler = logging.StreamHandler()
            hfilter = logging.Filter()
            hfilter.filter = level_map[level]['filter']
            handler.addFilter(hfilter)
            handler.setFormatter(logging.Formatter(level_map[level]['formatter']))
            handler.setLevel(logging.DEBUG)
            return handler
        return None

    def _init_setting(self, settings=None, config_file=None, args=None):
        setting = settings or Settings(self.default_config)
        if config_file:
            if isinstance(config_file, str):
                s = YamlLoader.load(config_file)
            else:
                s = yaml.load(config_file)
            setting.merge(s)
        if args:
            args = {k: v for k, v in args.items() if v is not None}
            s = DictLoader.load(args, key_mappings=self.args_mapping, only_key_mappings_includes=True)
            setting.merge(s)
        return setting

    @property
    def settings(self):
        return self._settings
