import logging
import click
import yaml
from colorama import Style, Fore
from hsettings import Settings
from hsettings.loaders import DictLoader, YamlLoader
from jumpserver_sync import __prog__, __version__
from jumpserver_sync.utils import *
from jumpserver_sync.workflow import DumpSettings, AssetsSync, AssetsSmartSync, AssetsCheckSync, AssetsCleanSync, AssetsListenSync


@click.group()
def cli(**kwargs):
    """
    Jumpserver sync tool.

    This tool is useful to sync large amount of assets from cloud service (such as AWS) to Jumpserver.
    """
    pass


@cli.command(short_help='Show version and exit.')
def version(**kwargs):
    """
    Show version and exit.
    """
    click.echo('{} {}'.format(__prog__, __version__))


@cli.command(short_help='Dump config file settings and exit.')
@click.option('-c', '--config-file', help='config file path', type=click.File('r'), required=True)
def dump(**kwargs):
    """
    Dump config file settings and exit.
    """
    app = Application(args=kwargs)
    app.run_workflow(DumpSettings)


@cli.command(short_help='Sync assets to Jumpserver.')
@click.option('-c', '--config-file', help='config file path', type=click.File('r'))
@click.option('-h', '--host', help='jumpserver host')
@click.option('-u', '--user', help='jumpserver admin username')
@click.option('-w', '--password', help='jumpserver admin password')
@click.option('-p', '--profile', help='profile name')
@click.option('-i', '--instance-ids', help='instance id or comma separated list')
@click.option('-e', '--provider', help='instance provider', type=click.Choice(['aws']), default='aws')
@click.option('--all/--no-all', help='force to sync all assets from provider', default=False)
@click.option('--push/--no-push', help='push system user after add asset or not', default=False)
@click.option('--push-check/--no-push-check', help='push and check system user after add asset or not', default=False)
@click.option('--force-push/--no-force-push', help='force push system user after add asset or not', default=False)
@click.option('--test/--no-test', help='test asset alive after add asset or not', default=False)
@click.option('--check-timeout', help='timeout seconds to check results', type=int)
@click.option('--check-interval', help='interval seconds to wait between check', type=int)
@click.option('--push-max-tries', help='max tries to push system_user', type=int)
@click.option('--push-system-users', help='specify system_users to push, comma separated, default is to push all')
@click.option('--show-task-log/--no-show-task-log', help='show task output log', default=False)
def sync(**kwargs):
    """
    Sync assets from cloud service provider (such as AWS) to Jumpserver.

    If --all option is specified, sync all assets produced by provider.
    If --instance-ids option is specified, only sync assets specified.
    Otherwise, will compare difference between Jumpserver and provider.
    Add assets to Jumpserver if assets produced by provider not exists.
    And delete assets in Jumpserver if assets not exists in provider.
    """
    app = Application(args=kwargs)
    if app.settings.get(CONF_INSTANCE_ALL_KEY, False) is True:
        # sync all assets
        workflow = AssetsSync
    elif app.settings.get(CONF_INSTANCE_IDS_KEY):
        # sync specified instance-ids
        workflow = AssetsSync
    else:
        # smart sync
        workflow = AssetsSmartSync
    app.run_workflow(workflow)


@cli.command(short_help='Listening on queues to sync assets to Jumpserver.')
@click.option('-c', '--config-file', help='config file path', type=click.File('r'))
@click.option('-h', '--host', help='jumpserver host')
@click.option('-u', '--user', help='jumpserver admin username')
@click.option('-w', '--password', help='jumpserver admin password')
@click.option('-l', '--listen-provider', help='listening task provider name')
@click.option('--push/--no-push', help='push system user after add asset or not', default=False)
@click.option('--push-check/--no-push-check', help='push and check system user after add asset or not', default=False)
@click.option('--force-push/--no-force-push', help='force push system user after add asset or not', default=False)
@click.option('--test/--no-test', help='test asset alive after add asset or not', default=False)
@click.option('--check-timeout', help='timeout seconds to check results', type=int)
@click.option('--check-interval', help='interval seconds to wait between check', type=int)
@click.option('--push-max-tries', help='max tries to push system_user', type=int)
@click.option('--push-system-users', help='specify system_users to push, comma separated, default is to push all')
@click.option('--show-task-log/--no-show-task-log', help='show task output log', default=False)
@click.option('--listen-interval', help='interval seconds between two check', type=int, default=3)
def listen(**kwargs):
    """
    Listening on queues (such as AWS SQS) to sync assets to Jumpserver

    If --listen-provider option is specified, listening on specified queue.
    Otherwise listening on all configured queues.
    """
    app = Application(args=kwargs)
    app.run_workflow(AssetsListenSync)


@cli.command(short_help='Check assets alive in Jumpserver.')
@click.option('-c', '--config-file', help='config file path', type=click.File('r'))
@click.option('-h', '--host', help='jumpserver host')
@click.option('-u', '--user', help='jumpserver admin username')
@click.option('-w', '--password', help='jumpserver admin password')
@click.option('-p', '--profile', help='profile name')
@click.option('-i', '--instance-ids', help='instance id or comma separated list')
@click.option('--check-timeout', help='timeout seconds to check results', type=int)
@click.option('--check-interval', help='interval seconds to wait between check', type=int)
@click.option('--show-task-log/--no-show-task-log', help='show task output log', default=True)
def check(**kwargs):
    app = Application(args=kwargs)
    app.run_workflow(AssetsCheckSync)


@cli.command(short_help='Clean assets in Jumpserver.')
@click.option('-c', '--config-file', help='config file path', type=click.File('r'))
@click.option('-h', '--host', help='jumpserver host')
@click.option('-u', '--user', help='jumpserver admin username')
@click.option('-w', '--password', help='jumpserver admin password')
@click.option('-p', '--profile', help='profile name')
@click.option('-e', '--provider', help='instance provider', type=click.Choice(['aws']), default='aws')
@click.option('-i', '--instance-ids', help='instance id or comma separated list')
@click.option('--all/--no-all', help='force to clean assets without test', default=False)
@click.option('--check-timeout', help='timeout seconds to check results', type=int)
@click.option('--check-interval', help='interval seconds to wait between check', type=int)
@click.option('--show-task-log/--no-show-task-log', help='show task output log', default=False)
def clean(**kwargs):
    """
    Clean assets in Jumpserver.

    By default it will only delete assets that not alive.
    Use --profile option to specify assets from which profile.
    Use --all to delete all assets.
    """
    app = Application(args=kwargs)
    app.run_workflow(AssetsCleanSync)


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
            'asset': {
                'aws': 'jumpserver_sync.providers.aws.AwsAssetsProvider'
            },
            'task': {
                'sqs': 'jumpserver_sync.providers.aws.AwsSqsTaskProvider'
            }
        },
        'profiles': {},
        'tag_selectors': [],
        'listening': {},
        'app': {
            'provider': '',
            'profile': '',
            'instance_all': False,
            'instance_ids': None,
            'push': False,
            'push_check': False,
            'force_push': False,
            'test_asset': False,
            'check_timeout': 30,
            'check_interval': 3,
            'push_max_tries': 3,
            'push_system_users': None,
            'show_task_log': False,
            'listen_provider': '',
            'listen_interval': None,
        },
    }

    args_mapping = {
        'host': CONF_BASE_URL_KEY,
        'user': CONF_USER_KEY,
        'password': CONF_PWD_KEY,
        'provider': CONF_PROVIDER_KEY,
        'profile': CONF_PROFILE_KEY,
        'all': CONF_INSTANCE_ALL_KEY,
        'instance_ids': CONF_INSTANCE_IDS_KEY,
        'push': CONF_PUSH_KEY,
        'push_check': CONF_PUSH_CHECK_KEY,
        'force_push': CONF_FORCE_PUSH_KEY,
        'test': CONF_TEST_ASSET_KEY,
        'check_timeout': CONF_CHECK_TIMEOUT_KEY,
        'check_interval': CONF_CHECK_INTERVAL_KEY,
        'push_max_tries': CONF_CHECK_MAX_TRIES_KEY,
        'push_system_users': CONF_PUSH_SYSTEM_USERS_KEY,
        'show_task_log': CONF_SHOW_TASK_LOG_KEY,
        'listen_provider': CONF_LISTEN_PROVIDER_KEY,
        'listen_interval': CONF_LISTEN_INTERVAL_KEY,
    }

    def __init__(self, args):
        self.args = args
        config_file = args['config_file'] if 'config_file' in args else None
        self._settings = self._init_setting(config_file=config_file, args=args)
        self._console_handlers = []
        self._init_logger()

    def run_workflow(self, workflow_cls):
        ins = workflow_cls(settings=self.settings)
        ins.run()

    def _init_logger(self):
        log_level = self._settings.get(CONF_LOG_LEVEL_KEY, 'INFO')
        log_formatter = self._settings.get(CONF_LOG_FORMATTER_KEY)
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
