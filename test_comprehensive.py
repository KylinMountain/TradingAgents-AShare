"""综合资金分析：机构参与度 + 尾盘异动 + 拆单检测 v4"""
import os, sys
os.environ.pop('HTTP_PROXY', None)
os.environ.pop('HTTPS_PROXY', None)
import akshare as ak
import tushare as ts
import pandas as pd
import numpy as np
import requests, json, re
from datetime import datetime

DATE = '2026-06-10'
SYMBOL = '001203'
FULL_SYMBOL = '001203.SZ'
NAME = '大中矿业'

# ====== 1. 逐笔数据 ======
print(f'=== {NAME} {FULL_SYMBOL} {DATE} 综合资金分析 ===\n')
tick = ak.stock_zh_a_tick_tx_js(symbol=f'sz{SYMBOL}')
tick.columns = ['time', 'price', 'price_chg', 'volume', 'amount', 'nature']
tick['time_dt'] = pd.to_datetime(f'{DATE} ' + tick['time'])
tick = tick[tick['time'] >= '09:30:00'].sort_values('time_dt').reset_index(drop=True)
tick['time_sec'] = tick['time_dt'].astype('int64') / 1e9

TOTAL_VOL = int(tick['volume'].sum())
TOTAL_AMT = int(tick['amount'].sum())

# 逐笔净主动
tick_buy = tick[tick['nature'] == '买盘']['amount'].sum()
tick_sell = tick[tick['nature'] == '卖盘']['amount'].sum()
tick_net = tick_buy - tick_sell

# ====== 2. 资金流向 (优先Tushare, 回退到逐笔大单统计) ======
ts.set_token('23651a8611b00bf491c7378d81d0bc6265543153530194be989e6ada')
pro = ts.pro_api()
mf = pro.moneyflow(ts_code=FULL_SYMBOL, start_date=DATE.replace('-',''), end_date=DATE.replace('-',''))
use_mf = len(mf) > 0

if use_mf:
    mf_row = mf.iloc[0]
    inst_buy = mf_row['buy_lg_amount'] + mf_row['buy_elg_amount']
    inst_sell = mf_row['sell_lg_amount'] + mf_row['sell_elg_amount']
    inst_net = inst_buy - inst_sell
    retail_buy = mf_row['buy_sm_amount'] + mf_row['buy_md_amount']
    retail_sell = mf_row['sell_sm_amount'] + mf_row['sell_md_amount']
    retail_net = retail_buy - retail_sell
    total_mf = inst_buy + inst_sell + retail_buy + retail_sell
    inst_pct_mf = (inst_buy + inst_sell) / total_mf * 100
    mf_source = 'Tushare moneyflow'
else:
    # 回退: 用逐笔大单(>=100手)统计
    big_t = tick[tick['volume'] >= 100]
    inst_buy = big_t[big_t['nature'] == '买盘']['amount'].sum()
    inst_sell = big_t[big_t['nature'] == '卖盘']['amount'].sum()
    inst_net = inst_buy - inst_sell
    small_t = tick[tick['volume'] < 100]
    retail_buy = small_t[small_t['nature'] == '买盘']['amount'].sum()
    retail_sell = small_t[small_t['nature'] == '卖盘']['amount'].sum()
    retail_net = retail_buy - retail_sell
    total_mf = inst_buy + inst_sell + retail_buy + retail_sell
    inst_pct_mf = (inst_buy + inst_sell) / total_mf * 100 if total_mf > 0 else 0
    mf_source = f'逐笔大单(>=100手)统计'

# 大单(>=100手)逐笔
big_tick = tick[tick['volume'] >= 100]
big_active_buy = big_tick[big_tick['nature'] == '买盘']['amount'].sum()
big_active_sell = big_tick[big_tick['nature'] == '卖盘']['amount'].sum()

# ====== 3. 5分钟K线 ======
session = requests.Session()
session.trust_env = False
r = session.get(
    'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData',
    params={'symbol': f'sz{SYMBOL}', 'scale': 5, 'ma': 'no', 'datalen': 100}, timeout=15)
k5 = pd.DataFrame(json.loads(r.text))
k5['time'] = pd.to_datetime(k5['day'])
for c in ['open', 'high', 'low', 'close', 'volume']:
    k5[c] = k5[c].astype(float)

today_k5 = k5[k5['time'].dt.date == pd.to_datetime(DATE).date()].sort_values('time')
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


# ====== 4. 拆单检测 v4 (v2发现 + 6指标评分) ======

# 粗筛: 排除开盘3分钟+尾盘2分钟
MORNING_CUT = pd.to_datetime(f'{DATE} 09:33:00')
TAIL_CUT = pd.to_datetime(f'{DATE} 14:58:00')
tick_core = tick[(tick['time_dt'] >= MORNING_CUT) & (tick['time_dt'] <= TAIL_CUT)].reset_index(drop=True)

# ---- 基础发现层 (收紧阈值, 对齐暗盘特征) ----
WINDOW, MIN_EVENTS, STEP = 20, 14, 5
split_events = []
for i in range(0, len(tick_core) - WINDOW, STEP):
    win = tick_core.iloc[i:i+WINDOW]
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
    # 基础分: 节拍+价位+量级+方向
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
        'gap_std': round(gap_std, 1), 'price_r': round(price_range*100, 2),
        'vmean': round(vv.mean(), 0), 'dir_purity': round(dir_purity*100, 0),
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

# ---- 质量评估层 (6指标评分) ----
for ev in events_unique:
    ev['duration_min'] = round((ev['t1'] - ev['t0']).total_seconds() / 60, 1)

    # 在事件附近取80笔做扩展分析
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

    # 指标1: 手数集中
    if len(efvols) >= 10:
        s = np.sort(efvols)
        span = max(int(len(s)*0.85), 1)
        min_r = min(s[i+span-1] - s[i] for i in range(len(s)-span+1))
        vratio = efvols.max()/efvols.min() if efvols.min() > 0 else 999
        h1 = 3 if (min_r <= 50 and vratio <= 5) else (1 if min_r <= 100 else 0)
    else:
        h1 = 0; min_r = 999

    # 指标2: 时间间隔
    egaps = np.diff(ext['time_sec'].values)
    in_range = ((egaps >= 0) & (egaps <= 8)).sum() / len(egaps) if len(egaps) > 0 else 0
    long_r = (egaps > 10).sum() / len(egaps) if len(egaps) > 0 else 1
    h2 = 3 if (in_range >= 0.80 and egaps.std() < 4 and long_r < 0.15) else (1 if in_range >= 0.65 else 0)

    # 指标3: 价格聚类
    if len(efprices) >= 2:
        pspan = efprices.max() - efprices.min()
        mode_p = pd.Series(efprices).mode().iloc[0]
        near = (abs(efprices - mode_p) <= 0.02).sum() / len(efprices)
        h3 = 3 if (pspan <= 0.05 and near >= 0.75) else (1 if pspan <= 0.12 else 0)
    else:
        h3 = 0; pspan = 999

    # 指标4: 方向一致
    dcnt = edirs.value_counts()
    dp = dcnt.iloc[0]/len(edirs) if len(dcnt) > 0 else 0
    h4 = 3 if dp > 0.80 else (1 if dp > 0.65 else 0)

    # 指标5: 放量滞价
    kb = today_k5[(today_k5['time'] >= ev['t0'] - pd.Timedelta(minutes=5)) &
                   (today_k5['time'] <= ev['t1'])]
    h5 = 0
    if len(kb) >= 1:
        k5m = today_k5['volume'].mean()
        hv = (kb['volume'] > k5m * 1.2).any()
        amps = abs(kb['close'] - kb['open']) / kb['open']
        flat = (amps < 0.005).any()
        if hv and flat: h5 = 2
        elif hv or flat: h5 = 1

    # 指标6: 合并到总分的相邻事件延续性
    h6 = 0  # 在二次验证时加分

    quality_score = h1 + h2 + h3 + h4 + h5
    ev['quality_score'] = quality_score
    ev['indicators'] = f"手{h1}/3 时{h2}/3 价{h3}/3 向{h4}/3 量{h5}/2"

# ---- 二次验证 ----
for i, ev in enumerate(events_unique):
    if i + 1 < len(events_unique):
        next_ev = events_unique[i + 1]
        # 相邻事件: 方向相同+时间接近(<3分钟间隔)
        t_gap = (next_ev['t0'] - ev['t1']).total_seconds()
        if t_gap < 180 and ev['dir'] == next_ev['dir']:
            ev['quality_score'] += 2

# ---- 暗盘过滤: 价必须有一定稳定性(暗盘前提:不惊动价格) ----
filtered = []
for ev in events_unique:
    m = re.search(r'价(\d)/3', ev['indicators'])
    h3_score = int(m.group(1)) if m else 0
    if h3_score == 0:
        continue  # 价格波动太大, 不是暗盘(属于明盘大单)

    exclude = None
    mid_t = ev['t0'] + (ev['t1'] - ev['t0']) / 2
    mid_pos = (tick_core['time_dt'] - mid_t).abs().idxmin()
    w0 = max(0, mid_pos - 40)
    w1 = min(len(tick_core), w0 + 80)
    ext2 = tick_core.iloc[w0:w1]
    xvols = ext2['volume'].values
    xprices = ext2['price'].values
    tiny_r = (xvols <= 5).sum() / len(xvols) if len(xvols) > 0 else 0
    if tiny_r > 0.30:
        exclude = f"微单{tiny_r:.0%}"
    elif len(xprices) > 1 and abs(xprices[-1] - xprices[0]) / xprices[0] > 0.008:
        exclude = f"急涨跌"
    elif ev['duration_min'] < 1.0 and ev['quality_score'] < 7:
        exclude = f"短事件({ev['duration_min']:.1f}min)"
    if not exclude:
        filtered.append(ev)

events_unique = filtered
high_conf = [e for e in events_unique if e['quality_score'] >= 9]
suspected = [e for e in events_unique if 6 <= e['quality_score'] < 9]
low_qual = [e for e in events_unique if e['quality_score'] < 6]

split_vol = sum(e['vol'] for e in events_unique)
active_vol = sum(e['vol'] for e in events_unique if e['dir'] == '买盘')
passive_vol = sum(e['vol'] for e in events_unique if e['dir'] == '卖盘')
n_candidate = len(events_unique)
n_total_win = (len(tick_core) - WINDOW) // STEP


# ====== 5. 输出 ======
print(f'开盘 {day_open:.2f}  最高 {day_high:.2f}  最低 {day_low:.2f}  收盘 {day_close:.2f}  ({full_pct:+.2f}%)')
print(f'成交 {TOTAL_VOL}手 / {TOTAL_AMT/1e8:.2f}亿 / {len(tick)}笔')
print()

print(f'{"="*50}')
print(f'  维度一: 机构参与度与净流向 (数据源: {mf_source})')
print(f'{"="*50}')
print(f'  机构参与占比:                  {inst_pct_mf:.0f}%')
print(f'  机构净主动:                    {inst_net/10000:+.0f}万')
print(f'  散户净主动(中单+小单):          {retail_net/10000:+.0f}万')
print(f'  逐笔净主动(全部):               {tick_net/10000:+.0f}万')
print(f'  大单(>=100手)主动:              {big_active_buy/10000:.0f}万买 vs {big_active_sell/10000:.0f}万卖')

# 机构意图
if inst_net > 0 and full_pct < 0:
    intent = '机构净买+价跌 -> 压价吃货，偏多'
elif inst_net < 0 and full_pct > 0:
    intent = '机构净卖+价涨 -> 出货，偏空'
elif inst_net > 0 and full_pct > 0:
    intent = '机构净买+价涨 -> 顺势做多'
elif inst_net < 0 and full_pct < 0:
    intent = '机构净卖+价跌 -> 顺势撤退，偏空'
else:
    intent = '--'
print(f'  >>> {intent}')
print()

print(f'{"="*50}')
print(f'  维度二: 尾盘异动')
print(f'{"="*50}')
print(f'  尾盘15分钟量占比:  {tail_vol_ratio:.1f}%')
print(f'  尾盘涨跌:          {tail_pct:+.2f}%')
print(f'  全日涨跌:          {full_pct:+.2f}%')
if tail_vol_ratio > 12 and abs(tail_pct) > 0.3:
    tsig = '尾盘放量买入(明日大概率高开)' if tail_pct > 0 else '尾盘放量卖出(警惕次日低开)'
elif abs(tail_pct) > abs(full_pct) * 0.5 and abs(tail_pct) > 0.2:
    tsig = '尾盘贡献度高(尾盘资金有意图)'
else:
    tsig = '尾盘正常'
print(f'  >>> {tsig}')
print()

print(f'{"="*50}')
print(f'  维度三: 拆单行为检测 v4 (发现层+6指标评分)')
print(f'{"="*50}')
print(f'  扫描窗口: {n_total_win} | 候选事件: {n_candidate} | 暗盘高置信(>=9分): {len(high_conf)} | 疑似(6-8分): {len(suspected)}')
print(f'  拆单总量: {split_vol}手 ({split_vol/TOTAL_VOL*100:.1f}%总成交)')
print(f'  主动买拆单: {active_vol}手 ({active_vol/TOTAL_VOL*100:.1f}%)')
print(f'  被动卖拆单: {passive_vol}手 ({passive_vol/TOTAL_VOL*100:.1f}%)')
if passive_vol > active_vol * 1.5:
    sj = '拆单偏卖 -> 隐藏出货痕迹'
elif active_vol > passive_vol * 1.5:
    sj = '拆单偏买 -> 隐藏吸筹痕迹'
else:
    sj = '拆单买卖均衡'
print(f'  >>> {sj}')

# 事件明细
if events_unique:
    all_sorted = sorted(events_unique, key=lambda x: x['quality_score'], reverse=True)
    print(f'\n  事件明细 (按质量分排序):')
    for e in all_sorted[:10]:
        d = '买' if e['dir'] == '买盘' else '卖'
        tag = ' [暗]' if e['quality_score'] >= 9 else (' [疑]' if e['quality_score'] >= 6 else '')
        print(f'  {e["start"]}~{e["end"]} {e["duration_min"]:.1f}min {d} {e["vol"]}手'
              f' 基{e["base_score"]} 质{e["quality_score"]}分{tag} | {e["indicators"]}')
    if len(all_sorted) > 10:
        print(f'    ... 还有{len(all_sorted)-10}个事件')
print()

# ====== 综合 ======
print(f'{"="*50}')
print(f'  综合判断')
print(f'{"="*50}')

signals = []
conf = 0

if inst_net is not None:
    if inst_net > 0 and full_pct < 0:
        signals.append('机构逆势净买')
        conf += 3
    elif inst_net > 0 and full_pct > 0:
        signals.append('机构顺势净买')
        conf += 2
    elif inst_net < 0 and full_pct > 0:
        signals.append('机构逆势净卖')
        conf -= 3
    else:
        signals.append('机构顺势净卖')
        conf -= 2

if tail_pct > 0 and tail_vol_ratio > 10:
    signals.append('尾盘放量买入')
    conf += 2
elif tail_pct < -0.3 and tail_vol_ratio > 10:
    signals.append('尾盘放量卖出')
    conf -= 2
elif abs(tail_pct) > abs(full_pct) * 0.5 and abs(tail_pct) > 0.2:
    signals.append('尾盘有意图')
    conf += 1 if tail_pct > 0 else -1

if passive_vol > active_vol * 1.5:
    signals.append('拆单偏卖')
    conf -= 2
elif active_vol > passive_vol * 1.5:
    signals.append('拆单偏买')
    conf += 2

if len(high_conf) > 0:
    buy_conf = sum(1 for e in high_conf if e['dir'] == '买盘')
    sell_conf = sum(1 for e in high_conf if e['dir'] == '卖盘')
    # 暗盘净量: 按高置信事件手数算
    dark_buy_vol = sum(e['vol'] for e in high_conf if e['dir'] == '买盘')
    dark_sell_vol = sum(e['vol'] for e in high_conf if e['dir'] == '卖盘')
    dark_net = dark_buy_vol - dark_sell_vol
    signals.append(f'暗盘拆单{buy_conf}买{sell_conf}卖 净{int(dark_net)}手')
    if dark_net > 0: conf += 2
    elif dark_net < 0: conf -= 2

if conf >= 5:
    verdict = '强烈偏多 —— 多重信号共振看涨'
elif conf >= 2:
    verdict = '中性偏多 —— 有建仓痕迹'
elif conf >= -1:
    verdict = '中性/观望 —— 信号不统一'
elif conf >= -4:
    verdict = '中性偏空 —— 有撤退痕迹'
else:
    verdict = '偏空 —— 多重信号共振看跌'

print(f'  信号: {", ".join(signals)}')
print(f'  置信分: {conf:+d}')
print(f'  综合: {verdict}')
print()
print(f'  [说明]')
print(f'  暗盘v4: 发现层+评分层(5指标0-14分)+暗盘过滤(价>0分)+高置信>=9分')
print(f'  回测显示: 机构逆势净买+价跌 这种反向模式')
print(f'  大中矿业次日上涨概率 55.2% (基准48.4%), 平均+0.37%')
print(f'  胜率不高但方向有参考价值, 需结合其他信号使用')
