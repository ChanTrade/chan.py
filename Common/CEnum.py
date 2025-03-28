from enum import Enum, auto
from typing import Literal


class DATA_SRC(Enum):
    BAO_STOCK = auto()
    CCXT = auto()
    CSV = auto()


class KL_TYPE(Enum):
    K_1M = auto()
    K_DAY = auto()
    K_WEEK = auto()
    K_MON = auto()
    K_YEAR = auto()
    K_5M = auto()
    K_15M = auto()
    K_30M = auto()
    K_60M = auto()
    K_3M = auto()
    K_QUARTER = auto()


class KLINE_DIR(Enum):
    '''
    合并K线的方向
    '''
    UP = auto()  # 向上合并
    DOWN = auto()  # 向下合并
    COMBINE = auto()  # 合并
    INCLUDED = auto()  # 包含


class FX_TYPE(Enum):
    BOTTOM = auto()
    TOP = auto()
    UNKNOWN = auto()


class BI_DIR(Enum):
    UP = auto()
    DOWN = auto()


class BI_TYPE(Enum):
    UNKNOWN = auto()
    STRICT = auto()
    SUB_VALUE = auto()  # 次高低点成笔
    TIAOKONG_THRED = auto()
    DAHENG = auto()
    TUIBI = auto()
    UNSTRICT = auto()
    TIAOKONG_VALUE = auto()


BSP_MAIN_TYPE = Literal['1', '2', '3']


class BSP_TYPE(Enum):
    T1 = '1'
    T1P = '1p'
    T2 = '2'
    T2S = '2s'
    T3A = '3a'  # 中枢在1类后面
    T3B = '3b'  # 中枢在1类前面

    def main_type(self) -> BSP_MAIN_TYPE:
        return self.value[0]  # type: ignore


class AUTYPE(Enum):
    QFQ = auto()
    HFQ = auto()
    NONE = auto()


class TREND_TYPE(Enum):
    MEAN = "mean"
    MAX = "max"
    MIN = "min"


class TREND_LINE_SIDE(Enum):
    INSIDE = auto()
    OUTSIDE = auto()


class LEFT_SEG_METHOD(Enum):
    ALL = auto()
    PEAK = auto()


class FX_CHECK_METHOD(Enum):
    STRICT = auto()
    LOSS = auto()
    HALF = auto()
    TOTALLY = auto()


class SEG_TYPE(Enum):
    BI = auto()
    SEG = auto()


class MACD_ALGO(Enum):
    AREA = auto()
    PEAK = auto()
    FULL_AREA = auto()
    DIFF = auto()
    SLOPE = auto()
    AMP = auto()
    VOLUMN = auto()
    AMOUNT = auto()
    VOLUMN_AVG = auto()
    AMOUNT_AVG = auto()
    TURNRATE_AVG = auto()
    RSI = auto()


class DATA_FIELD:
    FIELD_NAME = "symbol"
    FIELD_TIME = "time_key"
    FIELD_OPEN = "open"
    FIELD_HIGH = "high"
    FIELD_LOW = "low"
    FIELD_CLOSE = "close"
    FIELD_VOLUME = "volume"  # 成交量
    FIELD_TURNOVER = "turnover"  # 成交额
    FIELD_TURNRATE = "turnover_rate"  # 换手率

class LineStatus(Enum):
    '''
    线段状态
    '''
    Unknown = auto()  # 未知
    NewGenerated = auto()  # 新线段生成
    NotBreaking = auto()  # 未破坏
    BreakingTypeOne = auto()  # 线段一类破坏
    BreakingTypeTwo = auto()  # 线段二类破坏
    Completed = auto()  # 线段完成

TRADE_INFO_LST = [DATA_FIELD.FIELD_VOLUME, DATA_FIELD.FIELD_TURNOVER, DATA_FIELD.FIELD_TURNRATE]
