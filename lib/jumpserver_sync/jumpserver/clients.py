import logging
import requests
import time
from hsettings import Settings
from diskcache import Cache
from jumpserver_sync.utils import JumpserverAuthError


class RestfulResource:
    """
    Base class for Jumpserver restful resource.
    """

    BASE_URL_KEY = 'jumpserver.base_url'

    base_url = ''
    resource = ''

    def __init__(self, settings=None, **kwargs):
        """

        :param settings:
        :param kwargs:
        """
        self.settings = settings or Settings()
        self.base_url = self.settings.get(self.BASE_URL_KEY) or ''

    def list_resources(self, **kwargs):
        """
        List resources.

        :param kwargs:
        :return: list of resources
        """
        if not self.resource:
            raise ValueError('Invalid resource')
        res = self.send_request(url=self.resource, method='get', **kwargs)
        if res.status_code == 200:
            return res.json()
        else:
            logging.error(res.text)
            return []

    def get_resource(self, res_id, **kwargs):
        """
        Get resources.

        :param res_id: resource id
        :param kwargs: query params
        :return: resource object
        """
        res = self.send_request(url=self.resource.rstrip('/') + '/' + res_id, method='get', **kwargs)
        if res.status_code == 200:
            return res.json()
        else:
            logging.error(res.text)
            return {}

    def post_resource(self, data, **kwargs):
        """
        Create resource.

        :param data: resource data
        :param kwargs:
        :return: resource
        """
        res = self.send_request(url=self.resource, method='post', json=data, **kwargs)
        if res.status_code == 201:
            return res.json()
        else:
            logging.error(res.text)
            return {}

    def put_resource(self, res_id, data, **kwargs):
        """
        Update resource.

        :param res_id: resource id
        :param data: resource data
        :param kwargs:
        :return: resource
        """
        res = self.send_request(url=self.resource.rstrip('/') + '/' + res_id, method='put', json=data, **kwargs)
        if res.status_code == 200:
            return res.json()
        else:
            logging.error(res.text)
            return {}

    def delete_resource(self, res_id, **kwargs):
        """
        Delete resource.

        :param res_id: resource id
        :param kwargs:
        :return: resource
        """
        res = self.send_request(url=self.resource.rstrip('/') + '/' + res_id, method='delete', **kwargs)
        if res.status_code == 204:
            return True
        else:
            logging.error(res.text)
            return False

    def build_request(self, url, method='get', headers=None, params=None, data=None, json=None):
        """
        Build request.

        :param url:
        :param method:
        :param headers:
        :param params:
        :param data:
        :param json:
        :return: dict
        """
        p = {
            'method': method,
            'url': self.base_url.rstrip('/') + '/' + url.strip('/') + '/',
        }
        if headers:
            p['headers'] = headers
        if params:
            p['params'] = params
        if data:
            p['data'] = data
        if json:
            p['json'] = json
        return p

    def send_request(self, url, method='get', headers=None, params=None, data=None, json=None):
        """

        Send request.

        :param url:
        :param method:
        :param headers:
        :param params:
        :param data:
        :param json:
        :return: Response
        :rtype: requests.Response
        """
        p = self.build_request(url=url, method=method, headers=headers, params=params, data=data, json=json)
        return requests.request(**p)


class CachedResource(RestfulResource):

    CACHE_DIR_KEY = 'cache.dir'
    CACHE_TTL_KEY = 'cache.ttl'

    def __init__(self, settings=None, **kwargs):
        super().__init__(settings=settings, **kwargs)
        self._cache_dir = self.settings.get(self.CACHE_DIR_KEY, '.jumpserver_dir')
        self._cache_ttl = self.settings.get(self.CACHE_TTL_KEY, 60)

    def get_cache(self, key, default=None):
        if self._cache_dir:
            with Cache(self._cache_dir) as ref:
                return ref.get(key=key, default=default)
        else:
            return default

    def set_cache(self, key, value):
        if self._cache_dir:
            with Cache(self._cache_dir) as ref:
                ref.set(key=key, value=value, expire=self._cache_ttl)

    def clear_cache(self):
        if self._cache_dir:
            with Cache(self._cache_dir) as ref:
                ref.clear()

    def get_resource_from_cache(self, res_id, **kwargs):
        """
        Get resource from cache by resource id.

        :param res_id:
        :param kwargs:
        :return:
        """
        val = self.get_cache(key=res_id)
        if not val:
            res = self.send_request(url=self.resource + '/' + res_id + '/', method='get', **kwargs)
            if res.status_code == 200:
                val = res.json()
                self.set_cache(key=res_id, value=val)
                return val
            else:
                logging.error(res.text)
                return {}
        return val

    def get_resource(self, res_id, **kwargs):
        return self.get_resource_from_cache(res_id, **kwargs)

    def delete_resource(self, res_id, **kwargs):
        res = super().delete_resource(res_id, **kwargs)
        self.set_cache(key=res_id, value=None)
        return res


class JumpserverClient(CachedResource):

    CACHE_TOKEN_KEY = 'jms_token'
    USER_KEY = 'jumpserver.user'
    PWD_KEY = 'jumpserver.password'
    LOGIN_URL_KEY = 'jumpserver.login_url'

    def get_token(self):
        login_url = self.settings.get(self.LOGIN_URL_KEY)
        if not login_url:
            raise JumpserverAuthError('Invalid login url {}'.format(login_url))
        token = self.get_cache(self.CACHE_TOKEN_KEY)
        if token is None:
            user = self.settings.get(self.USER_KEY)
            pwd = self.settings.get(self.PWD_KEY)
            logging.debug('Login into Jumpserver by user {}'.format(user))
            res = requests.post(url=self.base_url.rstrip('/') + login_url, json={'username': user, 'password': pwd})
            if res.status_code == 200:
                res = res.json()
                token = res['token'] if 'token' in res else None
                if token:
                    self.set_cache(key=self.CACHE_TOKEN_KEY, value=token)
        return token

    def build_request(self, url, method='get', headers=None, params=None, data=None, json=None):
        token = self.get_token()
        if not token:
            raise JumpserverAuthError('Invalid token {}'.format(token))
        h = {'Authorization': 'Bearer ' + token, 'Accept': 'application/json'}
        if headers:
            h.update(headers)
        p = {
            'method': method,
            'url': self.base_url.rstrip('/') + '/' + url.strip('/') + '/',
            'headers': h
        }
        if params:
            p['params'] = params
        if data:
            p['data'] = data
        if json:
            p['json'] = json
        return p


class SystemUser(JumpserverClient):

    PASSED_FLAG = 'TASK [ping] \r\nok:'

    resource = 'api/assets/v1/system-user'

    def push(self, uid, asset_id=None):
        """
        Start task to push system_user to assets.

        :param uid:
        :param asset_id:
        :return:
        """
        if asset_id:
            url = '/'.join([self.resource, uid, 'asset', asset_id, 'push'])
        else:
            url = '/'.join([self.resource, uid, 'push'])
        res = self.send_request(url=url, method='get')
        if res.status_code == 200:
            return res.json()
        else:
            logging.error(res.text)
            return {}

    def test(self, uid, asset_id):
        """
        Start task to test system_user connectivity to assets.

        :param uid:
        :param asset_id:
        :return:
        """
        url = '/'.join([self.resource, uid, 'asset', asset_id, 'test'])
        res = self.send_request(url=url, method='get')
        if res.status_code == 200:
            return res.json()
        else:
            logging.error(res.text)
            return {}

    def is_checked(self, uid, asset_id, timeout=30, interval=3, show_output=False):
        """
        Check whether system_user is connective to assets. This method is synchronized to get result or reach timeout.

        :param uid:
        :param asset_id:
        :param timeout:
        :param interval:
        :param show_output:
        :return:
        """
        task = self.test(uid=uid, asset_id=asset_id)
        task_id = task['task'] if 'task' in task else None
        if task_id:
            celery = Celery(settings=self.settings)
            time.sleep(3)  # sleep some time for job to start
            res = celery.is_task_finished(task_id=task_id, timeout=timeout, interval=interval, show_output=show_output)
            if res and self.PASSED_FLAG in celery.output_log:
                return True
            return False
        else:
            logging.warning('Failed to check system_user {} to asset {} connective'.format(uid, asset_id))
            return False

    def push_checked(self, uid, asset_id, timeout=30, interval=3, show_output=False, max_tries=3, force_push=False):
        """
        Push and check system_user to assets. This method is synchronized to get result and push again if not success.

        :param uid:
        :param asset_id:
        :param timeout:
        :param interval:
        :param show_output:
        :param max_tries:
        :param force_push:
        :return:
        """
        celery = Celery(settings=self.settings)
        tries = 0
        while tries < max_tries:
            if force_push or not self.is_checked(uid=uid, asset_id=asset_id, timeout=timeout, interval=interval, show_output=show_output):
                force_push = False
                task = self.push(uid=uid, asset_id=asset_id)
                task_id = task['task'] if 'task' in task else None
                if task_id:
                    time.sleep(3)  # sleep some time for job to start
                    res = celery.is_task_finished(task_id=task_id, timeout=timeout, interval=interval,
                                                  show_output=show_output)
                    if res and self.is_checked(uid=uid, asset_id=asset_id, timeout=timeout, interval=interval, show_output=show_output):
                        return True
                else:
                    logging.warning('Failed to push system_user {} to asset {}'.format(uid, asset_id))
            else:
                return True
            tries += 1
        logging.error('Push system_user {} failed to asset {} because reach max tries {}'.format(uid, asset_id,  max_tries))
        return False


class AdminUser(JumpserverClient):

    resource = 'api/assets/v1/admin-user'


class Domain(JumpserverClient):

    resource = 'api/assets/v1/domain'


class Label(JumpserverClient):

    resource = 'api/assets/v1/labels'


class Node(JumpserverClient):

    resource = 'api/assets/v1/nodes'

    NODE_KEY_SEP = ':'
    NODE_PATH_SEP = '/'

    def get_node_id(self, node):
        """
        Get node id by node name (e.g. Default/ops/prod).

        :param node:
        :return: node id
        """
        node_list = node.split(self.NODE_PATH_SEP)
        if len(node_list) < 1:
            return None
        nodes = self.list_resources()
        layer = 1
        max_layer = len(node_list)
        parent_key = ''
        for n in node_list:
            for node in nodes:
                # check key
                if parent_key and not node['key'].startswith(parent_key):
                    continue
                keys = node['key'].split(self.NODE_KEY_SEP)
                if len(keys) != layer:
                    continue
                # found and go to next layer
                if node['value'] == n:
                    if layer == max_layer:
                        return node['id']
                    parent_key = node['key']
                    layer += 1
                    break
        return None

    def get_node_full_name(self, node_id):
        """
        Get node full name (e.g. Default/ops/prod) by leaf node id.

        :param node_id:
        :return: full node name
        """
        node = self.get_resource(res_id=node_id)
        if not node:
            return None
        values = [node['value']]
        key = node['key']
        nodes = self.list_resources()
        layer = len(key.split(self.NODE_KEY_SEP))
        for i in range(layer, 1, -1):
            if len(key.split(self.NODE_KEY_SEP)) != i:
                return None
            parent_key = key[:key.rindex(self.NODE_KEY_SEP)]
            for node in nodes:
                if node['key'] == parent_key:
                    key = node['key']
                    values.insert(0, node['value'])
                    break
        return self.NODE_PATH_SEP.join(values)


class Asset(JumpserverClient):

    PASSED_FLAG = 'TASK [ping] \r\nok:'

    resource = 'api/assets/v1/assets'

    def test(self, asset_id):
        """
        Start task to test asset alive.

        :param asset_id:
        :return:
        """
        url = '/'.join([self.resource, asset_id, 'alive'])
        res = self.send_request(url=url, method='get')
        if res.status_code == 200:
            return res.json()
        else:
            logging.error(res.text)
            return {}

    def is_alive(self, asset_id, timeout=30, interval=3, show_output=False):
        """
        Check asset is alive. This method is synchronized to get result.
        :param asset_id:
        :param timeout:
        :param interval:
        :param show_output:
        :return:
        """
        task = self.test(asset_id=asset_id)
        task_id = task['task'] if 'task' in task else None
        if task_id:
            celery = Celery(settings=self.settings)
            time.sleep(3)  # sleep some time for job to start
            res = celery.is_task_finished(task_id=task_id, timeout=timeout, interval=interval, show_output=show_output)
            if res and self.PASSED_FLAG in celery.output_log:
                return True
            return False
        else:
            logging.warning('Failed to check asset {} alive'.format(asset_id))
            return False


class Celery(JumpserverClient):

    FINISH_FLAG = 'Task finished'

    resource = 'api/ops/v1/celery/task'

    output_log = ''

    def log(self, task_id):
        url = '/'.join([self.resource, task_id, 'log'])
        res = self.send_request(url=url, method='get')
        if res.status_code == 200:
            return res.json()
        else:
            logging.error(res.text)
            return {}

    def result(self, task_id):
        url = '/'.join([self.resource, task_id, 'result'])
        res = self.send_request(url=url, method='get')
        if res.status_code == 200:
            return res.json()
        else:
            logging.error(res.text)
            return {}

    def is_task_finished(self, task_id, timeout=30, interval=3, show_output=False):
        """
        Check whether task is finished.

        :param task_id:
        :param timeout: total wait seconds
        :param interval: interval seconds for two test
        :param show_output:
        :return:
        """
        n = 0
        if show_output:
            logging.info('Output for task {}'.format(task_id))
        while n < timeout / interval:
            res = self.log(task_id)
            if 'data' in res:
                self.output_log = res['data']
                if show_output:
                    logging.info(res['data'])
                if self.FINISH_FLAG in res['data'][-20:]:
                    return True
            time.sleep(interval)
            n += 1
        return False
