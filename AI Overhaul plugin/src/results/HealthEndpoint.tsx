// Health Endpoint Results Component
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

interface HealthEndpointProps {
  healthData: HealthData;
  React: any;
}

const HealthEndpoint: React.FC<HealthEndpointProps> = ({ healthData, React }) => {
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
    // =============================================================================
    // MAIN STATUS SECTION
    // =============================================================================
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

    // =============================================================================
    // DATABASE STATUS
    // =============================================================================
    React.createElement('div', {
      key: 'database-status',
      style: {
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        marginBottom: '12px'
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

    // =============================================================================
    // QUEUE STATUS (if available)
    // =============================================================================
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
    ]) : null
  ]);
};

export default HealthEndpoint;