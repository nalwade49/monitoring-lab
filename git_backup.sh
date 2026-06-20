#!/bin/bash

cd /home/project/monitoring-lab

export GIT_SSH_COMMAND="ssh -i /home/project/.ssh/id_ed25519 -o IdentitiesOnly=yes"
export HOME=/home/project

if [[ -n $(git status --porcelain) ]]; then
    git add -A
    git commit -m "chrono: automated checkpoint $(date '+%Y-%m-%d %H:%M:%S')"
    git push origin main >> /home/project/monitoring-lab/git_cron.log 2>&1
fi
