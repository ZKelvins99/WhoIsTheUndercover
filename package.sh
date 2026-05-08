#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PACKAGE_NAME="who-game"

echo "========================================="
echo "  谁是卧底 - 本地打包"
echo "========================================="

# 1. Build frontend
echo "[1/3] 构建前端..."
cd "${PROJECT_DIR}/web"
npm install
npm run build
cd "${PROJECT_DIR}"

if [ ! -f "${PROJECT_DIR}/python/static/index.html" ]; then
    echo "错误: 前端构建失败"
    exit 1
fi

# 2. Package
echo "[2/3] 打包..."
TEMP_DIR=$(mktemp -d)
mkdir -p "${TEMP_DIR}/${PACKAGE_NAME}"

cp -r python/app           "${TEMP_DIR}/${PACKAGE_NAME}/"
cp -r python/static        "${TEMP_DIR}/${PACKAGE_NAME}/"
cp    python/requirements.txt "${TEMP_DIR}/${PACKAGE_NAME}/"

cat > "${TEMP_DIR}/${PACKAGE_NAME}/start.sh" << 'EOF'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${DIR}"

# Activate conda base environment
eval "$(conda shell.bash hook)"
conda activate base

nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info > uvicorn.log 2>&1 &
echo $! > uvicorn.pid
IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
echo "服务已启动 (PID: $(cat uvicorn.pid))"
echo "访问: http://${IP}:8000"
echo "日志: tail -f uvicorn.log"
EOF
chmod +x "${TEMP_DIR}/${PACKAGE_NAME}/start.sh"

cat > "${TEMP_DIR}/${PACKAGE_NAME}/stop.sh" << 'EOF'
#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="${DIR}/uvicorn.pid"
if [ -f "${PID_FILE}" ]; then
    PID=$(cat "${PID_FILE}")
    kill "${PID}" 2>/dev/null && echo "服务已停止 (PID: ${PID})" || echo "进程不存在"
    rm -f "${PID_FILE}"
else
    echo "未找到 PID 文件"
fi
EOF
chmod +x "${TEMP_DIR}/${PACKAGE_NAME}/stop.sh"

# 3. Pack
cd "${TEMP_DIR}"
tar czf "${PROJECT_DIR}/${PACKAGE_NAME}.tar.gz" "${PACKAGE_NAME}"
rm -rf "${TEMP_DIR}"

echo "[3/3] 完成!"
echo ""
echo "  文件: ${PACKAGE_NAME}.tar.gz ($(du -h "${PROJECT_DIR}/${PACKAGE_NAME}.tar.gz" | cut -f1))"
echo ""
echo "  上传: scp ${PACKAGE_NAME}.tar.gz root@服务器IP:/opt/"
echo "  解压: cd /opt && tar xzf ${PACKAGE_NAME}.tar.gz"
echo "  启动: cd who-game && ./start.sh"
echo "  停止: cd who-game && ./stop.sh"
