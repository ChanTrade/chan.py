import logging
from Chan import CChan
from KLine.KLine_Unit import CKLine_Unit
import numpy as np
from Common.CEnum import BI_DIR
from Bi.Bi import CBi

class ChanMa:
    def __init__(self, cchan_instance: CChan, log_to_file=False):
        """
        Initialize the ChanMa class.

        :param cchan_instance: An instance of the CChan class to leverage its data handling capabilities.
        :param log_to_file: Boolean flag to determine if logs should be written to a file.
        """
        self.cchan = cchan_instance
        self.segment_cache = {}  # Initialize a cache for segment data
        self.cached_segments = {}  # Track cached segments to avoid duplicates
        self.current_segments = {}  # Store the current segment for each level
        self.ma_group_dict = {}  # Store the ma_group for each level and seg_idx

        # Initialize logger
        self.logger = logging.getLogger('ChanMaLogger')
        self.logger.setLevel(logging.INFO)

        # Set up logging handler based on the flag
        if log_to_file:
            handler = logging.FileHandler('chanma.log')
        else:
            handler = logging.StreamHandler()

        # Set logging format
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)

        # Add handler to the logger
        self.logger.addHandler(handler)
    
    def RefreshCChan(self, klu: CKLine_Unit):
        """
        Run the ChanMa Calculation.
        """
        self.logger.info(f"klu: {klu.Info()}")
        # Iterate through each time level in CChan instance
        for lv_list in self.cchan.lv_list:
            # Get the CKLine_List for current level
            kline_list = self.cchan[lv_list]
            # Refresh the segment cache
            self.RefreshSegmentCache(lv_list, kline_list)

    # Refresh the segment cache for a given level
    def RefreshSegmentCache(self, lv_idx, kline_list):
            seg_list = kline_list.seg_list
            # print each seg info
            for seg in seg_list:
                self.logger.info(f"seg: {seg}")
            return
            # Initialize cache and tracking set for this level if not present
            if lv_idx not in self.segment_cache:
                self.segment_cache[lv_idx] = []
                self.cached_segments[lv_idx] = set()
            
            # clean the self.current_segments for this level because those segments are not sure
            self.current_segments[lv_idx] = []

            # Process segments and cache the data
            for seg_idx, seg in enumerate(seg_list):
                start_bi = seg.start_bi
                end_bi = seg.end_bi
                direction = seg.dir
                segment_id = (start_bi.begin_klc.time_begin, end_bi.end_klc.time_end)

                # Check if the segment is already cached and only cache the sure segment
                if segment_id not in self.cached_segments[lv_idx] and seg.is_sure:
                    # Cache the segment data
                    self.segment_cache[lv_idx].append({
                        'seg_idx': seg_idx,
                        'start_time': start_bi.begin_klc.time_begin,
                        'end_time': end_bi.end_klc.time_end,
                        'direction': direction
                    })
                    # Add segment_id to the tracking set
                    self.cached_segments[lv_idx].add(segment_id)
                    # Process segment data as needed
                    self.logger.info(f"new Segment confirmed {lv_idx}-{seg_idx}:"
                                    f"{start_bi.begin_klc.time_begin} - {end_bi.end_klc.time_end}, Direction: {direction}")
                    
                                    # display all the bi info in seg bilist
                    for bi in seg.bi_list:
                        self.logger.info(f"seg: {seg_idx} bi: {CBi.Info(bi)}")

                elif not seg.is_sure:                        
                    # Update or create the current segment for this level
                    self.current_segments[lv_idx].append({
                        'seg_idx': seg_idx,
                        'start_time': start_bi.begin_klc.time_begin,
                        'end_time': end_bi.end_klc.time_end,
                        'direction': direction
                    })
                    self.logger.info(f"current Segment {lv_idx}-{seg_idx}:"
                                    f"{start_bi.begin_klc.time_begin} - {end_bi.end_klc.time_end}, Direction: {direction}, is_sure: {seg.is_sure}")
                else:
                    self.logger.info(f"skip Segment {lv_idx}-{seg_idx}:"
                                    f"{start_bi.begin_klc.time_begin} - {end_bi.end_klc.time_end}, Direction: {direction}")
                    pass

    def CalcMA(self, Chan: CChan, klu: CKLine_Unit): 
        '''
        Calculate the MA (Moving Average) for a given klu 
        '''
        # walk through each level of the segment_cache
        for lv_idx in self.segment_cache:
            # Log segment information from cache
            self.logger.info(f"Level {lv_idx} segments:")
            if lv_idx in self.segment_cache:
                for seg in self.segment_cache[lv_idx]:
                    self.logger.info(f"  Cached segment {seg['seg_idx']}: {seg['start_time']} - {seg['end_time']}, Direction: {seg['direction']}")
            
            # Log current (unsure) segments
            if lv_idx in self.current_segments and self.current_segments[lv_idx]:
                self.logger.info(f"Level {lv_idx} current segments:")
                for seg in self.current_segments[lv_idx]:
                    self.logger.info(f"  Current segment {seg['seg_idx']}: {seg['start_time']} - {seg['end_time']}, Direction: {seg['direction']}")

    def CalcMaSingle(self, lv_idx, seg_idx, bi_idx, klu):
        '''
        Calculate the MA (Moving Average) for a given klu 
        the MA is 4 numpy array for one lv_idx and one seg_idx

        It's not batch calculation, it's a single calculation.
        '''

        # display the seg/bi/klu info each line
        
        


        return 
        # check if the ma_group is already in the ma_group_dict
        if lv_idx in self.ma_group_dict and seg_idx in self.ma_group_dict[lv_idx] and bi_idx in self.ma_group_dict[lv_idx][seg_idx]:
            ma_group = self.ma_group_dict[lv_idx][seg_idx][bi_idx]
        else:
            ma_group = {    
                'ma_opens': np.array([]),
                'ma_highs': np.array([]),
                'ma_lows': np.array([]),
                'ma_closes': np.array([])
            }

        if len(ma_group['ma_opens']) == 0:
            '''
            if the ma_group is empty, append the klu data as the first MA data to the ma_group
            '''
            ma_group['ma_opens'].append(klu.open)
            ma_group['ma_highs'].append(klu.high)
            ma_group['ma_lows'].append(klu.low)
            ma_group['ma_closes'].append(klu.close)
        else:
            # Calculate the new MA values efficiently
            # Get the current count of items
            prev_count   = len(ma_group['ma_opens'])
            # Calculate the sum of all previous values
            prev_sum_open = ma_group['ma_opens'][-1] * prev_count
            prev_sum_high = ma_group['ma_highs'][-1] * prev_count
            prev_sum_low = ma_group['ma_lows'][-1] * prev_count
            prev_sum_close = ma_group['ma_closes'][-1] * prev_count

            # Add new value and calculate new average
            ma_open = (prev_sum_open + klu.open) / (prev_count + 1)
            ma_high = (prev_sum_high + klu.high) / (prev_count + 1)
            ma_low = (prev_sum_low + klu.low) / (prev_count + 1)
            ma_close = (prev_sum_close + klu.close) / (prev_count + 1)

            # cache the ma_group {ma_opens, ma_highs, ma_lows, ma_closes} for each klu
            ma_group['ma_opens'].append(ma_open)
            ma_group['ma_highs'].append(ma_high)
            ma_group['ma_lows'].append(ma_low)
            ma_group['ma_closes'].append(ma_close)

        self.ma_group_dict[lv_idx][seg_idx][bi_idx] = ma_group
        return ma_group


    def CalcMaBatch(self, lv_idx,seg_idx, start_time, end_time=None):
        """
        Calculate the MA (Moving Average) for a given time range, It's a batch calculation.

        :param lv_idx: The index of the time level in CChan instance.
        :param start_time: The start time of the time range.
        :param end_time: The end time of the time range.
        :return: The MA value.
        """
        # check if the ma_group is already in the ma_group_dict
        if lv_idx in self.ma_group_dict and seg_idx in self.ma_group_dict[lv_idx]:
            ma_group = self.ma_group_dict[lv_idx][seg_idx]
        else:
            ma_group = {
                'ma_opens': np.array([]),
                'ma_highs': np.array([]),
                'ma_lows': np.array([]),
                'ma_closes': np.array([])
            }
            self.ma_group_dict[lv_idx][seg_idx] = ma_group

        klu_list = self.cchan[lv_idx].klu_iter()

        # Filter klu_list based on time range
        filtered_klus = [klu for klu in klu_list if klu._time >= start_time and (end_time is None or klu._time <= end_time)]

        # Get OHLC data from filtered klu_list
        opens = np.array([klu.open for klu in filtered_klus])
        highs = np.array([klu.high for klu in filtered_klus])
        lows = np.array([klu.low for klu in filtered_klus])
        closes = np.array([klu.close for klu in filtered_klus])

        # Calculate cumulative sums
        cum_opens = np.cumsum(opens)
        cum_highs = np.cumsum(highs) 
        cum_lows = np.cumsum(lows)
        cum_closes = np.cumsum(closes)

        # Calculate moving averages using cumsum
        # Add 1 to avoid division by zero for first element
        indices = np.arange(1, len(filtered_klus) + 1)
        ma_opens = cum_opens / indices
        ma_highs = cum_highs / indices
        ma_lows = cum_lows / indices
        ma_closes = cum_closes / indices
        # append the ma_group to the ma_group_dict
        self.ma_group_dict[lv_idx][seg_idx] = {
            'ma_opens': ma_opens,
            'ma_highs': ma_highs,
            'ma_lows': ma_lows,
            'ma_closes': ma_closes
        }
        return self.ma_group_dict[lv_idx][seg_idx]

    # check if the value is in the range of the ma
    def CheckValRange(self, v, rate, ma):
        '''
        Check if the value is in the range of the ma
        '''
        upper_bound = ma * (1 + rate)
        down_bound = ma * (1 - rate)
        if down_bound <= v <= upper_bound:
            return True, upper_bound, down_bound
        else:
            return False, upper_bound, down_bound
        
    # check if the value is in the range of the klu bar
    def CheckBarRange(self, klu, ma):
        '''
        Check if the value is in the range of the klu bar
        '''
        upper_bound = klu.high
        down_bound = klu.low
        if down_bound <= ma <= upper_bound:
            return True, upper_bound, down_bound
        else:
            return False, upper_bound, down_bound

    def CheckSignal(self, lv_idx, seg_idx, klu):
        '''
        Check if the signal is in the range of the ma
        '''
        # get segment data from cache
        seg_data = self.segment_cache[lv_idx][seg_idx]
        start_time = seg_data['start_time']
        end_time = seg_data['end_time']
        direction = seg_data['direction']

        # calculate ma_klu {ma_open, ma_high, ma_low, ma_close} groups for this segment
        klu_ma_data = self.CalcMa(lv_idx, seg_idx, start_time, end_time)

        '''
        # Signal detection
        '''
        # Filter klu_list based on time range
        klu_list = self.cchan[lv_idx].klu_iter()
        filtered_klus = [klu for klu in klu_list 
                         if klu.time >= start_time and (end_time is None or klu.time <= end_time)]
        for i, klu in enumerate(filtered_klus):
            self.logger.debug(f"Time: {klu.time}, MA_Open: {klu_ma_data['ma_opens'][i]:.2f}, "
                            f"MA_High: {klu_ma_data['ma_highs'][i]:.2f}, "
                            f"MA_Low: {klu_ma_data['ma_lows'][i]:.2f}, "
                            f"MA_Close: {klu_ma_data['ma_closes'][i]:.2f}")
            # check if the value is in the range of the ma
            IsInRange,up,down = self.CheckValRange(klu.low, 0.005, 
                                                  klu_ma_data['ma_lows'][i])
            if IsInRange and i > 10 and direction == BI_DIR.UP:
                self.logger.info(f"signal low - LT:{i} TIme: {klu.time} , "
                                f"{klu_ma_data['ma_lows'][i]:.3f} - {down:.3f} <= "
                                f"klu.low {klu.low:.3f} <= {up:.3f}")
            IsInRange,up,down = self.CheckValRange(klu.high, 0.005, 
                                                  klu_ma_data['ma_highs'][i]) 
            if IsInRange and i > 10 and direction == BI_DIR.DOWN:
                self.logger.info(f"signal high - HT:{i} TIme: {klu.time} , "
                                f"{klu_ma_data['ma_highs'][i]:.3f} - {down:.3f} <= "
                                f"klu.high {klu.high:.3f} <= {up:.3f}")

            # check if the value is in the range of the klu bar
            IsInRange,up,down = self.CheckBarRange(klu, klu_ma_data['ma_lows'][i])
            if IsInRange and i > 10 and direction == BI_DIR.UP:
                self.logger.info(f"[in kbar] signal low - LT:{i} TIme: {klu.time} , "
                                f"{klu_ma_data['ma_lows'][i]:.3f} - {down:.3f} <= "
                                f"klu.low {klu.low:.3f} <= {up:.3f}")
            IsInRange,up,down = self.CheckBarRange(klu, klu_ma_data['ma_highs'][i])
            if IsInRange and i > 10 and direction == BI_DIR.DOWN:
                self.logger.info(f"[in kbar] signal high - HT:{i} TIme: {klu.time} , "
                                f"{klu_ma_data['ma_highs'][i]:.3f} - {down:.3f} <= "
                                f"klu.high {klu.high:.3f} <= {up:.3f}")


