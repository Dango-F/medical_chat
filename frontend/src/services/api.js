import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000, // 增加到 120 秒，LLM 生成可能需要较长时间
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
api.interceptors.request.use(
  config => {
    // Add auth token if available
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => Promise.reject(error)
)

// Response interceptor
api.interceptors.response.use(
  response => response,
  error => {
    console.error('API Error:', error.response?.data || error.message)
    return Promise.reject(error)
  }
)

export const queryAPI = {
  // Submit a query (non-streaming)
  async query(queryData, signal) {
    const response = await api.post('/query', queryData, { signal })
    return response.data
  },

  // Stream query using fetch with POST (SSE)
  // 使用 POST 方式发送 SSE 请求，支持完整的请求体
  async streamQuery(queryData, onMessage, onError, onComplete, signal) {
    try {
      const response = await fetch('/api/v1/query/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(queryData),
        signal
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        
        if (done) {
          break
        }

        buffer += decoder.decode(value, { stream: true })
        
        // 解析 SSE 数据
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // 保留不完整的行

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              onMessage(data)
              
              if (data.status === 'complete') {
                if (onComplete) onComplete(data.response)
              } else if (data.status === 'error') {
                if (onError) onError(new Error(data.message))
              }
            } catch (e) {
              console.error('Parse error:', e, 'Line:', line)
            }
          }
        }
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        console.log('Stream request aborted')
        return
      }
      console.error('Stream error:', error)
      if (onError) onError(error)
    }
  },

  // Get example queries
  async getExamples() {
    const response = await api.get('/query/examples')
    return response.data
  }
}

export const kgAPI = {
  // Get node details
  async getNode(nodeId) {
    const response = await api.get(`/kg/node/${nodeId}`)
    return response.data
  },

  // Search nodes
  async searchNodes(query, types = null, limit = 20) {
    const params = { q: query, limit }
    if (types) params.types = types.join(',')
    const response = await api.get('/kg/search', { params })
    return response.data
  },

  // Get graph data for visualization
  async getGraphData(limit = 100) {
    const response = await api.get('/kg/graph', { params: { limit } })
    return response.data
  },

  // Get graph statistics
  async getStats() {
    const response = await api.get('/kg/stats')
    return response.data
  },

  // Get node types
  async getNodeTypes() {
    const response = await api.get('/kg/types')
    return response.data
  },

  // Get relationship types
  async getRelationshipTypes() {
    const response = await api.get('/kg/relationships')
    return response.data
  }
}

export const feedbackAPI = {
  // Submit feedback
  async submit(feedbackData) {
    const response = await api.post('/feedback', feedbackData)
    return response.data
  }
}

export const settingsAPI = {
  // Get LLM status
  async getLLMStatus() {
    const response = await api.get('/settings/llm/status')
    return response.data
  },

  // Update LLM config
  async updateLLM(config) {
    const response = await api.post('/settings/llm/update', config)
    return response.data
  },

  // Test LLM connection
  async testLLM(config) {
    const response = await api.post('/settings/llm/test', config)
    return response.data
  }
}

export const sessionAPI = {
  async saveSession(userId, session) {
    const response = await api.post('/sessions', { user_id: userId, session })
    return response.data
  },

  async listSessions(userId) {
    const response = await api.get(`/sessions/${encodeURIComponent(userId)}`)
    return response.data
  },

  async getSession(userId, sessionId) {
    const response = await api.get(`/sessions/${encodeURIComponent(userId)}/${encodeURIComponent(sessionId)}`)
    return response.data
  },

  async deleteSession(userId, sessionId) {
    const response = await api.delete(`/sessions/${encodeURIComponent(userId)}/${encodeURIComponent(sessionId)}`)
    return response.data
  }
}

export default api

