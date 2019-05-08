import re
from hsettings import NOTSET
from jumpserver_sync.utils import JumpserverError, object_format, import_string
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


class AssetsProvider:
    """
    Abstract class for all resources produce assets.
    """

    CONF_PREFIX_KEY = 'providers'
    CONF_PROVIDER_NAME_KEY = ''
    CONF_KEY = 'tag_selectors'

    TAG_IGNORE = 'jumpserver_ignore'

    def __init__(self, settings, profile):
        self._settings = settings
        self._profile = profile
        self._selectors = []
        p = self.settings.get('{}.{}.{}'.format(self.CONF_PREFIX_KEY, self.CONF_PROVIDER_NAME_KEY, profile), None)
        if not p:
            raise JumpserverError('Invalid {} account {}'.format(self.CONF_PROVIDER_NAME_KEY, profile))
        self._config = p
        self._selectors = []

    def get_tag_selectors(self):
        """
        Get tag selector list.

        :return: list
        """
        if not self._selectors:
            confs = self.settings.get(self.CONF_KEY, [])
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
            for l in asset.labels:
                if not isinstance(l, LabelTag):
                    l = LabelTag.create_tag(l)
                if l.key == self.TAG_IGNORE and l.value.lower() == 'true':
                    return True
        return False

    @property
    def settings(self):
        """
        Application settings.

        :return: Settings
        """
        return self._settings

    @property
    def profile(self):
        """
        Account profile.

        :return: str
        """
        return self._profile

    @property
    def config(self):
        """
        Provider configuration.

        :return: dict
        """
        return self._config


KEY_PROVIDER_CLS = 'provider_cls'


def get_provider(name, settings, profile) -> AssetsProvider:
    """
    Get provider.

    :param name:
    :param settings:
    :param profile:
    :return:
    """
    if not name:
        raise JumpserverError('Provider name not provided!')
    if not profile:
        raise JumpserverError('Profile not provided!')
    cls = settings.get('{}.{}'.format(KEY_PROVIDER_CLS, name))
    if cls and cls != NOTSET:
        cls = import_string(cls)
        return cls(settings=settings, profile=profile)
    else:
        raise JumpserverError('Invalid provider {}'.format(name))
