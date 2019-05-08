import logging
import click
import yaml
from colorama import Style, Back, Fore
from hsettings import Settings
from hsettings.loaders import DictLoader, YamlLoader
from jumpserver_sync import __prog__, __version__
from jumpserver_sync.workflow import Workflow, DumpSettings, AssetsSync, AssetsProfileSync, AssetsCleanSync


@click.command()
@click.option('--version', help='show version', is_flag=True, default=False)
@click.option('--dump', help='Dump settings and exit', is_flag=True, default=False)
@click.option('-c', '--config-file', help='config file path', type=click.File('r'))
@click.option('-p', '--profile', help='profile name')
@click.option('-i', '--instance-ids', help='instance id or comma separated list')
@click.option('-e', '--provider', help='instance provider', type=click.Choice(['aws']), default='aws')
@click.option('--all/--no-all', help='force to apply all assets, sync all assets by provider and if it used with --clean, will clean all assets', default=False)
@click.option('--clean', help='clean assets in Jumpserver, by default only delete assets that not alive', is_flag=True, default=False)
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

    CONF_DUMP_KEY = 'app.dump'
    CONF_LOG_LEVEL_KEY = 'log.log_level'
    CONF_LOG_FORMATTER_KEY = 'log.log_formatter'

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
            'instance_all': False,
            'clean': False,
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
        'dump': CONF_DUMP_KEY,
        'provider': Workflow.CONF_PROVIDER_KEY,
        'profile': Workflow.CONF_PROFILE_KEY,
        'all': Workflow.CONF_INSTANCE_ALL_KEY,
        'clean': Workflow.CONF_INSTANCE_CLEAN_KEY,
        'instance_ids': Workflow.CONF_INSTANCE_IDS_KEY,
        'push': Workflow.CONF_PUSH_KEY,
        'push_check': Workflow.CONF_PUSH_CHECK_KEY,
        'force_push': Workflow.CONF_FORCE_PUSH_KEY,
        'test': Workflow.CONF_TEST_ASSET_KEY,
        'check_timeout': Workflow.CONF_CHECK_TIMEOUT_KEY,
        'check_interval': Workflow.CONF_CHECK_INTERVAL_KEY,
        'push_max_tries': Workflow.CONF_CHECK_MAX_TRIES_KEY,
        'push_system_users': Workflow.CONF_PUSH_SYSTEM_USERS_KEY,
        'show_task_log': Workflow.CONF_SHOW_TASK_LOG_KEY,
    }

    def __init__(self, args):
        self.args = args
        config_file = args['config_file'] if 'config_file' in args else None
        self._settings = self._init_setting(config_file=config_file, args=args)
        self._console_handlers = []
        self._init_logger()

    def run(self):
        if self.settings.get(self.CONF_DUMP_KEY, False) is True:
            workflow = DumpSettings(settings=self.settings)
        elif self.settings.get(Workflow.CONF_INSTANCE_CLEAN_KEY, False) is True:
            workflow = AssetsCleanSync(settings=self.settings)
        elif self.settings.get(Workflow.CONF_INSTANCE_ALL_KEY, False) is True:
            workflow = AssetsSync(settings=self.settings)
        elif self.settings.get(Workflow.CONF_INSTANCE_IDS_KEY):
            workflow = AssetsSync(settings=self.settings)
        else:
            workflow = AssetsProfileSync(settings=self.settings)
        workflow.run()

    def _init_logger(self):
        log_level = self._settings.get(self.CONF_LOG_LEVEL_KEY, 'INFO')
        log_formatter = self._settings.get(self.CONF_LOG_FORMATTER_KEY)
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
