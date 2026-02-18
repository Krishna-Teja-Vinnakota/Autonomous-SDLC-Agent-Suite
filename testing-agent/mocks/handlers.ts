// MSW API handlers for integration tests
import { http, HttpResponse } from 'msw';

export const handlers = [
  // Example API handler - replace with your actual API endpoints
  http.get('/api/data', () => {
    return HttpResponse.json({
      data: 'mocked response'
    }, { status: 200 });
  }),
  
  http.post('/api/data', () => {
    return HttpResponse.json({
      success: true
    }, { status: 201 });
  }),
];
