from importlib import import_module


CONF_BASE_URL_KEY = 'jumpserver.base_url'
CONF_USER_KEY = 'jumpserver.user'
CONF_PWD_KEY = 'jumpserver.password'
CONF_LOGIN_URL_KEY = 'jumpserver.login_url'
CONF_CACHE_DIR_KEY = 'cache.dir'
CONF_CACHE_TTL_KEY = 'cache.ttl'
CONF_LOG_LEVEL_KEY = 'log.log_level'
CONF_LOG_FORMATTER_KEY = 'log.log_formatter'
CONF_PROFILES_KEY = 'profiles'
CONF_PROVIDERS_KEY = 'provider_cls'
CONF_TAG_SELECTORS_KEY = 'tag_selectors'
CONF_PROVIDER_KEY = 'app.provider'
CONF_PROFILE_KEY = 'app.profile'
CONF_TEST_ASSET_KEY = 'app.test_asset'
CONF_PUSH_KEY = 'app.push'
CONF_PUSH_CHECK_KEY = 'app.push_check'
CONF_FORCE_PUSH_KEY = 'app.force_push'
CONF_CHECK_TIMEOUT_KEY = 'app.check_timeout'
CONF_CHECK_INTERVAL_KEY = 'app.check_interval'
CONF_CHECK_MAX_TRIES_KEY = 'app.push_max_tries'
CONF_PUSH_SYSTEM_USERS_KEY = 'app.push_system_users'
CONF_SHOW_TASK_LOG_KEY = 'app.show_task_log'
CONF_INSTANCE_IDS_KEY = 'app.instance_ids'
CONF_INSTANCE_ALL_KEY = 'app.instance_all'
CONF_LISTEN_PROVIDER_KEY = 'app.listen_provider'
CONF_LISTEN_CONF_KEY = 'listening'


class JumpserverError(Exception):
    pass


class JumpserverAuthError(JumpserverError):
    pass


def import_string(dotted_path):
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.

    :param dotted_path: path to import
    :return: imported class
    :raise: ImportError
    """
    try:
        module_path, class_name = dotted_path.rsplit('.', 1)
    except ValueError:
        msg = "%s doesn't look like a module path" % dotted_path
        raise ImportError(msg)

    module = import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError:
        msg = 'Module "%s" does not define a "%s" attribute/class' % (
            module_path, class_name)
        raise ImportError(msg)


def object_format(obj, attr_vars):
    """
    Format string or string in object with variables.

    :param obj:
    :param attr_vars:
    :return:
    """
    if isinstance(obj, str):
        obj = obj.format(**attr_vars)
    elif isinstance(obj, list):
        obj = [object_format(v, attr_vars) for v in obj]
    elif isinstance(obj, dict):
        obj = {object_format(k, attr_vars): object_format(v, attr_vars) for k, v in obj.items()}
    return obj


class Profile:
    """
    Profile configuration
    """

    def __init__(self, profile_type, profile_name, config):
        """

        :param profile_type:
        :param profile_name:
        :param config:
        """
        self.profile_type = profile_type
        self.profile_name = profile_name
        self.config = config

    @classmethod
    def load_profile(cls, profiles, profile_name):
        if profile_name in profiles:
            if 'type' not in profiles[profile_name]:
                raise JumpserverError('No type in profile {}'.format(profile_name))
            return Profile(
                profile_type=profiles[profile_name]['type'],
                profile_name=profile_name,
                config=profiles[profile_name]
            )
        else:
            raise JumpserverError('Invalid profile {}'.format(profile_name))
