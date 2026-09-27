"""纯 Python 传输层加密（AES-ECB / SM4-ECB），对应帆软 SecurityToolbox。

远程设计握手时密码字段必须按服务端 `transmissionEncryption` 模式加密：

  type 2 (AES)  SecurityToolbox.aesEncrypt(pwd, frontSeed)
                → key = frontSeed 的 UTF-8 字节截断/补零到 16 字节
                → AES/ECB/PKCS5Padding → Base64
  type 3 (SM4)  SecurityToolbox.sm4Encrypt(pwd, frontSM4Key)
                → key = frontSM4Key 的 32 位 hex → 16 字节
                → SM4/ECB + ISO7816-4 填充（0x80 后补 0x00）→ Base64

零第三方依赖：AES 轮密钥与 S 盒在导入时按定义生成，避免抄表出错。
"""

import base64
import struct

# ---------------------------------------------------------------------------
# AES (encrypt only, ECB)
# ---------------------------------------------------------------------------
_SBOX = []
_INV_SBOX = []


def _init_sbox():
    p = q = 1
    sbox = [0] * 256
    # 用生成元 3 枚举 GF(2^8)/0x11b 的乘法群
    while True:
        p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)
        q ^= q << 1
        q ^= q << 2
        q ^= q << 4
        q &= 0xFF
        if q & 0x80:
            q ^= 0x09
        x = q ^ ((q << 1) | (q >> 7)) ^ ((q << 2) | (q >> 6)) \
            ^ ((q << 3) | (q >> 5)) ^ ((q << 4) | (q >> 4))
        sbox[p] = (x ^ 0x63) & 0xFF
        if p == 1:
            break
    sbox[0] = 0x63
    inv = [0] * 256
    for i, v in enumerate(sbox):
        inv[v] = i
    _SBOX.extend(sbox)
    _INV_SBOX.extend(inv)


_init_sbox()


def _xtime(a):
    a <<= 1
    return (a ^ 0x1B) & 0xFF if a & 0x100 else a


def _mul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        a = _xtime(a)
        b >>= 1
    return r


def _expand_key(key: bytes):
    nk = len(key) // 4
    nr = nk + 6
    w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
    rcon = 1
    for i in range(nk, 4 * (nr + 1)):
        t = list(w[i - 1])
        if i % nk == 0:
            t = t[1:] + t[:1]
            t = [_SBOX[b] for b in t]
            t[0] ^= rcon
            rcon = _xtime(rcon) if rcon < 0x80 else ((rcon << 1) ^ 0x1B) & 0xFF
        elif nk > 6 and i % nk == 4:
            t = [_SBOX[b] for b in t]
        w.append([w[i - nk][j] ^ t[j] for j in range(4)])
    return w, nr


def _encrypt_block(block: bytes, w, nr) -> bytes:
    s = [block[i] ^ w[i // 4][i % 4] for i in range(16)]
    for rnd in range(1, nr + 1):
        s = [_SBOX[b] for b in s]
        # ShiftRows（状态按列优先存放：s[c*4+r]）
        t = s[:]
        for r in range(1, 4):
            row = [t[c * 4 + r] for c in range(4)]
            row = row[r:] + row[:r]
            for c in range(4):
                s[c * 4 + r] = row[c]
        if rnd != nr:
            ns = [0] * 16
            for c in range(4):
                col = s[c * 4:c * 4 + 4]
                ns[c * 4 + 0] = _mul(col[0], 2) ^ _mul(col[1], 3) ^ col[2] ^ col[3]
                ns[c * 4 + 1] = col[0] ^ _mul(col[1], 2) ^ _mul(col[2], 3) ^ col[3]
                ns[c * 4 + 2] = col[0] ^ col[1] ^ _mul(col[2], 2) ^ _mul(col[3], 3)
                ns[c * 4 + 3] = _mul(col[0], 3) ^ col[1] ^ col[2] ^ _mul(col[3], 2)
            s = ns
        s = [s[i] ^ w[rnd * 4 + i // 4][i % 4] for i in range(16)]
    return bytes(s)


def pkcs7_pad(data: bytes, block: int = 16) -> bytes:
    n = block - len(data) % block
    return data + bytes([n]) * n


def aes_ecb_encrypt(data: bytes, key: bytes) -> bytes:
    """AES/ECB/PKCS5Padding（JCE 的 "AES" 默认变换）。"""
    w, nr = _expand_key(key)
    data = pkcs7_pad(data)
    return b"".join(_encrypt_block(data[i:i + 16], w, nr) for i in range(0, len(data), 16))


def aes_encrypt_b64(plain: str, seed: str) -> str:
    """SecurityToolbox.aesEncrypt(String, String)：key = seed 前 16 字节（不足补 0）。"""
    key = seed.encode("utf-8")[:16].ljust(16, b"\x00")
    return base64.b64encode(aes_ecb_encrypt(plain.encode("utf-8"), key)).decode()


# ---------------------------------------------------------------------------
# SM4 (encrypt only, ECB)
# ---------------------------------------------------------------------------
SM4_SBOX = (
    0xd6, 0x90, 0xe9, 0xfe, 0xcc, 0xe1, 0x3d, 0xb7, 0x16, 0xb6, 0x14, 0xc2, 0x28, 0xfb, 0x2c, 0x05,
    0x2b, 0x67, 0x9a, 0x76, 0x2a, 0xbe, 0x04, 0xc3, 0xaa, 0x44, 0x13, 0x26, 0x49, 0x86, 0x06, 0x99,
    0x9c, 0x42, 0x50, 0xf4, 0x91, 0xef, 0x98, 0x7a, 0x33, 0x54, 0x0b, 0x43, 0xed, 0xcf, 0xac, 0x62,
    0xe4, 0xb3, 0x1c, 0xa9, 0xc9, 0x08, 0xe8, 0x95, 0x80, 0xdf, 0x94, 0xfa, 0x75, 0x8f, 0x3f, 0xa6,
    0x47, 0x07, 0xa7, 0xfc, 0xf3, 0x73, 0x17, 0xba, 0x83, 0x59, 0x3c, 0x19, 0xe6, 0x85, 0x4f, 0xa8,
    0x68, 0x6b, 0x81, 0xb2, 0x71, 0x64, 0xda, 0x8b, 0xf8, 0xeb, 0x0f, 0x4b, 0x70, 0x56, 0x9d, 0x35,
    0x1e, 0x24, 0x0e, 0x5e, 0x63, 0x58, 0xd1, 0xa2, 0x25, 0x22, 0x7c, 0x3b, 0x01, 0x21, 0x78, 0x87,
    0xd4, 0x00, 0x46, 0x57, 0x9f, 0xd3, 0x27, 0x52, 0x4c, 0x36, 0x02, 0xe7, 0xa0, 0xc4, 0xc8, 0x9e,
    0xea, 0xbf, 0x8a, 0xd2, 0x40, 0xc7, 0x38, 0xb5, 0xa3, 0xf7, 0xf2, 0xce, 0xf9, 0x61, 0x15, 0xa1,
    0xe0, 0xae, 0x5d, 0xa4, 0x9b, 0x34, 0x1a, 0x55, 0xad, 0x93, 0x32, 0x30, 0xf5, 0x8c, 0xb1, 0xe3,
    0x1d, 0xf6, 0xe2, 0x2e, 0x82, 0x66, 0xca, 0x60, 0xc0, 0x29, 0x23, 0xab, 0x0d, 0x53, 0x4e, 0x6f,
    0xd5, 0xdb, 0x37, 0x45, 0xde, 0xfd, 0x8e, 0x2f, 0x03, 0xff, 0x6a, 0x72, 0x6d, 0x6c, 0x5b, 0x51,
    0x8d, 0x1b, 0xaf, 0x92, 0xbb, 0xdd, 0xbc, 0x7f, 0x11, 0xd9, 0x5c, 0x41, 0x1f, 0x10, 0x5a, 0xd8,
    0x0a, 0xc1, 0x31, 0x88, 0xa5, 0xcd, 0x7b, 0xbd, 0x2d, 0x74, 0xd0, 0x12, 0xb8, 0xe5, 0xb4, 0xb0,
    0x89, 0x69, 0x97, 0x4a, 0x0c, 0x96, 0x77, 0x7e, 0x65, 0xb9, 0xf1, 0x09, 0xc5, 0x6e, 0xc6, 0x84,
    0x18, 0xf0, 0x7d, 0xec, 0x3a, 0xdc, 0x4d, 0x20, 0x79, 0xee, 0x5f, 0x3e, 0xd7, 0xcb, 0x39, 0x48,
)

_SM4_FK = (0xA3B1BAC6, 0x56AA3350, 0x677D9197, 0xB27022DC)
_SM4_CK = tuple(
    ((4 * i + 0) * 7 % 256) << 24 | ((4 * i + 1) * 7 % 256) << 16
    | ((4 * i + 2) * 7 % 256) << 8 | ((4 * i + 3) * 7 % 256)
    for i in range(32)
)


def _rotl(x, n):
    return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF


def _tau(a):
    return (SM4_SBOX[(a >> 24) & 0xFF] << 24 | SM4_SBOX[(a >> 16) & 0xFF] << 16
            | SM4_SBOX[(a >> 8) & 0xFF] << 8 | SM4_SBOX[a & 0xFF])


def _t(a):
    """轮函数线性变换 L(B) = B ^ B<<<2 ^ B<<<10 ^ B<<<18 ^ B<<<24"""
    b = _tau(a)
    return (b ^ _rotl(b, 2) ^ _rotl(b, 10) ^ _rotl(b, 18) ^ _rotl(b, 24)) & 0xFFFFFFFF


def _t_key(a):
    """密钥扩展线性变换 L'(B) = B ^ B<<<13 ^ B<<<23（与轮函数不同，别混用）"""
    b = _tau(a)
    return (b ^ _rotl(b, 13) ^ _rotl(b, 23)) & 0xFFFFFFFF


def _sm4_keys(key: bytes):
    mk = list(struct.unpack(">4I", key))
    k = [mk[i] ^ _SM4_FK[i] for i in range(4)]
    rk = []
    for i in range(32):
        k.append(k[i] ^ _t_key(k[i + 1] ^ k[i + 2] ^ k[i + 3] ^ _SM4_CK[i]))
        rk.append(k[i + 4])
    return rk


def _sm4_block(block: bytes, rk) -> bytes:
    x = list(struct.unpack(">4I", block))
    for i in range(32):
        x.append(x[i] ^ _t(x[i + 1] ^ x[i + 2] ^ x[i + 3] ^ rk[i]))
    return struct.pack(">4I", *x[32:36][::-1])


def iso7816_pad(data: bytes, block: int = 16) -> bytes:
    """SM4Util.padding(_, 1)：先补 0x80，再补 0x00 到块边界（满了也要补一整块）。"""
    n = block - len(data) % block
    return data + b"\x80" + b"\x00" * (n - 1)


def sm4_ecb_encrypt(data: bytes, key: bytes) -> bytes:
    rk = _sm4_keys(key)
    data = iso7816_pad(data)
    return b"".join(_sm4_block(data[i:i + 16], rk) for i in range(0, len(data), 16))


def sm4_encrypt_b64(plain: str, hex_key: str) -> str:
    """SecurityToolbox.sm4Encrypt(String, String)：key 是 32 位 hex。"""
    return base64.b64encode(sm4_ecb_encrypt(plain.encode("utf-8"), bytes.fromhex(hex_key))).decode()


# ---------------------------------------------------------------------------
def encrypt_password(password: str, mode: int, front_seed: str, front_sm4_key: str) -> str:
    """按服务端返回的 transmissionEncryption 模式加密密码。"""
    if mode == 2:      # EncryptionMode.AES
        return aes_encrypt_b64(password, front_seed)
    if mode == 3:      # EncryptionMode.SM4
        return sm4_encrypt_b64(password, front_sm4_key)
    raise ValueError(
        f"服务端传输加密模式 {mode} 暂不支持（0=RSA/1=SM2/2=AES/3=SM4），"
        "本工具只实现了 AES 与 SM4")
