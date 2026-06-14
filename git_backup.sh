#!/bin/bash
# 1. Navigate to repository root
cd /home/raj/monitoring-lab
# 2. Force Git to use SSH key for authentication
export GIT_SSH_COMMAND="ssh -i /home/raj/.ssh/id_ed25519 -o IdentitiesOnly=yes"
# 3. Supply home environment for Git global configs inside Cron
export HOME=/home/raj
# 4. Only commit and push if changes exist
if [[ -n $(git status --porcelain) ]]; then
    git add .
    git commit -m "chrono: automated checkpoint $(date '+%Y-%m-%d %H:%M:%S')"
    git push origin main >> /home/raj/monitoring-lab/git_cron.log 2>&1
fi
