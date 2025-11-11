#!/bin/bash

# 新服务器部署脚本
# 用途：在新服务器上恢复数据并启动服务

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# 配置变量
PROJECT_PATH="/var/www/pic"
DB_NAME="your_database_name"  # 请修改为实际的数据库名称
DOMAIN_NAME="your_domain.com"  # 请修改为实际的域名
GIT_REPO="https://github.com/chf1117/pic_share.git"

# 查找最新的备份目录
BACKUP_DIR=$(ls -td /root/pic_backup_* 2>/dev/null | head -1)

if [ -z "$BACKUP_DIR" ]; then
    log_error "未找到备份目录！"
    log_error "请确保已经运行了 migrate.sh 脚本并传输了数据"
    exit 1
fi

log_info "=========================================="
log_info "图片分享平台新服务器部署脚本"
log_info "=========================================="
log_info "备份目录: ${BACKUP_DIR}"
log_info "项目路径: ${PROJECT_PATH}"
log_info "数据库名: ${DB_NAME}"
log_info "域名: ${DOMAIN_NAME}"
log_info "=========================================="

# 显示迁移清单
if [ -f "${BACKUP_DIR}/migration_manifest.txt" ]; then
    log_info "迁移清单："
    cat "${BACKUP_DIR}/migration_manifest.txt"
    echo ""
fi

# 确认操作
read -p "是否继续部署？(y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_warn "部署已取消"
    exit 0
fi

# 步骤1：检查并安装系统依赖
log_step "步骤1: 检查系统依赖..."

check_command() {
    if ! command -v $1 &> /dev/null; then
        log_warn "$1 未安装"
        return 1
    else
        log_info "$1 已安装"
        return 0
    fi
}

# 检查必要的命令
MISSING_DEPS=0
for cmd in python3 pip3 nginx supervisorctl mongod git; do
    if ! check_command $cmd; then
        MISSING_DEPS=1
    fi
done

if [ $MISSING_DEPS -eq 1 ]; then
    log_warn "检测到缺失的依赖，开始安装..."
    sudo apt update
    sudo apt install -y python3-pip python3-venv nginx supervisor git mongodb
    sudo apt install -y python3-dev build-essential libssl-dev libffi-dev
    log_info "依赖安装完成"
fi

# 启动 MongoDB
log_info "启动 MongoDB 服务..."
sudo systemctl start mongod
sudo systemctl enable mongod
sleep 2

# 检查 MongoDB 状态
if ! sudo systemctl is-active --quiet mongod; then
    log_error "MongoDB 启动失败！"
    exit 1
fi
log_info "MongoDB 运行正常"

# 步骤2：创建项目目录并克隆代码
log_step "步骤2: 设置项目目录..."

if [ -d "$PROJECT_PATH" ]; then
    log_warn "项目目录已存在，备份旧目录..."
    sudo mv "$PROJECT_PATH" "${PROJECT_PATH}_backup_$(date +%Y%m%d_%H%M%S)"
fi

log_info "创建项目目录..."
sudo mkdir -p "$PROJECT_PATH"
sudo chown -R $USER:$USER "$PROJECT_PATH"

log_info "克隆代码仓库..."
git clone "$GIT_REPO" "$PROJECT_PATH"

# 步骤3：创建虚拟环境并安装依赖
log_step "步骤3: 设置 Python 环境..."

cd "$PROJECT_PATH"
log_info "创建虚拟环境..."
python3 -m venv venv

log_info "安装 Python 依赖..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# 步骤4：恢复 MongoDB 数据
log_step "步骤4: 恢复 MongoDB 数据..."

if [ -d "${BACKUP_DIR}/mongodb_backup/${DB_NAME}" ]; then
    log_info "恢复数据库: ${DB_NAME}"
    mongorestore --db ${DB_NAME} "${BACKUP_DIR}/mongodb_backup/${DB_NAME}/"
    
    # 验证数据恢复
    log_info "验证数据库恢复..."
    IMAGES_COUNT=$(mongo ${DB_NAME} --quiet --eval "db.images.count()")
    USERS_COUNT=$(mongo ${DB_NAME} --quiet --eval "db.users.count()")
    log_info "图片数量: ${IMAGES_COUNT}"
    log_info "用户数量: ${USERS_COUNT}"
else
    log_error "未找到 MongoDB 备份数据！"
    exit 1
fi

# 步骤5：恢复上传的图片文件
log_step "步骤5: 恢复上传文件..."

if [ -f "${BACKUP_DIR}/uploads.tar.gz" ]; then
    log_info "解压上传文件..."
    cd "$PROJECT_PATH"
    tar -xzf "${BACKUP_DIR}/uploads.tar.gz"
    
    # 验证文件数量
    FILES_COUNT=$(find uploads -type f 2>/dev/null | wc -l)
    log_info "恢复文件数量: ${FILES_COUNT}"
else
    log_warn "未找到上传文件备份，创建空目录..."
    mkdir -p "$PROJECT_PATH/uploads"
fi

# 步骤6：创建必要的目录
log_step "步骤6: 创建必要的目录..."

sudo mkdir -p "$PROJECT_PATH/logs"
sudo mkdir -p /var/log/supervisor

# 步骤7：配置 Supervisor
log_step "步骤7: 配置 Supervisor..."

SUPERVISOR_CONF="/etc/supervisor/conf.d/pic.conf"
log_info "创建 Supervisor 配置文件..."

sudo tee "$SUPERVISOR_CONF" > /dev/null << EOF
[program:pic] 
directory=${PROJECT_PATH}
command=${PROJECT_PATH}/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 app:app 
user=www-data 
autostart=true 
autorestart=true 
stderr_logfile=/var/log/supervisor/pic-stderr.log 
stdout_logfile=/var/log/supervisor/pic-stdout.log 
environment=PYTHONPATH="${PROJECT_PATH}",MONGO_URI="mongodb://localhost:27017/${DB_NAME}" 
startsecs=5
stopwaitsecs=5
EOF

log_info "Supervisor 配置完成"

# 步骤8：配置 Nginx
log_step "步骤8: 配置 Nginx..."

NGINX_CONF="/etc/nginx/sites-available/pic"
log_info "创建 Nginx 配置文件..."

sudo tee "$NGINX_CONF" > /dev/null << EOF
server {
    listen 80;
    server_name ${DOMAIN_NAME};

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        client_max_body_size 10M;
    }

    location /static {
        alias ${PROJECT_PATH}/static;
    }

    location /uploads {
        alias ${PROJECT_PATH}/uploads;
        expires 14d;
        add_header Cache-Control "public, no-transform";
    }
}
EOF

# 启用站点
log_info "启用 Nginx 站点..."
sudo ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/pic

# 测试 Nginx 配置
log_info "测试 Nginx 配置..."
if sudo nginx -t; then
    log_info "Nginx 配置正确"
else
    log_error "Nginx 配置错误！"
    exit 1
fi

# 步骤9：设置目录权限
log_step "步骤9: 设置目录权限..."

sudo chown -R www-data:www-data "$PROJECT_PATH/logs"
sudo chown -R www-data:www-data "$PROJECT_PATH/uploads"
sudo chmod -R 755 "$PROJECT_PATH/logs"
sudo chmod -R 755 "$PROJECT_PATH/uploads"
sudo chown -R www-data:www-data /var/log/supervisor

log_info "权限设置完成"

# 步骤10：启动服务
log_step "步骤10: 启动服务..."

log_info "重新加载 Supervisor 配置..."
sudo supervisorctl reread
sudo supervisorctl update

log_info "启动应用..."
sudo supervisorctl start pic

log_info "重启 Nginx..."
sudo systemctl restart nginx

# 等待服务启动
sleep 3

# 步骤11：验证服务状态
log_step "步骤11: 验证服务状态..."

log_info "检查服务状态..."
echo ""
echo "=== Supervisor 状态 ==="
sudo supervisorctl status pic
echo ""

echo "=== Nginx 状态 ==="
sudo systemctl status nginx --no-pager -l
echo ""

echo "=== MongoDB 状态 ==="
sudo systemctl status mongod --no-pager -l
echo ""

# 测试本地访问
log_info "测试本地访问..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost | grep -q "200\|302"; then
    log_info "本地访问测试成功！"
else
    log_warn "本地访问测试失败，请检查日志"
fi

# 步骤12：显示日志位置
log_step "步骤12: 日志文件位置"

echo ""
echo "=== 日志文件位置 ==="
echo "应用日志: ${PROJECT_PATH}/logs/pic_app.log"
echo "Supervisor stdout: /var/log/supervisor/pic-stdout.log"
echo "Supervisor stderr: /var/log/supervisor/pic-stderr.log"
echo "Nginx access: /var/log/nginx/access.log"
echo "Nginx error: /var/log/nginx/error.log"
echo ""

# 显示最近的错误日志
log_info "最近的应用日志（最后10行）："
sudo tail -10 /var/log/supervisor/pic-stderr.log 2>/dev/null || echo "暂无错误日志"

# 完成
log_info "=========================================="
log_info "部署完成！"
log_info "=========================================="
log_info ""
log_info "下一步操作："
log_info "1. 测试网站访问："
log_info "   curl -I http://localhost"
log_info "   curl -I http://$(hostname -I | awk '{print $1}')"
log_info ""
log_info "2. 查看实时日志："
log_info "   sudo tail -f /var/log/supervisor/pic-stdout.log"
log_info ""
log_info "3. 更新 DNS 记录，将域名指向新服务器 IP"
log_info ""
log_info "4. 配置 HTTPS（可选）："
log_info "   sudo apt install certbot python3-certbot-nginx"
log_info "   sudo certbot --nginx -d ${DOMAIN_NAME}"
log_info ""
log_info "5. 设置自动备份（推荐）："
log_info "   参考 docs/deployment.md 中的备份策略"
log_info ""
log_info "=========================================="

# 询问是否查看日志
read -p "是否查看实时日志？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "按 Ctrl+C 退出日志查看"
    sleep 2
    sudo tail -f /var/log/supervisor/pic-stdout.log
fi
