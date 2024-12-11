# 部署指南

本文档介绍如何将图片分享平台部署到 Ubuntu 服务器上。

## 前置要求

- Ubuntu 服务器 (推荐 Ubuntu 20.04 LTS 或更高版本)
- Python 3.8+
- Nginx
- Supervisor (用于进程管理)
- Git
- MongoDB 4.4

## 端口配置说明

项目使用多层架构部署：

1. Nginx（前端代理）
   - 监听 80 端口（HTTP）
   - 监听 443 端口（HTTPS，如果配置）
   - 作为反向代理，将请求转发到 Gunicorn

2. Gunicorn（WSGI 服务器）
   - 监听 127.0.0.1:8000（本地回环地址）
   - 处理来自 Nginx 的请求
   - 运行 Flask 应用

3. Flask 应用
   - 本地开发环境：直接运行在 5000 端口
   - 生产环境：通过 Gunicorn 运行

### 端口流程图
```
外部访问 -> Nginx(80/443) -> Gunicorn(8000) -> Flask 应用
```

## 部署步骤

### 1. 安装系统依赖

```bash
# 更新系统包
sudo apt update
sudo apt upgrade -y

# 安装必要的系统包
sudo apt install -y python3-pip python3-venv nginx supervisor git mongodb

# 安装 Python 开发包
sudo apt install -y python3-dev build-essential libssl-dev libffi-dev
```

### 2. 创建项目目录和虚拟环境

```bash
# 创建项目目录
sudo mkdir -p /var/www/pic
sudo chown -R $USER:$USER /var/www/pic

# 克隆项目
git clone https://github.com/chf1117/pic_share.git /var/www/pic

# 创建虚拟环境
cd /var/www/pic
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置目录权限

```bash
# 创建并设置日志目录权限
sudo mkdir -p /var/www/pic/logs
sudo chown -R www-data:www-data /var/www/pic/logs
sudo chmod 755 /var/www/pic/logs

# 创建supervisor日志目录
sudo mkdir -p /var/log/supervisor
sudo chown -R www-data:www-data /var/log/supervisor

# 设置项目目录权限
sudo chown -R www-data:www-data /var/www/pic
sudo chmod -R 755 /var/www/pic
```

### 4. 配置 MongoDB

```bash
# 启动MongoDB服务
sudo systemctl start mongod
sudo systemctl enable mongod

# 验证MongoDB状态
sudo systemctl status mongod
```

### 5. 配置 Supervisor

创建 Supervisor 配置文件：

```bash
sudo nano /etc/supervisor/conf.d/pic.conf
```

添加以下内容：

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

### 6. 配置 Nginx

创建 Nginx 配置文件：

```bash
sudo nano /etc/nginx/sites-available/pic
```

添加以下内容：

```nginx
server {
    listen 80;
    server_name your_domain.com;  # 替换为实际域名

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 文件上传大小限制
        client_max_body_size 10M;
    }

    # 静态文件处理
    location /static {
        alias /var/www/pic/static;
    }

    # 上传文件处理
    location /uploads {
        alias /var/www/pic/uploads;
        expires 14d;
        add_header Cache-Control "public, no-transform";
    }
}
```

启用站点：

```bash
sudo ln -s /etc/nginx/sites-available/pic /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 7. 启动服务

```bash
# 重新加载supervisor配置
sudo supervisorctl reread
sudo supervisorctl update

# 启动服务
sudo supervisorctl restart pic

# 检查状态
sudo supervisorctl status pic
```

### 8. 日志查看

```bash
# 查看supervisor日志
sudo tail -f /var/log/supervisor/pic-stderr.log
sudo tail -f /var/log/supervisor/pic-stdout.log

# 查看应用日志
sudo tail -f /var/www/pic/logs/pic_app.log
```

## 维护和故障排除

### 1. 服务重启

```bash
# 重启应用
sudo supervisorctl restart pic

# 重启Nginx
sudo systemctl restart nginx

# 重启MongoDB
sudo systemctl restart mongod
```

### 2. 日志检查

```bash
# 检查supervisor错误日志
sudo cat /var/log/supervisor/pic-stderr.log

# 检查supervisor输出日志
sudo cat /var/log/supervisor/pic-stdout.log

# 检查应用日志
sudo cat /var/www/pic/logs/pic_app.log
```

### 3. 备份和恢复

```bash
# 备份MongoDB数据
mongodump --out backup_$(date +%Y%m%d)

# 备份上传的图片
cp -r /var/www/pic/uploads uploads_backup_$(date +%Y%m%d)

# 恢复MongoDB数据
mongorestore backup_[timestamp]

# 恢复图片文件
cp -r uploads_backup_[timestamp]/* /var/www/pic/uploads/
```

## 注意事项

1. 确保所有目录权限正确设置
2. 定期检查日志文件大小，避免磁盘空间耗尽
3. 定期备份数据库和图片文件
4. 更新代码后需要重启supervisor服务
5. 确保MongoDB服务正常运行
