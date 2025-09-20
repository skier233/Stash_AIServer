(function () {
  const PluginApi = (window as any).PluginApi;
  const React = PluginApi.React;
  const { Link } = PluginApi.libraries.ReactRouterDOM;
  const { Button } = PluginApi.libraries.Bootstrap;

  // Import external VisageImageResults component
  const VisageImageResults = (window as any).VisageImageResults;

  // Import HealthEndpoint component (will be embedded)
  const HealthEndpoint = ({ healthData, availableServices }: { healthData: any, availableServices: any[] }) => {
    // =============================================================================
    // UTILITY FUNCTIONS
    // =============================================================================
    const formatTimestamp = (timestamp: string): string => {
      return new Date(timestamp).toLocaleString();
    };

    const getStatusColor = (status: string | boolean): string => {
      if (typeof status === 'boolean') {
        return status ? '#4ade80' : '#f87171';
      }
      return status === 'healthy' ? '#4ade80' : '#f87171';
    };

    const getStatusIcon = (status: string | boolean): string => {
      if (typeof status === 'boolean') {
        return status ? '✓' : '✗';
      }
      return status === 'healthy' ? '✓' : '✗';
    };

    // =============================================================================
    // RENDER COMPONENT
    // =============================================================================
    return React.createElement('div', {
      className: 'ai-overhaul-health-results ai-overhaul-fade-in'
    }, [
      // Main Status Section
      React.createElement('div', {
        key: 'main-status',
        style: { 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'space-between',
          marginBottom: '16px',
          paddingBottom: '12px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)'
        }
      }, [
        React.createElement('div', {
          key: 'status-info',
          style: { display: 'flex', alignItems: 'center', gap: '12px' }
        }, [
          React.createElement('div', {
            key: 'status-icon',
            style: {
              color: getStatusColor(healthData.status),
              fontSize: '1.2rem',
              fontWeight: 'bold'
            }
          }, getStatusIcon(healthData.status)),
          React.createElement('div', { key: 'status-text' }, [
            React.createElement('div', {
              key: 'status-title',
              style: { 
                color: 'rgba(255, 255, 255, 0.9)',
                fontWeight: '600',
                fontSize: '1rem'
              }
            }, `Server ${healthData.status}`),
            React.createElement('div', {
              key: 'version',
              style: { 
                color: 'rgba(255, 255, 255, 0.6)',
                fontSize: '0.85rem'
              }
            }, `Version ${healthData.version}`)
          ])
        ]),
        React.createElement('div', {
          key: 'timestamp',
          style: {
            color: 'rgba(255, 255, 255, 0.5)',
            fontSize: '0.8rem',
            fontFamily: 'monospace'
          }
        }, formatTimestamp(healthData.timestamp))
      ]),

      // Database Status
      React.createElement('div', {
        key: 'database-status',
        style: {
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          marginBottom: healthData.queue ? '12px' : '0'
        }
      }, [
        React.createElement('span', {
          key: 'db-icon',
          style: { 
            color: getStatusColor(healthData.database === 'connected'),
            fontWeight: 'bold'
          }
        }, getStatusIcon(healthData.database === 'connected')),
        React.createElement('span', {
          key: 'db-label',
          style: { 
            color: 'rgba(255, 255, 255, 0.7)',
            fontSize: '0.9rem'
          }
        }, 'Database'),
        React.createElement('span', {
          key: 'db-status',
          style: { 
            color: getStatusColor(healthData.database === 'connected'),
            fontWeight: '500',
            fontSize: '0.9rem'
          }
        }, healthData.database)
      ]),

      // Queue Status (if available)
      healthData.queue ? React.createElement('div', {
        key: 'queue-section',
        style: {
          background: 'rgba(255, 255, 255, 0.02)',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          borderRadius: '8px',
          padding: '12px',
          marginTop: '8px'
        }
      }, [
        React.createElement('div', {
          key: 'queue-title',
          style: {
            color: 'rgba(255, 255, 255, 0.8)',
            fontWeight: '600',
            fontSize: '0.9rem',
            marginBottom: '8px'
          }
        }, 'Queue Manager'),
        
        // Queue Health
        React.createElement('div', {
          key: 'queue-health',
          style: { display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }
        }, [
          React.createElement('span', {
            key: 'queue-icon',
            style: { color: getStatusColor(healthData.queue.queue_healthy) }
          }, getStatusIcon(healthData.queue.queue_healthy)),
          React.createElement('span', {
            key: 'queue-text',
            style: { color: 'rgba(255, 255, 255, 0.7)', fontSize: '0.85rem' }
          }, `Queue ${healthData.queue.queue_healthy ? 'Healthy' : 'Unhealthy'}`)
        ]),

        // Manager Health
        React.createElement('div', {
          key: 'manager-health',
          style: { display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }
        }, [
          React.createElement('span', {
            key: 'manager-icon',
            style: { color: getStatusColor(healthData.queue.manager_healthy) }
          }, getStatusIcon(healthData.queue.manager_healthy)),
          React.createElement('span', {
            key: 'manager-text',
            style: { color: 'rgba(255, 255, 255, 0.7)', fontSize: '0.85rem' }
          }, `Manager ${healthData.queue.manager_healthy ? 'Healthy' : 'Unhealthy'}`)
        ]),

        // Queue Settings
        React.createElement('div', {
          key: 'queue-settings',
          style: { 
            marginTop: '8px',
            paddingTop: '8px',
            borderTop: '1px solid rgba(255, 255, 255, 0.05)'
          }
        }, [
          React.createElement('div', {
            key: 'queue-enabled',
            style: { 
              color: 'rgba(255, 255, 255, 0.6)', 
              fontSize: '0.8rem',
              marginBottom: '2px'
            }
          }, `Queue Enabled: ${healthData.queue.queue_enabled ? 'Yes' : 'No'}`),
          React.createElement('div', {
            key: 'direct-mode',
            style: { 
              color: 'rgba(255, 255, 255, 0.6)', 
              fontSize: '0.8rem'
            }
          }, `Direct Mode: ${healthData.queue.direct_mode ? 'Yes' : 'No'}`)
        ])
      ]) : null,

      // =============================================================================
      // AVAILABLE AI SERVICES
      // =============================================================================
      availableServices && availableServices.length > 0 ? React.createElement('div', {
        key: 'services-section',
        style: {
          background: 'rgba(74, 144, 226, 0.05)',
          border: '1px solid rgba(74, 144, 226, 0.15)',
          borderRadius: '8px',
          padding: '12px',
          marginTop: '12px'
        }
      }, [
        React.createElement('div', {
          key: 'services-title',
          style: {
            color: 'rgba(74, 144, 226, 0.9)',
            fontWeight: '600',
            fontSize: '0.9rem',
            marginBottom: '8px',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }
        }, [
          React.createElement('span', { key: 'ai-icon' }, '🤖'),
          'Available AI Services'
        ]),
        
        // Services List
        ...availableServices.map((service, index) => 
          React.createElement('div', {
            key: `service-${index}`,
            style: { 
              display: 'flex', 
              alignItems: 'center', 
              gap: '8px', 
              marginBottom: index < availableServices.length - 1 ? '6px' : '0',
              padding: '4px 0'
            }
          }, [
            React.createElement('span', {
              key: 'service-icon',
              style: { 
                color: '#4ade80',
                fontWeight: 'bold'
              }
            }, '✓'),
            React.createElement('span', {
              key: 'service-name',
              style: { 
                color: 'rgba(255, 255, 255, 0.9)',
                fontWeight: '500',
                fontSize: '0.85rem'
              }
            }, service.name),
            React.createElement('span', {
              key: 'service-desc',
              style: { 
                color: 'rgba(255, 255, 255, 0.6)',
                fontSize: '0.8rem'
              }
            }, `- ${service.description}`),
            React.createElement('span', {
              key: 'service-port',
              style: { 
                color: 'rgba(74, 144, 226, 0.7)',
                fontSize: '0.75rem',
                fontFamily: 'monospace',
                marginLeft: 'auto'
              }
            }, `:${service.port}`)
          ])
        )
      ]) : null
    ]);
  };

  // =============================================================================
  // IMPORT EXTERNAL VISAGE COMPONENT
  // =============================================================================
  // VisageImageResults is now an external component that handles image URL resolution internally


  // AI Overhaul Settings Page Component
  const AIOverhaulSettingsPage = () => {
    // =============================================================================
    // STATE MANAGEMENT
    // =============================================================================
    const [activeTab, setActiveTab] = React.useState('overview');
    const [settings, setSettings] = React.useState({
      stashAIServer: 'localhost',
      port: '9998'
    });

    const [healthStatus, setHealthStatus] = React.useState(null);
    const [isTestingConnection, setIsTestingConnection] = React.useState(false);
    const [availableServices, setAvailableServices] = React.useState([]);
    
    // History tab state - now showing jobs instead of tasks
    const [historyJobs, setHistoryJobs] = React.useState([]);
    const [isLoadingHistory, setIsLoadingHistory] = React.useState(false);
    const [historyFilter, setHistoryFilter] = React.useState('all');
    const [expandedJobs, setExpandedJobs] = React.useState(new Set());
    const [selectedTask, setSelectedTask] = React.useState(null);
    
    // Overlay state for results viewing
    const [showOverlay, setShowOverlay] = React.useState(false);
    const [overlayData, setOverlayData] = React.useState(null);

    // =============================================================================
    // UTILITY FUNCTIONS
    // =============================================================================
    const handleInputChange = (key: string, value: any) => {
      setSettings(prev => ({ ...prev, [key]: value }));
    };

    // Service discovery - test common AI service endpoints
    const detectAvailableServices = async (baseUrl: string) => {
      const services = [
        { name: 'Visage', endpoint: '/health', port: '9997', description: 'Face Recognition' },
        { name: 'Content Analysis', endpoint: '/health', port: '9999', description: 'Content Classification' },
        { name: 'Scene Analysis', endpoint: '/health', port: '9996', description: 'Scene Detection' }
      ];

      const availableServices = [];
      
      for (const service of services) {
        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 3000);
          
          const testUrl = `http://${settings.stashAIServer}:${service.port}${service.endpoint}`;
          const response = await fetch(testUrl, {
            method: 'GET',
            signal: controller.signal,
            headers: { 'Content-Type': 'application/json' }
          });
          
          clearTimeout(timeoutId);
          
          if (response.ok) {
            const serviceHealth = await response.json();
            availableServices.push({
              ...service,
              status: 'available',
              health: serviceHealth
            });
          }
        } catch (error) {
          // Service not available - skip silently
          console.debug(`${service.name} service not available:`, error.message);
        }
      }
      
      return availableServices;
    };

    const testConnection = async () => {
      if (!settings.stashAIServer || !settings.port) return;

      setIsTestingConnection(true);
      setHealthStatus(null);
      setAvailableServices([]);

      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);
        
        const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/health`, {
          method: 'GET',
          signal: controller.signal,
          headers: {
            'Content-Type': 'application/json',
          }
        });
        
        clearTimeout(timeoutId);

        if (response.ok) {
          const data = await response.json();
          setHealthStatus(data);
          console.log('StashAI Server Health:', data);

          // Detect available AI services
          console.log('Detecting available AI services...');
          const services = await detectAvailableServices(`http://${settings.stashAIServer}`);
          setAvailableServices(services);
          console.log('Available AI services:', services);
        } else {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
      } catch (error: any) {
        console.error('StashAI Server health check failed:', error);
        setHealthStatus({ error: error.message || 'Connection failed' });
        setAvailableServices([]);
      } finally {
        setIsTestingConnection(false);
      }
    };

    const handleUpdate = () => {
      // Save settings logic here
      localStorage.setItem('ai_overhaul_settings', JSON.stringify(settings));
      console.log('Settings saved:', settings);
      alert('Settings saved successfully!');
    };

    // =============================================================================
    // HISTORY TAB FUNCTIONS - Jobs with Tasks Hierarchy
    // =============================================================================
    const fetchHistoryJobs = async () => {
      if (!settings?.stashAIServer || !settings?.port) {
        console.warn('Missing server settings for history fetch');
        return;
      }
      
      setIsLoadingHistory(true);
      try {
        // Step 1: Fetch Jobs
        let jobsUrl = `http://${settings.stashAIServer}:${settings.port}/api/queue/jobs`;
        const jobsParams = new URLSearchParams();
        
        // Add status filter for jobs (completed, failed, partial)
        if (historyFilter !== 'all') {
          // Map task status filters to job status filters
          const statusMapping = {
            'finished': 'completed',
            'failed': 'failed'
          };
          const jobStatus = statusMapping[historyFilter] || historyFilter;
          jobsParams.append('status', jobStatus);
        }
        
        // Add limit for jobs
        jobsParams.append('limit', '50');
        
        const jobsFullUrl = `${jobsUrl}?${jobsParams.toString()}`;
        console.log('Fetching jobs from:', jobsFullUrl);
        
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 15000); // Longer timeout for jobs+tasks
        
        const jobsResponse = await fetch(jobsFullUrl, {
          method: 'GET',
          signal: controller.signal,
          headers: { 'Content-Type': 'application/json' }
        });
        
        if (jobsResponse.ok) {
          const jobsData = await jobsResponse.json();
          console.log('Jobs response:', jobsData);
          const jobs = jobsData.jobs || jobsData || [];
          
          // Step 2: For each job, fetch its detailed information including tasks
          const jobsWithTasks = [];
          
          for (const job of jobs) {
            try {
              // Fetch detailed job info with tasks
              const jobDetailUrl = `http://${settings.stashAIServer}:${settings.port}/api/queue/job/${job.job_id}`;
              console.log('Fetching job details for:', job.job_id);
              
              const jobDetailResponse = await fetch(jobDetailUrl, {
                method: 'GET',
                signal: controller.signal,
                headers: { 'Content-Type': 'application/json' }
              });
              
              if (jobDetailResponse.ok) {
                const jobDetail = await jobDetailResponse.json();
                console.log('Job detail response for', job.job_id, ':', jobDetail);
                jobsWithTasks.push(jobDetail);
              } else {
                console.warn('Failed to fetch details for job', job.job_id, '- using basic info');
                // Fallback to basic job info if detailed fetch fails
                jobsWithTasks.push({...job, tasks: []});
              }
            } catch (jobError) {
              console.warn('Error fetching job details for', job.job_id, ':', jobError);
              // Add job with empty tasks array as fallback
              jobsWithTasks.push({...job, tasks: []});
            }
          }
          
          console.log('Final jobs with tasks:', jobsWithTasks);
          setHistoryJobs(jobsWithTasks);
          
        } else {
          const errorText = await jobsResponse.text();
          console.error('Failed to fetch jobs:', jobsResponse.status, jobsResponse.statusText, errorText);
          throw new Error(`HTTP ${jobsResponse.status}: ${jobsResponse.statusText}`);
        }
        
        clearTimeout(timeoutId);
        
      } catch (error) {
        console.error('Failed to fetch history jobs:', error);
        // Show user-friendly error
        if (error.name === 'AbortError') {
          alert('Request timed out. Please check your server connection.');
        } else if (error.message.includes('Failed to fetch')) {
          alert('Cannot connect to AI server. Please check your settings and ensure the server is running.');
        } else {
          alert(`Error loading job history: ${error.message}`);
        }
      } finally {
        setIsLoadingHistory(false);
      }
    };

    const toggleJobExpansion = (jobId) => {
      setExpandedJobs(prev => {
        const newSet = new Set(prev);
        if (newSet.has(jobId)) {
          newSet.delete(jobId);
        } else {
          newSet.add(jobId);
        }
        return newSet;
      });
    };

    const openTaskContent = async (task) => {
      if (!task.input_data) {
        alert('No content data available for this task');
        return;
      }

      try {
        // Extract content information from input_data
        const inputData = task.input_data;
        let contentId = null;
        let contentType = null;

        // Determine content type and ID from input data
        if (inputData.image_id) {
          contentId = inputData.image_id;
          contentType = 'image';
        } else if (inputData.scene_id) {
          contentId = inputData.scene_id;
          contentType = 'scene';
        } else if (inputData.gallery_id) {
          contentId = inputData.gallery_id;
          contentType = 'gallery';
        } else if (inputData.performer_id) {
          contentId = inputData.performer_id;
          contentType = 'performer';
        } else {
          // Try to parse from other common patterns
          const possibleId = inputData.id || inputData.entity_id || inputData.target_id;
          if (possibleId) {
            contentId = possibleId;
            contentType = 'image'; // default to image
          }
        }

        if (!contentId) {
          alert('Could not determine content ID from task data');
          return;
        }

        // Navigate to the content
        const routes = {
          image: `/images/${contentId}`,
          scene: `/scenes/${contentId}`,
          gallery: `/galleries/${contentId}`,
          performer: `/performers/${contentId}`
        };

        const targetRoute = routes[contentType];
        if (targetRoute) {
          console.log(`Opening ${contentType} ${contentId}:`, targetRoute);
          // Use React Router navigation
          window.location.hash = `#${targetRoute}`;
          window.location.reload();
        } else {
          alert(`Unknown content type: ${contentType}`);
        }
      } catch (error) {
        console.error('Error opening task content:', error);
        alert(`Failed to open content: ${error.message}`);
      }
    };

    const viewTaskResults = async (task) => {
      if (!task.output_json) {
        alert('No results available for this task');
        return;
      }
      
      // Set selected task for detailed view
      setSelectedTask(task);
      
      // If it's a visage task with results, show the overlay
      if (task.adapter_name === 'visage' && task.output_json) {
        console.log('Visage results:', task.output_json);
        
        try {
          // Set up overlay data with task object (VisageImageResults will handle image URL resolution)
          const overlayInfo = {
            task: task,
            visageResults: task.output_json,
            taskId: task.task_id,
            taskType: task.task_type
          };
          
          console.log('Setting up overlay with:', overlayInfo);
          setOverlayData(overlayInfo);
          setShowOverlay(true);
          
        } catch (error) {
          console.error('Error setting up results overlay:', error);
          alert(`Error displaying results: ${error.message}`);
        }
      } else {
        // For non-visage tasks, show a simple JSON view
        alert(`Task results:\n${JSON.stringify(task.output_json, null, 2)}`);
      }
    };

    // Load settings from localStorage on component mount
    React.useEffect(() => {
      const saved = localStorage.getItem('ai_overhaul_settings');
      if (saved) {
        try {
          const parsedSettings = JSON.parse(saved);
          setSettings(prev => ({ ...prev, ...parsedSettings }));
          console.log('Loaded AI Overhaul settings:', parsedSettings);
        } catch (e) {
          console.warn('Failed to load AI Overhaul settings:', e);
        }
      }
    }, []);

    // Load history when switching to history tab
    React.useEffect(() => {
      if (activeTab === 'history' && settings?.stashAIServer && settings?.port) {
        fetchHistoryJobs();
      }
    }, [activeTab, historyFilter, settings?.stashAIServer, settings?.port]);

    // =============================================================================
    // RENDER COMPONENT
    // =============================================================================
    return React.createElement('div', {
      className: 'container-fluid ai-overhaul-container'
    }, [
      // =============================================================================
      // PAGE HEADER
      // =============================================================================
      React.createElement('div', {
        key: 'header',
        className: 'row'
      }, React.createElement('div', {
        className: 'col-12'
      }, [
        React.createElement('h1', {
          key: 'title',
          className: 'mb-4 ai-overhaul-title'
        }, 'AI Overhaul Settings'),
        
        // Tab Navigation
        React.createElement('div', {
          key: 'tab-nav',
          className: 'mb-4'
        }, React.createElement('ul', {
          className: 'nav nav-tabs'
        }, [
          React.createElement('li', {
            key: 'overview-tab',
            className: 'nav-item'
          }, React.createElement('a', {
            className: `nav-link ${activeTab === 'overview' ? 'active' : ''}`,
            href: '#',
            onClick: (e) => { e.preventDefault(); setActiveTab('overview'); }
          }, 'Overview')),
          React.createElement('li', {
            key: 'history-tab', 
            className: 'nav-item'
          }, React.createElement('a', {
            className: `nav-link ${activeTab === 'history' ? 'active' : ''}`,
            href: '#',
            onClick: (e) => { e.preventDefault(); setActiveTab('history'); }
          }, 'Task History'))
        ]))
      ])),

      // =============================================================================
      // TAB CONTENT
      // =============================================================================
      
      // Overview Tab Content
      activeTab === 'overview' && React.createElement('div', {
        key: 'overview-content',
        className: 'row'
      }, React.createElement('div', {
        className: 'col-md-6'
      }, React.createElement('div', {
        className: 'ai-overhaul-card'
      }, [
        // Card Header
        React.createElement('div', {
          key: 'card-header',
          className: 'ai-overhaul-card-header'
        }, React.createElement('h5', {
          className: 'ai-overhaul-card-title'
        }, 'Endpoint Configuration')),

        // Card Body
        React.createElement('div', {
          key: 'card-body',
          className: 'card-body'
        }, [
          // Single Line Input Row
          React.createElement('div', {
            key: 'input-row',
            className: 'row g-2 mb-3'
          }, [
            // Server Input Column
            React.createElement('div', {
              key: 'server-col',
              className: 'col-md-4'
            }, React.createElement('input', {
              type: 'text',
              className: 'form-control ai-overhaul-input',
              value: settings.stashAIServer,
              onChange: (e: any) => handleInputChange('stashAIServer', e.target.value),
              placeholder: 'Server (localhost or IP)'
            })),

            // Port Input Column
            React.createElement('div', {
              key: 'port-col',
              className: 'col-md-2'
            }, React.createElement('input', {
              type: 'text',
              className: 'form-control ai-overhaul-input',
              value: settings.port,
              onChange: (e: any) => handleInputChange('port', e.target.value),
              placeholder: 'Port'
            })),

            // Test Button Column
            React.createElement('div', {
              key: 'test-col',
              className: 'col-md-3'
            }, React.createElement(Button, {
              variant: 'outline-primary',
              onClick: testConnection,
              disabled: isTestingConnection,
              className: 'w-100 ai-overhaul-btn-secondary'
            }, isTestingConnection ? 'Testing...' : 'Test')),

            // Save Button Column
            React.createElement('div', {
              key: 'save-col',
              className: 'col-md-3'
            }, React.createElement(Button, {
              variant: 'primary',
              onClick: handleUpdate,
              className: 'w-100 ai-overhaul-btn'
            }, 'Save'))
          ]),

          // Endpoint Preview (Minimal)
          React.createElement('div', {
            key: 'endpoint-preview',
            className: 'mb-3'
          }, React.createElement('div', {
            className: 'ai-overhaul-endpoint-preview'
          }, `→ http://${settings.stashAIServer}:${settings.port}/health`)),

          // Health Status (Pretty Component)
          healthStatus ? (healthStatus.error ? 
            React.createElement('div', {
              key: 'error-status',
              className: 'ai-overhaul-status-error',
              style: { fontSize: '0.9rem', fontWeight: '500' }
            }, `✗ ${healthStatus.error}`) :
            React.createElement(HealthEndpoint, {
              key: 'health-component',
              healthData: healthStatus,
              availableServices: availableServices
            })
          ) : null
        ])
      ]))),
      
      // History Tab Content
      activeTab === 'history' && React.createElement('div', {
        key: 'history-content',
        className: 'row'
      }, React.createElement('div', {
        className: 'col-12'
      }, React.createElement('div', {
        className: 'ai-overhaul-card'
      }, [
        // Card Header
        React.createElement('div', {
          key: 'history-header',
          className: 'ai-overhaul-card-header'
        }, [
          React.createElement('h5', {
            key: 'history-title',
            className: 'ai-overhaul-card-title'
          }, 'Task History'),
          React.createElement('div', {
            key: 'history-controls',
            style: { display: 'flex', gap: '8px' }
          }, [
            React.createElement('select', {
              key: 'filter-select',
              className: 'form-select form-select-sm',
              value: historyFilter,
              onChange: (e) => setHistoryFilter(e.target.value),
              style: { width: 'auto' }
            }, [
              React.createElement('option', { key: 'all', value: 'all' }, 'All'),
              React.createElement('option', { key: 'completed', value: 'completed' }, 'Completed'),
              React.createElement('option', { key: 'failed', value: 'failed' }, 'Failed'),
              React.createElement('option', { key: 'partial', value: 'partial' }, 'Partial'),
              React.createElement('option', { key: 'running', value: 'running' }, 'Running')
            ]),
            React.createElement(Button, {
              key: 'refresh-btn',
              variant: 'outline-primary',
              size: 'sm',
              onClick: fetchHistoryJobs,
              disabled: isLoadingHistory
            }, isLoadingHistory ? 'Loading...' : 'Refresh')
          ])
        ]),

        // Card Body
        React.createElement('div', {
          key: 'history-body',
          className: 'card-body'
        }, [
          isLoadingHistory ? React.createElement('div', {
            key: 'loading',
            className: 'text-center py-4'
          }, [
            React.createElement('div', {
              key: 'spinner',
              className: 'spinner-border text-primary',
              role: 'status'
            }, React.createElement('span', {
              key: 'loading-text',
              className: 'visually-hidden'
            }, 'Loading...')),
            React.createElement('p', {
              key: 'loading-msg',
              className: 'mt-2'
            }, 'Loading task history...')
          ]) : historyJobs.length === 0 ? React.createElement('div', {
            key: 'no-tasks',
            className: 'text-center py-4 text-muted'
          }, [
            React.createElement('i', {
              key: 'empty-icon',
              className: 'fas fa-history',
              style: { fontSize: '48px', marginBottom: '16px', opacity: 0.5 }
            }),
            React.createElement('p', {
              key: 'empty-text'
            }, 'No completed jobs found'),
            React.createElement('small', {
              key: 'empty-desc'
            }, 'Completed AI jobs will appear here')
          ]) : React.createElement('div', {
            key: 'tasks-table',
            className: 'table-responsive'
          }, React.createElement('table', {
            className: 'table table-hover'
          }, [
            React.createElement('thead', {
              key: 'table-head'
            }, React.createElement('tr', null, [
              React.createElement('th', { key: 'expand', width: '30' }, ''), // Expand/collapse
              React.createElement('th', { key: 'job-name' }, 'Job Name'),
              React.createElement('th', { key: 'entity' }, 'Entity'),
              React.createElement('th', { key: 'service' }, 'Service'),
              React.createElement('th', { key: 'status' }, 'Status'),
              React.createElement('th', { key: 'progress' }, 'Progress'),
              React.createElement('th', { key: 'created' }, 'Created'),
              React.createElement('th', { key: 'actions' }, 'Actions')
            ])),
            React.createElement('tbody', {
              key: 'table-body'
            }, historyJobs.flatMap((job, jobIndex) => {
              const isExpanded = expandedJobs.has(job.job_id);
              const jobRows = [];
              
              // Job main row
              jobRows.push(React.createElement('tr', {
                key: `job-${job.job_id || jobIndex}`,
                style: { 
                  cursor: 'pointer',
                  backgroundColor: isExpanded ? 'rgba(74, 144, 226, 0.05)' : 'transparent'
                },
                onClick: () => toggleJobExpansion(job.job_id)
              }, [
                // Expand/collapse button
                React.createElement('td', {
                  key: 'expand-cell'
                }, React.createElement('i', {
                  className: `fas fa-chevron-${isExpanded ? 'down' : 'right'}`,
                  style: { fontSize: '0.8rem', color: '#666' }
                })),
                
                // Job Name
                React.createElement('td', {
                  key: 'job-name-cell'
                }, React.createElement('div', null, [
                  React.createElement('strong', {
                    key: 'job-name',
                    style: { color: 'white' }
                  }, job.job_name || 'Unnamed Job'),
                  React.createElement('br', { key: 'br' }),
                  React.createElement('small', {
                    key: 'job-id',
                    className: 'text-muted',
                    style: { fontFamily: 'monospace' }
                  }, job.job_id ? job.job_id.substring(0, 12) + '...' : 'Unknown')
                ])),
                
                // Entity (derived from job config or first task)
                React.createElement('td', {
                  key: 'entity-cell'
                }, (() => {
                  // Try to get entity info from job config first
                  const jobConfig = job.job_config || {};
                  let entityType = jobConfig.entity_type;
                  let entityId = jobConfig.entity_id;
                  
                  // Fallback: get from first task if available
                  if ((!entityType || !entityId) && job.tasks && job.tasks.length > 0) {
                    const firstTask = job.tasks[0];
                    const inputData = firstTask.input_data || {};
                    entityType = inputData.entity_type;
                    entityId = inputData.entity_id;
                    
                    // Further fallback: derive from legacy fields
                    if (!entityType || !entityId) {
                      if (inputData.image_id) {
                        entityType = 'image';
                        entityId = inputData.image_id;
                      } else if (inputData.scene_id) {
                        entityType = 'scene';
                        entityId = inputData.scene_id;
                      } else if (inputData.gallery_id) {
                        entityType = 'gallery';
                        entityId = inputData.gallery_id;
                      }
                    }
                  }
                  
                  if (entityType && entityId) {
                    const displayType = entityType.charAt(0).toUpperCase() + entityType.slice(1);
                    return React.createElement('span', {
                      className: 'badge bg-light text-dark',
                      style: { 
                        fontSize: '0.75rem',
                        fontFamily: 'monospace'
                      }
                    }, `${displayType} | ${entityId}`);
                  } else {
                    return React.createElement('span', {
                      className: 'text-muted small'
                    }, job.total_tasks > 1 ? 'Batch Job' : 'Unknown entity');
                  }
                })()),
                
                // Service
                React.createElement('td', {
                  key: 'service-cell'
                }, React.createElement('span', {
                  className: `badge ${job.adapter_name === 'visage' ? 'bg-info' : 'bg-secondary'}`
                }, job.adapter_name || 'unknown')),
                
                // Status
                React.createElement('td', {
                  key: 'status-cell'
                }, React.createElement('span', {
                  className: `badge ${
                    job.status === 'completed' ? 'bg-success' :
                    job.status === 'failed' ? 'bg-danger' :
                    job.status === 'partial' ? 'bg-warning' :
                    job.status === 'running' ? 'bg-primary' : 'bg-secondary'
                  }`
                }, job.status || 'unknown')),
                
                // Progress
                React.createElement('td', {
                  key: 'progress-cell',
                  className: 'small'
                }, `${job.completed_tasks || 0}/${job.total_tasks || 0} tasks`),
                
                // Created
                React.createElement('td', {
                  key: 'created-cell',
                  className: 'small'
                }, job.created_at ? new Date(job.created_at).toLocaleString() : 'Unknown'),
                
                // Actions - Job level actions could include viewing aggregate results
                React.createElement('td', {
                  key: 'actions-cell'
                }, React.createElement('div', {
                  style: { display: 'flex', gap: '4px' }
                }, [
                  React.createElement('small', {
                    key: 'expand-hint',
                    className: 'text-muted'
                  }, 'Click to expand tasks')
                ]))
              ]));
              
              // Task rows (only if expanded)
              if (isExpanded && job.tasks && job.tasks.length > 0) {
                job.tasks.forEach((task, taskIndex) => {
                  jobRows.push(React.createElement('tr', {
                    key: `task-${job.job_id}-${task.task_id || taskIndex}`,
                    style: { 
                      backgroundColor: 'rgba(255, 255, 255, 0.02)',
                      borderLeft: '3px solid rgba(74, 144, 226, 0.3)'
                    }
                  }, [
                    // Empty expand cell
                    React.createElement('td', { key: 'empty-expand' }, ''),
                    
                    // Task details indented
                    React.createElement('td', {
                      key: 'task-info-cell',
                      colSpan: 2
                    }, React.createElement('div', {
                      style: { paddingLeft: '20px' }
                    }, [
                      React.createElement('small', {
                        key: 'task-label',
                        className: 'text-muted'
                      }, 'Task: '),
                      React.createElement('code', {
                        key: 'task-id',
                        className: 'small'
                      }, task.task_id ? task.task_id.substring(0, 8) + '...' : 'Unknown'),
                      React.createElement('br', { key: 'task-br' }),
                      React.createElement('small', {
                        key: 'task-type',
                        className: 'text-muted'
                      }, task.task_type || 'Unknown type')
                    ])),
                    
                    // Task Service
                    React.createElement('td', {
                      key: 'task-service-cell'
                    }, React.createElement('span', {
                      className: `badge badge-sm ${task.adapter_name === 'visage' ? 'bg-info' : 'bg-secondary'}`,
                      style: { fontSize: '0.7rem' }
                    }, task.adapter_name || 'unknown')),
                    
                    // Task Status
                    React.createElement('td', {
                      key: 'task-status-cell'
                    }, React.createElement('span', {
                      className: `badge badge-sm ${
                        task.status === 'finished' ? 'bg-success' :
                        task.status === 'failed' ? 'bg-danger' :
                        task.status === 'running' ? 'bg-warning' : 'bg-secondary'
                      }`,
                      style: { fontSize: '0.7rem' }
                    }, task.status || 'unknown')),
                    
                    // Task Processing Time
                    React.createElement('td', {
                      key: 'task-time-cell',
                      className: 'small'
                    }, task.processing_time_ms ? `${Math.round(task.processing_time_ms)}ms` : '-'),
                    
                    // Task Created
                    React.createElement('td', {
                      key: 'task-created-cell',
                      className: 'small'
                    }, task.created_at ? new Date(task.created_at).toLocaleString() : '-'),
                    
                    // Task Actions
                    React.createElement('td', {
                      key: 'task-actions-cell'
                    }, React.createElement('div', {
                      style: { display: 'flex', gap: '4px' }
                    }, [
                      task.input_data && React.createElement(Button, {
                        key: 'task-open-btn',
                        variant: 'outline-primary',
                        size: 'sm',
                        onClick: (e) => { e.stopPropagation(); openTaskContent(task); },
                        title: 'Open content'
                      }, React.createElement('i', { className: 'fas fa-external-link-alt' })),
                      task.output_json && React.createElement(Button, {
                        key: 'task-results-btn',
                        variant: 'outline-success',
                        size: 'sm',
                        onClick: (e) => { e.stopPropagation(); viewTaskResults(task); },
                        title: 'View results'
                      }, React.createElement('i', { className: 'fas fa-eye' }))
                    ]))
                  ]));
                });
              }
              
              return jobRows;
            }))
          ]))
        ])
      ]))),
      
      // =============================================================================  
      // OVERLAY COMPONENTS
      // =============================================================================
      showOverlay && overlayData && VisageImageResults ? React.createElement(VisageImageResults, {
        key: 'visage-overlay',
        task: overlayData.task,
        visageResults: overlayData.visageResults,
        onClose: () => {
          setShowOverlay(false);
          setOverlayData(null);
        },
        React: React
      }) : showOverlay && overlayData ? React.createElement('div', {
        key: 'loading-overlay',
        style: {
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.9)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999
        },
        onClick: () => {
          setShowOverlay(false);
          setOverlayData(null);
        }
      }, React.createElement('div', {
        style: {
          color: 'white',
          textAlign: 'center'
        }
      }, [
        React.createElement('div', { key: 'loading-msg' }, 'VisageImageResults component not loaded'),
        React.createElement('div', { key: 'error-msg', style: { fontSize: '0.9rem', opacity: 0.7, marginTop: '8px' } }, 'Click to close')
      ])) : null
    ]);
  };

  // Register the AI Overhaul Settings page route
  PluginApi.register.route("/plugin/ai-overhaul", AIOverhaulSettingsPage);
  
  console.log('AI Overhaul Settings route registered at:', "/plugin/ai-overhaul");

  // Add AI Overhaul Settings button to Stash Settings Tools section
  PluginApi.patch.before("SettingsToolsSection", function (props: any) {
    const { Setting } = PluginApi.components;

    return [
      {
        children: React.createElement(React.Fragment, null,
          props.children,
          React.createElement(Setting, {
            heading: React.createElement(Link, { to: "/plugin/ai-overhaul" },
              React.createElement(Button, { variant: 'primary' },
                React.createElement('i', { className: 'fas fa-brain', style: { marginRight: '8px' } }),
                'AI Overhaul Settings'
              )
            )
          })
        )
      }
    ];
  });

})();