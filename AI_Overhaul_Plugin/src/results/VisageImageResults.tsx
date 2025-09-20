// =============================================================================
// Visage Image Results Overlay Component
// =============================================================================

interface VisagePerformer {
  id: string;
  name: string;
  confidence: number;
  image: string;
  country: string;
  hits: number;
  distance: number;
  performer_url: string;
}

interface VisageFaceDetection {
  image: string; // base64 data
  confidence: number;
  performers: VisagePerformer[];
}

// Interface kept for potential future use
// interface VisageResult {
//   data: VisageFaceDetection[][];
// }

interface VisageImageResultsProps {
  task: any; // Full task object with input_data
  visageResults: any; // Raw API response
  onClose: () => void;
  React: any;
}

const VisageImageResults: React.FC<VisageImageResultsProps> = ({ 
  task, 
  visageResults, 
  onClose, 
  React 
}) => {
  // =============================================================================
  // STATE MANAGEMENT
  // =============================================================================
  const [selectedFace, setSelectedFace] = React.useState(null);
  const [imageLoaded, setImageLoaded] = React.useState(false);
  const [imageUrl, setImageUrl] = React.useState(null);
  const [imageId, setImageId] = React.useState(null);
  const [imageError, setImageError] = React.useState(null);
  
  // Performer management state
  const [performerOperations, setPerformerOperations] = React.useState(new Map()); // Track ongoing operations
  const [associatedPerformers, setAssociatedPerformers] = React.useState(new Set()); // Track which performers are associated

  // =============================================================================
  // IMAGE URL RESOLUTION WITH UNIVERSAL GRAPHQL
  // =============================================================================
  React.useEffect(() => {
    const resolveImageUrl = async () => {
      if (!task || !task.input_data) {
        setImageError('No task input data available');
        return;
      }

      const inputData = task.input_data;
      console.log('VisageImageResults: Resolving image URL from task input data:', inputData);
      
      try {
        // Create UniversalGraphQL instance
        const UniversalGraphQL = (window as any).UniversalGraphQL;
        if (!UniversalGraphQL) {
          console.error('UniversalGraphQL not available, falling back to manual resolution');
          setImageError('UniversalGraphQL utility not available');
          return;
        }
        
        const graphqlUtil = UniversalGraphQL({ React });
        const result = await graphqlUtil.resolveImageFromTaskData(inputData);
        
        if (result.url) {
          setImageUrl(result.url);
          setImageId(result.id);
          setImageError(null);
          console.log('VisageImageResults: Successfully resolved image URL:', result);
        } else {
          const errorMsg = `Could not resolve image URL. Available fields: ${Object.keys(inputData).join(', ')}`;
          console.error('VisageImageResults:', errorMsg, inputData);
          setImageError(errorMsg);
        }
      } catch (error) {
        console.error('VisageImageResults: Error resolving image URL:', error);
        setImageError('Error resolving image URL');
      }
    };

    resolveImageUrl();
  }, [task]);

  // =============================================================================
  // PERFORMER MANAGEMENT FUNCTIONS
  // =============================================================================
  
  // Helper function to extract performer name from performer object
  const getPerformerName = (performer: any): string | null => {
    console.log('getPerformerName - Full performer object:', performer);
    console.log('getPerformerName - Available fields:', Object.keys(performer));
    
    // Check all possible name fields
    const possibleNameFields = [
      'performer_name', 'label', 'title', 'display_name', 'full_name', 
      'person_name', 'celebrity', 'actor', 'model', 'person'
    ];
    
    for (const field of possibleNameFields) {
      if (performer[field] && typeof performer[field] === 'string' && 
          !performer[field].includes('/9j/') && performer[field].length < 200) {
        console.log(`getPerformerName - Using field '${field}':`, performer[field]);
        return performer[field];
      }
    }
    
    // Last resort: check name field more carefully
    if (performer.name && typeof performer.name === 'string' && 
        !performer.name.includes('/9j/') && performer.name.length < 200) {
      console.log('getPerformerName - Using name field:', performer.name);
      return performer.name;
    }
    
    console.error('getPerformerName - No valid name field found');
    return null;
  };
  
  const handlePerformerAction = async (performer: any, detectionIndex: number, action: 'add' | 'remove') => {
    // Extract performer name first
    const performerName = getPerformerName(performer);
    if (!performerName) {
      console.error('Cannot identify performer name field. Available fields:', Object.keys(performer));
      console.error('Full performer object:', performer);
      alert('❌ Error: Cannot identify performer name - check console for details');
      return;
    }
    
    const operationKey = `${detectionIndex}-${performerName}`;
    
    // Check if operation is already in progress
    if (performerOperations.has(operationKey)) {
      console.log('Operation already in progress for:', operationKey);
      return;
    }
    
    // Mark operation as in progress
    setPerformerOperations(prev => new Map(prev.set(operationKey, action)));
    
    try {
      const MutateGraphQL = (window as any).MutateGraphQL;
      if (!MutateGraphQL) {
        throw new Error('MutateGraphQL utility not available');
      }
      
      const mutateUtil = MutateGraphQL({ React });
      
      if (!imageId) {
        throw new Error('Image ID not available');
      }
      
      // Get entity information from task
      const inputData = task.input_data;
      const entityType = inputData.entity_type || 'image'; // Default to image
      const entityId = imageId;
      
      if (action === 'add') {
        console.log('Adding performer to image:', performerName);
        console.log('Raw performer data:', performer);
        console.log('Face detection:', faceDetections[detectionIndex]);
        
        // Use the detected face image as performer image if available
        const faceDetection = faceDetections[detectionIndex];
        const performerImageData = faceDetection?.image || null;
        
        console.log('About to call associatePerformerWithEntity with:', {
          performerName,
          entityType, 
          entityId,
          performerImageDataPreview: performerImageData ? `${performerImageData.substring(0, 50)}...` : null
        });
        
        const result = await mutateUtil.associatePerformerWithEntity(
          performerName,
          entityType,
          entityId,
          performerImageData
        );
        
        if (result.success) {
          // Update associated performers set
          setAssociatedPerformers(prev => new Set(prev.add(performerName)));
          
          // Show success message
          alert(`✅ ${result.message}`);
        } else {
          throw new Error(result.error || 'Failed to associate performer');
        }
      } else if (action === 'remove') {
        console.log('Removing performer from image:', performerName);
        
        // First find the performer ID
        const existingPerformer = await mutateUtil.findPerformerByExactName(performerName);
        if (!existingPerformer) {
          throw new Error('Performer not found');
        }
        
        const result = await mutateUtil.removePerformerFromImage(entityId, existingPerformer.id);
        
        if (result.success) {
          // Update associated performers set
          setAssociatedPerformers(prev => {
            const newSet = new Set(prev);
            newSet.delete(performerName);
            return newSet;
          });
          
          alert(`✅ Removed performer "${performerName}" from image`);
        } else {
          throw new Error(result.error || 'Failed to remove performer');
        }
      }
    } catch (error) {
      console.error('Error in performer action:', error);
      alert(`❌ Error: ${error.message || 'Unknown error occurred'}`);
    } finally {
      // Clear operation status
      setPerformerOperations(prev => {
        const newMap = new Map(prev);
        newMap.delete(operationKey);
        return newMap;
      });
    }
  };

  // Check current image performers on load
  React.useEffect(() => {
    const checkAssociatedPerformers = async () => {
      if (!imageId) return;
      
      try {
        const MutateGraphQL = (window as any).MutateGraphQL;
        if (!MutateGraphQL) return;
        
        const mutateUtil = MutateGraphQL({ React });
        const currentPerformers = await mutateUtil.getImagePerformers(imageId);
        
        // Extract performer names that are currently associated
        const associatedNames = new Set(currentPerformers.map((p: any) => p.name));
        setAssociatedPerformers(associatedNames);
        
        console.log('Current associated performers:', Array.from(associatedNames));
      } catch (error) {
        console.error('Error checking associated performers:', error);
      }
    };
    
    checkAssociatedPerformers();
  }, [imageId]);

  // =============================================================================
  // UTILITY FUNCTIONS
  // =============================================================================
  // Parse the actual Visage API response
  const parseVisageResults = (results: any): VisageFaceDetection[] => {
    try {
      console.log('Raw Visage results:', results);
      
      // Return empty array if results is null/undefined
      if (!results) {
        console.warn('VisageImageResults: No results provided');
        return [];
      }
      
      // Handle both direct data array and nested structure
      let dataArray = results;
      if (results.data) {
        dataArray = results.data;
      }
      
      // Return empty array if dataArray is not valid
      if (!dataArray) {
        console.warn('VisageImageResults: No data array found');
        return [];
      }
      
      // Flatten nested arrays if needed (compatible with es2017)
      if (Array.isArray(dataArray) && dataArray.length > 0 && Array.isArray(dataArray[0])) {
        return dataArray.reduce((acc, val) => acc.concat(val), []);
      }
      
      return Array.isArray(dataArray) ? dataArray : [];
    } catch (error) {
      console.error('Error parsing Visage results:', error);
      return [];
    }
  };
  
  const faceDetections = parseVisageResults(visageResults);
  
  const getConfidenceColor = (confidence: number): string => {
    // Convert percentage to decimal if needed
    const conf = confidence > 1 ? confidence / 100 : confidence;
    if (conf >= 0.8) return '#4ade80';
    if (conf >= 0.6) return '#fbbf24';
    return '#f87171';
  };

  const formatConfidence = (confidence: number): string => {
    // Handle both decimal and percentage formats
    const conf = confidence > 1 ? confidence : confidence * 100;
    return `${conf.toFixed(1)}%`;
  };

  const handleImageLoad = () => {
    setImageLoaded(true);
  };

  // Get total face count across all detections
  const getTotalFaceCount = (): number => {
    if (!faceDetections || !Array.isArray(faceDetections)) {
      return 0;
    }
    return faceDetections.reduce((total, detection) => {
      if (!detection || !detection.performers || !Array.isArray(detection.performers)) {
        return total;
      }
      return total + detection.performers.length;
    }, 0);
  };
  
  const totalFaces = getTotalFaceCount();

  // =============================================================================
  // RENDER COMPONENT - Full viewport overlay
  // =============================================================================
  return React.createElement('div', {
    className: 'ai-overhaul-overlay',
    style: {
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100vw',
      height: '100vh',
      backgroundColor: 'rgba(0, 0, 0, 0.9)',
      backdropFilter: 'blur(10px)',
      zIndex: 2147483647, // Maximum z-index value
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px',
      margin: 0
    },
    onClick: (e: any) => {
      if (e.target === e.currentTarget) onClose();
    }
  }, [
    React.createElement('div', {
      key: 'content',
      className: 'ai-overhaul-overlay-content',
      style: {
        background: 'rgba(20, 20, 20, 0.95)',
        borderRadius: '16px',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        maxWidth: '90vw',
        maxHeight: '90vh',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column'
      }
    }, [
      // Header
      React.createElement('div', {
        key: 'header',
        style: {
          padding: '20px',
          borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }
      }, [
        React.createElement('div', { key: 'title-section' }, [
          React.createElement('h2', {
            key: 'title',
            style: {
              color: 'white',
              margin: '0 0 4px 0',
              fontSize: '1.5rem',
              fontWeight: '600'
            }
          }, 'Visage Face Recognition Results'),
          React.createElement('p', {
            key: 'subtitle',
            style: {
              color: 'rgba(255, 255, 255, 0.6)',
              margin: 0,
              fontSize: '0.9rem'
            }
          }, `Found ${totalFaces} face${totalFaces !== 1 ? 's' : ''} with ${faceDetections.length} detection${faceDetections.length !== 1 ? 's' : ''}`)
        ]),
        React.createElement('button', {
          key: 'close',
          onClick: onClose,
          style: {
            background: 'transparent',
            border: 'none',
            color: 'rgba(255, 255, 255, 0.6)',
            fontSize: '24px',
            cursor: 'pointer',
            padding: '8px',
            borderRadius: '4px'
          }
        }, '×')
      ]),

      // Content Area
      React.createElement('div', {
        key: 'content-area',
        style: {
          display: 'flex',
          flex: 1,
          overflow: 'hidden'
        }
      }, [
        // Image Section
        React.createElement('div', {
          key: 'image-section',
          style: {
            flex: 1,
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px'
          }
        }, [
          React.createElement('div', {
            key: 'image-container',
            style: { position: 'relative', display: 'inline-block' }
          }, [
            // Show loading/error state or image
            imageError ? React.createElement('div', {
              key: 'image-error',
              style: {
                padding: '40px',
                textAlign: 'center',
                color: 'rgba(255, 255, 255, 0.6)',
                backgroundColor: 'rgba(255, 255, 255, 0.05)',
                borderRadius: '8px',
                border: '1px solid rgba(255, 255, 255, 0.1)'
              }
            }, [
              React.createElement('div', { key: 'error-text' }, 'Failed to load image'),
              React.createElement('div', { 
                key: 'error-details', 
                style: { fontSize: '0.8rem', marginTop: '8px', opacity: 0.7 } 
              }, imageError)
            ]) : !imageUrl ? React.createElement('div', {
              key: 'image-loading',
              style: {
                padding: '40px',
                textAlign: 'center',
                color: 'rgba(255, 255, 255, 0.6)'
              }
            }, 'Loading image...') : React.createElement('img', {
              key: 'main-image',
              src: imageUrl,
              onLoad: handleImageLoad,
              onError: (e) => {
                console.error('Failed to load image:', imageUrl, e);
                setImageError('Failed to load image from resolved URL');
              },
              style: {
                maxWidth: '100%',
                maxHeight: '60vh',
                borderRadius: '8px',
                display: 'block'
              },
              alt: 'Analysis target'
            }),

            // Show detected face images if available
            imageLoaded && faceDetections && faceDetections.length > 0 && React.createElement('div', {
              key: 'detected-faces',
              style: {
                position: 'absolute',
                top: '10px',
                right: '10px',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                maxWidth: '100px'
              }
            }, faceDetections.map((detection, detectionIndex) => 
              detection && detection.image ? React.createElement('img', {
                key: `detected-face-${detectionIndex}`,
                src: `data:image/jpeg;base64,${detection.image}`,
                style: {
                  width: '80px',
                  height: '80px',
                  objectFit: 'cover',
                  borderRadius: '8px',
                  border: `2px solid ${getConfidenceColor(detection.confidence)}`,
                  cursor: 'pointer',
                  backgroundColor: selectedFace === detectionIndex ? 'rgba(74, 144, 226, 0.3)' : 'transparent'
                },
                onClick: () => setSelectedFace(selectedFace === detectionIndex ? null : detectionIndex),
                title: `Detection ${detectionIndex + 1}: ${formatConfidence(detection.confidence)} confidence`,
                alt: `Detected face ${detectionIndex + 1}`
              }) : null
            ))
          ])
        ]),

        // Details Panel
        React.createElement('div', {
          key: 'details-panel',
          style: {
            width: '300px',
            borderLeft: '1px solid rgba(255, 255, 255, 0.1)',
            padding: '20px',
            overflowY: 'auto'
          }
        }, [
          React.createElement('h3', {
            key: 'panel-title',
            style: {
              color: 'white',
              margin: '0 0 16px 0',
              fontSize: '1.1rem',
              fontWeight: '600'
            }
          }, 'Detection Details'),

          ...(faceDetections || []).map((detection, detectionIndex) => 
            !detection ? null : React.createElement('div', {
              key: `detection-${detectionIndex}`,
              style: {
                marginBottom: '16px'
              }
            }, [
              // Detection header
              React.createElement('div', {
                key: 'detection-header',
                style: {
                  padding: '12px',
                  backgroundColor: selectedFace === detectionIndex ? 'rgba(74, 144, 226, 0.1)' : 'rgba(255, 255, 255, 0.05)',
                  borderRadius: '8px',
                  border: `1px solid ${selectedFace === detectionIndex ? 'rgba(74, 144, 226, 0.3)' : 'rgba(255, 255, 255, 0.1)'}`,
                  cursor: 'pointer',
                  marginBottom: '8px'
                },
                onClick: () => setSelectedFace(selectedFace === detectionIndex ? null : detectionIndex)
              }, [
                React.createElement('div', {
                  key: 'detection-info',
                  style: { 
                    color: 'white',
                    fontWeight: '600',
                    marginBottom: '4px'
                  }
                }, `Detection ${detectionIndex + 1}`),
                React.createElement('div', {
                  key: 'detection-confidence',
                  style: { 
                    color: getConfidenceColor(detection.confidence),
                    fontSize: '0.9rem'
                  }
                }, `Confidence: ${formatConfidence(detection.confidence)}`)
              ]),
              
              // Performers list
              ...((detection && detection.performers && Array.isArray(detection.performers)) ? detection.performers : []).map((performer, performerIndex) =>
                !performer ? null : React.createElement('div', {
                  key: `performer-${detectionIndex}-${performerIndex}`,
                  style: {
                    padding: '10px',
                    marginBottom: '6px',
                    backgroundColor: 'rgba(255, 255, 255, 0.03)',
                    borderRadius: '6px',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                    marginLeft: '12px'
                  }
                }, [
                  React.createElement('div', {
                    key: 'performer-header',
                    style: {
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      marginBottom: '6px'
                    }
                  }, [
                    performer.image ? React.createElement('img', {
                      key: 'performer-image',
                      src: performer.image,
                      style: {
                        width: '32px',
                        height: '32px',
                        borderRadius: '4px',
                        objectFit: 'cover'
                      },
                      alt: getPerformerName(performer) || 'Performer'
                    }) : null,
                    React.createElement('div', {
                      key: 'performer-name',
                      style: {
                        color: 'white',
                        fontWeight: '500',
                        fontSize: '0.9rem'
                      }
                    }, getPerformerName(performer) || 'Unknown Performer')
                  ]),
                  React.createElement('div', {
                    key: 'performer-details',
                    style: {
                      fontSize: '0.8rem',
                      color: 'rgba(255, 255, 255, 0.7)'
                    }
                  }, [
                    React.createElement('div', { key: 'confidence' }, `Match: ${formatConfidence(performer.confidence)}`),
                    performer.country ? React.createElement('div', { key: 'country' }, `Country: ${performer.country}`) : null,
                    React.createElement('div', { key: 'distance' }, `Distance: ${performer.distance}`),
                    performer.hits ? React.createElement('div', { key: 'hits' }, `Hits: ${performer.hits}`) : null,
                    // StashDB link if available
                    performer.performer_url ? React.createElement('div', {
                      key: 'stashdb-link',
                      style: { marginTop: '4px' }
                    }, [
                      React.createElement('a', {
                        key: 'stashdb-url',
                        href: performer.performer_url,
                        target: '_blank',
                        rel: 'noopener noreferrer',
                        style: {
                          color: '#60a5fa',
                          textDecoration: 'none',
                          fontSize: '0.75rem',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '2px'
                        },
                        onMouseEnter: (e: any) => {
                          e.target.style.textDecoration = 'underline';
                        },
                        onMouseLeave: (e: any) => {
                          e.target.style.textDecoration = 'none';
                        }
                      }, [
                        '🔗 StashDB',
                        React.createElement('span', {
                          key: 'external-icon',
                          style: { fontSize: '0.6rem' }
                        }, ' ↗')
                      ])
                    ]) : null
                  ]),
                  
                  // Performer action buttons
                  React.createElement('div', {
                    key: 'performer-actions',
                    style: {
                      marginTop: '8px',
                      display: 'flex',
                      gap: '6px',
                      justifyContent: 'flex-end'
                    }
                  }, [
                    // Show current association status and appropriate action
                    (() => {
                      const performerName = getPerformerName(performer);
                      if (!performerName) return null; // Skip if we can't get the name
                      
                      const operationKey = `${detectionIndex}-${performerName}`;
                      const isOperationInProgress = performerOperations.has(operationKey);
                      const operationType = performerOperations.get(operationKey);
                      const isAssociated = associatedPerformers.has(performerName);
                      
                      if (isOperationInProgress) {
                        return React.createElement('div', {
                          key: 'operation-status',
                          style: {
                            fontSize: '0.75rem',
                            color: '#fbbf24',
                            fontStyle: 'italic'
                          }
                        }, `${operationType === 'add' ? 'Adding...' : 'Removing...'}`);
                      }
                      
                      if (isAssociated) {
                        return [
                          React.createElement('div', {
                            key: 'associated-status',
                            style: {
                              fontSize: '0.75rem',
                              color: '#4ade80',
                              fontWeight: '500'
                            }
                          }, '✓ Associated'),
                          React.createElement('button', {
                            key: 'remove-btn',
                            onClick: (e: any) => {
                              e.stopPropagation();
                              handlePerformerAction(performer, detectionIndex, 'remove');
                            },
                            style: {
                              fontSize: '0.7rem',
                              padding: '2px 6px',
                              backgroundColor: '#f87171',
                              color: 'white',
                              border: 'none',
                              borderRadius: '3px',
                              cursor: 'pointer'
                            },
                            title: `Remove ${performerName} from image`
                          }, 'Remove')
                        ];
                      } else {
                        return React.createElement('button', {
                          key: 'add-btn',
                          onClick: (e: any) => {
                            e.stopPropagation();
                            handlePerformerAction(performer, detectionIndex, 'add');
                          },
                          style: {
                            fontSize: '0.7rem',
                            padding: '4px 8px',
                            backgroundColor: '#4ade80',
                            color: 'white',
                            border: 'none',
                            borderRadius: '4px',
                            cursor: 'pointer',
                            fontWeight: '500'
                          },
                          title: `Add ${performerName} to image`
                        }, '+ Add to Image');
                      }
                    })()
                  ])
                ])
              )
            ])
          )
        ])
      ])
    ])
  ]);
};

// Expose globally for plugin usage
(window as any).VisageImageResults = VisageImageResults;

export default VisageImageResults;