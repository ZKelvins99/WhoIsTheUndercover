#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="${PROJECT_DIR}/python/uvicorn.pid"

start_server() {
  echo "========================================="
  echo "  谁是卧底 - 一键部署脚本"
  echo "========================================="

  # 1. Activate base environment
  echo ""
  echo "[1/4] 使用 conda base 环境..."
  eval "$(conda shell.bash hook)"
  conda activate base

  # 2. Install Python dependencies
  echo ""
  echo "[2/4] 安装 Python 依赖..."
  cd "${PROJECT_DIR}/python"
  pip install -r requirements.txt
  cd "${PROJECT_DIR}"

  # 3. Build frontend
  echo ""
  echo "[3/4] 构建前端..."
  cd "${PROJECT_DIR}/web"
  npm install
  npm run build
  cd "${PROJECT_DIR}"

  # 4. Verify static files
  if [ ! -f "${PROJECT_DIR}/python/static/index.html" ]; then
      echo "错误: 前端构建失败，python/static/index.html 不存在"
      exit 1
  fi
  echo "  构建完成，静态文件已输出到 python/static/"

  # 5. Start server
  echo ""
  echo "========================================="
  echo "  启动服务器"
  echo "  访问地址: http://$(hostname -I | awk '{print $1}'):8000"
  echo "========================================="
  echo ""
  cd "${PROJECT_DIR}/python"

  nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 > "${PROJECT_DIR}/python/uvicorn.log" 2>&1 &
  echo $! > "${PID_FILE}"
  echo "  服务已启动，PID: $(cat "${PID_FILE}")"
}

stop_server() {
  if [ -f "${PID_FILE}" ]; then
    PID=$(cat "${PID_FILE}")
    if ps -p "${PID}" > /dev/null 2>&1; then
      echo "正在停止服务 (PID: ${PID})..."
      kill "${PID}"
      rm -f "${PID_FILE}"
      echo "服务已停止"
    else
      echo "PID 文件存在但进程不存在，清理 PID 文件"
      rm -f "${PID_FILE}"
    fi
  else
    echo "未找到 PID 文件，服务可能未启动"
  fi
}

status_server() {
  if [ -f "${PID_FILE}" ] && ps -p "$(cat "${PID_FILE}")" > /dev/null 2>&1; then
    echo "服务运行中 (PID: $(cat "${PID_FILE}"))"
  else
    echo "服务未运行"
  fi
}

case "$1" in
  start|"")
    start_server
    ;;
  stop)
    stop_server
    ;;
  restart)
    stop_server
    start_server
    ;;
  status)
    status_server
    ;;
  *)
    echo "用法: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac