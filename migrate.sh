#!/bin/bash

# 服务器迁移脚本 - 旧服务器端
# 用途：在旧服务器上备份所有数据并传输到新服务器

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# 配置变量
OLD_SERVER_USER="root"
OLD_SERVER_HOST="120.79.186.114"
OLD_SERVER_PATH="/var/www/pic"
DB_NAME="your_database_name"  # 请修改为实际的数据库名称

# 新服务器配置（需要用户填写）
NEW_SERVER_USER="${NEW_SERVER_USER:-root}"
NEW_SERVER_HOST="${NEW_SERVER_HOST}"
NEW_SERVER_PATH="/var/www/pic"

# 检查是否提供了新服务器地址
if [ -z "$NEW_SERVER_HOST" ]; then
    log_error "请设置新服务器地址："
    echo "export NEW_SERVER_HOST='新服务器IP'"
    echo "export NEW_SERVER_USER='root'  # 可选，默认为root"
    echo "然后重新运行此脚本"
    exit 1
fi

# 创建备份目录
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/root/pic_backup_${TIMESTAMP}"

log_info "=========================================="
log_info "图片分享平台服务器迁移脚本"
log_info "=========================================="
log_info "旧服务器: ${OLD_SERVER_HOST}"
log_info "新服务器: ${NEW_SERVER_HOST}"
log_info "备份目录: ${BACKUP_DIR}"
log_info "=========================================="

# 确认操作
read -p "是否继续迁移？这将停止旧服务器上的服务。(y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_warn "迁移已取消"
    exit 0
fi

# 步骤1：在旧服务器上备份数据
log_info "步骤1: 在旧服务器上备份数据..."

ssh ${OLD_SERVER_USER}@${OLD_SERVER_HOST} << EOF
    set -e
    
    echo "创建备份目录..."
    mkdir -p ${BACKUP_DIR}
    
    echo "停止应用服务..."
    sudo supervisorctl stop pic || echo "服务可能已经停止"
    
    echo "备份 MongoDB 数据库..."
    mongodump --db ${DB_NAME} --out ${BACKUP_DIR}/mongodb_backup
    
    echo "打包上传的图片文件..."
    cd ${OLD_SERVER_PATH}
    tar -czf ${BACKUP_DIR}/uploads.tar.gz uploads/
    
    echo "备份配置文件..."
    sudo cp /etc/nginx/sites-available/pic ${BACKUP_DIR}/nginx_pic.conf || echo "Nginx配置文件不存在"
    sudo cp /etc/supervisor/conf.d/pic.conf ${BACKUP_DIR}/supervisor_pic.conf || echo "Supervisor配置文件不存在"
    
    echo "备份日志文件..."
    tar -czf ${BACKUP_DIR}/logs.tar.gz logs/ || echo "日志目录不存在"
    
    echo "创建迁移清单..."
    cat > ${BACKUP_DIR}/migration_manifest.txt << MANIFEST
备份时间: \$(date)
旧服务器: ${OLD_SERVER_HOST}
新服务器: ${NEW_SERVER_HOST}
数据库名称: ${DB_NAME}
项目路径: ${OLD_SERVER_PATH}
上传文件数量: \$(find ${OLD_SERVER_PATH}/uploads -type f 2>/dev/null | wc -l)
上传文件大小: \$(du -sh ${OLD_SERVER_PATH}/uploads 2>/dev/null | cut -f1)
MongoDB 大小: \$(du -sh ${BACKUP_DIR}/mongodb_backup 2>/dev/null | cut -f1)
MANIFEST
    
    echo "备份完成！"
    ls -lh ${BACKUP_DIR}
    cat ${BACKUP_DIR}/migration_manifest.txt
EOF

if [ $? -ne 0 ]; then
    log_error "备份失败！"
    exit 1
fi

log_info "步骤1完成：数据备份成功"

# 步骤2：压缩并传输数据到新服务器
log_info "步骤2: 传输数据到新服务器..."

ssh ${OLD_SERVER_USER}@${OLD_SERVER_HOST} << EOF
    cd /root
    echo "压缩备份目录..."
    tar -czf pic_backup_${TIMESTAMP}.tar.gz pic_backup_${TIMESTAMP}/
    echo "压缩完成"
    ls -lh pic_backup_${TIMESTAMP}.tar.gz
EOF

log_info "开始传输数据（这可能需要一些时间）..."
ssh ${OLD_SERVER_USER}@${OLD_SERVER_HOST} "cat /root/pic_backup_${TIMESTAMP}.tar.gz" | \
    ssh ${NEW_SERVER_USER}@${NEW_SERVER_HOST} "cat > /root/pic_backup_${TIMESTAMP}.tar.gz"

if [ $? -ne 0 ]; then
    log_error "数据传输失败！"
    exit 1
fi

log_info "步骤2完成：数据传输成功"

# 步骤3：在新服务器上解压和准备
log_info "步骤3: 在新服务器上解压数据..."

ssh ${NEW_SERVER_USER}@${NEW_SERVER_HOST} << EOF
    set -e
    
    cd /root
    echo "解压备份文件..."
    tar -xzf pic_backup_${TIMESTAMP}.tar.gz
    
    echo "验证备份内容..."
    ls -lh pic_backup_${TIMESTAMP}/
    
    echo "显示迁移清单..."
    cat pic_backup_${TIMESTAMP}/migration_manifest.txt
EOF

if [ $? -ne 0 ]; then
    log_error "解压失败！"
    exit 1
fi

log_info "步骤3完成：数据解压成功"

# 步骤4：提示用户下一步操作
log_info "=========================================="
log_info "数据传输完成！"
log_info "=========================================="
log_info "备份文件位置: /root/pic_backup_${TIMESTAMP}"
log_info ""
log_info "接下来请按照以下步骤在新服务器上完成部署："
log_info ""
log_info "1. 登录新服务器："
log_info "   ssh ${NEW_SERVER_USER}@${NEW_SERVER_HOST}"
log_info ""
log_info "2. 运行新服务器部署脚本："
log_info "   bash /root/pic_backup_${TIMESTAMP}/setup_new_server.sh"
log_info ""
log_info "或者手动执行以下步骤："
log_info "   - 克隆代码仓库"
log_info "   - 恢复 MongoDB 数据"
log_info "   - 恢复上传文件"
log_info "   - 配置 Nginx 和 Supervisor"
log_info "   - 启动服务"
log_info ""
log_info "详细步骤请参考: docs/migration_guide.md"
log_info "=========================================="

# 询问是否要保持旧服务器停止状态
read -p "是否重启旧服务器上的服务？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    log_info "重启旧服务器服务..."
    ssh ${OLD_SERVER_USER}@${OLD_SERVER_HOST} "sudo supervisorctl start pic"
    log_info "旧服务器服务已重启"
else
    log_warn "旧服务器服务保持停止状态"
fi

log_info "迁移脚本执行完成！"
