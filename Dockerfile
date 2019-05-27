FROM python:3.6
MAINTAINER wuwentao <wwtg99@126.com>

RUN pip install jumpserver-sync
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
