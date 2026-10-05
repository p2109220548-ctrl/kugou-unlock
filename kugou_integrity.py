#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
酷狗音乐解锁器 —— 完整性自校验模块（Ed25519 非对称签名版）
==========================================================

本项目内置防篡改保护：图形界面与命令行入口在启动时会调用本模块，
对下列受保护文件逐一重新计算 SHA-256 并与随软件分发的完整性清单
（integrity_manifest.json）比对；清单由开发者的 Ed25519 私钥签名，
签名锚定在 integrity_anchor.py 中，本模块内嵌配对公钥进行验签。

Ed25519（RFC 8032）是非对称签名：私钥仅开发者持有、永不随软件分发，
因此任何人——包括拿到全部软件文件的修改者——都无法为被篡改的清单
伪造出合法签名。被改动过的副本会在启动瞬间被数学方法识破。

只要下列任何一种情况发生，软件都会拒绝运行并提示重新下载原始副本：
  - 受保护文件被修改、替换或删除（包括文档、许可、安装脚本）
  - 完整性清单或锚文件被改动（签名验证失败）
  - 校验逻辑本身被篡改

依 LICENSE 条款：本模块、署名信息与免责声明不得删除或篡改。
开发者重新打包时请运行 _internal/generate_manifest.py 重新生成清单
与签名（该工具与私钥仅开发者持有，不随软件分发）。

开发者 / Author: 鼠鼠shushuu (shushuu) — https://github.com/p2109220548-ctrl
仅限个人非商业使用，禁止商用 / Personal non-commercial use only
"""

import hashlib
import json
import os

__author__ = "鼠鼠shushuu (https://github.com/p2109220548-ctrl)"
__license__ = "Personal-NonCommercial-Use-Only (see LICENSE file)"

AUTHOR_LINE = "由 鼠鼠shushuu (shushuu) 开发 · https://github.com/p2109220548-ctrl"
DISCLAIMER = "仅限个人使用 · 禁止商用 · 请勿二次分发"
OFFICIAL_URL = "https://github.com/p2109220548-ctrl/kugou-unlock"

MANIFEST_FILE = "integrity_manifest.json"
ANCHOR_FILE = "integrity_anchor.py"

# 受完整性保护的文件（相对软件根目录；由开发工具生成清单时使用）
PROTECTED_FILES = [
    "kugou_unlock.py",
    "kugou_unlock_gui.py",
    "kugou_integrity.py",
    "README.md",
    "SKILL.md",
    "LICENSE",
    "requirements.txt",
    "install_windows.bat",
    "install_windows.ps1",
    "start_kugou_unlocker.bat",
    "install_mac.command",
    "docs/python-download-page.png",
    "docs/logo.png",
    "酷狗解锁器用户手册.pdf",
    "python-3.14.8-amd64.exe",
]

# Ed25519 公钥（与开发者私钥 _internal/ed25519_secret.key 配对；公开信息，
# 随软件分发是安全的——没有私钥，任何人也无法签出合法清单）。
# 修改本常量将导致清单签名无法验证，软件拒绝运行。
_ED25519_PUBKEY_HEX = "9100b1a7a0c655362d38f10ec9a1520a601c2fe9a9772d731504b57a28bf977d"

# 软件标识（印在横幅 / 界面 / 文档各处）
LOGO_TEXT = "鼠鼠shushuu"
ASCII_LOGO = r"""
      (\_._/)     酷狗音乐解锁器 · KuGou Unlocker
      ( o.o )     by 鼠鼠shushuu (shushuu)
      ( > ^ <)>   仅限个人使用 · 禁止商用 · 请勿二次分发
"""


# ==================== Ed25519 纯 Python 实现（RFC 8032） ====================
# 刻意零第三方依赖：用户无需为校验安装任何密码学库（双击即用原则）。
# 纯大整数实现的验签耗时约 0.1~0.3 秒，仅在启动时执行一次。
# 实现已通过 RFC 8032 官方测试向量与 cryptography 库交叉验证。

_Q = 2**255 - 19                                   # 曲线域素数（edwards25519）
_L = 2**252 + 27742317777372353535851937790883648493  # 群的阶
_D = (-121665 * pow(121666, _Q - 2, _Q)) % _Q      # 曲线常数 d
_I = pow(2, (_Q - 1) // 4, _Q)                     # sqrt(-1) mod q

_IDENT = (0, 1)                                    # 群单位元（仿射坐标）
_BY = (4 * pow(5, _Q - 2, _Q)) % _Q                # 基点 B 的 y 坐标 = 4/5


def _xrecover(y):
    """由 y 坐标恢复 x（RFC 8032 5.1.3）。"""
    xx = (y * y - 1) * pow(_D * y * y + 1, _Q - 2, _Q) % _Q
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x % 2 != 0:
        x = _Q - x
    return x


_BX = _xrecover(_BY)
_B = (_BX % _Q, _BY % _Q)


def _isoncurve(P):
    """点是否满足曲线方程 -x² + y² = 1 + d·x²·y²。"""
    x, y = P
    return (-x * x + y * y - 1 - _D * x * x * y * y) % _Q == 0


def _edwards(P, Q):
    """Edwards 曲线点加法。"""
    x1, y1 = P
    x2, y2 = Q
    x3 = (x1 * y2 + x2 * y1) * pow(1 + _D * x1 * x2 * y1 * y2, _Q - 2, _Q)
    y3 = (y1 * y2 + x1 * x2) * pow(1 - _D * x1 * x2 * y1 * y2, _Q - 2, _Q)
    return (x3 % _Q, y3 % _Q)


def _scalarmult(P, e):
    """标量乘 [e]P（double-and-add，自最高位迭代）。"""
    Q = _IDENT
    for bit in bin(e)[2:]:
        Q = _edwards(Q, Q)
        if bit == "1":
            Q = _edwards(Q, P)
    return Q


def _encodepoint(P):
    """点编码：255 位 y（小端）+ 最高位放 x 的奇偶。"""
    x, y = P
    ba = bytearray(y.to_bytes(32, "little"))
    ba[31] = (ba[31] & 0x7F) | ((x & 1) << 7)
    return bytes(ba)


def _decodepoint(s):
    """点解码（含在曲线上的检查）；非法输入抛 ValueError。"""
    if len(s) != 32:
        raise ValueError("bad point length")
    y = int.from_bytes(s, "little") & ((1 << 255) - 1)
    sign_x = (s[31] >> 7) & 1
    x = _xrecover(y)
    if x & 1 != sign_x:
        x = _Q - x
    P = (x, y)
    if not _isoncurve(P):
        raise ValueError("point not on curve")
    return P


def _secret_expand(seed):
    """由 32 字节种子推导标量 a 与前缀 prefix（RFC 8032 5.1.5/5.1.6）。"""
    if len(seed) != 32:
        raise ValueError("Ed25519 seed must be 32 bytes")
    h = hashlib.sha512(seed).digest()
    a = 1 << 254
    for i in range(3, 254):
        a += ((h[i >> 3] >> (i & 7)) & 1) << i
    return a, h[32:]


def ed25519_publickey(seed):
    """由种子推导 32 字节公钥。"""
    a, _prefix = _secret_expand(seed)
    return _encodepoint(_scalarmult(_B, a))


def ed25519_sign(msg, seed):
    """Ed25519 签名（RFC 8032 5.1.6），返回 64 字节签名。"""
    a, prefix = _secret_expand(seed)
    pub = _encodepoint(_scalarmult(_B, a))
    r = int.from_bytes(hashlib.sha512(prefix + msg).digest(), "little")
    R = _encodepoint(_scalarmult(_B, r))
    k = int.from_bytes(hashlib.sha512(R + pub + msg).digest(), "little")
    S = (r + k * a) % _L
    return R + S.to_bytes(32, "little")


def ed25519_verify(sig, msg, pubkey):
    """Ed25519 验签（RFC 8032 5.1.7）。返回 bool，任何异常输入一律 False。"""
    if len(sig) != 64 or len(pubkey) != 32:
        return False
    try:
        R_pt = _decodepoint(sig[:32])
        A_pt = _decodepoint(pubkey)
    except Exception:
        return False
    S = int.from_bytes(sig[32:], "little")
    if S >= _L:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + pubkey + msg).digest(), "little")
    left = _scalarmult(_B, S)
    right = _edwards(R_pt, _scalarmult(A_pt, k))
    return _encodepoint(left) == _encodepoint(right)


# ==================== 完整性校验 ====================


def sha256_file(path):
    """计算文件 SHA-256；文件不存在返回 None。"""
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def _load_anchor(base_dir):
    """从 anchor 文件读取清单的 Ed25519 签名（不经 sys.path，避免导入副作用）。"""
    path = os.path.join(base_dir, ANCHOR_FILE)
    if not os.path.isfile(path):
        return None, "完整性锚文件缺失（%s）" % ANCHOR_FILE
    ns = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            exec(f.read(), ns)  # noqa: S102 - 仅读取自家常量文件，内容不含外部输入
    except Exception:
        return None, "完整性锚文件损坏（%s）" % ANCHOR_FILE
    sig_hex = ns.get("ANCHOR_SIGNATURE")
    if not isinstance(sig_hex, str):
        return None, "完整性锚内容非法（%s）" % ANCHOR_FILE
    try:
        sig = bytes.fromhex(sig_hex)
    except ValueError:
        return None, "完整性锚内容非法（%s）" % ANCHOR_FILE
    if len(sig) != 64:
        return None, "完整性锚内容非法（%s）" % ANCHOR_FILE
    return sig, None


def verify(base_dir=None):
    """完整校验。返回 (ok, problems)；problems 为中文问题描述列表。"""
    base = base_dir or os.path.dirname(os.path.abspath(__file__))

    # 1. 清单存在且通过 Ed25519 签名验证（无私钥无法伪造）
    manifest_path = os.path.join(base, MANIFEST_FILE)
    if not os.path.isfile(manifest_path):
        return False, ["完整性清单缺失（%s）" % MANIFEST_FILE]
    try:
        with open(manifest_path, "rb") as f:
            data = f.read()
    except OSError:
        return False, ["完整性清单无法读取（%s）" % MANIFEST_FILE]

    signature, err = _load_anchor(base)
    if err:
        return False, [err]
    pubkey = bytes.fromhex(_ED25519_PUBKEY_HEX)
    if not ed25519_verify(signature, data, pubkey):
        return False, ["完整性清单签名验证失败（清单或校验锚被修改）"]

    try:
        manifest = json.loads(data.decode("utf-8"))
    except Exception:
        return False, ["完整性清单格式损坏"]

    # 2. 逐文件比对 SHA-256
    problems = []
    for rel, expect in manifest.get("files", {}).items():
        path = os.path.join(base, rel.replace("/", os.sep))
        if not os.path.isfile(path):
            problems.append("文件缺失：%s" % rel)
            continue
        actual = sha256_file(path)
        if actual is None:
            problems.append("文件无法读取：%s" % rel)
        elif actual != expect.get("sha256"):
            problems.append("文件被修改：%s" % rel)
    return (not problems), problems


def fail_text(problems):
    """校验失败时的用户提示全文（含署名与免责声明）。"""
    lines = [
        "⚠ 完整性校验失败 —— 程序文件已被修改或损坏，软件拒绝运行。",
        "",
    ]
    lines += ["  · " + p for p in problems]
    lines += [
        "",
        "为保护你的使用安全与开发者权益，本软件在检测到文件被修改后",
        "将无法继续工作。请前往官方页面重新下载完整原始副本：",
        "  " + OFFICIAL_URL,
        "",
        "—— " + AUTHOR_LINE + " ——",
        "—— " + DISCLAIMER + " ——",
    ]
    return "\n".join(lines)


def banner(version):
    """启动横幅（CLI 输出 / 关于弹窗共用）：logo + 署名 + 免责声明。"""
    return "%s\n  版本 v%s\n%s" % (
        ASCII_LOGO.strip("\n"),
        version,
        "  " + AUTHOR_LINE + "\n  " + DISCLAIMER,
    )
