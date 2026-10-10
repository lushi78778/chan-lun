# -*- coding: utf-8 -*-
"""chan 缠论量化核心包(纯 Python 3.6 兼容)

模块:
    bars    - 行情数据归一化
    analysis - 标准行情校验后的批量组合与命名结果
    fx      - 包含处理 + 分型识别
    bi      - 笔识别
    xd      - 线段识别(特征序列两种标准)
    zs      - 中枢识别、走势类型与中枢状态机(课 20/69/70)
    decompose - 同级别分解: 走势类型序列(课 38/39)
    recurse - 级别递归 f2: 三个连续次级别走势类型重叠 = 高一级别中枢,
              逐级上推(课 35/63/84/102)
    bc      - 背驰识别(MACD 辅助: 趋势背驰/盘整背驰)
    bs      - 三类买卖点信号
    cross30 - 日线买卖点 -> 30 分钟跨级别共振确认(区间套)
    gap     - 缺口识别与力度三分类(课 77)

顶层 API: 本模块重新导出各子模块的公开入口, 因此:
    from chan import find_zs, confirm_buy3_30m
等价于:
    from chan.zs import find_zs
    from chan.cross30 import confirm_buy3_30m
完整导出清单见 __all__; 私有函数(下划线开头)与内部实现不在此列。

发布: 发行名 chan-lun-core(import 名 chan), 仓库根 = src/chan(标准
      src-layout, 本包位于仓库根的 src/chan/ 子目录, 见仓库根 pyproject.toml)。
     注意: __version__ 与 pyproject.toml 的 [project] version 需保持一致。
"""

from chan.bars import BAR_KEYS, bars_to_df, normalize_bars, validate_bars
from chan.fx import FX, NewBar, find_fxs, remove_includes
from chan.bi import (BI, BI_STANDARD_81, BI_STANDARD_106, MIN_K_GAP,
                     chan_fx_bi, find_bis)
from chan.xd import XD, chan_bis_xds, find_xds
from chan.zs import (ZS, ZsEvent, build_expanded_zs, classify_trend,
                     find_zs, track_zs, zs_relation)
from chan.bc import (ema, find_pan_bc, find_trend_bc, macd_series,
                     segment_area)
from chan.bs import find_buy_points, find_sell_points
from chan.cross30 import (confirm_buy2_30m, confirm_buy3_30m,
                          confirm_buy3_event_30m, confirm_sell3_30m,
                          confirm_sell3_event_30m, find_run_exhaustion)
from chan.gap import Gap, classify_gap, find_gaps
from chan.decompose import MoveType, same_level_decompose
from chan.recurse import level_up
from chan.zhongyin import (ZhongYinResult, boll_bands, boll_bs1_hints,
                           boll_events, boll_state, track_zhongyin)
from chan.osc import (OscReport, osc_strength, oscillation_monitor,
                      zn_next_estimate)
from chan.biaoli import (BI_TRANSITIONS, SEVERITY_RANKS, bi_state,
                         bi_transition_valid, disease_stage,
                         followup_quality, zhongyin_health)
from chan.levels import (MAX_LEVELS_DEFAULT, MIN_UNITS_FOR_NEXT,
                         LevelDecomposition, change_starts_low,
                         decompose_levels, level_reading)
from chan.strength import (MaArea, MaStrengthState, avg_strength_state,
                           find_ma_bc, ma_areas, sma_series)
from chan.turn import (TURN_BREAK, TURN_CANDIDATES, TURN_EXPANSION,
                       TURN_SUB_FLOOR, classify_bc_turn,
                       guaranteed_rebound_gap)
from chan.minor_turn import (STAGE_BREAKOUT, STAGE_STRONG, STAGE_SUB_BS3,
                             STAGE_WITHIN, classify_minor_turn)
from chan.nest import (BcNestInput, BcNestLevel, NestBcState, nested_bc)
from chan.kiss import (ALIGN_DOWN, ALIGN_UP, KISS_FLY, KISS_LIP, KISS_WET,
                       KissEvent, alignment_series, classify_kiss,
                       find_kisses)
from chan.analysis import AnalysisResult, analyze_bars
from chan.fxpower import (BREAK_EFFECTIVE, BREAK_NONE, BREAK_TESTING,
                          POWER_NEUTRAL, POWER_SEVERE, POWER_STRONG, POWER_WEAK,
                          FxPowerResult, MaBreakState, classify_fx,
                          classify_fx_power, ma_break_state)

__version__ = "0.4.3"

__all__ = [
    # chan.bars 行情归一化
    "BAR_KEYS", "normalize_bars", "bars_to_df", "validate_bars",
    # chan.analysis 批量组合入口
    "AnalysisResult", "analyze_bars",
    # chan.fx 包含处理 + 分型
    "NewBar", "FX", "remove_includes", "find_fxs",
    # chan.bi 笔
    "BI", "MIN_K_GAP", "BI_STANDARD_81", "BI_STANDARD_106", "find_bis", "chan_fx_bi",
    # chan.xd 线段
    "XD", "find_xds", "chan_bis_xds",
    # chan.zs 中枢与走势类型 + 中枢状态机(课 20/69/70)
    "ZS", "ZsEvent", "find_zs", "track_zs", "zs_relation",
    "build_expanded_zs", "classify_trend",
    # chan.bc 背驰(MACD 辅助)
    "ema", "macd_series", "segment_area", "find_trend_bc", "find_pan_bc",
    # chan.bs 三类买卖点
    "find_buy_points", "find_sell_points",
    # chan.cross30 30m 跨级别共振确认
    "find_run_exhaustion", "confirm_buy3_30m", "confirm_sell3_30m",
    "confirm_buy2_30m", "confirm_buy3_event_30m",
    "confirm_sell3_event_30m",
    # chan.gap 缺口识别与力度三分类(课 77)
    "Gap", "find_gaps", "classify_gap",
    # chan.decompose 同级别分解(课 38/39)
    "MoveType", "same_level_decompose",
    # chan.recurse 级别递归 f2(课 35/63/84/102)
    "level_up",
    # chan.zhongyin 中阴阶段 + 布林通道辅助判断(课 89/90)
    "ZhongYinResult", "track_zhongyin", "boll_bands", "boll_state",
    "boll_events", "boll_bs1_hints",
    # chan.osc 中枢震荡监视器(课 92)
    "OscReport", "oscillation_monitor", "osc_strength", "zn_next_estimate",
    # chan.biaoli 走势结构的两重表里关系(课 91/93/99)
    "bi_state", "BI_TRANSITIONS", "bi_transition_valid", "disease_stage",
    "SEVERITY_RANKS", "followup_quality", "zhongyin_health",
    # chan.levels 多级唯一分解——记数法(课 102)
    "LevelDecomposition", "decompose_levels", "level_reading",
    "change_starts_low", "MAX_LEVELS_DEFAULT", "MIN_UNITS_FOR_NEXT",
    # chan.strength 趋势力度与平均力度(课 15)
    "sma_series", "MaArea", "ma_areas", "find_ma_bc",
    "MaStrengthState", "avg_strength_state",
    # chan.turn 背驰-转折定理三分类(课 29)
    "TURN_EXPANSION", "TURN_BREAK", "TURN_SUB_FLOOR", "TURN_CANDIDATES",
    "classify_bc_turn", "guaranteed_rebound_gap",
    # chan.minor_turn 小级别背驰引发大级别转折(课 44/53)
    "STAGE_WITHIN", "STAGE_STRONG", "STAGE_SUB_BS3", "STAGE_BREAKOUT",
    "classify_minor_turn",
    # chan.nest 多级区间套定位(课 61/37)
    "BcNestInput", "BcNestLevel", "NestBcState", "nested_bc",
    # chan.kiss 均线吻系统(课 11/12)
    "KISS_FLY", "KISS_LIP", "KISS_WET", "ALIGN_UP", "ALIGN_DOWN",
    "KissEvent", "alignment_series", "find_kisses", "classify_kiss",
    # chan.fxpower 分型力度与破均线辅助(课79/82)
    "POWER_WEAK", "POWER_NEUTRAL", "POWER_STRONG", "POWER_SEVERE",
    "BREAK_NONE", "BREAK_TESTING", "BREAK_EFFECTIVE",
    "FxPowerResult", "MaBreakState", "classify_fx_power", "classify_fx",
    "ma_break_state",
    # 版本号
    "__version__",
]
