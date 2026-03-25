# Debate Battle View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a debate/battle visualization drawer that shows multi-round agent debates in a vertical timeline when users click debate-type agents.

**Architecture:** Backend emits `agent.debate` SSE events after each debate agent speaks. Frontend stores these in a transient `debateMessages` state, and a new `DebateDrawer` component renders them as a vertical timeline grouped by round. The drawer slides in from the right when triggered by clicking debate agents in `AgentCollaboration`.

**Tech Stack:** React 18, TypeScript, Zustand, Tailwind CSS, react-markdown, FastAPI SSE

**Spec:** `docs/superpowers/specs/2026-03-25-debate-battle-view-design.md`

---

## File Structure

### New files
| File | Responsibility |
|------|---------------|
| `frontend/src/components/DebateDrawer.tsx` | Drawer container: backdrop, slide animation, header, close button |
| `frontend/src/components/DebateTimeline.tsx` | Timeline renderer: round separators, speech cards, verdict card, empty placeholder |

### Modified files
| File | Changes |
|------|---------|
| `frontend/src/types/index.ts` | Add `DebateMessage` interface, add `'agent.debate'` to `SSEEventType` |
| `frontend/src/stores/analysisStore.ts` | Add `debateMessages` state + `addDebateMessage` action (transient) |
| `frontend/src/components/ChatCopilotPanel.tsx` | Handle `agent.debate` SSE event in `parseAndDispatch()` |
| `frontend/src/components/AgentCollaboration.tsx` | Add `onOpenDebate` prop, change click behavior for debate agents |
| `frontend/src/pages/Analysis.tsx` | Add drawer state, pass `onOpenDebate`, render `DebateDrawer` |
| `api/main.py` | Add `emit_debate_message()` to `AgentProgressTracker` |
| `tradingagents/agents/researchers/bull_researcher.py` | Emit `agent.debate` after streaming completes |
| `tradingagents/agents/researchers/bear_researcher.py` | Emit `agent.debate` after streaming completes |
| `tradingagents/agents/managers/research_manager.py` | Emit `agent.debate` verdict after streaming completes |
| `tradingagents/agents/risk_mgmt/aggressive_debator.py` | Emit `agent.debate` after `llm.invoke()` |
| `tradingagents/agents/risk_mgmt/conservative_debator.py` | Emit `agent.debate` after `llm.invoke()` |
| `tradingagents/agents/risk_mgmt/neutral_debator.py` | Emit `agent.debate` after `llm.invoke()` |
| `tradingagents/agents/managers/risk_manager.py` | Emit `agent.debate` verdict after `llm.invoke()` |

---

### Task 1: Add DebateMessage type and SSE event type

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add DebateMessage interface**

At the end of `frontend/src/types/index.ts`, before the closing content, add:

```typescript
// Debate message (for battle view)
export interface DebateMessage {
    debate: 'research' | 'risk'
    agent: string
    round: number        // -1 = verdict
    content: string
    isVerdict?: boolean
    horizon?: string
}
```

- [ ] **Step 2: Add 'agent.debate' to SSEEventType**

In the `SSEEventType` union (around line 119-134), add `'agent.debate'` to the list:

```typescript
export type SSEEventType =
    | 'job.created'
    | 'job.running'
    | 'job.completed'
    | 'job.failed'
    | 'agent.status'
    | 'agent.message'
    | 'agent.tool_call'
    | 'agent.report'
    | 'agent.report.chunk'
    | 'agent.snapshot'
    | 'agent.milestone'
    | 'agent.writing'
    | 'agent.activity'
    | 'agent.activity_complete'
    | 'agent.token'
    | 'agent.debate'
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add DebateMessage interface and agent.debate SSE event type (#68)"
```

---

### Task 2: Add debateMessages state to analysisStore

**Files:**
- Modify: `frontend/src/stores/analysisStore.ts`

- [ ] **Step 1: Add state field and action to the interface**

In `AnalysisState` interface, add after `chatMessages: ChatMessage[]` (around line 67):

```typescript
    // Debate messages (transient, for battle view)
    debateMessages: Record<string, DebateMessage[]>
```

Add the action signature before `clearChatMessages` (around line 106):

```typescript
    addDebateMessage: (msg: DebateMessage) => void
```

Add the import of `DebateMessage` to the imports from `@/types` at the top.

- [ ] **Step 2: Add initial state and action implementation**

In the store creation (after `chatMessages: createInitialChatMessages()`), add:

```typescript
    debateMessages: {},
```

Add the action implementation before `clearChatMessages`:

```typescript
    // 添加辩论消息
    addDebateMessage: (msg) => set((state) => {
        const key = msg.debate
        const existing = state.debateMessages[key] || []
        return {
            debateMessages: {
                ...state.debateMessages,
                [key]: [...existing, msg],
            }
        }
    }),
```

- [ ] **Step 3: Add to clearSession and reset**

In `clearSession()` (around line 328), add `debateMessages: {},` to the set object.

In `reset()` (around line 370), add `debateMessages: {},` to the set object.

- [ ] **Step 4: Add to merge function (transient reset)**

In the `merge` function (around line 405), add `debateMessages: {},` alongside other transient resets like `streamingSections: {}`.

- [ ] **Step 5: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add frontend/src/stores/analysisStore.ts
git commit -m "feat(store): add debateMessages state and addDebateMessage action (#68)"
```

---

### Task 3: Handle agent.debate SSE event in ChatCopilotPanel

**Files:**
- Modify: `frontend/src/components/ChatCopilotPanel.tsx`

- [ ] **Step 1: Add addDebateMessage to store destructuring**

In the `useAnalysisStore()` destructuring (around line 170), add `addDebateMessage`:

```typescript
    const {
        chatMessages,
        isAnalyzing,
        // ... existing ...
        addDebateMessage,
        clearSession,
        reset,
    } = useAnalysisStore()
```

- [ ] **Step 2: Add agent.debate case to parseAndDispatch**

In the `parseAndDispatch` function's switch statement, add before the `default:` case (around line 502).

**Important:** Backend emits snake_case `is_verdict` but the TypeScript interface uses camelCase `isVerdict`. Must map fields explicitly:

```typescript
            case 'agent.debate': {
                const raw = data as Record<string, unknown>
                addDebateMessage({
                    debate: raw.debate as 'research' | 'risk',
                    agent: raw.agent as string,
                    round: raw.round as number,
                    content: raw.content as string,
                    isVerdict: raw.is_verdict as boolean | undefined,
                    horizon: raw.horizon as string | undefined,
                })
                break
            }
```

Add `DebateMessage` to the imports from `@/types` at the top of the file.

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ChatCopilotPanel.tsx
git commit -m "feat(sse): handle agent.debate event in ChatCopilotPanel (#68)"
```

---

### Task 4: Create DebateTimeline component

**Files:**
- Create: `frontend/src/components/DebateTimeline.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/DebateTimeline.tsx`:

```typescript
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { DebateMessage } from '@/types'

// Agent metadata for debate participants
const DEBATE_AGENT_META: Record<string, { emoji: string; label: string; dotCls: string; borderCls: string; bgCls: string; textCls: string }> = {
    'Bull Researcher':       { emoji: '🐂', label: '多头研究员',  dotCls: 'bg-emerald-500', borderCls: 'border-emerald-500/30', bgCls: 'bg-emerald-500/5',  textCls: 'text-emerald-400' },
    'Bear Researcher':       { emoji: '🐻', label: '空头研究员',  dotCls: 'bg-rose-500',    borderCls: 'border-rose-500/30',    bgCls: 'bg-rose-500/5',     textCls: 'text-rose-400' },
    'Research Manager':      { emoji: '🏛️', label: '研究总监',    dotCls: 'bg-blue-500',    borderCls: 'border-blue-500/30',    bgCls: 'bg-blue-500/5',     textCls: 'text-blue-400' },
    'Aggressive Analyst':    { emoji: '🔥', label: '激进派',      dotCls: 'bg-red-500',     borderCls: 'border-red-500/30',     bgCls: 'bg-red-500/5',      textCls: 'text-red-400' },
    'Neutral Analyst':       { emoji: '⚖️', label: '中性派',      dotCls: 'bg-slate-500',   borderCls: 'border-slate-500/30',   bgCls: 'bg-slate-500/5',    textCls: 'text-slate-400' },
    'Conservative Analyst':  { emoji: '🛡️', label: '稳健派',      dotCls: 'bg-amber-500',   borderCls: 'border-amber-500/30',   bgCls: 'bg-amber-500/5',    textCls: 'text-amber-400' },
    'Portfolio Manager':     { emoji: '🏛️', label: '风控裁决',    dotCls: 'bg-blue-500',    borderCls: 'border-blue-500/30',    bgCls: 'bg-blue-500/5',     textCls: 'text-blue-400' },
}

interface DebateTimelineProps {
    messages: DebateMessage[]
    debate: 'research' | 'risk'
}

export default function DebateTimeline({ messages, debate }: DebateTimelineProps) {
    if (messages.length === 0) {
        return (
            <div className="flex items-center justify-center h-full text-slate-500 dark:text-slate-400">
                <div className="text-center">
                    <div className="text-3xl mb-3">{debate === 'research' ? '🐂⚔️🐻' : '🔥⚖️🛡️'}</div>
                    <p className="text-sm">辩论尚未开始</p>
                </div>
            </div>
        )
    }

    // Separate verdict and speech messages
    const speeches = messages.filter(m => !m.isVerdict)
    const verdict = messages.find(m => m.isVerdict)

    // Group speeches by round
    const rounds = new Map<number, DebateMessage[]>()
    for (const msg of speeches) {
        const list = rounds.get(msg.round) || []
        list.push(msg)
        rounds.set(msg.round, list)
    }
    const sortedRounds = [...rounds.entries()].sort(([a], [b]) => a - b)

    return (
        <div className="space-y-1">
            {sortedRounds.map(([round, msgs]) => (
                <div key={round}>
                    {/* Round separator */}
                    <div className="flex items-center gap-3 my-4">
                        <div className="flex-1 h-px bg-amber-500/20" />
                        <span className="text-xs font-bold text-amber-500 bg-amber-500/10 px-3 py-0.5 rounded-full">
                            Round {round}
                        </span>
                        <div className="flex-1 h-px bg-amber-500/20" />
                    </div>

                    {/* Speech cards */}
                    <div className="space-y-3 pl-4 relative">
                        {/* Timeline line */}
                        <div className="absolute left-[7px] top-2 bottom-2 w-0.5 bg-slate-700/50" />

                        {msgs.map((msg, i) => {
                            const meta = DEBATE_AGENT_META[msg.agent] || {
                                emoji: '💬', label: msg.agent, dotCls: 'bg-slate-500',
                                borderCls: 'border-slate-500/30', bgCls: 'bg-slate-500/5', textCls: 'text-slate-400',
                            }
                            return (
                                <div key={`${round}-${msg.agent}-${i}`} className="relative">
                                    {/* Timeline dot */}
                                    <div className={`absolute -left-4 top-3 w-2.5 h-2.5 rounded-full ${meta.dotCls} ring-2 ring-slate-900 z-10`} />

                                    {/* Speech card */}
                                    <div className={`ml-2 rounded-lg border ${meta.borderCls} ${meta.bgCls} p-4`}>
                                        <div className="flex items-center gap-2 mb-2">
                                            <span className="text-base">{meta.emoji}</span>
                                            <span className={`text-sm font-bold ${meta.textCls}`}>{meta.label}</span>
                                            {msg.horizon && (
                                                <span className="text-[10px] text-slate-500 bg-slate-800 px-1.5 py-0.5 rounded">
                                                    {msg.horizon === 'short' ? '短线' : '中线'}
                                                </span>
                                            )}
                                        </div>
                                        <div className="prose dark:prose-invert prose-sm max-w-none text-sm leading-relaxed">
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                {msg.content}
                                            </ReactMarkdown>
                                        </div>
                                    </div>
                                </div>
                            )
                        })}
                    </div>
                </div>
            ))}

            {/* Verdict card */}
            {verdict && (
                <div className="mt-6">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="flex-1 h-px bg-blue-500/30" />
                        <span className="text-xs font-bold text-blue-400 bg-blue-500/10 px-3 py-0.5 rounded-full">
                            裁决
                        </span>
                        <div className="flex-1 h-px bg-blue-500/30" />
                    </div>
                    <div className="rounded-lg border border-blue-500/40 bg-slate-900/80 p-4">
                        <div className="flex items-center gap-2 mb-2">
                            <span className="text-base">🏛️</span>
                            <span className="text-sm font-bold text-blue-400">
                                {debate === 'research' ? '研究总监裁决' : '风控裁决'}
                            </span>
                        </div>
                        <div className="prose dark:prose-invert prose-sm max-w-none text-sm leading-relaxed">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {verdict.content}
                            </ReactMarkdown>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/DebateTimeline.tsx
git commit -m "feat(ui): create DebateTimeline component (#68)"
```

---

### Task 5: Create DebateDrawer component

**Files:**
- Create: `frontend/src/components/DebateDrawer.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/DebateDrawer.tsx`:

```typescript
import { useEffect, useRef } from 'react'
import { X } from 'lucide-react'
import { useAnalysisStore } from '@/stores/analysisStore'
import DebateTimeline from './DebateTimeline'

const DEBATE_TITLES: Record<string, { title: string; emoji: string }> = {
    research: { title: '多空辩论', emoji: '🐂⚔️🐻' },
    risk: { title: '风控三方辩论', emoji: '🔥⚖️🛡️' },
}

const DEBATE_PARTICIPANTS: Record<string, { emoji: string; label: string; cls: string }[]> = {
    research: [
        { emoji: '🐂', label: '多头', cls: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' },
        { emoji: '🐻', label: '空头', cls: 'bg-rose-500/15 text-rose-400 border-rose-500/30' },
        { emoji: '🏛️', label: '研究总监', cls: 'bg-blue-500/15 text-blue-400 border-blue-500/30' },
    ],
    risk: [
        { emoji: '🔥', label: '激进', cls: 'bg-red-500/15 text-red-400 border-red-500/30' },
        { emoji: '⚖️', label: '中性', cls: 'bg-slate-500/15 text-slate-400 border-slate-500/30' },
        { emoji: '🛡️', label: '稳健', cls: 'bg-amber-500/15 text-amber-400 border-amber-500/30' },
        { emoji: '🏛️', label: '风控', cls: 'bg-blue-500/15 text-blue-400 border-blue-500/30' },
    ],
}

interface DebateDrawerProps {
    debate: 'research' | 'risk' | null
    onClose: () => void
}

export default function DebateDrawer({ debate, onClose }: DebateDrawerProps) {
    const debateMessages = useAnalysisStore(s => s.debateMessages)
    const scrollRef = useRef<HTMLDivElement>(null)
    const messages = debate ? (debateMessages[debate] || []) : []
    const meta = debate ? DEBATE_TITLES[debate] : null
    const participants = debate ? DEBATE_PARTICIPANTS[debate] : []

    // Auto-scroll on new messages
    useEffect(() => {
        if (scrollRef.current) {
            scrollRef.current.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
        }
    }, [messages.length])

    return (
        <>
            {/* Backdrop */}
            <div
                className={`fixed inset-0 bg-black/40 z-40 transition-opacity duration-300 ${debate ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
                onClick={onClose}
            />

            {/* Drawer */}
            <div className={`fixed top-0 right-0 h-full w-1/2 max-w-[720px] min-w-[400px] bg-slate-900 border-l border-slate-700 shadow-2xl z-50 flex flex-col transition-transform duration-300 ease-out ${debate ? 'translate-x-0' : 'translate-x-full'}`}>
                {/* Header */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
                    <div className="flex items-center gap-3">
                        <span className="text-lg">{meta?.emoji}</span>
                        <h2 className="text-lg font-bold text-white tracking-tight">{meta?.title}</h2>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Participant pills */}
                <div className="flex items-center gap-2 px-5 py-3 border-b border-slate-800/50">
                    {participants.map(p => (
                        <span key={p.label} className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${p.cls}`}>
                            <span>{p.emoji}</span>
                            <span>{p.label}</span>
                        </span>
                    ))}
                </div>

                {/* Scrollable timeline */}
                <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto px-5 py-4">
                    {debate && <DebateTimeline messages={messages} debate={debate} />}
                </div>
            </div>
        </>
    )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/DebateDrawer.tsx
git commit -m "feat(ui): create DebateDrawer component (#68)"
```

---

### Task 6: Wire up AgentCollaboration to open debate drawer

**Files:**
- Modify: `frontend/src/components/AgentCollaboration.tsx`

- [ ] **Step 1: Add debate metadata to META array**

In `AgentCollaboration.tsx`, add a `debate` field to the existing `AgentMeta` interface (around line 13). Add this one line after the `section?` field:

```typescript
    debate?: 'research' | 'risk'
```

Then add `debate` field to the relevant entries in the `META` array:

- `Bull Researcher` → add `debate: 'research'`
- `Bear Researcher` → add `debate: 'research'`
- `Research Manager` → add `debate: 'research'`
- `Aggressive Analyst` → add `debate: 'risk'`
- `Neutral Analyst` → add `debate: 'risk'`
- `Conservative Analyst` → add `debate: 'risk'`
- `Portfolio Manager` → add `debate: 'risk'`

- [ ] **Step 2: Add onOpenDebate prop and update click handling**

Update `AgentCollaborationProps` (around line 253):

```typescript
interface AgentCollaborationProps {
    onSelectSection: (section?: string) => void
    onOpenDebate: (debate: 'research' | 'risk') => void
    selectedSection?: string
}
```

Update the component signature:

```typescript
export default function AgentCollaboration({ onSelectSection, onOpenDebate, selectedSection }: AgentCollaborationProps) {
```

Add `debate` to `CardData` interface (around line 157):

```typescript
interface CardData extends AgentMeta {
    status: AgentStatus;
    isStreaming: boolean;
    verdict: Verdict | null;
    isParticipating: boolean;
}
```

(No change needed since `debate` is inherited from `AgentMeta` via `extends`.)

Update the `AgentCard` `onClick` in the render (around line 356):

```typescript
<AgentCard
    key={card.name}
    card={card}
    selected={!!card.section && card.section === selectedSection}
    onClick={() => {
        if (card.debate) {
            onOpenDebate(card.debate)
        } else if (card.section) {
            onSelectSection(card.section === selectedSection ? undefined : card.section)
        }
    }}
/>
```

Also update `clickable` in `AgentCard` (line 169) to include debate agents:

```typescript
const clickable = (!!card.section || !!card.debate) && (done || active)
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: Will fail because `Analysis.tsx` doesn't pass `onOpenDebate` yet — that's next task.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AgentCollaboration.tsx
git commit -m "feat(ui): add debate click handling to AgentCollaboration (#68)"
```

---

### Task 7: Wire up Analysis page with DebateDrawer

**Files:**
- Modify: `frontend/src/pages/Analysis.tsx`

- [ ] **Step 1: Add imports and state**

Add import at top:

```typescript
import DebateDrawer from '@/components/DebateDrawer'
```

Add state inside `Analysis` component (after `activeSection` state, around line 50):

```typescript
const [debateDrawer, setDebateDrawer] = useState<'research' | 'risk' | null>(null)
```

- [ ] **Step 2: Pass onOpenDebate to AgentCollaboration**

Update the `AgentCollaboration` JSX (around line 111):

```typescript
<AgentCollaboration
    onSelectSection={handleShowReport}
    onOpenDebate={setDebateDrawer}
    selectedSection={activeSection}
/>
```

- [ ] **Step 3: Render DebateDrawer**

Add before the closing `</div>` of the root element (around line 132):

```typescript
<DebateDrawer debate={debateDrawer} onClose={() => setDebateDrawer(null)} />
```

- [ ] **Step 4: Verify TypeScript compiles and build succeeds**

Run: `cd frontend && npx tsc --noEmit && npx vite build`
Expected: No errors, build succeeds

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Analysis.tsx
git commit -m "feat(ui): wire up DebateDrawer in Analysis page (#68)"
```

---

### Task 8: Add emit_debate_message to backend AgentProgressTracker

**Files:**
- Modify: `api/main.py`

- [ ] **Step 1: Add emit_debate_message method**

In `AgentProgressTracker` class, add after `_emit_token()` method (around line 1091):

```python
    def emit_debate_message(
        self, debate: str, agent: str, round_num: int,
        content: str, is_verdict: bool = False,
    ) -> None:
        """推送辩论消息（每个 agent 每轮完成后调用一次）"""
        _emit_job_event(
            self.job_id,
            "agent.debate",
            {
                "debate": debate,
                "agent": agent,
                "round": round_num,
                "content": content,
                "is_verdict": is_verdict,
                "horizon": self.horizon,
            },
        )
```

- [ ] **Step 2: Commit**

```bash
git add api/main.py
git commit -m "feat(api): add emit_debate_message to AgentProgressTracker (#68)"
```

---

### Task 9: Emit debate events from Research debate agents

**Files:**
- Modify: `tradingagents/agents/researchers/bull_researcher.py`
- Modify: `tradingagents/agents/researchers/bear_researcher.py`
- Modify: `tradingagents/agents/managers/research_manager.py`

- [ ] **Step 1: Emit debate message in bull_researcher.py**

After the streaming loop completes and before `update_debate_state_with_payload` (around line 67), add:

```python
        # ── 推送辩论消息 ──
        debate_round = int(investment_debate_state.get("count", 0) or 0) + 1
        if tracker:
            tracker.emit_debate_message(
                debate="research", agent="Bull Researcher",
                round_num=debate_round, content=full_content,
            )
```

- [ ] **Step 2: Emit debate message in bear_researcher.py**

Same pattern — after the streaming loop, before `update_debate_state_with_payload`, add:

```python
        # ── 推送辩论消息 ──
        debate_round = int(investment_debate_state.get("count", 0) or 0) + 1
        if tracker:
            tracker.emit_debate_message(
                debate="research", agent="Bear Researcher",
                round_num=debate_round, content=full_content,
            )
```

- [ ] **Step 3: Emit debate verdict in research_manager.py**

After the streaming loop completes (around line 54), add:

```python
        # ── 推送辩论裁决 ──
        if tracker:
            tracker.emit_debate_message(
                debate="research", agent="Research Manager",
                round_num=-1, content=full_content, is_verdict=True,
            )
```

- [ ] **Step 4: Commit**

```bash
git add tradingagents/agents/researchers/bull_researcher.py tradingagents/agents/researchers/bear_researcher.py tradingagents/agents/managers/research_manager.py
git commit -m "feat(agents): emit debate events from research team (#68)"
```

---

### Task 10: Emit debate events from Risk debate agents

**Files:**
- Modify: `tradingagents/agents/risk_mgmt/aggressive_debator.py`
- Modify: `tradingagents/agents/risk_mgmt/conservative_debator.py`
- Modify: `tradingagents/agents/risk_mgmt/neutral_debator.py`
- Modify: `tradingagents/agents/managers/risk_manager.py`

- [ ] **Step 1: Add tracker import to all three debators**

Add to imports in `aggressive_debator.py`, `conservative_debator.py`, and `neutral_debator.py`:

```python
from tradingagents.agents.utils.agent_states import current_tracker_var
```

- [ ] **Step 2: Emit debate message in aggressive_debator.py**

After `update_debate_state_with_payload` and before the return statement (around line 66), add:

```python
        # ── 推送辩论消息 ──
        tracker = current_tracker_var.get()
        debate_round = int(risk_debate_state.get("count", 0) or 0) + 1
        if tracker:
            tracker.emit_debate_message(
                debate="risk", agent="Aggressive Analyst",
                round_num=debate_round, content=clean_response,
            )
```

- [ ] **Step 3: Emit debate message in conservative_debator.py**

Same pattern after `update_debate_state_with_payload`, before return:

```python
        # ── 推送辩论消息 ──
        tracker = current_tracker_var.get()
        debate_round = int(risk_debate_state.get("count", 0) or 0) + 1
        if tracker:
            tracker.emit_debate_message(
                debate="risk", agent="Conservative Analyst",
                round_num=debate_round, content=clean_response,
            )
```

- [ ] **Step 4: Emit debate message in neutral_debator.py**

Same pattern:

```python
        # ── 推送辩论消息 ──
        tracker = current_tracker_var.get()
        debate_round = int(risk_debate_state.get("count", 0) or 0) + 1
        if tracker:
            tracker.emit_debate_message(
                debate="risk", agent="Neutral Analyst",
                round_num=debate_round, content=clean_response,
            )
```

- [ ] **Step 5: Add tracker import and emit verdict in risk_manager.py**

Add import:

```python
from tradingagents.agents.utils.agent_states import current_tracker_var
```

After `extract_risk_judge_result` and before building `new_risk_debate_state` (around line 57), add:

```python
        # ── 推送辩论裁决 ──
        tracker = current_tracker_var.get()
        if tracker:
            tracker.emit_debate_message(
                debate="risk", agent="Portfolio Manager",
                round_num=-1, content=cleaned_response, is_verdict=True,
            )
```

- [ ] **Step 6: Commit**

```bash
git add tradingagents/agents/risk_mgmt/aggressive_debator.py tradingagents/agents/risk_mgmt/conservative_debator.py tradingagents/agents/risk_mgmt/neutral_debator.py tradingagents/agents/managers/risk_manager.py
git commit -m "feat(agents): emit debate events from risk management team (#68)"
```

---

### Task 11: Final build verification

- [ ] **Step 1: Full frontend build**

Run: `cd frontend && npx tsc --noEmit && npx vite build`
Expected: No errors

- [ ] **Step 2: Python syntax check on modified backend files**

Run: `python -m py_compile api/main.py && python -m py_compile tradingagents/agents/researchers/bull_researcher.py && python -m py_compile tradingagents/agents/researchers/bear_researcher.py && python -m py_compile tradingagents/agents/managers/research_manager.py && python -m py_compile tradingagents/agents/risk_mgmt/aggressive_debator.py && python -m py_compile tradingagents/agents/risk_mgmt/conservative_debator.py && python -m py_compile tradingagents/agents/risk_mgmt/neutral_debator.py && python -m py_compile tradingagents/agents/managers/risk_manager.py`
Expected: No output (success)

- [ ] **Step 3: Commit (if any final fixes needed)**
