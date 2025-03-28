from typing import List, Optional

from Bi.Bi import CBi
from Bi.BiList import CBiList
from Common.CEnum import BI_DIR, FX_TYPE, KLINE_DIR, SEG_TYPE
from Common.ChanException import CChanException, ErrCode
from Common.func_util import revert_bi_dir, logger

from .Eigen import CEigen


class CEigenFX:
    def __init__(self, _dir: BI_DIR, exclude_included=True, lv=SEG_TYPE.BI):
        self.lv = lv
        self.dir = _dir  # 线段方向
        self.ele: List[Optional[CEigen]] = [None, None, None]
        self.lst: List[CBi] = []
        self.exclude_included = exclude_included
        self.kl_dir = KLINE_DIR.UP if _dir == BI_DIR.UP else KLINE_DIR.DOWN
        self.last_evidence_bi: Optional[CBi] = None
        self.which_ele = -1

    def treat_first_ele(self, bi: CBi) -> bool:
        logger.info(f"[EigenFX] treat_first_ele --->: which_ele: {self.which_ele}\n{bi}")
        self.ele[0] = CEigen(bi, self.kl_dir)
        self.which_ele = 0
        logger.info(f"[EigenFX] treat_first_ele <---: which_ele: {self.which_ele}\n{bi}")
        return False

    def treat_second_ele(self, bi: CBi) -> bool:
        assert self.ele[0] is not None
        logger.info(f"[EigenFX] treat_second_ele --->: which_ele: {self.which_ele}\n{bi}")
        # 处理特征序列分型是否需要合并
        combine_dir = self.ele[0].try_add(bi, exclude_included=self.exclude_included)
        if combine_dir != KLINE_DIR.COMBINE:  # 不能合并
            # 用第二条同向笔，创建新的特征序列分型
            self.ele[1] = CEigen(bi, self.kl_dir)
            self.which_ele = 1
            if (self.is_up() and self.ele[1].high < self.ele[0].high) or \
               (self.is_down() and self.ele[1].low > self.ele[0].low):  # 前两元素不可能成为分形
                return self.reset()
        logger.info(f"[EigenFX] treat_second_ele <---: which_ele: {self.which_ele}\n{bi}")
        return False

    def treat_third_ele(self, bi: CBi) -> bool:
        assert self.ele[0] is not None
        assert self.ele[1] is not None
        logger.info(f"[EigenFX] treat_third_ele --->: which_ele: {self.which_ele}\n{bi}")
        self.last_evidence_bi = bi
        allow_top_equal = (1 if bi.is_down() else -1) if self.exclude_included else None
        combine_dir = self.ele[1].try_add(bi, allow_top_equal=allow_top_equal)
        if combine_dir == KLINE_DIR.COMBINE:
            logger.info(f"[EigenFX] treat_third_ele combine_dir == KLINE_DIR.COMBINE <---: which_ele: {self.which_ele}\n{bi}")
            return False
        self.ele[2] = CEigen(bi, combine_dir)
        self.which_ele = 2
        if not self.actual_break():
            return self.reset()
        self.ele[1].update_fx(self.ele[0], self.ele[2], exclude_included=self.exclude_included, allow_top_equal=allow_top_equal)  # type: ignore
        fx = self.ele[1].fx
        is_fx = (self.is_up() and fx == FX_TYPE.TOP) or (self.is_down() and fx == FX_TYPE.BOTTOM)

        if is_fx:
            logger.info(f"[EigenFX] treat_third_ele <---: which_ele: {self.which_ele}\n{bi}, is_fx: {is_fx}")
            return True
        else:
            self.reset()
            return False

    def add(self, bi: CBi) -> bool:  # 返回是否出现分形
        assert bi.dir != self.dir
        ret = False
        self.lst.append(bi)
        logger.info(f"[EigenFX] dir: {self.dir} , which_ele: {self.which_ele} add --->: {bi}")
        if self.ele[0] is None:  # 第一元素
            ret = self.treat_first_ele(bi)
        elif self.ele[1] is None:  # 第二元素
            ret = self.treat_second_ele(bi)
        elif self.ele[2] is None:  # 第三元素
            ret = self.treat_third_ele(bi)
        else:
            raise CChanException(f"特征序列3个都找齐了还没处理!! 当前笔:{bi.idx},当前:{str(self)}", ErrCode.SEG_EIGEN_ERR)
        
        logger.info(f"[EigenFX] dir: {self.dir} , which_ele: {self.which_ele} add <---: ret: {ret}")
        return ret

    def reset(self):
        logger.info(f"[EigenFX] reset --->: which_ele: {self.which_ele}")
        # 重置特征序列分型
        self.which_ele = -1
        # 从线段的第二笔开始
        bi_tmp_list = list(self.lst[1:])
        if self.exclude_included:
            # 需要处理 笔包含关系
            self.clear()
            for bi in bi_tmp_list:
                # 逐笔处理分型，直到处理完成或者出现分型
                if self.add(bi):
                    logger.info(f"[EigenFX] reset <---: which_ele: {self.which_ele}")
                    return True
        else:
            # 不需要处理 笔包含关系
            assert self.ele[1] is not None
            ele2_begin_idx = self.ele[1].lst[0].idx
            # 重置特征序列分型
            self.ele[0], self.ele[1], self.ele[2] = self.ele[1], self.ele[2], None
            # 从第二元素开始
            self.lst = [bi for bi in bi_tmp_list if bi.idx >= ele2_begin_idx]  # 从第二元素开始
        logger.info(f"[EigenFX] reset <---: which_ele: {self.which_ele}")
        return False

    def can_be_end(self, bi_lst: CBiList):
        assert self.ele[1] is not None
        if self.ele[1].gap:
            assert self.ele[0] is not None
            end_bi_idx = self.GetPeakBiIdx()
            thred_value = bi_lst[end_bi_idx].get_end_val()
            break_thred = self.ele[0].low if self.is_up() else self.ele[0].high
            return self.find_revert_fx(bi_lst, end_bi_idx+2, thred_value, break_thred)
        else:
            return True

    def is_down(self):
        return self.dir == BI_DIR.DOWN

    def is_up(self):
        return self.dir == BI_DIR.UP

    def GetPeakBiIdx(self):
        assert self.ele[1] is not None
        return self.ele[1].GetPeakBiIdx()

    def all_bi_is_sure(self):
        assert self.last_evidence_bi is not None
        return next((False for bi in self.lst if not bi.is_sure), self.last_evidence_bi.is_sure)

    def clear(self):#
        # 清空特征序列分型
        self.ele = [None, None, None]
        # 清空笔列表
        self.lst = []

    def __str__(self):
        _t = [f"{[] if ele is None else ','.join([str(b.idx) for b in ele.lst])}" for ele in self.ele]
        return " | ".join(_t)

    def actual_break(self):
        if not self.exclude_included:
            return True
        assert self.ele[2] and self.ele[1]
        if (self.is_up() and self.ele[2].low < self.ele[1][-1]._low()) or \
           (self.is_down() and self.ele[2].high > self.ele[1][-1]._high()):  # 防止第二元素因为合并导致后面没有实际突破
            return True
        assert len(self.ele[2]) == 1
        ele2_bi = self.ele[2][0]
        if ele2_bi.next and ele2_bi.next.next:
            if ele2_bi.is_down() and ele2_bi.next.next._low() < ele2_bi._low():
                self.last_evidence_bi = ele2_bi.next.next
                return True
            elif ele2_bi.is_up() and ele2_bi.next.next._high() > ele2_bi._high():
                self.last_evidence_bi = ele2_bi.next.next
                return True
        return False

    def find_revert_fx(self, bi_list: CBiList, begin_idx: int, thred_value: float, break_thred: float):
        COMMON_COMBINE = True  # 是否用普通分形合并规则处理
        # 如果返回None，表示找到最后了
        first_bi_dir = bi_list[begin_idx].dir  # down则是要找顶分型
        egien_fx = CEigenFX(revert_bi_dir(first_bi_dir), exclude_included=not COMMON_COMBINE, lv=self.lv)  # 顶分型的话要找上升线段
        for bi in bi_list[begin_idx::2]:
            if egien_fx.add(bi):
                if COMMON_COMBINE:
                    return True

                while True:
                    _test = egien_fx.can_be_end(bi_list)
                    if _test in [True, None]:
                        self.last_evidence_bi = bi
                        return _test
                    elif not egien_fx.reset():
                        break
            # if (bi.is_down() and bi._low() < thred_value) or (bi.is_up() and bi._high() > thred_value):
            # 这段逻辑删除的原因参看#272，如果有其他badcase，再看怎么统一修复
            #     return False
        return None
