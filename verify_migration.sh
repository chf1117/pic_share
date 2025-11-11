#!/bin/bash

# 迁移验证脚本
# 用途：验证新服务器上的服务是否正常运行

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置变量
PROJECT_PATH="/var/www/pic"
DB_NAME="your_database_name"
DOMAIN_NAME="your_domain.com"

# 测试结果统计
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

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

log_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

# 测试函数
test_pass() {
    echo -e "${GREEN}✓ PASS${NC} $1"
    PASSED_TESTS=$((PASSED_TESTS + 1))
}

test_fail() {
    echo -e "${RED}✗ FAIL${NC} $1"
    FAILED_TESTS=$((FAILED_TESTS + 1))
}

run_test() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    log_test "$1"
}

# 开始验证
log_info "=========================================="
log_info "服务器迁移验证脚本"
log_info "=========================================="
log_info "项目路径: ${PROJECT_PATH}"
log_info "数据库名: ${DB_NAME}"
log_info "域名: ${DOMAIN_NAME}"
log_info "=========================================="
echo ""

# 1. 检查系统服务
log_info "=== 1. 系统服务检查 ==="
echo ""

run_test "MongoDB 服务状态"
if sudo systemctl is-active --quiet mongod; then
    test_pass "MongoDB 服务运行正常"
else
    test_fail "MongoDB 服务未运行"
fi

run_test "Nginx 服务状态"
if sudo systemctl is-active --quiet nginx; then
    test_pass "Nginx 服务运行正常"
else
    test_fail "Nginx 服务未运行"
fi

run_test "Supervisor 服务状态"
if sudo systemctl is-active --quiet supervisor; then
    test_pass "Supervisor 服务运行正常"
else
    test_fail "Supervisor 服务未运行"
fi

run_test "应用进程状态"
if sudo supervisorctl status pic | grep -q "RUNNING"; then
    test_pass "应用进程运行正常"
else
    test_fail "应用进程未运行"
fi

echo ""

# 2. 检查目录和文件
log_info "=== 2. 目录和文件检查 ==="
echo ""

run_test "项目目录存在"
if [ -d "$PROJECT_PATH" ]; then
    test_pass "项目目录存在: $PROJECT_PATH"
else
    test_fail "项目目录不存在: $PROJECT_PATH"
fi

run_test "虚拟环境存在"
if [ -d "$PROJECT_PATH/venv" ]; then
    test_pass "虚拟环境存在"
else
    test_fail "虚拟环境不存在"
fi

run_test "上传目录存在"
if [ -d "$PROJECT_PATH/uploads" ]; then
    UPLOAD_COUNT=$(find "$PROJECT_PATH/uploads" -type f 2>/dev/null | wc -l)
    test_pass "上传目录存在，文件数量: $UPLOAD_COUNT"
else
    test_fail "上传目录不存在"
fi

run_test "日志目录存在"
if [ -d "$PROJECT_PATH/logs" ]; then
    test_pass "日志目录存在"
else
    test_fail "日志目录不存在"
fi

run_test "应用文件存在"
if [ -f "$PROJECT_PATH/app.py" ]; then
    test_pass "应用文件存在"
else
    test_fail "应用文件不存在"
fi

echo ""

# 3. 检查数据库
log_info "=== 3. 数据库检查 ==="
echo ""

run_test "MongoDB 连接"
if mongo --eval "db.version()" > /dev/null 2>&1; then
    test_pass "MongoDB 连接成功"
    
    run_test "数据库存在"
    if mongo --eval "db.getName()" $DB_NAME > /dev/null 2>&1; then
        test_pass "数据库存在: $DB_NAME"
        
        # 检查集合
        run_test "用户集合"
        USER_COUNT=$(mongo $DB_NAME --quiet --eval "db.users.count()" 2>/dev/null || echo "0")
        if [ "$USER_COUNT" -gt 0 ]; then
            test_pass "用户数量: $USER_COUNT"
        else
            test_warn "用户数量为 0"
        fi
        
        run_test "图片集合"
        IMAGE_COUNT=$(mongo $DB_NAME --quiet --eval "db.images.count()" 2>/dev/null || echo "0")
        if [ "$IMAGE_COUNT" -gt 0 ]; then
            test_pass "图片数量: $IMAGE_COUNT"
        else
            test_warn "图片数量为 0"
        fi
    else
        test_fail "数据库不存在: $DB_NAME"
    fi
else
    test_fail "MongoDB 连接失败"
fi

echo ""

# 4. 检查配置文件
log_info "=== 4. 配置文件检查 ==="
echo ""

run_test "Nginx 配置文件"
if [ -f "/etc/nginx/sites-available/pic" ]; then
    test_pass "Nginx 配置文件存在"
    
    run_test "Nginx 配置语法"
    if sudo nginx -t > /dev/null 2>&1; then
        test_pass "Nginx 配置语法正确"
    else
        test_fail "Nginx 配置语法错误"
    fi
else
    test_fail "Nginx 配置文件不存在"
fi

run_test "Supervisor 配置文件"
if [ -f "/etc/supervisor/conf.d/pic.conf" ]; then
    test_pass "Supervisor 配置文件存在"
else
    test_fail "Supervisor 配置文件不存在"
fi

echo ""

# 5. 检查网络访问
log_info "=== 5. 网络访问检查 ==="
echo ""

run_test "本地端口 8000 (Gunicorn)"
if netstat -tlnp 2>/dev/null | grep -q ":8000"; then
    test_pass "端口 8000 正在监听"
else
    test_fail "端口 8000 未监听"
fi

run_test "本地端口 80 (Nginx)"
if netstat -tlnp 2>/dev/null | grep -q ":80"; then
    test_pass "端口 80 正在监听"
else
    test_fail "端口 80 未监听"
fi

run_test "本地 HTTP 访问"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
    test_pass "本地 HTTP 访问成功 (HTTP $HTTP_CODE)"
else
    test_fail "本地 HTTP 访问失败 (HTTP $HTTP_CODE)"
fi

run_test "服务器 IP 访问"
SERVER_IP=$(hostname -I | awk '{print $1}')
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://$SERVER_IP 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
    test_pass "服务器 IP 访问成功 (HTTP $HTTP_CODE)"
else
    test_fail "服务器 IP 访问失败 (HTTP $HTTP_CODE)"
fi

echo ""

# 6. 检查日志文件
log_info "=== 6. 日志文件检查 ==="
echo ""

run_test "Supervisor stdout 日志"
if [ -f "/var/log/supervisor/pic-stdout.log" ]; then
    LOG_SIZE=$(du -h /var/log/supervisor/pic-stdout.log | cut -f1)
    test_pass "日志文件存在，大小: $LOG_SIZE"
else
    test_warn "日志文件不存在"
fi

run_test "Supervisor stderr 日志"
if [ -f "/var/log/supervisor/pic-stderr.log" ]; then
    LOG_SIZE=$(du -h /var/log/supervisor/pic-stderr.log | cut -f1)
    ERROR_COUNT=$(wc -l < /var/log/supervisor/pic-stderr.log)
    if [ "$ERROR_COUNT" -gt 0 ]; then
        test_warn "错误日志有 $ERROR_COUNT 行，请检查"
    else
        test_pass "无错误日志"
    fi
else
    test_warn "错误日志文件不存在"
fi

run_test "应用日志"
if [ -f "$PROJECT_PATH/logs/pic_app.log" ]; then
    LOG_SIZE=$(du -h $PROJECT_PATH/logs/pic_app.log | cut -f1)
    test_pass "应用日志存在，大小: $LOG_SIZE"
else
    test_warn "应用日志不存在"
fi

echo ""

# 7. 检查权限
log_info "=== 7. 权限检查 ==="
echo ""

run_test "上传目录权限"
if [ -d "$PROJECT_PATH/uploads" ]; then
    OWNER=$(stat -c '%U:%G' "$PROJECT_PATH/uploads")
    if [ "$OWNER" = "www-data:www-data" ]; then
        test_pass "上传目录权限正确: $OWNER"
    else
        test_warn "上传目录权限可能不正确: $OWNER (期望: www-data:www-data)"
    fi
else
    test_fail "上传目录不存在"
fi

run_test "日志目录权限"
if [ -d "$PROJECT_PATH/logs" ]; then
    OWNER=$(stat -c '%U:%G' "$PROJECT_PATH/logs")
    if [ "$OWNER" = "www-data:www-data" ]; then
        test_pass "日志目录权限正确: $OWNER"
    else
        test_warn "日志目录权限可能不正确: $OWNER (期望: www-data:www-data)"
    fi
else
    test_fail "日志目录不存在"
fi

echo ""

# 8. 功能测试
log_info "=== 8. 功能测试 ==="
echo ""

run_test "静态文件访问"
if [ -f "$PROJECT_PATH/static/favicon.ico" ]; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/static/favicon.ico 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        test_pass "静态文件访问成功"
    else
        test_fail "静态文件访问失败 (HTTP $HTTP_CODE)"
    fi
else
    test_warn "静态文件不存在，跳过测试"
fi

run_test "上传文件访问"
FIRST_IMAGE=$(find "$PROJECT_PATH/uploads" -type f -name "*.jpg" -o -name "*.png" | head -1)
if [ -n "$FIRST_IMAGE" ]; then
    IMAGE_NAME=$(basename "$FIRST_IMAGE")
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/uploads/$IMAGE_NAME 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        test_pass "上传文件访问成功"
    else
        test_fail "上传文件访问失败 (HTTP $HTTP_CODE)"
    fi
else
    test_warn "没有上传文件，跳过测试"
fi

echo ""

# 显示测试结果摘要
log_info "=========================================="
log_info "测试结果摘要"
log_info "=========================================="
echo -e "总测试数: ${BLUE}${TOTAL_TESTS}${NC}"
echo -e "通过: ${GREEN}${PASSED_TESTS}${NC}"
echo -e "失败: ${RED}${FAILED_TESTS}${NC}"
echo -e "成功率: $(awk "BEGIN {printf \"%.1f\", ($PASSED_TESTS/$TOTAL_TESTS)*100}")%"
log_info "=========================================="
echo ""

# 根据测试结果给出建议
if [ $FAILED_TESTS -eq 0 ]; then
    log_info "✓ 所有测试通过！服务运行正常。"
    echo ""
    log_info "建议的后续操作："
    echo "1. 更新 DNS 记录，将域名指向新服务器"
    echo "2. 配置 HTTPS 证书"
    echo "3. 设置自动备份任务"
    echo "4. 配置监控和告警"
else
    log_warn "有 $FAILED_TESTS 个测试失败，请检查以下内容："
    echo ""
    echo "1. 查看错误日志："
    echo "   sudo tail -50 /var/log/supervisor/pic-stderr.log"
    echo ""
    echo "2. 查看应用日志："
    echo "   sudo tail -50 $PROJECT_PATH/logs/pic_app.log"
    echo ""
    echo "3. 检查服务状态："
    echo "   sudo supervisorctl status pic"
    echo "   sudo systemctl status nginx"
    echo "   sudo systemctl status mongod"
    echo ""
    echo "4. 重启服务："
    echo "   sudo supervisorctl restart pic"
    echo "   sudo systemctl restart nginx"
fi

echo ""

# 显示有用的命令
log_info "常用管理命令："
echo ""
echo "查看实时日志："
echo "  sudo tail -f /var/log/supervisor/pic-stdout.log"
echo ""
echo "重启应用："
echo "  sudo supervisorctl restart pic"
echo ""
echo "查看服务状态："
echo "  sudo supervisorctl status pic"
echo ""
echo "测试网站访问："
echo "  curl -I http://localhost"
echo "  curl -I http://$SERVER_IP"
echo ""

# 询问是否查看错误日志
if [ $FAILED_TESTS -gt 0 ]; then
    read -p "是否查看错误日志？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "=== Supervisor 错误日志（最后 50 行）==="
        sudo tail -50 /var/log/supervisor/pic-stderr.log 2>/dev/null || echo "无错误日志"
        echo ""
        log_info "=== 应用日志（最后 50 行）==="
        sudo tail -50 $PROJECT_PATH/logs/pic_app.log 2>/dev/null || echo "无应用日志"
    fi
fi

# 返回退出码
if [ $FAILED_TESTS -eq 0 ]; then
    exit 0
else
    exit 1
fi
