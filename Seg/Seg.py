from typing import Generic, List, Optional, TypeVar
from functools import lru_cache as makecache
Self = TypeVar('T', bound='CSeg')

from Bi.Bi import CBi
from Common.CEnum import BI_DIR, MACD_ALGO, TREND_LINE_SIDE
from Common.ChanException import CChanException, ErrCode
from KLine.KLine_Unit import CKLine_Unit
from Math.TrendLine import CTrendLine
from Common.CTime import CTime
from .EigenFX import CEigenFX
from Common.func_util import logger
from Common.CEnum import LineStatus
LINE_TYPE = TypeVar('LINE_TYPE', CBi, "CSeg")


class CSeg(Generic[LINE_TYPE]):
    def __init__(self, idx: int, start_bi: LINE_TYPE, end_bi: LINE_TYPE, status=LineStatus.Unknown, is_sure=True, seg_dir=None, reason="normal"):
        assert start_bi.idx == 0 or start_bi.dir == end_bi.dir or not is_sure, f"{start_bi.idx} {end_bi.idx} {start_bi.dir} {end_bi.dir}"
        self.idx = idx
        self.start_bi = start_bi
        self.end_bi = end_bi
        self.is_sure = is_sure
        self.dir = end_bi.dir if seg_dir is None else seg_dir
        self.status = status if status is not None else LineStatus.Unknown

        from ZS.ZS import CZS
        self.zs_lst: List[CZS[LINE_TYPE]] = []

        self.eigen_fx: Optional[CEigenFX] = None
        self.seg_idx = None  # 线段的线段用
        self.parent_seg: Optional[CSeg] = None  # 在哪个线段里面
        self.pre: Optional[Self] = None
        self.next: Optional[Self] = None

        from BuySellPoint.BS_Point import CBS_Point
        self.bsp: Optional[CBS_Point] = None  # 尾部是不是买卖点

        self.bi_list: List[LINE_TYPE] = []  # 仅通过self.update_bi_list来更新
        self.reason = reason
        self.support_trend_line = None
        self.resistance_trend_line = None
        if end_bi.idx - start_bi.idx < 2:
            self.is_sure = False
        self.check()

        self.ele_inside_is_sure = False
        logger.info(f"[Seg] __init__ <---: {self}")

    def set_seg_idx(self, idx):
        self.seg_idx = idx

    def check(self):
        if not self.is_sure:
            return
        if self.is_down():
            if self.start_bi.get_begin_val() < self.end_bi.get_end_val():
                raise CChanException(f"下降线段起始点应该高于结束点! idx={self.idx}", ErrCode.SEG_END_VALUE_ERR)
        elif self.start_bi.get_begin_val() > self.end_bi.get_end_val():
            raise CChanException(f"上升线段起始点应该低于结束点! idx={self.idx}", ErrCode.SEG_END_VALUE_ERR)
        if self.end_bi.idx - self.start_bi.idx < 2:
            raise CChanException(f"线段({self.start_bi.idx}-{self.end_bi.idx})长度不能小于2! idx={self.idx}", ErrCode.SEG_LEN_ERR)

    def __str__(self):
        return f"idx={self.idx} status={self.status} {self.start_bi.get_begin_klu().time}->{self.end_bi.get_end_klu().time}: dir={self.dir}  is_sure={self.is_sure} reason={self.reason}"

    def add_zs(self, zs):
        self.zs_lst = [zs] + self.zs_lst  # 因为中枢是反序加入的

    def cal_klu_slope(self):
        assert self.end_bi.idx >= self.start_bi.idx
        return (self.get_end_val()-self.get_begin_val())/(self.get_end_klu().idx-self.get_begin_klu().idx)/self.get_begin_val()

    def cal_amp(self):
        return (self.get_end_val()-self.get_begin_val())/self.get_begin_val()

    def cal_bi_cnt(self):
        return self.end_bi.idx-self.start_bi.idx+1

    def clear_zs_lst(self):
        self.zs_lst = []

    def _low(self):
        return self.end_bi.get_end_klu().low if self.is_down() else self.start_bi.get_begin_klu().low

    def _high(self):
        return self.end_bi.get_end_klu().high if self.is_up() else self.start_bi.get_begin_klu().high

    def is_down(self):
        return self.dir == BI_DIR.DOWN

    def is_up(self):
        return self.dir == BI_DIR.UP

    def get_end_val(self):
        return self.end_bi.get_end_val()

    def get_begin_val(self):
        return self.start_bi.get_begin_val()

    def amp(self):
        return abs(self.get_end_val() - self.get_begin_val())

    def get_end_klu(self) -> CKLine_Unit:
        return self.end_bi.get_end_klu()

    def get_begin_klu(self) -> CKLine_Unit:
        return self.start_bi.get_begin_klu()

    def get_klu_cnt(self):
        return self.get_end_klu().idx - self.get_begin_klu().idx + 1

    def cal_macd_metric(self, macd_algo, is_reverse):
        if macd_algo == MACD_ALGO.SLOPE:
            return self.Cal_MACD_slope()
        elif macd_algo == MACD_ALGO.AMP:
            return self.Cal_MACD_amp()
        else:
            raise CChanException(f"unsupport macd_algo={macd_algo} of Seg, should be one of slope/amp", ErrCode.PARA_ERROR)

    def Cal_MACD_slope(self):
        begin_klu = self.get_begin_klu()
        end_klu = self.get_end_klu()
        if self.is_up():
            return (end_klu.high - begin_klu.low)/end_klu.high/(end_klu.idx - begin_klu.idx + 1)
        else:
            return (begin_klu.high - end_klu.low)/begin_klu.high/(end_klu.idx - begin_klu.idx + 1)

    def Cal_MACD_amp(self):
        begin_klu = self.get_begin_klu()
        end_klu = self.get_end_klu()
        if self.is_down():
            return (begin_klu.high-end_klu.low)/begin_klu.high
        else:
            return (end_klu.high-begin_klu.low)/begin_klu.low

    def update_bi_list(self, bi_lst, idx1, idx2):
        logger.info(f"[Seg] update_bi_list --->: bi1={idx1}, end_bi={idx2}")
        for bi_idx in range(idx1, idx2+1):
            bi_lst[bi_idx].parent_seg = self
            logger.info(f"[Seg] update_bi_list --->: bi_lst[{bi_idx}]={bi_lst[bi_idx]}")
            self.bi_list.append(bi_lst[bi_idx])
        if len(self.bi_list) >= 3:
            self.support_trend_line = CTrendLine(self.bi_list, TREND_LINE_SIDE.INSIDE)
            self.resistance_trend_line = CTrendLine(self.bi_list, TREND_LINE_SIDE.OUTSIDE)
        logger.info(f"[Seg] update_bi_list <---")

    def get_first_multi_bi_zs(self):
        return next((zs for zs in self.zs_lst if not zs.is_one_bi_zs()), None)

    def get_final_multi_bi_zs(self):
        zs_idx = len(self.zs_lst) - 1
        while zs_idx >= 0:
            zs = self.zs_lst[zs_idx]
            if not zs.is_one_bi_zs():
                return zs
            zs_idx -= 1
        return None

    def get_multi_bi_zs_cnt(self):
        return sum(not zs.is_one_bi_zs() for zs in self.zs_lst)

    @staticmethod
    def InfoAsTable(seg: 'CSeg', output_file: str = None):
        """
        Display Seg properties in a table format with columns.

        @param seg: CSeg instance to display.
        @param output_file: Optional file path to write output to. If None, prints to console.
        """
        headers = [
            "Dir", "Sure", "BeginTime", "EndTime", "BeginVal", "EndVal",
            "High", "Low", "KLU_Cnt", "BiCnt", "ZsCnt", "MultiBiZsCnt",
            "HasNext", "HasPrev", "HasTrendLine"
        ]
        
        values = [
            str(seg.dir),
            str(seg.is_sure),
            seg.get_begin_klu().time,
            seg.get_end_klu().time,
            f"{seg.get_begin_val():.2f}",
            f"{seg.get_end_val():.2f}",
            f"{seg._high():.2f}",
            f"{seg._low():.2f}",
            str(seg.get_klu_cnt()),
            str(len(seg.bi_list)),
            str(len(seg.zs_lst)),
            str(seg.get_multi_bi_zs_cnt()),
            str(seg.next is not None),
            str(seg.pre is not None),
            str(seg.support_trend_line is not None),
            str(seg.resistance_trend_line is not None)
        ]

        # Calculate column widths, setting a fixed width for the 'Dir' column
        fixed_dir_width = 10  # Adjust this value as needed
        widths = [
            max(fixed_dir_width, len(headers[0])),  # Fixed width for 'Dir'
            *[
                max(len(h), len(str(v))) for h, v in zip(headers[1:], values[1:])
            ]
        ]
        
        # Create output lines
        header_line = " | ".join(h.ljust(w) for h, w in zip(headers, widths))
        separator = "-" * len(header_line)
        value_line = " | ".join(str(v).ljust(w) for v, w in zip(values, widths))
        
        # Output to file or console
        if output_file:
            with open(output_file, 'a') as f:
                f.write(header_line + '\n')
                f.write(value_line + '\n')
                f.write(separator + '\n')
        else:
            print(header_line)
            print(separator)
            print(value_line)