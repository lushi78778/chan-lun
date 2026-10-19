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

`test_contracts.py` 执行 README 的完整入门、空输入和回放示例，核对展示摘要，
并读取 `docs/usage.md` 的分步基础链与独立辅助示例。迁移指纹仍从
`docs/migration.md` 执行。文档移动时同步读取位置，不能只移走示例而移除原验证。
README 同时作为 PyPI 长描述，现有契约还检查导航链接不依赖仓库相对基址，
并核对指向本仓库文件的目标存在。现代构建阶段另以 twine 和既有发行工具的
`check-description` 实际渲染产物描述，渲染不可用及相对链接均不能通过。

原始包完整性、独立编译重建与数据工具适配测试位于
`validation/tests/`，使用 `python tools/check_core.py --scope validation`。
新增测试按所需输入放入对应层，不用跳过缺失数据来维持包测试通过。

## 夹具与独立预期

`fixtures/` 包括原图相对几何标注和真实行情独立标注。每组应记录来源、完整
最小输入、预期、理由及必要确认前缀；先独立冻结预期，再与库输出比较，不能
从算法输出反向生成期望。编译工具、原始材料和重建验收留在资产层。

`real_causal_formation_81.json` 是固定笔、MACD 辅助前提下的条件算术，
由现有因果回放测试覆盖；其 annotation/limits 保留完整 F1、严格一类
证明和默认零轴筛选的边界，不因构造结果为 failed 就提升为精确理论真值。
同一冻结输入的最低 F1-bi 切点和证明表集中在
`test_real_f1_originals.py`；其逐原始前缀、相邻 F2 和严格扫描检查覆盖
声明规则下不能直接升级的边界，不修改原条件 fixture。

`test_ma_points.py` 复用三个既有 fixture 的原始报价，独立整数 SMA 和固定
区间表核对真实均线辅助条件。日线二类包含非镜像买卖两侧和飞/唇吻，
60m/5m 核对面积与平均力度相反的分支、湿吻及即时预警撤销。实际确认
相邻前缀、收盘/到达边界、延迟与未来缺字段分别验证；不从原笔/XD 标签
推定均线点位，不把这些工程算术称为茅台原图或精确理论真值。

上/下镜像、逐前缀、退化输入和尾部修订按对应定义覆盖。未来数据隔离验证固定
观察时点之外的价格不影响可见结果；观察时点推进后的未完成结构修订另行验证。
单个窗口一致只证明该冻结样本，不扩大为全部理论或真实分支覆盖。

原图几何关系不等于恢复历史 OHLC；缺失报价、原图歧义和未找到的真实正例须
保留为证据边界。当前覆盖见[正式计划 §6](../docs/缠论理论逐一实现计划.md#6-实现清单进度表唯一进度维护处)，
逐版本输入和收据见[资产索引](../validation/README.md)。
