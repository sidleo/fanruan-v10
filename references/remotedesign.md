# 远程设计 RPC 协议（frcli report upload/delete 的底层）

> 本文件是 `src/frcli/remotedesign.py` + `jser.py` + `rdcrypto.py` 的协议说明与复核手册。
> 面向「换个 FineReport 版本后要重新核对报文」的场景。

## 1. 为什么是这条通道

决策平台 REST 里没有任何接口接收 .cpt 字节（`TemplateBean`/`FileBean` 只有元数据字段，
`ReportEntryService.addTemplates()` 只写条目记录）。Designer 的「远程设计」把服务端
`WEB-INF` 当远程文件系统用，走自带 RPC —— 它能做 Designer 能做的一切。

## 2. 三次请求

```
POST {workspace}/decision/remote/design/check
  → {"data":{"transmissionEncryption":2,"frontSeed":"…","frontSM4Key":"…"}}

POST {workspace}/decision/remote/design/verify      (form: username, password)
  → {"data":"<JWT>"}          password 必须按上一步的模式加密（见 §4）

POST {workspace}/decision/remote/design/channel     (body: 见 §3)
  → gzip(Java 对象流)         即 ResultSerializer 序列化的 FineResult
```

辅助：`/vt`（许可是否支持远程设计）、`/version`、`/branch`、
`/service`（表单 username+password → 可调服务类清单）。

## 3. `/channel` 载荷

```
body = gzip( ObjectOutputStream.writeObject(InvocationPack)
           + ObjectOutputStream.writeObject(HashMap metadata) )
```

- `InvocationPack` = `com.fr.rpc.serialization.InvocationSerializer$InvocationPack`
  （serialVersionUID `-7570816405484554698`），字段按序：
  `declareClassName:String`、`methodName:String`、`paramTypes:Class[]`、`params:byte[][]`。
- 每个参数单独序列化一份：`ObjectOutputStream(mark="JDK")` + `ObjectOutputStream(value)`。
- metadata 固定四个键：`username`、`id`（客户端 id，任意唯一串）、`token`（JWT）、
  `encryptVersion`（值同键名，绕开服务端「旧版本状态加密」判断）。
- 服务端 `WorkspaceServerInvoker`：`Class.forName(declareClassName).getDeclaredMethod(methodName, paramTypes)`
  → 从 `FineObjectPool.getServerPool()` 取实例 `invoke`；返回 `ResultSerializer` 序列化的
  `Marker{byte[] objectBytes, Throwable exception}`，`objectBytes` 内是 `mark + 序列化返回值`。

可调用的类就是 `/service` 返回的清单。模板相关：

| 类 | 方法 |
|----|------|
| `com.fr.workspace.resource.WorkResource` | `readFully/exist/length/list/list(Filter)/write/createFile/createDirectory/delete/rename/isDirectory/lastModified/openStream` |
| `com.fr.workspace.server.lock.TplOperator` | `readAndLockFile/closeAndFreeFile/rename/saveAs/delete/userIn/userOut` |

## 4. 密码加密

| `transmissionEncryption` | 算法 | key |
|---|---|---|
| 2 = AES | `AES/ECB/PKCS5Padding` → Base64 | `frontSeed` 的 UTF-8 字节截断/补零到 16 |
| 3 = SM4 | `SM4/ECB` + ISO7816 填充（先补 0x80 再补 0x00）→ Base64 | `frontSM4Key`（32 位 hex → 16 字节） |

0=RSA、1=SM2 未实现（`rdcrypto.encrypt_password` 会明确报错）。

## 5. 服务端权限语义

`com.fr.workspace.server.ServerWorkResource` 每个写方法前面都有 `RemoteDesignHelper.access(path)`：

```java
if (path.endsWith(".tmp")) path = path[:-4];
return !path.contains("reportlets") || checkAuth(path);   // checkAuth = 该账号的远程设计授权目录
```

- 路径**含 `reportlets`** → 查账号授权目录（`RemoteDesignAuthorityDataService`）；
- **不含** → 直接放行；
- **不满足时 `write` 静默返回**（不抛异常、不写盘）→ 只能靠回读比对判断。

## 6. 复核：从实测环境 Designer 生成参照报文

新增/改接口后，用帆软自己的代码产出参照字节，与 Python 实现逐字节比对。
`<FineReport 安装目录>` 里有全部 jar（`lib/` + `webapps/webroot/WEB-INF/lib/`）。

```java
// RefDump.java —— 用帆软原件生成 /channel 载荷
import com.fr.rpc.Invocation;
import com.fr.rpc.serialization.SafeInvocationSerializer;
import com.fr.serialization.*;
import java.nio.file.*;

public class RefDump {
    public static void main(String[] a) throws Exception {
        SerializerSummary.getDefault().complete();          // 必须：装配默认序列化器
        Invocation inv = Invocation.create(Class.forName(a[0]), a[1],
                new Class[]{String.class, byte[].class},
                a[2], Files.readAllBytes(Paths.get(a[3])));
        inv.addMetaData("username", "user");
        inv.addMetaData("id", "cid");
        inv.addMetaData("token", "tok");
        inv.addMetaData("encryptVersion", "encryptVersion");
        Files.write(Paths.get("/tmp/ref.bin"), SerializerHelper.serialize(
                inv, GZipSerializerWrapper.wrap(SafeInvocationSerializer.getDefault())));
    }
}
```

```bash
CP=$(ls <FineReport 安装目录>/lib/*.jar \
        <FineReport 安装目录>/webapps/webroot/WEB-INF/lib/*.jar \
        <FineReport 安装目录>/server/lib/*.jar | tr '\n' ':')
javac -nowarn -cp "$CP" -d out RefDump.java
java -cp "out:$CP" RefDump com.fr.workspace.resource.WorkResource write \
     reportlets/a/b.cpt /tmp/hw.bin
python3 - <<'PY'
import gzip, sys; sys.path.insert(0, "src")
from frcli.remotedesign import build_call
meta = {"username": "user", "id": "cid", "token": "tok",
        "encryptVersion": "encryptVersion"}
mine = build_call("com.fr.workspace.resource.WorkResource", "write",
                  [("java.lang.String", "reportlets/a/b.cpt"), ("byte[]", b"hello world")], meta)
ref = gzip.decompress(open("/tmp/ref.bin", "rb").read())
assert gzip.decompress(mine) == ref, "报文不一致"
print("报文与帆软原件逐字节一致")
PY
```

密码加密同理：`com.fr.security.SecurityToolbox.aesEncrypt/sm4Encrypt` 打印结果，
与 `frcli.rdcrypto` 比对（`tests/test_remotedesign.py` 里固化的向量就是这么来的）。

## 7. 报文里几处易错点（改 jser.py 时注意）

- `Class[]` 字段的 `ObjectStreamField` typeCode 是 `'['`（不是 `'L'`），字段名用 **raw UTF** 写、
  类型串才是 `TC_STRING`；`byte[][]` / `byte[]` 同理。
- Java 的句柄表按写入顺序分配（classdesc → 数组 → 元素），重复对象走 `TC_REFERENCE`；
  同名 String 会被复用，`HashMap` 的 `encryptVersion` 键值就是同一个对象。
- `HashMap` 有 `writeObject`：先写 `loadFactor`/`threshold`（`SC_WRITE_METHOD`），
  再 `TC_BLOCKDATA(8)` 写 capacity/size，随后键值对，最后补 `TC_ENDBLOCKDATA`。
- 字段顺序：基本类型在前、对象在后，各自按字段名排序（`Arrays.sort(ObjectStreamField[])`）。
- 数组类描述符的 SUID 不是 0：`[B`=`acf317f8060854e0`、`[[B`=`4bfd19156767db37`、
  `[Ljava.lang.Class;`=`ab16d7aecbcd5a99`；`java.lang.String`=`a0f0a4387a3bb342`。
- `java.lang.Object` 不是 Serializable，所以 `String` 的 classdesc **没有超类描述符**（直接 `TC_NULL`）。
