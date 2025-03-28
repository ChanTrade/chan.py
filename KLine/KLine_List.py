import copy
from typing import List, Union, overload

from Bi.Bi import CBi
from Bi.BiList import CBiList
from BuySellPoint.BSPointList import CBSPointList
from ChanConfig import CChanConfig
from Common.CEnum import KLINE_DIR, SEG_TYPE
from Common.ChanException import CChanException, ErrCode
from Seg.Seg import CSeg
from Seg.SegConfig import CSegConfig
from Seg.SegListComm import CSegListComm
from ZS.ZSList import CZSList
from Common.func_util import logger

from .KLine import CKLine
from .KLine_Unit import CKLine_Unit


def get_seglist_instance(seg_config: CSegConfig, lv) -> CSegListComm:
    # 根据 线段配置 获取 线段算法实例
    if seg_config.seg_algo == "chan":
        from Seg.SegListChan import CSegListChan
        return CSegListChan(seg_config, lv)
    elif seg_config.seg_algo == "1+1":
        print(f'Please avoid using seg_algo={seg_config.seg_algo} as it is deprecated and no longer maintained.')
        from Seg.SegListDYH import CSegListDYH
        return CSegListDYH(seg_config, lv)
    elif seg_config.seg_algo == "break":
        print(f'Please avoid using seg_algo={seg_config.seg_algo} as it is deprecated and no longer maintained.')
        from Seg.SegListDef import CSegListDef
        return CSegListDef(seg_config, lv)
    else:
        raise CChanException(f"unsupport seg algoright:{seg_config.seg_algo}", ErrCode.PARA_ERROR)


class CKLine_List:
    def __init__(self, kl_type, conf: CChanConfig):
        # 当前 K线周期类型
        self.kl_type = kl_type ,
        self.config = conf
        # 当前K线列表
        self.lst: List[CKLine] = []  # K线列表，可递归  元素KLine类型
        # 笔列表
        self.bi_list = CBiList(bi_conf=conf.bi_conf)
        # 线段列表
        self.seg_list: CSegListComm[CBi] = get_seglist_instance(seg_config=conf.seg_conf, lv=SEG_TYPE.BI)
        # 线段的线段列表
        self.segseg_list: CSegListComm[CSeg[CBi]] = get_seglist_instance(seg_config=conf.seg_conf, lv=SEG_TYPE.SEG)
        # 中枢列表  
        self.zs_list = CZSList(zs_config=conf.zs_conf)
        # 线段中枢列表
        self.segzs_list = CZSList(zs_config=conf.zs_conf)
        # 买卖点列表
        self.bs_point_lst = CBSPointList[CBi, CBiList](bs_point_config=conf.bs_point_conf)
        # 线段买卖点列表
        self.seg_bs_point_lst = CBSPointList[CSeg, CSegListComm](bs_point_config=conf.seg_bs_point_conf)

        # 获取基于单根K线驱动的指标模型列表
        self.metric_model_lst = conf.GetMetricModel()

        # 是否需要按步计算中枢和线段
        self.step_calculation = self.need_cal_step_by_step()
        # 最后一根确定的线段开始笔索引
        self.last_sure_seg_start_bi_idx = -1
        # 最后一根确定的线段线段开始笔索引
        self.last_sure_segseg_start_bi_idx = -1

    def __deepcopy__(self, memo):
        '''
        深拷贝
        '''
        new_obj = CKLine_List(self.kl_type, self.config)
        memo[id(self)] = new_obj
        # 深拷贝 每个K线
        for klc in self.lst:
            klus_new = []
            for klu in klc.lst:
                new_klu = copy.deepcopy(klu, memo)
                memo[id(klu)] = new_klu
                if klu.pre is not None:
                    new_klu.set_pre_klu(memo[id(klu.pre)])
                klus_new.append(new_klu)
            #
            new_klc = CKLine(klus_new[0], idx=klc.idx, _dir=klc.dir)
            new_klc.set_fx(klc.fx)
            new_klc.kl_type = klc.kl_type
            for idx, klu in enumerate(klus_new):
                klu.set_klc(new_klc)
                if idx != 0:
                    new_klc.add(klu)
            memo[id(klc)] = new_klc
            if new_obj.lst:
                new_obj.lst[-1].set_next(new_klc)
                new_klc.set_pre(new_obj.lst[-1])
            new_obj.lst.append(new_klc)
        
        # 深拷贝 笔列表、线段列表、线段线段列表、中枢列表、买卖点列表、指标模型列表、是否需要按步计算中枢和线段、线段买卖点列表
        new_obj.bi_list = copy.deepcopy(self.bi_list, memo)
        new_obj.seg_list = copy.deepcopy(self.seg_list, memo)
        new_obj.segseg_list = copy.deepcopy(self.segseg_list, memo)
        new_obj.zs_list = copy.deepcopy(self.zs_list, memo)
        new_obj.segzs_list = copy.deepcopy(self.segzs_list, memo)
        new_obj.bs_point_lst = copy.deepcopy(self.bs_point_lst, memo)
        new_obj.metric_model_lst = copy.deepcopy(self.metric_model_lst, memo)
        new_obj.step_calculation = copy.deepcopy(self.step_calculation, memo)
        new_obj.seg_bs_point_lst = copy.deepcopy(self.seg_bs_point_lst, memo)
        return new_obj

    @overload
    def __getitem__(self, index: int) -> CKLine: ...

    @overload
    def __getitem__(self, index: slice) -> List[CKLine]: ...

    def __getitem__(self, index: Union[slice, int]) -> Union[List[CKLine], CKLine]:
        return self.lst[index]

    def __len__(self):
        return len(self.lst)

    def cal_seg_and_zs(self):
        if not self.step_calculation:
            self.bi_list.try_add_virtual_bi(self.lst[-1])
        self.last_sure_seg_start_bi_idx = cal_seg(self.bi_list, self.seg_list, self.last_sure_seg_start_bi_idx)
        '''
        self.zs_list.cal_bi_zs(self.bi_list, self.seg_list)
        update_zs_in_seg(self.bi_list, self.seg_list, self.zs_list)  # 计算seg的zs_lst，以及中枢的bi_in, bi_out

        self.last_sure_segseg_start_bi_idx = cal_seg(self.seg_list, self.segseg_list, self.last_sure_segseg_start_bi_idx)
        self.segzs_list.cal_bi_zs(self.seg_list, self.segseg_list)
        update_zs_in_seg(self.seg_list, self.segseg_list, self.segzs_list)  # 计算segseg的zs_lst，以及中枢的bi_in, bi_out

        # 计算买卖点
        self.seg_bs_point_lst.cal(self.seg_list, self.segseg_list)  # 线段线段买卖点
        self.bs_point_lst.cal(self.bi_list, self.seg_list)  # 再算笔买卖点
        '''

    def need_cal_step_by_step(self):
        return self.config.trigger_step

    # 添加单根K线 - 行情第一根K线以及后续K线的处理
    def add_single_klu(self, klu: CKLine_Unit):
        # 这个函数只能计算当前K线 以及 当前K线之前的历史K线的 指标
        # 如 单根K线对应的 MACD, KDJ, RSI, BOLL, MA, 等
        klu.set_metric(self.metric_model_lst)
        # 如果lst为空，则添加当前 合并K线到 lst
        if len(self.lst) == 0:
            self.lst.append(CKLine(klu, idx=0))
        else:
            _dir = self.lst[-1].try_add(klu) # 做K线合并， 返回合并方向
            # 不需要合并K线, _dir 包含 向上合并，向下合并，包含关系
            if _dir != KLINE_DIR.COMBINE:
                # 添加新K线到列表
                self.lst.append(CKLine(klu, idx=len(self.lst), _dir=_dir))
                # 当前lst大于等于3，更新分型
                if len(self.lst) >= 3:
                    # 通过 倒数最后3根 合并K线 确定倒数第二根K的分型信息
                    self.lst[-2].update_fx(self.lst[-3], self.lst[-1])
        
                # 更新笔， 如果需要按步计算中枢和线段，则计算中枢和线段. self.step_calculation = conf.trigger_step
                if self.bi_list.update_bi(self.lst[-2], self.lst[-1], self.step_calculation) and self.step_calculation:
                    self.cal_seg_and_zs()
                    pass
            # 合并K线， 需要尝试添加虚拟笔
            elif self.step_calculation and self.bi_list.try_add_virtual_bi(self.lst[-1], need_del_end=True): 
                # 这里的必要性参见issue#175
                self.cal_seg_and_zs()
                pass

    def klu_iter(self, klc_begin_idx=0):
        for klc in self.lst[klc_begin_idx:]:
            yield from klc.lst


def cal_seg(bi_list, seg_list: CSegListComm, last_sure_seg_start_bi_idx) -> int:
    logger.info(f"[KLine_List] 0.0_cal_seg: bi_list_len={len(bi_list)}, seg_list_len={len(seg_list)}")
    seg_list.update(bi_list)
    logger.info(f"[KLine_List] 0.1_cal_seg: seg_list_len={len(seg_list)}")
    if len(seg_list) == 0:
        for bi in bi_list:
            bi.set_seg_idx(0)
        return -1
    cur_seg: CSeg = seg_list[-1]
    logger.info(f"[KLine_List] 0.2_cal_seg: cur_seg={cur_seg}")
    bi_idx = len(bi_list) - 1
    while bi_idx >= 0:
        bi = bi_list[bi_idx]
        if bi.seg_idx is not None and bi.idx < last_sure_seg_start_bi_idx:
            break
        if bi.idx > cur_seg.end_bi.idx:
            bi.set_seg_idx(cur_seg.idx+1)
            bi_idx -= 1
            continue
        if bi.idx < cur_seg.start_bi.idx:
            assert cur_seg.pre
            cur_seg = cur_seg.pre
        bi.set_seg_idx(cur_seg.idx)
        bi_idx -= 1
    logger.info(f"[KLine_List] 0.3_cal_seg : last_sure_seg_start_bi_idx={last_sure_seg_start_bi_idx}")
    last_sure_seg_start_bi_idx = -1
    seg = seg_list[-1]
    while seg:
        if seg.is_sure:
            last_sure_seg_start_bi_idx = seg.start_bi.idx
            break
        seg = seg.pre
    logger.info(f"[KLine_List] 0.4_cal_seg : last_sure_seg_start_bi_idx={last_sure_seg_start_bi_idx}\n\n")

    return last_sure_seg_start_bi_idx


def update_zs_in_seg(bi_list, seg_list, zs_list):
    sure_seg_cnt = 0
    seg_idx = len(seg_list) - 1
    while seg_idx >= 0:
        seg = seg_list[seg_idx]
        if seg.ele_inside_is_sure:
            break
        if seg.is_sure:
            sure_seg_cnt += 1
        seg.clear_zs_lst()
        _zs_idx = len(zs_list) - 1
        while _zs_idx >= 0:
            zs = zs_list[_zs_idx]
            if zs.end.idx < seg.start_bi.get_begin_klu().idx:
                break
            if zs.is_inside(seg):
                seg.add_zs(zs)
            assert zs.begin_bi.idx > 0
            zs.set_bi_in(bi_list[zs.begin_bi.idx-1])
            if zs.end_bi.idx+1 < len(bi_list):
                zs.set_bi_out(bi_list[zs.end_bi.idx+1])
            zs.set_bi_lst(list(bi_list[zs.begin_bi.idx:zs.end_bi.idx+1]))
            _zs_idx -= 1

        if sure_seg_cnt > 2:
            if not seg.ele_inside_is_sure:
                seg.ele_inside_is_sure = True
        seg_idx -= 1
