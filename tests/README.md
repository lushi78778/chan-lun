# 包测试

本目录维护可在独立源码仓库和解包 sdist 中执行的包测试。测试只读取
包源码、随 sdist 分发的工程工具、文档及 `fixtures/`，不读取 `validation/`
或维护者外层项目。fixtures 的原始来源与独立标注证据归档在仓库资产层。

在核心库仓库根准备开发环境后运行：

```bash
python tools/check_core.py
python tools/check_core.py --pattern test_contracts.py
python -m unittest discover -s tests -p 'test_*.py'
```

工程入口显式选择当前源码并传给测试子进程；标准 unittest 入口由各测试
定位源码。安装后的包另用 `python -I tools/verify_installed.py` 验收。

原始包完整性、独立编译重建与数据工具适配测试位于
`validation/tests/`，使用 `python tools/check_core.py --scope validation`。
新增测试按所需输入放入对应层，不用跳过缺失数据来维持包测试通过。
