# TradingAgents Dashboard

专业的金融交易分析界面，基于 React + TypeScript + Tailwind CSS 构建。

## 特性

- 🎨 **专业暗色主题** - 专为金融交易场景优化的深色界面
- 🤖 **Agent 流水线可视化** - 实时显示 12 个智能体的协作状态
- 📊 **实时日志流** - SSE 流式数据传输，毫秒级更新
- 📈 **交互式报告** - 分层展示多维度分析报告
- 🔄 **响应式设计** - 适配桌面、平板、手机多种设备

## 技术栈

- **框架**: React 18 + TypeScript
- **构建**: Vite
- **样式**: Tailwind CSS
- **状态管理**: Zustand
- **图标**: Lucide React
- **路由**: React Router

## 快速开始

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
VITE_API_URL=http://localhost:8000
```

### 3. 启动开发服务器

```bash
npm run dev
```

访问 http://localhost:5173

### 4. 构建生产版本

```bash
npm run build
```

## 项目结构

```
frontend/
├── src/
│   ├── components/       # 可复用组件
│   │   ├── Layout.tsx   # 布局组件
│   │   ├── Sidebar.tsx  # 侧边导航
│   │   ├── Header.tsx   # 顶部导航
│   │   ├── AgentPipeline.tsx  # Agent 流水线
│   │   ├── LogStream.tsx      # 实时日志
│   │   └── ReportViewer.tsx   # 报告阅读器
│   ├── pages/           # 页面组件
│   │   ├── Dashboard.tsx      # 控制台
│   │   ├── Analysis.tsx       # 分析页面
│   │   ├── Reports.tsx        # 报告列表
│   │   └── Settings.tsx       # 设置页面
│   ├── hooks/           # 自定义 Hooks
│   │   └── useSSE.ts    # SSE 连接
│   ├── stores/          # 状态管理
│   │   └── analysisStore.ts
│   ├── services/        # API 服务
│   │   └── api.ts
│   ├── types/           # TypeScript 类型
│   │   └── index.ts
│   ├── App.tsx          # 应用入口
│   ├── main.tsx         # 渲染入口
│   └── index.css        # 全局样式
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

## 界面预览

### 控制台 (Dashboard)
- 系统状态概览
- 快速操作入口
- 最近活动日志

### 分析页面 (Analysis)
- 股票代码和日期选择
- 分析师组合配置
- Agent 流水线实时监控
- 实时日志流
- 交互式报告展示

### 报告页面 (Reports)
- 历史报告列表
- 搜索和筛选
- 导出功能

### 设置页面 (Settings)
- API 配置
- LLM 提供商选择
- 默认分析参数

## 后端集成

本前端设计用于配合 TradingAgents FastAPI 后端使用：

```python
# 后端运行
python -m api.main
```

后端默认运行在 http://localhost:8000，已在 vite.config.ts 中配置代理。

## 自定义主题

编辑 `tailwind.config.js` 修改颜色：

```js
colors: {
  trading: {
    bg: {
      primary: '#0D1117',
      secondary: '#161B22',
      tertiary: '#21262D',
    },
    accent: {
      green: '#238636',
      red: '#DA3633',
      blue: '#58A6FF',
      // ...
    },
  },
}
```

## License

MIT
