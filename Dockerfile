FROM python:3.6
MAINTAINER wuwentao <wwtg99@126.com>

RUN pip install jumpserver-sync
ENTRYPOINT jumpserver_sync
