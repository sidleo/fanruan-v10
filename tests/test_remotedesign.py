"""远程设计通道的编解码回归测试。

参考字节来自真实帆软实现（Designer 侧 com.fr.rpc.serialization.
SafeInvocationSerializer / ResultSerializer），用Designer jar 跑
`RefDump` 生成后固化在下面，因此这些用例不需要 Java、不需要联网。
"""

import gzip
import sys

import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcli import jser, rdcrypto                       # noqa: E402
from frcli.remotedesign import build_call, parse_response, normalize_report_path  # noqa: E402

META = {"username": "user", "id": "cid", "token": "tok",
        "encryptVersion": "encryptVersion"}

# WorkResource#write("reportlets/a/b.cpt", b"hello world")，Designer 原件
REQ_HEX = (
    "aced00057372003c636f6d2e66722e7270632e73657269616c697a6174696f6e"
    "2e496e766f636174696f6e53657269616c697a657224496e766f636174696f6e"
    "5061636b96ef0e975364b6360200044c00106465636c617265436c6173734e61"
    "6d657400124c6a6176612f6c616e672f537472696e673b4c000a6d6574686f64"
    "4e616d6571007e00015b000a706172616d54797065737400125b4c6a6176612f"
    "6c616e672f436c6173733b5b0006706172616d737400035b5b42787074002663"
    "6f6d2e66722e776f726b73706163652e7265736f757263652e576f726b526573"
    "6f757263657400057772697465757200125b4c6a6176612e6c616e672e436c61"
    "73733bab16d7aecbcd5a99020000787000000002767200106a6176612e6c616e"
    "672e537472696e67a0f0a4387a3bb3420200007870767200025b42acf317f806"
    "0854e00200007870757200035b5b424bfd19156767db37020000787000000002"
    "7571007e000b00000023aced00057400034a444baced00057400127265706f72"
    "746c6574732f612f622e6370747571007e000b00000030aced00057400034a44"
    "4baced0005757200025b42acf317f8060854e002000078700000000b68656c6c"
    "6f20776f726c64737200116a6176612e7574696c2e486173684d61700507dac1"
    "c31660d103000246000a6c6f6164466163746f724900097468726573686f6c64"
    "78703f4000000000000c7708000000100000000474000e656e63727970745665"
    "7273696f6e71007e00137400026964740003636964740008757365726e616d65"
    "74000475736572740005746f6b656e740003746f6b78"
)

# 真实服务器对 exist("reportlets") 的应答（gzip + ResultSerializer.Marker）
RESP_HEX = (
    "1f8b08000000000000005bf39681b5b888c120393f572fad48afa82059af38b5"
    "28333127b32ab124333f4f2f28b5b834a724182a965aa4e29b58949d5a34ed3d"
    "dff4e0946d664c0c4c3e0c9ca915c9a90520e5250ca23e59896589fa398979e9"
    "fa211945f9e5894939a9d6d10cdcf94959a9c9254e9525a9c5250c4cd14e1505"
    "05a54520c69acfe23fd838421e303130541430303058ae01baa98481d9cbc57b"
    "0dc475822023f54046ea39e5e7e7a426e69d55286ab83ae7d73b2606c62806d6"
    "b2c49cd2d48a024600898bc62bcd000000"
)


def test_build_call_matches_designer_bytes():
    body = build_call("com.fr.workspace.resource.WorkResource", "write",
                      [("java.lang.String", "reportlets/a/b.cpt"),
                       ("byte[]", b"hello world")], META)
    assert gzip.decompress(body).hex() == REQ_HEX


def test_parse_real_server_response():
    res = parse_response(bytes.fromhex(RESP_HEX))
    assert res.ok
    assert res.exception is None
    assert res.value.fields["value"] is True       # java.lang.Boolean


def test_normalize_report_path():
    assert normalize_report_path("/demo_group/示例用户/示例目录/a.cpt") == \
        "reportlets/demo_group/示例用户/示例目录/a.cpt"
    assert normalize_report_path("reportlets/x/y.cpt") == "reportlets/x/y.cpt"


def test_hashmap_iteration_order_is_java_like():
    keys = ["username", "id", "token", "encryptVersion"]
    order = [k for _, k in jser.hashmap_order(keys)]
    assert order == ["encryptVersion", "id", "username", "token"]


# --- 加密：与帆软 SecurityToolbox 的实测输出一一对应 -------------------------
SEED = "FGljWYEQgXJGEhTP"
SM4_KEY = "9d679ac64745e8a20ba776a1092463e1"
# (明文, aesEncrypt 结果, sm4Encrypt 结果)，由Designer jar 打印
CRYPTO_VECTORS = [
    ("808580", "ZlbXgIIyVQ3UGuMNGu2s6w==", "FNjXTd9tLJiJPwigcDqAvA=="),
    ("a", "aqR0fI1sONXoketSh+7FzA==", "XQS5StkL7vonNospyXrN8Q=="),
    ("超长密码测试中文", "Q4w0muWLfObakS8olrzFhPo9kJz6+6AheyRuBVtCRps=",
     "w07BzvvTEiV9TCVPCv61nGD6cUy5iXB4dEq6hzNgo1Y="),
]


def test_aes_encrypt_matches_fine_security_toolbox():
    for plain, aes, _ in CRYPTO_VECTORS:
        assert rdcrypto.aes_encrypt_b64(plain, SEED) == aes


def test_sm4_encrypt_matches_fine_security_toolbox():
    for plain, _, sm4 in CRYPTO_VECTORS:
        assert rdcrypto.sm4_encrypt_b64(plain, SM4_KEY) == sm4


def test_sm4_standard_vector():
    key = bytes.fromhex("0123456789abcdeffedcba9876543210")
    assert rdcrypto._sm4_block(key, rdcrypto._sm4_keys(key)).hex() == \
        "681edf34d206965e86b3e94f536e4246"


def test_aes_nist_vector():
    got = rdcrypto.aes_ecb_encrypt(
        bytes.fromhex("00112233445566778899aabbccddeeff"),
        bytes.fromhex("000102030405060708090a0b0c0d0e0f"))
    assert got[:16].hex() == "69c4e0d86a7b0430d8cdb78070b4c55a"
    assert len(got) == 32      # PKCS5 补齐一整块


def test_encrypt_password_dispatch():
    import pytest
    assert rdcrypto.encrypt_password("x", 2, SEED, SM4_KEY) == \
        rdcrypto.aes_encrypt_b64("x", SEED)
    assert rdcrypto.encrypt_password("x", 3, SEED, SM4_KEY) == \
        rdcrypto.sm4_encrypt_b64("x", SM4_KEY)
    with pytest.raises(ValueError):
        rdcrypto.encrypt_password("x", 0, SEED, SM4_KEY)


# --- 格式守门：挡住「把 format=cpt 的产物写回模板」 --------------------------
from frcli.exceptions import ApiError                                   # noqa: E402
from frcli.remotedesign import assert_template_bytes                    # noqa: E402

FORMAT_CPT_STUB = (b'<?xml version="1.0" encoding="UTF-8"?>\n'
                   b'<TableDataMap xmlVersion="20211223" releaseVersion="10.0.0">\n'
                   b'<TableData name="x" class="com.fr.data.impl.DBTableData">'
                   b'</TableData></TableDataMap>')
REAL_WORKBOOK = (b'<?xml version="1.0" encoding="UTF-8"?>\n'
                 b'<WorkBook xmlVersion="20211223" releaseVersion="10.0.0">\n'
                 b'<TableDataMap/></WorkBook>')


def test_guard_rejects_format_cpt_output():
    import pytest
    with pytest.raises(ApiError) as ei:
        assert_template_bytes(FORMAT_CPT_STUB)
    assert "WorkBook" in str(ei.value)


def test_guard_accepts_real_workbook():
    assert_template_bytes(REAL_WORKBOOK)


def test_guard_allow_format_escape_hatch():
    assert_template_bytes(FORMAT_CPT_STUB, allow_format=True)


# --- 写沙箱：FRCLI_WRITE_SCOPE（agent 跑测试时的硬边界） ---------------------
from frcli.remotedesign import assert_in_write_scope, WRITE_SCOPE_ENV   # noqa: E402

SCOPE = "demo_group/demo_user/skill测试"


def _allowed(path):
    try:
        assert_in_write_scope(path)
        return True
    except ApiError:
        return False


def test_write_scope_allows_inside(monkeypatch):
    monkeypatch.setenv(WRITE_SCOPE_ENV, SCOPE)
    assert _allowed(f"{SCOPE}/a.cpt")
    assert _allowed(f"reportlets/{SCOPE}/sub/b.cpt")
    assert _allowed(f"/reportlets/{SCOPE}/x.cpt")


def test_write_scope_blocks_outside_and_traversal(monkeypatch):
    monkeypatch.setenv(WRITE_SCOPE_ENV, SCOPE)
    assert not _allowed("demo_group/demo_user/dept_a/dept_b/sales_daily.cpt")
    assert not _allowed(f"{SCOPE}/../dept_a/dept_b/sales_daily.cpt")
    assert not _allowed(f"reportlets/{SCOPE}/../../sales_daily.cpt")
    assert not _allowed("reportlets/超级管理员/x.cpt")
    # 前缀相同但不是子目录（skill测试2）也要拦住
    assert not _allowed(f"{SCOPE}2/a.cpt")


def test_write_scope_unset_is_fail_closed(monkeypatch):
    """沉默 ≠ 不限制：没设范围又没 --any-path 时必须拒绝（0.6.0 起）。

    这条是 2026-09 那次事故的直接回归 —— 当时"未设 = 不限制"，于是
    `report edit --apply` 在没设范围的 shell 里写出了团队目录。
    """
    monkeypatch.delenv(WRITE_SCOPE_ENV, raising=False)
    monkeypatch.delenv("FRCLI_ALLOW_ANY_PATH", raising=False)
    assert not _allowed("任意/路径.cpt")
    assert not _allowed("platform/other_user/legacy_rpt.cpt")
    monkeypatch.setenv("FRCLI_ALLOW_ANY_PATH", "1")
    assert _allowed("任意/路径.cpt")


def test_upload_template_enforces_scope_before_network(monkeypatch, tmp_path):
    """回归：守门必须挂在 upload_template 里，且在**任何网络调用之前**。

    曾经只挂在 delete_template 上、upload 漏挂 —— 而 upload 才是有权限覆盖生产模板的那个。
    这里用哨兵替换网络层：越界路径若出现在 Sentinel 里，说明守门没拦住。
    """
    from frcli.remotedesign import upload_template, RemoteDesignSession
    from frcli.config import ServerConfig

    class Sentinel(Exception):
        pass

    def boom(*a, **k):
        raise Sentinel("网络调用被触发")

    monkeypatch.setattr(RemoteDesignSession, "check", boom)
    monkeypatch.setattr(RemoteDesignSession, "_post", boom)
    monkeypatch.setenv(WRITE_SCOPE_ENV, SCOPE)

    f = tmp_path / "ok.cpt"
    f.write_bytes(b'<?xml version="1.0" encoding="UTF-8"?>\n<WorkBook xmlVersion="20211223"/>')
    cfg = ServerConfig(name="t", url="https://x", username="u", password="p")

    for bad in ("demo_group/demo_user/dept_a/dept_b/sales_daily.cpt",
                f"{SCOPE}/../dept_a/sales_daily.cpt",
                "reportlets/超级管理员/x.cpt",
                f"{SCOPE}2/x.cpt"):
        with pytest.raises(ApiError) as ei:
            upload_template(cfg, str(f), bad, force=True)
        assert "FRCLI_WRITE_SCOPE" in str(ei.value), bad

    # 域内路径应放行到网络层（这里由哨兵证明它走过去了）
    with pytest.raises(Sentinel):
        upload_template(cfg, str(f), f"{SCOPE}/ok.cpt", force=True)
