(function () {
  const PluginApi = (window as any).PluginApi;
  const React = PluginApi.React;

  // =============================================================================
  // TASK TRACKER - WebSocket Integration for Real-time Progress
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

  interface TrackingState {
    taskId: string;
    jobId?: string;
    serviceName: string;
    startTime: number;
    status: string;
    message?: string;
    progress?: number;
    totalTasks?: number;
    completedTasks?: number;
    failedTasks?: number;
    processingTimeMs?: number;
    outputJson?: any;
  }

  class TaskTracker {
    private wsManager: any = null;
    private activeTracking = new Map<string, TrackingState>();
    private listeners = new Map<string, (state: TrackingState) => void>();

    async initialize(): Promise<boolean> {
      try {
        const settings = JSON.parse(localStorage.getItem('ai_overhaul_settings') || '{}');
        if (!settings.stashAIServer || !settings.port) {
          console.warn('TaskTracker: Settings not available for WebSocket connection');
          return false;
        }

        const WebSocketManager = (window as any).AIOverhaulWebSocketManager;
        if (!WebSocketManager) {
          console.warn('TaskTracker: WebSocket manager not available');
          return false;
        }

        this.wsManager = new WebSocketManager(`${settings.stashAIServer}:${settings.port}`);
        
        try {
          await this.wsManager.connect();
          console.log('TaskTracker: WebSocket connected for real-time tracking');
          return true;
        } catch (error) {
          console.debug('TaskTracker: WebSocket connection failed (normal if server not running)');
          return false;
        }
      } catch (error) {
        console.error('TaskTracker: Failed to initialize WebSocket:', error);
        return false;
      }
    }

    startTracking(
      taskId: string, 
      serviceName: string, 
      jobId?: string,
      initialMessage?: string
    ): void {
      const trackingState: TrackingState = {
        taskId,
        jobId,
        serviceName,
        startTime: Date.now(),
        status: 'pending',
        message: initialMessage || 'Task queued for processing...'
      };

      this.activeTracking.set(taskId, trackingState);
      
      // Set up WebSocket subscriptions
      if (this.wsManager && this.wsManager.isConnected()) {
        if (jobId) {
          console.log(`TaskTracker: Subscribing to job updates for ${jobId}`);
          this.wsManager.subscribeToJob(jobId, (update: JobUpdate) => {
            this.handleJobUpdate(taskId, update);
          });
        } else {
          console.log(`TaskTracker: Subscribing to task updates for ${taskId}`);
          this.wsManager.subscribeToTask(taskId, (update: TaskUpdate) => {
            this.handleTaskUpdate(taskId, update);
          });
        }
      }

      // Notify listeners
      this.notifyListeners(taskId, trackingState);
    }

    private handleTaskUpdate(trackingId: string, update: TaskUpdate): void {
      const state = this.activeTracking.get(trackingId);
      if (!state) return;

      console.log(`TaskTracker: Task update for ${trackingId}:`, update);

      const updatedState: TrackingState = {
        ...state,
        status: update.status,
        processingTimeMs: update.processing_time_ms,
        outputJson: update.output_json,
        message: this.getStatusMessage(update.status, update.adapter_name, update.processing_time_ms)
      };

      this.activeTracking.set(trackingId, updatedState);
      this.notifyListeners(trackingId, updatedState);

      // Save completed tasks to recent tasks manager and clean up
      if (['finished', 'failed', 'cancelled'].includes(update.status)) {
        // Save to recent tasks for later viewing
        const recentTasks = (window as any).AIRecentTasks;
        if (recentTasks && state) {
          recentTasks.addCompleted(
            state.taskId,
            state.serviceName,
            update.status as 'finished' | 'failed' | 'cancelled',
            state.startTime,
            state.jobId,
            {
              message: updatedState.message,
              processingTimeMs: update.processing_time_ms,
              totalTasks: state.totalTasks,
              completedTasks: state.completedTasks,
              failedTasks: state.failedTasks
            }
          );
        }
        
        setTimeout(() => {
          this.stopTracking(trackingId);
        }, 5000); // Keep completed task visible for 5 seconds
      }
    }

    private handleJobUpdate(trackingId: string, update: JobUpdate): void {
      const state = this.activeTracking.get(trackingId);
      if (!state) return;

      console.log(`TaskTracker: Job update for ${trackingId}:`, update);

      const updatedState: TrackingState = {
        ...state,
        status: update.status,
        totalTasks: update.total_tasks,
        completedTasks: update.completed_tasks,
        failedTasks: update.failed_tasks,
        progress: update.progress_percentage,
        message: this.getJobStatusMessage(update)
      };

      this.activeTracking.set(trackingId, updatedState);
      this.notifyListeners(trackingId, updatedState);

      // Save completed jobs to recent tasks manager and clean up
      if (['completed', 'finished', 'failed'].includes(update.status)) {
        // Save to recent tasks for later viewing
        const recentTasks = (window as any).AIRecentTasks;
        if (recentTasks && state) {
          const jobStatus = update.status === 'completed' ? 'finished' : update.status as 'finished' | 'failed';
          recentTasks.addCompleted(
            state.taskId,
            state.serviceName,
            jobStatus,
            state.startTime,
            state.jobId,
            {
              message: updatedState.message,
              totalTasks: update.total_tasks,
              completedTasks: update.completed_tasks,
              failedTasks: update.failed_tasks,
              progress: update.progress_percentage
            }
          );
        }
        
        setTimeout(() => {
          this.stopTracking(trackingId);
        }, 8000); // Keep completed job visible for 8 seconds
      }
    }

    private getStatusMessage(status: string, adapterName?: string, processingTime?: number): string {
      switch (status) {
        case 'pending':
          return 'Queued for processing...';
        case 'running':
          return `Processing with ${adapterName || 'AI service'}...`;
        case 'finished':
          const timeStr = processingTime ? ` (${Math.round(processingTime / 1000)}s)` : '';
          return `Completed successfully${timeStr}`;
        case 'failed':
          return 'Processing failed';
        case 'cancelled':
          return 'Task cancelled';
        default:
          return `Status: ${status}`;
      }
    }

    private getJobStatusMessage(update: JobUpdate): string {
      const { status, completed_tasks, total_tasks, failed_tasks, progress_percentage } = update;
      
      switch (status) {
        case 'pending':
          return `Batch job queued (${total_tasks} tasks)`;
        case 'running':
          const failedText = failed_tasks > 0 ? `, ${failed_tasks} failed` : '';
          return `Processing: ${completed_tasks}/${total_tasks} complete${failedText}`;
        case 'completed':
        case 'finished':
          const summary = failed_tasks > 0 
            ? `${completed_tasks} completed, ${failed_tasks} failed`
            : `All ${completed_tasks} tasks completed successfully`;
          return `Batch finished: ${summary}`;
        case 'partial':
          return `Partially completed: ${completed_tasks}/${total_tasks} (${failed_tasks} failed)`;
        case 'failed':
          return `Batch failed: ${failed_tasks}/${total_tasks} tasks failed`;
        default:
          return `Batch status: ${status} (${progress_percentage}%)`;
      }
    }

    addListener(taskId: string, callback: (state: TrackingState) => void): void {
      this.listeners.set(taskId, callback);
      
      // If task is already being tracked, immediately notify
      const existingState = this.activeTracking.get(taskId);
      if (existingState) {
        callback(existingState);
      }
    }

    removeListener(taskId: string): void {
      this.listeners.delete(taskId);
    }

    private notifyListeners(taskId: string, state: TrackingState): void {
      const callback = this.listeners.get(taskId);
      if (callback) {
        callback(state);
      }
    }

    stopTracking(taskId: string): void {
      const state = this.activeTracking.get(taskId);
      if (!state) return;

      console.log(`TaskTracker: Stopping tracking for ${taskId}`);

      // Unsubscribe from WebSocket updates
      if (this.wsManager && this.wsManager.isConnected()) {
        if (state.jobId) {
          this.wsManager.unsubscribeFromJob(state.jobId);
        } else {
          this.wsManager.unsubscribeFromTask(taskId);
        }
      }

      // Clean up tracking state and listeners
      this.activeTracking.delete(taskId);
      this.listeners.delete(taskId);
    }

    getActiveTask(taskId: string): TrackingState | null {
      return this.activeTracking.get(taskId) || null;
    }

    getAllActiveTasks(): TrackingState[] {
      return Array.from(this.activeTracking.values());
    }

    disconnect(): void {
      if (this.wsManager) {
        this.wsManager.disconnect();
      }
      this.activeTracking.clear();
      this.listeners.clear();
    }
  }

  // Create global task tracker instance
  const globalTaskTracker = new TaskTracker();

  // Auto-initialize on settings availability
  const initializeTracker = async () => {
    try {
      const settings = localStorage.getItem('ai_overhaul_settings');
      if (settings) {
        await globalTaskTracker.initialize();
      }
    } catch (error) {
      console.debug('TaskTracker: Auto-initialization skipped');
    }
  };

  // Try to initialize immediately and on storage changes
  initializeTracker();
  window.addEventListener('storage', (e) => {
    if (e.key === 'ai_overhaul_settings') {
      initializeTracker();
    }
  });

  // Export for use in other components
  (window as any).AITaskTracker = globalTaskTracker;

  // Export utility functions
  (window as any).AITaskTracking = {
    startTask: (taskId: string, serviceName: string, jobId?: string, message?: string) => {
      return globalTaskTracker.startTracking(taskId, serviceName, jobId, message);
    },
    
    stopTask: (taskId: string) => {
      return globalTaskTracker.stopTracking(taskId);
    },
    
    getActiveTask: (taskId: string) => {
      return globalTaskTracker.getActiveTask(taskId);
    },
    
    onTaskUpdate: (taskId: string, callback: (state: any) => void) => {
      return globalTaskTracker.addListener(taskId, callback);
    },
    
    offTaskUpdate: (taskId: string) => {
      return globalTaskTracker.removeListener(taskId);
    }
  };

  console.log('AI Task Tracker: Successfully loaded with WebSocket integration');

})();