import abc
from typing import Generic, List, TypeVar, Union, overload

from Bi.Bi import CBi
from Bi.BiList import CBiList
from Common.CEnum import BI_DIR, LEFT_SEG_METHOD, SEG_TYPE
from Common.ChanException import CChanException, ErrCode

from .Seg import CSeg
from .SegConfig import CSegConfig
from Common.func_util import logger
from Common.CEnum import LineStatus
SUB_LINE_TYPE = TypeVar('SUB_LINE_TYPE', CBi, "CSeg")


class CSegListComm(Generic[SUB_LINE_TYPE]):
    def __init__(self, seg_config=CSegConfig(), lv=SEG_TYPE.BI):
        self.lst: List[CSeg[SUB_LINE_TYPE]] = []
        self.lv = lv
        self.do_init()
        self.config = seg_config

    def do_init(self):
        self.lst = []

    def __iter__(self):
        yield from self.lst

    @overload
    def __getitem__(self, index: int) -> CSeg[SUB_LINE_TYPE]: ...

    @overload
    def __getitem__(self, index: slice) -> List[CSeg[SUB_LINE_TYPE]]: ...

    def __getitem__(self, index: Union[slice, int]) -> Union[List[CSeg[SUB_LINE_TYPE]], CSeg[SUB_LINE_TYPE]]:
        return self.lst[index]

    def __len__(self):
        return len(self.lst)

    def left_bi_break(self, bi_lst: CBiList):
        # 最后一个确定线段之后的笔有突破该线段最后一笔的
        if len(self) == 0:
            return False
        last_seg_end_bi = self[-1].end_bi
        for bi in bi_lst[last_seg_end_bi.idx+1:]:
            if last_seg_end_bi.is_up() and bi._high() > last_seg_end_bi._high():
                return True
            elif last_seg_end_bi.is_down() and bi._low() < last_seg_end_bi._low():
                return True
        return False

    def collect_first_seg(self, bi_lst: CBiList):
        if len(bi_lst) < 3:
            return
        logger.info(f"[SegListComm] <<<collect_first_seg>>> --->: bi_lst_len={len(bi_lst)}")
        if self.config.left_method == LEFT_SEG_METHOD.PEAK:
            logger.info(f"[SegListComm] LeftSegMethod: {self.config.left_method}")
            # 找到笔列表的峰值笔
            _high = max(bi._high() for bi in bi_lst)
            _low = min(bi._low() for bi in bi_lst)
            # 如果 所有笔的最高值 和 第一笔 的开始 差值 大于等于 所有笔的最低值 和 第一笔 的开始 差值
            if abs(_high-bi_lst[0].get_begin_val()) >= abs(_low-bi_lst[0].get_begin_val()):
                logger.info(f"[SegListComm]  Up-Seg high-low: {_high-_low:.2f}, high-begin: {_high-bi_lst[0].get_begin_val():.2f}, low-begin: {_low-bi_lst[0].get_begin_val():.2f}")
                peak_bi = FindPeakBi(bi_lst, is_high=True)
                assert peak_bi is not None  
                if peak_bi.idx > 0:
                    self.add_new_seg(bi_lst, peak_bi.idx, is_sure=False, seg_dir=BI_DIR.UP, split_first_seg=False, reason="0seg_find_high")
                    logger.info(f"[SegListComm] <<<collect_first_seg>>> <---: Up-Seg")
                else:
                    logger.info(f"[SegListComm] <<<collect_first_seg>>> <---: Up-Seg, peak_bi.idx={peak_bi.idx} is 0")
            else:
                logger.info(f"[SegListComm]  Dwn-Seg high-low: {_high-_low:.2f}, high-begin: {_high-bi_lst[0].get_begin_val():.2f}, low-begin: {_low-bi_lst[0].get_begin_val():.2f}")
                peak_bi = FindPeakBi(bi_lst, is_high=False)
                assert peak_bi is not None
                if peak_bi.idx > 0:
                    self.add_new_seg(bi_lst, peak_bi.idx, is_sure=False, seg_dir=BI_DIR.DOWN, split_first_seg=False, reason="0seg_find_low")
                    logger.info(f"[SegListComm] <<<collect_first_seg>>> <---: Dwn-Seg")
                else:
                    logger.info(f"[SegListComm] <<<collect_first_seg>>> <---: Dwn-Seg, peak_bi.idx={peak_bi.idx} is 0")

            logger.info(f"[SegListComm] collect_left_as_seg_in_collect_first_seg --->:")
            self.collect_left_as_seg(bi_lst)
            logger.info(f"[SegListComm] collect_left_as_seg_in_collect_first_seg <---:")
            logger.info(f"[SegListComm] <<<collect_first_seg>>> <---: LeftSegMethod: {self.config.left_method}")
        elif self.config.left_method == LEFT_SEG_METHOD.ALL:
            logger.info(f"[SegListComm] LeftSegMethod: {self.config.left_method}")
            _dir = BI_DIR.UP if bi_lst[-1].get_end_val() >= bi_lst[0].get_begin_val() else BI_DIR.DOWN
            self.add_new_seg(bi_lst, bi_lst[-1].idx, is_sure=False, seg_dir=_dir, split_first_seg=False, reason="0seg_collect_all")
            logger.info(f"[SegListComm] <<<collect_first_seg>>> <---: All Seg Method, {_dir}-Seg")
        else:
            raise CChanException(f"unknown seg left_method = {self.config.left_method}", ErrCode.PARA_ERROR)

    def collect_left_seg_peak_method(self, last_seg_end_bi, bi_lst):
        if last_seg_end_bi.is_down():
            peak_bi = FindPeakBi(bi_lst[last_seg_end_bi.idx+3:], is_high=True)
            if peak_bi and peak_bi.idx - last_seg_end_bi.idx >= 3:
                self.add_new_seg(bi_lst, peak_bi.idx, is_sure=False, seg_dir=BI_DIR.UP, reason="collectleft_find_high")
        else:
            peak_bi = FindPeakBi(bi_lst[last_seg_end_bi.idx+3:], is_high=False)
            if peak_bi and peak_bi.idx - last_seg_end_bi.idx >= 3:
                self.add_new_seg(bi_lst, peak_bi.idx, is_sure=False, seg_dir=BI_DIR.DOWN, reason="collectleft_find_low")
        last_seg_end_bi = self[-1].end_bi

        logger.info(f"[SegListComm] collect_left_seg_peak_method in collect_left_seg_peak_method --->:")
        self.collect_left_as_seg(bi_lst)
        logger.info(f"[SegListComm] collect_left_seg_peak_method <---:")

    def collect_segs(self, bi_lst):
        logger.info(f"[SegListComm] collect_segs --->: bi_lst_len={len(bi_lst)}")
        last_bi = bi_lst[-1]
        last_seg_end_bi = self[-1].end_bi
        if last_bi.idx-last_seg_end_bi.idx < 3:
            logger.info(f"[SegListComm] collect_segs <---: bi_lst_len={len(bi_lst)}, last_bi.idx-last_seg_end_bi.idx={last_bi.idx-last_seg_end_bi.idx}")
            return
        if last_seg_end_bi.is_down() and last_bi.get_end_val() <= last_seg_end_bi.get_end_val():
            if peak_bi := FindPeakBi(bi_lst[last_seg_end_bi.idx+3:], is_high=True):
                self.add_new_seg(bi_lst, peak_bi.idx, is_sure=False, seg_dir=BI_DIR.UP, reason="collectleft_find_high_force")
                self.collect_left_seg(bi_lst)
            else:
                logger.info(f"[SegListComm] collect_segs <---: bi_lst_len={len(bi_lst)}, last_seg_end_bi.is_down() and last_bi.get_end_val() <= last_seg_end_bi.get_end_val() failed")
        elif last_seg_end_bi.is_up() and last_bi.get_end_val() >= last_seg_end_bi.get_end_val():
            if peak_bi := FindPeakBi(bi_lst[last_seg_end_bi.idx+3:], is_high=False):
                self.add_new_seg(bi_lst, peak_bi.idx, is_sure=False, seg_dir=BI_DIR.DOWN, reason="collectleft_find_low_force")
                self.collect_left_seg(bi_lst)
            else:
                logger.info(f"[SegListComm] collect_segs <---: bi_lst_len={len(bi_lst)}, last_seg_end_bi.is_up() and last_bi.get_end_val() >= last_seg_end_bi.get_end_val() failed")
        # 剩下线段的尾部相比于最后一个线段的尾部，高低关系和最后一个虚线段的方向一致
        elif self.config.left_method == LEFT_SEG_METHOD.ALL:
            # 容易找不到二类买卖点！！
            logger.info(f"[SegListComm] collect_segs in collect_segs --->:")    
            self.collect_left_as_seg(bi_lst)
            logger.info(f"[SegListComm] collect_segs in collect_segs <---:")
        elif self.config.left_method == LEFT_SEG_METHOD.PEAK:
            self.collect_left_seg_peak_method(last_seg_end_bi, bi_lst)
        else:
            raise CChanException(f"unknown seg left_method = {self.config.left_method}", ErrCode.PARA_ERROR)
        logger.info(f"[SegListComm] collect_segs <---: seg_cnt={len(self.lst)}")

    def collect_left_seg(self, bi_lst: CBiList):
        logger.info(f"[SegListComm] collect_left_seg --->: bi_lst_len={len(bi_lst)}")
        if len(self) == 0:
            self.collect_first_seg(bi_lst)
        else:
            self.collect_segs(bi_lst)
        logger.info(f"[SegListComm] collect_left_seg <---: seg_cnt={len(self.lst)}")

    def collect_left_as_seg(self, bi_lst: CBiList):
        """
        将剩下的笔列表中的笔 当作线段
        """
        last_bi = bi_lst[-1]
        last_seg_end_bi = self[-1].end_bi if len(self) > 0 else bi_lst[-1]
        logger.info(f"[SegListComm] collect_left_as_seg --->: last_seg_end_bi.idx+1:{last_seg_end_bi.idx+1} vs len(bi_lst)={len(bi_lst)}")
        if last_seg_end_bi.idx+1 >= len(bi_lst):
            # 最后一笔的索引+1 大于等于 笔列表的长度
            # 说明最后一笔是笔列表的最后一笔
            # 不需要将 笔列表中的笔 当作线段
            if len(self) == 0:
                self.add_new_seg(bi_lst, last_bi.idx, is_sure=False, reason="add_bi_to_last_seg")
                logger.info(f"[SegListComm] collect_left_as_seg <---: last_seg_end_bi.idx+1 >= len(bi_lst), global first_set:add_bi_to_last_seg")
            else:
                logger.info(f"[SegListComm] collect_left_as_seg <---: last_seg_end_bi.idx+1 >= len(bi_lst), no need to add_bi_to_last_seg")
            return
        if last_seg_end_bi.dir == last_bi.dir:
            # 笔列表的最后一笔，和最后一个线段的最后一个笔，方向一致，则
            # 从最后一笔的前一笔 添加新线段
            logger.info(f"[SegListComm] collect_left_as_seg --->: last_seg_end_bi.dir == last_bi.dir add_new_seg start from #{last_bi.idx-1} reason: collect_left_1")
            self.add_new_seg(bi_lst, last_bi.idx-1, is_sure=False, reason="collect_left_same_dir")
        else:
            # 笔列表的最后一笔，和最后一个线段的最后一个笔，方向不一致，则
            # 从最后一笔 添加新线段
            logger.info(f"[SegListComm] collect_left_as_seg --->: last_seg_end_bi.dir != last_bi.dir add_new_seg start from #{last_bi.idx} reason: collect_left_0")
            self.add_new_seg(bi_lst, last_bi.idx, is_sure=False, reason="collect_left_diff_dir")
        logger.info(f"[SegListComm] collect_left_as_seg <---:")
        return

    def try_add_new_seg(self, bi_lst, end_bi_idx: int, is_sure=True, seg_dir=None, split_first_seg=True, reason="normal"):
        logger.info(f"[SegListComm] try_add_new_seg --->: end_bi_idx: {end_bi_idx}, is_sure: {is_sure}, seg_dir: {seg_dir}, split_first_seg: {split_first_seg}, reason: {reason}")
        # 如果线段列表为空，并且需要分割第一个线段，并且最后一个笔的索引大于等于3
        if len(self) == 0 and split_first_seg and end_bi_idx >= 3:
            # 如果最后一个笔是向下笔，并且找到的峰值笔是向下笔，并且峰值笔的索引是0，并且峰值笔的值小于等于第一笔的值
            if peak_bi := FindPeakBi(bi_lst[end_bi_idx-3::-1], bi_lst[end_bi_idx].is_down()):
                if (peak_bi.is_down() and (peak_bi._low() < bi_lst[0]._low() or peak_bi.idx == 0)) or \
                   (peak_bi.is_up() and (peak_bi._high() > bi_lst[0]._high() or peak_bi.idx == 0)):  
                    # 要比第一笔开头还高/低（因为没有比较到）
                    # 生成新线段
                    logger.info(f"[SegListComm] try_add_new_seg --->: split_first_seg is True and end_bi_idx >= 3 and peak_bi is a peak")
                    self.add_new_seg(bi_lst, peak_bi.idx, is_sure=False, seg_dir=peak_bi.dir, reason="split_first_1st")
                    self.add_new_seg(bi_lst, end_bi_idx, is_sure=False, reason="split_first_2nd")
                    logger.info(f"[SegListComm] split_first new_seg <---: last_seg: {self.lst[-1]}")
                    return
                else:
                    logger.info(f"[SegListComm] try_add_new_seg <---: peak_bi is not None but peak_bi is not a peak")
            else:
                logger.info(f"[SegListComm] try_add_new_seg <---: peak_bi is None")
        else:
            logger.info(f"[SegListComm] try_add_new_seg <---: not empty seg list and split_first_seg is False and end_bi_idx < 3")

        # 生成新线段
        bi1_idx = 0 if len(self) == 0 else self[-1].end_bi.idx+1
        logger.warn(f"[SegListComm] <<<generate_new_seg>>> --->: bi1_idx: {bi1_idx}, bi2_idx: {end_bi_idx}, cur_seg_cnt: {len(self)}")
        bi1 = bi_lst[bi1_idx]
        bi2 = bi_lst[end_bi_idx]
        logger.warn(f"[SegListComm] generate_new_seg --->: \nbi1: {bi1}, \nbi2: {bi2}")
        new_seg = CSeg(len(self.lst), bi1, bi2, status=LineStatus.NewGenerated, is_sure=is_sure, seg_dir=seg_dir, reason=reason)
        self.lst.append(new_seg)
        logger.warn(f"[SegListComm] <<<generate_new_seg>>> <---: cur_seg_cnt: {len(self)}")

        if len(self.lst) >= 2:
            self.lst[-2].next = self.lst[-1]
            self.lst[-1].pre = self.lst[-2]
        # 更新线段的bi列表
        self.lst[-1].update_bi_list(bi_lst, bi1_idx, end_bi_idx)
        logger.info(f"[SegListComm] try_add_new_seg <---: last_seg: {self.lst[-1]}")
        return

    def add_new_seg(self, bi_lst: CBiList, end_bi_idx: int, is_sure=True, seg_dir=None, split_first_seg=True, reason="normal"):
        logger.info(f"[SegListComm] add_new_seg --->: end_bi_idx: {end_bi_idx}, is_sure: {is_sure}, seg_dir: {seg_dir}, split_first_seg: {split_first_seg}, reason: {reason}")
        try:
            self.try_add_new_seg(bi_lst, end_bi_idx, is_sure, seg_dir, split_first_seg, reason)
        except CChanException as e:
            if e.errcode == ErrCode.SEG_END_VALUE_ERR and len(self.lst) == 0:
                logger.info(f"[SegListComm] add_new_seg <--- False: last_seg: {self.lst[-1]}")
                return False
            raise e
        except Exception as e:
            raise e
        logger.info(f"[SegListComm] add_new_seg <--- True: last_seg: {self.lst[-1]}")
        return True

    @abc.abstractmethod
    def update(self, bi_lst: CBiList):
        ...

    def exist_sure_seg(self):
        return any(seg.is_sure for seg in self.lst)


def FindPeakBi(bi_lst: Union[CBiList, List[CBi]], is_high):
    # 找到笔列表的峰值笔
    logger.info(f"[SegListComm] FindPeakBi --->: is_high: {is_high}")
    peak_val = float("-inf") if is_high else float("inf")
    peak_bi = None
    for bi in bi_lst:
        if (is_high and bi.get_end_val() >= peak_val and bi.is_up()) or (not is_high and bi.get_end_val() <= peak_val and bi.is_down()):
            if bi.pre and bi.pre.pre and ((is_high and bi.pre.pre.get_end_val() > bi.get_end_val()) or (not is_high and bi.pre.pre.get_end_val() < bi.get_end_val())):
                continue
            peak_val = bi.get_end_val()
            peak_bi = bi
    logger.info(f"[SegListComm] FindPeakBi <---: peak_bi: {peak_bi}")
    return peak_bi
