"""
AkShare 接口问题总结与建议

## 问题接口

### 1. get_lhb_detail (龙虎榜)
- 问题：akshare 1.18.51 内部 bug
- 建议：暂时禁用，添加友好提示

### 2. get_board_fund_flow (板块资金流向)
- 问题：akshare 1.18.51 内部 bug
- 建议：暂时禁用，添加友好提示

### 3. stock_individual_spot_xq (雪球实时)
- 问题：雪球 API 变化
- 建议：移除或使用其他数据源

## 可用接口（无需修改）

- stock_news_em ✅
- news_cctv ✅
- stock_main_stock_holder ✅
- stock_zt_pool_em ✅
- stock_hot_follow_xq ✅

## 修复建议

1. **短期方案**：在有问题的方法中添加更友好的错误处理
2. **中期方案**：关注 akshare 更新，及时升级
3. **长期方案**：考虑直接调用东方财富 API，不依赖 akshare

## 依赖更新

已升级：
- akshare: 1.18.30 → 1.18.51
- pandas: 2.3.0 → 3.0.2
- numpy: 2.3.0 → 2.4.4

建议运行 `uv lock` 更新锁文件。
"""
