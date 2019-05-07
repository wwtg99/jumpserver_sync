import logging
from jumpserver_sync.utils import JumpserverError
from jumpserver_sync.jumpserver import LabelTag
from jumpserver_sync.jumpserver.clients import AdminUser, Domain, Label, Node, Asset, SystemUser


class InstanceAsset:
    """
    Describe instance asset in Jumpserver.
    """

    COMMENT_SEP = ';'
    COMMENT_PAIR_SEP = '='

    default_attrs = {
        'id': None,
        'number': None,
        'hostname': None,
        'protocol': 'ssh',
        'ip': None,
        'public_ip': None,
        'port': 22,
        'platform': 'Linux',
        'comment': None,
        'admin_user': None,
        'admin_user_id': None,
        'domain': None,
        'domain_id': None,
        'labels': [],
        'label_ids': [],
        'nodes': [],
        'node_ids': [],
        'account': None,
        'region': None
    }

    def __init__(self, **kwargs):
        self._attrs = dict(self.default_attrs)
        self._attrs.update(kwargs)

    @classmethod
    def from_jumpserver(cls, asset):
        if 'id' not in asset:
            raise JumpserverError('No id found in Jumpserver asset {}'.format(asset))
        fields = ['id', 'number', 'hostname', 'protocol', 'ip', 'public_ip', 'port', 'platform', 'comment']
        attrs = {f: asset[f] for f in fields if f in asset}
        if 'admin_user' in asset:
            attrs['admin_user_id'] = asset['admin_user']
        if 'domain' in asset:
            attrs['domain_id'] = asset['domain']
        if 'labels' in asset:
            attrs['label_ids'] = asset['labels']
        if 'nodes' in asset:
            attrs['node_ids'] = asset['nodes']
        return InstanceAsset(**attrs)

    def set_attr(self, name, value):
        self._attrs[name] = value

    def put_comment(self, **kwargs):
        """
        Put meta data into comment.

        :param kwargs:
        :return:
        """
        pairs = ['{}{}{}'.format(k, self.COMMENT_PAIR_SEP, v) for k, v in kwargs.items()]
        c = self.COMMENT_SEP.join(pairs)
        self._attrs['comment'] = c
        return c

    def extract_comment(self):
        """
        Extract meta data from comment.

        :return: meta data dict
        """
        if self._attrs['comment']:
            try:
                pairs = self._attrs['comment'].split(self.COMMENT_SEP)
                kv = {k.split(self.COMMENT_PAIR_SEP)[0]: k.split(self.COMMENT_PAIR_SEP)[1] for k in pairs}
                return kv
            except Exception as e:
                logging.warning('Invalid structure of comment {} for asset {}'.format(self._attrs['comment'], self))
        return None

    def to_dict(self):
        return {k: v for k, v in self._attrs.items() if v is not None}

    def clone(self):
        return InstanceAsset(**self._attrs)

    def __str__(self):
        return self.hostname + ': ' + self.ip

    def __eq__(self, o: object) -> bool:
        if isinstance(o, InstanceAsset):
            if self.id is not None and self.id == o.id:
                return True
            if self.number == o.number:
                return True
        return False

    def __getattr__(self, item):
        if item in self._attrs:
            return self._attrs[item]
        return None


class AssetAgent:

    _check_fields = ['admin_user', 'admin_user_id', 'domain', 'domain_id', 'labels', 'label_ids', 'nodes', 'node_ids']

    _attr_maps = {
        'admin_user_id': 'admin_user',
        'domain_id': 'domain',
        'label_ids': 'labels',
        'node_ids': 'nodes'
    }

    def __init__(self, settings):
        self._settings = settings
        self._client_cache = {}
        self._list_cache = {}

    def is_asset_linked(self, asset):
        """
        Check whether asset is linked to Jumpserver.

        :param asset:
        :return: bool
        """
        for f in self._check_fields:
            if not getattr(asset, f):
                return False
        return True

    def link_asset(self, asset):
        """
        Link asset data to Jumpserver.

        :param asset:
        :return: asset
        """
        if asset.admin_user and asset.admin_user_id is None:
            asset.set_attr('admin_user_id', self.get_admin_user_id(asset.admin_user))
        elif asset.admin_user is None and asset.admin_user_id:
            asset.set_attr('admin_user', asset.get_admin_user_name(asset.admin_user_id))
        if asset.domain and asset.domain_id is None:
            asset.set_attr('domain_id', self.get_domain_id(asset.domain))
        elif asset.domain is None and asset.domain_id:
            asset.set_attr('domain', self.get_domain_name(asset.domain_id))
        if asset.labels and not asset.label_ids:
            ids = []
            for l in asset.labels:
                lid = self.get_label_id(l)
                if lid is None:
                    logging.warning('Label {} not found'.format(l))
                else:
                    ids.append(lid)
            asset.set_attr('label_ids', ids)
        elif not asset.labels and asset.label_ids:
            lbs = []
            for lid in asset.label_ids:
                lb = self.get_label_name(lid)
                if lb is None:
                    logging.warning('Label id {} not found'.format(lid))
                else:
                    lbs.append(lb)
            asset.set_attr('labels', lbs)
        if asset.nodes and not asset.node_ids:
            ids = []
            for n in asset.nodes:
                nid = self.get_node_id(n)
                if nid is None:
                    logging.warning('Node {} not found'.format(n))
                else:
                    ids.append(nid)
            asset.set_attr('node_ids', ids)
        elif not asset.nodes and asset.node_ids:
            nds = []
            for nid in asset.nodes:
                nd = self.get_node_path(nid)
                if nd is None:
                    logging.warning('Node id {} not found'.format(nid))
                else:
                    nds.append(nd)
            asset.set_attr('nodes', nds)
        return asset

    def sync_asset(self, asset):
        """
        Sync asset to Jumpserver, create if not exists or update if exists.

        :param asset:
        :return: asset
        """
        aid = self.get_asset_id(asset)
        if aid:
            res = self.update_asset(asset_id=aid, asset=asset)
        else:
            res = self.create_asset(asset=asset)
        return res

    def create_asset(self, asset):
        """
        Create Jumpserver asset.

        :param asset:
        :return: asset
        """
        if not self.is_asset_linked(asset):
            asset = self.link_asset(asset)
        d = asset.to_dict()
        for k, v in self._attr_maps.items():
            if k in d:
                d[v] = d[k]
                del d[k]
        logging.info('Create asset {}'.format(asset))
        client = self.get_client(key='asset', client_cls=Asset)
        res = client.post_resource(data=d)
        return self.from_jumpserver(res)

    def update_asset(self, asset_id, asset):
        """
        Update Jumpserver asset.

        :param asset_id:
        :param asset:
        :return: asset
        """
        if not self.is_asset_linked(asset):
            asset = self.link_asset(asset)
        d = asset.to_dict()
        for k, v in self._attr_maps.items():
            if k in d:
                d[v] = d[k]
                del d[k]
        logging.info('Update asset {}'.format(asset))
        client = self.get_client(key='asset', client_cls=Asset)
        res = client.put_resource(res_id=asset_id, data=d)
        return self.from_jumpserver(res)

    def delete_asset(self, asset_id):
        """
        Delete Jumpserver asset.

        :param asset_id:
        :return:
        """
        logging.info('Delete asset {}'.format(asset_id))
        client = self.get_client(key='asset', client_cls=Asset)
        return client.delete_resource(res_id=asset_id)

    def check_assets_alive(self, asset_id, timeout=30, interval=3, show_output=False):
        """
        Check asset is alive or not.
        This method is synchronized to get result.

        :param asset_id:
        :param timeout:
        :param interval:
        :param show_output:
        :return:
        """
        cli = self.get_client(key='asset', client_cls=Asset)
        return cli.is_alive(asset_id=asset_id, timeout=timeout, interval=interval, show_output=show_output)

    def push_system_users(self, asset_id, system_users=None):
        """
        Push system_user to asset async.

        :param asset_id:
        :param system_users:
        :return:
        """
        cli = self.get_client('system_user', SystemUser)
        if system_users:
            # push specified system_users
            if isinstance(system_users, str):
                system_users = system_users.split(',')
            ids = []
            for u in system_users:
                ids.append(self.get_system_user_id(u))
            system_users = ids
        else:
            # push all exists system_users
            system_users = [u['id'] for u in cli.list_resources()]
        task_ids = []
        for uid in system_users:
            res = cli.push(uid=uid, asset_id=asset_id)
            if 'task' in res:
                task_ids.append(res['task'])
        return task_ids

    def push_check_system_users(self, asset_id, system_users=None, timeout=30, interval=3, show_output=False,
                                max_tries=3, force_push=False):
        """
        Push and check specified system_user or all to assets.
        This method is synchronized to get result and push again if not success.

        :param asset_id:
        :param system_users:
        :param timeout:
        :param interval:
        :param show_output:
        :param max_tries:
        :param force_push:
        :return:
        """
        cli = self.get_client('system_user', SystemUser)
        if system_users:
            # push specified system_users
            if isinstance(system_users, str):
                system_users = system_users.split(',')
            ids = []
            for u in system_users:
                ids.append(self.get_system_user_id(u))
            system_users = ids
        else:
            # push all exists system_users
            system_users = [u['id'] for u in cli.list_resources()]
        for uid in system_users:
            res = cli.push_checked(
                uid=uid,
                asset_id=asset_id,
                timeout=timeout,
                interval=interval,
                show_output=show_output,
                max_tries=max_tries,
                force_push=force_push
            )
            uname = self.get_system_user_name(uid)
            if res:
                logging.info('Successfully pushed system user {} to asset {}'.format(uname, asset_id))
            else:
                logging.error('Failed to push {} to asset {}'.format(uname, asset_id))

    def get_asset_id(self, asset):
        """
        Get asset id.

        :param asset:
        :return: asset id
        """
        client = self.get_client(key='asset', client_cls=Asset)
        if asset.id:
            res = client.get_resource(res_id=asset.id)
            return res['id'] if 'id' in res else None
        else:
            # get id by hostname
            hostname = asset.hostname
            res = client.list_resources(params={'hostname': hostname})
            if len(res) > 0:
                return res[0]['id'] if 'id' in res[0] else None
            else:
                return None

    def from_jumpserver(self, asset):
        """
        Get InstanceAsset from Jumpserver asset.

        :param asset:
        :return: asset
        """
        if not asset:
            return None
        for k, v in self._attr_maps.items():
            asset[k] = asset[v]
            del asset[v]
        return InstanceAsset(**asset)

    def get_client(self, key, client_cls):
        """
        Get Jumpserver client by key.

        :param key:
        :param client_cls:
        :return: client
        """
        if key in self._client_cache:
            client = self._client_cache[key]
        else:
            client = client_cls(self.settings)
            self._client_cache[key] = client
        return client

    def get_system_user_id(self, name):
        if not name:
            return None
        res = self._get_resource_list(key='system_user', client_cls=SystemUser)
        for r in res:
            if r['name'] == name:
                return r['id']
        return None

    def get_admin_user_id(self, name):
        if not name:
            return None
        res = self._get_resource_list(key='admin_user', client_cls=AdminUser)
        for r in res:
            if r['name'] == name:
                return r['id']
        return None

    def get_domain_id(self, name):
        if not name:
            return None
        res = self._get_resource_list(key='domain', client_cls=Domain)
        for r in res:
            if r['name'] == name:
                return r['id']
        return None

    def get_label_id(self, label):
        if not label:
            return None
        if not isinstance(label, LabelTag):
            label = LabelTag.create_tag(label)
        res = self._get_resource_list(key='label', client_cls=Label)
        for r in res:
            rlabel = LabelTag.create_tag(r)
            if rlabel == label:
                return r['id']
        return None

    def get_node_id(self, name):
        if not name:
            return None
        client = self.get_client(key='node', client_cls=Node)
        nid = client.get_node_id(name)
        return nid

    def get_system_user_name(self, res_id):
        res = self._get_resource_by_id(key='system_user', res_id=res_id, client_cls=SystemUser)
        return res['name'] if res and 'name' in res else None

    def get_admin_user_name(self, res_id):
        res = self._get_resource_by_id(key='admin_user', res_id=res_id, client_cls=AdminUser)
        return res['name'] if res and 'name' in res else None

    def get_domain_name(self, res_id):
        res = self._get_resource_by_id(key='domain', res_id=res_id, client_cls=Domain)
        return res['name'] if res and 'name' in res else None

    def get_label_name(self, res_id):
        res = self._get_resource_by_id(key='label', res_id=res_id, client_cls=Label)
        return LabelTag.create_tag(res)

    def get_node_path(self, res_id):
        if not res_id:
            return None
        client = self.get_client(key='node', client_cls=Node)
        n = client.get_node_full_name(res_id)
        return n

    def _get_resource_list(self, key, client_cls):
        """
        Get resource list.

        :param key: resource key
        :param client_cls: client class
        :return: resource list
        """
        if not key:
            return []
        if key in self._list_cache:
            res = self._list_cache[key]
        else:
            client = self.get_client(key=key, client_cls=client_cls)
            res = client.list_resources()
            self._list_cache[key] = res
        return res

    def _get_resource_by_id(self, key, res_id, client_cls):
        """
        Get resource by id.

        :param key: resource key
        :param res_id: resource id
        :param client_cls: client class
        :return: resource
        """
        if not key:
            return None
        if not res_id:
            return None
        client = self.get_client(key=key, client_cls=client_cls)
        res = client.get_resource(res_id=res_id)
        return res

    @property
    def settings(self):
        return self._settings
