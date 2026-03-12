import { useState, useEffect } from 'react'

interface UseTypeWriterOptions {
    speed?: number        // 每字符间隔(ms)，默认30ms
    onComplete?: () => void
}

interface UseTypeWriterReturn {
    displayed: string     // 已显示的文本
    isTyping: boolean     // 是否正在打字
    progress: number      // 进度 0-1
}

/**
 * 打字机效果 Hook
 * 
 * @param text 要显示的完整文本
 * @param isActive 是否开始打字
 * @param options 配置选项
 * @returns 打字机状态和进度
 * 
 * @example
 * const { displayed, isTyping, progress } = useTypeWriter(
 *     fullText, 
 *     isActive, 
 *     { speed: 30 }
 * )
 */
export function useTypeWriter(
    text: string,
    isActive: boolean,
    options: UseTypeWriterOptions = {}
): UseTypeWriterReturn {
    const { speed = 30, onComplete } = options
    const [displayed, setDisplayed] = useState('')
    const [isTyping, setIsTyping] = useState(false)
    const [hasCompleted, setHasCompleted] = useState(false)

    useEffect(() => {
        // 重置状态当文本变化时
        if (!isActive) {
            setDisplayed('')
            setIsTyping(false)
            setHasCompleted(false)
            return
        }

        // 如果已经完成，不再重复
        if (hasCompleted && displayed === text) {
            return
        }

        // 如果文本为空，直接完成
        if (!text) {
            setIsTyping(false)
            if (!hasCompleted) {
                setHasCompleted(true)
                onComplete?.()
            }
            return
        }

        setIsTyping(true)
        let index = 0
        setDisplayed('')

        const timer = setInterval(() => {
            if (index < text.length) {
                setDisplayed(text.slice(0, index + 1))
                index++
            } else {
                clearInterval(timer)
                setIsTyping(false)
                setHasCompleted(true)
                onComplete?.()
            }
        }, speed)

        return () => clearInterval(timer)
    }, [text, isActive, speed, onComplete, hasCompleted, displayed])

    const progress = text.length > 0 ? displayed.length / text.length : 0

    return { displayed, isTyping, progress }
}

/**
 * 多段落打字机效果 Hook
 * 用于报告章节的流式渲染
 */
interface UseStreamingSectionOptions {
    speed?: number
}

interface UseStreamingSectionReturn {
    displayed: string
    isTyping: boolean
    isComplete: boolean
}

export function useStreamingSection(
    chunks: string[],      // 文本片段数组
    isActive: boolean,
    options: UseStreamingSectionOptions = {}
): UseStreamingSectionReturn {
    const { speed = 30 } = options
    const [displayed, setDisplayed] = useState('')
    const [isTyping, setIsTyping] = useState(false)
    const [isComplete, setIsComplete] = useState(false)

    useEffect(() => {
        if (!isActive || chunks.length === 0) {
            if (!isActive) {
                setDisplayed('')
                setIsTyping(false)
                setIsComplete(false)
            }
            return
        }

        // 合并所有片段
        const fullText = chunks.join('')
        
        // 如果已经显示完整内容，标记完成
        if (displayed === fullText && fullText.length > 0) {
            setIsTyping(false)
            setIsComplete(true)
            return
        }

        setIsTyping(true)
        setIsComplete(false)

        const timer = setInterval(() => {
            setDisplayed(prev => {
                if (prev.length < fullText.length) {
                    return fullText.slice(0, prev.length + 1)
                }
                clearInterval(timer)
                setIsTyping(false)
                setIsComplete(true)
                return prev
            })
        }, speed)

        return () => clearInterval(timer)
    }, [chunks, isActive, speed, displayed])

    return { displayed, isTyping, isComplete }
}

export default useTypeWriter
