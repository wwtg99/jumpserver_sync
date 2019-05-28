FROM python:3.6
MAINTAINER wuwentao <wuwentao@patsnap.com>

RUN pip install awscli jumpserver-sync
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
