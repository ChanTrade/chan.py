from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, BSP_TYPE, DATA_SRC, FX_TYPE, KL_TYPE
import sys
import os
# Add the parent directory of Debug to the system path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Global variable to set the logging mode
LOG_MODE = "file"  # Change to "file" to log to a file

def log_message(message, mode=None, file_path="log.txt"):
    """
    Logs a message either to the console or to a file.

    :param message: The message to log.
    :param mode: The mode of logging, either 'print' or 'file'. If None, uses global LOG_MODE.
    :param file_path: The file path to write the log if mode is 'file'.
    """
    if mode is None:
        mode = LOG_MODE

    if mode == "print":
        print(message)
    elif mode == "file":
        with open(file_path, "a", encoding="utf-8") as file:
            file.write(message + "\n")

if __name__ == "__main__":
    """
    一个极其弱智的策略，只交易一类买卖点，底分型形成后就开仓，直到一类卖点顶分型形成后平仓
    只用做展示如何自己实现策略，做回测用~
    """
    code = "sz.000001"
    begin_time = "2021-01-01"
    end_time = None
    data_src = DATA_SRC.BAO_STOCK
    lv_list = [KL_TYPE.K_DAY]

    config = CChanConfig({
        "trigger_step": True,  # 打开开关！
        "divergence_rate": 0.8,
        "min_zs_cnt": 1,
    })

    chan = CChan(
        code=code,
        begin_time=begin_time,
        end_time=end_time,
        data_src=data_src,
        lv_list=lv_list,
        config=config,
        autype=AUTYPE.QFQ,
    )

    is_hold = False
    last_buy_price = None
    for chan_snapshot in chan.step_load():  # 每增加一根K线，返回当前静态精算结果
        
        # Get current level chan analysis
        cur_lv_chan = chan_snapshot[0]
        
        # Get latest K-line
        latest_kline = cur_lv_chan[-1][-1]
        
        # Check if latest K-line is part of a FX (分型)
        is_fx = False
        if len(cur_lv_chan) >= 2 and cur_lv_chan[-2].fx is not None:
            is_fx = True
            fx_type = cur_lv_chan[-2].fx
            log_message(f"{latest_kline.time}: K-line is part of a {fx_type} 分型")
            
        # Check if latest K-line is part of a BI (笔)
        is_bi = False
        if len(cur_lv_chan.bi_list) > 0:
            latest_bi = cur_lv_chan.bi_list[-1]
            if latest_kline in [klu for klc in latest_bi.klc_lst for klu in klc.lst]:
                is_bi = True
                log_message(f"{latest_kline.time}: K-line is part of BI {latest_bi.idx} ({latest_bi.dir})")
                
        # Check if latest K-line is part of a SEG (线段)
        is_seg = False
        if len(cur_lv_chan.seg_list) > 0:
            latest_seg = cur_lv_chan.seg_list[-1]
            if latest_kline in [klu for bi in latest_seg.bi_list for klc in bi.klc_lst for klu in klc.lst]:
                is_seg = True
                log_message(f"{latest_kline.time}: K-line is part of SEG {latest_seg.idx} ({latest_seg.dir})")

        # Print separator line for each K-line
        log_message(f"{latest_kline.time}: {'='*50}")

        bsp_list = chan_snapshot.get_bsp()  # 获取买卖点列表
        if not bsp_list:  # 为空
            continue
        last_bsp = bsp_list[-1]  # 最后一个买卖点
        if BSP_TYPE.T1 not in last_bsp.type and BSP_TYPE.T1P not in last_bsp.type:  # 假如只做1类买卖点
            continue
        cur_lv_chan = chan_snapshot[0]
        if last_bsp.klu.klc.idx != cur_lv_chan[-2].idx:
            continue
        if cur_lv_chan[-2].fx == FX_TYPE.BOTTOM and last_bsp.is_buy and not is_hold:  # 底分型形成后开仓
            last_buy_price = cur_lv_chan[-1][-1].close  # 开仓价格为最后一根K线close
            print(f'{cur_lv_chan[-1][-1].time}:buy price = {last_buy_price}')
            is_hold = True
        elif cur_lv_chan[-2].fx == FX_TYPE.TOP and not last_bsp.is_buy and is_hold:  # 顶分型形成后平仓
            sell_price = cur_lv_chan[-1][-1].close
            print(f'{cur_lv_chan[-1][-1].time}:sell price = {sell_price}, profit rate = {(sell_price-last_buy_price)/last_buy_price*100:.2f}%')
            is_hold = False
