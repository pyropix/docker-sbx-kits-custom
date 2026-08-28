#!/usr/bin/env bash
set -euxo pipefail

curl -fsSL https://get.docker.com | sudo REPO_ONLY=1 sh
sudo apt-get install docker-sbx
sudo usermod -aG kvm $USER
newgrp kvm

# Login to sbx
sbx login