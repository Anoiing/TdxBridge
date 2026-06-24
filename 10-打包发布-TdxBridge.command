#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "未找到 python3 或 python，请先安装 Python。"
  read -r -p "按回车键退出..."
  exit 1
fi

"$PYTHON_BIN" "$SCRIPT_DIR/scripts/build_release.py" --project-root "$SCRIPT_DIR"

echo
echo "打包完成。"
echo "按回车键关闭窗口。"
read -r _
