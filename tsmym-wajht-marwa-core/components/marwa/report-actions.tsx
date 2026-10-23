'use client'

import { useState } from 'react'
import { Check, Copy, ExternalLink } from 'lucide-react'

export function ReportActions({
  actions,
  body,
}: {
  actions?: { type: string; label: string; href?: string }[] | null
  body: string
}) {
  const [copied, setCopied] = useState(false)
  if (!actions?.length) return null
  return (
    <div className="mt-3 flex flex-wrap gap-2 border-t border-border/50 pt-3">
      {actions.map((action, index) => {
        if (action.type === 'copy') {
          return (
            <button
              key={`${action.type}-${index}`}
              type="button"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(body)
                  setCopied(true)
                  window.setTimeout(() => setCopied(false), 1600)
                } catch {
                  setCopied(false)
                }
              }}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-secondary/70 px-3 py-1.5 text-xs font-medium text-foreground hover:bg-secondary"
            >
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              {copied ? 'اتنسخ' : action.label}
            </button>
          )
        }
        if (action.type === 'navigate' && action.href?.startsWith('/agent/')) {
          return (
            <a
              key={`${action.type}-${index}`}
              href={action.href}
              className="inline-flex items-center gap-1.5 rounded-lg border border-primary/30 bg-primary/10 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/20"
            >
              <ExternalLink className="size-3.5" />
              {action.label}
            </a>
          )
        }
        return null
      })}
    </div>
  )
}
