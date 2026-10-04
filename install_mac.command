#!/bin/bash
# ============================================================
#  酷狗音乐解锁器 —— macOS 一键安装脚本（双击运行）
#  开发者: 鼠鼠shushuu (shushuu) — https://github.com/p2109220548-ctrl
#  仅限个人非商业使用 · 禁止商用 · 请勿二次分发
# ============================================================
# 双击本文件即可运行，全程无需输入任何命令。
# 它会：1) 检测 Python 3.11+（缺失时自动打开官方下载页）
#       2) 安装依赖组件  3) 生成双击启动器 start_kugou_unlocker.command
#
# 若提示"无法打开，因为无法验证开发者"：右键本文件 → 打开 → 打开。
# 若提示没有执行权限：打开「终端」，把本文件拖进去，前面加 chmod +x 回车。

cd "$(dirname "$0")" || exit 1

echo "============================================================"
echo "   酷狗音乐解锁器 · 一键安装向导（macOS）"
echo "   开发者: 鼠鼠shushuu  |  仅限个人使用 · 禁止商用"
echo "============================================================"

# ---------- 第 1 步：检查 Python 3.11+ ----------
echo ""
echo ">>> 第 1 步 / 共 3 步：检查 Python"
PY=""
for c in python3 python3.13 python3.12 python3.11 python; do
    if command -v "$c" >/dev/null 2>&1; then
        v=$("$c" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null)
        major="${v%%.*}"; minor="${v#*.}"
        if [ "${major:-0}" -ge 3 ] && [ "${minor:-0}" -ge 11 ] 2>/dev/null; then PY="$c"; break; fi
    fi
done

if [ -z "$PY" ]; then
    echo "    [!]  没有检测到 Python 3.11+，正在打开官方下载页…"
    echo "    请下载「macOS 64-bit universal2 installer」并安装（一路下一步），"
    echo "    装完后重新双击本文件即可。"
    open "https://www.python.org/downloads/latest/"
    exit 1
fi
echo "    [OK] 已检测到 Python：$PY"

# ---------- 第 2 步：安装依赖组件 ----------
echo ""
echo ">>> 第 2 步 / 共 3 步：安装运行组件（pycryptodome / numpy）"
if "$PY" -m pip install --user --disable-pip-version-check --quiet -i https://pypi.tuna.tsinghua.edu.cn/simple pycryptodome numpy; then
    echo "    [OK] 组件安装完成（清华镜像源）"
elif "$PY" -m pip install --user --disable-pip-version-check --quiet pycryptodome numpy; then
    echo "    [OK] 组件安装完成（官方源）"
else
    echo "    [!]  组件自动安装失败（不影响 .kgm/.kgma 文件的转换）。"
    echo "    之后处理 .kgg 报错时，在终端执行：$PY -m pip install --user pycryptodome numpy"
fi

# ---------- 第 3 步：生成双击启动器 ----------
echo ""
echo ">>> 第 3 步 / 共 3 步：生成启动器 start_kugou_unlocker.command"
PY_ABS="$($PY -c 'import sys;print(sys.executable)')"
cat > "start_kugou_unlocker.command" <<LAUNCHER
#!/bin/bash
# 酷狗音乐解锁器 启动器 · 开发者: 鼠鼠shushuu · 仅限个人使用 · 禁止商用
cd "\$(dirname "\$0")" || exit 1
exec "$PY_ABS" kugou_unlock_gui.py
LAUNCHER
chmod +x "start_kugou_unlocker.command"
echo "    [OK] 启动器已生成"

echo ""
echo "============================================================"
echo "   安装完成！"
echo "   双击文件夹里的 start_kugou_unlocker.command 即可打开界面："
echo "     ① 点「自动找到酷狗文件夹」（或手动选择文件/文件夹）"
echo "     ② 选保存位置  ③ 点「开始转换」"
echo "   详细图文教程见文件夹里的 用户手册.pdf 或 README.md"
echo "   —— 由 鼠鼠shushuu 开发 · 仅限个人使用 · 禁止商用 ——"
echo "============================================================"
