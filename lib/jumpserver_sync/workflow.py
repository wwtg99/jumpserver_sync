import logging
from jumpserver_sync.assets import AssetAgent
from jumpserver_sync.providers import get_provider
from jumpserver_sync.utils import JumpserverError


class Workflow:

    CONF_PROVIDER_KEY = 'app.provider'
    CONF_PROFILE_KEY = 'app.profile'

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

    def get_provider(self):
        """
        Get asset provider.

        :return: provider
        """
        return get_provider(
            name=self.settings.get(self.CONF_PROVIDER_KEY),
            settings=self.settings,
            profile=self.settings.get(self.CONF_PROFILE_KEY)
        )

    @property
    def settings(self):
        return self._settings

    @property
    def agent(self):
        return self._agent


class AssetsSync(Workflow):

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

    def run_without_exception(self):
        assets = self.sync_assets()
        # test assets alive
        if self.settings.get(self.CONF_TEST_ASSET_KEY, False) is True:
            self.check_assets_alive(assets)
        # check system_user connect
        if self.settings.get(self.CONF_PUSH_CHECK_KEY, False) is True:
            self.check_system_users_connective(assets)

    def sync_assets(self):
        assets = []
        ins = self.settings.get(self.CONF_INSTANCE_IDS_KEY).split(',')
        for a in self.get_provider().list_assets(asset_ids=ins):
            a = self.agent.sync_asset(a)
            assets.append(a)
            # push system_user to assets
            if self.settings.get(self.CONF_PUSH_KEY, False) is True:
                users = self.settings.get(self.CONF_PUSH_SYSTEM_USERS_KEY, None)
                if users:
                    logging.info('Push system users {} to asset {}'.format(users, a))
                    self.agent.push_system_users(asset_id=a.id, system_users=users)
                else:
                    logging.info('Push all system users to asset {}'.format(a))
                    self.agent.push_system_users(asset_id=a.id)
        return assets

    def check_assets_alive(self, assets):
        timeout = self.settings.get(self.CONF_CHECK_TIMEOUT_KEY)
        interval = self.settings.get(self.CONF_CHECK_INTERVAL_KEY)
        show_log = self.settings.get(self.CONF_SHOW_TASK_LOG_KEY)
        logging.info('Check assets alive ...')
        for a in assets:
            res = self.agent.check_assets_alive(asset_id=a.id, timeout=timeout, interval=interval, show_output=show_log)
            if res is True:
                logging.info('Asset {} is alive.'.format(a))
            else:
                logging.error('Asset {} is not alive!'.format(a))

    def check_system_users_connective(self, assets):
        timeout = self.settings.get(self.CONF_CHECK_TIMEOUT_KEY)
        interval = self.settings.get(self.CONF_CHECK_INTERVAL_KEY)
        max_tries = self.settings.get(self.CONF_CHECK_MAX_TRIES_KEY)
        show_log = self.settings.get(self.CONF_SHOW_TASK_LOG_KEY)
        force_push = self.settings.get(self.CONF_FORCE_PUSH_KEY)
        users = self.settings.get(self.CONF_PUSH_SYSTEM_USERS_KEY, None)
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
