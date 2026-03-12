/** @type {import('tailwindcss').Config} */
export default {
    darkMode: 'class',
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                // 保留 trading 命名空间用于特定业务颜色
                trading: {
                    accent: {
                        green: '#22c55e',
                        red: '#ef4444',
                        blue: '#3b82f6',
                        cyan: '#06b6d4',
                        purple: '#8b5cf6',
                        orange: '#f97316',
                        yellow: '#eab308',
                        pink: '#ec4899',
                    },
                },
            },
            fontFamily: {
                mono: ['JetBrains Mono', 'SF Mono', 'monospace'],
                sans: ['Inter', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
            },
            animation: {
                'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                'spin-slow': 'spin 3s linear infinite',
            },
        },
    },
    plugins: [],
}
