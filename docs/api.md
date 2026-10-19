# 公开 API 与行为契约

适用版本：1.x（契约建立于 0.13.x 的 R6 冻结阶段，1.0.0 沿用）。本文件是**契约参考**：回答
"能调用什么、返回什么、什么算稳定"。入门见 [README.md](../README.md)，详细用法见
[使用指南](usage.md)，分层与输入契约见
[ARCHITECTURE.md](architecture.md)，仓库职责见 [目录索引](README.md)。
理论进度唯一维护在实现计划 §6。

## 1. 冻结范围与变更规则

| 契约面 | 冻结等级 | 变更规则 |
|---|---|---|
| 导出名与 `__all__` | 冻结 | 只增不减不改名；删除须升主版本 |
| `to_dict()` 键集 | 冻结 | 只增不改名不删；新增须另排版本并登记 |
| 常量/枚举字符串值 | 冻结 | 值即协议，禁止改值重命名 |
| 时间字段语义 | 冻结 | 各对象的时间转换与 None 语义保持，具体见 §3、§5 |
| 异常类型 | 冻结 | `ValueError`/`TypeError` 分类不变 |
| 算法输出 | 按版本登记 | 相同输入与参数在同版内可复现；算法修正须旧/新逐点差异收据与 CHANGELOG，不将候选尾部修订当作兼容破坏 |
| 模块私有成员（`_` 开头） | 无契约 | 不向调用方保证稳定性；库内共享数学模块按架构约定使用 |

### 1.x 版本规则

按 [SemVer 2.0.0](https://semver.org/lang/zh-CN/) 评估变更，版本号与实际发布状态分别记录。

- 主版本：删除或重命名公开入口/字段，改变时间含义、空值含义、参数默认
  语义或异常分类等不兼容契约；提供迁移说明和行为差异证据。
- 次版本：兼容新增入口、可选参数、字段或原因码；旧调用和既有字段含义
  保持。新增序列化键需要明确登记，调用方不应把扩展键集当作位置协议。
- 修订版本：修复实现偏离既有文档契约的缺陷。即使修正算法输出，也须保留
  旧/新固定样本与逐前缀差异收据、解释影响范围并写入 CHANGELOG；若修正
  本身需要改变公开契约，则按主版本处理。
- 兼容的打包、安装、发行说明或文档错误修正可纳入修订版本；工程治理随
  实际影响迭代 1.x。仅内部维护可独立提交暂不发布，不为每笔提交机械升版；
  已发布版本的内容与标签保持不变。
- 输入被修订、参数改变、未完成尾部按新证据演进，按既有输入版本和时间
  契约解释；它们与同一输入的实现回归分别记录。

公开 = 出现在 `chan.__all__`（1.1.0 起 187 项，原 185 项保留）。模块 `__all__`
与包级保持同步，由契约测试检查。

## 2. 公开入口分层

单个行情或结构序列对应单标的、单周期；多级和跨成员接口接收调用方
显式对齐的多组序列。输出按模块区分结构识别、辅助候选与条件判定。

| 层 | 模块 | 代表入口 | 输入 | 性质 |
|---|---|---|---|---|
| 行情与基础结构 | `bars` `fx` `bi` `xd` `zs` `bc` | `normalize_bars` `find_fxs` `find_bis` `find_xds` `find_zs` | 原始行情及各入口要求的上游结构 | 结构识别 |
| 批量组合与回放 | `analysis` `replay` `availability` | `analyze_bars` `analyze_at` `replay_bars` `analyze_available` | bar 序列(+观察时点) | 接线组合 |
| 三类买卖点候选 | `bs` | `find_buy_points` `find_sell_points` | 笔级结构 | 笔级简化候选 |
| 两级辅助核对 | `cross30` | `confirm_buy3_30m` `confirm_sell3_30m` | 日线事件/边界与截断的 30m 行情 | 工程条件满足，不自动认定严格理论确认 |
| 已确认走势上的条件与组合 | `first` `second` `third` `strict` `point_chain` `completion` | `scan_first_points` `find_second_points` `find_third_points` `scan_strict_divergence` `analyze_point_chain` | 已确认次级走势及各入口要求的行情、上下文或力度方法 | 辅助候选、条件判定和组合分别解释 |
| 构造状态 | `bottom` `fractal_range` | `formation_state` `fractal_range_state` | 已确认事件，或已确认分型区间及后续可用行情 | 事件构造与分型区间辅助状态分别解释 |
| 因果谱系与诊断 | `lineage` `rounds` `causal_graph` | `track_center_lineage` `track_rounds` `causal_graph_dot` | 走势/单元序列 | 事件谱系 |
| 理论辅助模块 | `gap` `kiss` `strength` `turn` `minor_turn` `zhongyin` `osc` `biaoli` `levels` `sector` `fxpower` `macd_guard` `ma_points` `nest` `decompose` `recurse` | `classify_gap` `find_kisses` `classify_bc_turn` `track_zhongyin` `oscillation_monitor` `decompose_levels` … | 各模块声明的最小输入 | 课理论工程化，阈值已声明 |

## 3. 时间字段契约

| 字段 | 含义 | 序列化 |
|---|---|---|
| `dt` | 结构所在位置（分型中心 K、笔端点、bar 时间） | 依对象契约；`NewBar` 的例外见 §5 |
| `start_dt` / `end_dt` | 走势/段/中枢起止结构时间 | `str()` |
| `closed_dt` | bar 收盘时刻（输入元数据） | `str()` |
| `available_dt` | 行情实际到达时刻（实际可用时间门控） | `str()` |
| `confirmed_dt` | 全部被消费证据的最晚到达/成立时刻，不早于任何证据 | `str()` |
| `ended_dt` | 中阴/上下文实际结束确认时刻；未知为 `None` | `str()` 或 `None` |
| `as_of` | 输入截止观察时刻；空输入为 `None` | `str()` 或 `None` |
| `evidence_dt` | XD 最后一笔证据的端点；不等于实际行情确认时间 | `str()` 或 `None` |
| `MaPointState.observed_dt` | 即时组合所用最后行情的实际到达；不是精确点确认 | `str()` 或 `None` |

**结构时间 ≠ 确认时间 ≠ 可用时间**。按端点时间过滤全样本结果不能
还原历史可见状态；回放必须逐前缀重算或读当时快照，见
[时间与回放指南](usage.md#2-按观察时点计算与追踪修订)。

## 4. 身份体系

| 身份字段 | 所属对象 | 作用域与组合规则 |
|---|---|---|
| `move_id` | `ConfirmedMove`/`ConfirmedMoveType` | 调用方声明的稳定身份；同一输入版本内唯一 |
| `point_id` | `FirstPoint` | 一类候选身份（`[level, trend.move_id, 'first']` JSON） |
| `context_id` | `SecondPointContext`/`ThirdPointContext` | 独立反转/中枢上下文身份；多次反转不同身份，不是数组下标 |
| `center_id` | `ConfirmedCenter`/`CenterVersion` | 中枢身份；与 `context_id` 分属两套体系，不可互替 |
| `leave_move_id` / `pull_move_id` | `ThirdPoint`/`SecondPoint` | 参与走势身份；与 context_id 组合唯一区分点位 |
| `divergence_id` | `StrictDivergence` | 严格扫描结果身份 |
| `identity` | `ObservationChange` | 修订账本条目身份 |

身份须为非空字符串；重复/缺失身份在条件接口中抛 `ValueError`。
输入被供应方修订时须新建输入版本，禁止静默覆盖旧收据。

## 5. 序列化契约（`to_dict()` 键集冻结）

各对象的 `to_dict()` 键集与字段类型由 `tests/test_api_contract.py` 和模块测试
固化，不要求所有底层对象共用一个 JSON schema。属性本身保持原类型，
序列化不回写对象。

`AnalysisResult.to_dict()` 将时间转为字符串、数组转为列表，并生成独立的
JSON 可写快照。底层 `NewBar.to_dict()` 则保留原始 `dt` 类型，只复制
`elements`；若 `dt` 是 datetime/Timestamp，调用方须自行转换，或通过
`AnalysisResult.to_dict()` 存档。不能将任意底层对象或其 dict 一概视为可直接
`json.dumps`。其他对象的时间和空值转换按下表、各类 docstring 与模块测试执行。

核心链键集（0.13.1 快照）：

| 对象 | 键 |
|---|---|
| `AnalysisResult.to_dict()` | as_of, bi_trends, bi_zss, bis, buy_points, dea, dif, fxs, hist, new_bars, pan_bc, sell_points, trend_bc, xd_zss, xds |
| `NewBar.to_dict()` | close, dt, elements, high, low, open, volume |
| `FX.to_dict()` | bar_index, dt, elements, high, kind, low, value |
| `BI.to_dict()` | direction, end, end_dt, end_index, high, low, start, start_dt, start_index |
| `XD.to_dict()` | complete, dd, direction, end, evidence_dt, evidence_end_index, gg, mode, start |
| `ZS.to_dict()` | dd, direction, end_dt, extended_9, gg, start_dt, xd_count, zd, zg |
| `ReplaySnapshot.to_dict()` | changes, observed_dt, result |
| `ObservationChange.to_dict()` | after, before, field, first_seen, identity, kind, observed_dt |
| `Gap.to_dict()` | direction, dt_a, dt_b, index_a, index_b, lower, upper |
| `FirstPointScan.to_dict()` | completed_types, exclusions, points |
| `StrictScan.to_dict()` | completed_types, open_tail, results, skipped |
| `PointChain.to_dict()` | contexts, first_points, formations, second_points, third_points, unresolved_move_ids |
| `PointContext`（嵌套） | causal_center, first_point, previous_center, second_context |
| `MaPointState`（1.1.0 新增） | status, direction, observed_dt, reference_start_dt, reference_end_dt, evidence_start_dt, evidence_end_dt, kiss_start_dt, kiss_end_dt, kiss_index, kiss_kind, reference_strength, current_strength, stretch, stretch_shortening, reasons, kind, last_kiss_proven |

`ma_point_state` 的快照只描述当前可见输入，不累计历史预警。`status` 为
`insufficient_evidence / no_warning / warning`；仅 warning 时 kind 为
`ma_buy1_warning / ma_sell1_warning`，其余为 None。direction 是当前均线面积
方向，down 对应买侧预警。两个 strength 是绝对平均力度，stretch 带符号；
last_kiss_proven 始终 False。对象不含 dt、price 或 confirmed_dt；不会扩写
既有 MaPoint 的键集，也不能按永久已确认候选的方式使用。

其余带 `to_dict()` 的类（osc/zhongyin/kiss/strength/sector/fxpower/
lineage/rounds/nest/levels/ma_points/fractal_range/completion/
bottom/second/third/decompose/bi 的结构对象）键集同样冻结，见各自
docstring 与模块测试。

## 6. 常量与枚举值域

原因码与判据常量（值即协议，包级直出）：

| 常量 | 值 | 用途 |
|---|---|---|
| `REASON_BC` / `REASON_STRONGER` / `REASON_NO_EXTREME` / `REASON_WEAK_SIGN` / `REASON_NOT_NESTED` / `REASON_EMPTY` | `bc` / `stronger` / `no_new_extreme` / `weak_sign` / `not_nested` / `empty` | `nested_bc` 各级判定原因 |
| `TURN_BREAK` / `TURN_EXPANSION` / `TURN_SUB_FLOOR` | `turn` / `expansion` / `sub_floor` | 背驰-转折三分类 |
| `TURN_CANDIDATES` | `['consolidation', 'counter_trend']` | turn 后续候选 |
| `STAGE_WITHIN` / `STAGE_STRONG` / `STAGE_SUB_BS3` / `STAGE_BREAKOUT` | `within` / `strong` / `sub_bs3` / `breakout` | 小转大四阶段 |
| `KISS_FLY` / `KISS_LIP` / `KISS_WET` | `fly` / `lip` / `wet` | 均线吻三分类 |
| `ALIGN_UP` / `ALIGN_DOWN` | `up` / `down` | 多头/空头排列 |
| `POWER_WEAK` / `POWER_NEUTRAL` / `POWER_STRONG` / `POWER_SEVERE` | `weak` / `neutral` / `strong` / `severe` | 分型力度四档 |
| `BREAK_NONE` / `BREAK_TESTING` / `BREAK_EFFECTIVE` | `none` / `testing` / `effective` | 破均线三态 |
| `STRICT_CONFIRMED` / `STRICT_CANDIDATE` / `STRICT_INSUFFICIENT` / `STRICT_REJECTED` | `confirmed` / `candidate` / `insufficient_evidence` / `rejected` | 严格四类返回语义 |
| `BI_STANDARD_81` / `BI_STANDARD_106` | `'81'` / `'106'` | 笔标准 |
| `UPGRADE_UNITS` / `OSC_UPGRADE_N` | `9` / `9` | 中枢升级阈值（课 20/69/92） |
| `WEDGE_MIN_RUN` | `4` | 楔型最少 Zn 样本（工程阈值） |
| `MAX_LEVELS_DEFAULT` / `MIN_UNITS_FOR_NEXT` | `8` / `3` | 多级分解上推参数 |
| `MA_PERIODS` | `(5,13,21,34,55,89,144,233)` | 板块均线周期（课 106） |
| `MIN_K_GAP` | `3` | 成笔最少间隔 K 数 |

事件 `kind` 值域：`buy1/buy2/buy3/sell1/sell2/sell3`（点位类）、
`up/down/consolidation`（走势方向/类型）、`top/bottom`（分型与底顶）。
`ZhongYinResult.stage`：`before/center/ended`；`FormationState.phase`：
`constructing/completed/failed`；`ZhongYinResult.events` 内
`boll_state` 等词表见 `zhongyin.py` docstring。

## 7. 原因码体系

| 产生者 | 载体 | 值域 |
|---|---|---|
| `scan_first_points` | `exclusions` 每项 `(move_id, 原因码)` | `not_trend` / `no_comparable_center_tail` / `no_directional_compare_legs` / `center_waves_overlap` / `no_new_extreme` / `internal_extreme_time_unknown` / `waiting_price_evidence` / `area_not_positive_and_weaker` / `no_zero_axis_pull` / `zero_width_center` |
| `scan_strict_divergence` | `skipped` 每项 `(move_id, 原因码)`；`results[].reason` | skipped：`not_trend` / `no_matching_decomposition` / 完成项评估原因；result reason：`force_missing` / `force_unavailable`（证据不足）/ `force_not_declining`（否决）/ `force_decline`（成立）/ `trend_open`（开放尾部）等 |
| `strict_nested_chain` | `levels[].status` | `bc` / `no_new_extreme` / `force_not_declining` / `force_missing` / `force_unavailable` / `no_sub_center` / `no_compare_legs` / `not_covered` |
| `nested_bc` | `levels[].reason` | `REASON_*` 六常量 |
| `ma_point_state`（1.1.0） | `reasons` 有序元组，序列化为列表 | `no_visible_bars` / `ma_unavailable` / `reference_missing` / `kiss_missing` 为缺证据；`kiss_not_continuation` / `kiss_count_below_two` / `area_closed` / `price_not_trending` / `average_not_weaker` / `stretch_not_shortening` 表示本组合相应条件不满足，不判精确理论点位不存在 |

原因码字符串值属于冻结契约；新增码须排版本登记。

## 8. 校验与异常口径（两档）

| 档 | 适用 | 行为 |
|---|---|---|
| 条件判定入口（`classify_*`、`find_*`、`scan_*`、`track_*`） | 入参类型/结构非法 | 抛 `ValueError`（业务校验）或 `TypeError`（容器类型）；消息含中文字段名 |
| 纯读函数（`bi_state`、`bi_transition_valid` 等） | 入参值非法 | 返回 `None` / `False`，不抛异常 |

调用方不得依赖异常消息文本（非冻结），只依赖异常类型与抛出条件。

## 9. 空值与待判语义

- `None`：字段语义上的"未知/未形成/不适用"，非缺失错误（如
  `causal_center=None` 表示尚未形成因果中枢）。
- 空列表/空元组：计算完成且无结果（如无买卖点）。
- 排除清单（`exclusions`/`skipped`）：未输出该类候选/结果的首个原因，
  可含问题不适用、构造不足、证据未到达或当前筛选未通过，不能统一解读
  为严格接口的 `rejected`。`completed_types` 仅计已完成类型，独立保留。
- 开放尾部（`open_tail=True`、`STRICT_CANDIDATE`）随前缀演进，
  可被后续数据否决，不是确认。
- 均线力度（1.0.2 修正）：前导暖机之后的缺值不是相交证据，
  `ma_areas` 保留未封闭尾段，`avg_strength_state` 返回 `None`。
  缺口前实际相交确认的历史候选保留；与 1.0.1 的差异见 CHANGELOG。

## 10. 稳定性声明

- 严格接口输出是**条件判定**，不是交易指令；辅助候选（MACD 一类）
  不冒充严格理论结论。
- `FirstPointScan.exclusions` 是未输出辅助候选的首个原因，包含不适用、
  待补证与当前筛选未通过，不等于严格接口的 `rejected`。点位链的二/三类
  和构造终态继续依赖其一类锚点；点位由 `context_id` 关联 `point_id`，
  `formations` 与 `contexts` 同序对应，经上下文的 `first_point.method`
  核对来源，不能只凭 `kind` 或 `phase` 将辅助链解释为严格证明。
- 工程阈值（`WEDGE_MIN_RUN`、boll 参数、`fxpower` 档位等）已逐项
  声明理论/工程性质（见各模块 docstring 与《辅助模块能力与证据
  矩阵》）。
- 已发布版本保留；升级前保存旧结果并逐前缀比较，见[迁移指南](migration.md)。
