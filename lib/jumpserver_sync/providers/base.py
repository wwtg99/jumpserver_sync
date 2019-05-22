import re
from jumpserver_sync.utils import JumpserverError, object_format, import_string, Profile, CONF_PROFILES_KEY, \
    CONF_TAG_SELECTORS_KEY, CONF_PROFILE_KEY, CONF_PROVIDERS_KEY
from jumpserver_sync.jumpserver import LabelTag


class CompiledTag(LabelTag):
    """
    Present for asset compiled label. This class support regex pattern match.
    """

    def __init__(self, key, value):
        super().__init__(key, value)
        self.compiled_value = re.compile(self.value)

    def match(self, obj):
        return self.compiled_value.match(obj)


class TagSelector:
    """
    Class to select and update assets by defined rules.
    """

    CONF_KEY = 'tag_selectors'
    CONF_TAGS_KEY = 'tags'
    CONF_ATTRS_KEY = 'attrs'

    TAG_ADMIN_USER = 'jumpserver_admin_user'
    TAG_NODE = 'jumpserver_node'
    TAG_DOMAIN = 'jumpserver_domain'

    def __init__(self, conf):
        self._conf = conf
        self._tags = []
        self._attrs = {}
        self._build_selector()

    def select(self, asset):
        """
        Check asset for this selector, return updated asset if checked or None if not checked.

        :param asset:
        :return: asset or None
        """
        # check required fields
        if not asset.number or not asset.hostname or not asset.ip:
            return None
        # check tags
        if not self.match_tags(asset.labels):
            return None
        # update attributes
        attr_vars = {
            'number': asset.number,
            'hostname': asset.hostname,
            'ip': asset.ip,
            'public_ip': asset.public_ip,
            'account': asset.account,
            'region': asset.region
        }
        for attr in self._attrs:
            val = self._attrs[attr]
            val = object_format(val, attr_vars)
            asset.set_attr(attr, val)
        # override attributes by tag
        for label in asset.labels:
            if not isinstance(label, LabelTag):
                label = LabelTag.create_tag(label)
            # admin user tag
            if label.key == self.TAG_ADMIN_USER:
                asset.set_attr('admin_user', label.value)
            # node tag
            elif label.key == self.TAG_NODE:
                asset.set_attr('nodes', [label.value])
            # domain tag
            elif label.key == self.TAG_DOMAIN:
                asset.set_attr('domain', label.value)
        return asset

    def match_tags(self, labels) -> bool:
        """
        Check whether asset labels match selector tags.

        :param labels:
        :return: bool
        """
        for match_tag in self.tags:
            matched = False
            for label in labels:
                if not isinstance(label, LabelTag):
                    label = LabelTag.create_tag(label)
                # find tag in label
                if match_tag.key == label.key:
                    if match_tag.match(label.value) is None:
                        return False
                    else:
                        matched = True
                        break
            # tag not found in label
            if not matched:
                return False
        return True

    def _build_selector(self):
        if self.CONF_TAGS_KEY in self._conf:
            tags = self._conf[self.CONF_TAGS_KEY]
            for tag in tags:
                t = CompiledTag(**tag)
                self._tags.append(t)
        else:
            raise JumpserverError('Tags not found in selector settings!')
        if self.CONF_ATTRS_KEY in self._conf:
            self._attrs = self._conf[self.CONF_ATTRS_KEY]

    @property
    def tags(self):
        """
        Compiled tags.

        :return: list
        """
        return self._tags


class Task:

    def __init__(self, task_settings, produced_by):
        self.task_settings = task_settings
        self.produced_by = produced_by
        self.workflow_cls = None

    def __repr__(self):
        return str(self.task_settings.as_dict())


class BaseProvider:
    """
    Base class for all resources providers.
    """

    def __init__(self, settings, provider_type, provider_name):
        self._settings = settings
        self.provider_type = provider_type
        self.provider_name = provider_name
        self._profile = Profile.load_profile(
            profiles=self.settings.get(CONF_PROFILES_KEY, []),
            profile_name=self.settings.get(CONF_PROFILE_KEY, None)
        )

    @property
    def settings(self):
        """
        Application settings.

        :return: Settings
        """
        return self._settings

    @property
    def profile(self) -> Profile:
        """
        Profile.

        :return: Profile
        """
        return self._profile

    def __repr__(self):
        return '{} <{}>'.format(self.provider_name, self.provider_type)


class AssetsProvider(BaseProvider):
    """
    Abstract class for all resources produce assets.
    """

    TAG_IGNORE = 'jumpserver_ignore'

    def __init__(self, settings, provider_type, provider_name):
        super().__init__(settings, provider_type, provider_name)
        self._selectors = []

    def get_tag_selectors(self):
        """
        Get tag selector list.

        :return: list
        """
        if not self._selectors:
            confs = self.settings.get(CONF_TAG_SELECTORS_KEY, [])
            for conf in confs:
                if 'tags' in conf and 'attrs' in conf:
                    s = TagSelector(conf)
                    self._selectors.append(s)
        return self._selectors

    def list_assets(self, asset_ids=None, **kwargs):
        """
        List assets.

        :param asset_ids: asset id or id list
        :param kwargs:
        :return: asset generator
        """
        pass

    def is_ignored(self, asset):
        """
        Check if asset is ignored.

        :param asset:
        :return: bool
        """
        if not asset.number or not asset.hostname or not asset.ip or not asset.labels:
            return True
        if asset.labels:
            for lb in asset.labels:
                if not isinstance(lb, LabelTag):
                    lb = LabelTag.create_tag(lb)
                if lb.key == self.TAG_IGNORE and lb.value.lower() == 'true':
                    return True
        return False


class TaskProvider(BaseProvider):
    """
    Abstract class for all resources produce task.
    """

    def __init__(self, settings, provider_type, provider_name):
        super().__init__(settings, provider_type, provider_name)
        self.config = {}

    def configure(self, **kwargs):
        """
        Load other configuration.

        :param kwargs:
        :return:
        """
        self.config = kwargs
        return self

    def generate(self):
        """
        Generate tasks.

        :return:
        """
        yield Task(task_settings=self.settings, produced_by=self)

    def finish_task(self, task):
        """
        Called after task finished.

        :param task:
        :return:
        """
        pass

    def fail_task(self, task):
        """
        Called after task failed.

        :param task:
        :return:
        """
        pass


def get_provider(settings, provider_type, provider_name) -> BaseProvider:
    """
    Get provider.

    :param settings:
    :param provider_type: asset or task
    :param provider_name:
    :return:
    """
    if not provider_type:
        raise JumpserverError('Provider type not provided!')
    if not provider_name:
        raise JumpserverError('Provider name not provided!')
    if settings.get(CONF_PROFILE_KEY, None) is None:
        raise JumpserverError('Profile not provided!')
    cls = settings.get('{}.{}.{}'.format(CONF_PROVIDERS_KEY, provider_type, provider_name), None)
    if cls:
        cls = import_string(cls)
        return cls(settings=settings, provider_type=provider_type, provider_name=provider_name)
    else:
        raise JumpserverError('Invalid provider {} {}'.format(provider_type, provider_name))
