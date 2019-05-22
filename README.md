Jumpserver Sync Tool
====================

# Introduction

This tool sync assets from cloud providers (such as AWS) to Jumpserver. It is especially useful for situation that start and stop instances frequently (such as use large amount of spot instances). It can add or delete instances by specified tags.

# Installation

```
pip install jumpserver-sync
```

# Usage


# Test

Requirements

- Install pytest.
- Deploy a test server on domain test.jumpserver.com (change your hosts).
- Ensure username admin password admin is superuser (by default if you do not change).
- Add asset node Default/ops/prod.
- Add AWS SQS ops_test with no message for listening test.
- Configure your AWS profile.

Then use command below to run test
```
pytest
```
