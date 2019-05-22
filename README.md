Jumpserver Sync Tool
====================

# 简介

Jumpserver 是开源的多云环境的堡垒机，可以用于管理和登陆各个来源的实例。但是使用 Jumpserver 必须手动添加实例到系统，对于经常开关的集群不太方便。此工具用于将多云平台的实例快速添加到 Jumpserver 中，实现自动同步多云平台的实例。

目前支持的云服务：
- AWS

支持的 Jumpserver 版本：1.4.10+

# 安装

```
pip install jumpserver-sync
```

# 使用

## 配置

创建配置文件 `config.yml`，类似下面

```
# Jumpserver configuration
jumpserver:
  # Base url for Jumpserver, ex: http://demo.jumpserver.com
  base_url: ""
  # User name that has admin role
  user: ""
  # User password
  password: ""
  # Login url
  login_url: "/api/users/v1/auth/"
# Cache configuration
cache:
  # Cache directory
  dir: .jumpserver_cache
  # Cache ttl time
  ttl: 60
# Log configuration
log:
  # log level
  log_level: INFO
# Profile configuration
profiles:
  # Profile settings, required type, for aws type, can configure profile_name, region_name, aws_access_key_id, aws_secret_access_key
  account1:
    type: aws
    region_name: cn-northwest-1
    profile_name: cn-northwest-1_account1
# Tag selectors list
tag_selectors:
  - tags:
    # Tags to match
    - key: tag_name
      value: tag_value
    # Attributes to set if match, variables {number}, {hostname}, {ip}, {public_ip}, {account}, {region} are available
    attrs:
      admin_user: admin_user
      domain: domain
      labels:
        - label1
      nodes:
        - node1
# Listening configuration
listensing:
    # listening provider name
    test_sqs:
      # listening on AWS SQS
      type: sqs
      # Use this profile to receive message
      profile: account1
      # SQS URL
      queue: "queue_url"
      # max size to receive
      max_size: 1
      # specify system_users to push, comma separated
      push_system_users: ""
```

## 同步实例

同步云服务账户 account1 的实例到 Jumpserver
```
jumpserver_sync sync -c config.yml -p account1
```

配置文件中配置了 account1 的账户，使用前需要配置对应的 AWS 的 key 和 secret
```
aws configure --profile cn-northwest-1_account1
```

指定特定的实例 ID
```
jumpserver_sync sync -c config.yml -p account1 --instance-id i-08399a6b600f5e934
```

添加实例后测试连接性
```
jumpserver_sync sync -c config.yml -p account1 --test
```

添加实例后推送系统用户
```
jumpserver_sync sync -c config.yml -p account1 --push
```

指定推送的系统用户并检查是否推送成功
```
jumpserver_sync sync -c config.yml -p account1 --push-check --push-system-users=system_user_name
```

显示推送和测试的任务日志
```
jumpserver_sync sync -c config.yml -p account1 --push-check --show-task-log
```

## 测试实例

测试实例连接性
```
jumpserver_sync check -c config.yml -p account1
```

指定实例 ID
```
jumpserver_sync check -c config.yml -p account1 -i i-08399a6b600f5e934
```

## 移除 Jumpserver 中的实例

移除无法连接的实例
```
jumpserver_sync clean -c config.yml
```

指定特定的云账户
```
jumpserver_sync clean -c config.yml -p account1
```

指定实例 ID
```
jumpserver_sync clean -c config.yml -i i-08399a6b600f5e934
```

直接移除实例，不测试
```
jumpserver_sync clean -c config.yml --all
```

## 触发式添加

此工具可以监听特定的队列，当队列中有消息时自动添加或删除实例。

支持的队列：
- AWS SQS

### 监听 SQS

创建一个 SQS 队列，在配置文件的 `listening` 段配置监听任务，`tpye` 指定 `sqs`，`queue` 写上 SQS 的 URL。

```
jumpserver_sync listen -c config.yml -l test_sqs
```

此程序会持续监听队列，消费任何发送的消息，我们向队列发送一条实例 ID 的消息，
"i-08399a6b600f5e934"，程序将会检查实例是否存在，并添加到 Jumpserver。

支持的消息格式:
- i-08399a6b600f5e934
- i-08399a6b600f5e934,i-08399a6b600f5e935
- "i-08399a6b600f5e934"

### 使用 CloudWatch 事件规则

我们可以配置 CloudWatch 事件规则，在实例启动或停止时自动发送消息到 SQS，由程序持续消费队列并增减实例。

创建事件规则
1. 打开 CloudWatch，在左侧菜单选择 `事件-规则`
2. 在 `事件源` 中选择 `事件模式` （生成事件模式以匹配事件）， `服务名称` 选择 EC2， `事件类型` 选择 EC2 Instance State-change Notification
3. 选择 `任何状态` 或者 `特定状态` （如果要自动增加实例需要 running，如果要自动删除实例需要 terminated）
4. 在右侧目标栏，选择 SQS 队列，并选择配置的队列名
5. 配置详细，然后更新规则

当每次实例状态变化时（开启或关闭）即会向队列发送消息，在配置文件中配好对应的监听规则，即可启动监听。

# 测试

测试需要配置一个测试环境：

- 安装 pytest
- 部署一个测试 Jumpserver 服务，且使用域名 test.jumpserver.com (可以修改 hosts 文件)
- 保证使用 admin/admin 可以登陆且是管理员权限（默认配置）
- 在资产列表中添加一个测试资产节点 Default/ops/prod
- 添加 AWS SQS ops_test 且没有消息，用于测试监听
- 配置 AWS 密钥

使用下面的命令测试
```
pytest
```
