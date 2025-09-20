(function () {
  const PluginApi = (window as any).PluginApi;
  const React = PluginApi.React;

  // =============================================================================
  // AI OVERHAUL BUTTON COMPONENT
  // =============================================================================

  // =============================================================================
  // STASH GRAPHQL HANDLER
  // =============================================================================
  const findImage = async (id: string) => {
    const query = `
      query FindImage($id: ID!) {
        findImage(id: $id) {
          id
          title
          urls
          galleries {
            id
            title
          }
          paths {
            image
            preview
            thumbnail
            __typename
          }
        }
      }
    `;

    try {
      const response = await fetch('/graphql', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, variables: { id } })
      });

      if (!response.ok) {
        throw new Error(`GraphQL request failed: ${response.status}`);
      }

      const result = await response.json();
      if (result.errors) {
        throw new Error(`GraphQL errors: ${result.errors.map((e: any) => e.message).join(', ')}`);
      }

      return result.data?.findImage || null;
    } catch (error) {
      console.error('Failed to fetch image data:', error);
      throw error;
    }
  };

  const imageToBase64 = async (imageUrl: string): Promise<string> => {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.crossOrigin = 'anonymous';
      
      img.onload = () => {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        if (!ctx) {
          reject(new Error('Failed to get canvas context'));
          return;
        }
        
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0);
        
        try {
          const dataURL = canvas.toDataURL('image/jpeg', 0.9);
          const base64 = dataURL.replace(/^data:image\/[a-z]+;base64,/, '');
          resolve(base64);
        } catch (error) {
          reject(new Error(`Failed to convert image to base64: ${error}`));
        }
      };
      
      img.onerror = () => {
        reject(new Error(`Failed to load image from URL: ${imageUrl}`));
      };
      
      img.src = imageUrl;
    });
  };

  // =============================================================================
  // VISAGE RESULTS OVERLAY - Use global VisageImageResults component
  // =============================================================================



  // =============================================================================
  // PAGE CONTEXT DETECTION
  // =============================================================================
  interface PageContext {
    page: 'scenes' | 'galleries' | 'images' | 'groups' | 'performers' | 'home' | 'unknown';
    entityId: string | null;
    isDetailView: boolean;
  }

  const detectPageContext = (): PageContext => {
    const path = window.location.pathname;
    
    let page: PageContext['page'] = 'unknown';
    let entityId: string | null = null;
    let isDetailView = false;

    if (path.includes('/scenes')) {
      page = 'scenes';
      const sceneMatch = path.match(/\/scenes\/(\d+)/);
      if (sceneMatch) {
        entityId = sceneMatch[1];
        isDetailView = true;
      }
    } else if (path.includes('/galleries')) {
      page = 'galleries';
      const galleryMatch = path.match(/\/galleries\/(\d+)/);
      if (galleryMatch) {
        entityId = galleryMatch[1];
        isDetailView = true;
      }
    } else if (path.includes('/images')) {
      page = 'images';
      const imageMatch = path.match(/\/images\/(\d+)/);
      if (imageMatch) {
        entityId = imageMatch[1];
        isDetailView = true;
      }
    } else if (path.includes('/groups')) {
      page = 'groups';
      const groupMatch = path.match(/\/groups\/(\d+)/);
      if (groupMatch) {
        entityId = groupMatch[1];
        isDetailView = true;
      }
    } else if (path.includes('/performers')) {
      page = 'performers';
      const performerMatch = path.match(/\/performers\/(\d+)/);
      if (performerMatch) {
        entityId = performerMatch[1];
        isDetailView = true;
      }
    } else if (path === '/' || path === '/home') {
      page = 'home';
    }

    return { page, entityId, isDetailView };
  };

  const usePageContext = () => {
    const [context, setContext] = React.useState(detectPageContext());

    React.useEffect(() => {
      const updateContext = () => {
        const newContext = detectPageContext();
        setContext((prevContext: PageContext) => {
          if (
            prevContext.page !== newContext.page ||
            prevContext.entityId !== newContext.entityId ||
            prevContext.isDetailView !== newContext.isDetailView
          ) {
            return newContext;
          }
          return prevContext;
        });
      };

      updateContext();

      const handleLocationChange = () => {
        setTimeout(updateContext, 100);
      };

      window.addEventListener('popstate', handleLocationChange);
      
      // Listen for programmatic navigation
      const observer = new MutationObserver(handleLocationChange);
      observer.observe(document.body, { childList: true, subtree: true });

      return () => {
        window.removeEventListener('popstate', handleLocationChange);
        observer.disconnect();
      };
    }, []);

    return context;
  };

  const AIOverhaulButton: React.FC = () => {
    // =============================================================================
    // STATE MANAGEMENT
    // =============================================================================
    const [isProcessing, setIsProcessing] = React.useState(false);
    const [showDropdown, setShowDropdown] = React.useState(false);
    const [availableServices, setAvailableServices] = React.useState([]);
    const [settings, setSettings] = React.useState(null);
    const [showOverlay, setShowOverlay] = React.useState(false);
    const [overlayData, setOverlayData] = React.useState(null);
    const [showGalleryResultsOverlay, setShowGalleryResultsOverlay] = React.useState(false);
    const [galleryResultsData, setGalleryResultsData] = React.useState(null);
    const [activeTask, setActiveTask] = React.useState(() => {
      // Restore active task from localStorage on component mount
      try {
        const savedTask = localStorage.getItem('aiOverhaul_activeTask');
        return savedTask ? JSON.parse(savedTask) : null;
      } catch (error) {
        console.warn('Failed to restore active task from localStorage:', error);
        return null;
      }
    });
    const [wsManager, setWsManager] = React.useState(null);
    const [queueWebSocket, setQueueWebSocket] = React.useState(null);
    const [showNotificationDropdown, setShowNotificationDropdown] = React.useState(false);
    const [queueStats, setQueueStats] = React.useState(null);
    const [queueTasks, setQueueTasks] = React.useState([]);
    const [localQueue, setLocalQueue] = React.useState(new Map());
    const [serverJobs, setServerJobs] = React.useState([]);
    const [recentCompletedJobs, setRecentCompletedJobs] = React.useState([]);
    const [taskProgress, setTaskProgress] = React.useState(new Map());
    const [batchJobProgress, setBatchJobProgress] = React.useState(() => {
      // Restore batch job progress from localStorage on component mount
      try {
        const saved = localStorage.getItem('aiOverhaul_batchJobProgress');
        if (saved) {
          const parsedData = JSON.parse(saved);
          // Convert array back to Map and filter out expired jobs
          const now = Date.now();
          const fiveMinutes = 5 * 60 * 1000;
          const filteredJobs = parsedData.filter((job: any) => {
            // Keep active jobs or recently completed jobs
            return (
              (job.status !== 'completed' && job.status !== 'failed') ||
              (now - (job.lastUpdate || 0) < fiveMinutes)
            );
          });
          return new Map(filteredJobs.map((job: any) => [job.jobId, job]));
        }
      } catch (error) {
        console.warn('Failed to restore batch job progress from localStorage:', error);
      }
      return new Map();
    });
    const [hasNotifications, setHasNotifications] = React.useState(false);
    const [isDiscoveringServices, setIsDiscoveringServices] = React.useState(false);
    
    // Get current page context
    const context = usePageContext();

    // =============================================================================
    // MODULAR PROGRESS TRACKING SYSTEM
    // =============================================================================

    interface BatchJobProgress {
      jobId: string;
      service: string;
      status: string;
      progress?: number;
      current?: number;
      total?: number;
      message?: string;
      type: 'gallery_batch' | 'multi_select_batch' | 'custom_batch';
      details?: any;
      lastUpdate: number;
    }

    const updateBatchJobProgress = React.useCallback((jobId: string, progressData: {
      service: string;
      status: string;
      progress?: number;
      current?: number;
      total?: number;
      message?: string;
      type: 'gallery_batch' | 'multi_select_batch' | 'custom_batch';
      details?: any;
    }) => {
      setBatchJobProgress(prev => {
        const newProgress = new Map(prev);
        const existing = newProgress.get(jobId) || {};
        
        newProgress.set(jobId, Object.assign({}, existing, progressData, {
          lastUpdate: Date.now(),
          jobId
        }));
        
        return newProgress;
      });

      // Update notifications
      setHasNotifications(true);
    }, []);

    const getBatchJobStatus = React.useCallback((jobId: string) => {
      return batchJobProgress.get(jobId) || null;
    }, [batchJobProgress]);

    const clearBatchJobProgress = React.useCallback((jobId: string) => {
      setBatchJobProgress(prev => {
        const newProgress = new Map(prev);
        newProgress.delete(jobId);
        return newProgress;
      });
    }, []);

    // Cleanup completed batch jobs after 5 minutes
    React.useEffect(() => {
      const cleanupInterval = setInterval(() => {
        const now = Date.now();
        const fiveMinutes = 5 * 60 * 1000;
        
        setBatchJobProgress(prev => {
          const newProgress = new Map(prev);
          let hasChanges = false;
          
          for (const [jobId, job] of newProgress.entries()) {
            const jobData = job as BatchJobProgress;
            if (
              (jobData.status === 'completed' || jobData.status === 'failed') &&
              now - (jobData.lastUpdate || 0) > fiveMinutes
            ) {
              newProgress.delete(jobId);
              hasChanges = true;
            }
          }
          
          return hasChanges ? newProgress : prev;
        });
      }, 60000); // Check every minute

      return () => clearInterval(cleanupInterval);
    }, []);
    
    // Persist active task to localStorage whenever it changes
    React.useEffect(() => {
      try {
        if (activeTask) {
          localStorage.setItem('aiOverhaul_activeTask', JSON.stringify(activeTask));
        } else {
          localStorage.removeItem('aiOverhaul_activeTask');
        }
      } catch (error) {
        console.warn('Failed to persist active task to localStorage:', error);
      }
    }, [activeTask]);

    // Persist batch job progress to localStorage whenever it changes
    React.useEffect(() => {
      try {
        if (batchJobProgress.size > 0) {
          // Convert Map to array for JSON serialization
          const progressArray = Array.from(batchJobProgress.values());
          localStorage.setItem('aiOverhaul_batchJobProgress', JSON.stringify(progressArray));
        } else {
          localStorage.removeItem('aiOverhaul_batchJobProgress');
        }
      } catch (error) {
        console.warn('Failed to save batch job progress to localStorage:', error);
      }
    }, [batchJobProgress]);

    // =============================================================================
    // PERSISTENT QUEUE MANAGER WEBSOCKET
    // =============================================================================

    const setupPersistentQueueWebSocket = React.useCallback((settings: any) => {
      console.log('Setting up persistent WebSocket connection to queue manager...');
      
      const WebSocketManager = (window as any).AIOverhaulWebSocketManager;
      if (!WebSocketManager) {
        console.warn('WebSocket manager not available');
        return null;
      }

      // Create a dedicated queue manager WebSocket connection
      const queueManager = new WebSocketManager(`${settings.stashAIServer}:${settings.port}`, 'queue_monitor');
      
      // Connect and set up queue-wide event handlers
      queueManager.connect().then(() => {
        console.log('✅ Queue manager WebSocket connected');
        
        // Subscribe to queue statistics (this will give us job updates too)
        queueManager.sendMessage({
          type: 'subscribe_queue_stats'
        });

        // Handle all queue events in one place
        queueManager.ws.addEventListener('message', (event: MessageEvent) => {
          try {
            const message = JSON.parse(event.data);
            handleQueueManagerMessage(message, settings);
          } catch (error) {
            console.error('Error parsing queue manager message:', error);
          }
        });

      }).catch((error: any) => {
        console.warn('Failed to connect to queue manager WebSocket:', error);
        // Fall back to individual job subscriptions
        setupIndividualJobSubscriptions(settings);
      });

      return queueManager;
    }, []);

    const handleQueueManagerMessage = React.useCallback((message: any, settings: any) => {
      console.log('Queue manager message:', message);

      switch (message.type) {
        case 'job_progress':
          // Update progress for any job we're tracking
          if (batchJobProgress.has(message.job_id)) {
            const currentJob = batchJobProgress.get(message.job_id) as BatchJobProgress;
            const progressPercent = message.progress_percentage || 0;
            const baseProgress = 60; // Job submission was at 60%
            const remainingProgress = 40; // 40% left for job execution
            const currentProgress = baseProgress + (remainingProgress * (progressPercent / 100));
            
            updateBatchJobProgress(message.job_id, {
              service: currentJob.service,
              status: 'running',
              progress: currentProgress,
              current: message.completed_tasks,
              total: message.total_tasks,
              message: `${currentJob.service} processing: ${progressPercent.toFixed(1)}% (${message.completed_tasks || 0}/${message.total_tasks || 0})`,
              type: currentJob.type,
              details: message
            });
          }
          break;

        case 'job_completed':
        case 'job_finished':
          // Handle job completion
          if (batchJobProgress.has(message.job_id)) {
            const currentJob = batchJobProgress.get(message.job_id) as BatchJobProgress;
            updateBatchJobProgress(message.job_id, {
              service: currentJob.service,
              status: 'completed',
              progress: 100,
              current: message.completed_tasks || message.total_tasks,
              total: message.total_tasks,
              message: `${currentJob.service} batch completed: ${message.completed_tasks || message.total_tasks}/${message.total_tasks} tasks finished`,
              type: currentJob.type,
              details: message
            });

            // Trigger completion actions (could show results overlay here)
            handleBatchJobCompletion(message.job_id, currentJob, message);
          }
          break;

        case 'job_failed':
          // Handle job failure
          if (batchJobProgress.has(message.job_id)) {
            const currentJob = batchJobProgress.get(message.job_id) as BatchJobProgress;
            updateBatchJobProgress(message.job_id, {
              service: currentJob.service,
              status: 'failed',
              message: `${currentJob.service} batch job failed: ${message.error || 'Unknown error'}`,
              type: currentJob.type,
              details: message
            });
          }
          break;

        case 'queue_stats':
          // Update global queue statistics
          setQueueStats(message.stats);
          console.log('Queue stats updated:', message.stats);
          break;

        case 'worker_status':
          // Handle worker status changes
          console.log('Worker status update:', message);
          break;

        default:
          console.log('Unknown queue manager message type:', message.type);
      }
    }, [batchJobProgress, updateBatchJobProgress]);

    const handleBatchJobCompletion = React.useCallback((jobId: string, job: BatchJobProgress, completionData: any) => {
      console.log(`🎉 Batch job completed: ${jobId} (${job.service})`);
      
      // Add gallery batch jobs to recent completed jobs for viewing
      if (job.type === 'gallery_batch') {
        const galleryTitle = job.details?.gallery_title || 
          completionData.metadata?.gallery_title || 
          `Gallery Batch Analysis`;
        
        setRecentCompletedJobs(prev => [{
          job_id: jobId,
          type: job.service,
          job_type: 'gallery_analysis',
          title: `${job.service} - ${galleryTitle}`,
          completed_at: new Date().toISOString(),
          details: {
            type: 'gallery_batch',
            gallery_id: job.details?.gallery_id || completionData.metadata?.gallery_id,
            gallery_title: galleryTitle,
            total_tasks: completionData.total_tasks || job.total,
            completed_tasks: completionData.completed_tasks || job.current
          },
          status: 'completed'
        }, ...prev.slice(0, 4)]); // Keep last 5 jobs
        
        console.log('Added gallery batch job to recent completed jobs:', jobId);
      }

      // Show a notification
      if ((window as any).showToast) {
        (window as any).showToast(`${job.service} batch completed successfully!`, 'success');
      }
    }, []);

    // Legacy fallback - no longer used with persistent WebSocket
    const setupIndividualJobSubscriptions = React.useCallback(async (settings: any) => {
      console.log('Fallback: Starting polling for batch jobs (persistent WebSocket not available)');
      
      const batchJobArray = Array.from(batchJobProgress.values()) as BatchJobProgress[];
      const activeBatchJobs = batchJobArray.filter(job => 
        job.status !== 'completed' && job.status !== 'failed'
      );

      if (activeBatchJobs.length > 0) {
        startBatchJobPolling(settings, activeBatchJobs);
      }
    }, [batchJobProgress]);

    const startBatchJobPolling = React.useCallback((settings: any, jobsToTrack: BatchJobProgress[]) => {
      if (jobsToTrack.length === 0) return;

      console.log('Starting backup polling for batch jobs...');
      
      const pollInterval = setInterval(async () => {
        try {
          for (const job of jobsToTrack) {
            // Skip if job is already completed/failed
            const currentJob = batchJobProgress.get(job.jobId) as BatchJobProgress;
            if (!currentJob || currentJob.status === 'completed' || currentJob.status === 'failed') {
              continue;
            }

            // Poll job status from server
            const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/queue/job/${job.jobId}`);
            if (response.ok) {
              const jobData = await response.json();
              
              // Update progress if status changed
              if (jobData.status !== currentJob.status) {
                console.log(`Polling detected status change for ${job.jobId}: ${jobData.status}`);
                
                if (jobData.status === 'completed' || jobData.status === 'finished') {
                  updateBatchJobProgress(job.jobId, {
                    service: job.service,
                    status: 'completed',
                    progress: 100,
                    message: `${job.service} batch completed (via polling)`,
                    type: job.type,
                    details: jobData
                  });
                } else if (jobData.status === 'failed') {
                  updateBatchJobProgress(job.jobId, {
                    service: job.service,
                    status: 'failed',
                    message: `${job.service} batch failed (via polling)`,
                    type: job.type,
                    details: jobData
                  });
                }
              }
            }
          }

          // Check if all jobs are completed
          const remainingJobs = jobsToTrack.filter(job => {
            const current = batchJobProgress.get(job.jobId) as BatchJobProgress;
            return current && current.status !== 'completed' && current.status !== 'failed';
          });

          if (remainingJobs.length === 0) {
            console.log('All batch jobs completed, stopping polling');
            clearInterval(pollInterval);
          }
        } catch (error) {
          console.warn('Error during batch job polling:', error);
        }
      }, 5000); // Poll every 5 seconds

      // Clean up interval after 30 minutes max
      setTimeout(() => {
        clearInterval(pollInterval);
      }, 30 * 60 * 1000);
      
    }, [batchJobProgress, updateBatchJobProgress]);

    // =============================================================================
    // SETTINGS AND INITIALIZATION
    // =============================================================================
    React.useEffect(() => {
      // Load settings on mount
      const loadSettings = () => {
        const saved = localStorage.getItem('ai_overhaul_settings');
        if (saved) {
          try {
            const parsedSettings = JSON.parse(saved);
            setSettings(parsedSettings);
            
            // Initialize persistent queue WebSocket connection
            if (parsedSettings?.stashAIServer && parsedSettings?.port && !queueWebSocket) {
              const queueWS = setupPersistentQueueWebSocket(parsedSettings);
              if (queueWS) {
                setQueueWebSocket(queueWS);
              }
            }

            // Initialize legacy WebSocket manager for backward compatibility
            if (parsedSettings?.stashAIServer && parsedSettings?.port && !wsManager) {
              const WebSocketManager = (window as any).AIOverhaulWebSocketManager;
              if (WebSocketManager) {
                const manager = new WebSocketManager(`${parsedSettings.stashAIServer}:${parsedSettings.port}`);
                setWsManager(manager);
                
                // Only use legacy manager if persistent queue WebSocket failed
                if (!queueWebSocket) {
                  manager.connect().catch((error: any) => {
                    console.warn('Legacy WebSocket connection failed:', error);
                  });
                }
                
                // Check if restored active task is still running
                if (activeTask?.taskId) {
                  checkTaskStatus(activeTask.taskId, parsedSettings);
                }
              }
            }
          } catch (e) {
            console.warn('Failed to load AI Overhaul settings:', e);
          }
        }
      };

      loadSettings();
      
      // Cleanup WebSocket connections on unmount
      return () => {
        if (queueWebSocket) {
          queueWebSocket.disconnect();
        }
        if (wsManager) {
          wsManager.disconnect();
        }
      };
    }, []);

    // =============================================================================
    // TASK STATUS VERIFICATION
    // =============================================================================
    const checkTaskStatus = async (taskId: string, settingsObj: any) => {
      try {
        console.log('Checking status for restored task:', taskId);
        const response = await fetch(`http://${settingsObj.stashAIServer}:${settingsObj.port}/api/queue/job/${taskId}`);
        
        if (response.ok) {
          const taskData = await response.json();
          console.log('Restored task status:', taskData);
          
          if (taskData.status === 'completed' || taskData.status === 'failed') {
            // Task is no longer active, clear it
            console.log('Restored task is no longer active, clearing');
            setActiveTask(null);
            setIsProcessing(false);
          } else if (taskData.status === 'running' || taskData.status === 'pending') {
            // Task is still active, update the status
            console.log('Restored task is still active, updating status');
            setActiveTask(prev => ({
              ...prev,
              status: taskData.status,
              progress: getProgressMessage(taskData.status)
            }));
            setIsProcessing(true);
          }
        } else if (response.status === 404) {
          // Task not found, clear it
          console.log('Restored task not found on server, clearing');
          setActiveTask(null);
          setIsProcessing(false);
        }
      } catch (error) {
        console.warn('Failed to check restored task status:', error);
        // On error, leave the task as-is but log the issue
      }
    };

    // =============================================================================
    // SERVICE DISCOVERY
    // =============================================================================
    const discoverServices = async () => {
      if (!settings) return;

      const services = [
        { 
          name: 'Visage', 
          port: '9997', 
          description: 'Face Recognition',
          action: 'analyze-faces',
          icon: '👤',
          supportedTypes: ['image', 'scene']
        },
        { 
          name: 'Content Analysis', 
          port: '9999', 
          description: 'Content Classification',
          action: 'analyze-content',
          icon: '🔍',
          supportedTypes: ['image', 'scene']
        },
        { 
          name: 'Scene Analysis', 
          port: '9996', 
          description: 'Scene Detection',
          action: 'analyze-scene',
          icon: '🎬',
          supportedTypes: ['scene']
        },
        { 
          name: 'Gallery Batch Analysis', 
          port: '9998', 
          description: 'Analyze all images in gallery',
          action: 'analyze-gallery-batch',
          icon: '🖼️',
          supportedTypes: ['galleries']
        }
      ];

      const available: Array<{
        name: string;
        port: string;
        description: string;
        action: string;
        icon: string;
        supportedTypes: string[];
      }> = [];
      
      for (const service of services) {
        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => {
            console.debug(`${service.name} service check timeout after 3s`);
            controller.abort();
          }, 3000);
          
          const testUrl = `http://${settings.stashAIServer}:${service.port}/health`;
          const response = await fetch(testUrl, {
            method: 'GET',
            signal: controller.signal,
            headers: { 'Content-Type': 'application/json' }
          });
          
          clearTimeout(timeoutId);
          
          if (response.ok) {
            available.push(service);
            console.debug(`${service.name} service available at ${service.port}`);
          }
        } catch (error: any) {
          // Handle different error types more gracefully
          if (error.name === 'AbortError') {
            console.debug(`${service.name} service check timed out (${service.port})`);
          } else {
            console.debug(`${service.name} service not available (${service.port}):`, error.message);
          }
        }
      }
      
      setAvailableServices(available);
    };

    // Version that returns services directly for immediate use
    const discoverServicesAndReturn = async () => {
      if (!settings) return [];
      
      setIsDiscoveringServices(true);

      const services = [
        { 
          name: 'Visage', 
          port: '9997', 
          description: 'Face Recognition',
          action: 'analyze-faces',
          icon: '👤',
          supportedTypes: ['image', 'scene']
        },
        { 
          name: 'Content Analysis', 
          port: '9999', 
          description: 'Content Classification',
          action: 'analyze-content',
          icon: '🔍',
          supportedTypes: ['image', 'scene']
        },
        { 
          name: 'Scene Analysis', 
          port: '9996', 
          description: 'Scene Detection',
          action: 'analyze-scene',
          icon: '🎬',
          supportedTypes: ['scene']
        },
        { 
          name: 'Gallery Batch Analysis', 
          port: '9998', 
          description: 'Analyze all images in gallery',
          action: 'analyze-gallery-batch',
          icon: '🖼️',
          supportedTypes: ['galleries']
        }
      ];

      const available: Array<{
        name: string;
        port: string;
        description: string;
        action: string;
        icon: string;
        supportedTypes: string[];
      }> = [];
      
      for (const service of services) {
        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => {
            console.debug(`${service.name} service check timeout after 3s`);
            controller.abort();
          }, 3000); // Increased timeout for better reliability
          
          const testUrl = `http://${settings.stashAIServer}:${service.port}/health`;
          const response = await fetch(testUrl, {
            method: 'GET',
            signal: controller.signal,
            headers: { 'Content-Type': 'application/json' }
          });
          
          clearTimeout(timeoutId);
          
          if (response.ok) {
            available.push(service);
            console.debug(`${service.name} service available at ${service.port}`);
          }
        } catch (error: any) {
          // Handle different error types more gracefully
          if (error.name === 'AbortError') {
            console.debug(`${service.name} service check timed out (${service.port})`);
          } else {
            console.debug(`${service.name} service not available (${service.port}):`, error.message);
          }
        }
      }
      
      setAvailableServices(available);
      setIsDiscoveringServices(false);
      return available;
    };

    // =============================================================================
    // OVERLAY MANAGEMENT
    // =============================================================================
    const showVisageResults = (imageId: string, imageUrl: string, visageResults: any) => {
      setOverlayData({ imageId, imageUrl, visageResults });
      setShowOverlay(true);
    };

    const closeOverlay = () => {
      setShowOverlay(false);
      setOverlayData(null);
    };

    // =============================================================================
    // MULTI-SELECT ACTION EXECUTION
    // =============================================================================
    const executeMultiSelectImageAnalysis = async (serviceName: string, multiSelectContext: any) => {
      // Use ImageHandler for batch processing
      const ImageHandler = (window as any).ImageHandler;
      if (!ImageHandler) {
        throw new Error('ImageHandler not available');
      }

      const imageHandler = new ImageHandler();

      // Set up progress tracking
      const options = {
        maxConcurrent: 2,
        skipErrors: true,
        onProgress: (processed: number, total: number, current?: any) => {
          console.log(`Multi-select processing progress: ${processed}/${total}${current ? ` - ${current.title || current.id}` : ''}`);
        },
        onError: (error: Error, imageData: any) => {
          console.error(`Error processing selected image ${imageData.id}:`, error);
        }
      };

      // Process selected images with batch handler
      const batchResults = await imageHandler.batchGetImagesWithBase64(multiSelectContext.selectedItems, options);
      
      if (batchResults.length === 0) {
        return {
          success: false,
          message: 'Failed to process any of the selected images'
        };
      }

      // Create job data for the processed images
      const jobData = await imageHandler.createBatchJobData(
        batchResults,
        'multi_select_analysis',
        {
          source: 'multi_select',
          selection_size: multiSelectContext.selectedItems.length,
          processed_count: batchResults.length
        }
      );

      // Extract base64 images from job tasks for /api/visage/job endpoint
      const images = jobData.tasks.map((task: any) => task.input_data.image_data);
      
      // Submit to service batch job endpoint with correct format
      const jobPayload = {
        images: images,
        visage_api_url: `http://${settings.stashAIServer}:9997/api/predict_1`,
        config: {
          threshold: settings.visageThreshold || 0.7,
          job_name: `Multi-Select Batch: ${multiSelectContext.selectedItems.length} images`,
          user_id: 'ai_overhaul_plugin',
          session_id: 'multi_select_batch_session',
          additional_params: {
            max_faces: 10,
            return_embeddings: false,
            source: 'ai_overhaul_multi_select_batch',
            entity_type: 'image',
            batch_context: {
              selection_type: 'multi_select_images',
              batch_size: jobData.tasks.length,
              original_selection_size: multiSelectContext.selectedItems.length
            }
          }
        }
      };

      console.log('Submitting multi-select batch job:', jobPayload);
      const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/visage/job`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(jobPayload)
      });

      if (!response.ok) {
        throw new Error(`Failed to create batch job: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      console.log('Multi-select batch job created:', result);

      // Job tracking is now handled by persistent queue WebSocket
      const jobId = result.job_id || result.id;
      if (jobId) {
        console.log('Multi-select batch job submitted to queue, will be tracked via persistent WebSocket:', jobId);
      }

      return {
        success: true,
        message: `${serviceName} batch processing started! Processing ${jobData.tasks.length} selected images as single batch job.`,
        jobId: jobId,
        data: {
          jobId: jobId,
          processedImages: jobData.tasks.length,
          totalSelected: multiSelectContext.selectedItems.length,
          type: 'multi_select_batch'
        }
      };
    };

    const executeMultiSelectSceneAnalysis = async (serviceName: string, multiSelectContext: any) => {
      // For scenes, we'll submit each scene directly as individual tasks
      const taskIds: string[] = [];
      let successCount = 0;

      for (const sceneId of multiSelectContext.selectedItems) {
        try {
          const taskData = {
            scene_id: sceneId,
            threshold: settings.visageThreshold || 0.7,
            visage_api_url: `http://${settings.stashAIServer}:9997/api/predict_1`,
            additional_params: {
              max_faces: 10,
              return_embeddings: false,
              source: 'ai_overhaul_multi_select_scenes',
              entity_type: 'scene',
              entity_id: sceneId,
              batch_context: {
                selection_type: 'multi_select_scenes',
                batch_size: multiSelectContext.selectedItems.length
              }
            }
          };

          const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/visage/task`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData)
          });

          if (response.ok) {
            const result = await response.json();
            if (result.task_id) {
              taskIds.push(result.task_id);
            }
            successCount++;
          } else {
            console.error(`Failed to create task for scene ${sceneId}: ${response.status}`);
          }
        } catch (error) {
          console.error(`Error creating task for scene ${sceneId}:`, error);
        }
      }

      return {
        success: successCount > 0,
        message: `${serviceName} batch processing started! Processing ${successCount} of ${multiSelectContext.selectedItems.length} selected scenes. ${taskIds.length} tasks created.`,
        taskId: taskIds.length > 0 ? taskIds[0] : undefined,
        data: {
          taskIds,
          processedScenes: successCount,
          totalSelected: multiSelectContext.selectedItems.length,
          type: 'multi_select_scenes'
        }
      };
    };

    const executeMultiSelectGalleryAnalysis = async (serviceName: string, multiSelectContext: any) => {
      // For galleries, we'll process each gallery as a batch
      // This is essentially multiple gallery batch analyses
      return {
        success: false,
        message: 'Multi-select gallery analysis is not yet implemented'
      };
    };

    // =============================================================================
    // ACTION EXECUTION
    // =============================================================================
    const executeAIAction = async (action: string, serviceName: string) => {
      // Validate settings
      if (!settings) {
        return {
          success: false,
          message: 'AI Overhaul settings not found. Please configure in Settings > Tools > AI Overhaul Settings.'
        };
      }

      // Handle face analysis for images and scenes
      if (action === 'analyze-faces' && (context.page === 'images' || context.page === 'scenes') && context.isDetailView) {
        try {
          let imageData = null;
          let base64Data = null;

          // Get image data and convert to base64
          if (context.page === 'images' && context.entityId) {
            console.log('Fetching image data for:', context.entityId);
            imageData = await findImage(context.entityId);
            
            if (!imageData) {
              throw new Error('Image not found');
            }

            const imageUrl = imageData.paths.image || imageData.paths.preview || imageData.paths.thumbnail;
            if (!imageUrl) {
              throw new Error('No valid image path found');
            }

            console.log('Converting image to base64:', imageUrl);
            base64Data = await imageToBase64(imageUrl);
          }

          // Use the generalized API format that the backend expects
          const taskData = {
            service_type: "visage",
            image_data: {
              stash_image_id: context.entityId,
              image_base64: base64Data,
              stash_image_title: imageData.title || `Image ${context.entityId}`,
              image_metadata: {
                urls: imageData.urls || [],
                galleries: imageData.galleries || []
              }
            },
            config: {
              threshold: settings.visageThreshold || 0.7,
              service_config: {
                api_endpoint: `http://${settings.stashAIServer}:9997/api/predict_1`,
                max_faces: 10,
                return_embeddings: false,
                detection_mode: "multi"
              },
              source: 'ai_overhaul_navbar_button'
            }
          };

          const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/visage/task`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData)
          });

          if (response.ok) {
            const result = await response.json();
            console.log('AI task created:', result);
            
            // Track the task status
            if (result.task_id) {
              // Add to local queue for immediate feedback
              const localTaskId = addToLocalQueue({
                id: result.task_id,
                type: 'visage',
                entityId: context.entityId,
                title: `Visage: ${imageData.title || `Image ${context.entityId}`}`,
                status: 'pending',
                job_id: result.job_id || result.task_id,
                server_task_id: result.task_id
              });

              setActiveTask({ 
                taskId: result.task_id, 
                status: 'pending',
                progress: 'Task queued for processing...'
              });
              
              // Subscribe to WebSocket updates if available, with fallback polling
              if (wsManager && wsManager.isConnected()) {
                console.log('Subscribing to WebSocket updates for task:', result.task_id);
                wsManager.subscribeToTask(result.task_id, (update: any) => {
                  console.log('Task update received:', update);
                  
                  // Update local queue task status
                  updateLocalQueueTask(result.task_id, {
                    status: update.status,
                    processing_time_ms: update.processing_time_ms,
                    output_json: update.output_json,
                    error_message: update.error_message
                  });
                  
                  setActiveTask(prev => prev?.taskId === update.task_id ? {
                    taskId: update.task_id,
                    status: update.status,
                    progress: getProgressMessage(update.status)
                  } : prev);
                  
                  // If task completed with results, show the overlay
                  if ((update.status === 'completed' || update.status === 'finished') && update.output_json && imageData) {
                    const imageUrl = imageData.paths.image || imageData.paths.preview || imageData.paths.thumbnail;
                    showVisageResults(context.entityId, imageUrl, update.output_json);
                    
                    // Add to recent completed jobs for dropdown
                    setRecentCompletedJobs(prev => [{
                      job_id: update.task_id,
                      type: 'visage',
                      entityId: context.entityId,
                      title: `Face Analysis - ${imageData?.title || `Image ${context.entityId}`}`,
                      completed_at: new Date().toISOString(),
                      result: update.output_json,
                      status: 'completed'
                    }, ...prev.slice(0, 4)]); // Keep last 5
                    
                    // Clear the active task after a delay and remove from local queue
                    setTimeout(() => {
                      setActiveTask(null);
                      setIsProcessing(false);
                      removeFromLocalQueue(result.task_id);
                    }, 3000);
                  } else if (update.status === 'failed') {
                    // Clear the active task on failure and remove from local queue
                    setTimeout(() => {
                      setActiveTask(null);
                      setIsProcessing(false);
                      removeFromLocalQueue(result.task_id);
                    }, 5000);
                  }
                });
              }
            }
            
            // The response will include task_id and status
            // Results will come later via task completion
            return {
              success: true,
              message: `${serviceName} analysis started! Task ID: ${result.task_id}`,
              taskId: result.task_id,
              data: result
            };
          } else {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
          }
        } catch (error: any) {
          console.error('AI action failed:', error);
          return {
            success: false,
            message: `${serviceName} analysis failed: ${error.message}`
          };
        }
      }
      // Handle gallery batch analysis
      else if (action === 'analyze-gallery-batch' && context.page === 'galleries' && context.isDetailView) {
        try {
          console.log('Starting gallery batch analysis for:', context.entityId);

          // Use ImageHandler for batch processing
          const ImageHandler = (window as any).ImageHandler;
          if (!ImageHandler) {
            throw new Error('ImageHandler not available');
          }

          const imageHandler = new ImageHandler();

          // Set up progress tracking with modular system
          const options = {
            maxConcurrent: 2,
            skipErrors: true,
            onProgress: (processed: number, total: number, current?: any) => {
              console.log(`Gallery processing progress: ${processed}/${total}${current ? ` - ${current.title || current.id}` : ''}`);
              
              // Update progress in modular system
              updateBatchJobProgress('gallery_preprocessing', {
                service: serviceName,
                status: 'processing_images',
                progress: (processed / total) * 50, // Pre-processing is 50% of total progress
                current: processed,
                total: total,
                message: `Processing images: ${processed}/${total}`,
                type: 'gallery_batch',
                details: { currentImage: current?.title || current?.id }
              });
            },
            onError: (error: Error, imageData: any) => {
              console.error(`Error processing image ${imageData.id}:`, error);
              
              updateBatchJobProgress('gallery_preprocessing', {
                service: serviceName,
                status: 'processing_error',
                message: `Error processing image ${imageData.id}: ${error.message}`,
                type: 'gallery_batch'
              });
            }
          };

          // Create gallery job data
          const { galleryData, jobData } = await imageHandler.createGalleryJobData(
            context.entityId,
            options,
            'gallery_visage_analysis'
          );

          console.log('Gallery job data created:', jobData);

          // Update progress: preprocessing completed
          updateBatchJobProgress('gallery_preprocessing', {
            service: serviceName,
            status: 'preprocessing_complete',
            progress: 50,
            current: jobData.tasks.length,
            total: jobData.tasks.length,
            message: `Batch processing completed: ${jobData.tasks.length}/${jobData.tasks.length} images processed successfully`,
            type: 'gallery_batch'
          });

          // Extract base64 images from job tasks for /api/visage/job endpoint
          const images = jobData.tasks.map((task: any) => task.input_data.image_data);
          
          // Submit to service batch job endpoint with correct format
          const jobPayload = {
            images: images,
            visage_api_url: `http://${settings.stashAIServer}:9997/api/predict_1`,
            config: {
              threshold: settings.visageThreshold || 0.7,
              job_name: `Gallery Batch: ${galleryData.title || 'Untitled'}`,
              user_id: 'ai_overhaul_plugin',
              session_id: 'gallery_batch_session',
              additional_params: {
                max_faces: 10,
                return_embeddings: false,
                source: 'ai_overhaul_gallery_batch',
                gallery_id: context.entityId,
                gallery_title: galleryData.title,
                total_images: jobData.tasks.length
              }
            }
          };

          // Update progress: submitting job
          updateBatchJobProgress('gallery_preprocessing', {
            service: serviceName,
            status: 'submitting_job',
            progress: 60,
            message: `Submitting gallery batch job: ${images.length} images`,
            type: 'gallery_batch',
            details: { payload: jobPayload }
          });

          console.log('Submitting gallery batch job:', jobPayload);

          const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/visage/job`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(jobPayload)
          });

          if (!response.ok) {
            throw new Error(`Failed to create batch job: ${response.status} ${response.statusText}`);
          }

          const result = await response.json();
          console.log('Gallery batch job created:', result);

          // Job tracking is now handled by persistent queue WebSocket
          const jobId = result.job_id || result.id;
          if (jobId) {
            console.log('Job submitted to queue, will be tracked via persistent WebSocket:', jobId);
            
            // Update progress to indicate job is queued
            updateBatchJobProgress(jobId, {
              service: serviceName,
              status: 'queued',
              progress: 70,
              message: `${serviceName} job queued and ready for processing`,
              type: 'gallery_batch',
              details: result
            });

            // Start polling backup if persistent WebSocket isn't available
            if (!queueWebSocket) {
              console.log('Persistent WebSocket not available, starting polling backup');
              startBatchJobPolling(settings, [batchJobProgress.get(jobId) as BatchJobProgress]);
            }
          }

          return {
            success: true,
            message: `${serviceName} batch job started! Processing ${jobData.tasks.length} images from gallery "${galleryData.title || 'Untitled'}".`,
            taskId: jobId, // Return job ID for tracking
            data: {
              jobId: jobId,
              galleryData,
              totalImages: jobData.tasks.length,
              type: 'gallery_batch',
              jobData
            }
          };

        } catch (error: any) {
          console.error('Gallery batch analysis failed:', error);
          return {
            success: false,
            message: `${serviceName} gallery analysis failed: ${error.message}`
          };
        }
      }
      // Handle multi-select actions
      else if (action.startsWith('multi-select-')) {
        const originalAction = action.replace('multi-select-', '');
        const multiSelectContext = detectMultiSelectContext();
        
        if (!multiSelectContext || multiSelectContext.selectedItems.length <= 1) {
          return {
            success: false,
            message: 'Multi-select action requires multiple items to be selected'
          };
        }

        try {
          console.log(`Starting multi-select ${originalAction} for ${multiSelectContext.count} ${multiSelectContext.selectionType}`);
          
          // Handle different multi-select actions based on content type
          if (multiSelectContext.selectionType === 'images' && originalAction === 'analyze-faces') {
            return await executeMultiSelectImageAnalysis(serviceName, multiSelectContext);
          } else if (multiSelectContext.selectionType === 'scenes' && originalAction === 'analyze-faces') {
            return await executeMultiSelectSceneAnalysis(serviceName, multiSelectContext);
          } else if (multiSelectContext.selectionType === 'galleries' && originalAction === 'analyze-gallery-batch') {
            return await executeMultiSelectGalleryAnalysis(serviceName, multiSelectContext);
          } else {
            return {
              success: false,
              message: `Multi-select ${originalAction} is not yet implemented for ${multiSelectContext.selectionType}`
            };
          }
        } catch (error: any) {
          console.error('Multi-select action failed:', error);
          return {
            success: false,
            message: `Multi-select ${serviceName} failed: ${error.message}`
          };
        }
      } else {
        return {
          success: false,
          message: `${serviceName} analysis is not yet implemented for this content type`
        };
      }
    };

    // =============================================================================
    // ACTION HANDLERS
    // =============================================================================
    const handleAction = async (action: string, serviceName: string) => {
      setIsProcessing(true);
      setShowDropdown(false);

      try {
        const result = await executeAIAction(action, serviceName);
        
        if (result.success) {
          alert(`✓ ${result.message}`);
        } else {
          alert(`✗ ${result.message}`);
        }
      } catch (error: any) {
        console.error('Action execution failed:', error);
        alert(`✗ Unexpected error: ${error.message}`);
      } finally {
        setIsProcessing(false);
      }
    };

    // =============================================================================
    // EVENT HANDLERS
    // =============================================================================
    const handleButtonClick = async () => {
      if (!settings) {
        alert('Please configure AI Overhaul in Settings > Tools > AI Overhaul Settings first.');
        return;
      }

      if (availableServices.length === 0) {
        console.log('AI Overhaul: Discovering services...');
        // Discover services first
        const services = await discoverServicesAndReturn();
        
        if (services.length === 0) {
          alert('No AI services are currently available. Please check your AI Overhaul settings and ensure services are running.');
          return;
        }
      }

      setShowDropdown(!showDropdown);
    };

    // =============================================================================
    // LOCAL QUEUE MANAGEMENT
    // =============================================================================
    const addToLocalQueue = (task: any) => {
      const taskId = task.id || Date.now().toString();
      setLocalQueue(prev => new Map(prev).set(taskId, {
        id: taskId,
        type: task.type || 'unknown',
        entityId: task.entityId,
        title: task.title || 'Processing...',
        status: task.status || 'pending',
        created_at: new Date().toISOString(),
        ...task
      }));
      return taskId;
    };

    const updateLocalQueueTask = (taskId: string, updates: any) => {
      setLocalQueue(prev => {
        const newQueue = new Map(prev);
        const existing = newQueue.get(taskId);
        if (existing) {
          newQueue.set(taskId, Object.assign({}, existing, updates));
        }
        return newQueue;
      });
    };

    const removeFromLocalQueue = (taskId: string) => {
      setLocalQueue(prev => {
        const newQueue = new Map(prev);
        newQueue.delete(taskId);
        return newQueue;
      });
    };

    // =============================================================================
    // QUEUE STATUS FUNCTIONS
    // =============================================================================
    const fetchQueueStats = async () => {
      if (!settings?.stashAIServer || !settings?.port) return;
      
      try {
        const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/queue/stats`);
        if (response.ok) {
          const stats = await response.json();
          setQueueStats(stats);
        }
      } catch (error) {
        console.warn('Failed to fetch queue stats:', error);
      }
    };

    const fetchQueueJobs = async () => {
      if (!settings?.stashAIServer || !settings?.port) return;
      
      try {
        const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/queue/jobs?limit=10&status=running,pending`);
        if (response.ok) {
          const data = await response.json();
          setServerJobs(data.jobs || []);
        }
      } catch (error) {
        console.warn('Failed to fetch queue jobs:', error);
      }
    };

    const fetchQueueTasks = async () => {
      if (!settings?.stashAIServer || !settings?.port) return;
      
      try {
        const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/queue/tasks?limit=10&status=pending,running`);
        if (response.ok) {
          const data = await response.json();
          setQueueTasks(data.tasks || []);
          
          // Update task progress from task details
          const progressMap = new Map();
          data.tasks.forEach((task: any) => {
            if (task.task_id && task.status) {
              progressMap.set(task.task_id, {
                status: task.status,
                processing_time_ms: task.processing_time_ms,
                created_at: task.created_at,
                started_at: task.started_at
              });
            }
          });
          setTaskProgress(progressMap);
        }
      } catch (error) {
        console.warn('Failed to fetch queue tasks:', error);
      }
    };

    const handleNotificationToggle = async () => {
      setShowNotificationDropdown(!showNotificationDropdown);
      if (!showNotificationDropdown) {
        // Fetch latest data when opening
        await Promise.all([fetchQueueStats(), fetchQueueJobs(), fetchQueueTasks()]);
      }
    };

    // Fetch job results from queue manager
    const fetchJobResults = async (jobId: string): Promise<any> => {
      if (!settings) {
        throw new Error('Settings not available');
      }

      const response = await fetch(`http://${settings.stashAIServer}:9998/api/job/${jobId}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch job results: ${response.status}`);
      }

      const jobData = await response.json();
      console.log('Fetched job data:', jobData);
      return jobData;
    };

    // Handle viewing results from completed jobs
    const handleViewResults = async (job: any) => {
      console.log('Viewing results for job:', job);
      
      // Handle gallery batch jobs
      if (job.job_type === 'gallery_analysis' || (job.details && job.details.type === 'gallery_batch')) {
        try {
          console.log('Loading gallery batch results for job:', job.job_id || job.id);
          const jobResults = await fetchJobResults(job.job_id || job.id);
          
          if (jobResults && jobResults.tasks) {
            // Extract gallery data from job metadata or create from job details
            const galleryData = {
              id: jobResults.metadata?.gallery_id || 'unknown',
              title: jobResults.metadata?.gallery_title || 'Batch Analysis Results'
            };
            
            console.log('Opening gallery results overlay with:', { jobResults, galleryData });
            setGalleryResultsData({ jobData: jobResults, galleryData });
            setShowGalleryResultsOverlay(true);
          } else {
            alert('❌ No results data found for this batch job');
          }
        } catch (error) {
          console.error('Error loading batch job results:', error);
          alert(`❌ Failed to load batch results: ${error.message}`);
        }
      }
      // Handle individual visage jobs
      else if (job.type === 'visage' && job.result && job.entityId) {
        try {
          // Get the image data to show the overlay
          const imageData = await findImage(job.entityId);
          if (imageData) {
            const imageUrl = imageData.paths.image || imageData.paths.preview || imageData.paths.thumbnail;
            showVisageResults(job.entityId, imageUrl, job.result);
          } else {
            alert('❌ Could not load image data for viewing results');
          }
        } catch (error) {
          console.error('Error loading image for results view:', error);
          alert('❌ Error loading image data');
        }
      } else {
        console.log('Unsupported job type for results viewing:', job);
        alert('ℹ️ Result viewing not yet implemented for this job type');
      }
    };

    // Close gallery results overlay
    const closeGalleryResultsOverlay = () => {
      setShowGalleryResultsOverlay(false);
      setGalleryResultsData(null);
    };

    // =============================================================================
    // UTILITY FUNCTIONS
    // =============================================================================
    const getProgressMessage = (status: string): string => {
      switch (status) {
        case 'pending': return 'Task queued for processing...';
        case 'running': return 'Analyzing image...';
        case 'completed':
        case 'finished': return 'Analysis completed!';
        case 'failed': return 'Analysis failed';
        default: return 'Processing...';
      }
    };
    const getContextType = (): string => {
      if (context.page === 'images' && context.isDetailView) return 'image';
      if (context.page === 'scenes' && context.isDetailView) return 'scene';  
      if (context.page === 'performers' && context.isDetailView) return 'performer';
      return context.page || 'unknown';
    };

    const getContextLabel = (): string => {
      const labels: Record<string, string> = {
        scenes: context.isDetailView ? 'Scene Detail' : 'Scenes',
        galleries: context.isDetailView ? 'Gallery Detail' : 'Galleries', 
        images: context.isDetailView ? 'Image Detail' : 'Images',
        groups: context.isDetailView ? 'Group Detail' : 'Groups',
        performers: context.isDetailView ? 'Performer Detail' : 'Performers',
        home: 'Home',
        unknown: 'General'
      };
      return labels[context.page] || 'General';
    };

    const getAvailableActionsForContext = () => {
      const contextType = getContextType();
      const contextActions = availableServices.filter(service => 
        service.supportedTypes.includes(contextType)
      );
      
      // Check for multi-select actions
      const multiSelectActions = getMultiSelectActions();
      
      return [...contextActions, ...multiSelectActions];
    };

    // =============================================================================
    // MULTI-SELECT DETECTION AND ACTIONS
    // =============================================================================
    const getMultiSelectActions = () => {
      const multiSelectContext = detectMultiSelectContext();
      if (!multiSelectContext || multiSelectContext.selectedItems.length <= 1) {
        return [];
      }

      // Create multi-select actions based on selected content type
      const actions = [];
      
      switch (multiSelectContext.selectionType) {
        case 'images':
          // Add available services that support images with multi-select prefix
          availableServices.forEach(service => {
            if (service.supportedTypes.includes('image')) {
              actions.push({
                ...service,
                name: `Batch ${service.name} (${multiSelectContext.selectedItems.length} images)`,
                action: `multi-select-${service.action}`,
                icon: `📦${service.icon}`,
                supportedTypes: ['multi-select-images']
              });
            }
          });
          break;
          
        case 'scenes':
          availableServices.forEach(service => {
            if (service.supportedTypes.includes('scene')) {
              actions.push({
                ...service,
                name: `Batch ${service.name} (${multiSelectContext.selectedItems.length} scenes)`,
                action: `multi-select-${service.action}`,
                icon: `📦${service.icon}`,
                supportedTypes: ['multi-select-scenes']
              });
            }
          });
          break;
          
        case 'galleries':
          availableServices.forEach(service => {
            if (service.supportedTypes.includes('galleries')) {
              actions.push({
                ...service,
                name: `Batch ${service.name} (${multiSelectContext.selectedItems.length} galleries)`,
                action: `multi-select-${service.action}`,
                icon: `📦${service.icon}`,
                supportedTypes: ['multi-select-galleries']
              });
            }
          });
          break;
      }
      
      return actions;
    };

    const detectMultiSelectContext = () => {
      try {
        // Determine current page type from URL first
        const pathname = window.location.pathname;
        let selectionType: 'images' | 'scenes' | 'performers' | 'galleries' = 'images';
        
        if (pathname.includes('/scenes')) {
          selectionType = 'scenes';
        } else if (pathname.includes('/performers')) {
          selectionType = 'performers';
        } else if (pathname.includes('/galleries')) {
          selectionType = 'galleries';
        } else if (pathname.includes('/images')) {
          selectionType = 'images';
        }

        // Use Stash's actual selection pattern
        const selectedElements = document.querySelectorAll('.grid-card .card-check:checked');
        
        if (selectedElements.length <= 1) {
          return null;
        }

        const selectedItems: string[] = [];

        // Extract IDs from Stash's card structure
        for (let i = 0; i < selectedElements.length; i++) {
          const element = selectedElements[i];
          
          // The checkbox is inside the grid-card, so find the parent grid-card
          const cardElement = element.closest('.grid-card') as Element || element;
          
          let id = null;
          
          // Try to extract ID from data attributes first (most reliable)
          id = cardElement.getAttribute('data-id') || 
               cardElement.getAttribute('data-image-id') ||
               cardElement.getAttribute('data-scene-id') ||
               cardElement.getAttribute('data-performer-id') ||
               cardElement.getAttribute('data-gallery-id');
                    
          // If no data attribute, try to extract from href attributes
          if (!id) {
            const link = cardElement.querySelector('a[href]');
            if (link) {
              const href = link.getAttribute('href');
              const match = href?.match(/\/(images|scenes|galleries|performers)\/(\d+)/);
              if (match) {
                selectedItems.push(match[2]);
                selectionType = match[1] as any;
                continue;
              }
            }
          }
          
          // If still no ID, try looking for it in nested elements
          if (!id) {
            const allLinks = cardElement.querySelectorAll('a[href]');
            for (let j = 0; j < allLinks.length; j++) {
              const link = allLinks[j];
              const href = link.getAttribute('href');
              const match = href?.match(/\/(images|scenes|galleries|performers)\/(\d+)/);
              if (match) {
                id = match[2];
                selectionType = match[1] as any;
                break;
              }
            }
          }
          
          if (id) {
            selectedItems.push(id);
          }
        }

        if (selectedItems.length <= 1) {
          return null;
        }

        return {
          selectedItems,
          selectionType,
          count: selectedItems.length
        };

      } catch (error) {
        console.error('Error detecting multi-select context:', error);
        return null;
      }
    };

    // =============================================================================
    // RENDER COMPONENT
    // =============================================================================
    if (!settings) {
      return null; // Don't show button if no settings
    }

    const contextType = getContextType();
    const contextLabel = getContextLabel();
    const availableActions = getAvailableActionsForContext();

    // Calculate comprehensive processing state including batch jobs
    const localQueueArray = Array.from(localQueue.values());
    const batchJobArray = Array.from(batchJobProgress.values()) as BatchJobProgress[];
    const activeBatchJobs = batchJobArray.filter((job) => 
      job.status !== 'completed' && job.status !== 'failed'
    );
    
    const totalActiveJobs = serverJobs.length + localQueueArray.length + activeBatchJobs.length;
    const isAnyProcessing = totalActiveJobs > 0 || activeTask !== null;
    
    // Calculate progress from all sources
    const completedLocalTasks = localQueueArray.filter((t: any) => 
      t.status === 'completed' || t.status === 'finished' || t.status === 'failed'
    ).length;
    const totalLocalTasks = localQueueArray.length;
    
    // Get most recent batch job progress for display
    const mostRecentBatchJob = batchJobArray
      .filter((job) => job.status !== 'completed' && job.status !== 'failed')
      .sort((a, b) => (b.lastUpdate || 0) - (a.lastUpdate || 0))[0];
    
    const displayProgress = mostRecentBatchJob ? {
      current: mostRecentBatchJob.current || 0,
      total: mostRecentBatchJob.total || 1,
      progress: mostRecentBatchJob.progress || 0,
      message: mostRecentBatchJob.message || 'Processing...',
      service: mostRecentBatchJob.service || 'AI'
    } : {
      current: completedLocalTasks,
      total: Math.max(totalLocalTasks, queueStats?.total_tasks || 0),
      progress: totalLocalTasks > 0 ? (completedLocalTasks / totalLocalTasks) * 100 : 0,
      message: 'Processing...',
      service: 'AI'
    };

    return React.createElement('div', {
      className: 'ai-overhaul-button-container',
      'data-context': contextType,
      style: { position: 'relative', display: 'inline-block' }
    }, [
      // =============================================================================
      // MAIN AI BUTTON
      // =============================================================================
      React.createElement('button', {
        key: 'ai-button',
        className: 'btn ai-overhaul-btn',
        onClick: handleButtonClick,
        disabled: isProcessing || activeTask !== null || isDiscoveringServices,
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          fontSize: '0.875rem',
          padding: '6px 12px',
          minWidth: '80px',
          justifyContent: 'center'
        },
        title: mostRecentBatchJob ? 
          `${mostRecentBatchJob.service} - ${mostRecentBatchJob.message}` :
          `AI Overhaul - ${contextLabel}`
      }, [
        // Progressive indicator based on processing state
        isDiscoveringServices ? (
          React.createElement('div', {
            key: 'discovery-indicator',
            style: {
              display: 'flex',
              alignItems: 'center',
              gap: '4px'
            }
          }, [
            React.createElement('div', {
              key: 'discovery-spinner',
              style: {
                width: '14px',
                height: '14px',
                borderRadius: '50%',
                border: '2px solid rgba(255, 255, 255, 0.3)',
                borderTop: '2px solid white',
                animation: 'spin 1s linear infinite'
              }
            }),
            React.createElement('span', { 
              key: 'discovery-text',
              style: { fontSize: '0.8rem', fontWeight: 'bold' }
            }, 'Discovering...')
          ])
        ) : isAnyProcessing ? (
          displayProgress.total > 0 ? 
            React.createElement('div', {
              key: 'progress-indicator',
              style: {
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }
            }, [
              React.createElement('div', {
                key: 'spinner',
                style: {
                  width: '14px',
                  height: '14px',
                  borderRadius: '50%',
                  border: '2px solid rgba(255, 255, 255, 0.3)',
                  borderTop: '2px solid white',
                  animation: 'spin 1s linear infinite'
                }
              }),
              React.createElement('span', { 
                key: 'progress-text',
                style: { fontSize: '0.8rem', fontWeight: 'bold' }
              }, 
                mostRecentBatchJob ? 
                  `${Math.round(mostRecentBatchJob.progress || 0)}%` : 
                  `${displayProgress.current}/${displayProgress.total}`
              )
            ]) :
            React.createElement('span', { 
              key: 'processing-icon',
              style: { fontSize: '1rem' }
            }, '⚡')
        ) : (
          React.createElement('span', { 
            key: 'idle-icon',
            style: { fontSize: '1rem' }
          }, '🤖')
        ),
        React.createElement('span', { 
          key: 'text',
          style: { fontSize: '0.875rem' }
        }, 
          isDiscoveringServices ? 'Finding Services...' :
          activeTask ? (activeTask.progress || 'Processing...') :
          isAnyProcessing ? (
            mostRecentBatchJob ? 
              `${mostRecentBatchJob.service} ${Math.round(mostRecentBatchJob.progress || 0)}%` :
              displayProgress.total > 0 ? 'AI Processing' : 'Processing...'
          ) :
          'AI Analyze'
        ),
        // Notification chevron with badge
        recentCompletedJobs.length > 0 ? React.createElement('div', {
          key: 'notification-area',
          style: { position: 'relative', marginLeft: '4px' }
        }, [
          React.createElement('button', {
            key: 'notification-btn',
            onClick: (e: any) => {
              e.stopPropagation();
              handleNotificationToggle();
            },
            style: {
              background: 'none',
              border: 'none',
              color: 'inherit',
              cursor: 'pointer',
              padding: '2px',
              borderRadius: '2px',
              fontSize: '0.8rem',
              display: 'flex',
              alignItems: 'center'
            },
            title: `${recentCompletedJobs.length} completed jobs`
          }, '🔔'),
          // Notification badge
          React.createElement('div', {
            key: 'notification-badge',
            style: {
              position: 'absolute',
              top: '-2px',
              right: '-2px',
              backgroundColor: '#ef4444',
              color: 'white',
              borderRadius: '8px',
              fontSize: '0.6rem',
              fontWeight: 'bold',
              padding: '1px 4px',
              minWidth: '14px',
              height: '14px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              lineHeight: 1
            }
          }, recentCompletedJobs.length.toString())
        ]) : null
      ]),

      // =============================================================================
      // DROPDOWN MENU
      // =============================================================================
      showDropdown ? React.createElement('div', {
        key: 'dropdown',
        className: 'ai-overhaul-dropdown'
      }, [
        // Dropdown Header
        React.createElement('div', {
          key: 'dropdown-header',
          className: 'ai-overhaul-dropdown-header'
        }, [
          React.createElement('div', {
            key: 'header-text',
            className: 'ai-overhaul-dropdown-header-text'
          }, `AI Analysis - ${contextLabel}`)
        ]),

        // Available Actions
        availableActions.length > 0 ? 
          availableActions.map((service, index) =>
            React.createElement('button', {
              key: `action-${index}`,
              className: 'ai-overhaul-dropdown-item',
              onClick: () => handleAction(service.action, service.name)
            }, [
              React.createElement('span', { 
                key: 'service-icon',
                className: 'ai-overhaul-service-icon'
              }, service.icon),
              React.createElement('div', { key: 'service-info' }, [
                React.createElement('div', {
                  key: 'service-name',
                  className: 'ai-overhaul-service-name'
                }, service.name),
                React.createElement('div', {
                  key: 'service-desc',
                  className: 'ai-overhaul-service-desc'
                }, service.description)
              ])
            ])
          ) : 
          // No Available Actions
          React.createElement('div', {
            key: 'no-actions',
            className: 'ai-overhaul-no-actions'
          }, `No AI services available for ${contextLabel} analysis`)
      ]) : null,

      // =============================================================================
      // CLICK OUTSIDE HANDLER
      // =============================================================================
      showDropdown ? React.createElement('div', {
        key: 'backdrop',
        style: {
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          zIndex: 999
        },
        onClick: () => setShowDropdown(false)
      }) : null,

      // =============================================================================
      // NOTIFICATION DROPDOWN
      // =============================================================================
      showNotificationDropdown ? React.createElement('div', {
        key: 'notification-dropdown',
        style: {
          position: 'absolute',
          top: '100%',
          right: '0',
          marginTop: '8px',
          background: 'rgba(0, 0, 0, 0.95)',
          backdropFilter: 'blur(15px)',
          borderRadius: '8px',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          padding: '0',
          minWidth: '320px',
          maxWidth: '450px',
          zIndex: 10000,
          fontSize: '0.8rem',
          color: 'white',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
          overflow: 'hidden'
        }
      }, [
        // Header section
        React.createElement('div', {
          key: 'queue-header',
          style: {
            padding: '12px 16px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
            background: 'rgba(74, 144, 226, 0.1)'
          }
        }, [
          React.createElement('div', {
            key: 'header-title',
            style: { fontWeight: 'bold', fontSize: '14px', marginBottom: '4px' }
          }, (activeTask || serverJobs.length > 0 || queueTasks.length > 0) ? '🔄 AI Processing Queue' : '✅ AI Job Notifications'),
          React.createElement('div', {
            key: 'header-subtitle',
            style: { fontSize: '12px', color: 'rgba(255, 255, 255, 0.7)' }
          }, (activeTask || serverJobs.length > 0 || queueTasks.length > 0) ? 
            `${(activeTask ? 1 : 0) + serverJobs.length} active, ${queueTasks.length} queued` :
            `${recentCompletedJobs.length} recent completed jobs`
          )
        ]),
        
        // Content area
        React.createElement('div', {
          key: 'queue-content',
          style: { maxHeight: '300px', overflowY: 'auto' }
        }, [
          // Active jobs section
          (activeTask || serverJobs.length > 0 || queueTasks.length > 0) ? React.createElement('div', {
            key: 'active-jobs-section',
            style: { padding: '12px 16px' }
          }, [
            // Currently running task
            activeTask ? React.createElement('div', {
              key: 'current-task',
              style: { 
                marginBottom: '8px',
                padding: '8px 12px',
                background: 'rgba(74, 222, 128, 0.1)',
                border: '1px solid rgba(74, 222, 128, 0.3)',
                borderRadius: '6px'
              }
            }, [
              React.createElement('div', {
                key: 'task-header',
                style: { 
                  display: 'flex', 
                  alignItems: 'center', 
                  gap: '8px',
                  marginBottom: '4px'
                }
              }, [
                React.createElement('div', {
                  key: 'spinner',
                  style: {
                    width: '12px',
                    height: '12px',
                    border: '2px solid rgba(74, 222, 128, 0.3)',
                    borderTop: '2px solid #4ade80',
                    borderRadius: '50%',
                    animation: activeTask.status === 'running' ? 'spin 1s linear infinite' : 'none'
                  }
                }),
                React.createElement('span', {
                  key: 'task-type',
                  style: { fontWeight: '600', color: '#4ade80' }
                }, 'Visage Analysis'),
                React.createElement('span', {
                  key: 'entity-id', 
                  style: { fontSize: '0.75rem', opacity: 0.7 }
                }, `ID: ${activeTask.taskId.substring(0, 8)}...`)
              ]),
              React.createElement('div', {
                key: 'task-details',
                style: { fontSize: '0.75rem', color: 'rgba(255, 255, 255, 0.8)' }
              }, activeTask.progress || 'Processing...')
            ]) : null,

            // Server jobs with progress
            serverJobs.map((job: any, index: number) => 
              React.createElement('div', {
                key: `server-job-${job.job_id || index}`,
                style: {
                  marginBottom: '8px',
                  padding: '8px 12px',
                  background: 'rgba(59, 130, 246, 0.1)',
                  border: '1px solid rgba(59, 130, 246, 0.3)',
                  borderRadius: '6px'
                }
              }, [
                React.createElement('div', {
                  key: 'job-header',
                  style: { 
                    display: 'flex', 
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: '4px'
                  }
                }, [
                  React.createElement('span', {
                    key: 'job-type',
                    style: { fontWeight: '600', color: '#60a5fa' }
                  }, job.adapter_name || job.job_type || 'Processing'),
                  React.createElement('span', {
                    key: 'job-status',
                    style: { 
                      fontSize: '0.75rem',
                      color: job.status === 'running' ? '#4ade80' : '#fbbf24'
                    }
                  }, job.status || 'pending')
                ]),
                job.progress_percentage ? React.createElement('div', {
                  key: 'job-progress-bar',
                  style: { marginBottom: '4px' }
                }, [
                  React.createElement('div', {
                    key: 'progress-bg',
                    style: {
                      width: '100%',
                      height: '4px',
                      background: 'rgba(255, 255, 255, 0.1)',
                      borderRadius: '2px',
                      overflow: 'hidden'
                    }
                  }, [
                    React.createElement('div', {
                      key: 'progress-fill',
                      style: {
                        width: `${job.progress_percentage}%`,
                        height: '100%',
                        background: 'linear-gradient(90deg, #60a5fa, #4ade80)',
                        transition: 'width 0.3s ease'
                      }
                    })
                  ]),
                  React.createElement('div', {
                    key: 'progress-text',
                    style: { fontSize: '0.7rem', opacity: 0.7, marginTop: '2px' }
                  }, `${Math.round(job.progress_percentage)}% - ${job.completed_tasks || 0}/${job.total_tasks || 0} tasks`)
                ]) : null,
                React.createElement('div', {
                  key: 'job-id',
                  style: { fontSize: '0.7rem', opacity: 0.6 }
                }, `Job: ${(job.job_id || '').substring(0, 12)}...`)
              ])
            ),

            // Queued tasks (next up)
            queueTasks.length > 0 ? React.createElement('div', {
              key: 'queued-section'
            }, [
              React.createElement('div', {
                key: 'queued-header',
                style: { 
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  color: '#fbbf24',
                  marginBottom: '6px',
                  paddingTop: '8px',
                  borderTop: activeTask || serverJobs.length > 0 ? '1px solid rgba(255, 255, 255, 0.1)' : 'none'
                }
              }, `⏳ Next ${Math.min(queueTasks.length, 3)} in Queue`),
              ...queueTasks.slice(0, 3).map((task: any, index: number) =>
                React.createElement('div', {
                  key: `queued-task-${index}`,
                  style: {
                    marginBottom: '4px',
                    padding: '6px 8px',
                    background: 'rgba(251, 191, 36, 0.1)',
                    border: '1px solid rgba(251, 191, 36, 0.2)',
                    borderRadius: '4px',
                    fontSize: '0.75rem'
                  }
                }, [
                  React.createElement('div', {
                    key: 'queued-info',
                    style: { display: 'flex', justifyContent: 'space-between' }
                  }, [
                    React.createElement('span', { 
                      key: 'adapter',
                      style: { fontWeight: '500' }
                    }, task.adapter_name || 'Unknown'),
                    React.createElement('span', { 
                      key: 'position',
                      style: { opacity: 0.7 }
                    }, `#${index + 1}`)
                  ])
                ])
              )
            ]) : null
          ]) : null,

          // Recent completed jobs section
          recentCompletedJobs.length > 0 ? React.createElement('div', {
            key: 'completed-section',
            style: { 
              padding: '12px 16px',
              borderTop: '1px solid rgba(255, 255, 255, 0.1)'
            }
          }, [
            React.createElement('div', {
              key: 'completed-header',
              style: { 
                fontSize: '0.75rem',
                fontWeight: '600',
                color: '#4ade80',
                marginBottom: '8px'
              }
            }, '✅ Recent Completed'),
            ...recentCompletedJobs.slice(0, 3).map((job: any, index: number) =>
              React.createElement('div', {
                key: `completed-${index}`,
                style: {
                  marginBottom: '6px',
                  padding: '6px 8px',
                  background: 'rgba(74, 222, 128, 0.1)',
                  border: '1px solid rgba(74, 222, 128, 0.2)',
                  borderRadius: '4px',
                  fontSize: '0.75rem'
                }
              }, [
                React.createElement('div', {
                  key: 'completed-info',
                  style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }
                }, [
                  React.createElement('div', {
                    key: 'job-details',
                    style: { flex: 1 }
                  }, [
                    React.createElement('span', { 
                      key: 'type',
                      style: { fontWeight: '500' }
                    }, job.type || 'Analysis'),
                    React.createElement('span', { 
                      key: 'time',
                      style: { opacity: 0.7, fontSize: '0.7rem', marginLeft: '8px' }
                    }, new Date(job.completed_at).toLocaleTimeString())
                  ]),
                  React.createElement('button', {
                    key: 'view-btn',
                    onClick: (e: any) => {
                      e.stopPropagation();
                      handleViewResults(job);
                    },
                    style: {
                      fontSize: '0.65rem',
                      padding: '2px 6px',
                      backgroundColor: '#4ade80',
                      color: 'white',
                      border: 'none',
                      borderRadius: '3px',
                      cursor: 'pointer',
                      fontWeight: '500'
                    },
                    title: `View ${job.type} results`
                  }, '👁️ View')
                ]),
                job.title ? React.createElement('div', {
                  key: 'completed-title',
                  style: { opacity: 0.8, fontSize: '0.7rem', marginTop: '2px' }
                }, job.title) : null
              ])
            )
          ]) : null,

          // No activity message
          !activeTask && serverJobs.length === 0 && queueTasks.length === 0 && recentCompletedJobs.length === 0 ? 
            React.createElement('div', {
              key: 'no-activity',
              style: { 
                padding: '20px 16px',
                textAlign: 'center',
                color: 'rgba(255, 255, 255, 0.6)' 
              }
            }, '🕊️ No active tasks or queue activity') : null
        ])
      ]) : null,

      // =============================================================================
      // VISAGE RESULTS OVERLAY
      // =============================================================================
      showOverlay && overlayData ? React.createElement((window as any).VisageImageResults, {
        key: 'visage-overlay',
        task: overlayData.task || { 
          input_data: { 
            entity_type: 'image',
            entity_id: overlayData.imageId,
            image_id: overlayData.imageId
          } 
        },
        visageResults: overlayData.visageResults,
        onClose: closeOverlay,
        React: React
      }) : null,

      // =============================================================================
      // GALLERY RESULTS OVERLAY
      // =============================================================================
      showGalleryResultsOverlay && galleryResultsData ? React.createElement((window as any).AIResultsOverlayGalleries, {
        key: 'gallery-results-overlay',
        jobData: galleryResultsData.jobData,
        galleryData: galleryResultsData.galleryData,
        onClose: closeGalleryResultsOverlay,
        React: React
      }) : null
    ]);
  };

  // =============================================================================
  // INTEGRATE AI BUTTON INTO NAVBAR AND LIST OPERATIONS
  // =============================================================================

  // Patch the MainNavBar.UtilityItems to add our AI button
  PluginApi.patch.before("MainNavBar.UtilityItems", function (props: any) {
    return [
      {
        children: React.createElement(React.Fragment, null,
          React.createElement(AIOverhaulButton, { key: 'ai-overhaul-navbar-button' }),
          props.children
        )
      }
    ];
  });

  // Create a global detection function for use in patches
  const globalDetectMultiSelectContext = () => {
    try {
      // Determine current page type from URL first
      const pathname = window.location.pathname;
      let selectionType: 'images' | 'scenes' | 'performers' | 'galleries' = 'images';
      
      if (pathname.includes('/scenes')) {
        selectionType = 'scenes';
      } else if (pathname.includes('/performers')) {
        selectionType = 'performers';
      } else if (pathname.includes('/galleries')) {
        selectionType = 'galleries';
      } else if (pathname.includes('/images')) {
        selectionType = 'images';
      }

      // Look for selected elements using Stash's actual selection pattern
      const selectedElements = document.querySelectorAll('.grid-card .card-check:checked');
      
      if (selectedElements.length <= 1) {
        return null;
      }

      const selectedItems: string[] = [];

      // Extract IDs from Stash's card structure
      for (let i = 0; i < selectedElements.length; i++) {
        const element = selectedElements[i];
        let id = null;
        
        // The checkbox is inside the grid-card, so find the parent grid-card
        const cardElement = element.closest('.grid-card') as Element || element;
        
        // Try to extract ID from data attributes first (most reliable)
        id = cardElement.getAttribute('data-id') || 
             cardElement.getAttribute('data-image-id') ||
             cardElement.getAttribute('data-scene-id') ||
             cardElement.getAttribute('data-performer-id') ||
             cardElement.getAttribute('data-gallery-id');
                  
        // If no data attribute, try to extract from href attributes
        if (!id) {
          const link = cardElement.querySelector('a[href]');
          if (link) {
            const href = link.getAttribute('href');
            const match = href?.match(/\/(images|scenes|galleries|performers)\/(\d+)/);
            if (match) {
              selectedItems.push(match[2]);
              // Update selection type if we found it from URL
              selectionType = match[1] as any;
              continue;
            }
          }
        }
        
        // If still no ID, try looking for it in nested elements
        if (!id) {
          // Look for links in card content
          const allLinks = cardElement.querySelectorAll('a[href]');
          for (let j = 0; j < allLinks.length; j++) {
            const link = allLinks[j];
            const href = link.getAttribute('href');
            const match = href?.match(/\/(images|scenes|galleries|performers)\/(\d+)/);
            if (match) {
              id = match[2];
              selectionType = match[1] as any;
              break;
            }
          }
        }
        
        if (id) {
          selectedItems.push(id);
        }
      }

      if (selectedItems.length <= 1) {
        return null;
      }

      return {
        selectedItems,
        selectionType,
        count: selectedItems.length
      };

    } catch (error) {
      console.error('Error detecting multi-select context:', error);
      return null;
    }
  };

  // Global AI action handler for patches
  const globalHandleAIAction = async (action: string, serviceName: string) => {
    const context = globalDetectMultiSelectContext();
    if (!context) return;

    try {
      console.log('🚀 Starting batch AI action:', { action, serviceName, context });
      
      // Use the existing multi-select processing logic
      if (context.selectionType === 'images') {
        // Get ImageHandler for batch processing
        const ImageHandler = (window as any).ImageHandler;
        if (!ImageHandler) {
          throw new Error('ImageHandler not available');
        }

        const imageHandler = new ImageHandler();
        
        // Process images with batch handler
        const batchResults = await imageHandler.batchGetImagesWithBase64(context.selectedItems, {
          maxConcurrent: 2,
          skipErrors: true
        });

        if (batchResults.length === 0) {
          alert('❌ Failed to process any of the selected images');
          return;
        }

        // Create job data for AI processing
        const jobData = await imageHandler.createBatchJobData(
          batchResults,
          'multi_select_analysis',
          {
            source: 'multi_select',
            selection_size: context.selectedItems.length,
            processed_count: batchResults.length
          }
        );

        // Submit the batch job to the queue manager
        const response = await fetch(`http://localhost:9998/api/batch_job`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service_name: serviceName.toLowerCase(),
            job_data: jobData,
            metadata: {
              type: 'multi_select_batch',
              selection_type: context.selectionType,
              total_items: context.selectedItems.length
            }
          })
        });

        if (response.ok) {
          const result = await response.json();
          alert(`✅ ${serviceName} batch analysis started! Processing ${batchResults.length} images. Job ID: ${result.job_id}`);
        } else {
          throw new Error(`Failed to submit batch job: ${response.status}`);
        }

      } else {
        // For other types, show not implemented message
        alert(`🚧 Batch ${serviceName} analysis for ${context.selectionType} is not yet implemented`);
      }

    } catch (error: any) {
      console.error('Batch AI action failed:', error);
      alert(`❌ Batch ${serviceName} failed: ${error.message}`);
    }
  };

  // No patching needed - the existing AI button will detect multi-select and show batch options

  console.log('AI Overhaul Button: Successfully initialized with multi-select support');

})();