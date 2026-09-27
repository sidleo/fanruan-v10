"""最小 Java 对象序列化（协议 v2）编解码器。

只实现 FineReport 远程设计 RPC 通道所需的最小子集：

  request  = gzip( ObjectOutputStream(InvocationPack) + ObjectOutputStream(HashMap) )
  response = gzip( ObjectOutputStream(Marker{byte[] objectBytes, Throwable exception}) )

与帆软自带的 com.fr.rpc.serialization.SafeInvocationSerializer /
ResultSerializer 逐字节比对通过（见 tests/test_jser.py）。
"""

import struct

# --- stream constants -------------------------------------------------------
STREAM_MAGIC = b"\xac\xed"
STREAM_VERSION = b"\x00\x05"
BASE_HANDLE = 0x7E0000

TC_NULL = 0x70
TC_REFERENCE = 0x71
TC_CLASSDESC = 0x72
TC_OBJECT = 0x73
TC_STRING = 0x74
TC_ARRAY = 0x75
TC_CLASS = 0x76
TC_BLOCKDATA = 0x77
TC_ENDBLOCKDATA = 0x78
TC_RESET = 0x79
TC_BLOCKDATALONG = 0x7A
TC_EXCEPTION = 0x7B
TC_LONGSTRING = 0x7C
TC_PROXYCLASSDESC = 0x7D
TC_ENUM = 0x7E

SC_WRITE_METHOD = 0x01
SC_SERIALIZABLE = 0x02
SC_EXTERNALIZABLE = 0x04
SC_BLOCK_DATA = 0x08
SC_ENUM = 0x10


# ===========================================================================
# writer
# ===========================================================================
def _mutf8(s: str) -> bytes:
    out = bytearray()
    for ch in s:
        c = ord(ch)
        if c == 0:
            out += b"\xc0\x80"
        elif c < 0x80:
            out.append(c)
        elif c < 0x800:
            out.append(0xC0 | (c >> 6))
            out.append(0x80 | (c & 0x3F))
        elif c < 0x10000:
            out.append(0xE0 | (c >> 12))
            out.append(0x80 | ((c >> 6) & 0x3F))
            out.append(0x80 | (c & 0x3F))
        else:
            # surrogate pair
            c -= 0x10000
            for unit in (0xD800 + (c >> 10), 0xDC00 + (c & 0x3FF)):
                out.append(0xE0 | (unit >> 12))
                out.append(0x80 | ((unit >> 6) & 0x3F))
                out.append(0x80 | (unit & 0x3F))
    return bytes(out)


class Field:
    __slots__ = ("type_code", "name", "type_string")

    def __init__(self, type_code, name, type_string=None):
        self.type_code = type_code  # 'L' / '[' / 'I' / 'F' ...
        self.name = name
        self.type_string = type_string


class ClassDesc:
    def __init__(self, name, suid, flags, fields, super_desc=None):
        self.name = name
        self.suid = suid
        self.flags = flags
        self.fields = fields
        self.super_desc = super_desc


class JavaWriter:
    """Emits a Java serialization stream with correct handle bookkeeping."""

    def __init__(self):
        self.buf = bytearray()
        self.handles = {}          # identity key -> handle
        self.next_handle = BASE_HANDLE
        self._uid = 0

    # -- low level ----------------------------------------------------------
    def u1(self, v):
        self.buf.append(v & 0xFF)

    def u2(self, v):
        self.buf += struct.pack(">H", v)

    def i4(self, v):
        self.buf += struct.pack(">i", v)

    def raw(self, b):
        self.buf += b

    def utf(self, s: str):
        b = _mutf8(s)
        self.u2(len(b))
        self.buf += b

    def unique_key(self, tag):
        self._uid += 1
        return (tag, self._uid)

    # -- handles ------------------------------------------------------------
    def assign(self, key):
        h = self.next_handle
        self.next_handle += 1
        if key is not None:
            self.handles[key] = h
        return h

    def ref(self, key):
        return self.handles.get(key)

    # -- object writers -----------------------------------------------------
    def string(self, s: str, key=None):
        key = key if key is not None else ("str", s)
        h = self.ref(key)
        if h is not None:
            self.u1(TC_REFERENCE)
            self.i4(h)
            return
        self.assign(key)
        self.u1(TC_STRING)
        self.utf(s)

    def null(self):
        self.u1(TC_NULL)

    def class_desc(self, desc: ClassDesc, key=None):
        key = key if key is not None else ("desc", desc.name)
        h = self.ref(key)
        if h is not None:
            self.u1(TC_REFERENCE)
            self.i4(h)
            return
        self.u1(TC_CLASSDESC)
        self.assign(key)
        self.utf(desc.name)
        self.raw(struct.pack(">q", desc.suid))
        self.u1(desc.flags)
        self.u2(len(desc.fields))
        for f in desc.fields:
            self.u1(ord(f.type_code))
            self.utf(f.name)
            if f.type_string is not None:
                self.string(f.type_string)
        self.u1(TC_ENDBLOCKDATA)
        # 超类描述符；null => java.lang.Object（不可序列化，链到此为止）
        if desc.super_desc is None:
            self.null()
        else:
            self.class_desc(desc.super_desc)

    def cls(self, name, desc: ClassDesc):
        """TC_CLASS reference to a Class object."""
        key = ("class", name)
        h = self.ref(key)
        if h is not None:
            self.u1(TC_REFERENCE)
            self.i4(h)
            return
        self.u1(TC_CLASS)
        self.class_desc(desc)
        self.assign(key)

    def object(self, desc: ClassDesc, write_fields, key=None):
        key = key if key is not None else self.unique_key("obj")
        h = self.ref(key)
        if h is not None:
            self.u1(TC_REFERENCE)
            self.i4(h)
            return
        self.u1(TC_OBJECT)
        self.class_desc(desc)
        self.assign(key)
        write_fields()

    def array(self, desc: ClassDesc, elements, key=None):
        """elements: list of callables, or (kind, values) for primitives."""
        key = key if key is not None else self.unique_key("arr")
        self.u1(TC_ARRAY)
        self.class_desc(desc)
        self.assign(key)
        self.i4(len(elements))
        for w in elements:
            w()

    def primitive_array(self, desc: ClassDesc, payload: bytes, count: int, key=None):
        key = key if key is not None else self.unique_key("arr")
        self.u1(TC_ARRAY)
        self.class_desc(desc)
        self.assign(key)
        self.i4(count)
        self.raw(payload)

    def blockdata(self, payload: bytes):
        if len(payload) <= 0xFF:
            self.u1(TC_BLOCKDATA)
            self.u1(len(payload))
        else:
            self.u1(TC_BLOCKDATALONG)
            self.i4(len(payload))
        self.raw(payload)


# --- well known descriptors (SUIDs taken from the live stream) -------------
DESC_STRING = ClassDesc("java.lang.String", -6849794470754667710, SC_SERIALIZABLE, [])
DESC_CLASS_ARR = ClassDesc("[Ljava.lang.Class;", -6118465897992725863, SC_SERIALIZABLE, [])
DESC_BYTE_ARR = ClassDesc("[B", -5984413125824719648, SC_SERIALIZABLE, [])
DESC_BYTE_ARR_ARR = ClassDesc("[[B", 5475560301672258359, SC_SERIALIZABLE, [])

DESC_INVOCATION_PACK = ClassDesc(
    "com.fr.rpc.serialization.InvocationSerializer$InvocationPack",
    -7570816405484554698, SC_SERIALIZABLE,
    [Field("L", "declareClassName", "Ljava/lang/String;"),
     Field("L", "methodName", "Ljava/lang/String;"),
     Field("[", "paramTypes", "[Ljava/lang/Class;"),
     Field("[", "params", "[[B")])

DESC_HASHMAP = ClassDesc(
    "java.util.HashMap", 362498820763181265, SC_SERIALIZABLE | SC_WRITE_METHOD,
    [Field("F", "loadFactor"), Field("I", "threshold")])

DESC_MARKER = ClassDesc(
    "com.fr.rpc.serialization.ResultSerializer$Marker",
    -7570816405484554698, SC_SERIALIZABLE,
    [Field("[", "objectBytes", "[B"),
     Field("L", "exception", "Ljava/lang/Throwable;")])


def java_string_hash(s: str) -> int:
    h = 0
    for ch in s:
        h = (31 * h + ord(ch)) & 0xFFFFFFFF
    return h


def hashmap_order(keys):
    """Iteration order of a java.util.HashMap with capacity 16, no resize."""
    def idx(k):
        h = java_string_hash(k)
        h ^= h >> 16
        return h & 15
    return sorted(enumerate(keys), key=lambda p: (idx(p[1]), p[0]))


# ===========================================================================
# reader
# ===========================================================================
class JObject:
    def __init__(self, class_name):
        self.class_name = class_name
        self.fields = {}
        self.custom = None      # parsed custom data (dict) when understood
        self.raw_custom = None
        self.custom_chain = []   # [(类名, 解析结果, 原始块数据)]，父类→子类
        #   —— Date 的毫秒在 java.util.Date 那一层，只看叶子类取不到

    def __repr__(self):
        # 异常对象的 cause 常指向自己（Throwable 自引用），直接打印会无限递归
        return _safe_repr(self, 0)


def _safe_repr(obj, depth, _seen=None):
    seen = _seen if _seen is not None else set()
    if depth > 6 or id(obj) in seen:
        return "..."
    seen = seen | {id(obj)}
    if isinstance(obj, JObject):
        parts = ", ".join(f"{k}={_safe_repr(v, depth + 1, seen)}"
                          for k, v in obj.fields.items() if k != "cause" or depth < 2)
        if obj.custom is not None:
            parts += (", " if parts else "") + f"custom={_safe_repr(obj.custom, depth + 1, seen)}"
        return f"<{obj.class_name} {{{parts}}}>"
    if isinstance(obj, (JArray, list)):
        return "[" + ", ".join(_safe_repr(x, depth + 1, seen) for x in list(obj)[:8]) + "]"
    return repr(obj)


class JArray(list):
    def __init__(self, class_name, items):
        super().__init__(items)
        self.class_name = class_name


class JClass:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"<JClass {self.name}>"


class JavaReader:
    def __init__(self, data: bytes):
        self.d = data
        self.p = 0
        self.handles = []

    def u1(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def u2(self):
        v = struct.unpack_from(">H", self.d, self.p)[0]
        self.p += 2
        return v

    def i4(self):
        v = struct.unpack_from(">i", self.d, self.p)[0]
        self.p += 4
        return v

    def i8(self):
        v = struct.unpack_from(">q", self.d, self.p)[0]
        self.p += 8
        return v

    def raw(self, n):
        b = self.d[self.p:self.p + n]
        self.p += n
        return b

    def utf(self):
        n = self.u2()
        b = self.raw(n)
        return b.decode("utf-8", "replace")

    def handle(self, obj):
        self.handles.append(obj)
        return obj

    def read(self, expect_header=True):
        if expect_header:
            magic = self.raw(2)
            if magic != STREAM_MAGIC:
                raise ValueError(f"bad stream magic {magic!r}")
            self.raw(2)
        return self.read_object()

    def read_object(self):
        tc = self.u1()
        if tc == TC_NULL:
            return None
        if tc == TC_REFERENCE:
            return self.handles[self.i4() - BASE_HANDLE]
        if tc == TC_STRING:
            return self.handle(self.utf())
        if tc == TC_LONGSTRING:
            n = self.i8()
            return self.handle(self.raw(n).decode("utf-8", "replace"))
        if tc == TC_CLASSDESC:
            return self.read_classdesc()
        if tc == TC_OBJECT:
            return self.read_ordinary()
        if tc == TC_ARRAY:
            return self.read_array()
        if tc == TC_CLASS:
            desc = self.read_classdesc()
            return self.handle(JClass(desc.name if desc else None))
        if tc == TC_ENDBLOCKDATA:
            return _ENDBLOCK
        if tc == TC_BLOCKDATA:
            return self.raw(self.u1())
        if tc == TC_BLOCKDATALONG:
            return self.raw(self.i4())
        if tc == TC_EXCEPTION:
            self.read_object()
            raise JavaException(self.read_object())
        if tc == TC_RESET:
            self.handles = []
            return self.read_object()
        if tc == TC_ENUM:
            desc = self.read_classdesc()
            obj = self.handle(JObject(desc.name))
            obj.fields["__enum__"] = self.read_object()
            return obj
        if tc == TC_PROXYCLASSDESC:
            raise NotImplementedError("proxy classdesc")
        raise ValueError(f"unsupported type code 0x{tc:02x} at {self.p - 1}")

    def read_classdesc(self):
        tc = self.u1()
        if tc == TC_NULL:
            return None
        if tc == TC_REFERENCE:
            return self.handles[self.i4() - BASE_HANDLE]
        if tc != TC_CLASSDESC:
            raise ValueError(f"expected classdesc, got 0x{tc:02x}")
        name = self.utf()
        suid = self.i8()
        flags = self.u1()
        nfields = self.u2()
        desc = ClassDesc(name, suid, flags, [])
        self.handle(desc)
        for _ in range(nfields):
            code = chr(self.u1())
            fname = self.utf()
            tstr = None
            if code in "L[":
                tstr = self.read_object()
            desc.fields.append(Field(code, fname, tstr))
        while True:
            b = self.read_object()
            if b is _ENDBLOCK:
                break
        desc.super_desc = self.read_classdesc()
        return desc

    def read_ordinary(self):
        desc = self.read_classdesc()
        obj = self.handle(JObject(desc.name))
        # classdata 按「父类 → 子类」顺序写；每个类内部先基本类型、再对象字段。
        # 不读父类字段会导致句柄表错位（Throwable 的 4 个字段就在父类里）。
        for d in _class_chain(desc):
            for f in d.fields:
                if f.type_code not in "L[":
                    obj.fields[f.name] = self.read_primitive(f.type_code)
            for f in d.fields:
                if f.type_code in "L[":
                    obj.fields[f.name] = self.read_object()
            if d.flags & SC_WRITE_METHOD:
                custom, raw = self.read_custom(d)
                obj.custom_chain.append((d.name, custom, raw))
                if d is desc:
                    obj.custom, obj.raw_custom = custom, raw
        return obj

    def read_primitive(self, code):
        if code == "Z":
            return self.u1() != 0
        if code == "B":
            v = self.u1()
            return v - 256 if v > 127 else v
        if code == "C":
            return chr(self.u2())
        if code == "S":
            v = self.u2()
            return v - 65536 if v > 32767 else v
        if code == "I":
            return self.i4()
        if code == "J":
            return self.i8()
        if code == "F":
            return struct.unpack(">f", self.raw(4))[0]
        if code == "D":
            return struct.unpack(">d", self.raw(8))[0]
        raise ValueError(f"bad primitive {code}")

    def read_custom(self, desc):
        """Read SC_WRITE_METHOD block data; understand HashMap when possible.

        writeObject 的附加数据只可能是两类内容：基本类型（一律走
        BlockDataOutputStream → TC_BLOCKDATA）与对象（TC_* 标记）。以
        TC_ENDBLOCKDATA 收尾，所以可以通用地读到块结束 —— 碰到不认识的
        字节才停手（宁可少读也不要错位）。
        """
        if desc.name == "java.util.HashMap":
            chunks = bytearray()
            first = self.u1()
            if first not in (TC_BLOCKDATA, TC_BLOCKDATALONG):
                raise ValueError("expected blockdata in HashMap")
            if first == TC_BLOCKDATA:
                chunks += self.raw(self.u1())
            else:
                chunks += self.raw(self.i4())
            _cap, size = struct.unpack(">ii", bytes(chunks)[:8])
            # 键值对是流里的对象，跟在块数据后面
            items = {}
            for _ in range(size):
                k = self.read_object()
                v = self.read_object()
                items[k] = v
            end = self.read_object()
            assert end is _ENDBLOCK, "HashMap custom data not terminated"
            return items, bytes(chunks)
        items = []
        raw = bytearray()
        while self.p < len(self.d):
            tc = self.d[self.p]
            if tc == TC_ENDBLOCKDATA:
                self.p += 1
                break
            if tc == TC_BLOCKDATA:
                self.p += 1
                raw += self.raw(self.u1())
                continue
            if tc == TC_BLOCKDATALONG:
                self.p += 1
                raw += self.raw(self.i4())
                continue
            if tc in _OBJECT_TOKENS:
                items.append(self.read_object())
                continue
            break
        return (items or None), bytes(raw)

    def read_array(self):
        desc = self.read_classdesc()
        name = desc.name if desc else "?"
        comp = name[1:]
        if comp in "ZBCSIJFD":
            n = self.i4()
            vals = [self.read_primitive(comp) for _ in range(n)]
            return self.handle(JArray(name, vals))
        n = self.i4()
        arr = JArray(name, [])
        self.handle(arr)
        for _ in range(n):
            arr.append(self.read_object())
        return arr


class _EndBlock:
    pass


_ENDBLOCK = _EndBlock()

#: 可以出现在 writeObject 附加数据里的对象标记
_OBJECT_TOKENS = frozenset({TC_NULL, TC_REFERENCE, TC_STRING, TC_LONGSTRING,
                            TC_OBJECT, TC_ARRAY, TC_CLASS, TC_CLASSDESC, TC_ENUM})


def _class_chain(desc):
    """描述符链：最父类 → 最子类（= classdata 的写入顺序）。"""
    chain = []
    d = desc
    while d is not None:
        chain.append(d)
        d = getattr(d, "super_desc", None)
    chain.reverse()
    return chain


class JavaException(Exception):
    def __init__(self, obj):
        self.obj = obj
        super().__init__(str(obj))


def read_java_stream(data: bytes):
    return JavaReader(data)


def read_marked_value(data: bytes):
    """读 `mark + value` 两段流（SerializerHelper.serialize 的产物）。

    两段是**各自的 ObjectOutputStream**，句柄编号互不相干、都从 0x7E0000 开始：
    `mark` 里那句 "JDK" 占掉 0 号句柄，若沿用同一张句柄表，value 流里所有
    TC_REFERENCE 都会错位一格（踩过：`WeiXinRPCOperator.getAgents` 把 ArrayList
    的 classdesc 引用解析成字符串 "JDK"）。mark 为 "NullSerializer" 表示返回 void，
    此时没有第二段。
    """
    r = JavaReader(data)
    mark = r.read()
    r.handles = []
    if mark == "NullSerializer":
        return mark, None
    return mark, r.read()


# ---------------------------------------------------------------------------
# RPC 参数编码：每个参数 = JavaObjectStream(mark) + JavaObjectStream(value)
# 对应 com.fr.serialization.SerializerHelper.serialize(value, JDKSerializer)
# ---------------------------------------------------------------------------
def _header(w):
    w.raw(STREAM_MAGIC + STREAM_VERSION)


def string_param(value: str) -> bytes:
    mark, body = JavaWriter(), JavaWriter()
    _header(mark)
    mark.string("JDK")
    _header(body)
    body.string(value)
    return bytes(mark.buf) + bytes(body.buf)


def bytes_param(value: bytes) -> bytes:
    mark, body = JavaWriter(), JavaWriter()
    _header(mark)
    mark.string("JDK")
    _header(body)
    body.primitive_array(DESC_BYTE_ARR, value, len(value))
    return bytes(mark.buf) + bytes(body.buf)


PARAM_TYPE_DESC = {"java.lang.String": DESC_STRING, "byte[]": DESC_BYTE_ARR}


# ---------------------------------------------------------------------------
# 标量参数编码（`frcli rpc call --arg` 用）
#
# 规则：paramTypes 里的 Class[] 元素 —— 基本类型写 `int.class` 那样的无字段
# 描述符（suid=0, flags=0），包装类型写「无字段、无超类」的描述符（同 JDK 对
# `writeObject(SomeClass.class)` 的写法）；参数值一律是包装对象。
# 参照字节由 JDK 生成并固化在 tests/test_rpc.py。
# ---------------------------------------------------------------------------
def _suid(hex_str: str) -> int:
    v = int(hex_str, 16)
    return v - (1 << 64) if v >= (1 << 63) else v


PRIMITIVE_NAMES = ("boolean", "byte", "char", "short", "int", "long", "float", "double")

#: 基本类型 Class 对象：suid=0、flags=0、无字段
DESC_PRIMITIVE_CLASS = {n: ClassDesc(n, 0, 0, []) for n in PRIMITIVE_NAMES}

#: 包装类（数字型才有超类 Number；Boolean/Character 直接继承 Object）
DESC_NUMBER = ClassDesc("java.lang.Number", _suid("86ac951d0b94e08b"), SC_SERIALIZABLE, [])
#: 包装类 → (类名, suid, 字段类型码, 是否继承 Number)
_BOXED = {
    "boolean": ("java.lang.Boolean", "cd207280d59cfaee", "Z", False),
    "byte": ("java.lang.Byte", "9c4e6084ee50f51c", "B", True),
    "char": ("java.lang.Character", "348b47d96b1a2678", "C", False),
    "short": ("java.lang.Short", "684d37133460da52", "S", True),
    "int": ("java.lang.Integer", "12e2a0a4f7818738", "I", True),
    "long": ("java.lang.Long", "3b8be490cc8f23df", "J", True),
    "float": ("java.lang.Float", "daedc9a2db3cf0ec", "F", True),
    "double": ("java.lang.Double", "80b3c24a296bfb04", "D", True),
}
DESC_BOXED = {p: ClassDesc(cls, _suid(suid), SC_SERIALIZABLE, [Field(code, "value")],
                           super_desc=DESC_NUMBER if numeric else None)
              for p, (cls, suid, code, numeric) in _BOXED.items()}
#: 包装类的 Class 对象：classdesc 与「值」完全相同（字段 + 超类都在）
DESC_BOXED_CLASS = DESC_BOXED

DESC_INT_ARR = ClassDesc("[I", _suid("4dba602676eab2a5"), SC_SERIALIZABLE, [])
DESC_STRING_ARR = ClassDesc("[Ljava.lang.String;", _suid("add256e7e91d7b47"),
                            SC_SERIALIZABLE, [])
DESC_LONG_ARR = ClassDesc("[J", 0, SC_SERIALIZABLE, [])
DESC_DOUBLE_ARR = ClassDesc("[D", 0, SC_SERIALIZABLE, [])
DESC_BOOLEAN_ARR = ClassDesc("[Z", 0, SC_SERIALIZABLE, [])

#: 声明类型 → 该类型「值」的 Class 对象描述符
_SCALAR_CLASS = {}
for _p in PRIMITIVE_NAMES:
    _SCALAR_CLASS[_p] = DESC_PRIMITIVE_CLASS[_p]
    _SCALAR_CLASS[_BOXED[_p][0]] = DESC_BOXED_CLASS[_p]
_SCALAR_CLASS.update({
    "java.lang.String": DESC_STRING,
    "byte[]": DESC_BYTE_ARR,
    "int[]": DESC_INT_ARR,
    "long[]": DESC_LONG_ARR,
    "double[]": DESC_DOUBLE_ARR,
    "boolean[]": DESC_BOOLEAN_ARR,
    "java.lang.String[]": DESC_STRING_ARR,
})

#: 是否可为 null（非基本类型）
NULLABLE_TYPES = tuple(t for t in _SCALAR_CLASS if t not in PRIMITIVE_NAMES)

PARAM_TYPE_DESC.update(_SCALAR_CLASS)


def _int_of(value, bits, signed=True):
    v = int(value, 0) if isinstance(value, str) else int(value)
    lo, hi = (-(1 << (bits - 1)), (1 << (bits - 1)) - 1) if signed else (0, (1 << bits) - 1)
    if not lo <= v <= hi:
        raise ValueError(f"值 {v} 超出 {bits} 位有符号整数范围")
    return v


_SCALAR_WRITERS = {
    "boolean": lambda w, v: w.u1(1 if v else 0),
    "byte": lambda w, v: w.u1(int(v) & 0xFF),
    "char": lambda w, v: w.u2(ord(v) if isinstance(v, str) else int(v)),
    "short": lambda w, v: w.u2(int(v) & 0xFFFF),
    "int": lambda w, v: w.i4(v),
    "long": lambda w, v: w.raw(struct.pack(">q", v)),
    "float": lambda w, v: w.raw(struct.pack(">f", v)),
    "double": lambda w, v: w.raw(struct.pack(">d", v)),
}

_SCALAR_COERCERS = {
    "boolean": lambda v: v if isinstance(v, bool) else str(v).strip().lower() in
    ("1", "true", "yes", "y", "on"),
    "byte": lambda v: _int_of(v, 8),
    "short": lambda v: _int_of(v, 16),
    "int": lambda v: _int_of(v, 32),
    "long": lambda v: _int_of(v, 64),
    "float": float,
    "double": float,
    "char": lambda v: v if len(v) == 1 else (_ for _ in ()).throw(
        ValueError("char 需要一个字符")),
}

#: 声明类型 → 基本类型（用于选 writer）
_PRIM_OF = {p: p for p in PRIMITIVE_NAMES}
_PRIM_OF.update({cls: p for p, (cls, _s, _c, _n) in _BOXED.items()})


def normalize_param_type(type_name: str) -> str:
    """把 javap 里可能出现的写法归一（`java.lang.String...` / 泛型擦除等）。"""
    t = (type_name or "").strip()
    if t.endswith("..."):
        t = t[:-3] + "[]"
    return t


def is_scalar_type(type_name: str) -> bool:
    return normalize_param_type(type_name) in _SCALAR_CLASS


def encode_param(type_name: str, value):
    """把一个参数编码成 `mark + value` 两段 Java 流（对应 JDKSerializer）。

    value：str（CLI 原样）/ bytes（byte[]）/ None / list。
    `byte[]` 与基本类型数组需要 bytes 或 list。
    """
    t = normalize_param_type(type_name)
    if t not in _SCALAR_CLASS:
        raise ValueError(f"暂不支持的参数类型: {type_name}")
    value = _coerce_param(t, value)
    mark = JavaWriter()
    mark.raw(STREAM_MAGIC + STREAM_VERSION)
    mark.string("JDK")
    body = JavaWriter()
    body.raw(STREAM_MAGIC + STREAM_VERSION)
    if value is None:
        body.null()
    elif t == "java.lang.String":
        body.string(value)
    elif t == "byte[]":
        body.primitive_array(DESC_BYTE_ARR, value, len(value))
    elif t == "int[]":
        body.primitive_array(DESC_INT_ARR, b"".join(struct.pack(">i", v) for v in value),
                             len(value))
    elif t == "long[]":
        body.primitive_array(DESC_LONG_ARR, b"".join(struct.pack(">q", v) for v in value),
                             len(value))
    elif t == "double[]":
        body.primitive_array(DESC_DOUBLE_ARR,
                             b"".join(struct.pack(">d", v) for v in value), len(value))
    elif t == "boolean[]":
        body.primitive_array(DESC_BOOLEAN_ARR, bytes(1 if v else 0 for v in value),
                             len(value))
    elif t == "java.lang.String[]":
        body.array(DESC_STRING_ARR, [(lambda s=s: body.string(s)) for s in value])
    else:
        prim = _PRIM_OF[t]
        write = _SCALAR_WRITERS[prim]
        body.object(DESC_BOXED[prim], lambda: write(body, value))
    return bytes(mark.buf) + bytes(body.buf)


def _coerce_param(t: str, value):
    if value is None:
        if t in PRIMITIVE_NAMES:
            raise ValueError(f"{t} 是基本类型，不能传 null")
        return None
    if t == "java.lang.String":
        return value if isinstance(value, str) else str(value)
    if t == "byte[]":
        return value if isinstance(value, (bytes, bytearray)) else str(value).encode()
    if t.endswith("[]") and t != "java.lang.String[]":
        prim = t[:-2]
        coerce = _SCALAR_COERCERS[prim]
        return [coerce(x) for x in value]
    if t == "java.lang.String[]":
        return [x if isinstance(x, str) else str(x) for x in value]
    prim = _PRIM_OF.get(t)
    if prim is None:
        return value
    if isinstance(value, str) and value.strip() == "null":
        raise ValueError(f"{t} 是基本类型，不能传 null")
    return _SCALAR_COERCERS[prim](value)
