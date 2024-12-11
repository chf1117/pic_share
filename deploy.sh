#!/bin/bash

# 确保脚本在错误时停止
set -e

echo "开始部署流程..."

# 1. 备份服务器上的数据
echo "备份现有数据..."
ssh your_server "cd /var/www/pic && \
    mongodump --out backup_$(date +%Y%m%d_%H%M%S) && \
    cp -r uploads uploads_backup_$(date +%Y%m%d_%H%M%S)"

# 2. 提交本地更改
echo "提交本地更改..."
git add .
git commit -m "Update before deployment $(date +%Y%m%d_%H%M%S)"
git push origin main

# 3. 在服务器上更新代码
echo "更新服务器代码..."
ssh your_server "cd /var/www/pic && \
    git stash && \
    git pull origin main && \
    git stash pop || true"

# 4. 更新依赖
echo "更新Python依赖..."
ssh your_server "cd /var/www/pic && \
    source venv/bin/activate && \
    pip install -r requirements.txt"

# 5. 重启服务
echo "重启服务..."
ssh your_server "sudo supervisorctl restart pic"

echo "部署完成!"
