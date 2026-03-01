import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export const emailsApi = {
    list: (params = {}) => api.get('/emails', { params }),
    get: (id) => api.get(`/emails/${id}`),
    process: (id) => api.post(`/emails/${id}/process`),
    generateReply: (id) => api.post(`/emails/${id}/generate-reply`),
    sendReply: (id, body) => api.post(`/emails/${id}/send-reply`, body),
    rejectReply: (id, body) => api.post(`/emails/${id}/reject-reply`, body),
    detectDeadlines: (id) => api.get(`/emails/${id}/deadlines`),
}

export const repliesApi = {
    pending: () => api.get('/replies/pending'),
    get: (id) => api.get(`/replies/${id}`),
    approve: (id) => api.post(`/replies/${id}/approve`),
    edit: (id, content) => api.post(`/replies/${id}/edit`, { content }),
    reject: (id) => api.delete(`/replies/${id}`),
}

export const calendarApi = {
    availability: (date, duration = 30, timezone = 'UTC') =>
        api.get('/calendar/availability', { params: { date, duration, timezone } }),
    slots: (days_ahead = 3, duration = 30) =>
        api.get('/calendar/slots', { params: { days_ahead, duration } }),
    events: (days = 7) => api.get('/calendar/events', { params: { days } }),
    createEvent: (body) => api.post('/calendar/events', body),
    deadlines: (days = 7) => api.get('/calendar/deadlines', { params: { days } }),
    addFromEmail: (body) => api.post('/calendar/add-from-email', body),
}

export const reportsApi = {
    daily: () => api.get('/reports/daily'),
    weekly: () => api.get('/reports/weekly'),
    generateDaily: () => api.post('/reports/daily'),
    generateWeekly: () => api.post('/reports/weekly'),
}

export const searchApi = {
    search: (params = {}) => api.get('/search', { params }),
}
