// =============================================================================
// AI Overhaul - API Endpoints Manager
// =============================================================================

interface APIResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
}

interface AISettings {
  stashAIServer: string;
  port: string;
  enableVisageIntegration?: boolean;
  visageThreshold?: number;
}

interface TaskResult {
  task_id: string;
  adapter_name: string;
  task_type: string;
  status: string;
  input_data: any;
  output_json: any;
  error_message?: string;
  processing_time_ms?: number;
  retry_count: number;
  created_at: string;
  finished_at?: string;
  job_id?: string;
}

interface QueueStats {
  total_tasks: number;
  pending_tasks: number;
  running_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
}

interface HealthData {
  status: string;
  timestamp: string;
  database: string;
  version: string;
  queue?: {
    queue_healthy: boolean;
    health_check_result: any;
    timestamp: string;
    queue_enabled: boolean;
    direct_mode: boolean;
    manager_healthy: boolean;
  };
}

class AIEndpoints {
  private settings: AISettings;

  constructor(settings?: AISettings) {
    this.settings = settings || this.loadSettings();
  }

  // =============================================================================
  // SETTINGS MANAGEMENT
  // =============================================================================
  
  private loadSettings(): AISettings {
    const defaults: AISettings = {
      stashAIServer: 'localhost',
      port: '9998',
      enableVisageIntegration: false,
      visageThreshold: 0.7
    };

    const saved = localStorage.getItem('ai_overhaul_settings');
    if (saved) {
      try {
        return { ...defaults, ...JSON.parse(saved) };
      } catch (e) {
        console.warn('Failed to load AI Overhaul settings:', e);
        return defaults;
      }
    }

    return defaults;
  }

  updateSettings(newSettings: Partial<AISettings>): void {
    this.settings = { ...this.settings, ...newSettings };
    localStorage.setItem('ai_overhaul_settings', JSON.stringify(this.settings));
  }

  getBaseUrl(): string {
    return `http://${this.settings.stashAIServer}:${this.settings.port}`;
  }

  // =============================================================================
  // HTTP REQUEST HELPER
  // =============================================================================

  private async makeRequest<T = any>(
    endpoint: string, 
    options: RequestInit = {}
  ): Promise<APIResponse<T>> {
    try {
      const url = `${this.getBaseUrl()}${endpoint}`;
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      
      const response = await fetch(url, {
        signal: controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        },
        ...options
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      return { success: true, data };
    } catch (error: any) {
      console.error('API Request Error:', error);
      return { success: false, error: error.message };
    }
  }

  // =============================================================================
  // CORE SERVER ENDPOINTS
  // =============================================================================

  async getServerHealth(): Promise<APIResponse<HealthData>> {
    return this.makeRequest('/health');
  }

  async getQueueStats(): Promise<APIResponse<QueueStats>> {
    return this.makeRequest('/api/queue/stats');
  }

  async getQueueTasks(limit: number = 50, offset: number = 0, status?: string): Promise<APIResponse<TaskResult[]>> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString()
    });
    
    if (status) {
      params.append('status', status);
    }
    
    return this.makeRequest(`/api/queue/tasks?${params}`);
  }

  async getTask(taskId: string): Promise<APIResponse<TaskResult>> {
    return this.makeRequest(`/api/queue/task/${taskId}`);
  }

  // =============================================================================
  // AI SERVICE ENDPOINTS
  // =============================================================================

  async testVisageService(): Promise<APIResponse<any>> {
    const visageUrl = `http://${this.settings.stashAIServer}:9997/health`;
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const response = await fetch(visageUrl, {
        signal: controller.signal,
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });
      
      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        return { success: true, data };
      } else {
        throw new Error(`Visage service unavailable: ${response.status}`);
      }
    } catch (error: any) {
      return { success: false, error: error.message };
    }
  }

  async createVisageTask(imageId: string, imageData?: string): Promise<APIResponse<TaskResult>> {
    if (!this.settings.enableVisageIntegration) {
      return { success: false, error: 'Visage integration is disabled' };
    }

    const payload = {
      image_id: imageId,
      image_data: imageData,
      threshold: this.settings.visageThreshold,
      visage_api_url: `http://${this.settings.stashAIServer}:9997/api/predict_1`,
      additional_params: {
        max_faces: 10,
        return_embeddings: false,
        source: 'ai_overhaul_plugin'
      }
    };

    return this.makeRequest('/api/visage/task', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }

  // =============================================================================
  // SERVICE DISCOVERY
  // =============================================================================

  async discoverServices(): Promise<APIResponse<Array<{ name: string; port: string; status: string; description: string; health?: any }>>> {
    const services = [
      { name: 'Visage', port: '9997', description: 'Face Recognition' },
      { name: 'Content Analysis', port: '9999', description: 'Content Classification' },
      { name: 'Scene Analysis', port: '9996', description: 'Scene Detection' }
    ];

    const results: Array<{ name: string; port: string; status: string; description: string; health?: any }> = [];

    for (const service of services) {
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3000);
        
        const testUrl = `http://${this.settings.stashAIServer}:${service.port}/health`;
        const response = await fetch(testUrl, {
          method: 'GET',
          signal: controller.signal,
          headers: { 'Content-Type': 'application/json' }
        });
        
        clearTimeout(timeoutId);
        
        if (response.ok) {
          const serviceHealth = await response.json();
          results.push({
            ...service,
            status: 'available',
            health: serviceHealth
          });
        }
      } catch (error) {
        // Service not available - skip silently
        console.debug(`${service.name} service not available:`, error);
      }
    }

    return { success: true, data: results };
  }

  // =============================================================================
  // ENDPOINT INVENTORY
  // =============================================================================

  getEndpointInventory(): Record<string, { endpoint: string; method: string; description: string; parameters?: string[] }> {
    const baseUrl = this.getBaseUrl();
    
    return {
      // Core Server Endpoints
      'server_health': {
        endpoint: `${baseUrl}/health`,
        method: 'GET',
        description: 'Get server health status and system information'
      },
      'queue_stats': {
        endpoint: `${baseUrl}/api/queue/stats`,
        method: 'GET',
        description: 'Get queue statistics and task counts'
      },
      'queue_tasks': {
        endpoint: `${baseUrl}/api/queue/tasks`,
        method: 'GET',
        description: 'Get paginated list of queue tasks',
        parameters: ['limit', 'offset', 'status']
      },
      'get_task': {
        endpoint: `${baseUrl}/api/queue/task/{task_id}`,
        method: 'GET',
        description: 'Get specific task details by ID',
        parameters: ['task_id']
      },

      // AI Service Endpoints  
      'visage_health': {
        endpoint: `http://${this.settings.stashAIServer}:9997/health`,
        method: 'GET',
        description: 'Check Visage face recognition service health'
      },
      'visage_task': {
        endpoint: `${baseUrl}/api/visage/task`,
        method: 'POST',
        description: 'Create new Visage face recognition task',
        parameters: ['image_id', 'image_data', 'threshold', 'visage_api_url']
      },
      
      // Discovery Endpoints
      'content_analysis_health': {
        endpoint: `http://${this.settings.stashAIServer}:9999/health`,
        method: 'GET',
        description: 'Check Content Analysis service health'
      },
      'scene_analysis_health': {
        endpoint: `http://${this.settings.stashAIServer}:9996/health`,
        method: 'GET',
        description: 'Check Scene Analysis service health'
      }
    };
  }

  // =============================================================================
  // UTILITY METHODS
  // =============================================================================

  async testAllEndpoints(): Promise<Record<string, { success: boolean; responseTime: number; error?: string }>> {
    const endpoints = this.getEndpointInventory();
    const results: Record<string, { success: boolean; responseTime: number; error?: string }> = {};

    for (const [key, config] of Object.entries(endpoints)) {
      const startTime = Date.now();
      
      try {
        // Skip POST endpoints in general testing
        if (config.method === 'POST') {
          results[key] = { success: false, responseTime: 0, error: 'POST endpoint - skipped in general test' };
          continue;
        }

        // Skip parameterized endpoints
        if (config.endpoint.includes('{')) {
          results[key] = { success: false, responseTime: 0, error: 'Parameterized endpoint - skipped in general test' };
          continue;
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        
        const response = await fetch(config.endpoint, {
          method: config.method,
          signal: controller.signal,
          headers: { 'Content-Type': 'application/json' }
        });
        
        clearTimeout(timeoutId);
        const responseTime = Date.now() - startTime;

        results[key] = {
          success: response.ok,
          responseTime,
          error: response.ok ? undefined : `HTTP ${response.status}`
        };
      } catch (error: any) {
        const responseTime = Date.now() - startTime;
        results[key] = {
          success: false,
          responseTime,
          error: error.message
        };
      }
    }

    return results;
  }
}

export default AIEndpoints;