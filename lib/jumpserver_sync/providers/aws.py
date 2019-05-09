import logging
import json
import boto3
from jumpserver_sync.jumpserver import LabelTag
from jumpserver_sync.providers.base import AssetsProvider, TaskProvider, Task
from jumpserver_sync.assets import InstanceAsset
from jumpserver_sync.utils import CONF_INSTANCE_IDS_KEY


def get_aws_session(**kwargs):
    fields = ['profile_name', 'region_name', 'aws_access_key_id', 'aws_secret_access_key']
    conf = {k: kwargs[k] for k in fields if k in kwargs}
    return boto3.Session(**conf)


class AwsAssetsProvider(AssetsProvider):
    """
    Get assets resource from AWS.
    """

    def __init__(self, settings, provider_type, provider_name):
        super().__init__(settings, provider_type, provider_name)
        self._session = None
        self._region = self.profile.config['region_name'] if 'region_name' in self.profile.config else None

    def list_assets(self, asset_ids=None, **kwargs):
        limit = kwargs['limit'] if 'limit' in kwargs else None
        ec2 = self.session.resource('ec2')
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
                account=self.profile.profile_name,
                region=self._region
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

    @property
    def session(self):
        if not self._session:
            self._session = get_aws_session(**self.profile.config)
        return self._session


class AwsSqsTaskProvider(TaskProvider):
    """
    Generate task from AWS SQS.
    """

    CONF_RECEIPT_KEY = 'sqs.receipt_handle'

    def __init__(self, settings, provider_type, provider_name):
        super().__init__(settings, provider_type, provider_name)
        self._session = None
        self._sqs_client = None
        self.queue_url = ''
        self.max_size = 1

    def configure(self, **kwargs):
        self.queue_url = kwargs['queue'] if 'queue' in kwargs else ''
        self.max_size = kwargs['max_size'] if 'max_size' in kwargs else 1

    def generate(self):
        msg = self.sqs_client.receive_message(QueueUrl=self.queue_url, MaxNumberOfMessages=self.max_size)
        if 'Messages' in msg:
            logging.info('Receive {} messages from SQS'.format(len(msg['Messages'])))
            for m in msg['Messages']:
                s = self.extract_message(m)
                if s:
                    yield Task(task_settings=s, produced_by=self)
        else:
            logging.info('No messages received')
            return None

    def finish_task(self, task):
        receipt = task.task_settings.get(self.CONF_RECEIPT_KEY, None)
        if receipt:
            return self.delete_message(queue_url=self.queue_url, receipt=receipt)

    def fail_task(self, task):
        logging.error('Process failed for task {}'.format(task))

    def extract_message(self, message):
        """
        Extract settings from message.

        :param message: message
        :return: settings or None
        """
        if 'Body' in message and 'ReceiptHandle' in message:
            settings = self.settings.clone()
            body = message['Body']
            settings.set(self.CONF_RECEIPT_KEY, message['ReceiptHandle'])
            if body.startswith('i-'):
                settings.set(CONF_INSTANCE_IDS_KEY, body.strip())
            else:
                body = json.loads(body)
                if isinstance(body, str):
                    settings.set(CONF_INSTANCE_IDS_KEY, body.strip())
                elif isinstance(body, dict):
                    conf = body
                    settings.merge(conf)
            return settings
        return None

    def send_message(self, queue_url: str, message):
        """
        Send message to queue.

        :param queue_url: queue url
        :param message: message body
        :return:
        """
        return self.sqs_client.send_message(QueueUrl=queue_url, MessageBody=message)

    def delete_message(self, queue_url: str, receipt):
        """
        Delete message.

        :param queue_url: queue url
        :param receipt: message receipt
        :return:
        """
        return self.sqs_client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)

    @property
    def session(self):
        if not self._session:
            self._session = get_aws_session(**self.profile.config)
        return self._session

    @property
    def sqs_client(self):
        if not self._sqs_client:
            self._sqs_client = self.session.client('sqs')
        return self._sqs_client
