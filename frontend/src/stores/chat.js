import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { queryAPI, sessionAPI } from '@/services/api'

const STORAGE_KEY = 'medical_chat_sessions'
const CURRENT_SESSION_KEY = 'medical_chat_current_session_id'
const LEGACY_STORAGE_KEY = 'medical_chat_messages'

export const useChatStore = defineStore('chat', () => {
  // State
  const sessions = ref([])
  const currentSessionId = ref(null)
  const isLoading = ref(false)
  const error = ref(null)
  const examples = ref([])
  
  // 用于取消请求的 AbortController（按会话存储）
  const abortControllers = {}

  function setAbortController(sessionId, controller) {
    if (!sessionId) return
    abortControllers[sessionId] = controller
  }

  function getAbortController(sessionId) {
    if (!sessionId) return null
    return abortControllers[sessionId] || null
  }

  function clearAbortController(sessionId) {
    if (!sessionId) return
    delete abortControllers[sessionId]
  }

  // Getters
  const currentSession = computed(() => {
    return sessions.value.find(s => s.id === currentSessionId.value)
  })

  const messages = computed(() => {
    return currentSession.value?.messages || []
  })

  const hasMessages = computed(() => messages.value.length > 0)
  const lastMessage = computed(() => messages.value[messages.value.length - 1])
  const isCurrentLoading = computed(() => currentSession.value ? currentSession.value.messages.some(m => m.isLoading) : false)

  // 从 localStorage 加载会话
  function loadFromStorage() {
    try {
      const storedSessions = localStorage.getItem(STORAGE_KEY)
      const storedCurrentId = localStorage.getItem(CURRENT_SESSION_KEY)
      
      if (storedSessions) {
        const parsed = JSON.parse(storedSessions)
        sessions.value = parsed.map(s => ({
          ...s,
          messages: s.messages.filter(m => !m.isLoading).map(m => ({
            ...m,
            timestamp: new Date(m.timestamp)
          })),
          updatedAt: new Date(s.updatedAt || Date.now())
        }))
        
        if (storedCurrentId && sessions.value.find(s => s.id === storedCurrentId)) {
          currentSessionId.value = storedCurrentId
        } else {
          currentSessionId.value = sessions.value[0].id
        }
      } else {
        // 尝试迁移旧数据
        const legacyMessages = localStorage.getItem(LEGACY_STORAGE_KEY)
        if (legacyMessages) {
          try {
            const parsed = JSON.parse(legacyMessages)
            const msgs = parsed.filter(m => !m.isLoading).map(m => ({
              ...m,
              timestamp: new Date(m.timestamp)
            }))
            
            if (msgs.length > 0) {
              const newId = Date.now().toString()
              const firstUserMsg = msgs.find(m => m.role === 'user')
              const title = firstUserMsg ? (firstUserMsg.content.length > 20 ? firstUserMsg.content.slice(0, 20) + '...' : firstUserMsg.content) : '历史对话'
              
              const newSession = {
                id: newId,
                title: title,
                messages: msgs,
                updatedAt: new Date()
              }
              sessions.value = [newSession]
              currentSessionId.value = newId
              
              // 迁移完成后，可以考虑删除旧数据，这里保留以防万一
              // localStorage.removeItem(LEGACY_STORAGE_KEY)
            } else {
              createNewSession()
            }
          } catch (e) {
            console.error('Failed to migrate legacy messages:', e)
            createNewSession()
          }
        } else {
          createNewSession()
        }
      }
    } catch (e) {
      console.error('Failed to load sessions from storage:', e)
      createNewSession()
    }
  }

  // 保存会话到 localStorage
  function saveToStorage() {
    try {
      const toSave = sessions.value.map(s => ({
        ...s,
        messages: s.messages.filter(m => !m.isLoading)
      }))
      localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave))
      if (currentSessionId.value) {
        localStorage.setItem(CURRENT_SESSION_KEY, currentSessionId.value)
      }

      // 如果用户设置了 user_id（跨设备同步），则把当前会话同步到后端
      const userId = localStorage.getItem('medical_chat_user_id')
      const currentSessionForSync = sessions.value.find(s => s.id === currentSessionId.value)
      if (userId && currentSessionForSync) {
        try {
          sessionAPI.saveSession(userId, currentSessionForSync)
        } catch (e) {
          console.warn('Failed to sync session to server:', e)
        }
      }

    } catch (e) {
      console.error('Failed to save sessions to storage:', e)
    }
  }

  // 监听 sessions 和 currentSessionId 变化，自动保存
  watch([sessions, currentSessionId], () => {
    saveToStorage()
  }, { deep: true })

  // 创建新会话
  function createNewSession() {
    // 如果当前会话为空，就不创建新的，直接用当前的
    const existing = sessions.value.find(s => s.id === currentSessionId.value)
    if (existing && existing.messages.length === 0) {
      return
    }

    const newId = Date.now().toString()
    const newSession = {
      id: newId,
      title: '新对话',
      messages: [],
      updatedAt: new Date()
    }
    sessions.value.unshift(newSession) // 新会话排在前面
    currentSessionId.value = newId
  }

  // 切换会话（不取消其他会话的请求，允许多会话并行）
  function switchSession(id) {
    if (sessions.value.find(s => s.id === id)) {
      currentSessionId.value = id
    }
  }

  // 删除会话
  function deleteSession(id) {
    const index = sessions.value.findIndex(s => s.id === id)
    if (index === -1) return

    // 如果删除的会话当前有正在进行的请求，取消该会话的请求
    if (getAbortController(id)) {
      cancelCurrentRequest(id)
    }

    sessions.value.splice(index, 1)

    // 如果删除了当前会话，切换到其他会话
    if (id === currentSessionId.value) {
      if (sessions.value.length > 0) {
        currentSessionId.value = sessions.value[0].id
      } else {
        createNewSession()
      }
    }
  }

  // 批量删除会话
  function deleteSessions(ids) {
    const idsSet = new Set(ids)
    if (idsSet.size === 0) return

    // 取消被删除会话中存在的请求
    for (const id of idsSet) {
      if (getAbortController(id)) {
        cancelCurrentRequest(id)
      }
    }

    // 过滤掉要删除的会话
    sessions.value = sessions.value.filter(s => !idsSet.has(s.id))

    // 如果当前会话被删除了，需要切换到其他会话
    if (idsSet.has(currentSessionId.value)) {
      if (sessions.value.length > 0) {
        currentSessionId.value = sessions.value[0].id
      } else {
        createNewSession()
      }
    }
  }

  // 清空当前会话消息（不删除会话本身，或者重置）
  function clearMessages() {
    cancelCurrentRequest()
    const session = sessions.value.find(s => s.id === currentSessionId.value)
    if (session) {
      session.messages = []
      session.title = '新对话' // 重置标题
      error.value = null
      isLoading.value = false
    }
  }

  // Set user id for cross-device syncing (store in localStorage)
  function setUserId(userId) {
    if (userId) {
      localStorage.setItem('medical_chat_user_id', userId)
    } else {
      localStorage.removeItem('medical_chat_user_id')
    }
  }

  function getUserId() {
    return localStorage.getItem('medical_chat_user_id')
  }

  // 取消指定会话的请求（默认取消当前会话）
  function cancelCurrentRequest(sessionId = currentSessionId.value) {
    const ctrl = getAbortController(sessionId)
    if (ctrl) {
      try {
        ctrl.abort()
      } catch (e) {
        console.warn('Abort failed:', e)
      }
      clearAbortController(sessionId)
    }

    // 更新全局 isLoading（若没有任何会话在加载则设为 false）
    updateGlobalLoading()
  }

  function updateGlobalLoading() {
    isLoading.value = sessions.value.some(s => s.messages && s.messages.some(m => m.isLoading))
  }

  // 移除最后一组问答（用于重新提问）
  function removeLastQA() {
    const session = sessions.value.find(s => s.id === currentSessionId.value)
    if (!session) return
    
    const msgs = session.messages
    if (msgs.length >= 2) {
      const lastMsg = msgs[msgs.length - 1]
      if (lastMsg.isLoading) {
        session.messages = msgs.slice(0, -2)
      }
    } else if (msgs.length === 1) {
      const lastMsg = msgs[0]
      if (lastMsg.isLoading) {
        session.messages = []
      }
    }
  }

  // Actions
  async function sendMessage(query) {
    if (!query.trim() || !currentSessionId.value) return

    const sessionId = currentSessionId.value
    const session = sessions.value.find(s => s.id === sessionId)
    if (!session) return

    // 如果本会话正在加载，取消该会话的请求并移除之前的问答（不影响其他会话）
    const currentSessionLoading = session.messages.some(m => m.isLoading)
    if (currentSessionLoading) {
      cancelCurrentRequest(sessionId)
      removeLastQA()
    }

    error.value = null
    
    // 如果是新对话的第一条消息，更新标题
    if (session.messages.length === 0) {
      session.title = query.length > 20 ? query.slice(0, 20) + '...' : query
    }
    
    session.updatedAt = new Date()

    // 创建新的 AbortController 并绑定到当前会话
    const controller = new AbortController()
    setAbortController(sessionId, controller)
    
    // 构建历史消息（发送前的消息，不包括当前问题）
    // 只发送最近 6 轮对话（12 条消息），避免上下文过长
    const historyMessages = session.messages
      .filter(m => !m.isLoading && !m.isError)  // 过滤掉加载中和错误的消息
      .slice(-12)  // 最多取最近 12 条
      .map(m => ({
        role: m.role,
        content: m.content
      }))
    
    // Add user message
    session.messages.push({
      id: Date.now(),
      role: 'user',
      content: query,
      timestamp: new Date()
    })

    // Add loading message (will be updated with streaming content)
    const loadingId = Date.now() + 1
    session.messages.push({
      id: loadingId,
      role: 'assistant',
      content: '',
      isLoading: true,
      isStreaming: true,  // 标记正在流式输出
      timestamp: new Date()
    })

    // 标记本会话为加载中并更新全局状态
    isLoading.value = true
    updateGlobalLoading()

    // 把当前会话移到最前面
    const currentIdx = sessions.value.findIndex(s => s.id === sessionId)
    if (currentIdx > 0) {
        const s = sessions.value.splice(currentIdx, 1)[0]
        sessions.value.unshift(s)
    }

    // 用于累积流式内容
    let streamedContent = ''

    try {
      // 使用流式 API
      await queryAPI.streamQuery(
        {
          query,
          history: historyMessages.length > 0 ? historyMessages : undefined,
          max_answers: 5,
          include_kg_paths: true,
          include_evidence: true
        },
        // onMessage: 处理每个流式数据块
        (data) => {
          const loadingIndex = session.messages.findIndex(m => m.id === loadingId)
          if (loadingIndex === -1) return

          if (data.status === 'content') {
            // 累积流式内容
            streamedContent += data.text
            session.messages[loadingIndex].content = streamedContent
          } else if (data.status === 'searching' || data.status === 'generating') {
            // 更新状态提示
            session.messages[loadingIndex].statusMessage = data.message
          }
        },
        // onError: 处理错误
        (err) => {
          console.error('Stream error:', err)
          const loadingIndex = session.messages.findIndex(m => m.id === loadingId)
          if (loadingIndex !== -1) {
            session.messages[loadingIndex] = {
              id: loadingId,
              role: 'assistant',
              content: `错误: ${err.message || '流式请求失败'}`,
              isError: true,
              isLoading: false,
              isStreaming: false,
              timestamp: new Date()
            }
          }
          error.value = err.message || '流式请求失败'
          // 清理该会话的 AbortController
          clearAbortController(sessionId)
          updateGlobalLoading()
        },
        // onComplete: 流式完成，更新完整响应数据
        (response) => {
          const loadingIndex = session.messages.findIndex(m => m.id === loadingId)
          if (loadingIndex !== -1) {
            session.messages[loadingIndex] = {
              id: loadingId,
              role: 'assistant',
              content: response.answer,
              evidence: response.evidence,
              kgPaths: response.kg_paths,
              confidence: response.confidence_score,
              warnings: response.warnings,
              disclaimer: response.disclaimer,
              queryId: response.query_id,
              processingTime: response.processing_time_ms,
              isLoading: false,
              isStreaming: false,
              timestamp: new Date()
            }
          }
          // 清理该会话的 AbortController 并更新全局 loading
          clearAbortController(sessionId)
          updateGlobalLoading()
          saveToStorage()
        },
        controller.signal
      )
    } catch (err) {
      // 如果是取消的请求，不处理错误
      if (err.name === 'AbortError' || err.code === 'ERR_CANCELED') {
        return
      }
      
      console.error('Query failed:', err)
      
      // 构建详细的错误信息
      let errorMessage = '抱歉，查询处理时发生错误。'
      if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        errorMessage = '请求超时，AI 模型响应较慢，请稍后重试。'
      } else if (err.response?.data?.detail) {
        errorMessage = err.response.data.detail
      } else if (err.message) {
        errorMessage = `错误: ${err.message}`
      }
      
      error.value = errorMessage
      
      // Update loading message with error
      const loadingIndex = session.messages.findIndex(m => m.id === loadingId)
      if (loadingIndex !== -1) {
        session.messages[loadingIndex] = {
          id: loadingId,
          role: 'assistant',
          content: errorMessage,
          isError: true,
          isLoading: false,
          isStreaming: false,
          timestamp: new Date()
        }
      }
      // 清理该会话的 AbortController 并更新全局 loading
      clearAbortController(sessionId)
      updateGlobalLoading()
      saveToStorage()
    }
  }

  async function loadExamples() {
    try {
      const data = await queryAPI.getExamples()
      examples.value = data.examples
    } catch (err) {
      console.error('Failed to load examples:', err)
    }
  }

  // 初始化时加载
  loadFromStorage()

  return {
    // State
    sessions,
    currentSessionId,
    currentSession, // exposed for easy access
    messages, // exposed as readonly computed for compatibility
    isLoading,
    isCurrentLoading,
    error,
    examples,
    // Getters
    hasMessages,
    lastMessage,
    // Actions
    sendMessage,
    loadExamples,
    clearMessages,
    cancelCurrentRequest,
    createNewSession,
    switchSession,
    deleteSession,
    deleteSessions,
    // User id helpers for cross-device session sync
    setUserId,
    getUserId
  }
})
