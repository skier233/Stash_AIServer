(function () {
  // =============================================================================
  // RECENT TASKS MANAGER - Persistent Storage for Task Results
  // =============================================================================

  interface CompletedTask {
    taskId: string;
    jobId?: string;
    serviceName: string;
    status: 'finished' | 'failed' | 'cancelled';
    startTime: number;
    endTime: number;
    message?: string;
    isMultiImage: boolean;
    totalTasks?: number;
    completedTasks?: number;
    failedTasks?: number;
    processingTimeMs?: number;
  }

  class RecentTasksManager {
    private storageKey = 'ai_overhaul_recent_tasks';
    private maxTasks = 20; // Keep last 20 completed tasks
    private tasks: CompletedTask[] = [];

    constructor() {
      this.loadFromStorage();
    }

    private loadFromStorage(): void {
      try {
        const stored = localStorage.getItem(this.storageKey);
        if (stored) {
          const parsedTasks = JSON.parse(stored);
          this.tasks = Array.isArray(parsedTasks) ? parsedTasks : [];
          console.log('RecentTasksManager: Loaded', this.tasks.length, 'recent tasks from storage');
        } else {
          this.tasks = [];
          console.log('RecentTasksManager: No stored tasks found, starting fresh');
        }
      } catch (error) {
        console.error('RecentTasksManager: Failed to load from storage:', error);
        this.tasks = [];
      }
    }

    private saveToStorage(): void {
      try {
        localStorage.setItem(this.storageKey, JSON.stringify(this.tasks));
      } catch (error) {
        console.error('RecentTasksManager: Failed to save to storage:', error);
      }
    }

    addCompletedTask(
      taskId: string,
      serviceName: string,
      status: 'finished' | 'failed' | 'cancelled',
      startTime: number,
      jobId?: string,
      additionalData?: Partial<CompletedTask>
    ): void {
      const completedTask: CompletedTask = {
        taskId,
        jobId,
        serviceName,
        status,
        startTime,
        endTime: Date.now(),
        isMultiImage: !!jobId, // Jobs are typically multi-image operations
        ...additionalData
      };

      // Remove existing task if it exists (prevent duplicates)
      this.tasks = this.tasks.filter(task => task.taskId !== taskId);
      
      // Add to beginning of array
      this.tasks.unshift(completedTask);
      
      // Trim to max tasks
      if (this.tasks.length > this.maxTasks) {
        this.tasks = this.tasks.slice(0, this.maxTasks);
      }

      this.saveToStorage();
      console.log(`RecentTasksManager: Added completed task ${taskId} (${serviceName})`);
    }

    getRecentTasks(limit?: number): CompletedTask[] {
      const tasks = limit ? this.tasks.slice(0, limit) : this.tasks;
      return tasks.map(task => ({ ...task })); // Return copies
    }

    getTaskById(taskId: string): CompletedTask | null {
      const task = this.tasks.find(t => t.taskId === taskId);
      return task ? { ...task } : null;
    }

    removeTask(taskId: string): boolean {
      const initialLength = this.tasks.length;
      this.tasks = this.tasks.filter(task => task.taskId !== taskId);
      
      if (this.tasks.length < initialLength) {
        this.saveToStorage();
        console.log(`RecentTasksManager: Removed task ${taskId}`);
        return true;
      }
      
      return false;
    }

    clearAll(): void {
      this.tasks = [];
      this.saveToStorage();
      console.log('RecentTasksManager: Cleared all recent tasks');
    }

    // Get tasks by status
    getTasksByStatus(status: 'finished' | 'failed' | 'cancelled'): CompletedTask[] {
      return this.tasks.filter(task => task.status === status);
    }

    // Get tasks by service
    getTasksByService(serviceName: string): CompletedTask[] {
      return this.tasks.filter(task => task.serviceName === serviceName);
    }

    // Get recent successful tasks (finished status)
    getRecentSuccessfulTasks(limit: number = 10): CompletedTask[] {
      return this.tasks
        .filter(task => task.status === 'finished')
        .slice(0, limit);
    }

    // Get statistics
    getStats(): {
      total: number;
      finished: number;
      failed: number;
      cancelled: number;
      byService: Record<string, number>;
    } {
      const stats = {
        total: this.tasks.length,
        finished: 0,
        failed: 0,
        cancelled: 0,
        byService: {} as Record<string, number>
      };

      this.tasks.forEach(task => {
        stats[task.status]++;
        
        if (!stats.byService[task.serviceName]) {
          stats.byService[task.serviceName] = 0;
        }
        stats.byService[task.serviceName]++;
      });

      return stats;
    }
  }

  // Create global instance
  const globalRecentTasksManager = new RecentTasksManager();

  // Export for use in other components
  (window as any).AIRecentTasksManager = globalRecentTasksManager;

  // Export utility functions
  (window as any).AIRecentTasks = {
    addCompleted: (
      taskId: string,
      serviceName: string,
      status: 'finished' | 'failed' | 'cancelled',
      startTime: number,
      jobId?: string,
      additionalData?: any
    ) => {
      return globalRecentTasksManager.addCompletedTask(taskId, serviceName, status, startTime, jobId, additionalData);
    },

    getRecent: (limit?: number) => {
      return globalRecentTasksManager.getRecentTasks(limit);
    },

    getById: (taskId: string) => {
      return globalRecentTasksManager.getTaskById(taskId);
    },

    getSuccessful: (limit?: number) => {
      return globalRecentTasksManager.getRecentSuccessfulTasks(limit);
    },

    remove: (taskId: string) => {
      return globalRecentTasksManager.removeTask(taskId);
    },

    clear: () => {
      return globalRecentTasksManager.clearAll();
    },

    getStats: () => {
      return globalRecentTasksManager.getStats();
    }
  };

  console.log('AI Recent Tasks Manager: Successfully loaded');

})();