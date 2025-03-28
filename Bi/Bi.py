from typing import List, Optional

from Common.cache import make_cache
from Common.CEnum import BI_DIR, BI_TYPE, DATA_FIELD, FX_TYPE, MACD_ALGO
from Common.ChanException import CChanException, ErrCode
from KLine.KLine import CKLine
from KLine.KLine_Unit import CKLine_Unit
from Common.CTime import CTime
from Common.func_util import logger

class CBi:
    def __init__(self, begin_klc: CKLine, end_klc: CKLine, idx: int, is_sure: bool):
        """
        Initialize a CBi instance.

        @param begin_klc: The beginning KLine.
        @param end_klc: The ending KLine.
        @param idx: The index of the Bi.
        @param is_sure: Boolean indicating if the Bi is sure.
        """
        # self.__begin_klc = begin_klc
        # self.__end_klc = end_klc
        self.__dir = None
        self.__idx = idx
        self.__type = BI_TYPE.STRICT

        self.set(begin_klc, end_klc)

        self.__is_sure = is_sure
        self.__sure_end: List[CKLine] = []

        self.__seg_idx: Optional[int] = None

        from Seg.Seg import CSeg
        self.parent_seg: Optional[CSeg[CBi]] = None  # 在哪个线段里面

        from BuySellPoint.BS_Point import CBS_Point
        self.bsp: Optional[CBS_Point] = None  # 尾部是不是买卖点

        self.next: Optional[CBi] = None
        self.pre: Optional[CBi] = None

    def clean_cache(self):
        """
        Clean the memoization cache.
        """
        self._memoize_cache = {}

    @property
    def begin_klc(self): return self.__begin_klc

    @property
    def end_klc(self): return self.__end_klc

    @property
    def dir(self): return self.__dir

    @property
    def idx(self): return self.__idx

    @property
    def type(self): return self.__type

    @property
    def is_sure(self): return self.__is_sure

    @property
    def sure_end(self): return self.__sure_end

    @property
    def klc_lst(self):
        klc = self.begin_klc
        while True:
            yield klc
            klc = klc.next
            if not klc or klc.idx > self.end_klc.idx:
                break

    @property
    def klc_lst_re(self):
        klc = self.end_klc
        while True:
            yield klc
            klc = klc.pre
            if not klc or klc.idx < self.begin_klc.idx:
                break

    @property
    def seg_idx(self): return self.__seg_idx

    def set_seg_idx(self, idx):
        """
        Set the segment index.

        @param idx: The segment index to set.
        """
        self.__seg_idx = idx

    def __str__(self):
        """
        Return a string representation of the CBi instance.

        @return: A string representing the direction and KLine range.
        """
        return f"{self.dir}|{self.begin_klc} ~ {self.end_klc}"

    def check(self):
        """
        Check the consistency of the Bi's direction and endpoints.

        @raises CChanException: If the direction and endpoints are inconsistent.
        """
        try:
            if self.is_down():
                assert self.begin_klc.high > self.end_klc.low
            else:
                assert self.begin_klc.low < self.end_klc.high
        except Exception as e:
            raise CChanException(f"{self.idx}:{self.begin_klc[0].time}~{self.end_klc[-1].time}笔的方向和收尾位置不一致!", ErrCode.BI_ERR) from e

    def set(self, begin_klc: CKLine, end_klc: CKLine):
        """
        Set the beginning and ending KLine for the Bi.

        @param begin_klc: The beginning KLine.
        @param end_klc: The ending KLine.
        @raises CChanException: If the direction is invalid.
        """
        self.__begin_klc: CKLine = begin_klc
        self.__end_klc: CKLine = end_klc
        if begin_klc.fx == FX_TYPE.BOTTOM:
            self.__dir = BI_DIR.UP
        elif begin_klc.fx == FX_TYPE.TOP:
            self.__dir = BI_DIR.DOWN
        else:
            raise CChanException("ERROR DIRECTION when creating bi", ErrCode.BI_ERR)
        self.check()
        self.clean_cache()
    @property
    def starttime(self):
        """
        Get the start time of the Bi.

        @return: The time of the beginning KLine unit.
        """
        return self.begin_klc[0].time

    @property 
    def endtime(self):
        """
        Get the end time of the Bi.

        @return: The time of the ending KLine unit.
        """
        return self.end_klc[-1].time

    @make_cache
    def get_begin_val(self):
        return self.begin_klc.low if self.is_up() else self.begin_klc.high

    @make_cache
    def get_end_val(self):
        return self.end_klc.high if self.is_up() else self.end_klc.low

    @make_cache
    def get_begin_klu(self) -> CKLine_Unit:
        if self.is_up():
            return self.begin_klc.get_peak_klu(is_high=False)
        else:
            return self.begin_klc.get_peak_klu(is_high=True)

    @make_cache
    def get_end_klu(self) -> CKLine_Unit:
        if self.is_up():
            return self.end_klc.get_peak_klu(is_high=True)
        else:
            return self.end_klc.get_peak_klu(is_high=False)
    @property
    def start_klu(self):
        """
        Get the starting KLine unit of the Bi.

        @return: The starting KLine unit.
        """
        return self.get_begin_klu()

    @property
    def end_klu(self):
        """
        Get the ending KLine unit of the Bi.

        @return: The ending KLine unit.
        """
        return self.get_end_klu()

    @make_cache
    def amp(self):
        return abs(self.get_end_val() - self.get_begin_val())

    @make_cache
    def get_klu_cnt(self):
        return self.get_end_klu().idx - self.get_begin_klu().idx + 1

    @make_cache
    def get_klc_cnt(self):
        assert self.end_klc.idx == self.get_end_klu().klc.idx
        assert self.begin_klc.idx == self.get_begin_klu().klc.idx
        return self.end_klc.idx - self.begin_klc.idx + 1

    @make_cache
    def _high(self):
        return self.end_klc.high if self.is_up() else self.begin_klc.high

    @make_cache
    def _low(self):
        return self.begin_klc.low if self.is_up() else self.end_klc.low

    @make_cache
    def _mid(self):
        return (self._high() + self._low()) / 2  # 笔的中位价

    @make_cache
    def is_down(self):
        return self.dir == BI_DIR.DOWN

    @make_cache
    def is_up(self):
        return self.dir == BI_DIR.UP

    def update_virtual_end(self, new_klc: CKLine):
        """
        更新笔的虚拟结束K线
        """
        self.append_sure_end(self.end_klc)
        self.update_new_end(new_klc)
        self.__is_sure = False
        # print bi_list
        logger.info(f"[Bi] update_virtual_end -->bi_list: {self}")

    def restore_from_virtual_end(self, sure_end: CKLine):
        """
        从虚拟结束K线恢复到确定结束K线
        """
        self.__is_sure = True
        self.update_new_end(new_klc=sure_end)
        self.__sure_end = []
        logger.info(f"[Bi] restore_from_virtual_end -->bi_list: {self}")

    def append_sure_end(self, klc: CKLine):
        """
        添加确定结束K线
        """
        self.__sure_end.append(klc)

    def update_new_end(self, new_klc: CKLine):
        """
        更新笔的结束K线
        """
        self.__end_klc = new_klc
        self.check()
        self.clean_cache()

    def cal_macd_metric(self, macd_algo, is_reverse):
        """
        Calculate the MACD metric based on the specified algorithm.

        @param macd_algo: The MACD algorithm to use.
        @param is_reverse: Boolean indicating if the calculation is in reverse.
        @return: The calculated MACD metric.
        @raises CChanException: If the MACD algorithm is unsupported.
        """
        if macd_algo == MACD_ALGO.AREA:
            return self.Cal_MACD_half(is_reverse)
        elif macd_algo == MACD_ALGO.PEAK:
            return self.Cal_MACD_peak()
        elif macd_algo == MACD_ALGO.FULL_AREA:
            return self.Cal_MACD_area()
        elif macd_algo == MACD_ALGO.DIFF:
            return self.Cal_MACD_diff()
        elif macd_algo == MACD_ALGO.SLOPE:
            return self.Cal_MACD_slope()
        elif macd_algo == MACD_ALGO.AMP:
            return self.Cal_MACD_amp()
        elif macd_algo == MACD_ALGO.AMOUNT:
            return self.Cal_MACD_trade_metric(DATA_FIELD.FIELD_TURNOVER, cal_avg=False)
        elif macd_algo == MACD_ALGO.VOLUMN:
            return self.Cal_MACD_trade_metric(DATA_FIELD.FIELD_VOLUME, cal_avg=False)
        elif macd_algo == MACD_ALGO.VOLUMN_AVG:
            return self.Cal_MACD_trade_metric(DATA_FIELD.FIELD_VOLUME, cal_avg=True)
        elif macd_algo == MACD_ALGO.AMOUNT_AVG:
            return self.Cal_MACD_trade_metric(DATA_FIELD.FIELD_TURNOVER, cal_avg=True)
        elif macd_algo == MACD_ALGO.TURNRATE_AVG:
            return self.Cal_MACD_trade_metric(DATA_FIELD.FIELD_TURNRATE, cal_avg=True)
        elif macd_algo == MACD_ALGO.RSI:
            return self.Cal_Rsi()
        else:
            raise CChanException(f"unsupport macd_algo={macd_algo}, should be one of area/full_area/peak/diff/slope/amp", ErrCode.PARA_ERROR)

    @make_cache
    def Cal_Rsi(self):
        rsi_lst: List[float] = []
        for klc in self.klc_lst:
            rsi_lst.extend(klu.rsi for klu in klc.lst)
        return 10000.0/(min(rsi_lst)+1e-7) if self.is_down() else max(rsi_lst)

    @make_cache
    def Cal_MACD_area(self):
        _s = 1e-7
        begin_klu = self.get_begin_klu()
        end_klu = self.get_end_klu()
        for klc in self.klc_lst:
            for klu in klc.lst:
                if klu.idx < begin_klu.idx or klu.idx > end_klu.idx:
                    continue
                if (self.is_down() and klu.macd.macd < 0) or (self.is_up() and klu.macd.macd > 0):
                    _s += abs(klu.macd.macd)
        return _s

    @make_cache
    def Cal_MACD_peak(self):
        peak = 1e-7
        for klc in self.klc_lst:
            for klu in klc.lst:
                if abs(klu.macd.macd) > peak:
                    if self.is_down() and klu.macd.macd < 0:
                        peak = abs(klu.macd.macd)
                    elif self.is_up() and klu.macd.macd > 0:
                        peak = abs(klu.macd.macd)
        return peak

    def Cal_MACD_half(self, is_reverse):
        if is_reverse:
            return self.Cal_MACD_half_reverse()
        else:
            return self.Cal_MACD_half_obverse()

    @make_cache
    def Cal_MACD_half_obverse(self):
        _s = 1e-7
        begin_klu = self.get_begin_klu()
        peak_macd = begin_klu.macd.macd
        for klc in self.klc_lst:
            for klu in klc.lst:
                if klu.idx < begin_klu.idx:
                    continue
                if klu.macd.macd*peak_macd > 0:
                    _s += abs(klu.macd.macd)
                else:
                    break
            else:  # 没有被break，继续找写一个KLC
                continue
            break
        return _s

    @make_cache
    def Cal_MACD_half_reverse(self):
        _s = 1e-7
        begin_klu = self.get_end_klu()
        peak_macd = begin_klu.macd.macd
        for klc in self.klc_lst_re:
            for klu in klc[::-1]:
                if klu.idx > begin_klu.idx:
                    continue
                if klu.macd.macd*peak_macd > 0:
                    _s += abs(klu.macd.macd)
                else:
                    break
            else:  # 没有被break，继续找写一个KLC
                continue
            break
        return _s

    @make_cache
    def Cal_MACD_diff(self):
        """
        macd红绿柱最大值最小值之差
        """
        _max, _min = float("-inf"), float("inf")
        for klc in self.klc_lst:
            for klu in klc.lst:
                macd = klu.macd.macd
                if macd > _max:
                    _max = macd
                if macd < _min:
                    _min = macd
        return _max-_min

    @make_cache
    def Cal_MACD_slope(self):
        begin_klu = self.get_begin_klu()
        end_klu = self.get_end_klu()
        if self.is_up():
            return (end_klu.high - begin_klu.low)/end_klu.high/(end_klu.idx - begin_klu.idx + 1)
        else:
            return (begin_klu.high - end_klu.low)/begin_klu.high/(end_klu.idx - begin_klu.idx + 1)

    @make_cache
    def Cal_MACD_amp(self):
        begin_klu = self.get_begin_klu()
        end_klu = self.get_end_klu()
        if self.is_down():
            return (begin_klu.high-end_klu.low)/begin_klu.high
        else:
            return (end_klu.high-begin_klu.low)/begin_klu.low

    def Cal_MACD_trade_metric(self, metric: str, cal_avg=False) -> float:
        _s = 0
        for klc in self.klc_lst:
            for klu in klc.lst:
                metric_res = klu.trade_info.metric[metric]
                if metric_res is None:
                    return 0.0
                _s += metric_res
        return _s / self.get_klu_cnt() if cal_avg else _s

    # def set_klc_lst(self, lst):
    #     self.__klc_lst = lst

    @staticmethod
    def Info(bi: 'CBi'):
        """
        Print all properties and their values in a CBi instance.

        @param bi: CBi instance to inspect.
        """
        result = "=== CBi Instance Properties ===\n"
        
        # Basic properties
        result += "\nBasic Properties:\n"
        result += f"- idx: {bi.idx}\n"
        result += f"- direction: {bi.dir}\n"
        result += f"- type: {bi.type}\n"
        result += f"- is_sure: {bi.is_sure}\n"
        result += f"- segment_idx: {bi.seg_idx}\n"
        
        # KLine properties
        result += "\nKLine Properties:\n"
        result += f"- begin_klc time: {bi.begin_klc[0].time}\n"
        result += f"- end_klc time: {bi.end_klc[-1].time}\n"
        result += f"- begin value: {bi.get_begin_val():.2f}\n"
        result += f"- end value: {bi.get_end_val():.2f}\n"
        result += f"- high: {bi._high():.2f}\n"
        result += f"- low: {bi._low():.2f}\n"
        result += f"- mid: {bi._mid():.2f}\n"
        
        # Calculated properties
        result += "\nCalculated Properties:\n"
        result += f"- amplitude: {bi.amp():.2f}\n"
        result += f"- KLine unit count: {bi.get_klu_cnt()}\n"
        result += f"- KLine combination count: {bi.get_klc_cnt()}\n"
        
        # References
        result += "\nReferences:\n"
        result += f"- has parent segment: {bi.parent_seg is not None}\n"
        result += f"- has buy/sell point: {bi.bsp is not None}\n"
        result += f"- has previous bi: {bi.pre is not None}\n"
        result += f"- has next bi: {bi.next is not None}\n"
        
        # Sure end points
        if len(bi.sure_end) > 0:
            result += "\nSure End Points:\n"
            for idx, end in enumerate(bi.sure_end):
                result += f"- point {idx}: time={end[0].time}\n"
            
        return result

    @staticmethod
    def InfoAsTable(bi: 'CBi', output_file: str = None):
        """
        Display Bi properties in a table format with columns.

        @param bi: CBi instance to display.
        @param output_file: Optional file path to write output to. If None, prints to console.
        """
        headers = [
            "Idx", "Dir", "Type", "Sure", "SegIdx", 
            "BeginTime", "EndTime", "BeginVal", "EndVal",
            "High", "Low", "Mid", "Amp", "KLU_Cnt", "KLC_Cnt",
            "HasParent", "HasBSP", "HasPrev", "HasNext"
        ]
        
        values = [
            str(bi.idx),
            str(bi.dir),
            str(bi.type),
            str(bi.is_sure),
            str(bi.seg_idx),
            bi.begin_klc[0].time,
            bi.end_klc[-1].time,
            f"{bi.get_begin_val():.2f}",
            f"{bi.get_end_val():.2f}",
            f"{bi._high():.2f}",
            f"{bi._low():.2f}", 
            f"{bi._mid():.2f}",
            f"{bi.amp():.2f}",
            str(bi.get_klu_cnt()),
            str(bi.get_klc_cnt()),
            str(bi.parent_seg is not None),
            str(bi.bsp is not None),
            str(bi.pre is not None),
            str(bi.next is not None)
        ]

        # Calculate column widths
        widths = [
            max(len(h), len(str(v)) if isinstance(v, CTime) else len(v))
            for h, v in zip(headers, values)
        ]
        
        # Create output lines
        header_line = " | ".join(h.ljust(w) for h, w in zip(headers, widths))
        separator = "-" * len(header_line)
        value_line = " | ".join(str(v).ljust(w) for v, w in zip(values, widths))
        
        # Output to file or console
        if output_file:
            with open(output_file, 'a') as f:
                f.write(header_line + '\n')
                f.write(separator + '\n') 
                f.write(value_line + '\n')
                f.write('\n\n')  # Add extra newline as divider between rows
        else:
            print(header_line)
            print(separator)
            print(value_line)