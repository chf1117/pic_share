# 服务器迁移快速指南

## 概述

这是一个快速迁移指南，帮助你在最短时间内完成服务器迁移。详细说明请参考 `migration_guide.md`。

## 前提条件

- 旧服务器：120.79.186.114
- 新服务器：已准备好的 Ubuntu 服务器
- 数据库名称：your_database_name（请根据实际情况修改）
- 域名：your_domain.com（请根据实际情况修改）

## 迁移流程（3步完成）

### 步骤 1：在本地机器上运行迁移脚本

```bash
# 设置新服务器地址
export NEW_SERVER_HOST="新服务器IP"
export NEW_SERVER_USER="root"

# 运行迁移脚本（会自动备份并传输数据）
bash migrate.sh
```

**这个脚本会做什么：**
- 在旧服务器上停止服务
- 备份 MongoDB 数据库
- 备份上传的图片文件
- 备份配置文件
- 将所有数据传输到新服务器

**预计时间：** 10-30分钟（取决于数据量和网络速度）

### 步骤 2：在新服务器上运行部署脚本

```bash
# 登录新服务器
ssh root@新服务器IP

# 找到并运行部署脚本
cd /root
BACKUP_DIR=$(ls -td pic_backup_* | head -1)
cd $BACKUP_DIR

# 如果脚本存在，直接运行
bash setup_new_server.sh

# 或者手动执行以下命令
cd /root
bash /path/to/setup_new_server.sh
```

**这个脚本会做什么：**
- 安装必要的系统依赖
- 克隆代码仓库
- 恢复 MongoDB 数据
- 恢复上传文件
- 配置 Nginx 和 Supervisor
- 启动所有服务

**预计时间：** 5-15分钟

### 步骤 3：验证迁移结果

```bash
# 在新服务器上运行验证脚本
bash verify_migration.sh
```

**这个脚本会检查：**
- 所有服务是否运行
- 数据是否完整
- 网站是否可以访问
- 配置是否正确

## 手动迁移步骤（如果脚本失败）

### 在旧服务器上

```bash
# 1. 停止服务
sudo supervisorctl stop pic

# 2. 备份数据库
mongodump --db your_database_name --out /root/mongodb_backup

# 3. 备份上传文件
cd /var/www/pic
tar -czf /root/uploads.tar.gz uploads/

# 4. 传输到新服务器
scp /root/mongodb_backup.tar.gz root@新服务器IP:/root/
scp /root/uploads.tar.gz root@新服务器IP:/root/
```

### 在新服务器上

```bash
# 1. 安装依赖
sudo apt update
sudo apt install -y python3-pip python3-venv nginx supervisor git mongodb

# 2. 克隆代码
git clone https://github.com/chf1117/pic_share.git /var/www/pic

# 3. 创建虚拟环境
cd /var/www/pic
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. 恢复数据库
mongorestore --db your_database_name /root/mongodb_backup/your_database_name/

# 5. 恢复文件
cd /var/www/pic
tar -xzf /root/uploads.tar.gz

# 6. 配置 Supervisor
sudo nano /etc/supervisor/conf.d/pic.conf
# 复制 deployment.md 中的配置

# 7. 配置 Nginx
sudo nano /etc/nginx/sites-available/pic
# 复制 deployment.md 中的配置
sudo ln -s /etc/nginx/sites-available/pic /etc/nginx/sites-enabled/

# 8. 设置权限
sudo chown -R www-data:www-data /var/www/pic/logs
sudo chown -R www-data:www-data /var/www/pic/uploads

# 9. 启动服务
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start pic
sudo systemctl restart nginx
```

## 验证检查清单

- [ ] MongoDB 服务运行正常
- [ ] Nginx 服务运行正常
- [ ] 应用进程运行正常
- [ ] 数据库数据完整（用户数、图片数）
- [ ] 上传文件完整（文件数量）
- [ ] 网站可以通过 IP 访问
- [ ] 静态文件可以访问
- [ ] 上传的图片可以显示

## 测试命令

```bash
# 检查服务状态
sudo supervisorctl status pic
sudo systemctl status nginx
sudo systemctl status mongod

# 测试网站访问
curl -I http://localhost
curl -I http://$(hostname -I | awk '{print $1}')

# 检查数据库
mongo your_database_name --eval "db.stats()"
mongo your_database_name --eval "db.images.count()"
mongo your_database_name --eval "db.users.count()"

# 检查文件
ls -lh /var/www/pic/uploads/ | wc -l

# 查看日志
sudo tail -f /var/log/supervisor/pic-stdout.log
sudo tail -f /var/log/supervisor/pic-stderr.log
```

## DNS 切换

迁移验证成功后：

1. 登录域名服务商控制台
2. 修改 A 记录，将域名指向新服务器 IP
3. 等待 DNS 传播（通常 5-30 分钟）
4. 验证域名访问：`curl -I http://your_domain.com`

## 回滚方案

如果新服务器出现问题：

```bash
# 在旧服务器上重启服务
ssh root@120.79.186.114
sudo supervisorctl start pic
sudo systemctl start nginx

# 将 DNS 指向旧服务器
```

## 常见问题

### 1. MongoDB 连接失败

```bash
sudo systemctl start mongod
sudo systemctl status mongod
```

### 2. 应用启动失败

```bash
# 查看错误日志
sudo tail -50 /var/log/supervisor/pic-stderr.log

# 检查权限
sudo chown -R www-data:www-data /var/www/pic
```

### 3. Nginx 502 错误

```bash
# 检查应用是否运行
sudo supervisorctl status pic

# 检查端口
netstat -tlnp | grep 8000
```

### 4. 图片无法显示

```bash
# 检查文件权限
sudo chmod -R 755 /var/www/pic/uploads

# 检查 Nginx 配置
sudo nginx -t
```

## 迁移后优化

### 1. 配置 HTTPS

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your_domain.com
```

### 2. 设置自动备份

```bash
# 编辑 crontab
crontab -e

# 添加以下行
0 2 * * * mongodump --db your_database_name --out /backup/mongodb_$(date +\%Y\%m\%d)
0 3 * * * tar -czf /backup/uploads_$(date +\%Y\%m\%d).tar.gz /var/www/pic/uploads
```

### 3. 配置 MongoDB 索引

```bash
mongo your_database_name
db.images.createIndex({"user_id": 1})
db.images.createIndex({"created_at": -1})
db.images.createIndex({"tags": 1})
```

## 支持

如果遇到问题：

1. 查看详细文档：`docs/migration_guide.md`
2. 查看部署文档：`docs/deployment.md`
3. 运行验证脚本：`bash verify_migration.sh`
4. 检查日志文件

## 文件说明

- `migrate.sh` - 旧服务器数据备份和传输脚本
- `setup_new_server.sh` - 新服务器部署脚本
- `verify_migration.sh` - 迁移验证脚本
- `docs/migration_guide.md` - 详细迁移指南
- `docs/deployment.md` - 部署文档
