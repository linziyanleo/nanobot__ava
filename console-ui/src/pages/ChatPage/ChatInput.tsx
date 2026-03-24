import { useState } from 'react'
import { Send } from 'lucide-react'

interface ChatInputProps {
  onSend: (message: string) => void
  disabled: boolean
  isMobile?: boolean
}

export function ChatInput({ onSend, disabled, isMobile }: ChatInputProps) {
  const [input, setInput] = useState('')

  const handleSend = () => {
    const msg = input.trim()
    if (!msg || disabled) return
    setInput('')
    onSend(msg)
  }

  return (
    <div className={`p-4 border-t border-[var(--border)] ${isMobile ? 'pb-3' : 'pb-[calc(1rem+env(safe-area-inset-bottom,0px))]'}`}>
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder="Type a message..."
          disabled={disabled}
          className="flex-1 px-4 py-2.5 rounded-xl bg-[var(--bg-secondary)] border border-[var(--border)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)] disabled:opacity-50"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || disabled}
          className="px-4 py-2.5 rounded-xl bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white disabled:opacity-40 transition-colors"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  )
}
