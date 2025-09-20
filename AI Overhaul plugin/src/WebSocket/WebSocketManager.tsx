(function () {
  const PluginApi = (window as any).PluginApi;
  const React = PluginApi.React;

  // =============================================================================
  // WEBSOCKET MANAGER FOR TASK STATUS UPDATES
  // =============================================================================

  interface TaskUpdate {
    type: 'task_status';
    task_id: string;
    status: 'pending' | 'running' | 'finished' | 'failed';
    adapter_name: string;
    task_type: string;
    output_json?: any;
    processing_time_ms?: number;
    timestamp: string;
  }

  interface JobUpdate {
    type: 'job_progress';
    job_id: string;
    status: 'pending' | 'running' | 'completed' | 'finished' | 'partial' | 'failed';
    adapter_name: string;
    job_type: string;
    total_tasks: number;
    completed_tasks: number;
    failed_tasks: number;
    progress_percentage: number;
    timestamp: string;
  }

  interface WebSocketMessage {
    type: string;
    [key: string]: any;
  }

  class WebSocketManager {
    private ws: WebSocket | null = null;
    private serverUrl: string;
    private sessionId: string;
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 2;
    private reconnectDelay = 1000;
    private taskCallbacks = new Map<string, (update: TaskUpdate) => void>();
    private jobCallbacks = new Map<string, (update: JobUpdate) => void>();
    private isConnecting = false;
    private connectionTimeout: number | null = null;

    constructor(serverUrl: string, sessionId: string = 'ai_overhaul_session') {
      this.serverUrl = serverUrl;
      this.sessionId = sessionId;
    }

    // =============================================================================
    // CONNECTION MANAGEMENT
    // =============================================================================
    
    connect(): Promise<boolean> {
      return new Promise((resolve, reject) => {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
          resolve(true);
          return;
        }

        if (this.isConnecting) {
          reject(new Error('Connection already in progress'));
          return;
        }

        this.isConnecting = true;
        const wsUrl = `ws://${this.serverUrl.replace(/^https?:\/\//, '')}/ws/${this.sessionId}`;

        try {
          this.ws = new WebSocket(wsUrl);

          // Set connection timeout
          this.connectionTimeout = window.setTimeout(() => {
            if (this.ws && this.ws.readyState !== WebSocket.OPEN) {
              this.ws.close();
              this.isConnecting = false;
              reject(new Error('WebSocket connection timeout'));
            }
          }, 10000);

          this.ws.onopen = () => {
            this.isConnecting = false;
            this.reconnectAttempts = 0;
            if (this.connectionTimeout) {
              clearTimeout(this.connectionTimeout);
              this.connectionTimeout = null;
            }
            console.log('WebSocket connected to:', wsUrl);
            resolve(true);
          };

          this.ws.onmessage = (event) => {
            this.handleMessage(event.data);
          };

          this.ws.onclose = (event) => {
            this.isConnecting = false;
            if (this.connectionTimeout) {
              clearTimeout(this.connectionTimeout);
              this.connectionTimeout = null;
            }
            console.debug('WebSocket closed:', event.code);
            
            // Attempt reconnection if not intentionally closed
            if (event.code !== 1000 && this.reconnectAttempts < this.maxReconnectAttempts) {
              this.scheduleReconnect();
            }
          };

          this.ws.onerror = (error) => {
            this.isConnecting = false;
            console.debug('WebSocket connection failed (this is normal if AI server is not running)');
            if (this.connectionTimeout) {
              clearTimeout(this.connectionTimeout);
              this.connectionTimeout = null;
            }
            reject(error);
          };

        } catch (error) {
          this.isConnecting = false;
          reject(error);
        }
      });
    }

    private scheduleReconnect() {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
      
      console.debug(`Scheduling WebSocket reconnect attempt ${this.reconnectAttempts} in ${delay}ms`);
      
      setTimeout(() => {
        if (this.reconnectAttempts <= this.maxReconnectAttempts) {
          this.connect().catch(() => {
            // Silently fail reconnection attempts
            console.debug(`WebSocket reconnection attempt ${this.reconnectAttempts} failed`);
          });
        }
      }, delay);
    }

    disconnect() {
      if (this.ws) {
        this.ws.close(1000, 'Client disconnect');
        this.ws = null;
      }
      this.taskCallbacks.clear();
      this.jobCallbacks.clear();
    }

    isConnected(): boolean {
      return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
    }

    // =============================================================================
    // MESSAGE HANDLING
    // =============================================================================

    private handleMessage(data: string) {
      try {
        const message: WebSocketMessage = JSON.parse(data);
        
        switch (message.type) {
          case 'task_status':
            const taskUpdate = message as TaskUpdate;
            const taskCallback = this.taskCallbacks.get(taskUpdate.task_id);
            if (taskCallback) {
              taskCallback(taskUpdate);
            }
            break;

          case 'job_progress':
            const jobUpdate = message as JobUpdate;
            const jobCallback = this.jobCallbacks.get(jobUpdate.job_id);
            if (jobCallback) {
              jobCallback(jobUpdate);
            }
            break;

          case 'connection_established':
            console.log('WebSocket connection established:', message);
            break;

          case 'subscription_confirmed':
            console.log('WebSocket subscription confirmed:', message);
            break;

          case 'error':
            console.error('WebSocket error message:', message);
            break;

          default:
            console.log('Unknown WebSocket message type:', message.type);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error, data);
      }
    }

    private sendMessage(message: object): boolean {
      if (!this.isConnected()) {
        console.warn('WebSocket not connected, cannot send message:', message);
        return false;
      }

      try {
        this.ws!.send(JSON.stringify(message));
        return true;
      } catch (error) {
        console.error('Error sending WebSocket message:', error);
        return false;
      }
    }

    // =============================================================================
    // SUBSCRIPTION MANAGEMENT
    // =============================================================================

    subscribeToTask(taskId: string, callback: (update: TaskUpdate) => void): boolean {
      console.log('WebSocket: Adding task callback for:', taskId);
      this.taskCallbacks.set(taskId, callback);
      
      const subscribeMessage = {
        type: 'subscribe_task',
        task_id: taskId
      };
      console.log('WebSocket: Sending subscription message:', subscribeMessage);
      
      return this.sendMessage(subscribeMessage);
    }

    unsubscribeFromTask(taskId: string): boolean {
      this.taskCallbacks.delete(taskId);
      
      return this.sendMessage({
        type: 'unsubscribe_task',
        task_id: taskId
      });
    }

    subscribeToJob(jobId: string, callback: (update: JobUpdate) => void): boolean {
      this.jobCallbacks.set(jobId, callback);
      
      return this.sendMessage({
        type: 'subscribe_job',
        job_id: jobId
      });
    }

    unsubscribeFromJob(jobId: string): boolean {
      this.jobCallbacks.delete(jobId);
      
      return this.sendMessage({
        type: 'unsubscribe_job',
        job_id: jobId
      });
    }

    // =============================================================================
    // TASK CANCELLATION
    // =============================================================================

    async cancelTask(taskId: string): Promise<{success: boolean, message: string}> {
      try {
        const serverHost = this.serverUrl.replace(/^ws:\/\/|^wss:\/\//, '').replace(/\/.*$/, '');
        const cancelUrl = `http://${serverHost}/api/queue/cancel/${taskId}`;
        
        console.log(`Attempting to cancel task: ${taskId}`);
        
        const response = await fetch(cancelUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          }
        });

        if (!response.ok) {
          throw new Error(`Failed to cancel task: ${response.status} ${response.statusText}`);
        }

        const result = await response.json();
        console.log(`Task cancellation response:`, result);
        
        // Unsubscribe from task updates since it's cancelled
        this.unsubscribeFromTask(taskId);
        
        return {
          success: true,
          message: result.message || `Task ${taskId} cancelled successfully`
        };

      } catch (error: any) {
        console.error(`Failed to cancel task ${taskId}:`, error);
        return {
          success: false,
          message: `Failed to cancel task: ${error.message}`
        };
      }
    }

    async cancelJob(jobId: string): Promise<{success: boolean, message: string, cancelledTasks: string[]}> {
      try {
        // First, get job details to find all its tasks
        const serverHost = this.serverUrl.replace(/^ws:\/\/|^wss:\/\//, '').replace(/\/.*$/, '');
        const jobUrl = `http://${serverHost}/api/queue/job/${jobId}`;
        
        console.log(`Getting job details for cancellation: ${jobId}`);
        
        const jobResponse = await fetch(jobUrl);
        if (!jobResponse.ok) {
          throw new Error(`Failed to get job details: ${jobResponse.status} ${jobResponse.statusText}`);
        }

        const jobData = await jobResponse.json();
        const tasks = jobData.tasks || [];
        
        if (tasks.length === 0) {
          return {
            success: false,
            message: 'No tasks found in this job or job already completed',
            cancelledTasks: []
          };
        }

        // Cancel all tasks in the job
        const cancelledTasks: string[] = [];
        const failedCancellations: string[] = [];

        for (const task of tasks) {
          // Only cancel tasks that are still pending or running
          if (task.status === 'pending' || task.status === 'running') {
            const cancelResult = await this.cancelTask(task.task_id);
            if (cancelResult.success) {
              cancelledTasks.push(task.task_id);
            } else {
              failedCancellations.push(task.task_id);
            }
          }
        }

        // Unsubscribe from job updates
        this.unsubscribeFromJob(jobId);

        if (cancelledTasks.length === 0 && failedCancellations.length === 0) {
          return {
            success: false,
            message: 'All tasks in this job have already completed',
            cancelledTasks: []
          };
        }

        const message = failedCancellations.length > 0 
          ? `Cancelled ${cancelledTasks.length} tasks. Failed to cancel ${failedCancellations.length} tasks.`
          : `Successfully cancelled all ${cancelledTasks.length} tasks in job`;

        return {
          success: cancelledTasks.length > 0,
          message,
          cancelledTasks
        };

      } catch (error: any) {
        console.error(`Failed to cancel job ${jobId}:`, error);
        return {
          success: false,
          message: `Failed to cancel job: ${error.message}`,
          cancelledTasks: []
        };
      }
    }

    // =============================================================================
    // UTILITY METHODS
    // =============================================================================

    getStatus(): string {
      if (!this.ws) return 'disconnected';
      
      switch (this.ws.readyState) {
        case WebSocket.CONNECTING: return 'connecting';
        case WebSocket.OPEN: return 'connected';
        case WebSocket.CLOSING: return 'closing';
        case WebSocket.CLOSED: return 'closed';
        default: return 'unknown';
      }
    }

    getConnectionInfo() {
      return {
        status: this.getStatus(),
        url: this.serverUrl,
        sessionId: this.sessionId,
        reconnectAttempts: this.reconnectAttempts,
        activeTaskSubscriptions: this.taskCallbacks.size,
        activeJobSubscriptions: this.jobCallbacks.size
      };
    }
  }

  // Export for use in other components
  (window as any).AIOverhaulWebSocketManager = WebSocketManager;

  // Add global utility functions for easy cancellation access
  (window as any).AIOverhaulCancellation = {
    cancelTask: async (taskId: string) => {
      const settings = JSON.parse(localStorage.getItem('ai_overhaul_settings') || '{}');
      if (!settings.stashAIServer || !settings.port) {
        return { success: false, message: 'AI Overhaul settings not found' };
      }
      
      const wsManager = new WebSocketManager(`${settings.stashAIServer}:${settings.port}`);
      return await wsManager.cancelTask(taskId);
    },
    
    cancelJob: async (jobId: string) => {
      const settings = JSON.parse(localStorage.getItem('ai_overhaul_settings') || '{}');
      if (!settings.stashAIServer || !settings.port) {
        return { success: false, message: 'AI Overhaul settings not found', cancelledTasks: [] };
      }
      
      const wsManager = new WebSocketManager(`${settings.stashAIServer}:${settings.port}`);
      return await wsManager.cancelJob(jobId);
    }
  };

  console.log('AI Overhaul WebSocket Manager: Successfully loaded with cancellation support');

})();