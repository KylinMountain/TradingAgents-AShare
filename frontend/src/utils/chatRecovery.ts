export interface RecoverableChatMessage {
    role: string
    content: string
    agent?: string
    complete?: boolean
}

const AGENT_PLACEHOLDER_PATTERN = /正在思考并撰写报告中/

export function reconcilePersistedChatMessages<T extends RecoverableChatMessage>(messages: T[]): T[] {
    return messages.reduce<T[]>((restored, message) => {
        const orphanedAgentMessage = message.role === 'assistant' && Boolean(message.agent) && !message.complete
        if (!orphanedAgentMessage) {
            restored.push(message)
            return restored
        }

        if (AGENT_PLACEHOLDER_PATTERN.test(message.content)) {
            return restored
        }

        restored.push({ ...message, complete: true })
        return restored
    }, [])
}
