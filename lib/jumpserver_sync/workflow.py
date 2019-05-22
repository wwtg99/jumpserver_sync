import logging
import time
from jumpserver_sync.assets import AssetAgent
from jumpserver_sync.providers.base import get_provider, AssetsProvider, TaskProvider
from jumpserver_sync.utils import *


class Workflow:
    """
    Base workflow class.
    """

    def __init__(self, settings):
        self._settings = settings
        self._agent = AssetAgent(settings=settings)

    def run(self):
        """
        Run workflow.

        :return:
        """
        try:
            return self.run_without_exception()
        except JumpserverError as e1:
            logging.error(e1)
        except ImportError as e2:
            logging.error(e2)

    def run_without_exception(self):
        """
        Run workflow and raise exceptions if any.

        :return:
        """
        pass

    @property
    def settings(self):
        return self._settings

    @property
    def agent(self):
        return self._agent


class DumpSettings(Workflow):

    def run_without_exception(self):
        print(self.settings)


class AssetsSync(Workflow):
    """
    Sync assets to Jumpserver by profile and asset id.
    """

    META_PROFILE_KEY = 'account'
    PROVIDER_TYPE = 'asset'

    def run_without_exception(self):
        assets = self.sync_assets()
        # test assets alive
        if self.settings.get(CONF_TEST_ASSET_KEY, False) is True and len(assets) > 0:
            self.check_assets_alive(assets)
        # check system_user connect
        if self.settings.get(CONF_PUSH_CHECK_KEY, False) is True and len(assets) > 0:
            self.check_system_users_connective(assets)

    def sync_assets(self):
        """
        Get and sync assets to Jumpserver.

        :return: assets to sync
        """
        assets = []
        ins = self.settings.get(CONF_INSTANCE_IDS_KEY).split(',') \
            if self.settings.get(CONF_INSTANCE_IDS_KEY, None) else None
        provider = get_provider(
            settings=self.settings,
            provider_type=self.PROVIDER_TYPE,
            provider_name=self.settings.get(CONF_PROVIDER_KEY, None)
        )
        if not isinstance(provider, AssetsProvider):
            raise JumpserverError('Invalid provider {}'.format(provider))
        for a in provider.list_assets(asset_ids=ins):
            a = self.agent.sync_asset(a)
            if a:
                assets.append(a)
                # push system_user to assets
                if self.settings.get(CONF_PUSH_KEY, False) is True:
                    users = self.settings.get(CONF_PUSH_SYSTEM_USERS_KEY, None)
                    if users:
                        logging.info('Push system users {} to asset {}'.format(users, a))
                        self.agent.push_system_users(asset_id=a.id, system_users=users)
                    else:
                        logging.info('Push all system users to asset {}'.format(a))
                        self.agent.push_system_users(asset_id=a.id)
        return assets

    def check_assets_alive(self, assets):
        """
        Check whether assets is alive.

        :param assets:
        :return:
        """
        timeout = self.settings.get(CONF_CHECK_TIMEOUT_KEY)
        interval = self.settings.get(CONF_CHECK_INTERVAL_KEY)
        show_log = self.settings.get(CONF_SHOW_TASK_LOG_KEY)
        logging.info('Check assets alive ...')
        for a in assets:
            res = self.agent.check_assets_alive(asset_id=a.id, timeout=timeout, interval=interval, show_output=show_log)
            if res is True:
                logging.info('Asset {} is alive.'.format(a))
            else:
                logging.error('Asset {} is not alive!'.format(a))

    def check_system_users_connective(self, assets):
        """
        Check whether system users is pushed to assets.

        :param assets:
        :return:
        """
        timeout = self.settings.get(CONF_CHECK_TIMEOUT_KEY)
        interval = self.settings.get(CONF_CHECK_INTERVAL_KEY)
        max_tries = self.settings.get(CONF_CHECK_MAX_TRIES_KEY)
        show_log = self.settings.get(CONF_SHOW_TASK_LOG_KEY)
        force_push = self.settings.get(CONF_FORCE_PUSH_KEY)
        users = self.settings.get(CONF_PUSH_SYSTEM_USERS_KEY, None)
        logging.info('Push system_users to assets ...')
        for a in assets:
            self.agent.push_check_system_users(
                asset_id=a.id,
                system_users=users,
                timeout=timeout,
                interval=interval,
                max_tries=max_tries,
                show_output=show_log,
                force_push=force_push
            )


class AssetsCheckSync(AssetsSync):

    def sync_assets(self):
        timeout = self.settings.get(CONF_CHECK_TIMEOUT_KEY)
        interval = self.settings.get(CONF_CHECK_INTERVAL_KEY)
        show_log = self.settings.get(CONF_SHOW_TASK_LOG_KEY)
        profile = self.settings.get(CONF_PROFILE_KEY, None)
        ins = self.settings.get(CONF_INSTANCE_IDS_KEY).split(',') \
            if self.settings.get(CONF_INSTANCE_IDS_KEY, None) else None
        jms_assets = []
        # get all assets from Jumpserver by profile
        for a in self.agent.list_assets():
            if ins:
                if a.number in ins:
                    jms_assets.append(a)
            else:
                if profile:
                    comment = a.extract_comment()
                    if self.META_PROFILE_KEY in comment and comment[self.META_PROFILE_KEY] == profile:
                        jms_assets.append(a)
                else:
                    jms_assets.append(a)
        for a in jms_assets:
            res = self.agent.check_assets_alive(asset_id=a.id, timeout=timeout, interval=interval, show_output=show_log)
            if res:
                logging.info('Instance {} alive'.format(a))
            else:
                logging.warning('Instance {} not alive'.format(a))


class AssetsCleanSync(AssetsSync):
    """
    Clean assets in Jumpserver.
    If provide --profile option, will only delete assets from specified profile.
    If provide --all option, will delete all assets without check, otherwise only not alive assets will be deleted.
    """

    def sync_assets(self):
        jms_assets = []
        del_assets = []
        profile = self.settings.get(CONF_PROFILE_KEY, None)
        ins = self.settings.get(CONF_INSTANCE_IDS_KEY).split(',') \
            if self.settings.get(CONF_INSTANCE_IDS_KEY, None) else None
        # get all assets from Jumpserver by profile
        for a in self.agent.list_assets():
            if ins:
                if a.number in ins:
                    del_assets.append(a)
            else:
                if profile:
                    comment = a.extract_comment()
                    if comment and self.META_PROFILE_KEY in comment and comment[self.META_PROFILE_KEY] == profile:
                        jms_assets.append(a)
                else:
                    jms_assets.append(a)
        # check assets alive if not specify --all
        if self.settings.get(CONF_INSTANCE_ALL_KEY, False) is False:
            timeout = self.settings.get(CONF_CHECK_TIMEOUT_KEY)
            interval = self.settings.get(CONF_CHECK_INTERVAL_KEY)
            show_log = self.settings.get(CONF_SHOW_TASK_LOG_KEY)
            for a in jms_assets:
                res = self.agent.check_assets_alive(asset_id=a.id, timeout=timeout, interval=interval,
                                                    show_output=show_log)
                if res is False:
                    del_assets.append(a)
        else:
            del_assets.extend(jms_assets)
        # assets to delete in Jumpserver
        del_num = 0
        for a in del_assets:
            res = self.agent.delete_asset(a.id)
            if res:
                del_num += 1
        logging.info('Delete {} assets'.format(del_num))
        return []


class AssetsSmartSync(AssetsSync):
    """
    Sync assets automatically.
    Add assets to Jumpserver if assets provided by provider not exists.
    Delete assets in Jumpserver if assets not exists in provider.
    """

    def sync_assets(self):
        assets = []
        profile = self.settings.get(CONF_PROFILE_KEY, None)
        # get all assets from provider by profile
        provider_assets_number = {}
        provider_assets = []
        provider = get_provider(
            settings=self.settings,
            provider_type=self.PROVIDER_TYPE,
            provider_name=self.settings.get(CONF_PROVIDER_KEY, None)
        )
        if not isinstance(provider, AssetsProvider):
            raise JumpserverError('Invalid provider {}'.format(provider))
        for a in provider.list_assets():
            provider_assets.append(a)
            provider_assets_number[a.number] = len(provider_assets) - 1
        # get all assets from Jumpserver by profile
        jms_assets_number = {}
        jms_assets = []
        for a in self.agent.list_assets():
            jms_assets.append(a)
            comment = a.extract_comment()
            if self.META_PROFILE_KEY in comment and comment[self.META_PROFILE_KEY] == profile:
                jms_assets_number[a.number] = len(jms_assets) - 1
        # assets to add to Jumpserver
        assets_to_add = [provider_assets[i] for n, i in provider_assets_number.items() if n not in jms_assets_number]
        for a in assets_to_add:
            a = self.agent.sync_asset(a)
            if a:
                assets.append(a)
                # push system_user to assets
                if self.settings.get(CONF_PUSH_KEY, False) is True:
                    users = self.settings.get(CONF_PUSH_SYSTEM_USERS_KEY, None)
                    if users:
                        logging.info('Push system users {} to asset {}'.format(users, a))
                        self.agent.push_system_users(asset_id=a.id, system_users=users)
                    else:
                        logging.info('Push all system users to asset {}'.format(a))
                        self.agent.push_system_users(asset_id=a.id)
        logging.info('Sync {} assets'.format(len(assets)))
        # assets to delete in Jumpserver
        del_num = 0
        assets_to_del = [jms_assets[i] for n, i in jms_assets_number.items() if n not in provider_assets_number]
        for a in assets_to_del:
            res = self.agent.delete_asset(a.id)
            if res:
                del_num += 1
        logging.info('Delete {} assets'.format(del_num))
        return assets


class AssetsListenSync(AssetsSync):
    """
    Listening on task providers and call AssetsSync workflow to handle task.
    """

    PROVIDER_TYPE = 'task'

    def run(self):
        listen_provider = self.settings.get(CONF_LISTEN_PROVIDER_KEY, None)
        listen_inv = self.settings.get(CONF_LISTEN_INTERVAL_KEY, None)
        while True:
            try:
                for provider in self.get_task_provider(provider=listen_provider):
                    for task in provider.generate():
                        if self.process_task(task=task):
                            provider.finish_task(task=task)
                        else:
                            provider.fail_task(task=task)
                    if listen_inv:
                        time.sleep(listen_inv)
            except JumpserverError as e1:
                logging.error(e1)
                if listen_inv:
                    time.sleep(listen_inv)
            except ImportError as e2:
                logging.error(e2)

    def process_task(self, task):
        try:
            workflow_cls = import_string(task.workflow_cls)
            workflow = workflow_cls(settings=task.task_settings)
            workflow.run()
            return True
        except Exception as e:
            return False

    def get_task_provider(self, provider=None):
        if provider:
            conf = self.settings.get('{}.{}'.format(CONF_LISTEN_CONF_KEY, provider), None)
            if not conf:
                raise JumpserverError('Invalid listening provider {}'.format(provider))
            if 'type' not in conf:
                raise JumpserverError('Invalid type in listening provider {}'.format(provider))
            name = conf['type']
            if 'profile' not in conf:
                raise JumpserverError('Invalid profile in listening provider {}'.format(provider))
            profile = conf['profile']
            settings = self.settings.clone()
            settings.set(CONF_PROFILE_KEY, profile)
            p = get_provider(settings=settings, provider_type=self.PROVIDER_TYPE, provider_name=name)
            if isinstance(p, TaskProvider):
                p.configure(**conf)
                yield p
        else:
            providers = self.settings.get(CONF_LISTEN_CONF_KEY, [])
            for provider in providers:
                yield self.get_task_provider(provider=provider)
