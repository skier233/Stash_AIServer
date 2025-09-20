(function () {
  const PluginApi = (window as any).PluginApi;
  const React = PluginApi.React;

  // =============================================================================
  // AI TASK PROGRESS HOVER COMPONENT
  // =============================================================================

  interface TaskProgress {
    taskId: string;
    jobId?: string;
    status: 'pending' | 'running' | 'finished' | 'failed' | 'cancelled';
    serviceName: string;
    progress?: number;
    message?: string;
    startTime: number;
    currentTask?: string;
    totalTasks?: number;
    completedTasks?: number;
    failedTasks?: number;
    processingTimeMs?: number;
    outputJson?: any;
  }

  interface AITaskProgressHoverProps {
    activeTask: TaskProgress | null;
    onCancel?: (taskId: string, jobId?: string) => void;
    onClose?: () => void; // New close callback
    isVisible: boolean;
    mode?: 'progress' | 'results'; // New mode prop
  }

  const formatDuration = (startTime: number): string => {
    const elapsed = Date.now() - startTime;
    const seconds = Math.floor(elapsed / 1000);
    const minutes = Math.floor(seconds / 60);
    
    if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
    }
    return `${seconds}s`;
  };

  const getStatusIcon = (status: string): string => {
    switch (status) {
      case 'pending': return '⏳';
      case 'running': return '⚡';
      case 'finished': return '✅';
      case 'failed': return '❌';
      case 'cancelled': return '🚫';
      default: return '⚡';
    }
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'pending': return '#f59e0b';
      case 'running': return '#3b82f6';
      case 'finished': return '#10b981';
      case 'failed': return '#ef4444';
      case 'cancelled': return '#6b7280';
      default: return '#3b82f6';
    }
  };

  const AITaskProgressHover = ({ 
    activeTask, 
    onCancel,
    onClose, 
    isVisible,
    mode = 'progress'
  }: AITaskProgressHoverProps) => {
    const [showingResults, setShowingResults] = React.useState(false);
    const [resultsData, setResultsData] = React.useState(null as any);

    // Fetch task/job results for completed tasks
    const fetchResults = async (task: TaskProgress) => {
      if (!task.taskId || task.status !== 'finished') {
        return null;
      }

      try {
        const settings = JSON.parse(localStorage.getItem('ai_overhaul_settings') || '{}');
        if (!settings.stashAIServer || !settings.port) {
          console.warn('Settings not available for results fetching');
          return null;
        }

        if (task.jobId) {
          // Fetch job results for batch/gallery operations
          console.log(`Fetching job results for: ${task.jobId}`);
          const jobUrl = `http://${settings.stashAIServer}:${settings.port}/api/queue/job/${task.jobId}`;
          const response = await fetch(jobUrl);
          
          if (!response.ok) {
            throw new Error(`Failed to fetch job results: ${response.status}`);
          }
          
          const jobData = await response.json();
          return {
            type: 'job',
            data: jobData,
            isMultiImage: true
          };
        } else {
          // Fetch single task results
          console.log(`Fetching task results for: ${task.taskId}`);
          const taskUrl = `http://${settings.stashAIServer}:${settings.port}/api/queue/task/${task.taskId}`;
          const response = await fetch(taskUrl);
          
          if (!response.ok) {
            throw new Error(`Failed to fetch task results: ${response.status}`);
          }
          
          const taskData = await response.json();
          return {
            type: 'task',
            data: taskData,
            isMultiImage: false
          };
        }
      } catch (error) {
        console.error('Failed to fetch results:', error);
        return null;
      }
    };

    // Handle showing results
    const handleShowResults = async () => {
      if (!activeTask) return;

      console.log('Fetching results for task:', activeTask);
      const results = await fetchResults(activeTask);
      
      if (results) {
        setResultsData(results);
        setShowingResults(true);
      } else {
        alert('Unable to fetch results for this task. Results may not be available or the task may still be processing.');
      }
    };

    // Determine which results component to use
    const getResultsComponent = () => {
      if (!resultsData || !showingResults) return null;

      const VisageImageResults = (window as any).VisageImageResults;
      const AIResultsOverlayGalleries = (window as any).AIResultsOverlayGalleries;

      console.log('🎯 AITaskProgressHover: Rendering results component:', {
        isMultiImage: resultsData.isMultiImage,
        dataType: resultsData.type,
        hasVisageImageResults: !!VisageImageResults,
        hasAIResultsOverlayGalleries: !!AIResultsOverlayGalleries,
        data: resultsData.data
      });

      if (resultsData.isMultiImage && AIResultsOverlayGalleries) {
        // Use gallery/batch results component for jobs
        return React.createElement(AIResultsOverlayGalleries, {
          key: 'gallery-results',
          jobData: resultsData.data,
          onClose: () => {
            console.log('🔒 AITaskProgressHover: Closing gallery results overlay');
            setShowingResults(false);
            setResultsData(null);
          },
          React: React
        });
      } else if (!resultsData.isMultiImage && VisageImageResults && resultsData.data.output_json) {
        // Use single image results component for individual tasks
        console.log('🖼️ AITaskProgressHover: Rendering VisageImageResults with:', {
          task: resultsData.data,
          visageResults: resultsData.data.output_json
        });
        
        return React.createElement(VisageImageResults, {
          key: 'image-results',
          task: resultsData.data,
          visageResults: resultsData.data.output_json,
          onClose: () => {
            console.log('🔒 AITaskProgressHover: Closing image results overlay');
            setShowingResults(false);
            setResultsData(null);
          },
          React: React
        });
      } else {
        // Fallback: show a simple results display
        console.warn('🚨 AITaskProgressHover: No suitable results component found, showing fallback');
        return React.createElement('div', {
          key: 'fallback-results',
          style: {
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.8)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px'
          }
        }, [
          React.createElement('div', {
            key: 'fallback-content',
            style: {
              backgroundColor: '#1f2937',
              borderRadius: '12px',
              padding: '24px',
              maxWidth: '80vw',
              maxHeight: '80vh',
              overflow: 'auto',
              border: '1px solid #374151'
            }
          }, [
            React.createElement('div', {
              key: 'fallback-header',
              style: {
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '16px',
                paddingBottom: '16px',
                borderBottom: '1px solid #374151'
              }
            }, [
              React.createElement('h2', {
                key: 'title',
                style: { color: '#f9fafb', margin: 0 }
              }, `${activeTask?.serviceName || 'Task'} Results`),
              React.createElement('button', {
                key: 'close',
                onClick: () => {
                  setShowingResults(false);
                  setResultsData(null);
                },
                style: {
                  background: 'none',
                  border: 'none',
                  color: '#9ca3af',
                  fontSize: '24px',
                  cursor: 'pointer',
                  padding: '4px'
                }
              }, '×')
            ]),
            React.createElement('pre', {
              key: 'data',
              style: {
                color: '#d1d5db',
                fontSize: '12px',
                lineHeight: '1.5',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                backgroundColor: '#111827',
                padding: '16px',
                borderRadius: '8px',
                border: '1px solid #374151'
              }
            }, JSON.stringify(resultsData.data, null, 2))
          ])
        ]);
      }

      return null;
    };

    // Note: WebSocket connection is handled by the global TaskTracker
    // This component relies on the existing TaskTracker WebSocket connection
    React.useEffect(() => {
      console.log('AI Task Hover: Using existing TaskTracker WebSocket connection');
    }, []);

    // Handle task cancellation
    const handleCancel = async () => {
      if (!activeTask) return;

      const confirmed = confirm(
        `Cancel ${activeTask.serviceName} task?\n\n` +
        `Task ID: ${activeTask.taskId}\n` +
        `This will stop the processing and cannot be undone.`
      );

      if (!confirmed) return;

      try {
        const cancellation = (window as any).AIOverhaulCancellation;
        if (!cancellation) {
          throw new Error('Cancellation utilities not available');
        }

        let result;
        if (activeTask.jobId) {
          console.log(`Cancelling job ${activeTask.jobId}...`);
          result = await cancellation.cancelJob(activeTask.jobId);
        } else {
          console.log(`Cancelling task ${activeTask.taskId}...`);
          result = await cancellation.cancelTask(activeTask.taskId);
        }

        if (result.success) {
          alert(`✅ Cancellation successful!\n\n${result.message}`);
          onCancel?.(activeTask.taskId, activeTask.jobId);
        } else {
          alert(`❌ Cancellation failed:\n\n${result.message}`);
        }
      } catch (error: any) {
        console.error('Failed to cancel task:', error);
        alert(`❌ Failed to cancel task:\n\n${error.message}`);
      }
    };

    if (!isVisible || !activeTask) {
      return showingResults ? getResultsComponent() : null;
    }

    const statusColor = getStatusColor(activeTask.status);
    const statusIcon = getStatusIcon(activeTask.status);
    const duration = formatDuration(activeTask.startTime);
    const isJobTask = activeTask.totalTasks && activeTask.totalTasks > 1;

    // Render results overlay separately if showing
    if (showingResults) {
      return getResultsComponent();
    }

    return React.createElement('div', {
      className: 'ai-task-progress-hover',
      style: {
        position: 'absolute',
        top: '100%',
        right: '0',
        marginTop: '8px',
        minWidth: '280px',
        maxWidth: '320px',
        padding: '16px',
        borderRadius: '12px',
        background: 'rgba(17, 24, 39, 0.95)',
        backdropFilter: 'blur(12px)',
        border: '1px solid rgba(75, 85, 99, 0.3)',
        boxShadow: '0 10px 25px rgba(0, 0, 0, 0.4), 0 6px 10px rgba(0, 0, 0, 0.3)',
        color: '#f9fafb',
        fontSize: '13px',
        zIndex: 1000,
        animation: 'fadeInUp 0.2s ease-out'
      }
    }, [
      // Header with service name and status
      React.createElement('div', {
        key: 'header',
        style: {
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '12px'
        }
      }, [
        React.createElement('div', {
          key: 'service-info',
          style: { display: 'flex', alignItems: 'center', gap: '8px' }
        }, [
          React.createElement('span', {
            key: 'status-icon',
            style: { fontSize: '16px' }
          }, statusIcon),
          React.createElement('div', {
            key: 'service-text'
          }, [
            React.createElement('div', {
              key: 'service-name',
              style: { fontWeight: '600', color: '#f9fafb' }
            }, activeTask.serviceName),
            React.createElement('div', {
              key: 'status-text',
              style: { fontSize: '11px', color: statusColor, textTransform: 'capitalize' }
            }, activeTask.status)
          ])
        ]),
        React.createElement('div', {
          key: 'header-right',
          style: { display: 'flex', alignItems: 'center', gap: '8px' }
        }, [
          React.createElement('div', {
            key: 'duration',
            style: { fontSize: '11px', color: '#9ca3af' }
          }, duration),
          onClose ? React.createElement('button', {
            key: 'close-btn',
            onClick: onClose,
            style: {
              background: 'none',
              border: 'none',
              color: '#9ca3af',
              fontSize: '16px',
              cursor: 'pointer',
              padding: '2px',
              lineHeight: '1',
              borderRadius: '4px',
              transition: 'color 0.2s ease'
            },
            onMouseEnter: (e: any) => {
              e.target.style.color = '#f9fafb';
            },
            onMouseLeave: (e: any) => {
              e.target.style.color = '#9ca3af';
            },
            title: 'Close'
          }, '×') : null
        ])
      ]),

      // Progress information
      React.createElement('div', {
        key: 'progress-info',
        style: { marginBottom: '12px' }
      }, [
        // Progress bar for jobs
        isJobTask && activeTask.completedTasks !== undefined && activeTask.totalTasks ? 
          React.createElement('div', {
            key: 'progress-section',
            style: { marginBottom: '8px' }
          }, [
            React.createElement('div', {
              key: 'progress-text',
              style: {
                display: 'flex',
                justifyContent: 'space-between',
                marginBottom: '4px',
                fontSize: '11px',
                color: '#d1d5db'
              }
            }, [
              React.createElement('span', { key: 'completed' }, 
                `${activeTask.completedTasks}/${activeTask.totalTasks} tasks`),
              React.createElement('span', { key: 'percentage' }, 
                `${Math.round((activeTask.completedTasks / activeTask.totalTasks) * 100)}%`)
            ]),
            React.createElement('div', {
              key: 'progress-bar-bg',
              style: {
                width: '100%',
                height: '6px',
                backgroundColor: 'rgba(75, 85, 99, 0.5)',
                borderRadius: '3px',
                overflow: 'hidden'
              }
            }, [
              React.createElement('div', {
                key: 'progress-bar-fill',
                style: {
                  width: `${(activeTask.completedTasks / activeTask.totalTasks) * 100}%`,
                  height: '100%',
                  backgroundColor: statusColor,
                  borderRadius: '3px',
                  transition: 'width 0.3s ease'
                }
              })
            ])
          ]) : null,

        // Current message
        activeTask.message ? React.createElement('div', {
          key: 'message',
          style: {
            fontSize: '11px',
            color: '#d1d5db',
            lineHeight: '1.4',
            marginBottom: '8px'
          }
        }, activeTask.message) : null,

        // Task details
        React.createElement('div', {
          key: 'task-details',
          style: {
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '8px',
            fontSize: '11px',
            color: '#9ca3af'
          }
        }, [
          React.createElement('div', { key: 'task-id' }, [
            React.createElement('span', { 
              key: 'task-label',
              style: { color: '#6b7280' } 
            }, isJobTask ? 'Job ID: ' : 'Task ID: '),
            React.createElement('span', { 
              key: 'task-value',
              style: { fontFamily: 'monospace', fontSize: '10px' } 
            }, (activeTask.jobId || activeTask.taskId).substring(0, 8) + '...')
          ]),
          activeTask.failedTasks !== undefined && activeTask.failedTasks > 0 ? 
            React.createElement('div', { key: 'failed-tasks' }, [
              React.createElement('span', { 
                key: 'failed-label',
                style: { color: '#ef4444' } 
              }, 'Failed: '),
              React.createElement('span', { key: 'failed-value' }, activeTask.failedTasks)
            ]) : null
        ])
      ]),

      // Action buttons
      React.createElement('div', {
        key: 'actions',
        style: {
          display: 'flex',
          gap: '8px',
          paddingTop: '12px',
          borderTop: '1px solid rgba(75, 85, 99, 0.3)'
        }
      }, [
        // Cancel button (only show for pending/running tasks)
        ['pending', 'running'].includes(activeTask.status) ? 
          React.createElement('button', {
            key: 'cancel-btn',
            onClick: handleCancel,
            style: {
              flex: 1,
              padding: '6px 12px',
              fontSize: '11px',
              fontWeight: '500',
              color: '#f9fafb',
              backgroundColor: 'rgba(239, 68, 68, 0.2)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              borderRadius: '6px',
              cursor: 'pointer',
              transition: 'all 0.2s ease'
            },
            onMouseEnter: (e: any) => {
              e.target.style.backgroundColor = 'rgba(239, 68, 68, 0.3)';
            },
            onMouseLeave: (e: any) => {
              e.target.style.backgroundColor = 'rgba(239, 68, 68, 0.2)';
            }
          }, '🚫 Cancel') : null,

        // View Results button (for finished tasks)
        activeTask.status === 'finished' ? 
          React.createElement('button', {
            key: 'results-btn',
            onClick: handleShowResults,
            style: {
              flex: 1,
              padding: '6px 12px',
              fontSize: '11px',
              fontWeight: '500',
              color: '#f9fafb',
              backgroundColor: 'rgba(16, 185, 129, 0.2)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              borderRadius: '6px',
              cursor: 'pointer',
              transition: 'all 0.2s ease'
            },
            onMouseEnter: (e: any) => {
              e.target.style.backgroundColor = 'rgba(16, 185, 129, 0.3)';
            },
            onMouseLeave: (e: any) => {
              e.target.style.backgroundColor = 'rgba(16, 185, 129, 0.2)';
            }
          }, '🔍 View Results') :
        // View details button for non-finished tasks
        React.createElement('button', {
          key: 'details-btn',
          onClick: () => {
            console.log('Active Task Details:', activeTask);
            alert(`Task Details:\n\n${JSON.stringify(activeTask, null, 2)}`);
          },
          style: {
            flex: 1,
            padding: '6px 12px',
            fontSize: '11px',
            fontWeight: '500',
            color: '#f9fafb',
            backgroundColor: 'rgba(59, 130, 246, 0.2)',
            border: '1px solid rgba(59, 130, 246, 0.3)',
            borderRadius: '6px',
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          },
          onMouseEnter: (e: any) => {
            e.target.style.backgroundColor = 'rgba(59, 130, 246, 0.3)';
          },
          onMouseLeave: (e: any) => {
            e.target.style.backgroundColor = 'rgba(59, 130, 246, 0.2)';
          }
        }, '📋 Details')
      ]),
      
      // Note: Results are rendered separately as full-screen overlays outside this container
    ]);
  };

  // Add CSS animation keyframes
  const style = document.createElement('style');
  style.textContent = `
    @keyframes fadeInUp {
      from {
        opacity: 0;
        transform: translateY(-10px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    .ai-task-progress-hover {
      pointer-events: auto;
    }

    .ai-task-progress-hover button:active {
      transform: scale(0.98);
    }
  `;
  document.head.appendChild(style);

  // Export for use in other components
  (window as any).AITaskProgressHover = AITaskProgressHover;

  console.log('AI Task Progress Hover: Successfully loaded');

})();