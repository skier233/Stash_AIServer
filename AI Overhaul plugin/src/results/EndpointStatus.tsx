// Endpoint Status Results Component - Shows API endpoint health and usage
interface EndpointStatusProps {
  endpointResults: Record<string, { success: boolean; responseTime: number; error?: string }>;
  endpoints: Record<string, { endpoint: string; method: string; description: string; parameters?: string[] }>;
  React: any;
}

const EndpointStatus: React.FC<EndpointStatusProps> = ({ endpointResults, endpoints, React }) => {
  // =============================================================================
  // UTILITY FUNCTIONS
  // =============================================================================
  const getStatusColor = (success: boolean): string => {
    return success ? '#4ade80' : '#f87171';
  };

  const getStatusIcon = (success: boolean): string => {
    return success ? '✓' : '✗';
  };

  const getMethodColor = (method: string): string => {
    switch (method) {
      case 'GET': return '#10b981';
      case 'POST': return '#3b82f6';
      case 'PUT': return '#f59e0b';
      case 'DELETE': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const formatResponseTime = (time: number): string => {
    return time < 1000 ? `${time}ms` : `${(time / 1000).toFixed(2)}s`;
  };

  const categorizeEndpoints = () => {
    const categories = {
      'Core Server': ['server_health', 'queue_stats', 'queue_tasks', 'get_task'],
      'AI Services': ['visage_health', 'visage_task'],
      'Service Discovery': ['content_analysis_health', 'scene_analysis_health']
    };

    return categories;
  };

  // =============================================================================
  // RENDER COMPONENT
  // =============================================================================
  return React.createElement('div', {
    className: 'ai-overhaul-health-results ai-overhaul-fade-in'
  }, [
    // =============================================================================
    // HEADER SECTION
    // =============================================================================
    React.createElement('div', {
      key: 'header',
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
        key: 'title-section',
        style: { display: 'flex', alignItems: 'center', gap: '8px' }
      }, [
        React.createElement('span', { key: 'endpoint-icon' }, '🔗'),
        React.createElement('h4', {
          key: 'title',
          style: {
            color: 'rgba(255, 255, 255, 0.9)',
            fontSize: '1rem',
            fontWeight: '600',
            margin: '0'
          }
        }, 'API Endpoint Status')
      ]),
      React.createElement('div', {
        key: 'summary',
        style: {
          color: 'rgba(255, 255, 255, 0.6)',
          fontSize: '0.8rem'
        }
      }, `${Object.keys(endpointResults).filter(k => endpointResults[k].success).length}/${Object.keys(endpointResults).length} endpoints available`)
    ]),

    // =============================================================================
    // ENDPOINT CATEGORIES
    // =============================================================================
    ...Object.entries(categorizeEndpoints()).map(([categoryName, endpointKeys]) =>
      React.createElement('div', {
        key: `category-${categoryName}`,
        style: {
          background: 'rgba(255, 255, 255, 0.02)',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          borderRadius: '8px',
          padding: '12px',
          marginBottom: '8px'
        }
      }, [
        // Category Header
        React.createElement('div', {
          key: 'category-header',
          style: {
            color: 'rgba(255, 255, 255, 0.8)',
            fontWeight: '600',
            fontSize: '0.85rem',
            marginBottom: '8px',
            textTransform: 'uppercase',
            letterSpacing: '0.5px'
          }
        }, categoryName),

        // Endpoints in Category
        ...endpointKeys
          .filter(key => endpointResults[key] && endpoints[key])
          .map((key) => {
            const result = endpointResults[key];
            const config = endpoints[key];
            
            return React.createElement('div', {
              key: `endpoint-${key}`,
              style: {
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 8px',
                marginBottom: '4px',
                backgroundColor: result.success ? 'rgba(74, 222, 128, 0.03)' : 'rgba(248, 113, 113, 0.03)',
                borderRadius: '4px',
                border: `1px solid ${result.success ? 'rgba(74, 222, 128, 0.1)' : 'rgba(248, 113, 113, 0.1)'}`,
                fontSize: '0.8rem'
              }
            }, [
              // Status Icon
              React.createElement('span', {
                key: 'status-icon',
                style: {
                  color: getStatusColor(result.success),
                  fontWeight: 'bold',
                  width: '12px'
                }
              }, getStatusIcon(result.success)),

              // Method Badge
              React.createElement('span', {
                key: 'method',
                style: {
                  backgroundColor: getMethodColor(config.method),
                  color: 'white',
                  padding: '2px 6px',
                  borderRadius: '3px',
                  fontSize: '0.7rem',
                  fontWeight: '600',
                  minWidth: '40px',
                  textAlign: 'center'
                }
              }, config.method),

              // Endpoint Description
              React.createElement('span', {
                key: 'description',
                style: {
                  color: 'rgba(255, 255, 255, 0.8)',
                  flex: '1'
                }
              }, config.description),

              // Response Time (if successful)
              result.success ? React.createElement('span', {
                key: 'response-time',
                style: {
                  color: 'rgba(74, 222, 128, 0.8)',
                  fontFamily: 'monospace',
                  fontSize: '0.75rem'
                }
              }, formatResponseTime(result.responseTime)) : null,

              // Error (if failed)
              result.error ? React.createElement('span', {
                key: 'error',
                style: {
                  color: 'rgba(248, 113, 113, 0.8)',
                  fontSize: '0.75rem',
                  fontStyle: 'italic'
                }
              }, result.error) : null
            ]);
          })
      ])
    ),

    // =============================================================================
    // ENDPOINT URLS (COLLAPSIBLE)
    // =============================================================================
    React.createElement('div', {
      key: 'urls-section',
      style: {
        background: 'rgba(0, 0, 0, 0.1)',
        border: '1px solid rgba(255, 255, 255, 0.05)',
        borderRadius: '6px',
        padding: '8px',
        marginTop: '8px'
      }
    }, [
      React.createElement('div', {
        key: 'urls-title',
        style: {
          color: 'rgba(255, 255, 255, 0.6)',
          fontSize: '0.75rem',
          marginBottom: '6px',
          textTransform: 'uppercase',
          letterSpacing: '0.5px'
        }
      }, 'Endpoint URLs'),
      
      ...Object.entries(endpoints)
        .filter(([key]) => endpointResults[key]?.success)
        .map(([key, config]) =>
          React.createElement('div', {
            key: `url-${key}`,
            style: {
              fontFamily: 'monospace',
              fontSize: '0.7rem',
              color: 'rgba(255, 255, 255, 0.5)',
              marginBottom: '2px',
              wordBreak: 'break-all'
            }
          }, `${config.method} ${config.endpoint}`)
        )
    ])
  ]);
};

export default EndpointStatus;