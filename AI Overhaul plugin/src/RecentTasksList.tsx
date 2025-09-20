(function () {
  const PluginApi = (window as any).PluginApi;
  const React = PluginApi.React;

  // =============================================================================
  // RECENT TASKS LIST COMPONENT
  // =============================================================================

  interface RecentTasksListProps {
    limit?: number;
    showSuccessfulOnly?: boolean;
    onTaskSelect?: (taskId: string) => void;
  }

  const RecentTasksList = ({
    limit = 10,
    showSuccessfulOnly = false,
    onTaskSelect
  }: RecentTasksListProps) => {
    const [recentTasks, setRecentTasks] = React.useState([] as any[]);
    const [showingResults, setShowingResults] = React.useState(false);
    const [selectedTask, setSelectedTask] = React.useState(null as any);

    // Load recent tasks
    React.useEffect(() => {
      const recentTasksManager = (window as any).AIRecentTasks;
      if (recentTasksManager) {
        const tasks = showSuccessfulOnly 
          ? recentTasksManager.getSuccessful(limit)
          : recentTasksManager.getRecent(limit);
        setRecentTasks(tasks);
      }
    }, [limit, showSuccessfulOnly]);

    // Handle task selection and results viewing
    const handleTaskClick = async (task: any) => {
      console.log('Opening results for task:', task);
      onTaskSelect?.(task.taskId);

      // Fetch and show results
      try {
        const settings = JSON.parse(localStorage.getItem('ai_overhaul_settings') || '{}');
        if (!settings.stashAIServer || !settings.port) {
          alert('AI settings not found');
          return;
        }

        let resultsData = null;

        if (task.jobId) {
          // Fetch job results
          const jobUrl = `http://${settings.stashAIServer}:${settings.port}/api/queue/job/${task.jobId}`;
          const response = await fetch(jobUrl);
          
          if (response.ok) {
            const jobData = await response.json();
            resultsData = {
              type: 'job',
              data: jobData,
              isMultiImage: true
            };
          }
        } else {
          // Fetch single task results
          const taskUrl = `http://${settings.stashAIServer}:${settings.port}/api/queue/task/${task.taskId}`;
          const response = await fetch(taskUrl);
          
          if (response.ok) {
            const taskData = await response.json();
            resultsData = {
              type: 'task',
              data: taskData,
              isMultiImage: false
            };
          }
        }

        if (resultsData) {
          setSelectedTask({ ...task, resultsData });
          setShowingResults(true);
        } else {
          alert('Unable to fetch results for this task');
        }

      } catch (error) {
        console.error('Failed to fetch task results:', error);
        alert('Failed to load task results');
      }
    };

    // Get results component
    const getResultsComponent = () => {
      if (!selectedTask || !showingResults || !selectedTask.resultsData) return null;

      const VisageImageResults = (window as any).VisageImageResults;
      const AIResultsOverlayGalleries = (window as any).AIResultsOverlayGalleries;

      if (selectedTask.resultsData.isMultiImage && AIResultsOverlayGalleries) {
        return React.createElement(AIResultsOverlayGalleries, {
          key: 'gallery-results',
          jobData: selectedTask.resultsData.data,
          onClose: () => setShowingResults(false),
          React: React
        });
      } else if (!selectedTask.resultsData.isMultiImage && VisageImageResults) {
        return React.createElement(VisageImageResults, {
          key: 'image-results',
          task: selectedTask.resultsData.data,
          visageResults: selectedTask.resultsData.data.output_json,
          onClose: () => setShowingResults(false),
          React: React
        });
      }

      return null;
    };

    // Format task duration
    const formatDuration = (startTime: number, endTime: number) => {
      const duration = endTime - startTime;
      const seconds = Math.floor(duration / 1000);
      const minutes = Math.floor(seconds / 60);
      
      if (minutes > 0) {
        return `${minutes}m ${seconds % 60}s`;
      }
      return `${seconds}s`;
    };

    // Get status icon
    const getStatusIcon = (status: string) => {
      switch (status) {
        case 'finished': return '✅';
        case 'failed': return '❌';
        case 'cancelled': return '🚫';
        default: return '❓';
      }
    };

    if (recentTasks.length === 0) {
      return React.createElement('div', {
        style: {
          padding: '16px',
          textAlign: 'center',
          color: '#6b7280',
          fontSize: '14px'
        }
      }, showSuccessfulOnly ? 'No successful tasks yet' : 'No recent tasks yet');
    }

    return React.createElement('div', {
      className: 'recent-tasks-list',
      style: {
        maxHeight: '300px',
        overflowY: 'auto',
        border: '1px solid rgba(75, 85, 99, 0.3)',
        borderRadius: '8px',
        backgroundColor: 'rgba(17, 24, 39, 0.8)'
      }
    }, [
      ...recentTasks.map((task, index) =>
        React.createElement('div', {
          key: task.taskId,
          onClick: () => handleTaskClick(task),
          style: {
            padding: '12px 16px',
            borderBottom: index < recentTasks.length - 1 ? '1px solid rgba(75, 85, 99, 0.2)' : 'none',
            cursor: 'pointer',
            transition: 'background-color 0.2s ease',
            backgroundColor: 'transparent'
          },
          onMouseEnter: (e: any) => {
            e.target.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
          },
          onMouseLeave: (e: any) => {
            e.target.style.backgroundColor = 'transparent';
          }
        }, [
          React.createElement('div', {
            key: 'task-header',
            style: {
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '4px'
            }
          }, [
            React.createElement('div', {
              key: 'service-info',
              style: {
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }
            }, [
              React.createElement('span', {
                key: 'status-icon',
                style: { fontSize: '14px' }
              }, getStatusIcon(task.status)),
              React.createElement('span', {
                key: 'service-name',
                style: {
                  fontWeight: '500',
                  color: '#f9fafb',
                  fontSize: '14px'
                }
              }, task.serviceName),
              task.isMultiImage ? React.createElement('span', {
                key: 'multi-badge',
                style: {
                  fontSize: '10px',
                  padding: '2px 6px',
                  backgroundColor: 'rgba(59, 130, 246, 0.2)',
                  color: '#93c5fd',
                  borderRadius: '10px'
                }
              }, 'BATCH') : null
            ]),
            React.createElement('span', {
              key: 'duration',
              style: {
                fontSize: '11px',
                color: '#9ca3af'
              }
            }, formatDuration(task.startTime, task.endTime))
          ]),
          React.createElement('div', {
            key: 'task-details',
            style: {
              fontSize: '11px',
              color: '#d1d5db'
            }
          }, [
            React.createElement('div', { key: 'message' }, task.message || 'Task completed'),
            task.totalTasks ? React.createElement('div', {
              key: 'progress',
              style: { marginTop: '2px', color: '#9ca3af' }
            }, `${task.completedTasks || 0}/${task.totalTasks} tasks${task.failedTasks > 0 ? ` (${task.failedTasks} failed)` : ''}`) : null
          ])
        ])
      ),
      
      // Results overlay
      showingResults ? getResultsComponent() : null
    ]);
  };

  // Export for use in other components
  (window as any).RecentTasksList = RecentTasksList;

  console.log('Recent Tasks List: Successfully loaded');

})();