#!/bin/bash

if [ -f "${AWS_PROFILE_SCRIPT}" ];then
    bash ${AWS_PROFILE_SCRIPT}
else
    echo "No profile file exists"
fi
jumpserver_sync $*
