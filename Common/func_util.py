from .CEnum import BI_DIR, KL_TYPE

# Need to import inspect for the frame inspection
import inspect


def kltype_lt_day(_type):
    # 日级别以下 不包含日级别 {1分钟, 5分钟, 15分钟, 30分钟, 60分钟}
    return _type in [KL_TYPE.K_1M, KL_TYPE.K_5M, KL_TYPE.K_15M, KL_TYPE.K_30M, KL_TYPE.K_60M]


def kltype_lte_day(_type):
    # 日级别以下 包含日级别 {1分钟, 5分钟, 15分钟, 30分钟, 60分钟, 日线}
    return _type in [KL_TYPE.K_1M, KL_TYPE.K_5M, KL_TYPE.K_15M, KL_TYPE.K_30M, KL_TYPE.K_60M, KL_TYPE.K_DAY]


def check_kltype_order(type_list: list):
    # 检查K线类型列表的顺序是否从大级别到小级别
    _dict = {
        KL_TYPE.K_1M: 1,
        KL_TYPE.K_3M: 2,
        KL_TYPE.K_5M: 3,
        KL_TYPE.K_15M: 4,
        KL_TYPE.K_30M: 5,
        KL_TYPE.K_60M: 6,
        KL_TYPE.K_DAY: 7,
        KL_TYPE.K_WEEK: 8,
        KL_TYPE.K_MON: 9,
        KL_TYPE.K_QUARTER: 10,
        KL_TYPE.K_YEAR: 11,
    }
    last_lv = float("inf")
    for kl_type in type_list:
        cur_lv = _dict[kl_type]
        assert cur_lv < last_lv, "lv_list的顺序必须从大级别到小级别"
        last_lv = cur_lv


def revert_bi_dir(dir):
    # 笔方向反转
    return BI_DIR.DOWN if dir == BI_DIR.UP else BI_DIR.UP


def has_overlap(l1, h1, l2, h2, equal=False):
    # 判断两个区间是否重叠 若equal=True，则表示区间相等也算重叠
    return h2 >= l1 and h1 >= l2 if equal else h2 > l1 and h1 > l2


def str2float(s):
    # 将字符串转换为浮点数 若转换失败，则返回0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_inf(v):
    # 将无穷大和无穷小转换为字符串
    if type(v) == float:
        if v == float("inf"):
            v = 'float("inf")'
        if v == float("-inf"):
            v = 'float("-inf")'
    return v


import logging
# Initialize global logger
logger = logging.getLogger('ChanMaLogger')
logger.setLevel(logging.DEBUG)
# Configure logging to file by default
log_to_file = True
# Set up logging handler based on the flag
if log_to_file:
    handler = logging.FileHandler('cchan.log')
else:
    handler = logging.StreamHandler()
# Set logging format
# formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
formatter = logging.Formatter('%(levelname)s - %(message)s')
handler.setFormatter(formatter)
# Add handler to the logger
logger.addHandler(handler)

def tabs(n):
    """
    Returns a string with n tab characters.
    
    :param n: Number of tab characters
    :return: String with n tab characters
    """
    return "\t" * n


