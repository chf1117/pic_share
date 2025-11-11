# 服务器迁移指南

本文档详细说明如何将图片分享平台从旧服务器迁移到新服务器，确保数据完整性和服务连续性。

## 迁移概述

### 需要迁移的数据
1. **MongoDB 数据库** - 用户信息、图片元数据、标签等
2. **上传的图片文件** - `/var/www/pic/uploads/` 目录
3. **应用代码** - Git 仓库代码
4. **配置文件** - Nginx、Supervisor 配置
5. **日志文件**（可选）- 历史日志记录

### 迁移策略
- **停机迁移**：短暂停机，确保数据一致性（推荐）
- **热迁移**：服务不中断，但需要更复杂的同步机制

## 迁移前准备

### 1. 新服务器信息记录
```bash
# 记录新服务器信息
NEW_SERVER_IP="新服务器IP"
NEW_SERVER_USER="root"
OLD_SERVER_IP="120.79.186.114"
OLD_SERVER_USER="root"
```

### 2. 检查旧服务器数据
```bash
# 登录旧服务器
ssh root@120.79.186.114

# 检查 MongoDB 数据库大小
mongo --eval "db.stats()" your_database_name

# 检查上传文件大小
du -sh /var/www/pic/uploads/

# 检查服务状态
sudo supervisorctl status pic
```

### 3. 新服务器环境准备
在新服务器上执行以下操作：

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装必要软件
sudo apt install -y python3-pip python3-venv nginx supervisor git mongodb

# 安装 Python 开发包
sudo apt install -y python3-dev build-essential libssl-dev libffi-dev

# 启动 MongoDB
sudo systemctl start mongod
sudo systemctl enable mongod
```

## 迁移步骤（停机迁移）

### 第一步：在旧服务器上备份数据

```bash
# 登录旧服务器
ssh root@120.79.186.114

# 创建备份目录
BACKUP_DIR="/root/pic_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

# 1. 停止服务（重要：确保数据一致性）
sudo supervisorctl stop pic

# 2. 备份 MongoDB 数据库
cd $BACKUP_DIR
mongodump --db your_database_name --out mongodb_backup

# 3. 打包上传的图片文件
cd /var/www/pic
tar -czf $BACKUP_DIR/uploads.tar.gz uploads/

# 4. 备份配置文件
cp /etc/nginx/sites-available/pic $BACKUP_DIR/nginx_pic.conf
cp /etc/supervisor/conf.d/pic.conf $BACKUP_DIR/supervisor_pic.conf

# 5. 备份日志（可选）
tar -czf $BACKUP_DIR/logs.tar.gz logs/

# 6. 创建数据清单
cd $BACKUP_DIR
cat > migration_manifest.txt << EOF
备份时间: $(date)
MongoDB 数据库: your_database_name
上传文件数量: $(find /var/www/pic/uploads -type f | wc -l)
上传文件大小: $(du -sh /var/www/pic/uploads | cut -f1)
MongoDB 大小: $(du -sh mongodb_backup | cut -f1)
EOF

echo "备份完成，备份目录: $BACKUP_DIR"
ls -lh $BACKUP_DIR
```

### 第二步：传输数据到新服务器

```bash
# 在旧服务器上执行
NEW_SERVER_IP="新服务器IP"
NEW_SERVER_USER="root"

# 压缩整个备份目录
cd /root
tar -czf pic_backup.tar.gz pic_backup_*

# 传输到新服务器
scp pic_backup.tar.gz $NEW_SERVER_USER@$NEW_SERVER_IP:/root/

# 或者使用 rsync（更快，支持断点续传）
rsync -avz --progress pic_backup.tar.gz $NEW_SERVER_USER@$NEW_SERVER_IP:/root/
```

### 第三步：在新服务器上部署应用

```bash
# 登录新服务器
ssh root@新服务器IP

# 1. 解压备份文件
cd /root
tar -xzf pic_backup.tar.gz
BACKUP_DIR=$(ls -d pic_backup_* | head -1)

# 2. 创建项目目录
sudo mkdir -p /var/www/pic
sudo chown -R $USER:$USER /var/www/pic

# 3. 克隆代码仓库
git clone https://github.com/chf1117/pic_share.git /var/www/pic

# 4. 创建虚拟环境并安装依赖
cd /var/www/pic
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. 恢复 MongoDB 数据
cd /root/$BACKUP_DIR
mongorestore --db your_database_name mongodb_backup/your_database_name/

# 验证数据恢复
mongo --eval "db.stats()" your_database_name

# 6. 恢复上传的图片文件
cd /var/www/pic
tar -xzf /root/$BACKUP_DIR/uploads.tar.gz

# 验证文件数量
echo "上传文件数量: $(find uploads -type f | wc -l)"

# 7. 创建必要的目录
sudo mkdir -p /var/www/pic/logs
sudo mkdir -p /var/log/supervisor
```

### 第四步：配置服务

```bash
# 1. 配置 Supervisor
sudo nano /etc/supervisor/conf.d/pic.conf
```

添加以下内容（根据实际情况修改）：
```ini
[program:pic] 
directory=/var/www/pic 
command=/var/www/pic/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 app:app 
user=www-data 
autostart=true 
autorestart=true 
stderr_logfile=/var/log/supervisor/pic-stderr.log 
stdout_logfile=/var/log/supervisor/pic-stdout.log 
environment=PYTHONPATH="/var/www/pic",MONGO_URI="mongodb://localhost:27017/your_database_name" 
startsecs=5
stopwaitsecs=5
```

```bash
# 2. 配置 Nginx
sudo nano /etc/nginx/sites-available/pic
```

添加以下内容（替换域名）：
```nginx
server {
    listen 80;
    server_name your_domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        client_max_body_size 10M;
    }

    location /static {
        alias /var/www/pic/static;
    }

    location /uploads {
        alias /var/www/pic/uploads;
        expires 14d;
        add_header Cache-Control "public, no-transform";
    }
}
```

```bash
# 3. 设置目录权限
sudo chown -R www-data:www-data /var/www/pic/logs
sudo chown -R www-data:www-data /var/www/pic/uploads
sudo chmod -R 755 /var/www/pic/logs
sudo chmod -R 755 /var/www/pic/uploads

# 4. 启用 Nginx 站点
sudo ln -s /etc/nginx/sites-available/pic /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# 5. 启动应用
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start pic
```

### 第五步：验证迁移

```bash
# 1. 检查服务状态
sudo supervisorctl status pic
sudo systemctl status nginx
sudo systemctl status mongod

# 2. 检查日志
sudo tail -f /var/log/supervisor/pic-stdout.log
sudo tail -f /var/log/supervisor/pic-stderr.log

# 3. 验证数据库
mongo --eval "db.images.count()" your_database_name
mongo --eval "db.users.count()" your_database_name

# 4. 验证文件
ls -lh /var/www/pic/uploads/ | wc -l

# 5. 测试网站访问
curl -I http://localhost
curl -I http://新服务器IP
```

### 第六步：DNS 切换

```bash
# 1. 更新 DNS 记录，将域名指向新服务器 IP
# 在域名服务商控制台操作

# 2. 等待 DNS 传播（通常需要几分钟到几小时）
# 可以使用以下命令检查 DNS 是否生效
nslookup your_domain.com

# 3. 验证新服务器可以通过域名访问
curl -I http://your_domain.com
```

### 第七步：清理旧服务器（确认新服务器正常运行后）

```bash
# 登录旧服务器
ssh root@120.79.186.114

# 保留备份，但可以停止服务
sudo supervisorctl stop pic
sudo systemctl stop nginx

# 不要立即删除数据，保留一段时间作为备份
# 建议保留 1-2 周后再清理
```

## 热迁移方案（可选）

如果需要零停机迁移，可以使用以下方案：

### 1. 数据同步
```bash
# 在旧服务器上设置 MongoDB 复制
# 使用 rsync 持续同步上传文件
rsync -avz --delete /var/www/pic/uploads/ root@新服务器IP:/var/www/pic/uploads/
```

### 2. 双写策略
- 配置应用同时写入新旧两个服务器
- 或使用负载均衡器逐步切换流量

### 3. 最终同步
- 在切换前进行最后一次数据同步
- 快速切换 DNS

## 回滚方案

如果迁移出现问题，可以快速回滚：

```bash
# 1. 将 DNS 指向旧服务器
# 2. 在旧服务器上重启服务
ssh root@120.79.186.114
sudo supervisorctl start pic
sudo systemctl start nginx
```

## 迁移检查清单

- [ ] 新服务器环境已准备就绪
- [ ] 旧服务器数据已完整备份
- [ ] MongoDB 数据已成功恢复
- [ ] 上传文件已完整传输
- [ ] Nginx 配置正确
- [ ] Supervisor 配置正确
- [ ] 目录权限设置正确
- [ ] 服务启动正常
- [ ] 网站可以正常访问
- [ ] 用户登录功能正常
- [ ] 图片上传功能正常
- [ ] 图片显示正常
- [ ] DNS 已切换到新服务器
- [ ] 监控已配置（可选）
- [ ] 备份策略已设置

## 常见问题

### 1. MongoDB 连接失败
```bash
# 检查 MongoDB 服务状态
sudo systemctl status mongod

# 检查 MongoDB 日志
sudo tail -f /var/log/mongodb/mongod.log

# 确认数据库名称正确
mongo --eval "show dbs"
```

### 2. 文件权限问题
```bash
# 重新设置权限
sudo chown -R www-data:www-data /var/www/pic
sudo chmod -R 755 /var/www/pic
```

### 3. Nginx 502 错误
```bash
# 检查 Gunicorn 是否运行
sudo supervisorctl status pic

# 检查端口是否被占用
netstat -tlnp | grep 8000

# 查看错误日志
sudo tail -f /var/log/nginx/error.log
```

### 4. 图片无法显示
```bash
# 检查上传目录
ls -lh /var/www/pic/uploads/

# 检查 Nginx 配置中的 uploads 路径
sudo nginx -t

# 检查文件权限
sudo chmod -R 755 /var/www/pic/uploads
```

## 性能优化建议

迁移完成后，可以考虑以下优化：

1. **配置 MongoDB 索引**
```bash
mongo your_database_name
db.images.createIndex({"user_id": 1})
db.images.createIndex({"created_at": -1})
db.images.createIndex({"tags": 1})
```

2. **配置自动备份**
```bash
# 添加到 crontab
0 2 * * * /usr/bin/mongodump --out /backup/mongodb_$(date +\%Y\%m\%d)
0 3 * * * tar -czf /backup/uploads_$(date +\%Y\%m\%d).tar.gz /var/www/pic/uploads
```

3. **配置 HTTPS**（推荐使用 Let's Encrypt）
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your_domain.com
```

## 联系支持

如果在迁移过程中遇到问题，请检查：
1. 服务器日志文件
2. MongoDB 日志
3. Nginx 错误日志
4. Supervisor 日志

保留所有备份文件，直到确认新服务器完全正常运行。
