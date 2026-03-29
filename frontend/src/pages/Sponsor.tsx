import { Heart, Github, ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const GITHUB_URL = 'https://github.com/KylinMountain/TradingAgents-AShare'

export default function Sponsor() {
    const navigate = useNavigate()

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-pink-50/30 to-slate-100 dark:from-slate-950 dark:via-pink-950/10 dark:to-slate-950 flex items-center justify-center p-6">
            <div className="w-full max-w-md">
                <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-xl overflow-hidden">
                    {/* Header */}
                    <div className="bg-gradient-to-r from-pink-500 to-rose-500 px-6 py-5 text-center">
                        <Heart className="w-8 h-8 text-white mx-auto mb-2" fill="white" />
                        <h1 className="text-xl font-bold text-white">支持 TradingAgents</h1>
                        <p className="text-pink-100 text-sm mt-1">你的支持是项目持续发展的动力</p>
                    </div>

                    {/* QR Code */}
                    <div className="px-6 py-6 text-center">
                        <p className="text-sm text-slate-500 dark:text-slate-400 mb-4">支付宝扫码赞助</p>
                        <div className="inline-block rounded-2xl border border-slate-200 dark:border-slate-700 p-3 bg-white">
                            <img
                                src="/assets/alipay.png"
                                alt="支付宝收款码"
                                className="w-56 h-56 object-contain"
                            />
                        </div>
                        <p className="text-xs text-slate-400 dark:text-slate-500 mt-4">金额随意，心意最重要</p>
                    </div>

                    {/* Footer links */}
                    <div className="px-6 pb-6 flex items-center justify-center gap-4">
                        <button
                            onClick={() => navigate(-1)}
                            className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
                        >
                            <ArrowLeft className="w-4 h-4" />
                            返回
                        </button>
                        <a
                            href={GITHUB_URL}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200 transition-colors"
                        >
                            <Github className="w-4 h-4" />
                            GitHub
                        </a>
                    </div>
                </div>
            </div>
        </div>
    )
}
