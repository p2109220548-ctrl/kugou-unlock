# ============================================================
#  酷狗音乐解锁器 —— Windows 一键安装脚本（由 install_windows.bat 调起）
#  开发者: 鼠鼠shushuu (shushuu) — https://github.com/p2109220548-ctrl
#  仅限个人非商业使用 · 禁止商用 · 请勿二次分发
# ============================================================
# 双击 install_windows.bat 即可运行本脚本，全程无需输入任何命令。
# 它会：1) 检测/静默安装 Python  2) 安装依赖组件  3) 创建桌面快捷方式

$ErrorActionPreference = "Continue"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

function Write-Step($msg)  { Write-Host "" ; Write-Host ">>> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "    [!]  $msg" -ForegroundColor Yellow }

Write-Host "============================================================"
Write-Host "   酷狗音乐解锁器 · 一键安装向导（Windows）"
Write-Host "   开发者: 鼠鼠shushuu  |  仅限个人使用 · 禁止商用"
Write-Host "============================================================"

# ------------------------------------------------------------
# 第 1 步：找一个可用的 Python 3.11+
# ------------------------------------------------------------
function Find-Python {
    $candidates = @()
    foreach ($name in @("py", "python3", "python")) {
        try { $src = (Get-Command $name -ErrorAction SilentlyContinue).Source
              if ($src) { $candidates += $src } } catch {}
    }
    # 官方安装器默认位置也直接看一眼
    foreach ($p in @(
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "C:\Program Files\Python313\python.exe",
        "C:\Program Files\Python312\python.exe",
        "C:\Program Files\Python311\python.exe"
    )) { if (Test-Path $p) { $candidates += $p } }

    foreach ($c in $candidates) {
        try {
            $ver = (& $c -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null | Out-String).Trim()
            if ($ver -match '^3\.(\d+)$' -and [int]$Matches[1] -ge 11) { return $c }
        } catch {}
    }
    return $null
}

# 全自动安装 Python（官方源 + 国内镜像，静默安装）。成功返回 python 路径；
# 下载或安装失败时已给出指引并 exit，不会返回。
function Install-PythonAuto {
    $installer = Join-Path $env:TEMP "python-3.12.8-amd64.exe"
    $ok = $false
    # 主源 + 国内镜像源依次尝试
    $urls = @(
        "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe",
        "https://registry.npmmirror.com/-/binary/python/3.12.8/python-3.12.8-amd64.exe",
        "https://mirrors.huaweicloud.com/python/3.12.8/python-3.12.8-amd64.exe"
    )
    foreach ($u in $urls) {
        try {
            Write-Host "    正在从 $u 下载…"
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            Invoke-WebRequest -Uri $u -OutFile $installer -UseBasicParsing
            if ((Get-Item $installer).Length -gt 10MB) { $ok = $true; break }
        } catch { Write-Warn2 "该地址下载失败，换下一个…" }
    }
    if (-not $ok) {
        Write-Warn2 "自动下载失败。正在打开官方下载页，请手动下载安装："
        Write-Warn2 "  1) 选择 Windows installer (64-bit) 下载并双击安装"
        Write-Warn2 "  2) 安装时勾选底部 Add python.exe to PATH"
        Write-Warn2 "  3) 装完后重新双击 install_windows.bat"
        Start-Process "https://www.python.org/downloads/latest/"
        exit 1
    }
    Write-Ok "下载完成，正在静默安装 Python（窗口若闪出属正常现象，约需 1~2 分钟）…"
    $proc = Start-Process -FilePath $installer -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1" -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        Write-Warn2 "静默安装未成功（返回码 $($proc.ExitCode)）。正在打开官方安装包，请手动安装："
        Write-Warn2 "  一路下一步即可，【记得勾选 Add python.exe to PATH】，装完后重新双击 install_windows.bat。"
        Start-Process $installer
        exit 1
    }
    # 刷新当前会话的 PATH，让刚装的 Python 立即可见
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $found = Find-Python
    if (-not $found) { $found = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" }
    if (-not (Test-Path $found)) {
        Write-Warn2 "Python 安装完成但未自动找到。请重新双击 install_windows.bat 再试一次。"
        exit 1
    }
    Write-Ok "Python 安装成功：$found"
    return $found
}

Write-Step "第 1 步 / 共 3 步：检查 Python"
$py = Find-Python
if ($py) {
    Write-Ok "已检测到 Python：$py"
} else {
    Write-Warn2 "没有检测到 Python 3.11+。"
    Write-Host ""
    Write-Host "    已经自己装过 Python？可以不用再装一个。请选择：" -ForegroundColor Yellow
    Write-Host "      直接回车 或 1 = 自动下载并安装官方 Python（推荐 · 什么都不用做）"
    Write-Host "      2 = 我已经装了 Python —— 手动指定它的 python.exe 路径"
    Write-Host "      3 = 跳过安装 Python（本次到此为止，以后可重新运行本脚本）"
    Write-Host ""
    $choice = (Read-Host "    输入数字后回车").Trim()
    if ($choice -eq "3") {
        Write-Warn2 "已跳过 Python 安装，组件与快捷方式本次不处理。"
        Write-Warn2 "以后装好 Python 3.11+ 时，重新双击 install_windows.bat 即可继续。"
        exit 0
    }
    if ($choice -eq "2") {
        $py = $null
        foreach ($attempt in 1..3) {
            $in = (Read-Host "    请输入 python.exe 完整路径（把文件直接拖进本窗口也行），回车确认").Trim()
            $in = $in.Trim('"').Trim("'")
            if (-not $in) {
                Write-Warn2 "路径为空，请重新输入（第 $attempt / 3 次）"
                continue
            }
            if (-not (Test-Path $in)) {
                Write-Warn2 "路径不存在：$in（第 $attempt / 3 次）"
                continue
            }
            $ver = ""
            try { $ver = (& $in -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null | Out-String).Trim() } catch {}
            if ($ver -match '^3\.(\d+)$' -and [int]$Matches[1] -ge 11) {
                $py = $in
                Write-Ok "使用你指定的 Python（$ver）：$in"
                break
            }
            $yes = Read-Host "    检测到版本 '$ver'（本工具推荐 3.11+，偏低可能跑不起来）。仍要使用吗？[y/N]"
            if ($yes -match '^[Yy]') {
                $py = $in
                Write-Ok "按你的选择使用：$in"
                break
            }
            Write-Warn2 "请换一个路径再试（第 $attempt / 3 次）"
        }
        if (-not $py) {
            Write-Warn2 "没有指定可用的 Python。重新双击 install_windows.bat 可以再来一次。"
            exit 1
        }
    } else {
        $py = Install-PythonAuto
        if (-not $py) { exit 1 }
    }
}

# ------------------------------------------------------------
# 第 2 步：安装运行所需的两个小组件
# ------------------------------------------------------------
Write-Step "第 2 步 / 共 3 步：安装运行组件（pycryptodome / numpy）"
Write-Host "    （处理 .kgg 文件需要 pycryptodome；numpy 让转换更快。只装一次。）"
& $py -m pip install --disable-pip-version-check --quiet -i https://pypi.tuna.tsinghua.edu.cn/simple pycryptodome numpy | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Ok "组件安装完成（清华镜像源）"
} else {
    Write-Warn2 "镜像源不可用，改用官方源重试…"
    & $py -m pip install --disable-pip-version-check --quiet pycryptodome numpy | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "组件安装完成（官方源）"
    } else {
        Write-Warn2 "组件自动安装失败（不影响 .kgm/.kgma 文件的转换）。"
        Write-Warn2 "之后处理 .kgg 报错时，再手动执行：$py -m pip install pycryptodome numpy"
    }
}

# ------------------------------------------------------------
# 第 3 步：创建桌面快捷方式（双击即用）
# ------------------------------------------------------------
Write-Step "第 3 步 / 共 3 步：创建桌面快捷方式"
try {
    $pythonw = Join-Path (Split-Path -Parent $py) "pythonw.exe"
    if (-not (Test-Path $pythonw)) { $pythonw = $py }
    $ws = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath("Desktop")
    $lnkPath = Join-Path $desktop "酷狗音乐解锁器.lnk"
    $lnk = $ws.CreateShortcut($lnkPath)
    $lnk.TargetPath = $pythonw
    $lnk.Arguments  = '"' + (Join-Path $scriptDir "kugou_unlock_gui.py") + '"'
    $lnk.WorkingDirectory = $scriptDir
    $lnk.Description = "酷狗音乐解锁器 v2.3 · 由 鼠鼠shushuu 开发 · 仅限个人使用"
    $lnk.Save()
    Write-Ok "桌面快捷方式已创建：酷狗音乐解锁器"
} catch {
    Write-Warn2 "快捷方式创建失败（不影响使用）。可以直接双击文件夹里的 start_kugou_unlocker.bat 启动。"
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "   安装完成！" -ForegroundColor Green
Write-Host "   双击桌面的「酷狗音乐解锁器」即可打开图形界面：" -ForegroundColor Green
Write-Host "     ① 点「自动找到酷狗文件夹」（或手动选择文件/文件夹）" -ForegroundColor Green
Write-Host "     ② 选保存位置  ③ 点「开始转换」" -ForegroundColor Green
Write-Host "   详细图文教程见文件夹里的 用户手册.pdf 或 README.md" -ForegroundColor Green
Write-Host "   —— 由 鼠鼠shushuu 开发 · 仅限个人使用 · 禁止商用 ——" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
