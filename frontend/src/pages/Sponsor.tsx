import { Heart, Github, ArrowLeft } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

const GITHUB_URL = 'https://github.com/KylinMountain/TradingAgents-AShare'

export default function Sponsor() {
    const navigate = useNavigate()

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-50 via-pink-50/30 to-slate-100 dark:from-slate-950 dark:via-pink-950/10 dark:to-slate-950 flex items-center justify-center p-6">
            <div className="w-full max-w-2xl">
                <div className="bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-xl overflow-hidden">
                    {/* Header */}
                    <div className="bg-gradient-to-r from-pink-500 to-rose-500 px-6 py-5 text-center">
                        <Heart className="w-8 h-8 text-white mx-auto mb-2" fill="white" />
                        <h1 className="text-xl font-bold text-white">支持 TradingAgents-AShare</h1>
                        <p className="text-pink-100 text-sm mt-1">你的支持是项目持续发展的动力</p>
                    </div>

                    {/* QR Codes */}
                    <div className="px-6 py-6">
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                            {/* WeChat */}
                            <div className="text-center">
                                <p className="text-sm text-slate-500 dark:text-slate-400 mb-3 font-medium">微信支付</p>
                                <div className="inline-block rounded-2xl border border-slate-200 dark:border-slate-700 p-3 bg-white">
                                    <img
                                        src="/assets/wechat.png"
                                        alt="微信收款码"
                                        className="w-48 h-48 object-contain"
                                    />
                                </div>
                            </div>
                            {/* Alipay */}
                            <div className="text-center">
                                <p className="text-sm text-slate-500 dark:text-slate-400 mb-3 font-medium">支付宝</p>
                                <div className="inline-block rounded-2xl border border-slate-200 dark:border-slate-700 p-3 bg-white">
                                    <img
                                        src="/assets/alipay.png"
                                        alt="支付宝收款码"
                                        className="w-48 h-48 object-contain"
                                    />
                                </div>
                            </div>
                        </div>
                        <div className="text-center mt-5">
                            <p className="text-xs text-slate-400 dark:text-slate-500">金额随意，心意最重要</p>
                            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">转账时可备注您的昵称和邮箱或 GitHub ID，方便致谢</p>
                            <p className="text-sm text-rose-400 dark:text-rose-300 mt-2 font-medium">祝您股市长红，收益长虹 🚀</p>
                        </div>
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
