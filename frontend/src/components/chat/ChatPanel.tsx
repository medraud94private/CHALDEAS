/**
 * ChatPanel - SHEBA AI Chat Interface
 */
import { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation } from '@tanstack/react-query'
import { chatApi } from '../../api/client'
import { AgentResponseRenderer } from './AgentResponseRenderer'
import { useTimelineStore } from '../../store/timelineStore'
import { useGlobeStore } from '../../store/globeStore'
import type { AgentResponse } from '../../types'
import './chat.css'

interface ChatMessage {
  id: string
  type: 'user' | 'agent'
  content: string
  response?: AgentResponse
  timestamp: Date
}

interface Props {
  isOpen: boolean
  onClose: () => void
  onFollowupClick?: (query: string) => void
  initialQuery?: string | null
  onQueryProcessed?: () => void
}

const API_KEY_STORAGE_KEY = 'chaldeas_openai_api_key'

export function ChatPanel({ isOpen, onClose, onFollowupClick, initialQuery, onQueryProcessed }: Props) {
  const { t } = useTranslation()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [showApiKeyInput, setShowApiKeyInput] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const initialQueryProcessed = useRef(false)

  // Load API key from localStorage on mount
  useEffect(() => {
    const savedKey = localStorage.getItem(API_KEY_STORAGE_KEY)
    if (savedKey) {
      setApiKey(savedKey)
    }
  }, [])

  // Save API key to localStorage
  const saveApiKey = () => {
    if (apiKey) {
      localStorage.setItem(API_KEY_STORAGE_KEY, apiKey)
      setShowApiKeyInput(false)
    }
  }

  // Clear API key
  const clearApiKey = () => {
    localStorage.removeItem(API_KEY_STORAGE_KEY)
    setApiKey('')
  }

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus()
    }
  }, [isOpen])

  // Agent mutation - passes API key if available
  const agentMutation = useMutation({
    mutationFn: (query: string) => chatApi.agent(query, apiKey || undefined),
    onSuccess: (response) => {
      const agentResponse = response.data as AgentResponse
      setMessages((prev) => [
        ...prev,
        {
          id: `agent-${Date.now()}`,
          type: 'agent',
          content: agentResponse.response.answer,
          response: agentResponse,
          timestamp: new Date(),
        },
      ])

      // Auto-navigate to target year if available
      if (agentResponse.response.navigation?.target_year) {
        useTimelineStore.getState().setCurrentYear(agentResponse.response.navigation.target_year)
      }

      // Set highlighted locations on globe if available
      if (agentResponse.response.navigation?.locations) {
        useGlobeStore.getState().setHighlightedLocations(agentResponse.response.navigation.locations)
      }
    },
    onError: (error) => {
      console.error('Agent error:', error)
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          type: 'agent',
          content: t('chat.error'),
          timestamp: new Date(),
        },
      ])
    },
  })

  // Process initial query from "Ask SHEBA" button
  useEffect(() => {
    if (isOpen && initialQuery && !initialQueryProcessed.current) {
      initialQueryProcessed.current = true

      // Add user message
      setMessages((prev) => [
        ...prev,
        {
          id: `user-${Date.now()}`,
          type: 'user',
          content: initialQuery,
          timestamp: new Date(),
        },
      ])

      // Send to agent
      agentMutation.mutate(initialQuery)
      onQueryProcessed?.()
    }
  }, [isOpen, initialQuery, agentMutation, onQueryProcessed])

  // Reset flag when panel closes
  useEffect(() => {
    if (!isOpen) {
      initialQueryProcessed.current = false
    }
  }, [isOpen])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || agentMutation.isPending) return

    const query = input.trim()
    setInput('')

    // Add user message
    setMessages((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        type: 'user',
        content: query,
        timestamp: new Date(),
      },
    ])

    // Send to agent
    agentMutation.mutate(query)
  }

  const handleFollowup = (query: string) => {
    setInput(query)
    onFollowupClick?.(query)
    // Auto-submit followup
    setMessages((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        type: 'user',
        content: query,
        timestamp: new Date(),
      },
    ])
    agentMutation.mutate(query)
  }

  if (!isOpen) return null

  return (
    <div className="chat-panel">
      {/* Header */}
      <div className="chat-header">
        <div className="chat-title">
          <span className="chat-icon">◎</span>
          <div>
            <span className="chat-title-text">{t('chat.title')}</span>
            <span className="chat-subtitle">{t('chat.subtitle')}</span>
          </div>
        </div>
        <div className="chat-header-actions">
          <button
            className={`api-key-status ${apiKey ? 'has-key' : ''}`}
            onClick={() => setShowApiKeyInput(!showApiKeyInput)}
            title={t('chat.apiKey.hint')}
          >
            🔑 {apiKey ? t('chat.apiKey.saved') : t('chat.apiKey.notSet')}
          </button>
          <button className="chat-close-btn" onClick={onClose}>
            ✕
          </button>
        </div>
      </div>

      {/* API Key Input */}
      {showApiKeyInput && (
        <div className="api-key-panel">
          <div className="api-key-label">{t('chat.apiKey.label')}</div>
          <div className="api-key-input-row">
            <input
              type="password"
              className="api-key-input"
              placeholder={t('chat.apiKey.placeholder')}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
            <button className="api-key-save-btn" onClick={saveApiKey}>
              {t('chat.apiKey.save')}
            </button>
            {apiKey && (
              <button className="api-key-clear-btn" onClick={clearApiKey}>
                {t('chat.apiKey.clear')}
              </button>
            )}
          </div>
          <div className="api-key-hint">{t('chat.apiKey.hint')}</div>
        </div>
      )}

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-welcome">
            <div className="welcome-icon">◎</div>
            <h3>{t('chat.welcome.title')}</h3>
            <p>{t('chat.welcome.description')}</p>
            <div className="welcome-examples">
              <button onClick={() => handleFollowup(t('chat.welcome.examples.compare'))}>
                {t('chat.welcome.examples.compare')}
              </button>
              <button onClick={() => handleFollowup(t('chat.welcome.examples.socrates'))}>
                {t('chat.welcome.examples.socrates')}
              </button>
              <button onClick={() => handleFollowup(t('chat.welcome.examples.persian'))}>
                {t('chat.welcome.examples.persian')}
              </button>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div key={msg.id} className={`chat-message ${msg.type}`}>
            {msg.type === 'user' ? (
              <div className="message-content user-message">
                <span className="message-text">{msg.content}</span>
              </div>
            ) : (
              <div className="message-content agent-message">
                {msg.response ? (
                  <AgentResponseRenderer
                    response={msg.response.response}
                  />
                ) : (
                  <p className="message-text">{msg.content}</p>
                )}
                {/* Followup buttons */}
                {msg.response?.response.suggested_followups && (
                  <div className="message-followups">
                    {msg.response.response.suggested_followups.map((q, i) => (
                      <button
                        key={i}
                        className="followup-chip"
                        onClick={() => handleFollowup(q)}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {agentMutation.isPending && (
          <div className="chat-message agent">
            <div className="message-content agent-message">
              <div className="loading-indicator">
                <span className="loading-dot" />
                <span className="loading-dot" />
                <span className="loading-dot" />
                <span className="loading-text">{t('chat.analyzing')}</span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form className="chat-input-container" onSubmit={handleSubmit}>
        <input
          ref={inputRef}
          type="text"
          className="chat-input"
          placeholder={t('chat.inputPlaceholder')}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={agentMutation.isPending}
        />
        <button
          type="submit"
          className="chat-send-btn"
          disabled={!input.trim() || agentMutation.isPending}
        >
          ▶
        </button>
      </form>
    </div>
  )
}
