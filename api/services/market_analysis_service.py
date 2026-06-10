"""
大盘智能分析服务
金银手指 + 智能图谱 + 阳谱阴谱
数据源: tushare (指数日K + 个股资金流)
"""

import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta


def _get_tushare_pro():
    import tushare as ts
    token = "23651a8611b00bf491c7378d81d0bc6265543153530194be989e6ada"
    ts.set_token(token)
    return ts.pro_api()


def _fetch_index_kline(pro, days: int = 730) -> pd.DataFrame:
    end = datetime.now().strftime('%Y%m%d')
    start = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
    df = pro.index_daily(ts_code='000001.SH', start_date=start, end_date=end)
    if df is None or df.empty:
        return pd.DataFrame()
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.sort_values('trade_date').set_index('trade_date')
    return df[['open', 'high', 'low', 'close', 'vol']]


def _fetch_stock_moneyflow(pro, symbol: str, days: int = 730) -> pd.DataFrame:
    if not symbol.endswith(('.SH', '.SZ')):
        suffix = '.SH' if symbol.startswith(('5', '6', '9')) else '.SZ'
        ts_code = symbol + suffix
    else:
        ts_code = symbol
    end = datetime.now().strftime('%Y%m%d')
    start = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
    df = pro.moneyflow(ts_code=ts_code, start_date=start, end_date=end)
    if df is None or df.empty:
        return pd.DataFrame()
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.sort_values('trade_date').set_index('trade_date')
    return df


def _fetch_stock_kline(pro, symbol: str, days: int = 730) -> pd.DataFrame:
    import tushare as ts
    if not symbol.endswith(('.SH', '.SZ')):
        suffix = '.SH' if symbol.startswith(('5', '6', '9')) else '.SZ'
        ts_code = symbol + suffix
    else:
        ts_code = symbol
    end = datetime.now().strftime('%Y%m%d')
    start = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
    df = ts.pro_bar(ts_code=ts_code, adj='qfq', start_date=start, end_date=end)
    if df is None or df.empty:
        return pd.DataFrame()
    df['trade_date'] = pd.to_datetime(df['trade_date'])
    df = df.sort_values('trade_date').set_index('trade_date')
    if 'vol' in df.columns:
        df = df.rename(columns={'vol': 'volume'})
    return df[['open', 'high', 'low', 'close', 'volume']]


def _calc_smart_chart(idx_df: pd.DataFrame) -> pd.DataFrame:
    c1 = idx_df['close']
    m5 = c1.rolling(5).mean()
    m34 = c1.rolling(34).mean()

    bullish_day = (c1 > idx_df['open']).astype(int)
    r5 = bullish_day.rolling(5).sum()
    r6 = bullish_day.rolling(6).sum()

    a1 = (c1 < c1.shift(2) * 1.0200).astype(int)
    a2 = (c1 < c1.shift(2) * 1.0050).astype(int)
    a3 = (c1 < c1.shift(2) * 0.985).astype(int)
    a4 = (c1 < c1.shift(2) * 0.970).astype(int)

    diff_approx = r5.rolling(2).mean() - r5.rolling(4).mean()
    diff2_approx = r5.rolling(6).mean() - r5.rolling(12).mean()

    a5 = (diff_approx > 0).astype(int) * 2
    a6 = (diff2_approx > 0).astype(int) * 2
    a7 = (c1 > m34).astype(int) * 2
    a8 = (c1 > m5).astype(int) * 2
    a9 = (r5 > 3).astype(int) * 2
    a10 = (r6 > 3).astype(int)

    az = a1 + a2 + a3 + a4 + a5 + a6 + a7 + a8 + a9 + a10

    green = pd.Series(0, index=idx_df.index, dtype=int)
    red = pd.Series(0, index=idx_df.index, dtype=int)

    for i in range(len(idx_df)):
        if c1.iloc[i] < m5.iloc[i]:
            green.iloc[i] = 1
        elif az.iloc[i] > 2.5:
            red.iloc[i] = 1
        else:
            green.iloc[i] = 1

    window = 20
    yang_pct = red.rolling(window).sum() / window * 100
    yin_pct = green.rolling(window).sum() / window * 100

    return pd.DataFrame({
        'close': c1, 'm5': m5, 'm34': m34,
        'az': az, 'red': red, 'green': green,
        'yang_pct': yang_pct, 'yin_pct': yin_pct,
    }, index=idx_df.index)


def _calc_gold_silver_finger(mf: pd.DataFrame) -> pd.DataFrame:
    b1 = mf['buy_sm_vol']
    b2 = mf['sell_sm_vol']
    gold = (b1 < b2) & (b1.shift(1) >= b2.shift(1))
    silver = (b1 > b2) & (b1.shift(1) <= b2.shift(1))
    net_inflow = b1 > b2
    return pd.DataFrame({
        'b1': b1, 'b2': b2,
        'net_inflow': net_inflow,
        'gold_finger': gold, 'silver_finger': silver,
    }, index=mf.index)


# 内存缓存 (stock_date -> result, 5分钟TTL)
_cache: Dict[str, tuple] = {}
_CACHE_TTL = 300  # 秒

def _parallel_fetch(ak_symbol, full_symbol, date):
    """并行拉取三个数据源"""
    import os, json
    import requests as req
    import akshare as ak
    from concurrent.futures import ThreadPoolExecutor, as_completed

    for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        os.environ.pop(k, None)

    pro = _get_tushare_pro()
    results = {'tick': None, 'mf': None, 'k5': None, 'error': None}

    def fetch_tick():
        t = ak.stock_zh_a_tick_tx_js(symbol=ak_symbol)
        t.columns = ['time', 'price', 'price_chg', 'volume', 'amount', 'nature']
        t['time_dt'] = pd.to_datetime(f'{date} ' + t['time'])
        t = t[t['time'] >= '09:30:00'].sort_values('time_dt').reset_index(drop=True)
        t['time_sec'] = t['time_dt'].astype('int64') / 1e9
        return t

    def fetch_mf():
        return pro.moneyflow(ts_code=full_symbol, start_date=date.replace('-', ''), end_date=date.replace('-', ''))

    def fetch_k5():
        session = req.Session()
        session.trust_env = False
        r = session.get(
            'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData',
            params={'symbol': ak_symbol, 'scale': 5, 'ma': 'no', 'datalen': 100}, timeout=10)
        k5 = pd.DataFrame(json.loads(r.text))
        k5['time'] = pd.to_datetime(k5['day'])
        for c in ['open', 'high', 'low', 'close', 'volume']:
            k5[c] = k5[c].astype(float)
        return k5[k5['time'].dt.date == pd.to_datetime(date).date()].sort_values('time')

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(fetch_tick): 'tick',
            pool.submit(fetch_mf): 'mf',
            pool.submit(fetch_k5): 'k5',
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                if key == 'tick':
                    results['error'] = f'逐笔数据获取失败: {e}'

    return results


def analyze_dark_pool(symbol: str, date: str = None) -> Dict[str, Any]:
    """v4盘面资金分析: 机构参与度 + 尾盘异动 + 拆单检测"""
    import os, json
    import requests as req

    for k in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
        os.environ.pop(k, None)

    if not date:
        date = datetime.now().strftime('%Y-%m-%d')

    # 股票代码格式
    symbol_raw = symbol.replace('.SZ', '').replace('.SH', '').replace('sz', '').replace('sh', '')
    if symbol.endswith('.SZ') or symbol.startswith(('0', '3')):
        full_symbol = f'{symbol_raw}.SZ'
        ak_symbol = f'sz{symbol_raw}'
    else:
        full_symbol = f'{symbol_raw}.SH'
        ak_symbol = f'sh{symbol_raw}'

    # 检查缓存
    cache_key = f'{full_symbol}_{date}'
    if cache_key in _cache:
        cached_result, cached_time = _cache[cache_key]
        if datetime.now().timestamp() - cached_time < _CACHE_TTL:
            return cached_result

    result = {
        'symbol': full_symbol,
        'name': '',
        'date': date,
        'dim1_institutional': {},
        'dim2_tail': {},
        'dim3_split': {},
        'composite': {},
        'error': None,
    }

    # ==== 并行拉取数据 ====
    fetched = _parallel_fetch(ak_symbol, full_symbol, date)
    if fetched['error']:
        result['error'] = fetched['error']
        return result

    tick = fetched['tick']
    mf_data = fetched['mf']
    today_k5 = fetched['k5']

    TOTAL_VOL = int(tick['volume'].sum())
    TOTAL_AMT = int(tick['amount'].sum())

    tick_buy = tick[tick['nature'] == '买盘']['amount'].sum()
    tick_sell = tick[tick['nature'] == '卖盘']['amount'].sum()
    tick_net = tick_buy - tick_sell

    # ==== 2. 资金流向 (已并行预取) ====
    use_mf = mf_data is not None and len(mf_data) > 0

    if use_mf:
        # Tushare moneyflow 金额单位已是万元
        mf_row = mf_data.iloc[0]
        inst_buy = mf_row['buy_lg_amount'] + mf_row['buy_elg_amount']
        inst_sell = mf_row['sell_lg_amount'] + mf_row['sell_elg_amount']
        inst_net = inst_buy - inst_sell
        retail_buy = mf_row['buy_sm_amount'] + mf_row['buy_md_amount']
        retail_sell = mf_row['sell_sm_amount'] + mf_row['sell_md_amount']
        retail_net = retail_buy - retail_sell
        total_mf = inst_buy + inst_sell + retail_buy + retail_sell
        inst_pct = (inst_buy + inst_sell) / total_mf * 100 if total_mf > 0 else 0
    else:
        # 逐笔成交 fallback，amount 单位为元，统一转为万
        big_t = tick[tick['volume'] >= 100]
        inst_buy = big_t[big_t['nature'] == '买盘']['amount'].sum() / 10000
        inst_sell = big_t[big_t['nature'] == '卖盘']['amount'].sum() / 10000
        inst_net = inst_buy - inst_sell
        small_t = tick[tick['volume'] < 100]
        retail_buy = small_t[small_t['nature'] == '买盘']['amount'].sum() / 10000
        retail_sell = small_t[small_t['nature'] == '卖盘']['amount'].sum() / 10000
        retail_net = retail_buy - retail_sell
        total_mf = inst_buy + inst_sell + retail_buy + retail_sell
        inst_pct = (inst_buy + inst_sell) / total_mf * 100 if total_mf > 0 else 0

    # 大单主动买/卖，tick amount 为元，统一转为万
    big_active_buy = tick[(tick['volume'] >= 100) & (tick['nature'] == '买盘')]['amount'].sum() / 10000
    big_active_sell = tick[(tick['volume'] >= 100) & (tick['nature'] == '卖盘')]['amount'].sum() / 10000

    # ==== 3. 5分钟K线 (已并行预取) ====
    if today_k5 is not None and len(today_k5) > 0:
        day_open = today_k5['open'].iloc[0]
        day_close = today_k5['close'].iloc[-1]
        day_high = today_k5['high'].max()
        day_low = today_k5['low'].min()
        full_pct = (day_close - day_open) / day_open * 100

        tail = today_k5.tail(3)
        tail_vol = tail['volume'].sum()
        tail_pct = (tail['close'].iloc[-1] - tail['open'].iloc[0]) / tail['open'].iloc[0] * 100
        day_vol_k5 = today_k5['volume'].sum()
        tail_vol_ratio = tail_vol / day_vol_k5 * 100
    else:
        day_open = tick['price'].iloc[0]
        day_close = tick['price'].iloc[-1]
        day_high = tick['price'].max()
        day_low = tick['price'].min()
        full_pct = (day_close - day_open) / day_open * 100
        tail_vol_ratio = 0
        tail_pct = 0
        today_k5 = pd.DataFrame()

    # ==== 维度一: 机构参与度 ====
    if inst_net > 0 and full_pct < 0:
        intent = '机构逆势净买 -> 压价吃货，偏多'
    elif inst_net < 0 and full_pct > 0:
        intent = '机构逆势净卖 -> 出货，偏空'
    elif inst_net > 0:
        intent = '机构顺势净买'
    elif inst_net < 0:
        intent = '机构顺势净卖'
    else:
        intent = '机构中性'

    result['dim1_institutional'] = {
        'inst_participation_pct': round(inst_pct, 1),
        'inst_net_wan': int(round(inst_net)),
        'retail_net_wan': int(round(retail_net)),
        'tick_net_wan': int(round(tick_net / 10000)),
        'big_active_buy_wan': int(round(big_active_buy)),
        'big_active_sell_wan': int(round(big_active_sell)),
        'intent': intent,
    }

    # ==== 维度二: 尾盘异动 ====
    if tail_vol_ratio > 12 and abs(tail_pct) > 0.3:
        tail_signal = '尾盘放量买入' if tail_pct > 0 else '尾盘放量卖出'
    elif abs(tail_pct) > abs(full_pct) * 0.5 and abs(tail_pct) > 0.2:
        tail_signal = '尾盘资金有意图'
    else:
        tail_signal = '尾盘正常'

    result['dim2_tail'] = {
        'tail_vol_ratio_pct': round(tail_vol_ratio, 1),
        'tail_chg_pct': round(tail_pct, 2),
        'full_chg_pct': round(full_pct, 2),
        'signal': tail_signal,
    }

    # ==== 维度三: v4拆单检测 ====
    MORNING_CUT = pd.to_datetime(f'{date} 09:33:00')
    TAIL_CUT = pd.to_datetime(f'{date} 14:58:00')
    tick_core = tick[(tick['time_dt'] >= MORNING_CUT) & (tick['time_dt'] <= TAIL_CUT)].reset_index(drop=True)

    WINDOW, MIN_EVENTS, STEP = 20, 14, 5
    split_events = []

    for i in range(0, len(tick_core) - WINDOW, STEP):
        win = tick_core.iloc[i:i + WINDOW]
        gaps = np.diff(win['time_sec'].values)
        gap_mean, gap_std = gaps.mean(), gaps.std()
        if gap_mean > 10 or gap_std > 4:
            continue
        prices = win['price'].values
        price_range = (prices.max() - prices.min()) / prices.mean()
        if price_range > 0.005:
            continue
        vols = win['volume'].values
        vmask = (vols >= 5) & (vols <= 100)
        if vmask.sum() < MIN_EVENTS:
            continue
        vv = vols[vmask]
        vol_cv = vv.std() / vv.mean()
        if vol_cv > 0.8:
            continue
        dirs = win.loc[win.index[vmask], 'nature']
        main_dir = dirs.mode().iloc[0]
        dir_purity = (dirs == main_dir).sum() / len(dirs)
        if dir_purity < 0.60:
            continue

        base_score = 0
        if gap_std < 2.0: base_score += 2
        elif gap_std < 3.5: base_score += 1
        if price_range < 0.002: base_score += 2
        elif price_range < 0.005: base_score += 1
        if vol_cv < 0.4: base_score += 2
        elif vol_cv < 0.7: base_score += 1
        if dir_purity > 0.80: base_score += 2
        elif dir_purity > 0.65: base_score += 1

        split_events.append({
            'start': win['time'].iloc[0], 'end': win['time'].iloc[-1],
            'vol': int(win['volume'].sum()), 'amt': int(win['amount'].sum()),
            'dir': main_dir, 'base_score': base_score,
            'gap_std': round(gap_std, 1), 'price_r': round(price_range * 100, 2),
            'vmean': round(vv.mean(), 0), 'dir_purity': round(dir_purity * 100, 0),
            'vol_cv': round(vol_cv, 2),
            't0': win['time_dt'].iloc[0], 't1': win['time_dt'].iloc[-1],
        })

    # 去重
    events_unique = []
    last_end_t = ''
    for ev in sorted(split_events, key=lambda x: x['start']):
        if not last_end_t or ev['start'] >= last_end_t:
            events_unique.append(ev)
            last_end_t = ev['end']

    # 质量评分
    for ev in events_unique:
        ev['duration_min'] = round((ev['t1'] - ev['t0']).total_seconds() / 60, 1)
        mid_t = ev['t0'] + (ev['t1'] - ev['t0']) / 2
        mid_pos = (tick_core['time_dt'] - mid_t).abs().idxmin()
        w0 = max(0, mid_pos - 40)
        w1 = min(len(tick_core), w0 + 80)
        ext = tick_core.iloc[w0:w1]
        evols = ext['volume'].values
        eprices = ext['price'].values
        fmask = (evols > 5) & (evols <= 100)
        efvols = evols[fmask]
        efprices = eprices[fmask]
        edirs = ext.iloc[fmask]['nature'] if fmask.sum() > 10 else ext['nature']

        # h1: 手数集中
        if len(efvols) >= 10:
            s = np.sort(efvols)
            span = max(int(len(s) * 0.85), 1)
            min_r = min(s[i + span - 1] - s[i] for i in range(len(s) - span + 1))
            vratio = efvols.max() / efvols.min() if efvols.min() > 0 else 999
            h1 = 3 if (min_r <= 50 and vratio <= 5) else (1 if min_r <= 100 else 0)
        else:
            h1 = 0

        # h2: 时间间隔
        egaps = np.diff(ext['time_sec'].values)
        in_range = ((egaps >= 0) & (egaps <= 8)).sum() / len(egaps) if len(egaps) > 0 else 0
        long_r = (egaps > 10).sum() / len(egaps) if len(egaps) > 0 else 1
        h2 = 3 if (in_range >= 0.80 and egaps.std() < 4 and long_r < 0.15) else (1 if in_range >= 0.65 else 0)

        # h3: 价格聚类
        if len(efprices) >= 2:
            pspan = efprices.max() - efprices.min()
            mode_p = pd.Series(efprices).mode().iloc[0]
            near = (abs(efprices - mode_p) <= 0.02).sum() / len(efprices)
            h3 = 3 if (pspan <= 0.05 and near >= 0.75) else (1 if pspan <= 0.12 else 0)
        else:
            h3 = 0

        # h4: 方向一致
        dcnt = edirs.value_counts()
        dp = dcnt.iloc[0] / len(edirs) if len(dcnt) > 0 else 0
        h4 = 3 if dp > 0.80 else (1 if dp > 0.65 else 0)

        # h5: 放量滞价
        h5 = 0
        if len(today_k5) >= 1:
            kb = today_k5[(today_k5['time'] >= ev['t0'] - pd.Timedelta(minutes=5)) &
                           (today_k5['time'] <= ev['t1'])]
            if len(kb) >= 1:
                k5m = today_k5['volume'].mean()
                hv = (kb['volume'] > k5m * 1.2).any()
                amps = abs(kb['close'] - kb['open']) / kb['open']
                flat = (amps < 0.005).any()
                if hv and flat: h5 = 2
                elif hv or flat: h5 = 1

        quality_score = h1 + h2 + h3 + h4 + h5
        ev['quality_score'] = quality_score
        ev['indicators'] = f'手{h1}/3 时{h2}/3 价{h3}/3 向{h4}/3 量{h5}/2'

    # 二次验证
    for i, ev in enumerate(events_unique):
        if i + 1 < len(events_unique):
            next_ev = events_unique[i + 1]
            t_gap = (next_ev['t0'] - ev['t1']).total_seconds()
            if t_gap < 180 and ev['dir'] == next_ev['dir']:
                ev['quality_score'] += 2

    # 暗盘过滤
    import re as re_m
    filtered = []
    for ev in events_unique:
        m = re_m.search(r'价(\d)/3', ev['indicators'])
        h3_score = int(m.group(1)) if m else 0
        if h3_score == 0:
            continue
        mid_t = ev['t0'] + (ev['t1'] - ev['t0']) / 2
        mid_pos = (tick_core['time_dt'] - mid_t).abs().idxmin()
        w0 = max(0, mid_pos - 40)
        w1 = min(len(tick_core), w0 + 80)
        ext2 = tick_core.iloc[w0:w1]
        xvols = ext2['volume'].values
        xprices = ext2['price'].values
        tiny_r = (xvols <= 5).sum() / len(xvols) if len(xvols) > 0 else 0
        if tiny_r > 0.30:
            continue
        if len(xprices) > 1 and abs(xprices[-1] - xprices[0]) / xprices[0] > 0.008:
            continue
        if ev['duration_min'] < 1.0 and ev['quality_score'] < 7:
            continue
        filtered.append(ev)

    events_unique = filtered
    high_conf = [e for e in events_unique if e['quality_score'] >= 9]
    suspected = [e for e in events_unique if 6 <= e['quality_score'] < 9]

    split_vol = sum(e['vol'] for e in events_unique)
    active_vol = sum(e['vol'] for e in events_unique if e['dir'] == '买盘')
    passive_vol = sum(e['vol'] for e in events_unique if e['dir'] == '卖盘')

    dark_events = []
    for e in sorted(events_unique, key=lambda x: x['quality_score'], reverse=True):
        dark_events.append({
            'start': e['start'], 'end': e['end'],
            'duration_min': e['duration_min'],
            'direction': '买' if e['dir'] == '买盘' else '卖',
            'volume': e['vol'],
            'base_score': e['base_score'],
            'quality_score': e['quality_score'],
            'level': '暗盘' if e['quality_score'] >= 9 else ('疑似' if e['quality_score'] >= 6 else '低分'),
            'indicators': e['indicators'],
        })

    direction = '买偏多' if active_vol > passive_vol * 1.5 else ('卖偏多' if passive_vol > active_vol * 1.5 else '均衡')

    result['dim3_split'] = {
        'total_events': len(events_unique),
        'high_conf_count': len(high_conf),
        'suspected_count': len(suspected),
        'split_vol': split_vol,
        'split_vol_pct': round(split_vol / TOTAL_VOL * 100, 2),
        'active_buy_vol': active_vol,
        'active_sell_vol': passive_vol,
        'direction': direction,
        'events': dark_events,
    }

    # ==== 综合 ====
    conf = 0
    signals = []

    if inst_net > 0 and full_pct < 0:
        signals.append('机构逆势净买')
        conf += 3
    elif inst_net > 0:
        signals.append('机构顺势净买')
        conf += 2
    elif inst_net < 0 and full_pct > 0:
        signals.append('机构逆势净卖')
        conf -= 3
    elif inst_net < 0:
        signals.append('机构顺势净卖')
        conf -= 2

    if tail_pct > 0 and tail_vol_ratio > 10:
        signals.append('尾盘放量买入')
        conf += 2
    elif tail_pct < -0.3 and tail_vol_ratio > 10:
        signals.append('尾盘放量卖出')
        conf -= 2

    if passive_vol > active_vol * 1.5:
        signals.append('拆单偏卖')
        conf -= 2
    elif active_vol > passive_vol * 1.5:
        signals.append('拆单偏买')
        conf += 2

    if len(high_conf) > 0:
        buy_conf = sum(1 for e in high_conf if e['dir'] == '买盘')
        sell_conf = sum(1 for e in high_conf if e['dir'] == '卖盘')
        signals.append(f'暗盘{buy_conf}买{sell_conf}卖')
        if buy_conf > sell_conf: conf += 2
        elif sell_conf > buy_conf: conf -= 2

    if conf >= 5: verdict = '强烈偏多'
    elif conf >= 2: verdict = '中性偏多'
    elif conf >= -1: verdict = '中性/观望'
    elif conf >= -4: verdict = '中性偏空'
    else: verdict = '偏空'

    # ==== 主力意图推断 ====
    dark_buy = sum(e['vol'] for e in events_unique if e.get('quality_score', 0) >= 6 and e['dir'] == '买盘')
    dark_sell = sum(e['vol'] for e in events_unique if e.get('quality_score', 0) >= 6 and e['dir'] == '卖盘')
    has_dark = len(high_conf) > 0 or len(suspected) > 0

    # 主力意图
    if inst_net > 0 and full_pct < -0.5 and has_dark:
        intent_narrative = '主力趁跌暗中吸筹。价跌但机构净买，同时检测到拆单痕迹（隐藏大单意图），典型压价吃货模式。'
    elif inst_net > 0 and full_pct < 0 and not has_dark:
        intent_narrative = '机构逆势承接。价跌但机构净买，可能在维护股价或低位建仓，但未检测到明显拆单行为。'
    elif inst_net < 0 and full_pct > 0.5 and has_dark:
        intent_narrative = '主力趁涨暗中出货。价涨但机构净卖，同时检测到拆单痕迹（隐藏抛售意图），典型拉高出货模式。'
    elif inst_net < 0 and full_pct > 0 and not has_dark:
        intent_narrative = '机构借反弹减仓。价涨但机构净卖，可能在逐步撤退，但未检测到明显拆单行为。'
    elif inst_net > 0 and full_pct >= 0:
        intent_narrative = '机构顺势做多。价涨且机构净买，属于正常的趋势跟随，非隐藏行为。'
    elif inst_net < 0 and full_pct <= 0:
        intent_narrative = '机构顺势撤退。价跌且机构净卖，属于正常的趋势跟随，非隐藏行为。'
    else:
        intent_narrative = '机构动向不明确，多空力量均衡，建议观望。'

    # 短期预测
    if conf >= 5:
        if inst_net > 0:
            prediction = '短期偏多，若明日继续放量可确认反转，关注开盘量能。'
        else:
            prediction = '短期偏多，信号共振强烈，关注次日能否高开确认。'
    elif conf >= 2:
        prediction = '短期中性偏多，有建仓迹象但力度不够，需观察1-2日确认。'
    elif conf >= -1:
        prediction = '短期方向不明，多空信号混杂，建议观望等待更明确信号。'
    elif conf >= -4:
        prediction = '短期中性偏空，有撤退痕迹但未形成趋势，注意风控。'
    else:
        prediction = '短期偏空，多重信号共振看跌，建议减仓或回避。'

    # 关键数据摘要
    key_facts = []
    key_facts.append(f'机构净主动{inst_net/10000:+.0f}万{"（逆势）" if (inst_net>0 and full_pct<0) or (inst_net<0 and full_pct>0) else ""}')
    key_facts.append(f'全日{full_pct:+.2f}%')
    if has_dark:
        key_facts.append(f'暗盘拆单{dark_buy}手买/{dark_sell}手卖')
    if tail_vol_ratio > 8:
        key_facts.append(f'尾盘占比{tail_vol_ratio:.0f}%{tail_pct:+.2f}%')

    result['composite'] = {
        'signals': signals,
        'confidence': conf,
        'verdict': verdict,
        'intent': intent_narrative,
        'prediction': prediction,
        'key_facts': key_facts,
    }

    # 基础行情
    result['name'] = ak_symbol  # 先放代码，前端可以查名称
    result['market'] = {
        'open': round(float(day_open), 2),
        'high': round(float(day_high), 2),
        'low': round(float(day_low), 2),
        'close': round(float(day_close), 2),
        'chg_pct': round(float(full_pct), 2),
        'total_vol': TOTAL_VOL,
        'total_amt_wan': round(TOTAL_AMT / 10000, 0),
        'tick_count': len(tick),
    }

    # 写入缓存
    _cache[cache_key] = (result, datetime.now().timestamp())
    return result


def analyze_market(symbol: str = "600938", days: int = 730) -> Dict[str, Any]:
    pro = _get_tushare_pro()

    idx_df = _fetch_index_kline(pro, days)
    stock_mf = _fetch_stock_moneyflow(pro, symbol, days)
    stock_kline = _fetch_stock_kline(pro, symbol, days)

    if idx_df.empty or stock_mf.empty:
        return {"error": "数据获取失败"}

    common = idx_df.index.intersection(stock_mf.index).intersection(stock_kline.index) if not stock_kline.empty else idx_df.index.intersection(stock_mf.index)
    idx_df = idx_df.loc[common]
    stock_mf = stock_mf.loc[common]
    if not stock_kline.empty:
        stock_kline = stock_kline.loc[common]

    sc = _calc_smart_chart(idx_df)
    gs = _calc_gold_silver_finger(stock_mf)

    # 金手指后N日涨跌
    finger_stats = {}
    for ft_name, ft_mask in [('gold', gs['gold_finger']), ('silver', gs['silver_finger'])]:
        stats = {}
        for hold_days in [1, 3, 5]:
            returns = []
            for d in gs[ft_mask].index:
                idx_pos = stock_kline.index.get_loc(d) if not stock_kline.empty else -1
                if idx_pos >= 0 and idx_pos + hold_days < len(stock_kline):
                    future_p = stock_kline['close'].iloc[idx_pos + hold_days]
                    curr_p = stock_kline['close'].iloc[idx_pos]
                    returns.append(round((future_p / curr_p - 1) * 100, 2))
            if returns:
                stats[str(hold_days)] = {
                    "avg_return": round(float(np.mean(returns)), 2),
                    "win_rate": round(sum(1 for r in returns if (r > 0 if ft_name == 'gold' else r < 0)) / len(returns) * 100, 1),
                    "count": len(returns),
                }
        finger_stats[ft_name] = stats

    # K线数据 (上证指数)
    kline_data = []
    for d in idx_df.index:
        row = {"date": d.strftime("%Y-%m-%d")}
        row["open"] = round(float(idx_df.loc[d, 'open']), 2)
        row["high"] = round(float(idx_df.loc[d, 'high']), 2)
        row["low"] = round(float(idx_df.loc[d, 'low']), 2)
        row["close"] = round(float(idx_df.loc[d, 'close']), 2)
        if d in sc.index:
            row["m5"] = round(float(sc.loc[d, 'm5']), 2) if pd.notna(sc.loc[d, 'm5']) else None
            row["m34"] = round(float(sc.loc[d, 'm34']), 2) if pd.notna(sc.loc[d, 'm34']) else None
            row["zone"] = "red" if sc.loc[d, 'red'] == 1 else "green"
            row["az"] = round(float(sc.loc[d, 'az']), 1) if pd.notna(sc.loc[d, 'az']) else None
            row["yang_pct"] = round(float(sc.loc[d, 'yang_pct']), 1) if pd.notna(sc.loc[d, 'yang_pct']) else None
            row["yin_pct"] = round(float(sc.loc[d, 'yin_pct']), 1) if pd.notna(sc.loc[d, 'yin_pct']) else None
        if d in gs.index:
            row["gold_finger"] = bool(gs.loc[d, 'gold_finger'])
            row["silver_finger"] = bool(gs.loc[d, 'silver_finger'])
        kline_data.append(row)

    # 当前状态
    last_date = idx_df.index[-1]
    last_sc = sc.iloc[-1]
    last_gs = gs.iloc[-1]

    status = {
        "date": last_date.strftime("%Y-%m-%d"),
        "index_close": round(float(last_sc['close']), 2),
        "zone": "red" if last_sc['red'] == 1 else "green",
        "az": round(float(last_sc['az']), 1),
        "yang_pct": round(float(last_sc['yang_pct']), 1) if pd.notna(last_sc['yang_pct']) else None,
        "yin_pct": round(float(last_sc['yin_pct']), 1) if pd.notna(last_sc['yin_pct']) else None,
        "stock_close": round(float(stock_kline['close'].iloc[-1]), 2) if not stock_kline.empty else None,
        "net_inflow": bool(last_gs['net_inflow']),
        "gold_finger": bool(last_gs['gold_finger']),
        "silver_finger": bool(last_gs['silver_finger']),
    }

    # 信号统计
    signal_stats = {
        "gold_count": int(gs['gold_finger'].sum()),
        "silver_count": int(gs['silver_finger'].sum()),
        "red_days": int(sc['red'].sum()),
        "green_days": int(sc['green'].sum()),
    }

    # 金手指买→银手指卖 配对回测
    trades = []
    position = None
    for i in range(len(stock_kline)):
        d = stock_kline.index[i]
        close = stock_kline['close'].iloc[i]
        if d in gs.index:
            if gs.loc[d, 'gold_finger'] and position is None:
                position = {'entry_date': d, 'entry_price': close}
            elif gs.loc[d, 'silver_finger'] and position is not None:
                pnl = round((close / position['entry_price'] - 1) * 100, 2)
                trades.append({
                    "entry_date": position['entry_date'].strftime("%Y-%m-%d"),
                    "exit_date": d.strftime("%Y-%m-%d"),
                    "entry_price": round(float(position['entry_price']), 2),
                    "exit_price": round(float(close), 2),
                    "pnl_pct": pnl,
                    "holding_days": (d - position['entry_date']).days,
                })
                position = None

    wins = sum(1 for t in trades if t['pnl_pct'] > 0)
    trade_stats = {
        "total": len(trades),
        "wins": wins,
        "losses": len(trades) - wins,
        "win_rate": round(wins / len(trades) * 100, 1) if trades else 0,
        "avg_pnl": round(float(np.mean([t['pnl_pct'] for t in trades])), 2) if trades else 0,
        "trades": trades[-20:],  # 最近20笔
    }

    return {
        "status": status,
        "signal_stats": signal_stats,
        "finger_stats": finger_stats,
        "trade_stats": trade_stats,
        "kline": kline_data,
    }
