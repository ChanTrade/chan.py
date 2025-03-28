from typing import List, Optional, Union, overload

from Common.CEnum import FX_TYPE, KLINE_DIR
from KLine.KLine import CKLine

from .Bi import CBi
from .BiConfig import CBiConfig
from Common.func_util import logger

class CBiList:
    def __init__(self, bi_conf=CBiConfig()):
        self.bi_list: List[CBi] = []
        self.last_end = None  # 最后一笔的尾部
        self.config = bi_conf

        self.free_klc_lst = []  # 仅仅用作第一笔未画出来之前的缓存，为了获得更精准的结果而已，不加这块逻辑其实对后续计算没太大影响

    def __str__(self):
        return "\n".join([str(bi) for bi in self.bi_list])

    def __iter__(self):
        yield from self.bi_list

    @overload
    def __getitem__(self, index: int) -> CBi: ...

    @overload
    def __getitem__(self, index: slice) -> List[CBi]: ...

    def __getitem__(self, index: Union[slice, int]) -> Union[List[CBi], CBi]:
        return self.bi_list[index]

    def __len__(self):
        return len(self.bi_list)

    def try_create_first_bi(self, klc: CKLine) -> bool:
        # 尝试创建第一笔
        for exist_free_klc in self.free_klc_lst:
            # 如果存在自由K线，则判断是否可以生成笔
            if exist_free_klc.fx == klc.fx:
                continue
            # 如果可以生成笔，则添加新笔
            if self.can_make_bi(klc, exist_free_klc):
                logger.info(f"[Bi]### \nTry_Create first bi:\nstart={exist_free_klc.time_begin.to_str()},\nend={klc.time_begin.to_str()}, start_fx={exist_free_klc.fx}, end_fx={klc.fx}\n")
                self.add_new_bi(exist_free_klc, klc)
                self.last_end = klc
                return True
        # 如果不能生成笔，则将当前K线加入自由K线列表
        self.free_klc_lst.append(klc)
        self.last_end = klc
        return False

    def update_bi(self, klc: CKLine, last_klc: CKLine, cal_virtual: bool) -> bool:
        """
        klc: 倒数第二根klc (倒数第二根K线)
        last_klc: 倒数第1根klc (最新K线)
        cal_virtual: 是否计算虚拟笔
        更新笔
        """
        # 寻找确定结束的笔
        flag1 = self.update_bi_sure(klc)
        # 如果需要计算虚拟笔，则计算虚拟笔
        if cal_virtual:
            logger.info(f"[Bi] Try add virtual bi after update_bi_sure --->: {last_klc}") 
            flag2 = self.try_add_virtual_bi(last_klc)
            logger.info(f"[Bi] Try add virtual bi after update_bi_sure <---: {last_klc}, flag2: {flag2}")
            return flag1 or flag2
        else:
            return flag1

    # 判断是否可以更新笔的极值点
    def can_update_peak(self, klc: CKLine):
        if self.config.bi_allow_sub_peak or len(self.bi_list) < 2:
            logger.info(f"[Bi] u0 - Cannot update peak: bi_allow_sub_peak is enabled or not enough bi elements")
            return False
        if self.bi_list[-1].is_down() and klc.high < self.bi_list[-1].get_begin_val():
            logger.info(f"[Bi] u1 - Cannot update peak: down bi with klc.high({klc.high}) < begin_val({self.bi_list[-1].get_begin_val()})")
            return False
        if self.bi_list[-1].is_up() and klc.low > self.bi_list[-1].get_begin_val():
            logger.info(f"[Bi] u2 - Cannot update peak: up bi with klc.low({klc.low}) > begin_val({self.bi_list[-1].get_begin_val()})")
            return False
        if not end_is_peak(self.bi_list[-2].begin_klc, klc):
            logger.info(f"[Bi] u3 - Cannot update peak: end is not a peak between bi_list[-2].begin_klc and klc")
            return False
        if self[-1].is_down() and self[-1].get_end_val() < self[-2].get_begin_val():
            logger.info(f"[Bi] u4 - Cannot update peak: down bi with end_val({self[-1].get_end_val()}) < previous begin_val({self[-2].get_begin_val()})")    
            return False
        if self[-1].is_up() and self[-1].get_end_val() > self[-2].get_begin_val():
            logger.info(f"[Bi] u5 - Cannot update peak: up bi with end_val({self[-1].get_end_val()}) > previous begin_val({self[-2].get_begin_val()})")
            return False
        logger.info(f"[Bi] u6 - Can update peak: all conditions passed")
        return True

    # 更新笔的极值点
    def update_peak(self, klc: CKLine, for_virtual=False):
        logger.info(f"[Bi] update_peak --> : {klc}")
        # 判断是否可以更新笔的极值点
        if not self.can_update_peak(klc):
            logger.info(f"[Bi] update_peak <--: cannot update peak")
            return False
        assert len(self.bi_list) > 0
        # 删除最后一笔
        _tmp_last_bi = self.bi_list[-1]
        self.bi_list.pop()
        # 尝试更新笔的结束K线
        if not self.try_update_end(klc, for_virtual=for_virtual):
            # 如果不能更新笔的结束K线，则恢复最后一笔
            self.bi_list.append(_tmp_last_bi)
            logger.info(f"[Bi] update_peak <--: cannot update end")
            return False
        else:
            # 如果可以更新笔的结束K线，则添加确定结束K线
            if for_virtual:
                self.bi_list[-1].append_sure_end(_tmp_last_bi.end_klc)
            logger.info(f"[Bi] update_peak <--: update end success")
            return True

    # 更新笔的确定结束K线
    def update_bi_sure(self, klc: CKLine) -> bool:
        """
        klc: 倒数第二根klc (倒数第二根K线)
        """
        # 获取bi_list的最后一笔的结束K线索引, 这最后一笔可能是确定结束的笔，也可能是虚拟结束的笔
        _tmp_end = self.get_last_klu_of_last_bi()
        # 删除虚拟笔，更新 self.last_end 和 self[-1].next 属性
        self.delete_virtual_bi()
        logger.info(f"[Bi] update_bi_sure --->: {klc}, _tmp_end: {_tmp_end}")
        '''
        下面的if case顺序不能打乱，必须先处理 未知分型 的情况，否则会出错
        '''
        # 如果当前K线返回的fx为未知，在删除虚拟笔后，判断 之前最后一笔的结束K线 是否与 删除虚拟笔后的最后一笔的结束K线 相同
        if klc.fx == FX_TYPE.UNKNOWN:
            if len(self.bi_list) > 0:
                logger.info(f"[Bi] u0- fx is unknown, it has new peak: {self[-1].get_end_val()}, last_end: {self.last_end}")
            return _tmp_end != self.get_last_klu_of_last_bi()  # 虚笔是否有变
        if self.last_end is None or len(self.bi_list) == 0:
            # 如果最后一笔的结束K线为None，或者笔列表为空，则尝试创建第一笔
            logger.info(f"[Bi] u1 - Try create first bi: {klc}")
            return self.try_create_first_bi(klc)
        if klc.fx == self.last_end.fx:
            # 如果当前K线的分型类型与最后一笔的结束K线的分型类型相同，则尝试更新最后一笔的结束K线
            logger.info(f"[Bi] u2 - Try update end: {klc}")
            return self.try_update_end(klc)
        elif self.can_make_bi(klc, self.last_end):
            # 如果可以生成笔，则添加新笔
            logger.info(f"[Bi] u3 - It's a new bi: {klc}")
            self.add_new_bi(self.last_end, klc)
            self.last_end = klc
            logger.info(f"[Bi] u4 - Add New bi: {self[-1]} , last_end: {self.last_end}")
            return True
        elif self.update_peak(klc):
            # 如果可以更新笔的 极值点，则返回True
            logger.info(f"[Bi] u5 - Updated peak done: {self[-1]} , peak: {self[-1].get_end_val()}")
            return True
        logger.info(f"[Bi] u6 - check _tmp_end != self.get_last_klu_of_last_bi(): {_tmp_end != self.get_last_klu_of_last_bi()}")
        return _tmp_end != self.get_last_klu_of_last_bi()

    def delete_virtual_bi(self):
        """
        删除虚拟笔，更新 self.last_end 和 self[-1].next 属性
        """
        # 如果笔列表不为空，且最后一笔为未确定笔
        if len(self) > 0 and not self.bi_list[-1].is_sure:
            # 获取最后一笔的确定结束K线列表
            sure_end_list = [klc for klc in self.bi_list[-1].sure_end]
            if len(sure_end_list):
                # 恢复最后一笔的确定结束K线
                self.bi_list[-1].restore_from_virtual_end(sure_end_list[0])
                # 更新最后一笔的结束K线
                self.last_end = self[-1].end_klc
                # 添加新的确定结束K线
                for sure_end in sure_end_list[1:]:
                    # 为什么要添加新的笔？
                    self.add_new_bi(self.last_end, sure_end, is_sure=True)
                    # 更新最后一笔的结束K线 为 bi_list[-1].end_klc
                    self.last_end = self[-1].end_klc
            else:
                # 删除最后一笔
                del self.bi_list[-1]
            # 更新最后一笔的结束K线
            self.last_end = self[-1].end_klc if len(self) > 0 else None

        # 如果还有笔，则更新最后一笔的下一个笔为None - 未完成的笔
        if len(self) > 0:
            self[-1].next = None

    def try_add_virtual_bi(self, klc: CKLine, need_del_end=False):
        """
        @param klc: 当前Klc
        @param need_del_end: 是否需要删除最后一笔
        """
        logger.info(f"[Bi] try_add_virtual_bi --->: {klc}, need_del_end: {need_del_end}")
        if need_del_end:
            self.delete_virtual_bi()
        if len(self) == 0:
            # 当前没有确定的笔，没必要添加虚拟笔
            logger.info(f"[Bi] u0 - Try add virtual bi failed: {klc}")
            return False
        if klc.idx == self[-1].end_klc.idx:
            # 当前Klc与最后一笔的结束K线相同，没必要添加虚拟笔
            logger.info(f"[Bi] u1 - Try add virtual bi failed: {klc}")
            return False
        if (self[-1].is_up() and klc.high >= self[-1].end_klc.high) or \
            (self[-1].is_down() and klc.low <= self[-1].end_klc.low):
            # 如果最后一笔是向上的笔，并且当前Klc的high大于等于最后一笔的结束K线的high，
            # 或者最后一笔是向下的笔，并且当前Klc的low小于等于最后一笔的结束K线的low，
            # 则根据 klc 更新 最后一笔的 属性 包括
            # 1. 添加 虚拟结束K线 到 sure_end 列表
            # 2. 更新 确定结束K线
            # 3. 设置 是否确定笔 为 False
            self.bi_list[-1].update_virtual_end(klc)
            logger.info(f"[Bi] u2 - Try update end of virtual bi success: {klc}")
            return True
        # 保存临时 klc
        _tmp_klc = klc
        while _tmp_klc and _tmp_klc.idx > self[-1].end_klc.idx:
            assert _tmp_klc is not None
            if self.can_make_bi(_tmp_klc, self[-1].end_klc, for_virtual=True):
                # 新增一笔
                self.add_new_bi(self.last_end, _tmp_klc, is_sure=False)
                logger.info(f"[Bi] u3 - <<<Try add new bi success>>>: {self[-1]}")
                return True
            elif self.update_peak(_tmp_klc, for_virtual=True):
                logger.info(f"[Bi] u4 - Try update peak of virtual bi success: {self[-1]}")
                return True
            # 继续遍历前一笔
            _tmp_klc = _tmp_klc.pre
        logger.info(f"[Bi] u5 - Try add virtual bi failed: {klc}")
        return False

    # 添加新笔， 主要是操作 bi_list 的 next 和 pre 属性
    def add_new_bi(self, pre_klc, cur_klc, is_sure=True):
        # 添加新笔
        self.bi_list.append(CBi(pre_klc, cur_klc, idx=len(self.bi_list), is_sure=is_sure))
        # 如果笔列表长度大于等于2，则设置前一笔的下一个笔为当前笔，当前笔的前一笔为前前笔
        if len(self.bi_list) >= 2:
            self.bi_list[-2].next = self.bi_list[-1]
            self.bi_list[-1].pre = self.bi_list[-2]

    def satisfy_bi_span(self, klc: CKLine, last_end: CKLine):
        # 判断是否满足笔的跨度
        bi_span = self.get_klc_span(klc, last_end)
        if self.config.is_strict:
            return bi_span >= 4
        uint_kl_cnt = 0
        tmp_klc = last_end.next
        while tmp_klc:
            uint_kl_cnt += len(tmp_klc.lst)
            if not tmp_klc.next:  # 最后尾部虚笔的时候，可能klc.idx == last_end.idx+1
                return False
            if tmp_klc.next.idx < klc.idx:
                tmp_klc = tmp_klc.next
            else:
                break
        return bi_span >= 3 and uint_kl_cnt >= 3

    def get_klc_span(self, klc: CKLine, last_end: CKLine) -> int:
        # 获取笔的跨度
        span = klc.idx - last_end.idx
        if not self.config.gap_as_kl:
            return span
        if span >= 4:  # 加速运算，如果span需要真正精确的值，需要去掉这一行
            return span
        tmp_klc = last_end
        while tmp_klc and tmp_klc.idx < klc.idx:
            if tmp_klc.has_gap_with_next():
                span += 1
            tmp_klc = tmp_klc.next
        return span

    def can_make_bi(self, klc: CKLine, last_end: CKLine, for_virtual: bool = False):
        '''
        判断是否可以生成笔
        1. 判断是否满足笔的跨度
        2. 判断是否满足笔的顶点
        3. 判断是否满足笔的结束
        '''
        logger.info(f"[Bi] can_make_bi: {klc}, {last_end}, for_virtual: {for_virtual}")
        # 判断是否满足笔的跨度
        satisify_span = True if self.config.bi_algo == 'fx' else self.satisfy_bi_span(klc, last_end)
        if not satisify_span:   
            return False
        # 判断是否满足笔的顶点
        if not last_end.check_fx_valid(klc, self.config.bi_fx_check, for_virtual):
            logger.info(f"[Bi] can_make_bi: False, not last_end.check_fx_valid")
            return False
        # 判断是否满足笔的结束
        if self.config.bi_end_is_peak and not end_is_peak(last_end, klc):
            logger.info(f"[Bi] can_make_bi: False, not end_is_peak")
            return False
        logger.info(f"[Bi] can_make_bi: True")
        return True

    def try_update_end(self, klc: CKLine, for_virtual=False) -> bool:
        def check_top(klc: CKLine, for_virtual):
            if for_virtual:
                return klc.dir == KLINE_DIR.UP
            else:
                return klc.fx == FX_TYPE.TOP

        def check_bottom(klc: CKLine, for_virtual):
            if for_virtual:
                return klc.dir == KLINE_DIR.DOWN
            else:
                return klc.fx == FX_TYPE.BOTTOM

        if len(self.bi_list) == 0:
            return False
        last_bi = self.bi_list[-1]
        if (last_bi.is_up() and check_top(klc, for_virtual) and klc.high >= last_bi.get_end_val()) or \
           (last_bi.is_down() and check_bottom(klc, for_virtual) and klc.low <= last_bi.get_end_val()):
            last_bi.update_virtual_end(klc) if for_virtual else last_bi.update_new_end(klc)
            self.last_end = klc
            logger.info(f"Updated {'virtual' if for_virtual else 'new'} end of bi: {last_bi}, new end: {klc}")
            return True
        else:
            logger.info(f"keep end of bi: {last_bi}, candidate: {klc}, for_virtual: {for_virtual}")
            return False

    def get_last_klu_of_last_bi(self) -> Optional[int]:
        """
        如果 bi_list 不为空，则返回 bi_list 的最后一笔的结束K线索引，否则返回 None
        """
        return self.bi_list[-1].get_end_klu().idx if len(self) > 0 else None


def end_is_peak(last_end: CKLine, cur_end: CKLine) -> bool:
    # 判断last_end是否是cur_end的顶点
    if last_end.fx == FX_TYPE.BOTTOM:
        # 如果last_end是底部，则判断cur_end的顶部是否大于last_end的顶部
        cmp_thred = cur_end.high  # 或者严格点选择get_klu_max_high()
        klc = last_end.get_next()
        # 遍历last_end的下一个K线，直到找到cur_end
        while True:
            # 如果找到cur_end，则返回True
            if klc.idx >= cur_end.idx:
                return True
            # 如果cur_end的顶部大于cmp_thred，则返回False
            if klc.high > cmp_thred:
                return False
            # 继续遍历下一个K线
            klc = klc.get_next()
    elif last_end.fx == FX_TYPE.TOP:
        # 如果last_end是顶部，则判断cur_end的底部是否小于last_end的底部
        cmp_thred = cur_end.low  # 或者严格点选择get_klu_min_low()
        klc = last_end.get_next()
        # 遍历last_end的下一个K线，直到找到cur_end
        while True:
            # 如果找到cur_end，则返回True
            if klc.idx >= cur_end.idx:
                return True
            # 如果cur_end的底部小于cmp_thred，则返回False
            if klc.low < cmp_thred:
                return False
            # 继续遍历下一个K线
            klc = klc.get_next()
    return True
