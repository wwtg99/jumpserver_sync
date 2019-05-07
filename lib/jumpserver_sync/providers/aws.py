import logging
import boto3
from jumpserver_sync.jumpserver import LabelTag
from jumpserver_sync.providers import AssetsProvider
from jumpserver_sync.assets import InstanceAsset


class AwsAssetsProvider(AssetsProvider):
    """
    Get assets resource from AWS.
    """
    CONF_PROVIDER_NAME_KEY = 'aws'

    def __init__(self, settings, profile):
        super().__init__(settings, profile)
        self._session = None

    def get_session(self):
        if not self._session:
            self._session = self.get_aws_session(**self.config)
        return self._session

    def list_assets(self, asset_ids=None, **kwargs):
        limit = kwargs['limit'] if 'limit' in kwargs else None
        ec2 = self.get_session().resource('ec2')
        if asset_ids:
            # provide instances id list
            if not isinstance(asset_ids, list):
                asset_ids = [asset_ids]
            ins_list = ec2.instances.filter(InstanceIds=asset_ids)
        else:
            # list all instances
            ins_list = ec2.instances.all()
        generated = 0
        for instance in ins_list:
            # only running instance
            if instance.state['Name'] != 'running':
                continue
            # create asset
            asset = self.create_asset_from_resource(
                instance=instance,
                account=self.profile,
                region=self.config['region_name'] if 'region_name' in self.config else None
            )
            # check is ignored
            if self.is_ignored(asset):
                logging.info('Ignore instance {} because user add ignore tag!'.format(asset))
                continue
            # select asset
            selected = False
            for selector in self.get_tag_selectors():
                a = selector.select(asset)
                if a is not None:
                    selected = True
                    logging.info('Generate instance asset {}'.format(a))
                    generated += 1
                    yield a
            if not selected:
                logging.info('Instance asset {} did not match any selector, skip'.format(asset))
            if limit and generated >= limit:
                break
        logging.info('Generated {} instances'.format(generated))

    @staticmethod
    def get_aws_session(**kwargs):
        fields = ['profile_name', 'region_name', 'aws_access_key_id', 'aws_secret_access_key']
        conf = {k: kwargs[k] for k in fields if k in kwargs}
        return boto3.Session(**conf)

    @classmethod
    def create_asset_from_resource(cls, instance, account, region):
        tag_name = ''
        if instance.tags:
            for t in instance.tags:
                if t['Key'] == 'Name':
                    tag_name = t['Value']
        hostname = cls.get_hostname(instance.instance_id, tag_name)
        comment = {
            'provider': 'aws',
            'account': account,
            'region': region,
            'instance_type': instance.instance_type,
            'key_name': instance.key_name,
            'image_id': instance.image_id
        }
        obj = {
            'number': instance.instance_id,
            'hostname': hostname,
            'ip': instance.private_ip_address,
            'public_ip': instance.public_ip_address,
            'platform': instance.platform if instance.platform else 'Linux',
            'labels': [LabelTag.create_tag(t) for t in instance.tags],
            'account': account,
            'region': region or instance.placement['AvailabilityZone'][:-1],
        }
        ins = InstanceAsset(**obj)
        ins.put_comment(**comment)
        return ins

    @classmethod
    def get_hostname(cls, instance_id, name):
        name = name.strip()
        if not name:
            name = instance_id
        if not name.endswith(instance_id):
            name += '-' + instance_id
        return name
