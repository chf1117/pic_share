# 服务器迁移指南（Windows 开发 → 阿里云 Ubuntu）

## 📋 背景说明

- **开发环境**：Windows 本地开发
- **旧服务器**：阿里云 Ubuntu (120.79.186.114)
- **新服务器**：阿里云 Ubuntu (39.101.66.20)
- **迁移目标**：将所有数据和服务从旧服务器迁移到新服务器
- **操作方式**：在 Windows PowerShell 中通过 SSH 连接服务器操作

## 🎯 迁移内容

1. MongoDB 数据库（用户、图片元数据、标签等）
2. 上传的图片文件（`/var/www/pic/uploads/` - 约 1970 个文件，1.5GB）
3. 应用代码（从旧服务器直接复制，避免 GitHub 连接问题）
4. 配置文件（Nginx、Supervisor）

## ⏱️ 实际耗时

- 数据备份：5-10 分钟
- 数据传输：10-30 分钟（取决于数据量和网络）
- 新服务器部署：15-20 分钟（包含问题排查）
- **总计**：约 30-60 分钟

## ⚠️ 重要提示

本指南基于实际迁移经验编写，包含了所有遇到的问题和解决方案：
- MongoDB 在 Ubuntu 22.04 需要从官方仓库安装
- GitHub 访问可能不稳定，建议从旧服务器直接复制代码
- 需要复制所有 Python 文件（包括 utils.py 等）
- 上传文件目录结构需要验证

## 📝 迁移步骤

### 准备阶段

#### 1. 确认数据库名称

在 Windows PowerShell 中运行：

```powershell
# SSH 登录旧服务器
ssh root@120.79.186.114
```

在服务器上查看数据库名：

```bash
mongo
show dbs
# 你会看到类似这样的输出：
# admin           0.000GB
# config          0.000GB
# local           0.000GB
# your_database_name  0.005GB  <-- 这是你的数据库名

# 记下你的数据库名称，然后退出
exit
exit
```

#### 2. 确认新服务器信息

- 新服务器 IP 地址：`39.101.66.20`
- SSH 登录用户：通常是 `root` 密码#Chf1117#
- 确保可以 SSH 登录新服务器

### 执行阶段

#### 步骤 1：备份旧服务器数据

**在 Windows PowerShell 中：**

```powershell
# SSH 登录旧服务器
ssh root@120.79.186.114
```

**在旧服务器上执行（复制整段命令一次性运行）：**

```bash
# 设置变量（请修改为你的实际数据库名）
DB_NAME="your_database_name"  # 改为你的数据库名
BACKUP_TIME=$(date +%Y%m%d_%H%M%S)

# 停止服务（确保数据一致性）
echo "停止服务..."
sudo supervisorctl stop pic

# 创建备份目录
echo "创建备份目录..."
mkdir -p /root/pic_backup_$BACKUP_TIME
cd /root/pic_backup_$BACKUP_TIME

# 备份 MongoDB 数据库
echo "备份数据库..."
mongodump --db $DB_NAME --out mongodb_backup

# 备份上传的图片文件
echo "备份图片文件..."
cd /var/www/pic
tar -czf /root/pic_backup_$BACKUP_TIME/uploads.tar.gz uploads/

# 备份配置文件
echo "备份配置文件..."
sudo cp /etc/nginx/sites-available/pic /root/pic_backup_$BACKUP_TIME/nginx_pic.conf 2>/dev/null || echo "Nginx配置不存在"
sudo cp /etc/supervisor/conf.d/pic.conf /root/pic_backup_$BACKUP_TIME/supervisor_pic.conf 2>/dev/null || echo "Supervisor配置不存在"

# 创建迁移清单
cat > /root/pic_backup_$BACKUP_TIME/manifest.txt << EOF
备份时间: $(date)
数据库名: $DB_NAME
图片数量: $(find /var/www/pic/uploads -type f 2>/dev/null | wc -l)
数据大小: $(du -sh /var/www/pic/uploads 2>/dev/null | cut -f1)
备份目录: /root/pic_backup_$BACKUP_TIME
EOF

# 压缩所有备份
echo "压缩备份文件..."
cd /root
tar -czf pic_backup_$BACKUP_TIME.tar.gz pic_backup_$BACKUP_TIME/

# 显示备份信息
echo "=========================================="
echo "备份完成！"
echo "=========================================="
ls -lh pic_backup_$BACKUP_TIME.tar.gz
echo ""
cat pic_backup_$BACKUP_TIME/manifest.txt
echo "=========================================="
```

#### 步骤 2：传输数据到新服务器

**在旧服务器上继续执行：**

```bash
# 设置新服务器 IP（请修改为实际 IP）
NEW_SERVER_IP="39.101.66.20"

# 传输备份文件
echo "开始传输数据到新服务器..."
scp pic_backup_*.tar.gz root@$NEW_SERVER_IP:/root/

echo "数据传输完成！"
```

**传输完成后，可以选择重启旧服务器的服务（可选）：**

```bash
# 如果需要保持旧服务器继续运行
sudo supervisorctl start pic
```

**退出旧服务器：**

```bash
exit
```

#### 步骤 3：在新服务器上部署

**在 Windows PowerShell 中（新开一个窗口或标签）：**

```powershell
# SSH 登录新服务器（替换为实际 IP）
ssh root@39.101.66.20
password #Chf1117#
```

**在新服务器上执行（复制整段命令一次性运行）：**

```bash
# 设置变量（请修改为你的实际信息）
DB_NAME="your_database_name"    # 改为你的数据库名
DOMAIN_NAME="39.101.66.20"      # 改为你的域名或服务器IP
GIT_REPO="https://github.com/chf1117/pic_share.git"

# 1. 安装 MongoDB 7.0（Ubuntu 22.04 官方仓库没有 mongodb 包）
echo "安装 MongoDB 7.0..."
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update
sudo apt install -y mongodb-org

# 2. 安装其他系统依赖
echo "安装其他依赖..."
sudo apt install -y python3-pip python3.10-venv nginx supervisor git
sudo apt install -y python3-dev build-essential libssl-dev libffi-dev

# 3. 启动 MongoDB
echo "启动 MongoDB..."
sudo systemctl start mongod
sudo systemctl enable mongod
sleep 3

# 验证 MongoDB 状态
sudo systemctl status mongod --no-pager | head -5

# 3. 解压备份文件
echo "解压备份文件..."
cd /root
BACKUP_FILE=$(ls -t pic_backup_*.tar.gz | head -1)
tar -xzf $BACKUP_FILE
BACKUP_DIR=$(ls -td pic_backup_* | grep -v ".tar.gz" | head -1)

# 4. 显示备份信息
echo "=========================================="
cat $BACKUP_DIR/manifest.txt
echo "=========================================="

# 5. 从旧服务器复制代码（避免 GitHub 连接问题）
echo "从旧服务器复制代码..."
sudo mkdir -p /var/www/pic
sudo chown -R $USER:$USER /var/www/pic
cd /var/www/pic

# 一次性复制所有代码文件（只需输入一次密码）
scp root@120.79.186.114:/var/www/pic/*.py ./
scp -r root@120.79.186.114:/var/www/pic/{static,templates} ./

# 检查文件是否完整
echo "代码文件列表："
ls -la *.py

# 6. 创建虚拟环境并安装依赖
echo "创建虚拟环境..."
cd /var/www/pic
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# 7. 恢复 MongoDB 数据
echo "恢复数据库..."
mongorestore --db $DB_NAME /root/$BACKUP_DIR/mongodb_backup/$DB_NAME/

# 验证数据库
echo "验证数据库..."
mongosh $DB_NAME --quiet --eval "db.stats().dataSize"

# 8. 恢复上传文件
echo "恢复上传文件..."
cd /var/www/pic
tar -xzf /root/$BACKUP_DIR/uploads.tar.gz

# 检查 uploads 目录结构是否正确
if [ -d "uploads/var/www/pic/uploads" ]; then
    echo "修正 uploads 路径..."
    mv uploads/var/www/pic/uploads/* uploads/
    rm -rf uploads/var
fi

# 验证文件
echo "上传文件数量: $(find uploads -type f 2>/dev/null | wc -l)"

# 9. 创建必要目录
sudo mkdir -p /var/www/pic/logs
sudo mkdir -p /var/log/supervisor

# 10. 配置 Supervisor
echo "配置 Supervisor..."
sudo tee /etc/supervisor/conf.d/pic.conf > /dev/null << EOF
[program:pic]
directory=/var/www/pic
command=/var/www/pic/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 app:app
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/supervisor/pic-stderr.log
stdout_logfile=/var/log/supervisor/pic-stdout.log
environment=PYTHONPATH="/var/www/pic",MONGO_URI="mongodb://localhost:27017/$DB_NAME"
startsecs=5
stopwaitsecs=5
EOF

# 11. 配置 Nginx
echo "配置 Nginx..."
sudo tee /etc/nginx/sites-available/pic > /dev/null << EOF
server {
    listen 80;
    server_name $DOMAIN_NAME;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
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
EOF

# 12. 设置权限
echo "设置目录权限..."
sudo chown -R www-data:www-data /var/www/pic/logs
sudo chown -R www-data:www-data /var/www/pic/uploads
sudo chmod -R 755 /var/www/pic/logs
sudo chmod -R 755 /var/www/pic/uploads

# 13. 启用 Nginx 站点
sudo ln -sf /etc/nginx/sites-available/pic /etc/nginx/sites-enabled/
sudo nginx -t

# 14. 启动服务
echo "启动服务..."
sudo systemctl restart nginx
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start pic

# 等待服务启动
sleep 3

# 15. 显示服务状态
echo "=========================================="
echo "部署完成！服务状态："
echo "=========================================="
sudo supervisorctl status pic
echo ""
sudo systemctl status nginx --no-pager -l | head -5
echo ""
sudo systemctl status mongod --no-pager -l | head -5
echo "=========================================="
```

#### 步骤 4：验证迁移结果

**在新服务器上继续执行：**

```bash
# 检查服务状态
echo "1. 检查服务状态..."
sudo supervisorctl status pic
sudo systemctl status nginx | grep Active
sudo systemctl status mongod | grep Active

# 检查数据库
echo ""
echo "2. 检查数据库..."
mongo your_database_name --quiet --eval "print('用户数量: ' + db.users.count())"
mongo your_database_name --quiet --eval "print('图片数量: ' + db.images.count())"

# 检查文件
echo ""
echo "3. 检查上传文件..."
echo "文件数量: $(find /var/www/pic/uploads -type f | wc -l)"
echo "文件大小: $(du -sh /var/www/pic/uploads | cut -f1)"

# 测试网站访问
echo ""
echo "4. 测试网站访问..."
curl -I http://localhost 2>/dev/null | head -1
SERVER_IP=$(hostname -I | awk '{print $1}')
echo "服务器 IP: $SERVER_IP"
curl -I http://$SERVER_IP 2>/dev/null | head -1

# 查看最近日志
echo ""
echo "5. 最近的应用日志（最后 10 行）："
sudo tail -10 /var/log/supervisor/pic-stdout.log 2>/dev/null || echo "暂无日志"
```

## ✅ 验证检查清单

完成部署后，请逐项确认：

- [ ] MongoDB 服务运行正常（`sudo systemctl status mongod`）
- [ ] Nginx 服务运行正常（`sudo systemctl status nginx`）
- [ ] 应用进程运行正常（`sudo supervisorctl status pic`）
- [ ] 数据库数据完整（用户数、图片数与旧服务器一致）
- [ ] 上传文件完整（文件数量与旧服务器一致）
- [ ] 可以通过 IP 访问网站（`http://新服务器IP`）
- [ ] 图片可以正常显示
- [ ] 用户可以正常登录

## 🌐 DNS 切换

**重要：只有在新服务器完全正常后才进行 DNS 切换！**

### 在浏览器中测试

1. 在浏览器访问：`http://新服务器IP`
2. 测试登录功能
3. 测试图片显示
4. 测试图片上传

### 切换 DNS

1. 登录阿里云控制台
2. 进入"云解析 DNS"
3. 找到你的域名
4. 修改 A 记录：
   - 主机记录：`@` 或 `www`
   - 记录类型：`A`
   - 记录值：新服务器 IP
   - TTL：`600`（10分钟）
5. 保存并等待生效（通常 5-30 分钟）

### 验证 DNS 生效

在 Windows PowerShell 中：

```powershell
# 查询 DNS 解析
nslookup your_domain.com

# 测试域名访问
curl -I http://your_domain.com
```

## 🔧 常见问题及解决方案

### 1. MongoDB 安装失败：Package 'mongodb' has no installation candidate

**问题**：Ubuntu 22.04 官方仓库没有 mongodb 包

**解决方案**：从 MongoDB 官方仓库安装

```bash
# 添加 MongoDB 7.0 官方仓库
curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | sudo gpg --dearmor -o /usr/share/keyrings/mongodb-server-7.0.gpg
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
sudo apt update
sudo apt install -y mongodb-org
```

### 2. GitHub 克隆失败：GnuTLS recv error (-110)

**问题**：阿里云服务器访问 GitHub 不稳定

**解决方案**：从旧服务器直接复制代码

```bash
# 从旧服务器复制所有代码文件
cd /var/www/pic
scp root@120.79.186.114:/var/www/pic/*.py ./
scp -r root@120.79.186.114:/var/www/pic/{static,templates} ./
```

### 3. 应用启动失败：ModuleNotFoundError: No module named 'utils'

**问题**：缺少 utils.py 等 Python 文件

**解决方案**：确保复制所有 Python 文件

```bash
# 复制所有 Python 文件
cd /var/www/pic
scp root@120.79.186.114:/var/www/pic/*.py ./

# 检查文件
ls -la *.py
# 应该看到：app.py, utils.py, forms.py, models.py 等
```

### 4. 虚拟环境创建失败：ensurepip is not available

**问题**：缺少 python3-venv 包

**解决方案**：

```bash
sudo apt install -y python3.10-venv
```

### 5. Nginx 502 错误

**问题**：应用未正常启动

**解决方案**：

```bash
# 查看错误日志
sudo tail -50 /var/log/supervisor/pic-stderr.log

# 检查应用状态
sudo supervisorctl status pic

# 手动测试应用
cd /var/www/pic
source venv/bin/activate
python app.py

# 重启服务
sudo supervisorctl restart pic
```

### 6. uploads 目录结构错误

**问题**：解压时保留了完整路径 `uploads/var/www/pic/uploads/`

**解决方案**：

```bash
# 检查并修正路径
cd /var/www/pic
if [ -d "uploads/var/www/pic/uploads" ]; then
    mv uploads/var/www/pic/uploads/* uploads/
    rm -rf uploads/var
fi
```

### 7. 图片无法显示

**问题**：权限或路径问题

**解决方案**：

```bash
# 检查文件是否存在
ls -lh /var/www/pic/uploads/ | head -20

# 设置正确权限
sudo chown -R www-data:www-data /var/www/pic/uploads
sudo chmod -R 755 /var/www/pic/uploads

# 重启 Nginx
sudo systemctl restart nginx
```

## 📊 常用管理命令

### 查看服务状态

```bash
# 查看所有服务状态
sudo supervisorctl status pic
sudo systemctl status nginx
sudo systemctl status mongod
```

### 查看日志

```bash
# 实时查看应用日志
sudo tail -f /var/log/supervisor/pic-stdout.log

# 查看错误日志
sudo tail -f /var/log/supervisor/pic-stderr.log

# 查看 Nginx 日志
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### 重启服务

```bash
# 重启应用
sudo supervisorctl restart pic

# 重启 Nginx
sudo systemctl restart nginx

# 重启 MongoDB
sudo systemctl restart mongod
```

## 🔐 迁移后优化

### 1. 配置 HTTPS（推荐）

```bash
# 安装 certbot
sudo apt install certbot python3-certbot-nginx

# 申请证书
sudo certbot --nginx -d your_domain.com

# 自动续期
sudo certbot renew --dry-run
```

### 2. 设置自动备份

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每天凌晨 2 点备份）
0 2 * * * mongodump --db your_database_name --out /backup/mongodb_$(date +\%Y\%m\%d)
0 3 * * * tar -czf /backup/uploads_$(date +\%Y\%m\%d).tar.gz /var/www/pic/uploads
```

### 3. 配置防火墙

```bash
# 允许 HTTP 和 HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

### 4. 优化 MongoDB

```bash
# 创建索引
mongo your_database_name
db.images.createIndex({"user_id": 1})
db.images.createIndex({"created_at": -1})
db.images.createIndex({"tags": 1})
exit
```

## 🚨 回滚方案

如果新服务器出现问题，可以快速回滚：

### 方法 1：DNS 回滚

1. 将 DNS A 记录改回旧服务器 IP
2. 等待 DNS 生效

### 方法 2：重启旧服务器

```powershell
# SSH 登录旧服务器
ssh root@120.79.186.114
```

```bash
# 重启服务
sudo supervisorctl start pic
sudo systemctl start nginx

# 检查状态
sudo supervisorctl status pic
```

## 📝 迁移完成后的清理

**建议保留旧服务器数据 1-2 周，确认新服务器完全正常后再清理。**

### 清理旧服务器（1-2周后）

```bash
# SSH 登录旧服务器
ssh root@120.79.186.114

# 停止服务
sudo supervisorctl stop pic
sudo systemctl stop nginx

# 备份重要数据到本地（可选）
# 然后可以考虑释放服务器资源
```

### 清理新服务器上的备份文件

```bash
# SSH 登录新服务器
ssh root@新服务器IP

# 删除备份文件（确认一切正常后）
rm -rf /root/pic_backup_*
```

## 📝 实际迁移经验总结

### 成功迁移的关键点

1. **MongoDB 安装**
   - Ubuntu 22.04 必须从官方仓库安装 MongoDB 7.0
   - 不能使用 `apt install mongodb`，会报错

2. **代码复制策略**
   - GitHub 访问不稳定，建议直接从旧服务器 scp 复制
   - 必须复制所有 `.py` 文件（app.py, utils.py, forms.py, models.py 等）
   - 使用 `scp -r root@OLD_IP:/var/www/pic/{static,templates} ./` 一次性复制多个目录

3. **依赖安装**
   - 需要安装 `python3.10-venv` 而不是 `python3-venv`
   - 虚拟环境创建前确保包已安装

4. **数据恢复**
   - MongoDB 数据恢复使用 `mongorestore` 命令
   - 使用 `mongosh` 而不是旧的 `mongo` 命令验证数据
   - uploads 目录解压后检查路径结构

5. **服务配置**
   - Supervisor 配置中 MONGO_URI 要正确
   - Nginx 配置中 `$` 符号需要转义为 `\$`
   - 权限设置：logs 和 uploads 目录归 www-data 用户

### 实际遇到的问题及耗时

| 问题 | 耗时 | 解决方案 |
|------|------|----------|
| MongoDB 包不存在 | 5分钟 | 添加官方仓库 |
| GitHub 克隆失败 | 3分钟 | 改用 scp 从旧服务器复制 |
| 缺少 utils.py | 2分钟 | 补充复制所有 .py 文件 |
| python3-venv 错误 | 2分钟 | 安装 python3.10-venv |
| 应用启动失败 | 3分钟 | 检查日志，发现缺少文件 |

**总耗时**：约 40 分钟（包含问题排查）

### 验证成功的标志

```bash
# 所有服务都应该是 RUNNING/active 状态
sudo supervisorctl status pic
# pic                              RUNNING   pid 26547, uptime 0:00:08

# HTTP 返回 200 OK
curl -I http://localhost
# HTTP/1.1 200 OK

# 数据完整
mongosh your_database_name --quiet --eval "db.images.count()"
# 1958

find /var/www/pic/uploads -type f | wc -l
# 1970
```

## 🎉 完成

恭喜！你已经成功完成服务器迁移。

**下一步建议：**

1. ✅ 在浏览器测试所有功能（登录、上传、浏览）
2. ✅ 监控新服务器运行状态 24-48 小时
3. ✅ 配置 HTTPS 证书（使用 certbot）
4. ✅ 设置自动备份（crontab）
5. ✅ 切换 DNS 到新服务器
6. ✅ 保留旧服务器 1-2 周作为备份
7. ✅ 优化数据库性能（创建索引）

**迁移完成检查清单：**

- [x] MongoDB 服务运行正常
- [x] 应用服务运行正常  
- [x] Nginx 服务运行正常
- [x] 数据库数据完整（1959 条记录）
- [x] 上传文件完整（1970 个文件）
- [x] 网站可以通过 IP 访问
- [ ] 网站可以通过域名访问（DNS 切换后）
- [ ] HTTPS 配置完成
- [ ] 自动备份配置完成

如有问题，请查看日志文件或参考常见问题部分。
