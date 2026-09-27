"""`frcli rpc` 的离线回归测试：签名解析 / 策略判定 / 路径守门 / 参数编码 / 解码修复。

参考字节由JDK 的 `ObjectOutputStream` 生成后固化（`javap` 抽样的签名同理），
因此这些用例**不需要 Java、不需要联网**，换 FineReport 版本后仍可跑。
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from frcli import jser, rpc as R, rpc_catalog as C                       # noqa: E402
from frcli.exceptions import ApiError                                    # noqa: E402
from frcli.rpc_services import SERVICES, SOURCE_HOME as SERVICES_SOURCE_HOME  # noqa: E402

# ---------------------------------------------------------------------------
# 1. javap 签名解析
# ---------------------------------------------------------------------------
JAVAP_SAMPLE = """\
Compiled from "WorkResource.java"
public interface com.fr.workspace.resource.WorkResource {
  public abstract byte[] readFully(java.lang.String);
  public abstract void write(java.lang.String, byte[]);
  public abstract boolean rename(java.lang.String, java.lang.String);
  public abstract java.lang.String[] list(java.lang.String, com.fr.stable.Filter<java.lang.String>);
  public abstract long lastModified(java.lang.String) throws java.io.IOException;
  public default void save(java.lang.String, java.lang.String, byte[]);
  public static final java.lang.String PNG_FORMAT;
  static {};
}
"""


def test_parse_javap_kind_and_signatures():
    parsed = C.parse_javap(JAVAP_SAMPLE)
    assert parsed["kind"] == "interface"
    assert parsed["name"] == "com.fr.workspace.resource.WorkResource"
    by_name = {m["name"]: m for m in parsed["methods"]}
    assert by_name["readFully"] == {"name": "readFully", "returns": "byte[]",
                                    "params": ["java.lang.String"], "throws": [],
                                    "flags": "a"}
    assert by_name["write"]["params"] == ["java.lang.String", "byte[]"]
    assert by_name["save"]["flags"] == "d"
    assert by_name["lastModified"]["returns"] == "long"
    assert by_name["lastModified"]["throws"] == ["java.io.IOException"]
    # 字段不算方法；`static {};` 也不算
    assert by_name["readFully"] is not None and len(parsed["methods"]) == 6
    assert [f["name"] for f in parsed["fields"]] == ["PNG_FORMAT"]


def test_parse_javap_generics_and_varargs():
    text = (
        "public interface com.fr.data.operator.DataOperatorProvider {\n"
        "  public abstract java.util.List<com.fr.data.core.db.TableProcedure[]> "
        "getProcedures(com.fr.data.impl.Connection, java.lang.String[], boolean, boolean);\n"
        "  public abstract java.lang.String[] getTableSummary(com.fr.data.impl.Connection, "
        "java.lang.String...);\n"
        "  public abstract <T extends com.fr.config.entity.Base> java.util.List<T> "
        "getConfig(java.lang.Class<T>, java.lang.String);\n"
        "}\n")
    parsed = C.parse_javap(text)
    by_name = {m["name"]: m for m in parsed["methods"]}
    assert by_name["getProcedures"]["returns"] == \
        "java.util.List<com.fr.data.core.db.TableProcedure[]>"
    assert by_name["getProcedures"]["params"] == ["com.fr.data.impl.Connection",
                                                  "java.lang.String[]", "boolean", "boolean"]
    # 变长参数归一成数组；泛型方法剥掉类型参数声明、参数擦到 raw 类型
    assert by_name["getTableSummary"]["params"] == ["com.fr.data.impl.Connection",
                                                    "java.lang.String..."]
    assert by_name["getConfig"]["returns"] == "java.util.List<T>"
    assert by_name["getConfig"]["params"] == ["java.lang.Class", "java.lang.String"]
    assert jser.normalize_param_type("java.lang.String...") == "java.lang.String[]"


# ---------------------------------------------------------------------------
# 2. 策略表与真清单一致
# ---------------------------------------------------------------------------
def test_every_service_has_policy():
    assert set(R.POLICY) == set(SERVICES), "POLICY 与服务清单必须一一对应"


def test_policy_deny_for_platform_writes():
    assert R.method_policy("com.fr.config.dao.CommitHelper", "commit") == R.DENY
    assert R.method_policy("com.fr.workspace.server.authority.AuthorityOperator",
                           "updateAuthorities") == R.DENY
    assert R.method_policy("com.fr.base.rpc.encrypt.EncryptOperator", "readKey") == R.DENY
    assert R.method_policy("com.fr.workspace.server.vcs.VcsOperator", "rollbackTo") == R.DENY
    assert R.method_policy("com.fr.security.encryption.storage.StorageTransfer",
                           "decrypt") == R.DENY


def test_policy_read_and_write():
    assert R.method_policy("com.fr.workspace.resource.WorkResource", "readFully") == R.READ
    assert R.method_policy("com.fr.workspace.resource.WorkResource", "write") == R.WRITE
    assert R.method_policy("com.fr.workspace.server.lock.TplOperator", "delete") == R.WRITE
    assert R.method_policy("com.fr.workspace.server.vcs.VcsOperator",
                           "getVersions") == R.READ
    # 未列出的方法落回服务默认值（保守）
    assert R.method_policy("com.fr.workspace.resource.WorkResource", "brandNew") == R.WRITE
    assert R.method_policy("com.fr.config.dao.CommitHelper", "whatever") == R.DENY


# ---------------------------------------------------------------------------
# 3. 路径守门
# ---------------------------------------------------------------------------
SCOPE = "reportlets/demo_group/demo_user/skill测试"


@pytest.mark.parametrize("path", [
    SCOPE,
    SCOPE + "/a.cpt",
    "/" + SCOPE + "/x.cpt",                     # 前导斜杠
    "demo_group/demo_user/skill测试/a.cpt",      # 平台展示路径（归一化后同域）
    SCOPE + "/a.cpt.tmp",                       # 域内的 .tmp 落点，允许
])
def test_in_scope_allows(path):
    assert R.in_scope(path, SCOPE)


@pytest.mark.parametrize("path", [
    "reportlets/demo_group/other_user/x.cpt",              # 别人的目录
    SCOPE + "_evil/x.cpt",                                # 前缀伪造（段边界）
    SCOPE + "/../../other_user/x.cpt",                        # .. 穿越
    SCOPE + "/../skill测试2/x.cpt",
    "reportlets/demo_group/demo_user/skill测试2/x.cpt",
    "/etc/passwd",
    "reportlets",
    "",
    SCOPE.replace("reportlets", "reportlets/../reportlets") + "/../../x",
    SCOPE + ".tmp",                                       # 兄弟节点，绝不能剥 .tmp 后放行
    SCOPE + ".tmp/x.cpt",
])
def test_in_scope_denies(path):
    assert not R.in_scope(path, SCOPE)


def test_check_write_scope_uses_env(monkeypatch):
    monkeypatch.setenv("FRCLI_WRITE_SCOPE", SCOPE)                 # 0.6.0 起未设范围即拒绝
    ok = ("com.fr.workspace.resource.WorkResource", "write")
    R.check_write_scope(*ok, [SCOPE + "/a.cpt", b"data"])          # 范围内 → 放行
    with pytest.raises(ApiError):
        R.check_write_scope(*ok, ["reportlets/别人/a.cpt", b"data"])
    # 环境变量优先：设成别的目录后，默认范围也被拒
    monkeypatch.setenv("FRCLI_WRITE_SCOPE", "reportlets/另一个团队/测试")
    with pytest.raises(ApiError):
        R.check_write_scope(*ok, [SCOPE + "/a.cpt", b"data"])
    R.check_write_scope(*ok, ["reportlets/另一个团队/测试/a.cpt", b"data"])


def test_check_write_scope_rejects_unverifiable_write():
    # 写语义但没有声明路径参数 → 拒绝（无法验证范围）
    with pytest.raises(ApiError):
        R.check_write_scope("com.fr.workspace.server.lock.editlock.EditLockOperator",
                            "lock", [b"\x00"])


def test_rename_checks_both_paths(monkeypatch):
    monkeypatch.setenv("FRCLI_WRITE_SCOPE", SCOPE)
    spec = ("com.fr.workspace.resource.WorkResource", "rename")
    R.check_write_scope(*spec, [SCOPE + "/a.cpt", SCOPE + "/b.cpt"])
    with pytest.raises(ApiError):
        R.check_write_scope(*spec, [SCOPE + "/a.cpt", "reportlets/别人/b.cpt"])


# ---------------------------------------------------------------------------
# 4. 重载消歧
# ---------------------------------------------------------------------------
def test_resolve_method_by_arity():
    m = R.resolve_method("com.fr.workspace.resource.WorkResource", "list", arity=1)
    assert m.params == ("java.lang.String",)
    m2 = R.resolve_method("com.fr.workspace.resource.WorkResource", "list", arity=2)
    assert m2.params == ("java.lang.String", "com.fr.stable.Filter")
    with pytest.raises(ApiError):        # 没有 3 个参数的 list 重载
        R.resolve_method("com.fr.workspace.resource.WorkResource", "list", arity=3)


def test_resolve_method_by_sig():
    m = R.resolve_method("com.fr.workspace.resource.WorkResource", "list",
                         sig="java.lang.String")
    assert m.params == ("java.lang.String",)
    m2 = R.resolve_method("com.fr.workspace.resource.WorkResource", "list",
                          sig="java.lang.String,com.fr.stable.Filter")
    assert m2.params == ("java.lang.String", "com.fr.stable.Filter")


def test_resolve_service_short_name():
    assert R.resolve_service("WorkResource") == "com.fr.workspace.resource.WorkResource"
    with pytest.raises(ApiError):
        R.resolve_service("NoSuchService")


# ---------------------------------------------------------------------------
# 5. 参数编码：与 JDK 参考字节逐字节一致
# ---------------------------------------------------------------------------
#: JDK `ObjectOutputStream.writeObject(X.class)` 的原样输出
CLASS_OBJECTS = {
    "int": "aced000576720003696e7400000000000000000000007870",
    "boolean": "aced000576720007626f6f6c65616e00000000000000000000007870",
    "long": "aced0005767200046c6f6e6700000000000000000000007870",
    "double": "aced000576720006646f75626c6500000000000000000000007870",
    "float": "aced000576720005666c6f617400000000000000000000007870",
    "short": "aced00057672000573686f727400000000000000000000007870",
    "byte": "aced0005767200046279746500000000000000000000007870",
    "char": "aced0005767200046368617200000000000000000000007870",
    "java.lang.String":
        "aced0005767200106a6176612e6c616e672e537472696e67a0f0a4387a3bb3420200007870",
    "byte[]": "aced0005767200025b42acf317f8060854e00200007870",
    "int[]": "aced0005767200025b494dba602676eab2a50200007870",
    "java.lang.String[]":
        "aced0005767200135b4c6a6176612e6c616e672e537472696e673badd256e7e91d7b470200007870",
    "java.lang.Integer":
        "aced0005767200116a6176612e6c616e672e496e746567657212e2a0a4f781873802000149000576"
        "616c7565787200106a6176612e6c616e672e4e756d62657286ac951d0b94e08b0200007870",
    "java.lang.Long":
        "aced00057672000e6a6176612e6c616e672e4c6f6e673b8be490cc8f23df0200014a000576616c75"
        "65787200106a6176612e6c616e672e4e756d62657286ac951d0b94e08b0200007870",
    "java.lang.Boolean":
        "aced0005767200116a6176612e6c616e672e426f6f6c65616ecd207280d59cfaee0200015a000576"
        "616c75657870",
    "java.lang.Double":
        "aced0005767200106a6176612e6c616e672e446f75626c6580b3c24a296bfb040200014400057661"
        "6c7565787200106a6176612e6c616e672e4e756d62657286ac951d0b94e08b0200007870",
    "java.lang.Float":
        "aced00057672000f6a6176612e6c616e672e466c6f6174daedc9a2db3cf0ec02000146000576616c"
        "7565787200106a6176612e6c616e672e4e756d62657286ac951d0b94e08b0200007870",
    "java.lang.Short":
        "aced00057672000f6a6176612e6c616e672e53686f7274684d37133460da5202000153000576616c"
        "7565787200106a6176612e6c616e672e4e756d62657286ac951d0b94e08b0200007870",
    "java.lang.Byte":
        "aced00057672000e6a6176612e6c616e672e427974659c4e6084ee50f51c02000142000576616c75"
        "65787200106a6176612e6c616e672e4e756d62657286ac951d0b94e08b0200007870",
    "java.lang.Character":
        "aced0005767200136a6176612e6c616e672e436861726163746572348b47d96b1a26780200014300"
        "0576616c75657870",
}

#: `--arg` 的值编码（`mark + value` 里的 value 段）
VALUES = {
    ("int", "42"):
        "aced0005737200116a6176612e6c616e672e496e746567657212e2a0a4f781873802000149000576"
        "616c7565787200106a6176612e6c616e672e4e756d62657286ac951d0b94e08b02000078700000002a",
    ("long", "42"):
        "aced00057372000e6a6176612e6c616e672e4c6f6e673b8be490cc8f23df0200014a000576616c75"
        "65787200106a6176612e6c616e672e4e756d62657286ac951d0b94e08b0200007870"
        "000000000000002a",
    ("boolean", "true"):
        "aced0005737200116a6176612e6c616e672e426f6f6c65616ecd207280d59cfaee0200015a000576"
        "616c7565787001",
    ("double", "1.5"):
        "aced0005737200106a6176612e6c616e672e446f75626c6580b3c24a296bfb040200014400057661"
        "6c7565787200106a6176612e6c616e672e4e756d62657286ac951d0b94e08b0200007870"
        "3ff8000000000000",
    ("float", "1.5"):
        "aced00057372000f6a6176612e6c616e672e466c6f6174daedc9a2db3cf0ec02000146000576616c"
        "7565787200106a6176612e6c616e672e4e756d62657286ac951d0b94e08b02000078703fc00000",
    ("short", "7"):
        "aced00057372000f6a6176612e6c616e672e53686f7274684d37133460da5202000153000576616c"
        "7565787200106a6176612e6c616e672e4e756d62657286ac951d0b94e08b02000078700007",
    ("byte", "7"):
        "aced00057372000e6a6176612e6c616e672e427974659c4e6084ee50f51c02000142000576616c75"
        "65787200106a6176612e6c616e672e4e756d62657286ac951d0b94e08b020000787007",
    ("char", "A"):
        "aced0005737200136a6176612e6c616e672e436861726163746572348b47d96b1a26780200014300"
        "0576616c756578700041",
    ("int[]", "1,2"):
        "aced0005757200025b494dba602676eab2a50200007870000000020000000100000002",
    ("java.lang.String[]", "ab,cd"):
        "aced0005757200135b4c6a6176612e6c616e672e537472696e673badd256e7e91d7b470200007870"
        "0000000274000261627400026364",
}

#: `SerializerHelper.serialize(value, JDKSerializer)` 的 mark 段（固定前缀）
MARK_HEX = "aced00057400034a444b"


def test_class_object_encoding_matches_jdk():
    """paramTypes 里的 Class[] 元素 —— 与 JDK 的 `writeObject(X.class)` 一致。"""
    for name, expected in CLASS_OBJECTS.items():
        w = jser.JavaWriter()
        w.raw(jser.STREAM_MAGIC + jser.STREAM_VERSION)
        w.cls(name, jser.PARAM_TYPE_DESC[name])
        assert bytes(w.buf).hex() == expected, f"{name} 的 Class 对象编码不一致"


def test_value_encoding_matches_jdk():
    for (type_name, raw), expected in VALUES.items():
        value = raw.split(",") if type_name.endswith("[]") and type_name != "byte[]" else raw
        got = jser.encode_param(type_name, value).hex()
        assert got == MARK_HEX + expected, f"{type_name}={raw} 编码不一致"


def test_encode_param_null_and_errors():
    assert jser.encode_param("java.lang.String", None).hex() == MARK_HEX + "aced000570"
    with pytest.raises(ValueError):
        jser.encode_param("int", None)
    with pytest.raises(ValueError):
        jser.encode_param("com.fr.report.LockItem", "x")


def test_parse_arg_bytearray_from_file(tmp_path):
    p = tmp_path / "b.bin"
    p.write_bytes(b"\x01\x02")
    assert R.parse_arg(str(p), "byte[]") == b"\x01\x02"
    assert R.parse_arg("@" + str(p), "byte[]") == b"\x01\x02"
    with pytest.raises(ApiError):
        R.parse_arg(str(tmp_path / "missing.bin"), "byte[]")
    assert R.parse_arg("reportlets/a.cpt", "java.lang.String") == "reportlets/a.cpt"
    assert R.parse_arg("null", "java.lang.String") is None
    # TYPE=VALUE 显式写法
    assert R.parse_arg("java.lang.String=42", "java.lang.String") == "42"


# ---------------------------------------------------------------------------
# 6. 解码：句柄表 / 父类 classdata / writeObject 附加数据
# ---------------------------------------------------------------------------
#: JDK `ObjectOutputStream.writeObject(new String[]{"ab","ab"})`：第二个元素是
#: TC_REFERENCE(handle 2)。若 mark 段与 value 段共用句柄表，就会错位解成 "JDK"。
DUP_STR = ("aced0005757200135b4c6a6176612e6c616e672e537472696e673badd256e7e91d7b47"
           "020000787000000002740002616271007e0002")

#: JDK `writeObject(new java.io.FileNotFoundException("x"))`：4 层父类链 + 自引用 cause
THROWABLE = (
    "aced00057372001d6a6176612e696f2e46696c654e6f74466f756e64457863657074696f6ef38a2bd6"
    "e0216ae4020000787200136a6176612e696f2e494f457863657074696f6e6c8073646525f0ab020000"
    "787200136a6176612e6c616e672e457863657074696f6ed0fd1f3e1a3b1cc4020000787200136a6176"
    "612e6c616e672e5468726f7761626c65d5c635273977b8cb0300044c000563617573657400154c6a61"
    "76612f6c616e672f5468726f7761626c653b4c000d64657461696c4d6573736167657400124c6a6176"
    "612f6c616e672f537472696e673b5b000a737461636b547261636574001e5b4c6a6176612f6c616e67"
    "2f537461636b5472616365456c656d656e743b4c001473757070726573736564457863657074696f6e"
    "737400104c6a6176612f7574696c2f4c6973743b787071007e0008740001787572001e5b4c6a617661"
    "2e6c616e672e537461636b5472616365456c656d656e743b02462a3c3cfd2239020000787000000001"
    "7372001b6a6176612e6c616e672e537461636b5472616365456c656d656e746109c59a2636dd850200"
    "08420006666f726d617449000a6c696e654e756d6265724c000f636c6173734c6f616465724e616d65"
    "71007e00054c000e6465636c6172696e67436c61737371007e00054c000866696c654e616d6571007e"
    "00054c000a6d6574686f644e616d6571007e00054c000a6d6f64756c654e616d6571007e00054c000d"
    "6d6f64756c6556657273696f6e71007e00057870010000001e74000361707074000356656374000856"
    "65632e6a6176617400046d61696e70707372001f6a6176612e7574696c2e436f6c6c656374696f6e73"
    "24456d7074794c6973747ab817b43ca79ede020000787078")

#: JDK `writeObject(new ArrayList<>(Arrays.asList("ab","cd")))`：writeObject 附加数据
ARRAYLIST = ("aced0005737200136a6176612e7574696c2e41727261794c6973747881d21d99c7619d03"
             "000149000473697a657870000000027704000000027400026162740002636478")

HASHMAP = ("aced0005737200116a6176612e7574696c2e486173684d61700507dac1c31660d1030002"
           "46000a6c6f6164466163746f724900097468726573686f6c6478703f400000000000017708"
           "00000002000000017400016b7400017678")

#: JDK `writeObject(new HashSet<>(Arrays.asList("x")))`
#: HashSet.writeObject 把内部 map **摊平**写（容量/负载/大小 + 元素），不是嵌套 HashMap
HASHSET = ("aced0005737200116a6176612e7574696c2e48617368536574ba44859596b8b7340300007870"
           "770c000000103f400000000000017400017878")

#: JDK `writeObject(new java.util.Date(1700000000000L))`：毫秒在 writeObject 的块数据里
DATE = ("aced00057372000e6a6176612e7574696c2e44617465686a81014b597419030000787077080000"
        "018bcfe5680078")

#: JDK `writeObject(new java.sql.Timestamp(1700000000000L))`：毫秒在父类 Date 那一层
TIMESTAMP = ("aced0005737200126a6176612e73716c2e54696d657374616d702618d5c80153bf6502000149"
             "00056e616e6f737872000e6a6176612e7574696c2e44617465686a81014b597419030000787077"
             "080000018bcfe568007800000000")


def test_read_marked_value_resets_handle_table():
    """mark 段与 value 段是两条独立流，句柄表必须重置（否则引用错位一格）。"""
    mark, value = jser.read_marked_value(bytes.fromhex(MARK_HEX + DUP_STR))
    assert mark == "JDK"
    assert list(value) == ["ab", "ab"]
    # 直接读原始 value 流，结果应一致（说明参照系本身没写错）
    assert list(jser.JavaReader(bytes.fromhex(DUP_STR)).read()) == ["ab", "ab"]


def test_roundtrip_with_marked_value():
    for type_name, raw in (("java.lang.String", "hi"),
                           ("int", "42"),
                           ("java.lang.String[]", ["ab", "cd"]),
                           ("byte[]", b"\x00\xff")):
        mark, value = jser.read_marked_value(jser.encode_param(type_name, raw))
        assert mark == "JDK"
        got = R.simplify(value)
        if type_name == "byte[]":
            assert got == {"__bytes__": 2}
        elif type_name == "int":
            assert got == 42
        else:
            assert got == raw


def test_reads_superclass_classdata_and_self_referential_cause():
    """Throwable 的 4 个字段都在父类里；cause 未初始化时指向自己。"""
    exc = jser.JavaReader(bytes.fromhex(THROWABLE)).read()
    assert exc.class_name == "java.io.FileNotFoundException"
    assert exc.fields["detailMessage"] == "x"
    assert exc.fields["cause"] is exc                       # 自引用，不能无限递归
    assert len(exc.fields["stackTrace"]) == 1
    assert exc.fields["stackTrace"][0].fields["methodName"] == "main"
    text = R._exception_text(exc)
    assert text.startswith("java.io.FileNotFoundException: x")
    assert "cause" not in text.split(": ", 1)[1]            # 自引用不再展开


def test_reads_writeobject_custom_data():
    arr = jser.JavaReader(bytes.fromhex(ARRAYLIST)).read()
    assert arr.class_name == "java.util.ArrayList"
    assert arr.fields["size"] == 2
    assert arr.custom == ["ab", "cd"]
    assert R.simplify(arr) == ["ab", "cd"]

    hm = jser.JavaReader(bytes.fromhex(HASHMAP)).read()
    assert hm.class_name == "java.util.HashMap"
    assert hm.custom == {"k": "v"}
    assert R.simplify(hm) == {"k": "v"}


def test_simplify_boxed_and_arrays():
    _, v = jser.read_marked_value(jser.encode_param("int", "42"))
    assert R.simplify(v) == 42
    _, v = jser.read_marked_value(jser.encode_param("boolean", "true"))
    assert R.simplify(v) is True


def test_hashset_is_decoded_flattened():
    """回归：HashSet 的 writeObject 把 map 摊平写，按「嵌套 HashMap」解会读成空集 ——
    `checkFont` 因此会把「缺字体」误报成「没问题」（实测 legacy_rpt.cpt 缺 SimSun）。"""
    s = jser.JavaReader(bytes.fromhex(HASHSET)).read()
    assert s.class_name == "java.util.HashSet"
    assert s.custom == ["x"]
    assert R.simplify(s) == ["x"]


def test_date_millis_live_in_superclass_custom_data():
    """回归：毫秒在 java.util.Date 那一层，只看叶子类取不到（VcsOperator 的提交时间）。"""
    from frcli.reportops import _timestamp
    d = jser.JavaReader(bytes.fromhex(DATE)).read()
    assert [c for c, _i, _r in d.custom_chain] == ["java.util.Date"]
    assert _timestamp(d) == "2023-11-15 06:13:20"
    ts = jser.JavaReader(bytes.fromhex(TIMESTAMP)).read()
    # Timestamp 自身没有 writeObject（nanos 是普通字段），块数据只在父类 Date 那一层
    assert [c for c, _i, _r in ts.custom_chain] == ["java.util.Date"]
    assert ts.fields["nanos"] == 0
    assert _timestamp(ts) == "2023-11-15 06:13:20"


def test_simplify_guards_cycles():
    a = jser.JObject("com.fr.X")
    a.fields["self"] = a
    assert R.simplify(a) == {"__class__": "com.fr.X", "self": "<循环引用>"}


# ---------------------------------------------------------------------------
# 7. 生成的清单本体
# ---------------------------------------------------------------------------
EXPECTED_SERVICES = {
    "com.fr.workspace.resource.WorkResource",
    "com.fr.workspace.server.vcs.VcsOperator",
    "com.fr.workspace.server.check.TemplateChecker",
    "com.fr.workspace.server.exporter.TemplateExportOperator",
    "com.fr.workspace.server.lock.TplOperator",
}


def test_generated_catalog_shape():
    assert len(SERVICES) == 28
    assert EXPECTED_SERVICES <= set(SERVICES)
    total = sum(len(s.methods) for s in SERVICES.values())
    assert total >= 140, f"方法总数偏少（{total}），清单可能没生成完整"
    for cls, svc in SERVICES.items():
        assert svc.jar, f"{cls} 没有 jar 归属"
        for m in svc.methods:
            assert m.name and m.returns
            assert isinstance(m.params, tuple)


def test_generated_catalog_matches_javap_when_available():
    """设了 $FINEREPORT_HOME 且指向 FineReport 安装包时，抽样用 javap 现算结果对齐。"""
    home = Path(SERVICES_SOURCE_HOME)
    if not home.is_dir() or not C.discover_jars(home):
        pytest.skip("未设 $FINEREPORT_HOME（或该目录里没有 FineReport 安装包）")
    jars = C.discover_jars(home)
    for cls in sorted(EXPECTED_SERVICES):
        jar = C.locate_class(cls, jars)
        if jar is None:
            pytest.skip(f"{cls} 不在安装包内的 jar 里")
        live = C.parse_javap(C.javap_signatures(cls, os.pathsep.join(str(j) for j in jars)))
        want = [(m.name, m.returns, tuple(m.params)) for m in SERVICES[cls].methods]
        got = [(m["name"], m["returns"], tuple(m["params"])) for m in live["methods"]]
        assert got == want, f"{cls} 生成清单与 javap 不一致"


# ---------------------------------------------------------------------------
# 8. 路径口径提示 / 字节结果
# ---------------------------------------------------------------------------
def test_path_hint_for_workspace_service():
    hint = R.path_hint("com.fr.workspace.resource.WorkResource",
                       [("java.lang.String", "demo_group/demo_user/skill测试")])
    assert "reportlets/" in hint and "工作区路径" in hint
    # 正确前缀 / 接口自带前缀都不提醒
    assert R.path_hint("com.fr.workspace.resource.WorkResource",
                       [("java.lang.String", "reportlets/a/b.cpt")]) == ""
    assert R.path_hint("com.fr.workspace.resource.WorkResource",
                       [("java.lang.String", "assets/vcs")]) == ""
    assert R.path_hint("com.fr.workspace.resource.WorkResource",
                       [("java.lang.String", "")]) == ""


def test_path_hint_for_display_service():
    hint = R.path_hint("com.fr.workspace.server.vcs.VcsOperator",
                       [("java.lang.String", "reportlets/a/b.cpt")])
    assert "展示路径" in hint
    assert R.path_hint("com.fr.workspace.server.vcs.VcsOperator",
                       [("java.lang.String", "a/b.cpt")]) == ""
    # 无关服务不提路径口径
    assert R.path_hint("com.fr.base.operator.common.CommonOperator",
                       [("java.lang.String", "随便什么")]) == ""


def test_raw_bytes_and_describe(tmp_path):
    assert R.raw_bytes(jser.JArray("[B", [1, 2, 255])) == b"\x01\x02\xff"
    assert R.raw_bytes("字符串") is None
    p = tmp_path / "o.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 10)
    info = R.describe_bytes(p.read_bytes(), str(p))
    assert info["format"] == "png" and info["size"] == 18 and len(info["sha256"]) == 64
    assert R.describe_bytes(b"no-magic-here", "x")["format"] is None
