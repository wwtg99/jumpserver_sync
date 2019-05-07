from itertools import product
from jumpserver_sync.utils import JumpserverError
from jumpserver_sync.jumpserver.clients import AdminUser, Domain, Label, Node, Asset


class LabelTag:
    """
    Present for asset label.
    """
    def __init__(self, key, value):
        self.key = key
        self.value = value

    @classmethod
    def create_tag(cls, obj):
        if 'key' in obj:
            key = obj['key']
        elif 'Key' in obj:
            key = obj['Key']
        elif 'name' in obj:
            key = obj['name']
        else:
            raise JumpserverError('Could not transform object {} to LabelTag.'.format(obj))
        if 'value' in obj:
            value = obj['value']
        elif 'Value' in obj:
            value = obj['Value']
        else:
            raise JumpserverError('Could not transform object {} to LabelTag'.format(obj))
        return LabelTag(key=key, value=value)

    def __eq__(self, other):
        if isinstance(other, LabelTag):
            return self.key == other.key and self.value == other.value
        return False

    def __str__(self):
        return '{}:{}'.format(self.key, self.value)


class JumpserverManager:

    def __init__(self, settings):
        self._settings = settings
        self._list_cache = {}

    def update_asset(self, asset):
        """
        Update asset related resource ids from Jumpserver.

        :param asset:
        :return: asset
        """
        if asset.admin_user and asset.admin_user_id is None:
            asset.set_attr('admin_user_id', self.get_admin_user_id(asset.admin_user))
        if asset.domain and asset.domain_id is None:
            asset.set_attr('domain_id', self.get_domain_id(asset.domain))
        if asset.labels and not asset.label_ids:
            asset.set_attr('label_ids', self.get_label_ids(asset.labels))
        if asset.nodes and not asset.node_ids:
            asset.set_attr('node_ids', self.get_node_ids(asset.nodes))
        return asset

    # def add_to_jumpserver(self, asset):
    #     """
    #     Add asset or asset list to Jumpserver.
    #
    #     :param asset:
    #     :return:
    #     """
    #     cli = Asset(settings=self.settings)
    #     if isinstance(asset, InstanceAsset):
    #         return cli.add_asset(asset)
    #     else:
    #         return cli.add_assets(asset)

    def parse_from_jumpserver(self, asset_obj):
        pass


    def get_admin_user_id(self, admin_user):
        """
        Get admin_user id by name.

        :param admin_user: admin_user name
        :return: admin_user id
        """
        if not admin_user:
            return None
        key = 'admin_user'
        if key in self._list_cache:
            res = self._list_cache[key]
        else:
            client = AdminUser(settings=self.settings)
            res = client.list_resources()
        for r in res:
            if r['name'] == admin_user:
                return r['id']
        return None

    def get_domain_id(self, domain):
        """
        Get domain id by name.

        :param domain: domain name
        :return: domain id
        """
        if not domain:
            return None
        key = 'domain'
        if key in self._list_cache:
            res = self._list_cache[key]
        else:
            client = Domain(settings=self.settings)
            res = client.list_resources()
        for r in res:
            if r['name'] == domain:
                return r['id']
        return None

    def get_label_ids(self, labels):
        """
        Get label ids by labels.

        :param labels: label list
        :return: label id list
        """
        if not labels:
            return []
        key = 'labels'
        if key in self._list_cache:
            res = self._list_cache[key]
        else:
            client = Label(settings=self.settings)
            res = client.list_resources()
        label_ids = []
        for r, l in product(res, labels):
            if r['name'] == l['Key'] and r['value'] == l['Value']:
                label_ids.append(r['id'])
        return label_ids

    def get_node_ids(self, nodes):
        """
        Get node ids by node name.

        :param nodes: node name list
        :return: node id list
        """
        if not nodes:
            return []
        cli = Node(settings=self.settings)
        node_ids = []
        for node in nodes:
            nid = cli.get_node_id(node)
            if nid:
                node_ids.append(nid)
        return node_ids

    def get_admin_user_name(self, admin_user_id):
        """
        Get admin_user name by id.

        :param admin_user_id: admin_user id
        :return: admin_user name
        """
        if not admin_user_id:
            return None
        key = 'admin_user_name'
        if key in self._list_cache:
            res = self._list_cache[key]
        else:
            client = AdminUser(settings=self.settings)
            res = client.get_resource(res_id=admin_user_id)
        return res

    def get_domain_name(self, domain_id):
        """
        Get domain name by id.

        :param domain_id: domain id
        :return: domain name
        """
        if not domain_id:
            return None
        key = 'domain_name'
        if key in self._list_cache:
            res = self._list_cache[key]
        else:
            client = Domain(settings=self.settings)
            res = client.get_resource(res_id=domain_id)
        return res

    def get_labels_name(self, label_ids):
        """
        Get label name by id.

        :param label_ids: label id list
        :return: label name list
        """
        if not label_ids:
            return []
        key = 'label_names'
        if key in self._list_cache:
            res = self._list_cache[key]
        else:
            client = Label(settings=self.settings)
            res = client.get_resource(res_id=domain_id)
        return res

    @property
    def settings(self):
        return self._settings
