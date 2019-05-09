from jumpserver_sync.utils import JumpserverError, import_string, CONF_PROVIDERS_KEY, CONF_LISTEN_PROVIDERS_CLS_KEY, \
    CONF_LISTEN_PROVIDERS_KEY
from jumpserver_sync.providers import ProfileProvider
from jumpserver_sync.providers.aws import get_aws_session


class ListeningProvider:
    """
    Base class for listening provider.
    """

    PROVIDER_TYPE = ''

    def __init__(self, settings, profile, **kwargs):
        self._settings = settings
        self.profile = profile
        self._profile_provider = ProfileProvider(
            providers=self.settings.get(CONF_PROVIDERS_KEY),
            provider_type=self.PROVIDER_TYPE,
            profile=profile
        )

    def listen(self):
        pass

    @property
    def settings(self):
        return self._settings

    @property
    def profile_provider(self):
        return self._profile_provider


class SQSProvider(ListeningProvider):

    PROVIDER_TYPE = 'aws'

    def __init__(self, settings, profile, **kwargs):
        super().__init__(settings, profile, **kwargs)
        self._queue = queue
        self._session = None

    def get_session(self):
        if not self._session:
            self._session = get_aws_session(**self.profile_provider.conf)
        return self._session


def get_listening_provider(name, settings) -> ListeningProvider:
    if not name:
        raise JumpserverError('Listening provider name not provided!')
    conf = settings.get('{}.{}'.format(CONF_LISTEN_PROVIDERS_KEY, name), None)
    cls = settings.get('{}.{}'.format(CONF_LISTEN_PROVIDERS_CLS_KEY, name), None)
    if cls:
        cls = import_string(cls)
        return cls(settings=settings, profile=profile)
    else:
        raise JumpserverError('Invalid listening provider {}'.format(name))
