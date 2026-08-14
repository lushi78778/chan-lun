# -*- coding: utf-8 -*-
"""chan 缠论量化核心包(纯 Python 3.6 兼容)

模块:
    bars    - 行情数据归一化
    fx      - 包含处理 + 分型识别
    bi      - 笔识别
    xd      - 线段识别(特征序列两种标准)
    zs      - 中枢识别与走势类型
    bc      - 背驰识别(MACD 辅助: 趋势背驰/盘整背驰)
    bs      - 三类买卖点信号
    cross30 - 日线买卖点 -> 30 分钟跨级别共振确认(区间套)

发布: 发行名 chan-lun(import 名 chan), pyproject.toml 与本包同目录
      (src/chan 即 chan-lun 仓库根)。
     注意: __version__ 与 pyproject.toml 的 [project] version 需保持一致。
"""

__version__ = "0.1.1"
