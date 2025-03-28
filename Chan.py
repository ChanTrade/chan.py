import copy
import datetime
from collections import defaultdict
from typing import Dict, Iterable, List, Optional, Union

from BuySellPoint.BS_Point import CBS_Point
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE
from Common.ChanException import CChanException, ErrCode
from Common.CTime import CTime
from Common.func_util import check_kltype_order, kltype_lte_day
from DataAPI.CommonStockAPI import CCommonStockApi
from KLine.KLine_List import CKLine_List
from KLine.KLine_Unit import CKLine_Unit
import dill  # Add this import at the top of the file


class CChan:
    def __init__(
        self,
        code,
        begin_time=None,
        end_time=None,
        data_src: Union[DATA_SRC, str] = DATA_SRC.BAO_STOCK,
        lv_list=None,
        config=None,
        autype: AUTYPE = AUTYPE.QFQ,
    ):
        if lv_list is None:
            lv_list = [KL_TYPE.K_DAY, KL_TYPE.K_60M]
        check_kltype_order(lv_list)  # lv_list顺序从高到低
        self.code = code
        self.begin_time = str(begin_time) if isinstance(begin_time, datetime.date) else begin_time
        self.end_time = str(end_time) if isinstance(end_time, datetime.date) else end_time
        self.autype = autype
        self.data_src = data_src
        self.lv_list: List[KL_TYPE] = lv_list
        # 配置
        if config is None:
            config = CChanConfig()
        self.conf = config
        # 存储 不对齐的K线数量
        self.kl_misalign_cnt = 0
        # 存储每个级别K线时间不一致的K线时间
        self.kl_inconsistent_detail = defaultdict(list)
        # 存储每个级别K线迭代器
        self.g_kl_iter = defaultdict(list)
        # 初始化
        self.do_init()
        # 如果非回放模式，则加载所有K线
        if not config.trigger_step:
            for _ in self.load():
                ...

    def __deepcopy__(self, memo):
        cls = self.__class__
        obj: CChan = cls.__new__(cls)
        memo[id(self)] = obj
        obj.code = self.code
        obj.begin_time = self.begin_time
        obj.end_time = self.end_time
        obj.autype = self.autype
        obj.data_src = self.data_src
        obj.lv_list = copy.deepcopy(self.lv_list, memo)
        obj.conf = copy.deepcopy(self.conf, memo)
        obj.kl_misalign_cnt = self.kl_misalign_cnt
        obj.kl_inconsistent_detail = copy.deepcopy(self.kl_inconsistent_detail, memo)
        obj.g_kl_iter = copy.deepcopy(self.g_kl_iter, memo)
        if hasattr(self, 'klu_cache'):
            obj.klu_cache = copy.deepcopy(self.klu_cache, memo)
        if hasattr(self, 'klu_last_t'):
            obj.klu_last_t = copy.deepcopy(self.klu_last_t, memo)
        obj.kl_datas = {}
        for kl_type, ckline in self.kl_datas.items():
            obj.kl_datas[kl_type] = copy.deepcopy(ckline, memo)
        for kl_type, ckline in self.kl_datas.items():
            for klc in ckline:
                for klu in klc.lst:
                    assert id(klu) in memo
                    if klu.sup_kl:
                        memo[id(klu)].sup_kl = memo[id(klu.sup_kl)]
                    memo[id(klu)].sub_kl_list = [memo[id(sub_kl)] for sub_kl in klu.sub_kl_list]
        return obj

    def do_init(self):
        self.kl_datas: Dict[KL_TYPE, CKLine_List] = {}
        for idx in range(len(self.lv_list)):
            self.kl_datas[self.lv_list[idx]] = CKLine_List(self.lv_list[idx], conf=self.conf)

    def load_stock_data(self, stockapi_instance: CCommonStockApi, lv) -> Iterable[CKLine_Unit]:
        '''
        加载K线数据
        用yield返回K线数据的原因是：
        1. 如果数据量很大，一次性返回所有K线数据会导致内存不足
        2. 如果数据量很大，一次性返回所有K线数据会导致计算时间过长
        3. 如果数据量很大，一次性返回所有K线数据会导致计算结果不准确
        '''
        for KLU_IDX, klu in enumerate(stockapi_instance.get_kl_data()):
            # 设置K线索引
            klu.set_idx(KLU_IDX)
            # 设置K线级别
            klu.kl_type = lv
            # 返回K线
            yield klu

    def get_load_stock_iter(self, stockapi_cls, lv):
        '''
        获取每个级别K线迭代器
        '''
        stockapi_instance = stockapi_cls(code=self.code, k_type=lv, begin_date=self.begin_time, end_date=self.end_time, autype=self.autype)
        return self.load_stock_data(stockapi_instance, lv)

    # 添加每个级别K线迭代器
    def add_lv_iter(self, lv_idx, iter):
        if isinstance(lv_idx, int):
            self.g_kl_iter[self.lv_list[lv_idx]].append(iter)
        else:
            self.g_kl_iter[lv_idx].append(iter)

    # 获取下一个K线
    def get_next_lv_klu(self, lv_idx):
        '''
        获取当前级别K线迭代器，如果当前级别K线迭代器为空，则抛出StopIteration异常
        '''
        if isinstance(lv_idx, int):
            lv_idx = self.lv_list[lv_idx]
        if len(self.g_kl_iter[lv_idx]) == 0:
            raise StopIteration
        try:
            # 获取当前级别K线迭代器的下一个K线
            return self.g_kl_iter[lv_idx][0].__next__()
        except StopIteration:
            # 用当前级别K线迭代器中的下一个K线替换当前级别K线迭代器
            self.g_kl_iter[lv_idx] = self.g_kl_iter[lv_idx][1:]
            if len(self.g_kl_iter[lv_idx]) != 0:
                # 如果当前级别K线迭代器不为空，则递归获取下一个K线
                return self.get_next_lv_klu(lv_idx)
            else:
                raise

    def step_load(self):
        assert self.conf.trigger_step
        self.do_init()  # 清空数据，防止再次重跑没有数据
        yielded = False  # 是否曾经返回过结果
        for idx, snapshot in enumerate(self.load(self.conf.trigger_step)):
            if idx < self.conf.skip_step:
                continue
            yield snapshot
            yielded = True
        if not yielded:
            yield self

    def trigger_load(self, inp):
        # {type: [klu, ...]}
        if not hasattr(self, 'klu_cache'):
            self.klu_cache: List[Optional[CKLine_Unit]] = [None for _ in self.lv_list]
        if not hasattr(self, 'klu_last_t'):
            self.klu_last_t = [CTime(1980, 1, 1, 0, 0) for _ in self.lv_list]
        for lv_idx, lv in enumerate(self.lv_list):
            if lv not in inp:
                if lv_idx == 0:
                    raise CChanException(f"最高级别{lv}没有传入数据", ErrCode.NO_DATA)
                continue
            for klu in inp[lv]:
                klu.kl_type = lv
            assert isinstance(inp[lv], list)
            self.add_lv_iter(lv, iter(inp[lv]))
        for _ in self.load_iterator(lv_idx=0, parent_klu=None, step=False):
            ...
        if not self.conf.trigger_step:  # 非回放模式全部算完之后才算一次中枢和线段
            for lv in self.lv_list:
                self.kl_datas[lv].cal_seg_and_zs()

    def init_lv_klu_iter(self, stockapi_cls):
        '''
        初始化每个级别K线迭代器
        '''
        # 为了跳过一些获取数据失败的级别
        lv_klu_iter = []
        valid_lv_list = []
        # 遍历每个级别 构造每个级别的K线迭代器 保存到lv_klu_iter中
        for lv in self.lv_list:
            try:
                # 获取每个级别K线迭代器
                lv_klu_iter.append(self.get_load_stock_iter(stockapi_cls, lv))
                # 存储有效级别
                valid_lv_list.append(lv)
            except CChanException as e:
                # 如果数据源不存在，并且配置了自动跳过非法子级别，则跳过
                if e.errcode == ErrCode.SRC_DATA_NOT_FOUND and self.conf.auto_skip_illegal_sub_lv:
                    if self.conf.print_warning:
                        print(f"[WARNING-{self.code}]{lv}级别获取数据失败，跳过")
                    del self.kl_datas[lv]
                    continue
                raise e
        self.lv_list = valid_lv_list
        return lv_klu_iter

    def GetStockAPI(self):
        _dict = {}
        if self.data_src == DATA_SRC.BAO_STOCK:
            from DataAPI.BaoStockAPI import CBaoStock
            _dict[DATA_SRC.BAO_STOCK] = CBaoStock
        elif self.data_src == DATA_SRC.CCXT:
            from DataAPI.ccxt import CCXT
            _dict[DATA_SRC.CCXT] = CCXT
        elif self.data_src == DATA_SRC.CSV:
            from DataAPI.csvAPI import CSV_API
            _dict[DATA_SRC.CSV] = CSV_API
        if self.data_src in _dict:
            return _dict[self.data_src]
        assert isinstance(self.data_src, str)
        if self.data_src.find("custom:") < 0:
            raise CChanException("load src type error", ErrCode.SRC_DATA_TYPE_ERR)
        package_info = self.data_src.split(":")[1]
        package_name, cls_name = package_info.split(".")
        exec(f"from DataAPI.{package_name} import {cls_name}")
        return eval(cls_name)

    def load(self, step=False):
        '''
        加载K线
        step: 是否是回放模式
        '''
        stockapi_cls = self.GetStockAPI()
        try:
            # 初始化数据源
            stockapi_cls.do_init()
            # 初始化每个级别K线迭代器
            for lv_idx, klu_iter in enumerate(self.init_lv_klu_iter(stockapi_cls)):
                # 将每个级别K线迭代器添加到g_kl_iter中
                self.add_lv_iter(lv_idx, klu_iter)
            # 初始化每个级别K线缓存
            self.klu_cache: List[Optional[CKLine_Unit]] = [None for _ in self.lv_list]
            # 初始化每个级别K线时间
            self.klu_last_t = [CTime(1980, 1, 1, 0, 0) for _ in self.lv_list]
            # 计算入口
            yield from self.load_iterator(lv_idx=0, parent_klu=None, step=step)
            if not step:
                # 非回放模式全部算完之后才算一次中枢和线段
                for lv in self.lv_list:
                    self.kl_datas[lv].cal_seg_and_zs()
        except Exception:
            raise
        finally:
            # 关闭数据源
            stockapi_cls.do_close()
        if len(self[0]) == 0:
            raise CChanException("最高级别没有获得任何数据", ErrCode.NO_DATA)

    def set_klu_parent_relation(self, parent_klu, kline_unit, cur_lv, lv_idx):
        # 设置K线父子关系
        if self.conf.kl_data_check and kltype_lte_day(cur_lv) and kltype_lte_day(self.lv_list[lv_idx-1]):
            # 若配置了检查K线数据一致性，并且当前级别和上一级别都是日级别以下，则检查K线数据一致性
            self.check_kl_consitent(parent_klu, kline_unit)
        parent_klu.add_children(kline_unit)
        kline_unit.set_parent(parent_klu)

    def add_new_kl(self, cur_lv: KL_TYPE, kline_unit):
        '''
        非常关键的函数，添加新K线，并计算 各种基于单根K线的指标
        '''
        try:
            # 添加新K线
            self.kl_datas[cur_lv].add_single_klu(kline_unit)
        except Exception:
            if self.conf.print_err_time:
                print(f"[ERROR-{self.code}]在计算{kline_unit.time}K线时发生错误!")
            raise

    def try_set_klu_idx(self, lv_idx: int, kline_unit: CKLine_Unit):
        # 如果K线索引大于0，则直接返回
        if kline_unit.idx >= 0:
            return
        # 如果当前级别K线列表为空，则设置K线索引为0
        if len(self[lv_idx]) == 0:
            kline_unit.set_idx(0)
        else:
            # 如果当前级别K线列表不为空，则设置K线索引为最后一个K线的索引加1
            kline_unit.set_idx(self[lv_idx][-1][-1].idx + 1)

    # 加载K线迭代器
    def load_iterator(self, lv_idx, parent_klu, step):
        # K线时间天级别以下描述的是结束时间，如60M线，每天第一根是10点30的
        # 天以上是当天日期

        # 获取当前级别
        cur_lv = self.lv_list[lv_idx]
        # Retrieve the last CKLine_Unit from the last CKLine in the list at level lv_idx.
        # This is done by first checking if there are any CKLines at the specified level (self[lv_idx])
        # and then ensuring that the last CKLine itself contains any CKLine_Units.
        # If both conditions are met, access the last CKLine_Unit; otherwise, set pre_klu to None.
        pre_klu = self[lv_idx][-1][-1] if len(self[lv_idx]) > 0 and len(self[lv_idx][-1]) > 0 else None
        while True:
            # klu缓存非None, 则使用该lv_idx的缓存
            if self.klu_cache[lv_idx]:
                kline_unit = self.klu_cache[lv_idx]
                assert kline_unit is not None
                # 缓存置空
                self.klu_cache[lv_idx] = None
            else:
                try:
                    # 获取下一个K线
                    kline_unit = self.get_next_lv_klu(lv_idx)
                    # 设置K线索引
                    self.try_set_klu_idx(lv_idx, kline_unit)
                    # 检查K线时间是否单调
                    if not kline_unit.time > self.klu_last_t[lv_idx]:
                        raise CChanException(f"kline time err, cur={kline_unit.time}, last={self.klu_last_t[lv_idx]},"
                                             f"or refer to quick_guide.md, try set auto=False in the CTime returned by your data source class",
                                             ErrCode.KL_NOT_MONOTONOUS)
                    # 更新前一个K线时间
                    self.klu_last_t[lv_idx] = kline_unit.time
                except StopIteration:
                    # 如果当前级别K线迭代器为空，则退出
                    break
            # 如果父级别存在，并且当前K线时间大于父级别K线时间
            if parent_klu and kline_unit.time > parent_klu.time:
                # 缓存当前K线
                self.klu_cache[lv_idx] = kline_unit
                break
            # 设置当前K线的前一个K线
            kline_unit.set_pre_klu(pre_klu)
            # 更新前一个K线
            pre_klu = kline_unit
            # 添加当前级别 lv_idx 的新K线 并且进行缠论的逐根计算
            self.add_new_kl(cur_lv, kline_unit)
            # 设置当前K线的父级别
            if parent_klu:
                self.set_klu_parent_relation(parent_klu, kline_unit, cur_lv, lv_idx)
            # 递归处理下一级别
            if lv_idx != len(self.lv_list)-1:
                for _ in self.load_iterator(lv_idx+1, kline_unit, step):
                    ...
                # 检查 不同周期的K线是否对齐
                self.check_kl_align(kline_unit, lv_idx)
            if lv_idx == 0 and step:
                # 如果是最高级别，并且是回放模式，则返回缠论计算结果
                yield self

    def check_kl_consitent(self, parent_klu, sub_klu):
        # 检查 父级别和子级别K线时间是否一致
        if parent_klu.time.year != sub_klu.time.year or \
           parent_klu.time.month != sub_klu.time.month or \
           parent_klu.time.day != sub_klu.time.day:
            # 若父级别和子级别的 年月日 不一致，则记录不一致的K线时间
            self.kl_inconsistent_detail[str(parent_klu.time)].append(sub_klu.time)
            if self.conf.print_warning:
                print(f"[WARNING-{self.code}]父级别时间是{parent_klu.time}，次级别时间却是{sub_klu.time}")
            if len(self.kl_inconsistent_detail) >= self.conf.max_kl_inconsistent_cnt:
                # 若父&子级别K线时间不一致条数超过配置，则抛出异常
                raise CChanException(f"父&子级别K线时间不一致条数超过{self.conf.max_kl_inconsistent_cnt}！！", ErrCode.KL_TIME_INCONSISTENT)

    def check_kl_align(self, kline_unit, lv_idx):
        # 检查 当前K线是否在次级别找到K线
        if self.conf.kl_data_check and len(kline_unit.sub_kl_list) == 0:
            self.kl_misalign_cnt += 1
            if self.conf.print_warning:
                print(f"[WARNING-{self.code}]当前{kline_unit.time}没在次级别{self.lv_list[lv_idx+1]}找到K线！！")
            if self.kl_misalign_cnt >= self.conf.max_kl_misalgin_cnt:
                # 若在次级别找不到K线条数超过配置，则抛出异常
                raise CChanException(f"在次级别找不到K线条数超过{self.conf.max_kl_misalgin_cnt}！！", ErrCode.KL_DATA_NOT_ALIGN)

    def __getitem__(self, n) -> CKLine_List:
        '''
        # 获取指定级别的 CKline列表, CKL_TYPE 获取指定级别的CKline列表, int 获取指定索引的CKline列表
        # CKline可以是 Kline,Bi,ZS,Seg
        # KL_TYPE 是枚举类型，int 是整数类型
        '''
        if isinstance(n, KL_TYPE):
            return self.kl_datas[n]
        elif isinstance(n, int):
            return self.kl_datas[self.lv_list[n]]
        else:
            raise CChanException("unspoourt query type", ErrCode.COMMON_ERROR)

    def get_bsp(self, idx=None) -> List[CBS_Point]:
        if idx is not None:
            return self[idx].bs_point_lst.getSortedBspList()
        assert len(self.lv_list) == 1
        return self[0].bs_point_lst.getSortedBspList()

    @staticmethod
    def save_snapshot(chan: 'CChan', filepath: str) -> None:
        """
        Save Chan instance to file using dill
        
        Args:
            chan: CChan instance to save
            filepath: File path to save the snapshot
        """
        try:
            with open(filepath, 'wb') as f:
                # Print object info before dumping
                print(f"Saving Chan object:")
                print(f"Code: {chan.code}")
                print(f"Begin time: {chan.begin_time}")
                print(f"End time: {chan.end_time}")
                print(f"Data source: {chan.data_src}")
                print(f"Level list: {chan.lv_list}")
                print(f"Config: {chan.conf}")
                # Dump the object
                dill.dump(chan, f)  # Use dill instead of pickle
        except Exception as e:
            print(f"Failed to save snapshot: {e}")

    @staticmethod 
    def load_snapshot(filepath: str) -> 'CChan':
        """
        Load Chan instance from dill file
        
        Args:
            filepath: File path to load the snapshot from
            
        Returns:
            CChan instance loaded from file
        """
        try:
            with open(filepath, 'rb') as f:
                return dill.load(f)  # Use dill instead of pickle
        except Exception as e:
            print(f"Failed to load snapshot: {e}")
            return None