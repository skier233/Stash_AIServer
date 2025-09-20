// =============================================================================
// New Responsive AI Button Component
// =============================================================================

// ActionManager will be available globally after AIActions loads

interface PageContext {
  page: 'scenes' | 'galleries' | 'images' | 'groups' | 'performers' | 'home' | 'unknown';
  entityId: string | null;
  isDetailView: boolean;
}

interface IAIButtonProps {
  context?: PageContext;
}

// =============================================================================
// PAGE CONTEXT DETECTION
// =============================================================================
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
  const React = (window as any).PluginApi.React;
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

// =============================================================================
// SERVICE DISCOVERY
// =============================================================================
interface AIService {
  name: string;
  port?: string;
  description: string;
  action: string;
  icon: string;
  supportedTypes: string[];
}

const discoverServicesAndReturn = async (settings: any): Promise<AIService[]> => {
  if (!settings?.stashAIServer || !settings?.port) {
    console.warn('🚀 New AI Button: Settings not available for service discovery');
    return [];
  }

  const services = [
    { 
      name: 'Visage', 
      description: 'Face Recognition',
      action: 'analyze-faces',
      icon: '👤',
      supportedTypes: ['image', 'scene']
    },
    { 
      name: 'Content Analysis', 
      description: 'Content Classification',
      action: 'analyze-content',
      icon: '🔍',
      supportedTypes: ['image', 'scene']
    },
    { 
      name: 'Scene Analysis', 
      description: 'Scene Detection',
      action: 'analyze-scene',
      icon: '🎬',
      supportedTypes: ['scene']
    },
    { 
      name: 'Gallery Batch Analysis', 
      description: 'Analyze all images in gallery',
      action: 'analyze-gallery-batch',
      icon: '🖼️',
      supportedTypes: ['galleries']
    }
  ];

  try {
    // Shorter timeout for health checks to prevent UI blocking
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      console.debug('🚀 New AI Button: StashAI Server health check timeout after 2s');
      controller.abort();
    }, 2000); // Reduced from 3s to 2s
    
    const healthUrl = `http://${settings.stashAIServer}:${settings.port}/health`;
    console.debug(`🚀 New AI Button: Checking StashAI Server health at ${healthUrl}`);
    
    const healthResponse = await fetch(healthUrl, {
      signal: controller.signal,
      headers: {
        'Cache-Control': 'no-cache',
        'Connection': 'close' // Prevent keep-alive connections that might hang
      }
    });
    
    clearTimeout(timeoutId);
    
    if (healthResponse.ok) {
      console.debug(`✅ StashAI Server available at ${settings.stashAIServer}:${settings.port}`);
      // If server is healthy, return all services
      return services.map(service => ({ ...service, port: settings.port }));
    } else {
      console.debug(`❌ StashAI Server unhealthy (${healthResponse.status}) at ${settings.stashAIServer}:${settings.port}`);
      return [];
    }
  } catch (error) {
    if ((error as Error).name === 'AbortError') {
      console.debug(`⏰ StashAI Server timeout at ${settings.stashAIServer}:${settings.port}`);
    } else {
      console.debug(`❌ StashAI Server unavailable at ${settings.stashAIServer}:${settings.port}:`, (error as Error).message);
    }
    return [];
  }
};

const NewAIButton: React.FC<IAIButtonProps> = ({ context: propContext }) => {
  const React = (window as any).PluginApi.React;
  
  // Use prop context or detect current page context
  const detectedContext = usePageContext();
  const context = propContext || detectedContext;
  
  // Debug logging
  React.useEffect(() => {
    console.log('🚀 New AI Button: Context detected:', context);
  }, [context]);
  
  // State management
  const [showDropdown, setShowDropdown] = React.useState(false);
  const [showJobSuite, setShowJobSuite] = React.useState(false);
  const [isProcessing, setIsProcessing] = React.useState(false);
  const [activeTask, setActiveTask] = React.useState(null);
  const [availableServices, setAvailableServices] = React.useState([]);
  const [isDiscoveringServices, setIsDiscoveringServices] = React.useState(false);
  const [settings, setSettings] = React.useState(null);
  const [suiteJobs, setSuiteJobs] = React.useState([]);
  const [lastJobsUpdate, setLastJobsUpdate] = React.useState(0);
  
  // Add refs to prevent duplicate operations
  const isServiceDiscoveryInProgress = React.useRef(false);
  const jobFetchInProgress = React.useRef(false);

  // Load settings from localStorage
  React.useEffect(() => {
    const loadSettings = () => {
      const saved = localStorage.getItem('ai_overhaul_settings');
      if (saved) {
        try {
          const parsedSettings = JSON.parse(saved);
          setSettings(parsedSettings);
          console.log('🚀 New AI Button: Settings loaded:', parsedSettings);
        } catch (error) {
          console.error('Failed to parse AI Overhaul settings:', error);
        }
      } else {
        console.warn('🚀 New AI Button: No AI Overhaul settings found in localStorage');
      }
    };

    loadSettings();
  }, []);

  // Fetch latest jobs for suite display with debouncing
  const fetchLatestJobs = async (forceRefresh = false) => {
    if (!settings?.stashAIServer || !settings?.port) return [];
    
    // Prevent multiple concurrent requests
    if (jobFetchInProgress.current && !forceRefresh) {
      console.debug('🔍 Job fetch already in progress, skipping...');
      return suiteJobs;
    }
    
    // Rate limiting: don't fetch too frequently unless forced
    const timeSinceLastUpdate = Date.now() - lastJobsUpdate;
    if (timeSinceLastUpdate < 5000 && !forceRefresh) {
      console.debug('🔍 Rate limit: Skipping job fetch (too recent)');
      return suiteJobs;
    }
    
    jobFetchInProgress.current = true;
    
    try {
      // Shorter timeout to prevent blocking UI
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        console.debug('🔍 Job fetch timeout after 3 seconds');
        controller.abort();
      }, 3000); // Reduced from 5s to 3s
      
      console.debug('🔍 Fetching latest jobs for suite display...');
      const jobsResponse = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/queue/jobs?limit=3&include_completed=true&include_partial=true`, {
        signal: controller.signal,
        headers: {
          'Cache-Control': 'no-cache'
        }
      });
      
      clearTimeout(timeoutId);
      
      if (jobsResponse.ok) {
        const jobsData = await jobsResponse.json();
        console.debug('📊 Suite jobs fetched:', jobsData.jobs?.length || 0, 'jobs');
        setSuiteJobs(jobsData.jobs || []);
        setLastJobsUpdate(Date.now());
        return jobsData.jobs || [];
      }
    } catch (error) {
      if ((error as Error).name === 'AbortError') {
        console.debug('🔍 Job fetch was aborted due to timeout');
      } else {
        console.debug('Failed to fetch suite jobs (normal if server offline):', error);
      }
    } finally {
      jobFetchInProgress.current = false;
    }
    return [];
  };
  
  // Toggle suite view and fetch jobs when expanding
  const toggleJobSuite = async () => {
    if (!showJobSuite) {
      console.log('🔧 Expanding job suite, fetching latest jobs...');
      await fetchLatestJobs();
    }
    setShowJobSuite(!showJobSuite);
  };
  
  // Auto-refresh jobs periodically to keep status updated (only when job suite is open)
  React.useEffect(() => {
    let interval: any = null;
    
    if (settings?.stashAIServer && settings?.port && showJobSuite) {
      console.debug('🔄 Starting auto-refresh for job suite (15s interval)');
      
      // Initial fetch with slight delay to avoid conflicts
      const initialDelay = setTimeout(() => {
        fetchLatestJobs();
      }, 1000);
      
      // Set up interval for periodic updates
      interval = setInterval(() => {
        console.debug('🔄 Auto-refreshing jobs...');
        fetchLatestJobs();
      }, 15000); // Increased from 10s to 15s to reduce server load
      
      return () => {
        clearTimeout(initialDelay);
        if (interval) {
          console.debug('🔄 Stopping auto-refresh for job suite');
          clearInterval(interval);
        }
      };
    }
    
    return () => {
      if (interval) {
        console.debug('🔄 Cleaning up auto-refresh interval');
        clearInterval(interval);
      }
    };
  }, [settings?.stashAIServer, settings?.port, showJobSuite]); // More specific dependencies

  // =============================================================================
  // CONTEXTUAL ACTION FILTERING
  // =============================================================================
  const getContextType = () => {
    if (context.page === 'images' && context.isDetailView) return 'image';
    if (context.page === 'scenes' && context.isDetailView) return 'scene';  
    if (context.page === 'performers' && context.isDetailView) return 'performer';
    return context.page || 'unknown';
  };

  const getContextLabel = () => {
    const labels = {
      'scenes': 'Scenes',
      'galleries': 'Galleries', 
      'images': 'Images',
      'groups': 'Groups',
      'performers': 'Performers',
      'home': 'Home'
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
    
    console.log('🚀 New AI Button: Available actions:', {
      contextType,
      contextActions: contextActions.length,
      multiSelectActions: multiSelectActions.length,
      totalServices: availableServices.length
    });
    
    return [...contextActions, ...multiSelectActions];
  };

  // =============================================================================
  // MULTI-SELECT DETECTION AND ACTIONS
  // =============================================================================
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

      // Look for selected grid cards or list items
      const selectedCheckboxes = document.querySelectorAll('.grid-card .card-check:checked, .scene-card .card-check:checked, .performer-card .card-check:checked, .gallery-card .card-check:checked');
      
      if (selectedCheckboxes.length <= 1) {
        return null; // No multi-select
      }

      // Extract IDs from selected items
      const selectedItems: string[] = [];
      selectedCheckboxes.forEach((checkbox: Element) => {
        const card = checkbox.closest('.grid-card, .scene-card, .performer-card, .gallery-card');
        if (card) {
          const link = card.querySelector('a[href]') as HTMLAnchorElement;
          if (link) {
            const match = link.href.match(/\/(?:images|scenes|performers|galleries)\/(\d+)/);
            if (match) {
              selectedItems.push(match[1]);
            }
          }
        }
      });

      if (selectedItems.length <= 1) {
        return null;
      }

      console.log(`🎯 Multi-select detected: ${selectedItems.length} ${selectionType} selected`);

      return {
        selectionType,
        selectedItems,
        count: selectedItems.length
      };

    } catch (error) {
      console.error('Error detecting multi-select context:', error);
      return null;
    }
  };

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

  // =============================================================================
  // ACTION HANDLERS
  // =============================================================================
  const handleServiceAction = async (service: AIService) => {
    setShowDropdown(false);
    setIsProcessing(true);
    
    try {
      // Get ActionManager from global window
      const ActionManagerClass = (window as any).ActionManager;
      if (!ActionManagerClass) {
        throw new Error('ActionManager not available. Please ensure AIActions are loaded.');
      }

      const actionManager = new ActionManagerClass();
      
      // Execute the action using ActionManager
      const result = await actionManager.executeAction(
        service.action,
        service.name,
        context,
        settings
      );
      
      if (result.success) {
        alert(`✅ ${service.name} completed!\n\n${result.message}${result.taskId ? `\n\nTask ID: ${result.taskId}` : ''}`);
      } else {
        alert(`❌ ${service.name} failed:\n\n${result.message}`);
      }
      
    } catch (error) {
      console.error('Service action failed:', error);
      alert(`❌ Failed to execute ${service.name}:\n\n${error.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  // Button click handler with improved service discovery
  const handleButtonClick = async () => {
    // Check if settings are available
    if (!settings) {
      alert('AI Overhaul settings not found. Please configure your AI services in the settings page first.');
      return;
    }

    // Discover services if not already done, with duplicate prevention
    if (availableServices.length === 0 && !isDiscoveringServices && !isServiceDiscoveryInProgress.current) {
      isServiceDiscoveryInProgress.current = true;
      setIsDiscoveringServices(true);
      
      try {
        console.log('🚀 New AI Button: Discovering services...');
        const services = await discoverServicesAndReturn(settings);
        setAvailableServices(services);
        
        if (services.length === 0) {
          console.debug(`❌ No AI services available at ${settings.stashAIServer}:${settings.port}`);
          alert(`No AI services are currently available. Please check that your StashAI Server is running at ${settings.stashAIServer}:${settings.port}`);
          return;
        } else {
          console.debug(`✅ Discovered ${services.length} AI services`);
        }
      } catch (error) {
        console.error('Failed to discover services:', error);
        alert('Failed to discover AI services. Please check your network connection and try again.');
        return;
      } finally {
        setIsDiscoveringServices(false);
        isServiceDiscoveryInProgress.current = false;
      }
    }

    setShowDropdown(!showDropdown);
  };

  // Close dropdown when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const button = document.querySelector('.new-ai-button');
      const dropdown = document.querySelector('.new-ai-button .dropdown');
      const target = event.target as Node;
      
      // Don't close if clicking on button or dropdown content
      if (button && button.contains(target)) {
        return;
      }
      if (dropdown && dropdown.contains(target)) {
        return;
      }
      
      setShowDropdown(false);
      setShowJobSuite(false);
    };

    if (showDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [showDropdown]);

  // Don't show button if no settings
  if (!settings) {
    return null;
  }

  return React.createElement('div', {
    className: 'new-ai-button'
  }, [
    // Main Button
    React.createElement('button', {
      key: 'main-button',
      onClick: handleButtonClick,
      className: isProcessing ? 'processing' : '',
      title: isProcessing ? 'AI Processing...' : 'StashAI Services'
    }, [
      // Use SVGIcons utility for clean icon loading with fallback
      (window as any).AIOverhaulSVGIcons?.createInline(
        (window as any).AIOverhaulSVGIcons.StashAI,
        {
          width: '24',
          height: '24'
        }
      ) || React.createElement('div', {
        key: 'fallback-icon',
        style: {
          width: '24px',
          height: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: '16px',
          fontWeight: 'bold'
        }
      }, '🤖')
    ]),

    // Dropdown Menu with contextual services
    showDropdown ? React.createElement('div', {
      key: 'dropdown',
      className: 'dropdown'
    }, [
      React.createElement('div', {
        key: 'header',
        className: 'dropdown-header'
      }, [
        React.createElement('div', {
          key: 'title-row',
          style: {
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            cursor: 'pointer'
          },
          onClick: toggleJobSuite
        }, [
          React.createElement('h3', {
            key: 'title',
            style: { margin: 0 }
          }, 'StashAI Services'),
          React.createElement('span', {
            key: 'chevron',
            style: {
              fontSize: '16px',
              transition: 'transform 0.2s ease',
              transform: showJobSuite ? 'rotate(180deg)' : 'rotate(0deg)'
            }
          }, '▼')
        ]),
        React.createElement('p', {
          key: 'subtitle',
          style: { margin: '4px 0 0 0' }
        }, `${getContextLabel()} • ${context.isDetailView ? 'Detail View' : 'List View'}`)
      ]),
      
      React.createElement('div', {
        key: 'services',
        className: 'dropdown-content'
      }, (() => {
        const availableActions = getAvailableActionsForContext();
        
        if (isDiscoveringServices) {
          return React.createElement('div', {
            style: { textAlign: 'center', padding: '16px' }
          }, '🔍 Discovering services...');
        }
        
        if (availableActions.length === 0) {
          return React.createElement('div', {
            style: { textAlign: 'center', padding: '16px', color: '#9ca3af' }
          }, `No AI services available for ${getContextLabel().toLowerCase()}`);
        }
        
        return availableActions.map((service, index) => 
          React.createElement('div', {
            key: `service-${index}`,
            className: 'service-item',
            style: {
              display: 'flex',
              alignItems: 'center',
              padding: '12px 16px',
              cursor: 'pointer',
              borderRadius: '4px',
              transition: 'background-color 0.2s ease'
            },
            onClick: () => handleServiceAction(service),
            onMouseEnter: (e: any) => {
              e.target.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
            },
            onMouseLeave: (e: any) => {
              e.target.style.backgroundColor = 'transparent';
            }
          }, [
            React.createElement('span', {
              key: 'icon',
              style: { fontSize: '18px', marginRight: '12px' }
            }, service.icon),
            React.createElement('div', {
              key: 'info',
              style: { flex: 1 }
            }, [
              React.createElement('div', {
                key: 'name',
                style: { 
                  fontSize: '14px', 
                  fontWeight: '500',
                  color: '#f9fafb',
                  marginBottom: '2px'
                }
              }, service.name),
              React.createElement('div', {
                key: 'description',
                style: { 
                  fontSize: '12px', 
                  color: '#9ca3af'
                }
              }, service.description)
            ])
          ])
        );
      })()),
      
      // Job Suite Display (when expanded)
      showJobSuite ? React.createElement('div', {
        key: 'suite-section',
        style: {
          borderTop: '1px solid rgba(255, 255, 255, 0.1)',
          marginTop: '12px',
          paddingTop: '12px'
        }
      }, [
        React.createElement('div', {
          key: 'suite-header',
          style: {
            fontSize: '12px',
            fontWeight: '600',
            color: '#9ca3af',
            paddingBottom: '8px',
            textTransform: 'uppercase',
            letterSpacing: '0.5px'
          }
        }, `Recent Jobs (${suiteJobs.length})`),
        
        suiteJobs.length === 0 ? 
          React.createElement('div', {
            key: 'no-jobs',
            style: { 
              textAlign: 'center', 
              padding: '16px',
              color: '#6b7280',
              fontSize: '13px'
            }
          }, 'No jobs found') :
          suiteJobs.map((job, index) => {
            const isActive = job.status === 'running' || job.status === 'pending';
            const isCompleted = job.status === 'completed';
            const isFailed = job.status === 'failed';
            const isPartial = job.status === 'partial';
            
            // Calculate progress for active jobs
            const progressPercent = job.total_tasks > 0 ? 
              (job.completed_tasks / job.total_tasks) * 100 : 0;
            
            return React.createElement('div', {
              key: `suite-job-${index}`,
              style: {
                display: 'flex',
                alignItems: 'center',
                padding: '10px 12px',
                marginBottom: '6px',
                borderRadius: '6px',
                backgroundColor: isActive ? 'rgba(59, 130, 246, 0.1)' : 
                              isCompleted ? 'rgba(16, 185, 129, 0.1)' :
                              isFailed ? 'rgba(239, 68, 68, 0.1)' :
                              isPartial ? 'rgba(251, 191, 36, 0.1)' : 'transparent',
                border: `1px solid ${isActive ? 'rgba(59, 130, 246, 0.2)' : 
                              isCompleted ? 'rgba(16, 185, 129, 0.2)' :
                              isFailed ? 'rgba(239, 68, 68, 0.2)' :
                              isPartial ? 'rgba(251, 191, 36, 0.2)' : 'transparent'}`,
                transition: 'all 0.2s ease'
              }
            }, [
              React.createElement('div', {
                key: 'job-info',
                style: { flex: 1 }
              }, [
                React.createElement('div', {
                  key: 'job-header',
                  style: {
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '4px'
                  }
                }, [
                  React.createElement('div', {
                    key: 'job-title',
                    style: {
                      fontSize: '13px',
                      fontWeight: '500',
                      color: '#f9fafb'
                    }
                  }, [
                    React.createElement('span', {
                      key: 'status-icon',
                      style: { marginRight: '6px' }
                    }, isActive ? '⚡' : isCompleted ? '✅' : isFailed ? '❌' : isPartial ? '⚠️' : '⏸️'),
                    job.job_name || job.adapter_name || 'AI Processing'
                  ]),
                  React.createElement('div', {
                    key: 'job-status',
                    style: {
                      fontSize: '10px',
                      color: isActive ? '#3b82f6' : 
                            isCompleted ? '#10b981' :
                            isFailed ? '#ef4444' :
                            isPartial ? '#f59e0b' : '#6b7280',
                      textTransform: 'uppercase',
                      fontWeight: '600'
                    }
                  }, job.status)
                ]),
                
                // Progress bar for active jobs
                isActive && job.total_tasks > 0 ? React.createElement('div', {
                  key: 'progress-section',
                  style: { marginBottom: '6px' }
                }, [
                  React.createElement('div', {
                    key: 'progress-text',
                    style: {
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '10px',
                      color: '#d1d5db',
                      marginBottom: '2px'
                    }
                  }, [
                    React.createElement('span', { key: 'tasks' }, 
                      `${job.completed_tasks}/${job.total_tasks} tasks`),
                    React.createElement('span', { key: 'percent' }, 
                      `${Math.round(progressPercent)}%`)
                  ]),
                  React.createElement('div', {
                    key: 'progress-bar',
                    style: {
                      width: '100%',
                      height: '4px',
                      backgroundColor: 'rgba(255, 255, 255, 0.1)',
                      borderRadius: '2px',
                      overflow: 'hidden'
                    }
                  }, [
                    React.createElement('div', {
                      key: 'progress-fill',
                      style: {
                        width: `${progressPercent}%`,
                        height: '100%',
                        backgroundColor: '#3b82f6',
                        borderRadius: '2px',
                        transition: 'width 0.3s ease'
                      }
                    })
                  ])
                ]) : null,
                
                React.createElement('div', {
                  key: 'job-details',
                  style: {
                    fontSize: '10px',
                    color: '#9ca3af'
                  }
                }, [
                  `Job ID: ${job.job_id.substring(0, 8)}...`,
                  job.total_tasks > 0 ? ` • ${job.total_tasks} total` : '',
                  job.failed_tasks > 0 ? ` • ${job.failed_tasks} failed` : ''
                ].join(''))
              ]),
              
              // Action buttons (Cancel for active jobs, View for completed jobs)
              React.createElement('div', {
                key: 'action-buttons',
                style: { 
                  display: 'flex', 
                  gap: '4px',
                  marginLeft: '8px'
                }
              }, [
                // Cancel button for active jobs
                isActive ? React.createElement('button', {
                  key: 'cancel-job',
                  style: {
                    padding: '4px 8px',
                    fontSize: '10px',
                    fontWeight: '500',
                    color: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  },
                  onClick: async (e: any) => {
                    e.stopPropagation();
                    console.log('🚫 Cancelling job:', job);
                    
                    if (confirm(`Cancel job "${job.job_name || job.adapter_name || 'AI Processing'}"?`)) {
                      if (!settings?.stashAIServer || !settings?.port) {
                        alert('Server settings not available');
                        return;
                      }
                      
                      try {
                        // Try to use existing WebSocketManager first
                        const cancellation = (window as any).AIOverhaulWebSocketManager?.cancellation;
                        const wsManager = (window as any).AIOverhaulWebSocketManager;
                        
                        if (cancellation) {
                          console.log(`Cancelling job ${job.job_id} via WebSocketManager cancellation...`);
                          const result = await cancellation.cancelJob(job.job_id);
                          
                          if (result.success) {
                            alert(`Job cancelled successfully!\n\nCancelled ${result.cancelledTasks.length} tasks`);
                          } else {
                            alert(`Failed to cancel job:\n\n${result.message}`);
                          }
                        } else if (wsManager && wsManager.cancelJob) {
                          console.log(`Cancelling job ${job.job_id} via direct WebSocketManager...`);
                          const result = await wsManager.cancelJob(job.job_id);
                          
                          if (result.success) {
                            alert(`Job cancelled successfully!\n\nCancelled ${result.cancelledTasks.length} tasks`);
                          } else {
                            alert(`Failed to cancel job:\n\n${result.message}`);
                          }
                        } else {
                          // Direct API fallback - cancel individual tasks like WebSocketManager does
                          console.log(`WebSocketManager not available, using direct API for job ${job.job_id}...`);
                          
                          // Get job details to find tasks
                          const jobDetailUrl = `http://${settings.stashAIServer}:${settings.port}/api/queue/job/${job.job_id}`;
                          const jobResponse = await fetch(jobDetailUrl, {
                            method: 'GET',
                            headers: { 'Content-Type': 'application/json' }
                          });
                          
                          if (jobResponse.ok) {
                            const jobDetail = await jobResponse.json();
                            const tasks = jobDetail.tasks || [];
                            
                            if (tasks.length === 0) {
                              alert('No tasks found in this job or job already completed');
                            } else {
                              // Cancel each task individually
                              let cancelledCount = 0;
                              
                              for (const task of tasks) {
                                // Only cancel pending or running tasks
                                if (task.status === 'pending' || task.status === 'running') {
                                  try {
                                    const cancelTaskUrl = `http://${settings.stashAIServer}:${settings.port}/api/queue/cancel/${task.task_id}`;
                                    const cancelResponse = await fetch(cancelTaskUrl, {
                                      method: 'POST',
                                      headers: { 'Content-Type': 'application/json' }
                                    });
                                    
                                    if (cancelResponse.ok) {
                                      cancelledCount++;
                                      console.log(`Successfully cancelled task ${task.task_id}`);
                                    } else {
                                      console.warn(`Failed to cancel task ${task.task_id}: ${cancelResponse.status} ${cancelResponse.statusText}`);
                                    }
                                  } catch (taskError) {
                                    console.warn(`Failed to cancel task ${task.task_id}:`, taskError);
                                  }
                                }
                              }
                              
                              if (cancelledCount > 0) {
                                alert(`Job cancellation completed!\n\nCancelled ${cancelledCount} tasks`);
                                // Refresh job list to show updated status
                                setTimeout(() => fetchLatestJobs(), 1000);
                              } else {
                                alert('No tasks were available to cancel (job may already be completed)');
                              }
                            }
                          } else {
                            alert('Failed to fetch job details for cancellation');
                          }
                        }
                        
                        // Refresh the job list multiple times to catch status changes
                        const refreshDropdown = async (attempt = 1, maxAttempts = 3) => {
                          setTimeout(async () => {
                            const jobs = await fetchLatestJobs();
                            setSuiteJobs(jobs);
                            
                            // Continue refreshing for a few attempts to catch delayed cancellations
                            if (attempt < maxAttempts) {
                              refreshDropdown(attempt + 1, maxAttempts);
                            }
                          }, attempt * 2000); // 2s, 4s, 6s delays
                        };
                        
                        refreshDropdown();
                      } catch (error) {
                        console.error('Failed to cancel job:', error);
                        alert(`Failed to cancel job:\n\n${error.message}`);
                      }
                    }
                  },
                  onMouseEnter: (e: any) => {
                    e.target.style.backgroundColor = 'rgba(239, 68, 68, 0.2)';
                  },
                  onMouseLeave: (e: any) => {
                    e.target.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
                  }
                }, '🚫 Cancel') : null,
                
                // View button for completed and partial jobs
                (isCompleted || isPartial) ? React.createElement('button', {
                key: 'view-results',
                style: {
                  padding: '4px 8px',
                  fontSize: '10px',
                  fontWeight: '500',
                  color: isPartial ? '#f59e0b' : '#10b981',
                  backgroundColor: isPartial ? 'rgba(251, 191, 36, 0.1)' : 'rgba(16, 185, 129, 0.1)',
                  border: isPartial ? '1px solid rgba(251, 191, 36, 0.3)' : '1px solid rgba(16, 185, 129, 0.3)',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  marginLeft: '8px'
                },
                onClick: async (e) => {
                  e.stopPropagation();
                  console.log('🔍 Viewing results for job:', job);
                  
                  if (!settings?.stashAIServer || !settings?.port) {
                    alert('Server settings not available');
                    return;
                  }
                  
                  try {
                    // Fetch detailed job info with tasks to get results (same as SettingsPage)
                    const jobDetailUrl = `http://${settings.stashAIServer}:${settings.port}/api/queue/job/${job.job_id}`;
                    const response = await fetch(jobDetailUrl, {
                      method: 'GET',
                      headers: { 'Content-Type': 'application/json' }
                    });
                    
                    if (response.ok) {
                      const jobDetail = await response.json();
                      const tasks = jobDetail.tasks || [];
                      
                      // Check if this is a batch job with multiple tasks
                      const hasBatchResults = tasks.length > 1 && tasks.some(task => task.output_json);
                      
                      if (hasBatchResults && job.adapter_name === 'visage' && (window as any).AIResultsOverlayGalleries) {
                        // Use batch gallery overlay for multiple image processing
                        console.log('Opening batch gallery results overlay for job:', job);
                        
                        const jobWithTasks = {
                          ...job,
                          tasks: tasks
                        };
                        
                        // Create and show the gallery overlay
                        const overlay = React.createElement((window as any).AIResultsOverlayGalleries, {
                          jobData: jobWithTasks,
                          onClose: () => {
                            document.body.removeChild(overlayContainer);
                          },
                          React: React
                        });
                        
                        const overlayContainer = document.createElement('div');
                        document.body.appendChild(overlayContainer);
                        const ReactDOM = (window as any).PluginApi?.ReactDOM || React;
                        if (ReactDOM.render) {
                          ReactDOM.render(overlay, overlayContainer);
                        } else {
                          // Fallback for newer React versions
                          const root = ReactDOM.createRoot(overlayContainer);
                          root.render(overlay);
                        }
                        
                        setShowDropdown(false);
                      } else {
                        // Single task - use existing VisageImageResults overlay
                        const taskWithResults = tasks.find(task => task.output_json);
                        
                        if (taskWithResults && taskWithResults.adapter_name === 'visage' && (window as any).VisageImageResults) {
                          console.log('Opening single image results overlay for task:', taskWithResults);
                          
                          const overlayInfo = {
                            task: taskWithResults,
                            visageResults: taskWithResults.output_json,
                            taskId: taskWithResults.task_id,
                            taskType: taskWithResults.task_type
                          };
                          
                          // Create and show the overlay
                          const overlay = React.createElement((window as any).VisageImageResults, {
                            task: overlayInfo.task,
                            visageResults: overlayInfo.visageResults,
                            onClose: () => {
                              document.body.removeChild(overlayContainer);
                            },
                            React: React
                          });
                          
                          const overlayContainer = document.createElement('div');
                          document.body.appendChild(overlayContainer);
                          const ReactDOM = (window as any).PluginApi?.ReactDOM || React;
                          if (ReactDOM.render) {
                            ReactDOM.render(overlay, overlayContainer);
                          } else {
                            // Fallback for newer React versions
                            const root = ReactDOM.createRoot(overlayContainer);
                            root.render(overlay);
                          }
                          
                          setShowDropdown(false);
                        } else if (taskWithResults) {
                          // For non-visage tasks, show JSON (same as SettingsPage)
                          alert(`Task results:\n${JSON.stringify(taskWithResults.output_json, null, 2)}`);
                        } else {
                          alert('No viewable results found for this job');
                        }
                      }
                    } else {
                      alert('Failed to fetch job details');
                    }
                  } catch (error) {
                    console.error('Failed to fetch job results:', error);
                    alert('Failed to load job results');
                  }
                },
                onMouseEnter: (e: any) => {
                  e.target.style.backgroundColor = isPartial ? 'rgba(251, 191, 36, 0.2)' : 'rgba(16, 185, 129, 0.2)';
                },
                onMouseLeave: (e: any) => {
                  e.target.style.backgroundColor = isPartial ? 'rgba(251, 191, 36, 0.1)' : 'rgba(16, 185, 129, 0.1)';
                }
              }, '👁️ View') : null
              ])
            ]);
          })
      ]) : null
    ]) : null
  ]);
};

// CSS is now handled in NewButtonCSS.css

// Make the component available globally
(window as any).NewAIButton = NewAIButton;

export default NewAIButton;