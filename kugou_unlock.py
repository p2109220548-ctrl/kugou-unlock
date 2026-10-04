#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
酷狗音乐解锁器 —— 核心解密库 + 命令行工具
==========================================

把酷狗客户端下载的加密音频（.kgm / .kgma / .vpr / .kgg）还原为标准音频文件
（FLAC / MP3 / WAV / OGG / M4A），并可在装有 FFmpeg 时转码为指定格式。

解密是**无损去壳**：音频载荷逐字节还原，不重新编码，与酷狗服务器下发的
原始文件完全一致。全程本地运行，不联网、不上传任何文件。

重要 —— 仅限个人使用：
    只处理你本人拥有合法使用权的本地文件（自己账号下载的音乐）。
    解密产物仅限私人播放，请勿二次分发。

图形界面：见同目录下的 kugou_unlock_gui.py（无需命令行知识）。

用法（命令行）
    python kugou_unlock.py <输入文件或目录> <输出目录> [--fmt auto|flac|mp3|wav]
                           [--db 路径] [--keyfile 路径] [--procs N] [--only kgm,kgg]

依赖
    Python >= 3.11（sqlite3.Connection.deserialize）
    numpy        可选，KGM 路径约 20 倍加速（缺失时自动回退纯 Python）
    pycryptodome 仅 .kgg 需要（密钥库页解密的 AES）
    FFmpeg       可选，仅在需要转码（--fmt 非 auto）时使用
"""

import argparse
import base64
import hashlib
import os
import shutil
import sqlite3
import struct
import subprocess
import sys

import kugou_integrity as integrity

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

try:
    from Crypto.Cipher import AES
except ImportError:  # pragma: no cover
    AES = None

# ---------------------------------------------------------------------------
# 项目签名 / Project signature —— 依 LICENSE 条款不得删除或篡改
# 开发者 / Author: 鼠鼠shushuu (shushuu) — https://github.com/p2109220548-ctrl
# 仅限个人非商业使用，禁止商用 / Personal non-commercial use only
# ---------------------------------------------------------------------------
__author__ = "鼠鼠shushuu (https://github.com/p2109220548-ctrl)"
__license__ = "Personal-NonCommercial-Use-Only (see LICENSE file)"
__version__ = "2.4.0"
__title__ = "酷狗音乐解锁器"
__title_en__ = "KuGou Unlocker"

AUDIO_EXTS = ("kgm", "kgma", "vpr", "kgg")   # 支持的加密输入格式
TARGET_FMTS = ("auto", "flac", "mp3", "wav")  # 支持的输出格式（auto = 保持解密后的原始格式）

# ---------------------------------------------------------------------------
# 第一部分：KGM V2 XOR 掩码（.kgm / .kgma / .vpr）
#
#   fileKey   = 文件头 [0x1C:0x2C] + 0x00        （共 17 字节）
#   headerLen = 文件头 [0x10] 处的 uint32 (LE)
#   audio     = 从 headerLen 开始的音频数据
#   out[i]    = T( maskV2(i) ^ audio[i] ^ fileKey[i % 17] )
#   T(x)      = x ^ ((x & 0x0f) << 4)
#   maskV2(i) = tableV2[i % 272] ^ maskV1(i >> 4)
#   maskV1(o) = while o >= 0x11: v ^= table1[o % 272]; o >>= 4;
#                             v ^= table2[o % 272]; o >>= 4
#   (.vpr 在 T 之后额外异或 vprKey[i % 17])
#
# 常量表来自社区公开实现（unlock-music 等），已与参考实现对拍验证。
# ---------------------------------------------------------------------------
TABLE_SIZE = 272

table1 = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 33, 1, 97, 1, 33, 1, 225, 1, 33, 1, 97, 1, 33, 1, 210, 35, 2, 2, 66, 66, 2, 2, 194, 194, 2, 2, 66, 66, 2, 2, 211, 211, 2, 3, 99, 67, 99, 3, 227, 195, 227, 3, 99, 67, 99, 3, 148, 180, 148, 101, 4, 4, 4, 4, 132, 132, 132, 132, 4, 4, 4, 4, 149, 149, 149, 149, 4, 5, 37, 5, 229, 133, 165, 133, 229, 5, 37, 5, 214, 182, 150, 182, 214, 39, 6, 6, 198, 198, 134, 134, 198, 198, 6, 6, 215, 215, 151, 151, 215, 215, 6, 7, 231, 199, 231, 135, 231, 199, 231, 7, 24, 56, 24, 120, 24, 56, 24, 233, 8, 8, 8, 8, 8, 8, 8, 8, 25, 25, 25, 25, 25, 25, 25, 25, 8, 9, 41, 9, 105, 9, 41, 9, 218, 58, 26, 58, 90, 58, 26, 58, 218, 43, 10, 10, 74, 74, 10, 10, 219, 219, 27, 27, 91, 91, 27, 27, 219, 219, 10, 11, 107, 75, 107, 11, 156, 188, 156, 124, 28, 60, 28, 124, 156, 188, 156, 109, 12, 12, 12, 12, 157, 157, 157, 157, 29, 29, 29, 29, 157, 157, 157, 157, 12, 13, 45, 13, 222, 190, 158, 190, 222, 62, 30, 62, 222, 190, 158, 190, 222, 47, 14, 14, 223, 223, 159, 159, 223, 223, 31, 31, 223, 223, 159, 159, 223, 223, 14, 15, 0, 32, 0, 96, 0, 32, 0, 224, 0, 32, 0, 96, 0, 32, 0, 241]
table2 = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 35, 1, 103, 1, 35, 1, 239, 1, 35, 1, 103, 1, 35, 1, 223, 33, 2, 2, 70, 70, 2, 2, 206, 206, 2, 2, 70, 70, 2, 2, 222, 222, 2, 3, 101, 71, 101, 3, 237, 207, 237, 3, 101, 71, 101, 3, 157, 191, 157, 99, 4, 4, 4, 4, 140, 140, 140, 140, 4, 4, 4, 4, 156, 156, 156, 156, 4, 5, 39, 5, 235, 141, 175, 141, 235, 5, 39, 5, 219, 189, 159, 189, 219, 37, 6, 6, 202, 202, 142, 142, 202, 202, 6, 6, 218, 218, 158, 158, 218, 218, 6, 7, 233, 203, 233, 143, 233, 203, 233, 7, 25, 59, 25, 127, 25, 59, 25, 231, 8, 8, 8, 8, 8, 8, 8, 8, 24, 24, 24, 24, 24, 24, 24, 24, 8, 9, 43, 9, 111, 9, 43, 9, 215, 57, 27, 57, 95, 57, 27, 57, 215, 41, 10, 10, 78, 78, 10, 10, 214, 214, 26, 26, 94, 94, 26, 26, 214, 214, 10, 11, 109, 79, 109, 11, 149, 183, 149, 123, 29, 63, 29, 123, 149, 183, 149, 107, 12, 12, 12, 12, 148, 148, 148, 148, 28, 28, 28, 28, 148, 148, 148, 148, 12, 13, 47, 13, 211, 181, 151, 181, 211, 61, 31, 61, 211, 181, 151, 181, 211, 45, 14, 14, 210, 210, 150, 150, 210, 210, 30, 30, 210, 210, 150, 150, 210, 210, 14, 15, 0, 34, 0, 102, 0, 34, 0, 238, 0, 34, 0, 102, 0, 34, 0, 254]
tableV2 = [184, 213, 61, 178, 233, 175, 120, 140, 131, 51, 113, 81, 118, 160, 205, 55, 47, 62, 53, 141, 169, 190, 152, 183, 231, 140, 34, 206, 90, 97, 223, 104, 105, 137, 254, 165, 182, 222, 169, 119, 252, 200, 189, 189, 229, 109, 62, 90, 54, 239, 105, 78, 190, 225, 233, 102, 28, 243, 217, 2, 182, 242, 18, 155, 68, 208, 111, 185, 53, 137, 182, 70, 109, 115, 130, 6, 105, 193, 237, 215, 133, 194, 48, 223, 162, 98, 190, 121, 45, 98, 98, 61, 13, 126, 190, 72, 137, 35, 2, 160, 228, 213, 117, 81, 50, 2, 83, 253, 22, 58, 33, 59, 22, 15, 195, 178, 187, 179, 226, 186, 58, 61, 19, 236, 246, 1, 69, 132, 165, 112, 15, 147, 73, 12, 100, 205, 49, 213, 204, 76, 7, 1, 158, 0, 26, 35, 144, 191, 136, 30, 59, 171, 166, 62, 196, 115, 71, 16, 126, 59, 94, 188, 227, 0, 132, 255, 9, 212, 224, 137, 15, 91, 88, 112, 79, 251, 101, 216, 92, 83, 27, 211, 200, 198, 191, 239, 152, 176, 80, 79, 15, 234, 229, 131, 88, 140, 40, 44, 132, 103, 205, 208, 158, 71, 219, 39, 80, 202, 244, 99, 99, 232, 151, 127, 27, 75, 12, 194, 193, 33, 76, 204, 88, 245, 148, 82, 163, 243, 211, 224, 104, 244, 0, 35, 243, 94, 10, 123, 147, 221, 171, 18, 178, 19, 232, 132, 215, 167, 159, 15, 50, 76, 85, 29, 4, 54, 82, 220, 3, 243, 249, 78, 66, 233, 61, 97, 239, 124, 182, 179, 147, 80]
vprKey = [37, 223, 232, 166, 117, 30, 117, 14, 47, 128, 243, 45, 184, 182, 227, 17, 0]

if np is not None:
    _t1 = np.array(table1, dtype=np.uint8)
    _t2 = np.array(table2, dtype=np.uint8)
    _tv2 = np.array(tableV2, dtype=np.uint8)
    _T_LUT = np.array([x ^ ((x & 0x0F) << 4) & 0xFF for x in range(256)], dtype=np.uint8)


def _mask_v1_scalar(offset):
    """maskV1 的标量参考实现（纯 Python 回退路径使用）。"""
    value = 0
    while offset >= 0x11:
        value ^= table1[offset % TABLE_SIZE]
        offset >>= 4
        value ^= table2[offset % TABLE_SIZE]
        offset >>= 4
    return value


def _mask_v1_block(j0, count):
    """对 j ∈ [j0, j0+count) 批量计算 mask_v1(j) —— numpy 向量化版本。"""
    o = np.arange(j0, j0 + count, dtype=np.uint64)
    acc = np.zeros(count, dtype=np.uint8)
    while True:
        act = o >= 0x11
        if not act.any():
            break
        oa = o[act]
        a = acc[act]
        a ^= _t1[oa % 272]
        oa = oa >> 4
        a ^= _t2[oa % 272]
        oa = oa >> 4
        acc[act] = a
        o[act] = oa
    return acc


CHUNK = 1 << 25  # 每块 32MB；必须保持为 16 的倍数（对齐 maskV1(i>>4) 的边界）


def decrypt_xor_stream(fin, fout, is_vpr=False):
    """解密 .kgm / .kgma（以及 .vpr）文件，返回检测到的音频格式字符串。"""
    with open(fin, 'rb') as f:
        header = f.read(0x3C)
        if len(header) < 0x3C:
            raise ValueError('文件过小，不是合法的 KGM 容器')
        fk = np.frombuffer(header[0x1C:0x2C] + b'\x00', dtype=np.uint8) if np is not None \
            else header[0x1C:0x2C] + b'\x00'
        header_len = struct.unpack_from('<I', header, 0x10)[0]
        f.seek(header_len)
        total = os.fstat(f.fileno()).st_size - header_len
        with open(fout, 'wb') as g:
            if np is not None:
                # numpy 加速路径：逐块生成掩码流后大数组异或，全程 C 速度
                off0 = 0
                vk = np.array(vprKey, dtype=np.uint8) if is_vpr else None
                while off0 < total:
                    n = min(CHUNK, total - off0)
                    audio = np.frombuffer(f.read(n), dtype=np.uint8)
                    rot = off0 % 272
                    t2p = np.tile(np.roll(_tv2, -rot), int(np.ceil(n / 272)) + 1)[:n]
                    rotf = off0 % 17
                    fkp = np.tile(np.roll(fk, -rotf), int(np.ceil(n / 17)) + 1)[:n]
                    cs = _mask_v1_block(off0 >> 4, (n >> 4) + 1)
                    v1p = np.repeat(cs, 16)[:n]
                    out = _T_LUT[audio ^ t2p ^ v1p ^ fkp]
                    if is_vpr:
                        out ^= np.tile(np.roll(vk, off0 % 17), int(np.ceil(n / 17)) + 1)[:n]
                    g.write(out.tobytes())
                    off0 += n
            else:
                # 纯 Python 回退路径（逐字节等价，只是慢）
                filekey = bytes(fk)
                offset = 0
                while True:
                    block = f.read(1 << 16)
                    if not block:
                        break
                    b = bytearray(block)
                    for i in range(len(b)):
                        x = _mask_v1_scalar((offset + i) >> 4) ^ tableV2[(offset + i) % TABLE_SIZE] \
                            ^ block[i] ^ filekey[(offset + i) % 17]
                        b[i] = (x ^ ((x & 0x0F) << 4)) & 0xFF
                    if is_vpr:
                        for i in range(len(b)):
                            b[i] ^= vprKey[(offset + i) % 17]
                    g.write(b)
                    offset += len(b)
    return detect_format_path(fout)


# ---------------------------------------------------------------------------
# 第二部分：输出格式检测（音频魔数）
# ---------------------------------------------------------------------------
def detect_format_bytes(head):
    """根据文件头魔数判断音频格式。"""
    if head[:4] == b'fLaC':
        return 'flac'
    if head[:3] == b'ID3' or (len(head) > 1 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return 'mp3'
    if head[:4] == b'RIFF':
        return 'wav'
    if head[:4] == b'OggS':
        return 'ogg'
    if head[4:8] == b'ftyp':
        return 'm4a'
    return 'unknown'


def detect_format_path(path):
    with open(path, 'rb') as f:
        return detect_format_bytes(f.read(8))


def is_valid_audio_bytes(head):
    """校验魔数：合法音频返回 True。非法结果一律丢弃，绝不产出损坏文件。"""
    return detect_format_bytes(head) != 'unknown'


# ---------------------------------------------------------------------------
# 第三部分：KGMusicV3.db（KGG 密钥库）页解密
#
# 酷狗客户端把每首歌的 ekey 存在 KGMusicV3.db 里。该库使用自定义页加密
# （AES-128-CBC，页大小 1024 字节），页密钥/IV 由社区已公开的主密钥常量派生
# （与 unlock-music / Kugo-Music-Converter 一致）。可用环境变量
# KGG_DB_MASTER_KEY（hex）覆盖。解密全程在内存中完成，不落盘。
# ---------------------------------------------------------------------------
DB_PAGE = 0x400
SQLITE_HDR = b'SQLite format 3\x00'
DEFAULT_MASTER_KEY = bytes([0x1D, 0x61, 0x31, 0x45, 0xB2, 0x47, 0xBF, 0x7F,
                            0x3D, 0x18, 0x96, 0x72, 0x14, 0x4F, 0xE4, 0xBF])


def _u32(x):
    return x & 0xFFFFFFFF


def _next_page_iv(seed):
    left = _u32(seed * 0x9EF4)
    right = _u32((seed // 0xCE26) * 0x7FFFFF07)
    value = _u32(left - right)
    if value & 0x80000000 == 0:
        return value
    return _u32(value + 0x7FFFFF07)


def _page_key(seed, master):
    buf = master + struct.pack('<I', seed) + struct.pack('<I', 0x546C4173)
    return hashlib.md5(buf).digest()


def _page_iv(seed):
    iv = b''
    s = _u32(seed + 1)
    for _ in range(4):
        s = _next_page_iv(s)
        iv += struct.pack('<I', s)
    return hashlib.md5(iv).digest()


def decrypt_kgg_db(db_path, master=None):
    """解密 KGMusicV3.db，返回 {audioHash: ekey} 映射。"""
    if AES is None:
        raise RuntimeError('处理 .kgg 需要 pycryptodome：pip install pycryptodome')
    if master is None:
        env = os.environ.get('KGG_DB_MASTER_KEY', '').strip()
        master = bytes.fromhex(env) if env else DEFAULT_MASTER_KEY
    data = open(db_path, 'rb').read()
    if data[:16] == SQLITE_HDR:
        plain = data  # 未加密的数据库，直接用
    else:
        if len(data) % DB_PAGE != 0:
            raise ValueError('密钥库大小非法：%d' % len(data))
        buf = bytearray(data)
        p1 = bytearray(buf[:DB_PAGE])
        o10 = struct.unpack_from('<I', p1, 0x10)[0]
        o14 = struct.unpack_from('<I', p1, 0x14)[0]
        v6 = ((o10 & 0xFF) << 8) | ((o10 & 0xFF00) << 16)
        if not (o14 == 0x20204000 and _u32(v6 - 0x200) <= 0xFE00 and ((v6 - 1) & v6) == 0):
            raise ValueError('密钥库：页 1 头部校验失败')
        expected = bytes(p1[0x10:0x18])
        p1[0x10:0x18] = p1[0x08:0x10]  # 把存放在 [0x08:0x10] 的校验锚移到解密区开头
        c = AES.new(_page_key(1, master), AES.MODE_CBC, _page_iv(1))
        p1[0x10:] = c.decrypt(bytes(p1[0x10:]))
        if p1[0x10:0x18] != expected:
            raise ValueError('密钥库：页 1 完整性校验失败（主密钥不匹配？）')
        p1[:16] = SQLITE_HDR  # 还原标准 SQLite 魔数
        buf[:DB_PAGE] = p1
        for pg in range(2, len(buf) // DB_PAGE + 1):
            off = (pg - 1) * DB_PAGE
            c = AES.new(_page_key(pg, master), AES.MODE_CBC, _page_iv(pg))
            buf[off:off + DB_PAGE] = c.decrypt(bytes(buf[off:off + DB_PAGE]))
        plain = bytes(buf)
    con = sqlite3.connect(':memory:')
    try:
        con.deserialize(plain)
        rows = con.execute(
            "SELECT EncryptionKeyId, EncryptionKey FROM ShareFileItems "
            "WHERE EncryptionKeyId IS NOT NULL AND EncryptionKeyId != '' "
            "AND EncryptionKey IS NOT NULL AND EncryptionKey != ''"
        ).fetchall()
    finally:
        con.close()
    return {k if isinstance(k, str) else k.decode('latin-1'):
            v if isinstance(v, str) else v.decode('latin-1') for k, v in rows}


def load_kgg_key_file(path):
    """解析 kgg.key 文本文件（每行 `<audioHash>$<ekey>`）。"""
    out = {}
    for line in open(path, 'r', encoding='utf-8', errors='replace').read().splitlines():
        if '$' in line:
            k, v = line.split('$', 1)
            if k:
                out[k] = v
    return out


def _kugou_data_dirs():
    """收集常见酷狗数据目录（跨平台）：Windows 看 AppData，macOS 看 Library。"""
    dirs = []
    home = os.path.expanduser('~')
    if os.name == 'nt':
        for env in ('APPDATA', 'LOCALAPPDATA'):
            base = os.environ.get(env)
            if base:
                dirs.append(os.path.join(base, 'KuGou8'))
    else:
        # macOS：数据目录在 ~/Library/Application Support 下名字含 KuGou 的
        # 文件夹；沙盒版客户端则藏在 ~/Library/Containers/<App>/Data/... 里
        support = os.path.join(home, 'Library', 'Application Support')
        if os.path.isdir(support):
            try:
                for name in os.listdir(support):
                    if 'kugou' in name.lower():
                        dirs.append(os.path.join(support, name))
            except OSError:
                pass
        containers = os.path.join(home, 'Library', 'Containers')
        if os.path.isdir(containers):
            try:
                for name in os.listdir(containers):
                    if 'kugou' in name.lower():
                        dirs.append(os.path.join(containers, name, 'Data',
                                                 'Library', 'Application Support'))
            except OSError:
                pass
    return [d for d in dirs if os.path.isdir(d)]


def discover_kgg_db():
    """自动发现本机酷狗密钥库 KGMusicV3.db，找不到返回 None。"""
    for base in _kugou_data_dirs():
        cand = os.path.join(base, 'KGMusicV3.db')
        if os.path.exists(cand):
            return cand
    return None


def _read_kugou_ini_download_path():
    """从酷狗配置文件 KuGou.ini 读取用户设置的下载目录（DownloadPath）。

    该文件是 UTF-16 编码的 ini；不同酷狗版本可能不同，解码失败返回 None。
    """
    for base in _kugou_data_dirs():
        ini = os.path.join(base, 'KuGou.ini')
        if not os.path.exists(ini):
            continue
        raw = open(ini, 'rb').read()
        text = None
        for enc in ('utf-16', 'utf-16-le', 'gbk', 'utf-8'):
            try:
                text = raw.decode(enc)
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        if not text:
            continue
        for line in text.splitlines():
            if line.strip().lower().startswith('downloadpath='):
                path = line.split('=', 1)[1].strip().strip('"')
                if path and os.path.isdir(path):
                    return path
    return None


def _dir_has_encrypted_audio(path):
    """目录中是否存在加密音频文件（快速判断，不递归）。"""
    try:
        for name in os.listdir(path):
            if os.path.splitext(name)[1].lower().lstrip('.') in AUDIO_EXTS:
                return True
    except OSError:
        return False
    return False


def discover_kugou_music_dir():
    r"""自动寻找酷狗的下载文件夹。

    查找顺序：
    1. 酷狗配置 KuGou.ini 里记录的下载目录（DownloadPath）及其下的
       KugouMusic / KGMusic 子目录 —— 这是最准确的来源；
    2. 常见默认位置：Windows 扫描每个盘符（X:\KuGou\KugouMusic 等、
       Program Files / Program Files (x86) 下的 KuGou / KuGou8）；macOS 查
       用户"音乐"（~/Music/KuGou）与"文档"目录；两边都会找酷狗数据目录
       里的 KugouMusic / KGMusic 子目录。

    返回含有加密音频文件的第一个目录；若没找到含加密文件的目录，
    返回第一个存在的候选目录；全部落空返回 None。
    """
    candidates = []
    dl = _read_kugou_ini_download_path()
    if dl:
        candidates.append(dl)
        candidates.append(os.path.join(dl, 'KugouMusic'))
        candidates.append(os.path.join(dl, 'KGMusic'))
    # Windows：遍历所有盘符的常见默认位置（C 盘、D 盘……每个盘都找一遍）：
    # 各盘根目录 + Program Files / Program Files (x86) 下的 KuGou / KuGou8
    if os.name == 'nt':
        import string
        for letter in string.ascii_uppercase:
            root = letter + ':\\'
            if not os.path.exists(root):
                continue
            for sub in ('KuGou', 'KuGou8',
                        os.path.join('Program Files', 'KuGou'),
                        os.path.join('Program Files', 'KuGou8'),
                        os.path.join('Program Files (x86)', 'KuGou'),
                        os.path.join('Program Files (x86)', 'KuGou8')):
                candidates.append(os.path.join(root, sub, 'KugouMusic'))
                candidates.append(os.path.join(root, sub, 'KGMusic'))
            # 极旧版本：直接下载进安装目录的 KGMusic\DownloadMusic
            candidates.append(os.path.join(root, 'Program Files', 'KuGou',
                                            'KGMusic', 'DownloadMusic'))
            candidates.append(os.path.join(root, 'Program Files (x86)', 'KuGou',
                                            'KGMusic', 'DownloadMusic'))
    # 用户"音乐"/"文档"文件夹（新版客户端默认 %USERPROFILE%\Music\KuGou）
    home = os.path.expanduser('~')
    candidates.append(os.path.join(home, 'Music', 'KuGou'))
    candidates.append(os.path.join(home, 'Music', 'KuGou', 'KugouMusic'))
    candidates.append(os.path.join(home, 'Music', 'KuGou', 'KGMusic'))
    candidates.append(os.path.join(home, 'Music', 'KugouMusic'))
    candidates.append(os.path.join(home, 'Music', 'KGMusic'))
    candidates.append(os.path.join(home, 'Documents', 'KuGou', 'KGMusic'))
    candidates.append(os.path.join(home, 'Documents', 'KuGou', 'KugouMusic'))
    # 酷狗数据目录下的歌曲子目录（macOS: ~/Library/Application Support/KuGou 等）
    for base in _kugou_data_dirs():
        candidates.append(os.path.join(base, 'KugouMusic'))
        candidates.append(os.path.join(base, 'KGMusic'))
        candidates.append(os.path.join(base, 'DownloadMusic'))
    candidates = [os.path.normpath(c) for c in candidates]
    seen, unique = set(), []
    for c in candidates:
        if c not in seen and os.path.isdir(c):
            seen.add(c)
            unique.append(c)
    # 优先返回真正含加密歌曲的目录
    for c in unique:
        if _dir_has_encrypted_audio(c):
            return c
    return unique[0] if unique else None


def find_kgg_keymap(db_path=None, keyfile=None):
    """汇总 kgg 密钥映射。先读密钥库（自动发现或指定路径），再叠加 keyfile。"""
    keymap = {}
    db = db_path or discover_kgg_db()
    if db and os.path.exists(db):
        keymap.update(decrypt_kgg_db(db))
    if keyfile and os.path.exists(keyfile):
        keymap.update(load_kgg_key_file(keyfile))
    return keymap


# ---------------------------------------------------------------------------
# 第四部分：ekey 派生（腾讯 TEA，32 半轮）
# ---------------------------------------------------------------------------
DELTA = 0x9E3779B9
RAW_KEY_PREFIX_V2 = b'QQMusic EncV2,Key:'
DERIVE_V2_KEY1 = bytes([0x33, 0x38, 0x36, 0x5A, 0x4A, 0x59, 0x21, 0x40, 0x23, 0x2A, 0x24, 0x25, 0x5E, 0x26, 0x29, 0x28])
DERIVE_V2_KEY2 = bytes([0x2A, 0x2A, 0x23, 0x21, 0x28, 0x23, 0x24, 0x25, 0x26, 0x5E, 0x61, 0x31, 0x63, 0x5A, 0x2C, 0x54])


def _tea_decrypt_block(v0, v1, k, rounds=32):
    # rounds 语义与 x/crypto/tea 对齐：32 个半轮 = 16 次双半轮循环，
    # sum 初始值 = delta * (rounds//2)。此细节错了整个 ekey 都解不出来。
    s = (DELTA * (rounds // 2)) & 0xFFFFFFFF
    for _ in range(rounds // 2):
        v1 = (v1 - ((((v0 << 4) & 0xFFFFFFFF) + k[2]) ^ ((v0 + s) & 0xFFFFFFFF) ^ (((v0 >> 5) & 0xFFFFFFFF) + k[3]))) & 0xFFFFFFFF
        v0 = (v0 - ((((v1 << 4) & 0xFFFFFFFF) + k[0]) ^ ((v1 + s) & 0xFFFFFFFF) ^ (((v1 >> 5) & 0xFFFFFFFF) + k[1]))) & 0xFFFFFFFF
        s = (s - DELTA) & 0xFFFFFFFF
    return v0, v1


def _tea_decrypt(data, key):
    """TEA ECB 解密（8 字节块，大端）。"""
    k = struct.unpack('>4I', key)
    out = bytearray()
    for i in range(0, len(data), 8):
        v0, v1 = struct.unpack('>2I', data[i:i + 8])
        v0, v1 = _tea_decrypt_block(v0, v1, k)
        out += struct.pack('>2I', v0, v1)
    return bytes(out)


def _simple_make_key(salt, length):
    import math
    out = bytearray()
    for i in range(length):
        out.append(int(abs(math.tan(salt + i * 0.1)) * 100.0) & 0xFF)
    return bytes(out)


def _decrypt_tencent_tea(in_buf, key):
    """TC_TEA CBC 解密（TarsCpp 变体：明文[i] = D(dest) ^ ivPrev）。"""
    salt_len, zero_len = 2, 7
    if len(in_buf) % 8 != 0:
        raise ValueError('TEA：输入长度不是 8 的倍数')
    if len(in_buf) < 16:
        raise ValueError('TEA：输入过小')
    dest = bytearray(_tea_decrypt(in_buf[:8], key))
    pad_len = dest[0] & 0x7
    out_len = len(in_buf) - 1 - pad_len - salt_len - zero_len
    out = bytearray(out_len)
    iv_prev = bytearray(8)
    iv_cur = in_buf[:8]
    pos = 8
    dest_idx = 1 + pad_len

    def crypt_block():
        nonlocal iv_prev, iv_cur, pos, dest_idx, dest
        iv_prev = iv_cur
        iv_cur = in_buf[pos:pos + 8]
        for i in range(8):
            dest[i] ^= in_buf[pos + i]
        dest[:] = _tea_decrypt(bytes(dest), key)
        pos += 8
        dest_idx = 0

    i = 1
    while i <= salt_len:
        if dest_idx < 8:
            dest_idx += 1
            i += 1
        elif dest_idx == 8:
            crypt_block()
    out_pos = 0
    while out_pos < out_len:
        if dest_idx < 8:
            out[out_pos] = dest[dest_idx] ^ iv_prev[dest_idx]
            dest_idx += 1
            out_pos += 1
        elif dest_idx == 8:
            crypt_block()
    return bytes(out)


def derive_key(ekey_str):
    """ekey 字符串 → QMC2 原始密钥（支持 EncV1 / EncV2 前缀）。"""
    raw = base64.b64decode(ekey_str)
    if raw.startswith(RAW_KEY_PREFIX_V2):
        buf = _decrypt_tencent_tea(raw[len(RAW_KEY_PREFIX_V2):], DERIVE_V2_KEY1)
        buf = _decrypt_tencent_tea(buf, DERIVE_V2_KEY2)
        raw = base64.b64decode(buf)
    if len(raw) < 16:
        raise ValueError('ekey 过短')
    simple = _simple_make_key(106, 8)
    tea_key = bytearray(16)
    for i in range(8):
        tea_key[i << 1] = simple[i]
        tea_key[i << 1 | 1] = raw[i]
    rs = _decrypt_tencent_tea(raw[8:], bytes(tea_key))
    return raw[:8] + rs


# ---------------------------------------------------------------------------
# 第五部分：QMC2 流加密（MAP / RC4）—— QQ 音乐与酷狗 kgg 共用
# ---------------------------------------------------------------------------
class QMC2Map:
    """QMCv2 MAP 加密（密钥长度 ≤ 300 字节），按 0x8000 掩码表循环取掩码。"""

    def __init__(self, key):
        self.key = key
        self.size = len(key)
        masks = bytearray(0x8000)
        for o in range(0x8000):
            idx = (o * o + 71214) % self.size
            v = key[idx]
            r = ((idx & 7) + 4) % 8
            # 注意：(v << r) | (v >> r) 不是循环移位 —— 两个移位方向使用同一个
            # 位移量且在 8 位内截断。这是 QMC2 的既定行为，"修正"它反而全错。
            masks[o] = ((v << r) | (v >> r)) & 0xFF
        self.masks = bytes(masks)

    def _mask_stream(self, offset, n):
        out = bytearray()
        off = offset
        while len(out) < n:
            if off <= 0x7FFF:
                mo = off
                cs = 0x7FFF - off + 1
            else:
                mo = off % 0x7FFF
                cs = 0x7FFF - mo
            cs = min(cs, n - len(out))
            out += self.masks[mo:mo + cs]
            off += cs
        return bytes(out[:n])

    def decrypt(self, audio, offset=0):
        ms = self._mask_stream(offset, len(audio))
        return (int.from_bytes(audio, 'big') ^ int.from_bytes(ms, 'big')).to_bytes(len(audio), 'big')


class QMC2RC4:
    """QMCv2 RC4 加密（密钥长度 > 300 字节），按 5120 字节分段重启 PRGA。"""

    SEG = 5120
    FIRST = 128

    def __init__(self, key):
        self.key = key
        self.n = n = len(key)
        # Go 语义：box[i] = byte(i) —— n > 256 时按 256 截断回绕，必须保持。
        box = [i & 0xFF for i in range(n)]
        j = 0
        for i in range(n):
            j = (j + box[i] + key[i % n]) % n
            box[i], box[j] = box[j], box[i]
        self.box = bytes(box)
        h = 1
        for i in range(n):
            v = key[i]
            if v == 0:
                continue
            nh = (h * v) & 0xFFFFFFFF
            if nh == 0 or nh <= h:
                break
            h = nh
        self.hash = h

    def _seg_skip(self, seg_id):
        seed = self.key[seg_id % self.n]
        denom = (seg_id + 1) * seed
        if denom == 0:
            # Go amd64：除零 → +Inf → int64(+Inf) = INT64_MIN，再按位转 uint64 取模。
            # 与 unlock-music 逐字节对齐的关键细节。
            return 0x8000000000000000 % self.n
        idx = int(float(self.hash) / float(denom) * 100.0)
        return (idx & 0xFFFFFFFFFFFFFFFF) % self.n

    def _enc_segment(self, buf, start, length, off):
        box = bytearray(self.box)
        j = k = 0
        n = self.n
        skip = (off % self.SEG) + self._seg_skip(off // self.SEG)
        for i in range(-skip, length):
            j = (j + 1) % n
            k = (box[j] + k) % n
            box[j], box[k] = box[k], box[j]
            if i >= 0:
                buf[start + i] ^= box[(box[j] + box[k]) % n]

    def decrypt(self, audio, offset=0):
        buf = bytearray(audio)
        off = offset
        to_process = len(buf)
        processed = 0
        if off < self.FIRST:
            bs = min(to_process, self.FIRST - off)
            for i in range(bs):
                buf[processed + i] ^= self.key[self._seg_skip(off + i)]
            off += bs; to_process -= bs; processed += bs
            if to_process == 0:
                return bytes(buf)
        if off % self.SEG != 0:
            bs = min(to_process, self.SEG - off % self.SEG)
            self._enc_segment(buf, processed, bs, off)
            off += bs; to_process -= bs; processed += bs
            if to_process == 0:
                return bytes(buf)
        while to_process > self.SEG:
            self._enc_segment(buf, processed, self.SEG, off)
            off += self.SEG; to_process -= self.SEG; processed += self.SEG
        if to_process > 0:
            self._enc_segment(buf, processed, to_process, off)
        return bytes(buf)


def make_qmc2(ekey_str):
    """根据 ekey 构建对应的 QMC2 解密器。"""
    key = derive_key(ekey_str)
    if len(key) > 300:
        return QMC2RC4(key)
    return QMC2Map(key)


# ---------------------------------------------------------------------------
# 第六部分：.kgg 文件解密
# ---------------------------------------------------------------------------
KGM_MAGIC = bytes([0x7C, 0xD5, 0x32, 0xEB, 0x86, 0x02, 0x7F, 0x4B, 0xA8, 0xAF, 0xA6, 0x8E, 0x0F, 0xFF, 0x99, 0x14])
VPR_MAGIC = bytes([0x05, 0x28, 0xBC, 0x96, 0xE9, 0xE4, 0x5A, 0x43, 0x91, 0xAA, 0xBD, 0xD0, 0x7A, 0xF5, 0x36, 0x31])


def decrypt_kgg(in_path, out_path, keymap):
    """解密单个 .kgg 文件（需 {audioHash: ekey} 映射），返回音频格式。"""
    with open(in_path, 'rb') as f:
        head = f.read(0x48 + 256)
    if len(head) < 0x48:
        raise ValueError('kgg：文件过小')
    if head[:16] not in (KGM_MAGIC, VPR_MAGIC):
        raise ValueError('kgg：魔数不匹配（这不是 kgg 文件？）')
    header_len = struct.unpack_from('<I', head, 0x10)[0]
    ver = struct.unpack_from('<I', head, 0x14)[0]
    if ver != 5:
        raise ValueError('kgg：不支持的加密版本 %d' % ver)
    hash_len = struct.unpack_from('<I', head, 0x44)[0]
    if hash_len <= 0 or hash_len > 256:
        raise ValueError('kgg：audioHash 长度异常 %d' % hash_len)
    audio_hash = head[0x48:0x48 + hash_len].decode('latin-1')
    if audio_hash not in keymap:
        raise KeyError('kgg：密钥库中找不到这首歌的密钥（请在酷狗里播放/下载一次后重试）')
    cipher = make_qmc2(keymap[audio_hash])
    with open(in_path, 'rb') as f:
        f.seek(header_len)
        audio = f.read()
    data = cipher.decrypt(audio, 0)
    fmt = detect_format_bytes(data[:8])
    if fmt == 'unknown':
        raise ValueError('kgg：解密结果的音频头非法（密钥错误？）')
    with open(out_path, 'wb') as g:
        g.write(data)
    return fmt


# ---------------------------------------------------------------------------
# 第七部分：FFmpeg 转码（可选功能）
# ---------------------------------------------------------------------------
def check_ffmpeg():
    """检测系统中的 FFmpeg，返回可执行文件路径或 None。"""
    return shutil.which('ffmpeg')


def transcode(src, dst, target_fmt):
    """调用 FFmpeg 把 src 转成 target_fmt（flac / mp3 / wav）。返回 dst。

    MP3 使用 320kbps CBR；FLAC / WAV 为无损转码。
    """
    exe = check_ffmpeg()
    if not exe:
        raise RuntimeError('未找到 FFmpeg，无法转码（保持原始格式无需 FFmpeg）')
    if target_fmt == 'flac':
        cmd = [exe, '-y', '-i', src, '-c:a', 'flac', dst]
    elif target_fmt == 'mp3':
        cmd = [exe, '-y', '-i', src, '-c:a', 'libmp3lame', '-b:a', '320k', dst]
    elif target_fmt == 'wav':
        cmd = [exe, '-y', '-i', src, '-c:a', 'pcm_s16le', dst]
    else:
        raise ValueError('不支持的转码目标格式：%s' % target_fmt)
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if proc.returncode != 0 or not os.path.exists(dst):
        raise RuntimeError('FFmpeg 转码失败：%s' % proc.stderr.decode('utf-8', 'replace')[-300:])
    return dst


# ---------------------------------------------------------------------------
# 第八部分：高层 API（供图形界面与命令行共用）
# ---------------------------------------------------------------------------
def collect_files(src, only=None):
    """收集加密音频。src 可以是目录、单个文件路径，或多个文件路径的列表。

    返回 [(路径, 扩展名小写)]。
    """
    if isinstance(src, (list, tuple)):
        out = []
        for p in src:
            ext = os.path.splitext(p)[1].lower().lstrip('.')
            if ext in AUDIO_EXTS and (not only or ext in only):
                out.append((p, ext))
        return out
    if os.path.isfile(src):
        ext = os.path.splitext(src)[1].lower().lstrip('.')
        if ext not in AUDIO_EXTS:
            raise ValueError('不支持的输入格式：.%s（支持：%s）' % (ext, '/'.join(AUDIO_EXTS)))
        return [(src, ext)]
    picked = []
    for name in sorted(os.listdir(src)):
        ext = os.path.splitext(name)[1].lower().lstrip('.')
        if ext in AUDIO_EXTS and (not only or ext in only):
            picked.append((os.path.join(src, name), ext))
    return picked


def decrypt_file(src, out_dir, target_fmt='auto', keymap=None, db_path=None, keyfile=None):
    """解密单个文件到 out_dir，按需转码。返回 (输出路径, 实际格式)。

    target_fmt：'auto' 保持解密后的原始格式（无损）；'flac'/'mp3'/'wav' 转码。
    """
    os.makedirs(out_dir, exist_ok=True)
    ext = os.path.splitext(src)[1].lower().lstrip('.')
    if ext not in AUDIO_EXTS:
        raise ValueError('不支持的输入格式：.%s' % ext)
    base = os.path.splitext(os.path.basename(src))[0]
    tmp = os.path.join(out_dir, base + '.dec.tmp')
    if ext == 'kgg':
        if keymap is None:
            keymap = find_kgg_keymap(db_path, keyfile)
        raw_fmt = decrypt_kgg(src, tmp, keymap)
    else:
        raw_fmt = decrypt_xor_stream(src, tmp, is_vpr=(ext == 'vpr'))
    try:
        if target_fmt != 'auto' and target_fmt != raw_fmt:
            final = transcode(tmp, os.path.join(out_dir, base + '.' + target_fmt), target_fmt)
            os.remove(tmp)
            return final, target_fmt
        final = os.path.join(out_dir, base + '.' + raw_fmt)
        os.replace(tmp, final)
        return final, raw_fmt
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def batch_convert(src, out_dir, target_fmt='auto', procs=None, db_path=None,
                  keyfile=None, progress_cb=None):
    """批量解密（+ 可选转码）。src 可以是文件或目录。

    progress_cb(done, total, path, status, info)：每完成/失败一个文件回调一次，
    status 为 'ok' / 'fail'。返回 (成功数, 失败数)。
    """
    os.makedirs(out_dir, exist_ok=True)
    items = collect_files(src)
    if not items:
        if progress_cb:
            progress_cb(0, 0, src, 'ok', '未发现加密音频文件')
        return 0, 0
    if procs is None:
        procs = min(8, os.cpu_count() or 4)

    # 只有目录里存在 kgg 时才需要加载密钥库（kgm/kgma/vpr 完全不需要）
    has_kgg = any(ext == 'kgg' for _, ext in items)
    keymap = find_kgg_keymap(db_path, keyfile) if has_kgg else {}
    if has_kgg and not keymap:
        raise RuntimeError('本目录包含 .kgg 文件，但找不到可用密钥（请先安装酷狗客户端并播放一次）')

    # 同名冲突（同一首歌既有 .kgma 又有 .kgg）时，kgg 版本输出名加 " (kgg)"
    from collections import Counter
    base_count = Counter(os.path.splitext(os.path.basename(p))[0] for p, _ in items)

    jobs = []
    for path, ext in items:
        base = os.path.splitext(os.path.basename(path))[0]
        if ext == 'kgg' and base_count[base] > 1:
            base = base + ' (kgg)'
        jobs.append((path, base, ext))

    def run_one(job):
        path, base, ext = job
        tmp = os.path.join(out_dir, base + '.dec.tmp')
        try:
            if ext == 'kgg':
                raw_fmt = decrypt_kgg(path, tmp, keymap)
            else:
                raw_fmt = decrypt_xor_stream(path, tmp, is_vpr=(ext == 'vpr'))
            if target_fmt != 'auto' and target_fmt != raw_fmt:
                final = transcode(tmp, os.path.join(out_dir, base + '.' + target_fmt), target_fmt)
                os.remove(tmp)
                return (path, 'ok', target_fmt)
            final = os.path.join(out_dir, base + '.' + raw_fmt)
            os.replace(tmp, final)
            return (path, 'ok', raw_fmt)
        except Exception as e:
            if os.path.exists(tmp):
                os.remove(tmp)
            return (path, 'fail', '%s: %s' % (type(e).__name__, e))

    done, ok_count, fail_count = 0, 0, 0
    if len(jobs) > 2 and (procs or 1) > 1:
        from multiprocessing import Pool
        with Pool(procs) as pool:
            for path, status, info in pool.imap_unordered(run_one, jobs):
                done += 1
                ok_count += status == 'ok'
                fail_count += status == 'fail'
                if progress_cb:
                    progress_cb(done, len(jobs), path, status, info)
    else:
        for job in jobs:
            path, status, info = run_one(job)
            done += 1
            ok_count += status == 'ok'
            fail_count += status == 'fail'
            if progress_cb:
                progress_cb(done, len(jobs), path, status, info)
    return ok_count, fail_count


# ---------------------------------------------------------------------------
# 第九部分：命令行入口
# ---------------------------------------------------------------------------
def main(argv=None):
    if os.name == 'nt':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

    # 完整性自校验：文件被修改/缺失时拒绝运行（防篡改保护，见 kugou_integrity.py）
    ok, problems = integrity.verify()
    if not ok:
        print(integrity.fail_text(problems))
        return 2

    ap = argparse.ArgumentParser(
        prog='kugou_unlock',
        description='酷狗加密音频解密工具（.kgm/.kgma/.vpr/.kgg → FLAC/MP3 等）。仅限个人使用。')
    ap.add_argument('src', help='加密文件，或包含加密文件的目录')
    ap.add_argument('dst', help='输出目录')
    ap.add_argument('--fmt', default='auto', choices=TARGET_FMTS,
                    help='输出格式：auto=保持原始（默认，无损）；flac/mp3/wav 需要 FFmpeg')
    ap.add_argument('--db', default=None, help='手动指定 KGMusicV3.db 路径（默认自动发现）')
    ap.add_argument('--keyfile', default=None, help='手动指定 kgg.key 文本文件')
    ap.add_argument('--procs', type=int, default=None, help='并行进程数（默认 min(8, CPU 核数)）')
    ap.add_argument('--only', default=None, help='只处理指定扩展名，如 kgm,kgg')
    ap.add_argument('--version', action='version',
                    version='酷狗解锁器 v' + __version__ + '  |  开发者: 鼠鼠shushuu  |  仅限个人使用 · 禁止商用 (personal use only)')
    args = ap.parse_args(argv)

    only = set(e.strip().lower() for e in args.only.split(',')) if args.only else None
    if args.fmt != 'auto' and not check_ffmpeg():
        ap.error('输出格式 %s 需要 FFmpeg，但系统中未找到（保持原始格式 auto 无需 FFmpeg）' % args.fmt)

    print(integrity.banner(__version__))
    print('-' * 60)

    def progress(done, total, path, status, info):
        mark = '✓' if status == 'ok' else '✗'
        print('[%d/%d] %s %s (%s)' % (done, total, mark, os.path.basename(path), info))

    try:
        ok, fail = batch_convert(args.src, args.dst, target_fmt=args.fmt,
                                 procs=args.procs, db_path=args.db,
                                 keyfile=args.keyfile, progress_cb=progress)
    except RuntimeError as e:
        print('错误：%s' % e, file=sys.stderr)
        return 1
    print('完成：%d 成功，%d 失败 → %s' % (ok, fail, os.path.abspath(args.dst)))
    return 0 if fail == 0 else 2


if __name__ == '__main__':
    sys.exit(main())
