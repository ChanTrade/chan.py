# from typing import Generic, Iterable, List, Optional, Self, TypeVar, Union, overload
from typing import TypeVar, Generic, Iterable, List, Optional, Union, overload

Self = TypeVar('T', bound='CKLine_Combiner')

from Common.cache import make_cache
from Common.CEnum import FX_TYPE, KLINE_DIR
from Common.ChanException import CChanException, ErrCode
from KLine.KLine_Unit import CKLine_Unit

from .Combine_Item import CCombine_Item
from Common.func_util import logger
from Common.CTime import CTime
T = TypeVar('T')


# 合并后的K线类
class CKLine_Combiner(Generic[T]):
    def __init__(self, kl_unit: T, _dir):
        '''
        初始化合并后的K线类
        '''
        item = CCombine_Item(kl_unit)
        # 合并K线的开始时间
        self.__time_begin = item.time_begin
        # 合并K线的结束时间
        self.__time_end = item.time_end
        # 合并K线的最高价
        self.__high = item.high
        # 合并K线的最低价
        self.__low = item.low
        # 合并K线的单位K线列表
        self.__lst: List[T] = [kl_unit]  # 本级别每一根单位K线
        # 合并K线的方向
        self.__dir = _dir
        # 合并K线的类型
        self.__fx = FX_TYPE.UNKNOWN
        # 合并K线的上一个合并K线
        self.__pre: Optional[Self] = None
        # 合并K线的下一个合并K线
        self.__next: Optional[Self] = None

    def clean_cache(self):
        '''
        清除缓存
        '''
        self._memoize_cache = {}

    @property
    def time_begin(self): return self.__time_begin

    @property
    def time_end(self): return self.__time_end

    @property
    def high(self): return self.__high

    @property
    def low(self): return self.__low

    @property
    def lst(self): return self.__lst

    @property
    def dir(self): return self.__dir

    @property
    def fx(self): return self.__fx

    @property
    def pre(self) -> Self:
        assert self.__pre is not None
        return self.__pre

    @property
    def next(self): return self.__next

    def get_next(self) -> Self:
        assert self.next is not None
        return self.next

    def test_combine(self, item: CCombine_Item, exclude_included=False, allow_top_equal=None):
        '''
        检测合并K线
        !TODO: 需要优化， 需要考虑 使用CChan 的 Seg,Bi,SegSeg 进一步优化合并操作
        '''
        # 左侧包含关系
        if (self.high >= item.high and self.low <= item.low):
            # 如果合并K线的最高价大于等于单位K线的最高价，并且合并K线的最低价小于等于单位K线的最低价，则是 左侧包含关系
            logger.info("[Check Combine] Left-side inclusion: Combined K-line({},{}) includes Unit K-line({},{}), It's Combine".format(self.high, self.low, item.high, item.low))
            return KLINE_DIR.COMBINE
        # 右侧包含关系
        elif (self.high <= item.high and self.low >= item.low):
            # 如果合并K线的最高价小于等于单位K线的最高价，并且合并K线的最低价大于等于单位K线的最低价，则是 右侧包含关系
            if allow_top_equal == 1 and self.high == item.high and self.low > item.low:
                # 如果允许顶部相等，并且合并K线的最高价等于单位K线的最高价，并且合并K线的最低价大于单位K线的最低价，则返回 向下合并
                logger.info("[Check Combine] Right-side inclusion (equal tops): Unit K-line({},{}) includes Combined K-line({},{}), It's Down".format(item.high, item.low, self.high, self.low))
                return KLINE_DIR.DOWN
            elif allow_top_equal == -1 and self.low == item.low and self.high < item.high:
                # 如果允许底部相等，并且合并K线的最低价等于单位K线的最低价，并且合并K线的最高价小于单位K线的最高价，则返回 向上合并
                logger.info("[Check Combine] Right-side inclusion (equal bottoms): Unit K-line({},{}) includes Combined K-line({},{}), It's Up".format(item.high, item.low, self.high, self.low))
                return KLINE_DIR.UP
            # 如果 exclude_included 为 True，则返回 包含关系 否则返回合并
            result = KLINE_DIR.INCLUDED if exclude_included else KLINE_DIR.COMBINE
            logger.info("[Check Combine] Right-side inclusion: Unit K-line({},{}) includes Combined K-line({},{}), exclude_included={}, returning {}".format(item.high, item.low, self.high, self.low, exclude_included, result))
            return result
        elif (self.high > item.high and self.low > item.low):
            # 如果合并K线的最高价大于单位K线的最高价，并且合并K线的最低价大于单位K线的最低价，则返回 向下 非合并
            logger.info("[Check Combine] Down Trend: Combined K-line({},{}) high point higher than Unit K-line({},{}) and low point higher than Unit K-line, It's Down".format(self.high, self.low, item.high, item.low))
            return KLINE_DIR.DOWN
        elif (self.high < item.high and self.low < item.low):
            # 如果合并K线的最高价小于单位K线的最高价，并且合并K线的最低价小于单位K线的最低价，则返回 向上 非合并
            logger.info("[Check Combine] Up Trend: Combined K-line({},{}) high point lower than Unit K-line({},{}) and low point lower than Unit K-line, It's Up".format(self.high, self.low, item.high, item.low))
            return KLINE_DIR.UP
        else:
            # 如果合并K线的最高价和最低价都不大于或小于单位K线的最高价和最低价，则抛出异常
            raise CChanException("combine type unknown", ErrCode.COMBINER_ERR)

    # 添加单位K线
    def add(self, unit_kl: T):
        # only for deepcopy
        self.__lst.append(unit_kl)
    # 设置合并K线的类型
    def set_fx(self, fx: FX_TYPE):
        # only for deepcopy
        self.__fx = fx

    # K线合并算法
    def try_add(self, unit_kl: T, exclude_included=False, allow_top_equal=None):
        # allow_top_equal = None普通模式
        # allow_top_equal = 1 被包含，顶部相等不合并
        # allow_top_equal = -1 被包含，底部相等不合并
        combine_item = CCombine_Item(unit_kl)
        if isinstance(unit_kl, CKLine_Unit):    
            logger.info(f"[Try_Add_KLU Processing type: CKLine_Unit, time_begin={combine_item.time_begin}, time_end={combine_item.time_end}")
        else:
            logger.info(f"[Try_Add_Bi_Seg] Processing type: {type(unit_kl)}, time_begin={combine_item.time_begin}, time_end={combine_item.time_end}")

        # 检测 当前合并K和 unit_kl 的 合并关系
        _dir = self.test_combine(combine_item, exclude_included, allow_top_equal)
        if _dir == KLINE_DIR.COMBINE:
            # 如果 合并关系为 合并，则将 unit_kl 添加到 当前合并K的 lst 中
            self.__lst.append(unit_kl)
            # 如果 unit_kl 是 CKLine_Unit 类型，则将 unit_kl 的 klc 设置为 当前合并K
            if isinstance(unit_kl, CKLine_Unit):
                unit_kl.set_klc(self)
            # 如果 当前合并K的方向为 向上合并，则更新 当前合并K 的最高价和最低价
            if self.dir == KLINE_DIR.UP:
                # 非一字K线
                if combine_item.high != combine_item.low or combine_item.high != self.high:
                    # 如果 unit_kl 的最高价和最低价不相等，并且 unit_kl 的最高价大于当前合并K的最高价，则更新 当前合并K 的最高价
                    self.__high = max(combine_item.high, self.high)
                    # 如果 unit_kl 的最低价小于当前合并K的最低价，则更新 当前合并K 的最低价
                    self.__low = max(combine_item.low, self.low)
            # 如果 当前合并K的方向为 向下合并，则更新 当前合并K 的最高价和最低价
            elif self.dir == KLINE_DIR.DOWN:    
                # 非一字K线
                if combine_item.high != combine_item.low or combine_item.low != self.low:
                    # 如果 unit_kl 的最高价和最低价不相等，并且 unit_kl 的最低价小于当前合并K的最高价，则更新 当前合并K 的最高价
                    self.__high = min(combine_item.high, self.high)
                    # 如果 unit_kl 的最低价小于当前合并K的最低价，则更新 当前合并K 的最低价
                    self.__low = min(combine_item.low, self.low)
            else:
                raise CChanException(f"KLINE_DIR = {self.dir} err!!! must be {KLINE_DIR.UP}/{KLINE_DIR.DOWN}", ErrCode.COMBINER_ERR)
            # 更新 当前合并K 的结束时间
            self.__time_end = combine_item.time_end
            if isinstance(unit_kl, CKLine_Unit):
                logger.info(f"[Try_Add_KLU Combine Done - Updated time_end: {self.__time_end}")
            else:
                logger.info(f"[Try_Add_Bi_Seg] Combine Done - Updated time_end: {self.__time_end}")
            # 清除缓存
            self.clean_cache()
        # 返回UP/DOWN/COMBINE给KL_LIST，设置下一个的方向
        if isinstance(unit_kl, CKLine_Unit):
            logger.info(f"[Try_Add_KLU Try add result: {_dir} {combine_item.time_begin}~{combine_item.time_end}")
        else:
            logger.info(f"[Try_Add_Bi_Seg] Try add result: {_dir} {combine_item.time_begin}~{combine_item.time_end}")
        return _dir

    def get_peak_klu(self, is_high) -> T:
        # 获取最大值 or 最小值所在klu/bi
        return self.get_high_peak_klu() if is_high else self.get_low_peak_klu()

    @make_cache
    def get_high_peak_klu(self) -> T:
        for kl in self.lst[::-1]:
            if CCombine_Item(kl).high == self.high:
                return kl
        raise CChanException("can't find peak...", ErrCode.COMBINER_ERR)

    @make_cache
    def get_low_peak_klu(self) -> T:
        for kl in self.lst[::-1]:
            if CCombine_Item(kl).low == self.low:
                return kl
        raise CChanException("can't find peak...", ErrCode.COMBINER_ERR)

    # 分型处理算法
    def update_fx(self, _pre: Self, _next: Self, exclude_included=False, allow_top_equal=None):
        # allow_top_equal = None普通模式
        # allow_top_equal = 1 被包含，顶部相等不合并
        # allow_top_equal = -1 被包含，底部相等不合并
        # 设置下一个合并K线
        self.set_next(_next)
        # 设置上一个合并K线
        self.set_pre(_pre)
        # 设置下一个合并K线的上一个合并K线
        _next.set_pre(self)
        # 如果 exclude_included 为 True，则进行分型处理
        # Log the current K-line's datetime information for debugging
        if exclude_included:
            # 如果 上一个合并K线的最高价小于当前合并K线的最高价
            # 并且 下一个合并K线的最高价小于等于当前合并K线的最高价
            # 并且 下一个合并K线的最低价小于当前合并K线的最低价
            logger.info(f"[Update FX] FX Update: {_pre.time_begin}~{_pre.time_end} -> {self.time_begin}~{self.time_end} -> {_next.time_begin}~{_next.time_end}")
            logger.info(f"[Update FX] Pre: {_pre.low}->{_pre.high}, Current: {self.low}->{self.high}, Next: {_next.low}->{_next.high}")
            logger.info(f"[Update FX] Params: exclude_included={exclude_included}, allow_top_equal={allow_top_equal}")
            
            if _pre.high < self.high and _next.high <= self.high and _next.low < self.low:
                # 如果 allow_top_equal 为 1，则允许顶部相等，否则不允许
                logger.info(f"[Update FX] Exclude mode - TOP condition: Pre.high({_pre.high}) < Self.high({self.high}) and Next.high({_next.high}) <= Self.high({self.high}) and Next.low({_next.low}) < Self.low({self.low})")
                if allow_top_equal == 1 or _next.high < self.high:
                    logger.info(f"[Update FX] TOP confirmed: allow_top_equal={allow_top_equal} or Next.high({_next.high}) < Self.high({self.high})")
                    self.__fx = FX_TYPE.TOP
                else:
                    logger.info(f"[Update FX] TOP rejected: allow_top_equal={allow_top_equal} and Next.high({_next.high}) == Self.high({self.high})")
            # 如果 下一个合并K线的最高价大于当前合并K线的最高价，
            # 并且 上一个合并K线的最低价大于当前合并K线的最低价，
            # 并且 下一个合并K线的最低价大于等于当前合并K线的最低价
            elif _next.high > self.high and _pre.low > self.low and _next.low >= self.low:
                # 如果 allow_top_equal 为 -1，则允许底部相等，否则不允许
                logger.info(f"[Update FX] Exclude mode - BOTTOM condition: Next.high({_next.high}) > Self.high({self.high}) and Pre.low({_pre.low}) > Self.low({self.low}) and Next.low({_next.low}) >= Self.low({self.low})")
                if allow_top_equal == -1 or _next.low > self.low:
                    logger.info(f"[Update FX] BOTTOM confirmed: allow_top_equal={allow_top_equal} or Next.low({_next.low}) > Self.low({self.low})")
                    self.__fx = FX_TYPE.BOTTOM
                else:
                    logger.info(f"[Update FX] BOTTOM rejected: allow_top_equal={allow_top_equal} and Next.low({_next.low}) == Self.low({self.low})")
            else:
                logger.info(f"[Update FX] Exclude mode - No FX condition met")
        # 如果 上一个合并K线的最高价小于当前合并K线的最高价
        # 并且 下一个合并K线的最高价小于等于当前合并K线的最高价
        # 并且 下一个合并K线的最低价小于当前合并K线的最低价
        elif _pre.high < self.high and _next.high < self.high and _pre.low < self.low and _next.low < self.low:
            logger.info(f"[Update FX] Normal mode - TOP condition: {_pre.high < self.high and _next.high < self.high and _pre.low < self.low and _next.low < self.low}"
                            f"| Pre: {_pre.time_begin}~{_pre.time_end}, Self: {self.time_begin}~{self.time_end}, Next: {_next.time_begin}~{_next.time_end}")
            self.__fx = FX_TYPE.TOP
        # 如果 上一个合并K线的最高价大于当前合并K线的最高价
        # 并且 下一个合并K线的最高价大于等于当前合并K线的最高价
        # 并且 下一个合并K线的最低价大于当前合并K线的最低价
        elif _pre.high > self.high and _next.high > self.high and _pre.low > self.low and _next.low > self.low:
            logger.info(f"[Update FX] Normal mode - BOTTOM condition: {_pre.high > self.high and _next.high > self.high and _pre.low > self.low and _next.low > self.low}"
                              f"| Pre: {_pre.time_begin}~{_pre.time_end}, Self: {self.time_begin}~{self.time_end}, Next: {_next.time_begin}~{_next.time_end}")
            self.__fx = FX_TYPE.BOTTOM

        # Check if previous K-line is in a downtrend compared to current K-line
        # This is indicated by prev high < self high AND prev low < self low
        elif _pre.high < self.high and _pre.low < self.low and self.high < _next.high and self.low < _next.low:
            logger.info(f"[Update FX] Detected uptrend pattern: Pre({_pre.low}->{_pre.high}) -> Self({self.low}->{self.high}) -> Next({_next.low}->{_next.high})"
                              f" | Pre: {_pre.time_begin}~{_pre.time_end}, Self: {self.time_begin}~{self.time_end}, Next: {_next.time_begin}~{_next.time_end}")
            # This indicates an uptrend from previous to current, followed by downtrend to next K-line
            # Additional logic can be added here if needed for this pattern handling
        elif _pre.high > self.high and _pre.low > self.low and self.high > _next.high and self.low > _next.low:
            logger.info(f"[Update FX] Detected downtrend pattern: Pre({_pre.low}->{_pre.high}) -> Self({self.low}->{self.high}) -> Next({_next.low}->{_next.high})"
                              f"| Pre: {_pre.time_begin}~{_pre.time_end}, Self: {self.time_begin}~{self.time_end}, Next: {_next.time_begin}~{_next.time_end}")
            # This indicates a downtrend from previous to current, followed by uptrend to next K-line
            # Additional logic can be added here if needed for this pattern handling
        else:
            # Raise exception for unhandled cases
            # This ensures all possible conditions are explicitly handled
            logger.warning(f"[Update FX] Unhandled FX case detected with values: Pre({_pre.low}->{_pre.high}), Self({self.low}->{self.high}), Next({_next.low}->{_next.high})"
                                f"| Pre: {_pre.time_begin}~{_pre.time_end}, Self: {self.time_begin}~{self.time_end}, Next: {_next.time_begin}~{_next.time_end}")
            logger.warning(f"[Update FX] Conditions: exclude_included={exclude_included}, allow_top_equal={allow_top_equal}")
            # We don't raise an exception here as it would disrupt normal operation
            raise CChanException("Unhandled FX case detected", ErrCode.COMBINER_ERR)
            # Instead, we log a warning for debugging purposes
            
        # 清除缓存
        self.clean_cache()

    def __str__(self):
        return f"{self.time_begin}~{self.time_end} {self.low}->{self.high}"

    @overload
    def __getitem__(self, index: int) -> T: ...

    @overload
    def __getitem__(self, index: slice) -> List[T]: ...

    def __getitem__(self, index: Union[slice, int]) -> Union[List[T], T]:
        return self.lst[index]

    def __len__(self):
        return len(self.lst)

    def __iter__(self) -> Iterable[T]:
        yield from self.lst

    def set_pre(self, _pre: Self):
        self.__pre = _pre
        self.clean_cache()

    def set_next(self, _next: Self):
        self.__next = _next
        self.clean_cache()
