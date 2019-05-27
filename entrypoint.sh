#!/bin/bash

if [ -f "/.aws_profile.sh" ];then
    bash /.aws_profile.sh
else
    echo "No profile file exists"
fi
jumpserver_sync $*
