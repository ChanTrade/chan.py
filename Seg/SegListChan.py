from Bi.BiList import CBiList
from Bi.Bi import CBi
from Common.CEnum import BI_DIR, SEG_TYPE

from .EigenFX import CEigenFX
from .SegConfig import CSegConfig
from .SegListComm import CSegListComm
from Common.func_util import logger

class CSegListChan(CSegListComm):
    def __init__(self, seg_config=CSegConfig(), lv=SEG_TYPE.BI):
        super(CSegListChan, self).__init__(seg_config=seg_config, lv=lv)

    def do_init(self):
        # 删除末尾不确定的线段
        while len(self) and not self.lst[-1].is_sure:
            _seg = self[-1]
            for bi in _seg.bi_list:
                bi.parent_seg = None
            if _seg.pre:
                _seg.pre.next = None
            self.lst.pop()
        if len(self):
            assert self.lst[-1].eigen_fx and self.lst[-1].eigen_fx.ele[-1]
            if not self.lst[-1].eigen_fx.ele[-1].lst[-1].is_sure:
                # 如果确定线段的分形的第三元素包含不确定笔，也需要重新算，不然线段分形元素的高低点可能不对
                self.lst.pop()

    def update(self, bi_lst: CBiList):
        logger.info(f"[SegListChan] 1.0-update do_init --->")
        self.do_init()
        logger.info(f"[SegListChan] 1.1-update do_init <---")
        if len(self) == 0:
            logger.info(f"[SegListChan] 1.2.0-update --->: begin_idx=0")
            self.cal_seg_sure(bi_lst, begin_idx=0)
        else:
            logger.info(f"[SegListChan] 1.2.1-update --->: begin_idx={self[-1].end_bi.idx+1}")
            self.cal_seg_sure(bi_lst, begin_idx=self[-1].end_bi.idx+1)
        self.collect_left_seg(bi_lst)
        logger.info(f"[SegListChan] 1.3-update <---: seg_cnt={len(self.lst)}")

    def cal_seg_sure(self, bi_lst: CBiList, begin_idx: int):
        logger.info(f"[SegListChan] 1.0-cal_seg_sure --->: bi_list:\n{bi_lst}\nbegin_idx: {begin_idx}")
        up_eigen = CEigenFX(BI_DIR.UP, lv=self.lv)  # 上升线段下降笔
        down_eigen = CEigenFX(BI_DIR.DOWN, lv=self.lv)  # 下降线段上升笔
        last_seg_dir = None if len(self) == 0 else self[-1].dir
        for bi in bi_lst[begin_idx:]:
            logger.info(f"[SegListChan] 1.1-cal_seg_sure for eigen --->: {bi}")
            fx_eigen = None
            if bi.is_down() and last_seg_dir != BI_DIR.UP:
                if up_eigen.add(bi):
                    fx_eigen = up_eigen
            elif bi.is_up() and last_seg_dir != BI_DIR.DOWN:
                if down_eigen.add(bi):
                    fx_eigen = down_eigen
            if len(self) == 0:  # 尝试确定第一段方向，不要以谁先成为分形来决定，反例：US.EVRG
                if up_eigen.ele[1] is not None and bi.is_down():
                    last_seg_dir = BI_DIR.DOWN
                    down_eigen.clear()
                elif down_eigen.ele[1] is not None and bi.is_up():
                    up_eigen.clear()
                    last_seg_dir = BI_DIR.UP
                if up_eigen.ele[1] is None and last_seg_dir == BI_DIR.DOWN and bi.dir == BI_DIR.DOWN:
                    last_seg_dir = None
                elif down_eigen.ele[1] is None and last_seg_dir == BI_DIR.UP and bi.dir == BI_DIR.UP:
                    last_seg_dir = None

            if fx_eigen:
                self.treat_fx_eigen(fx_eigen, bi_lst)
                break
        logger.info(f"[SegListChan] 1.2-cal_seg_sure <---: seg_cnt={len(self.lst)}")

    def treat_fx_eigen(self, fx_eigen, bi_lst: CBiList):
        logger.info(f"[SegListChan] 1.0-treat_fx_eigen --->: {fx_eigen}")
        _test = fx_eigen.can_be_end(bi_lst)
        end_bi_idx = fx_eigen.GetPeakBiIdx()
        if _test in [True, None]:  # None表示反向分型找到尾部也没找到
            is_true = _test is not None  # 如果是正常结束
            if not self.add_new_seg(bi_lst, end_bi_idx, is_sure=is_true and fx_eigen.all_bi_is_sure()):  # 防止第一根线段的方向与首尾值异常
                self.cal_seg_sure(bi_lst, end_bi_idx+1)
                logger.info(f"[SegListChan] 1.1-treat_fx_eigen add_new_seg <---: {self.lst}")
                return
            self.lst[-1].eigen_fx = fx_eigen
            if is_true:
                self.cal_seg_sure(bi_lst, end_bi_idx + 1)
        else:
            self.cal_seg_sure(bi_lst, fx_eigen.lst[1].idx)
        logger.info(f"[SegListChan] 1.2-treat_fx_eigen <---: {self.lst}")
