import os
import sys
import random


sys.path.insert(0, os.path.abspath('lib'))

import pytest
from hsettings import Settings
from jumpserver_sync.jumpserver import LabelTag
from jumpserver_sync.jumpserver.clients import JumpserverClient, AdminUser, Domain, Node, Asset, Label
from jumpserver_sync.assets import InstanceAsset, AssetAgent
from jumpserver_sync.providers import get_provider, AssetsProvider, CompiledTag, TagSelector


class TestAsset:

    def test_instance_asset(self):
        d = {'number': 'i-123456', 'hostname': 'test', 'ip': '127.0.0.1'}
        asset = InstanceAsset(**d)
        assert asset.number == d['number']
        assert asset.hostname == d['hostname']
        assert asset.ip == d['ip']
        asset.set_attr('hostname', 'test2')
        assert asset.hostname == 'test2'
        asset2 = asset.clone()
        assert asset == asset2
        assert asset is not asset2
        assert asset.to_dict() == asset2.to_dict()
        asset2.set_attr('number', 'i-111111')
        assert asset != asset2
        pairs = {'provider': 'aws', 'account': 'account1', 'region': 'region1'}
        c = asset.put_comment(**pairs)
        assert c == asset.comment
        assert c == 'provider=aws;account=account1;region=region1'
        assert asset.extract_comment() == pairs


class TestProvider:

    @pytest.fixture(scope='module')
    def settings(self):
        return Settings({
            'jumpserver': {
                'base_url': 'http://test.jumpserver.com',
                'user': 'admin',
                'password': 'admin',
                'login_url': '/api/users/v1/auth/'
            },
            'providers': {
                'aws': {
                    'us0066': {
                        'region_name': 'us-east-1',
                        'profile_name': 'us-east-1_0066'
                    }
                }
            },
            'cache': {
                'dir': '.jumpserver_cache',
                'ttl': 60
            },
            'log': {
                'log_level': 'INFO',
                'log_formatter': '[%(levelname)s] %(asctime)s : %(message)s',
            },
            'provider_cls': {
                'aws': 'jumpserver_sync.providers.aws.AwsAssetsProvider'
            },
            'tag_selectors': [
                {
                    'tags': [
                        {'key': 'Name', 'value': 'ecs-cluster-'},
                    ],
                    'attrs': {
                        'domain': 'test_domain',
                        'nodes': ['test_node'],
                        'admin_user': 'test_admin_user'
                    }
                }
            ]
        })

    def test_compiled_tag(self):
        kv = {'key': 'Name', 'value': 'test'}
        tag = CompiledTag(**kv)
        assert tag.key == 'Name'
        assert tag.value == 'test'
        tag = CompiledTag(**kv)
        assert tag.match('k') is None
        assert tag.match('k1') is None
        assert tag.match('test') is not None
        assert tag.match('t') is None
        assert tag.match('te') is None
        assert tag.match('test1') is not None
        kv = {'key': 'Name', 'value': 'k\\d{1,2}$'}
        tag = CompiledTag(**kv)
        assert tag.match('k') is None
        assert tag.match('k1') is not None
        assert tag.match('k11') is not None
        assert tag.match('k111') is None
        assert tag.match('d') is None
        assert tag.match('d1') is None

    def test_tag_selector(self):
        conf1 = {
            'tags': [
                {'key': 'Name', 'value': 'test1'},
            ],
            'attrs': {
                'domain': 'test_domain1',
                'nodes': ['test_node1'],
                'admin_user': 'test_admin_user1'
            }
        }
        conf2 = {
            'tags': [
                {'key': 'Name', 'value': 'test2'},
            ],
            'attrs': {
                'domain': 'test_{number}',
                'nodes': ['test_{hostname}'],
                'admin_user': 'test_{ip}'
            }
        }
        selector = TagSelector(conf1)
        # select no number
        d = {
            'hostname': 'test1',
            'ip': '127.0.0.1',
            'labels': [
                {'Key': 'Name', 'Value': 'test1'}
            ]
        }
        asset = InstanceAsset(**d)
        sel_asset = selector.select(asset)
        assert sel_asset is None
        # match labels
        d = {
            'number': 'i-111',
            'hostname': 'test1',
            'ip': '127.0.0.1',
            'labels': [
                {'Key': 'Name', 'Value': 'test1'}
            ]
        }
        asset = InstanceAsset(**d)
        sel_asset = selector.select(asset)
        assert sel_asset is not None
        assert sel_asset.domain == 'test_domain1'
        assert sel_asset.nodes == ['test_node1']
        assert sel_asset.admin_user == 'test_admin_user1'
        # not match labels
        d = {
            'number': 'i-111',
            'hostname': 'test1',
            'ip': '127.0.0.1',
            'labels': [
                LabelTag.create_tag({'Key': 'Name', 'Value': 'test2'})
            ]
        }
        asset = InstanceAsset(**d)
        sel_asset = selector.select(asset)
        assert sel_asset is None
        # replace variables
        selector = TagSelector(conf2)
        sel_asset = selector.select(asset)
        assert sel_asset is not None
        assert sel_asset.domain == 'test_i-111'
        assert sel_asset.nodes == ['test_test1']
        assert sel_asset.admin_user == 'test_127.0.0.1'

    def test_provider(self, settings):
        provider = 'aws'
        profile = 'us0066'
        p = get_provider(provider, settings, profile)
        assert isinstance(p, AssetsProvider)
        assert p.profile == profile
        assert p.config == settings.get('providers.{}.{}'.format(provider, profile))
        assert len(p.get_tag_selectors()) == 1
        for i in range(len(p.get_tag_selectors())):
            selector = p.get_tag_selectors()[i]
            assert len(selector.tags) == 1
            for j in range(len(selector.tags)):
                t = selector.tags[j]
                assert t.key == settings.get('tag_selectors')[i]['tags'][j]['key']
                assert t.value == settings.get('tag_selectors')[i]['tags'][j]['value']

    def test_aws_list_assets(self, settings):
        # should configure aws profile first
        from jumpserver_sync.providers.aws import AwsAssetsProvider
        provider = AwsAssetsProvider(settings=settings, profile='us0066')
        asset_ids = []
        for a in provider.list_assets(limit=2):
            assert a.account == 'us0066'
            asset_ids.append(a.number)
        for a in provider.list_assets(asset_ids=asset_ids):
            assert a.number in asset_ids


class TestClient:

    @pytest.fixture(scope='module')
    def settings(self):
        return Settings({
            'jumpserver': {
                'base_url': 'http://test.jumpserver.com',
                'user': 'admin',
                'password': 'admin',
                'login_url': '/api/users/v1/auth/'
            },
            'providers': {
                'aws': {
                    'us0066': {
                        'region_name': 'us-east-1',
                        'profile_name': 'us-east-1_0066'
                    }
                }
            },
            'cache': {
                'dir': '.jumpserver_cache',
                'ttl': 60
            },
            'log': {
                'log_level': 'INFO',
                'log_formatter': '[%(levelname)s] %(asctime)s : %(message)s',
            },
            'provider_cls': {
                'aws': 'jumpserver_sync.providers.aws.AwsAssetsProvider'
            },
            'tag_selectors': [
                {
                    'tags': [
                        {'key': 'Name', 'value': 'ecs-cluster-'},
                    ],
                    'attrs': {
                        'domain': 'test_domain',
                        'nodes': ['test_node'],
                        'admin_user': 'test_admin_user'
                    }
                }
            ]
        })

    def test_login(self, settings):
        cli = JumpserverClient(settings=settings)
        token = cli.get_token()
        assert token is not None

    def test_build_request(self, settings):
        cli = JumpserverClient(settings=settings)
        url = 'test'
        method = 'get'
        p = cli.build_request(url=url, method=method)
        assert p['url'] == settings.get('jumpserver.base_url') + '/test/'
        assert p['method'] == method
        assert 'Authorization' in p['headers']
        url = '/api/users/v1/auth/'
        method = 'post'
        p = cli.build_request(url=url, method=method)
        assert p['url'] == settings.get('jumpserver.base_url') + '/api/users/v1/auth/'
        assert p['method'] == method
        assert 'Authorization' in p['headers']
        url = '/api/users/v1/auth'
        method = 'post'
        p = cli.build_request(url=url, method=method)
        assert p['url'] == settings.get('jumpserver.base_url') + '/api/users/v1/auth/'
        assert p['method'] == method
        assert 'Authorization' in p['headers']

    def test_admin_user(self, settings):
        cli = AdminUser(settings=settings)
        admin_user_name = 'test_admin_user_' + str(random.randint(100, 999))
        admin_user_username = 'test_admin_user'
        data = {
            'name': admin_user_name,
            'username': admin_user_username
        }
        res = cli.post_resource(data=data)
        assert 'id' in res and res['id']
        assert res['name'] == admin_user_name
        assert res['username'] == admin_user_username
        res2 = cli.get_resource(res_id=res['id'])
        assert res == res2
        update = {'name': admin_user_name, 'username': 'update_admin_user'}
        res = cli.put_resource(res_id=res['id'], data=update)
        assert 'id' in res and res['id']
        assert res['name'] == admin_user_name
        assert res['username'] == 'update_admin_user'
        ls = cli.list_resources()
        for r in ls:
            assert 'id' in r and r['id']
        res2 = cli.delete_resource(res_id=res['id'])
        assert res2 is True
        res2 = cli.get_resource(res_id=res['id'])
        assert res2 == {}

    def test_node(self, settings):
        # Test jumpserver contain node Default/ops/prod
        cli = Node(settings=settings)
        node = 'Default/ops/prod'
        nid = cli.get_node_id(node)
        assert nid is not None
        n = cli.get_node_full_name(nid)
        assert n == node


class TestAssetAgent:

    clear_ids = {
        'domain': [],
        'admin_user': [],
        'label': []
    }

    @pytest.fixture(scope='module')
    def settings(self):
        settings = Settings({
            'jumpserver': {
                'base_url': 'http://test.jumpserver.com',
                'user': 'admin',
                'password': 'admin',
                'login_url': '/api/users/v1/auth/'
            },
            'providers': {
                'aws': {
                    'us0066': {
                        'region_name': 'us-east-1',
                        'profile_name': 'us-east-1_0066'
                    }
                }
            },
            'cache': {
                'dir': '.jumpserver_cache',
                'ttl': 60
            },
            'log': {
                'log_level': 'INFO',
                'log_formatter': '[%(levelname)s] %(asctime)s : %(message)s',
            },
            'provider_cls': {
                'aws': 'jumpserver_sync.providers.aws.AwsAssetsProvider'
            },
            'tag_selectors': [
                {
                    'tags': [
                        {'key': 'Name', 'value': 'ecs-cluster-'},
                    ],
                    'attrs': {
                        'domain': 'test_domain',
                        'nodes': ['Default/ops/prod'],
                        'admin_user': 'test_admin_user',
                        'labels': [{'key': 'account', 'value': 'us0066'}]
                    }
                }
            ]
        })
        yield settings
        domain = Domain(settings)
        for r in self.clear_ids['domain']:
            domain.delete_resource(res_id=r)
        self.clear_ids['domain'].clear()
        admin_user = AdminUser(settings)
        for r in self.clear_ids['admin_user']:
            admin_user.delete_resource(res_id=r)
        self.clear_ids['admin_user'].clear()
        label = Label(settings)
        for r in self.clear_ids['label']:
            label.delete_resource(res_id=r)
        self.clear_ids['label'].clear()

    def test_asset_agent(self, settings):
        agent = AssetAgent(settings)
        # create test domain
        domain = Domain(settings)
        domain_data = {'name': 'test_domain_' + str(random.randint(100, 999))}
        res = domain.post_resource(data=domain_data)
        assert 'id' in res
        domain_id = res['id']
        self.clear_ids['domain'].append(domain_id)
        # create test admin_user
        admin_user = AdminUser(settings)
        admin_user_data = {'name': 'test_admin_user_' + str(random.randint(100, 999)), 'username': 'test_admin_user'}
        res = admin_user.post_resource(data=admin_user_data)
        assert 'id' in res
        admin_user_id = res['id']
        self.clear_ids['admin_user'].append(admin_user_id)
        # create test label
        label = Label(settings)
        label_data = {'name': 'account', 'value': 'test_account'}
        res = label.post_resource(data=label_data)
        assert 'id' in res
        label_id = res['id']
        self.clear_ids['label'].append(label_id)
        # create asset
        d = {
            'hostname': 'test_hostname',
            'ip': '10.10.10.10',
            'number': 'i-12345678',
            'admin_user': admin_user_data['name'],
            'domain': domain_data['name'],
            'labels': [LabelTag.create_tag(label_data)],
            'nodes': ['Default/ops/prod']
        }
        asset = InstanceAsset(**d)
        # link asset
        assert agent.is_asset_linked(asset) is False
        asset = agent.link_asset(asset)
        assert agent.is_asset_linked(asset) is True
        assert asset.domain_id == domain_id
        assert asset.admin_user_id == admin_user_id
        assert asset.label_ids == [label_id]
        assert agent.get_asset_id(asset) is None
        # create asset
        res = agent.create_asset(asset)
        assert res is not None
        assert res.id is not None
        assert res.hostname == d['hostname']
        assert res.ip == d['ip']
        assert res.number == d['number']
        assert res.admin_user_id == admin_user_id
        assert res.domain_id == domain_id
        assert res.label_ids == [label_id]
        asset_id = res.id
        assert agent.get_asset_id(asset) is not None
        # update asset
        newip = '10.10.10.11'
        asset.set_attr('ip', newip)
        res2 = agent.update_asset(asset_id=asset_id, asset=asset)
        assert res2 is not None
        assert res2.id == asset_id
        assert res2.ip == newip
        assert res2.hostname == res.hostname
        assert res2.number == res.number
        # delete asset
        res3 = agent.delete_asset(asset_id=asset_id)
        assert res3 is True

    def test_sync(self, settings):
        # create test domain
        domain = Domain(settings)
        d = {'name': 'test_domain'}
        res = domain.post_resource(data=d)
        assert 'id' in res
        domain_id = res['id']
        self.clear_ids['domain'].append(domain_id)
        # create test admin_user
        admin_user = AdminUser(settings)
        d = {'name': 'test_admin_user', 'username': 'test_admin_user'}
        res = admin_user.post_resource(data=d)
        assert 'id' in res
        admin_user_id = res['id']
        self.clear_ids['admin_user'].append(admin_user_id)
        # create test label
        label = Label(settings)
        d = {'name': 'account', 'value': 'us0066'}
        res = label.post_resource(data=d)
        assert 'id' in res
        label_id = res['id']
        self.clear_ids['label'].append(label_id)
        # list assets
        agent = AssetAgent(settings)
        provider = 'aws'
        profile = 'us0066'
        p = get_provider(provider, settings, profile)
        for a in p.list_assets(limit=2):
            assert agent.is_asset_linked(a) is False
            a = agent.link_asset(a)
            assert agent.is_asset_linked(a) is True
            assert a.domain_id == domain_id
            assert a.admin_user_id == admin_user_id
            assert a.label_ids == [label_id]
            assert agent.get_asset_id(a) is None
            res = agent.sync_asset(a)
            assert res is not None
            assert agent.get_asset_id(a) is not None
            res = agent.delete_asset(res.id)
            assert res is True


