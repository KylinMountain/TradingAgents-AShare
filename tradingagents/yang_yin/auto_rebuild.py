"""启动时检测关键源码是否有变，有则自动重建衍生数据。

不必每次部署手动 sftp 数据文件——git pull + restart 即可，数据自动再生。
"""
import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 受监控的源码文件（相对于仓库根目录）
WATCHED_FILES = [
    "tradingagents/yang_yin/factors_v7.py",
    "tradingagents/yang_yin/model_v7.py",
    "tradingagents/yang_yin/aggregation.py",
    "tradingagents/yang_yin/gold_silver_v8_1.py",
    "tradingagents/yang_yin/red_green_bg.py",
]

# 仓库根目录（从本文件位置向上推导）
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _compute_hashes() -> dict[str, str]:
    result = {}
    for rel in WATCHED_FILES:
        p = _REPO_ROOT / rel
        if p.exists():
            result[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def check_and_rebuild(rebuild_force: bool = False) -> bool:
    """检测源码变更 → 自动重建衍生数据。返回 True 表示执行了重建。

    调用时机：uvicorn lifespan 启动阶段，在特征面板缓存等大数据已就绪之后。
    """
    from .pipeline import YangYinPipeline

    pipeline = YangYinPipeline()
    summary = pipeline.summary_dir
    hash_path = summary / "source_hash.json"

    current = _compute_hashes()
    if not current:
        logger.warning("auto_rebuild: 无法计算源码哈希，跳过")
        return False

    if not rebuild_force and hash_path.exists():
        try:
            stored = json.loads(hash_path.read_text(encoding="utf-8"))
            if stored == current:
                logger.info("auto_rebuild: 源码未变更，跳过重建")
                return False
        except Exception:
            logger.warning("auto_rebuild: 哈希文件损坏，强制重建")

    logger.info("auto_rebuild: 检测到源码变更，开始重建衍生数据...")
    try:
        _rebuild_yangpu_history(pipeline)
        _rebuild_gold_finger(pipeline)
        _rebuild_red_green_bg(pipeline)

        hash_path.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("auto_rebuild: 重建完成，哈希已更新")
        return True
    except Exception:
        logger.exception("auto_rebuild: 重建失败")
        return False


def _rebuild_yangpu_history(pipeline):
    from .factors_v7 import compute_factors
    from .model_v7 import predict_yangpu
    from .aggregation import save_prev_yangpu
    import pandas as pd

    logger.info("  重建阳谱历史...")
    feat = pipeline.load_feature_panel()
    if feat is None:
        logger.warning("  特征面板不存在，先构建面板+特征")
        if pipeline.load_panel() is None:
            pipeline.build_panel()
        feat = pipeline.build_feature_panel()

    all_dates = sorted(feat["trade_date"].unique())
    rows = []
    prev = 50.0
    for dt in all_dates:
        factors = compute_factors(feat, dt, prev_yangpu=prev)
        if factors is None:
            continue
        pred = predict_yangpu(factors)
        n = feat[feat["trade_date"] == dt]["ts_code"].nunique()
        rows.append({
            "trade_date": dt,
            "total_scored": n,
            "yang_pct": round(pred, 1),
            "yin_pct": round(100 - pred, 1),
            "updated_at": f"{dt[:4]}-{dt[4:6]}-{dt[6:8]} 15:00",
        })
        prev = pred

    hist_df = pd.DataFrame(rows)
    hist_path = pipeline.summary_dir / "yang_yin_history.parquet"
    hist_df.to_parquet(hist_path, index=False)

    last = rows[-1]
    save_prev_yangpu(last["yang_pct"], last["trade_date"], pipeline, source="market_close")
    logger.info(f"  阳谱历史: {len(hist_df)} 条, 最新 {last['trade_date']} → {last['yang_pct']}%")


def _rebuild_gold_finger(pipeline):
    from .gold_silver_v8_1 import generate_history, save_gold_finger_history
    from .aggregation import load_history

    logger.info("  重建金银手指...")
    panel = pipeline.load_panel()
    if panel is None:
        logger.warning("  面板不存在，先构建")
        panel = pipeline.build_panel()

    yang_hist = load_history(pipeline)
    gold_df = generate_history(panel, yang_hist)
    if not gold_df.empty:
        save_gold_finger_history(gold_df, pipeline)
        latest = gold_df.iloc[-1]
        logger.info(f"  金银手指: {len(gold_df)} 条, 最新 {latest['trade_date']} → {latest['signal']}")


def _rebuild_red_green_bg(pipeline):
    from .red_green_bg import fetch_index_kline, compute_gs, compute_background, update_bg_state
    from .aggregation import load_history

    logger.info("  重建红绿背景...")
    try:
        kline = fetch_index_kline(days=120)
        gs = compute_gs(kline)
        yang_hist = load_history(pipeline)
        state = update_bg_state(kline, yang_hist, pipeline, trade_date=None)
        logger.info(f"  红绿背景: {state.get('background', '?')}")
    except Exception:
        logger.warning("  红绿背景重建失败", exc_info=True)
