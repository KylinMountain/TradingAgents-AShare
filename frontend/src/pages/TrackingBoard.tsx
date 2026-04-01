import TrackingBoardPanel from '@/components/TrackingBoardPanel'

export default function TrackingBoard() {
    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">跟踪看板</h1>
                <p className="mt-1 text-slate-500 dark:text-slate-400">
                    聚合 QMT 持仓、实盘价格、昨日报告区间和交易员建议，方便盘中快速跟踪。
                </p>
            </div>

            <TrackingBoardPanel />
        </div>
    )
}
