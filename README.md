Jumpserver Sync Tool
====================

# 简介

[Jumpserver](https://github.com/jumpserver/jumpserver) 是开源的多云环境的堡垒机，可以用于管理和登陆各个来源的实例。但是使用 Jumpserver 必须手动添加实例到系统，对于经常开关的集群不太方便。此工具用于将多云平台的实例快速添加到 Jumpserver 中，实现自动同步多云平台的实例。

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
      - Key: region
        Value: {region}
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

### Jumpserver 服务器配置

```
jumpserver:
  # Jumpserver 的服务器路径, 类似 http://demo.jumpserver.com
  base_url: ""
  # 管理员用户名
  user: ""
  # 管理员密码
  password: ""
```

### 缓存配置

```
cache:
  # 缓存目录
  dir: .jumpserver_cache
  # 缓存时间（秒）
  ttl: 60
```

### 日志配置

```
log:
  # 日志级别
  log_level: INFO
  # 日志格式
  log_formatter: "[%(levelname)s] %(asctime)s : %(message)s"
```

### 云服务账号配置

```
profiles:
  # 账户名称
  account1:
    # 账户类型，可选： aws
    type: aws
    # 云服务配置，取决于使用的云服务商，使用 AWS 可以使用 profile_name, region_name, aws_access_key_id, aws_secret_access_key，具体含义可以参考 AWS 官方文档
    region_name: cn-northwest-1
    # 使用 profile_name 需要配置 access_key 和 secret 在 aws 的 profile 里
    profile_name: cn-northwest-1_account1
```

### 标签选择器配置

```
tag_selectors:
  - tags:
    # 需要匹配的标签
    - key: tag_name
      value: tag_value
    # 匹配标签后需要设置的属性, 支持变量的使用 {number}, {hostname}, {ip}, {public_ip}, {account}, {region}
    attrs:
      admin_user: admin_user
      domain: domain
      labels:
      - Key: region
        Value: {region}
      nodes:
      - node1
```

在 `tag_selectors` 中可以配置多个选择器，对每个发现的实例逐个匹配，当匹配一个选择器后，就应用选择器的属性设置修改实例的属性值，并添加到 Jumpserver 中，未匹配的实例不会添加。

在 `tags` 中的 `key` 是实例标签的键，`value` 是实例标签的值，支持正则表达式，使用了 `re.match` 来匹配。
例如，`key=Team value=t1` 能匹配 `key=Team value=t1`, `key=Team value=t111` 等实例，需要完全匹配需要使用 `value="^t1$"`。 

在 `attrs` 中能设置替换的属性，支持如下变量替换
- {number}: 实例 ID
- {hostname}：实例 hostname，hostname 默认从实例的 Name 标签获取值
- {ip}: 实例的内网 IP
- {public_ip}: 实例的公网 IP
- {account}：实例的云服务账户名称
- {region}：实例的云服务区域

也可以使用对应的资源名称，如 `admin_user: admin_user` 会查找 `name=admin_user` 的管理用户。

注意，所有指定的资源（管理用户，系统用户，网域，标签，资源节点）必须事先创建好，如果不存在会插入失败。

### 监听配置

```
listensing:
    # 监听配置名称
    test_sqs:
      # 监听类型，支持 sqs
      type: sqs
      # 使用的云账户配置名称，关联上面的 profiles 配置中的项
      profile: account1
      # 指定推送系统用户的名称，默认全部
      push_system_users: ""
      # 对于 SQS 类型的配置
      # queue 的 URL
      queue: "queue_url"
      # 最大接受消息数量，1 ～ 10
      max_size: 1
```

### 实例标签配置

jumpserver-sync 提供了一些实例功能标签，这些标签影响实例能否被添加。

- Name: 需要添加的实例必须有 Name 标签，这个标签用来生成实例的 hostname
- jumpserver_ignore：当实例有`jumpserver_ignore`标签，且值为`true`时，实例会被忽略

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

# Docker 中使用

使用提供的 Dockerfile 构建镜像。

```
docker build -t jumpserver-sync:latest .
```

如果虚拟机或容器没有获取实例的权限，则需要用 key 的方式注入容器。
准备好 profile 文件（用于授权获取实例的权限，如 AWS 的 access_key 和 secret。

例如，AWS profile script

```
aws configure set aws_access_key_id AAAAAAAAAAAA --profile test
aws configure set aws_secret_access_key SSSSSSSSS --profile test
aws configure set region us-east-1 --profile test
```

同时需要准备 config.yml 配置文件。

使用 docker 运行容器，并提供 profile 脚本和配置文件

```
docker run -d -e "AWS_PROFILE_SCRIPT=/opt/aws/.aws_profile.sh" -v .aws_profile.sh:/opt/aws/.aws_profile.sh -v config.yml:/opt/jms/config.yml jumpserver-sync:latest sync -c /opt/jms/config.yml
```

`AWS_PROFILE_SCRIPT`环境变量用于指定 profile 脚本的路径。

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
