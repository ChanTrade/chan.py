import copy
from typing import Dict, Optional

from Common.CEnum import DATA_FIELD, TRADE_INFO_LST, TREND_TYPE
from Common.ChanException import CChanException, ErrCode
from Common.CTime import CTime
from Math.BOLL import BOLL_Metric, BollModel
from Math.Demark import CDemarkEngine, CDemarkIndex
from Math.KDJ import KDJ
from Math.MACD import CMACD, CMACD_item
from Math.RSI import RSI
from Math.TrendModel import CTrendModel

from .TradeInfo import CTradeInfo


class CKLine_Unit:
    def __init__(self, kl_dict, autofix=False):
        # _time, _close, _open, _high, _low, _extra_info={}
        self.kl_type = None
        self.time: CTime = kl_dict[DATA_FIELD.FIELD_TIME]
        self.close = kl_dict[DATA_FIELD.FIELD_CLOSE]
        self.open = kl_dict[DATA_FIELD.FIELD_OPEN]
        self.high = kl_dict[DATA_FIELD.FIELD_HIGH]
        self.low = kl_dict[DATA_FIELD.FIELD_LOW]

        self.check(autofix)

        self.trade_info = CTradeInfo(kl_dict)

        self.demark: CDemarkIndex = CDemarkIndex()

        self.sub_kl_list = []  # 次级别KLU列表
        self.sup_kl: Optional[CKLine_Unit] = None  # 指向更高级别KLU

        from KLine.KLine import CKLine
        self.__klc: Optional[CKLine] = None  # 指向KLine

        # self.macd: Optional[CMACD_item] = None
        # self.boll: Optional[BOLL_Metric] = None
        self.trend: Dict[TREND_TYPE, Dict[int, float]] = {}  # int -> float

        self.limit_flag = 0  # 0:普通 -1:跌停，1:涨停
        self.pre: Optional[CKLine_Unit] = None
        self.next: Optional[CKLine_Unit] = None

        self.set_idx(-1)

    def __deepcopy__(self, memo):
        _dict = {
            DATA_FIELD.FIELD_TIME: self.time,
            DATA_FIELD.FIELD_CLOSE: self.close,
            DATA_FIELD.FIELD_OPEN: self.open,
            DATA_FIELD.FIELD_HIGH: self.high,
            DATA_FIELD.FIELD_LOW: self.low,
        }
        for metric in TRADE_INFO_LST:
            if metric in self.trade_info.metric:
                _dict[metric] = self.trade_info.metric[metric]
        obj = CKLine_Unit(_dict)
        obj.demark = copy.deepcopy(self.demark, memo)
        obj.trend = copy.deepcopy(self.trend, memo)
        obj.limit_flag = self.limit_flag
        obj.macd = copy.deepcopy(self.macd, memo)
        obj.boll = copy.deepcopy(self.boll, memo)
        if hasattr(self, "rsi"):
            obj.rsi = copy.deepcopy(self.rsi, memo)
        if hasattr(self, "kdj"):
            obj.kdj = copy.deepcopy(self.kdj, memo)
        obj.set_idx(self.idx)
        memo[id(self)] = obj
        return obj

    @property
    def klc(self):
        assert self.__klc is not None
        return self.__klc

    def set_klc(self, klc):
        self.__klc = klc

    @property
    def idx(self):
        return self.__idx

    def set_idx(self, idx):
        self.__idx: int = idx

    @property
    def _time(self) -> CTime:
        return self.time

    def __str__(self):
        return f"{self.idx}:{self.time_str}/{self.kl_type} open={self.open} close={self.close} high={self.high} low={self.low} {self.trade_info}"

    def check(self, autofix=False):
        '''
        检查K线数据是否合法
        '''
        if self.low > min([self.low, self.open, self.high, self.close]):
            if autofix:
                self.low = min([self.low, self.open, self.high, self.close])
            else:
                raise CChanException(f"{self.time} low price={self.low} is not min of [low={self.low}, open={self.open}, high={self.high}, close={self.close}]", ErrCode.KL_DATA_INVALID)
        if self.high < max([self.low, self.open, self.high, self.close]):
            if autofix:
                self.high = max([self.low, self.open, self.high, self.close])
            else:
                raise CChanException(f"{self.time} high price={self.high} is not max of [low={self.low}, open={self.open}, high={self.high}, close={self.close}]", ErrCode.KL_DATA_INVALID)

    def add_children(self, child):
        '''
        添加子K线
        '''
        self.sub_kl_list.append(child)

    def set_parent(self, parent: 'CKLine_Unit'):
        '''
        设置父K线
        '''
        self.sup_kl = parent

    def get_children(self):
        '''
        获取子K线列表
        '''
        yield from self.sub_kl_list

    @property
    def _low(self):
        return self.low

    @property 
    def _high(self):
        return self.high

    # 计算基于裸K的各种指标
    def set_metric(self, metric_model_lst: list) -> None:
        for metric_model in metric_model_lst:
            if isinstance(metric_model, CMACD):
                # 使用当前K线的收盘价 计算 MACD 指标
                self.macd: CMACD_item = metric_model.add(self.close)
            elif isinstance(metric_model, CTrendModel):
                if metric_model.type not in self.trend:
                    self.trend[metric_model.type] = {}
                    # 使用当前K线的收盘价 计算 趋势指标
                self.trend[metric_model.type][metric_model.T] = metric_model.add(self.close)
            elif isinstance(metric_model, BollModel):
                # 使用当前K线的收盘价 计算 BOLL 指标
                self.boll: BOLL_Metric = metric_model.add(self.close)
            elif isinstance(metric_model, CDemarkEngine):
                # 使用当前K线的收盘价 计算 Demark 指标
                self.demark = metric_model.update(idx=self.idx, close=self.close, high=self.high, low=self.low)
            elif isinstance(metric_model, RSI):
                # 使用当前K线的收盘价 计算 RSI 指标
                self.rsi = metric_model.add(self.close)
            elif isinstance(metric_model, KDJ):
                # 使用当前K线的最高价、最低价、收盘价 计算 KDJ 指标
                self.kdj = metric_model.add(self.high, self.low, self.close)

    def get_parent_klc(self):
        '''
        获取父K线
        '''
        assert self.sup_kl is not None
        return self.sup_kl.klc

    def include_sub_lv_time(self, sub_lv_t: str) -> bool:
        '''
        判断当前K线是否包含子级别K线
        '''
        if self.time.to_str() == sub_lv_t:
            return True
        for sub_klu in self.sub_kl_list:
            if sub_klu.time.to_str() == sub_lv_t:
                return True
            if sub_klu.include_sub_lv_time(sub_lv_t):
                return True
        return False

    def set_pre_klu(self, pre_klu: Optional['CKLine_Unit']):
        # 设置当前K线的前一个K线
        if pre_klu is None:
            return
        pre_klu.next = self
        self.pre = pre_klu

    def Info(self):
        # 获取当前K线的信息
        str = (f"{self.kl_type} - kid:{self.idx:05d}:{self.time} open={self.open:.2f} close={self.close:.2f} high={self.high:.2f} low={self.low:.2f}")
        return str