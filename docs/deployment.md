# 部署指南

本文档介绍如何将图片分享平台部署到 Ubuntu 服务器上。

## 前置要求

- Ubuntu 服务器 (推荐 Ubuntu 20.04 LTS 或更高版本)
- Python 3.8+
- Nginx
- Supervisor (用于进程管理)
- Git

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
sudo apt install -y python3-pip python3-venv nginx supervisor git

# 安装 Python 开发包
sudo apt install -y python3-dev build-essential libssl-dev libffi-dev
```

### 2. 创建项目目录和虚拟环境

```bash
# 创建项目目录
sudo mkdir -p /var/www/pic
sudo chown -R $USER:$USER /var/www/pic

# 克隆项目
git clone [你的项目Git地址] /var/www/pic

# 创建虚拟环境
cd /var/www/pic
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
pip install gunicorn  # 用于生产环境的WSGI服务器
```

### 3. 配置 Supervisor

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
stderr_logfile=/var/log/pic/pic.err.log
stdout_logfile=/var/log/pic/pic.out.log

[supervisord]
logfile=/var/log/supervisor/supervisord.log
pidfile=/var/run/supervisord.pid
childlogdir=/var/log/supervisor
```

创建日志目录：

```bash
sudo mkdir -p /var/log/pic
sudo chown -R www-data:www-data /var/log/pic
```

### 4. 配置 Nginx

创建 Nginx 配置文件：

```bash
sudo nano /etc/nginx/sites-available/pic
```

添加以下内容：

```nginx
server {
    listen 80;
    server_name your_domain.com;  # 替换为你的域名

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /static {
        alias /var/www/pic/static;
    }

    location /uploads {
        alias /var/www/pic/uploads;
        client_max_body_size 10M;  # 允许上传的最大文件大小
    }
}
```

启用站点：

```bash
sudo ln -s /etc/nginx/sites-available/pic /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default  # 删除默认站点
sudo nginx -t  # 测试配置
sudo systemctl restart nginx
```

### 5. 启动服务

```bash
# 重新加载 Supervisor 配置
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start pic

# 检查状态
sudo supervisorctl status pic
```

### 6. 配置防火墙

```bash
# 允许 HTTP 和 HTTPS 流量
sudo ufw allow 80
sudo ufw allow 443
```

## 访问项目

部署完成后，可以通过以下方式访问项目：

### 1. 使用域名访问（推荐）
1. 购买域名（如通过 Godaddy、Namecheap 等）
2. 将域名解析到你的服务器IP
3. 在 Nginx 配置中设置域名：
   ```nginx
   server {
       listen 80;
       server_name your_domain.com;  # 替换为你的实际域名
       ...
   }
   ```
4. 访问地址：
   - HTTP: `http://your_domain.com`
   - HTTPS: `https://your_domain.com` (配置 SSL 证书后)

### 2. 使用IP直接访问
1. 确保服务器防火墙允许 80 端口访问
2. 访问地址：`http://你的服务器IP`

### 3. 端口说明
- 生产环境：
  - 外部访问使用 80/443 端口（由 Nginx 处理）
  - 内部 Gunicorn 运行在 8000 端口
  - 无需手动访问 8000 端口
- 本地开发：
  - 直接访问 5000 端口
  - 例如：`http://localhost:5000`

注意：
- 建议使用域名 + HTTPS 的方式，这样更安全也更专业
- 如果要启用 HTTPS，需要按照上述安全建议中的步骤配置 SSL 证书
- 不要直接对外暴露 8000 端口，所有外部访问都应该通过 Nginx 代理

## 维护指南

### 更新代码

```bash
cd /var/www/pic
source venv/bin/activate
git pull
pip install -r requirements.txt
sudo supervisorctl restart pic
```

### 查看日志

- 应用日志：
  ```bash
  sudo tail -f /var/log/pic/pic.out.log  # 标准输出
  sudo tail -f /var/log/pic/pic.err.log  # 错误日志
  ```

- Nginx 日志：
  ```bash
  sudo tail -f /var/log/nginx/access.log
  sudo tail -f /var/log/nginx/error.log
  ```

### 常见问题排查

1. 如果网站无法访问：
   - 检查 Supervisor 状态：`sudo supervisorctl status pic`
   - 检查 Nginx 状态：`sudo systemctl status nginx`
   - 检查应用日志：`sudo tail -f /var/log/pic/pic.err.log`

2. 如果上传失败：
   - 检查目录权限：`ls -la /var/www/pic/uploads`
   - 检查 Nginx 上传限制：`client_max_body_size` 设置

3. 如果静态文件无法加载：
   - 检查 Nginx 配置中的静态文件路径
   - 确保静态文件存在且权限正确

## 安全建议

1. 启用 HTTPS：
   ```bash
   # 安装 Certbot
   sudo apt install -y certbot python3-certbot-nginx
   
   # 获取并安装证书
   sudo certbot --nginx -d your_domain.com
   ```

2. 定期更新系统：
   ```bash
   sudo apt update
   sudo apt upgrade
   ```

3. 配置防火墙规则：
   ```bash
   sudo ufw enable
   sudo ufw default deny incoming
   sudo ufw default allow outgoing
   sudo ufw allow ssh
   sudo ufw allow http
   sudo ufw allow https
   ```

4. 设置文件权限：
   ```bash
   sudo chown -R www-data:www-data /var/www/pic/uploads
   sudo chmod -R 755 /var/www/pic/static
   ```

## 备份策略

1. 数据库备份：
   ```bash
   # 创建备份目录
   sudo mkdir -p /var/backups/pic
   
   # 设置定时备份（每天凌晨2点）
   sudo crontab -e
   0 2 * * * sqlite3 /var/www/pic/instance/pic.db ".backup '/var/backups/pic/pic_$(date +\%Y\%m\%d).db'"
   ```

2. 上传文件备份：
   ```bash
   # 备份上传的图片
   sudo rsync -av /var/www/pic/uploads/ /var/backups/pic/uploads/
   ```

## 性能优化建议

1. 配置 Gunicorn 工作进程：
   - 建议设置为 CPU 核心数 * 2
   - 在 supervisor 配置中调整 `-w` 参数

2. 配置 Nginx 缓存：
   ```nginx
   location /static {
       expires 30d;
       add_header Cache-Control "public, no-transform";
   }
   ```

3. 启用 Gzip 压缩：
   ```nginx
   gzip on;
   gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
   ```
