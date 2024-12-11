#!/bin/bash

# 确保脚本在错误时停止
set -e

# 服务器配置
SERVER_USER="root"
SERVER_HOST="120.79.186.114"
SERVER_PATH="/var/www/pic"

echo "开始部署流程..."

# 1. 备份服务器上的数据
echo "备份现有数据..."
ssh $SERVER_USER@$SERVER_HOST "cd $SERVER_PATH && \
    mongodump --out backup_$(date +%Y%m%d_%H%M%S) && \
    cp -r uploads uploads_backup_$(date +%Y%m%d_%H%M%S)"

# 2. 提交本地更改
echo "提交本地更改..."
git add .
git commit -m "Update before deployment $(date +%Y%m%d_%H%M%S)"
git push origin main

# 3. 在服务器上更新代码
echo "更新服务器代码..."
ssh $SERVER_USER@$SERVER_HOST "cd $SERVER_PATH && \
    git stash && \
    git pull origin main && \
    git stash pop || true"

# 4. 确保目录权限正确
echo "设置目录权限..."
ssh $SERVER_USER@$SERVER_HOST "sudo mkdir -p $SERVER_PATH/logs && \
    sudo mkdir -p $SERVER_PATH/uploads && \
    sudo chown -R www-data:www-data $SERVER_PATH/logs && \
    sudo chown -R www-data:www-data $SERVER_PATH/uploads && \
    sudo chmod -R 755 $SERVER_PATH/logs && \
    sudo chmod -R 755 $SERVER_PATH/uploads"

# 5. 更新依赖
echo "更新Python依赖..."
ssh $SERVER_USER@$SERVER_HOST "cd $SERVER_PATH && \
    source venv/bin/activate && \
    pip install -r requirements.txt"

# 6. 重启服务
echo "重启服务..."
ssh $SERVER_USER@$SERVER_HOST "sudo supervisorctl restart pic && \
    sudo systemctl restart nginx"

# 7. 检查服务状态
echo "检查服务状态..."
ssh $SERVER_USER@$SERVER_HOST "sudo supervisorctl status pic"

echo "部署完成!"
