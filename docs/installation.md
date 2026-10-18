# 安装与环境排错

发行名为 `chan-lun-core`，导入名为 `chan`。本页维护安装、Notebook 和
导入排错；最小用法见 [README](../README.md)，源码开发见
[CONTRIBUTING](../CONTRIBUTING.md)。


## 普通 Python 环境

使用将要运行程序的解释器安装，固定版本便于复现：

```bash
python -m pip install 'chan-lun-core==1.0.0'
python -c "import chan; print(chan.__version__); print(chan.__file__)"
```

`pip` 发行名与 `import` 名不同，不要安装名为 `chan` 的其他发行包来替代。
依赖下限为 Python 3.6、numpy 1.14、pandas 0.23。现代本地开发环境与
聚宽旧环境分开准备，兼容性验证范围见[开发与验收](../CONTRIBUTING.md#两层验收)。

## 聚宽研究 Notebook

一个安装单元格，保留换行：

```python
import sys
!{sys.executable} -m pip install --user chan-lun-core==1.0.0 --no-cache-dir
```

如果当前镜像尚未提供 `1.0.0`，可继续使用已经安装并可导入的版本。
镜像同步时间不由本库控制；版本不可获取时不要把安装失败当成算法错误。
如能访问 GitHub Release，也可安装指定 wheel：

```python
import sys
!{sys.executable} -m pip install --user https://github.com/lushi78778/chan-lun/releases/download/v1.0.0/chan_lun_core-1.0.0-py3-none-any.whl
```

离线时，先下载该 wheel 并上传到 Notebook 能读取的目录，再用当前解释器
对实际文件绝对路径执行 `-m pip install --user /绝对路径/文件.whl`。
保持已有 numpy/pandas，不为安装本库升级聚宽内置环境。

安装后若此前已导入过 `chan`，重启内核，再在新的单元格确认：

```python
import sys
import chan

print("python:", sys.version.split()[0])
print("chan version:", chan.__version__)
print("chan file:", chan.__file__)
print("has find_bis:", hasattr(chan, "find_bis"))
```

本文命令以 `1.0.0` 为固定示例。旧脚本保留各自依赖；升级影响见
[迁移指南](migration.md)，版本事实见 [CHANGELOG](../CHANGELOG.md)。

## `chan.__version__` 不存在时

先确认实际导入对象，不要给错误模块手工补版本号：

```python
import sys
import chan

print("python:", sys.version.split()[0])
print("file:", getattr(chan, "__file__", None))
print("path:", list(getattr(chan, "__path__", [])))
print("spec:", getattr(chan, "__spec__", None))
print("version:", getattr(chan, "__version__", None))
print("has find_bis:", hasattr(chan, "find_bis"))
```

| 现象 | 含义与处理 |
|---|---|
| `file=None`、`origin='namespace'`，路径为工作目录 `/home/jquser/chan` | 导入了同名目录形成的命名空间包。用当前内核解释器安装 `chan-lun-core`，重启内核后再查 |
| 文件来自工作区的 `chan.py` 或其他 `chan/__init__.py` | 有同名模块遮蔽。检查导入路径和该文件用途，消除遮蔽后重新启动 |
| 文件来自 `site-packages/chan/__init__.py`，但版本或入口不符合预期 | 检查当前解释器的安装元数据、安装版本及内核缓存 |
| `ModuleNotFoundError` | 当前解释器找不到包；用同一解释器安装，而不是其他终端中的 pip |

聚宽 Python 3.6 可额外检查安装元数据：

```python
import pkg_resources

try:
    dist = pkg_resources.get_distribution("chan-lun-core")
    print("installed:", dist.version, dist.location)
except pkg_resources.DistributionNotFound:
    print("chan-lun-core: 未安装")
```

元数据说明发行包已安装，不单独证明 `import chan` 加载了它。
本仓库提供 [`tools/diagnose_chan.py`](../tools/diagnose_chan.py)，可同时核对运行时路径、
版本、安装元数据和关键公开入口。

## 本地诊断与安装包验收

在克隆仓库中，可用目标解释器执行：

```bash
python /绝对路径/chan-lun/tools/diagnose_chan.py
```

诊断只读取环境，不注入源码、不自动安装。应同时检查解释器、实际导入文件、
安装元数据与公开入口；包已安装和导入了正确的包是两项检查。
安装包的隔离导入检查见[工程工具](../tools/README.md)。本机导入成功、旧环境
实跑和聚宽平台验收分别记录。
