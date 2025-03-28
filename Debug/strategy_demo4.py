import sys
import os

# Add the parent directory of Debug to the system path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from Chan import CChan
from ChanConfig import CChanConfig
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE
from DataAPI.BaoStockAPI import CBaoStock
from DataAPI.csvAPI import CSV_API
from IdeaIndicator.chanma import ChanMa
from Common.CTime import CTime
from Chan import CChan
from ChanConfig import CChanConfig
from Bi.Bi import CBi
from Seg.Seg import CSeg
from Common.CEnum import AUTYPE, DATA_SRC, KL_TYPE
from Plot.AnimatePlotDriver import CAnimateDriver
from Plot.PlotDriver import CPlotDriver

if __name__ == "__main__":
    """
    本demo演示当你要用多级别trigger load的时候，如何巧妙的解决时间对齐的问题：
    解决方案就是喂第一根最大级别的时候，直接把所有的次级别全部喂进去
    之后每次只需要喂一根最大级别即可，复用框架内置的K线时间对齐能力
    从而避免了在trigger_load入参那里进行K线对齐，自己去找出最大级别那根K线下所有次级别的K线
    """
    code = "sh.000001"
    begin_time = "2007-10-14"
    end_time = "2008-07-18"
    # data_src = DATA_SRC.BAO_STOCK
    data_src = DATA_SRC.CSV
    # lv_list = [KL_TYPE.K_DAY, KL_TYPE.K_30M]
    lv_list = [KL_TYPE.K_DAY]

    config = CChanConfig({
        "trigger_step": True,
        "divergence_rate": 0.8,
        "min_zs_cnt": 1,
    })

    plot_config = {
        "plot_kline": True,
        "plot_kline_combine": True,
        "plot_bi": True,
        "plot_seg": True,
        "plot_eigen": True,
        "plot_zs": True,
        "plot_macd": False,
        "plot_mean": False,
        "plot_channel": False,
        "plot_bsp": True,
        "plot_extrainfo": False,
        "plot_demark": False,
        "plot_marker": False,
        "plot_rsi": False,
        "plot_kdj": False,
    }

    plot_para = {
        "seg": {
            # "plot_trendline": True,
        },
        "bi": {
            # "show_num": True,
            # "disp_end": True,
        },
        "figure": {
            "x_range": 3300,
        },
        "marker": {
            # "markers": {  # text, position, color
            #     '2023/06/01': ('marker here', 'up', 'red'),
            #     '2023/06/08': ('marker here', 'down')
            # },
        }
    }

    chan = CChan(
        code=code,
        begin_time=begin_time,  # 已经没啥用了这一行
        end_time=end_time,  # 已经没啥用了这一行
        data_src=data_src,  # 已经没啥用了这一行
        lv_list=lv_list,
        config=config,
        autype=AUTYPE.QFQ,  # 已经没啥用了这一行
    )

    # if not config.trigger_step:
    #     plot_driver = CPlotDriver(
    #         chan,
    #         plot_config=plot_config,
    #         plot_para=plot_para,
    #     )
    #     plot_driver.figure.show()
    #     plot_driver.save2img("./test.png")
    # else:
    #     CAnimateDriver(
    #         chan,
    #         plot_config=plot_config,
    #         plot_para=plot_para,
    #     )
        
    # CBaoStock.do_init()
    # data_src_day = CBaoStock(code, k_type=KL_TYPE.K_DAY, begin_date=begin_time, end_date=end_time, autype=AUTYPE.QFQ)
    # data_src_30m = CBaoStock(code, k_type=KL_TYPE.K_30M, begin_date=begin_time, end_date=end_time, autype=AUTYPE.QFQ)
    # kl_30m_all = list(data_src_30m.get_kl_data())

    data_src_day = CSV_API(code, k_type=KL_TYPE.K_DAY, begin_date=begin_time, end_date=end_time, autype=AUTYPE.QFQ)
    # 计算ChanMa
    chanma = ChanMa(chan, log_to_file=True)
    for _idx, klu in enumerate(data_src_day.get_kl_data()):
        # 本质是每喂一根日线的时候，这根日线之前的都要喂过，提前喂多点不要紧，框架会自动根据日线来截取需要的30M K线
        # 30M一口气全部喂完，后续就不用关注时间对齐的问题了
        # if _idx == 0:
        #     chan.trigger_load({KL_TYPE.K_DAY: [klu], KL_TYPE.K_30M: kl_30m_all})
        # else:
        #     chan.trigger_load({KL_TYPE.K_DAY: [klu]})

        chan.trigger_load({KL_TYPE.K_DAY: [klu]})

        # 检查时间对齐
        # if _idx < 3320:  # demo只检查4根日线
        #     continue
        # 检查时间对齐
        # print("当前所有日线:", [klu.time.to_str() for klu in chan[0].klu_iter()])
        # print("当前所有30M K线:", [klu.time.to_str() for klu in chan[1].klu_iter()], "\n")
        # 当前日线
        # klu.Info()
        # 刷新Chan 笔，段信息
        # Only run ChanMa calculations if the current klu time is 2009-02-12
        # chanma.RefreshCChan(klu)


    # CBaoStock.do_close()
