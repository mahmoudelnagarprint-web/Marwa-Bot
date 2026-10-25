'use client'

// components/agent/MessageBubble.tsx — فقاعة رسالة بحركة دخول سلسة + Markdown + جداول
// + Scratchpad (التفكير الداخلي) Collapsible + رقائق استدعاءات الأدوات (Tool Chips).
import { useState } from 'react'
import { motion } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Brain, ChevronDown, Wrench } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ChatMessage } from '@/stores/agentStore'

export function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user'
  const isSystem = msg.role === 'system'
  const [openPad, setOpenPad] = useState(false)

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 14, scale: 0.985 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -8, scale: 0.98 }}
      transition={{ type: 'spring', stiffness: 320, damping: 30 }}
      className={cn('flex w-full', isUser ? 'justify-start' : 'justify-end', isSystem && 'justify-center')}
    >
      <div
        className={cn(
          'max-w-[86%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm',
          isSystem
            ? 'border border-gold-800/50 bg-gold-400/[0.05] text-gold-200'
            : isUser
              ? 'rounded-es-sm border border-gold-700/40 bg-gradient-to-bl from-gold-400/[0.14] to-gold-400/[0.06] text-foreground'
              : 'rounded-ee-sm border border-matte-600 bg-matte-800 text-foreground',
        )}
      >
        <div className="md-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
        </div>

        {/* التفكير الداخلي — Collapsible أنيق */}
        {msg.scratchpad && (
          <div className="mt-2 border-t border-matte-600/60 pt-1.5">
            <button
              type="button"
              onClick={() => setOpenPad((v) => !v)}
              className="inline-flex items-center gap-1.5 text-[10px] text-matte-600 transition-colors hover:text-gold-300"
              aria-expanded={openPad}
            >
              <Brain className="size-3" aria-hidden="true" />
              التفكير الداخلي
              <ChevronDown className={cn('size-3 transition-transform', !openPad && '-rotate-90')} aria-hidden="true" />
            </button>
            {openPad && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                className="mt-1.5 overflow-hidden rounded-md border border-matte-600 bg-matte-900 p-2 font-mono text-[10px] leading-relaxed text-matte-600"
              >
                {msg.scratchpad}
              </motion.div>
            )}
          </div>
        )}

        {/* رقائق استدعاءات الأدوات */}
        {(msg.toolCalls?.length ?? 0) > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {msg.toolCalls!.map((t) => (
              <span
                key={t.id}
                className={cn(
                  'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 font-mono text-[10px]',
                  t.status === 'running'
                    ? 'border-sky-500/30 bg-sky-500/10 text-sky-300'
                    : t.status === 'done'
                      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                      : 'border-rose-500/30 bg-rose-500/10 text-rose-300',
                )}
                title={t.preview}
              >
                <Wrench className="size-2.5" aria-hidden="true" />
                {t.tool}
                {t.ms !== undefined && <span className="opacity-70">{t.ms}ms</span>}
              </span>
            ))}
          </div>
        )}

        <span className="mt-1.5 block text-end text-[10px] font-mono opacity-60">{msg.time}</span>
      </div>
    </motion.div>
  )
}
