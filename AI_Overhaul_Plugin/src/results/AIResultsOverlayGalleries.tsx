// =============================================================================
// AI Results Overlay for Gallery Batch Processing
// =============================================================================
// Displays batch processing results for galleries with performer management

interface DetectedPerformer {
  id: string;
  name: string;
  confidence: number;
  distance: number;
  image: string;
  image_url?: string;
  performer_url: string;
  stash_url?: string;
  faceIndex?: number;
  additional_info?: any;
}

interface ImageProcessingResult {
  imageId: string;
  imageUrl: string;
  success: boolean;
  performers: DetectedPerformer[];
  error?: string;
  processingTime?: number;
}

interface PerformerFrequency {
  performer: DetectedPerformer;
  frequency: number;
  appearances: {
    imageId: string;
    imageUrl: string;
    confidence: number;
  }[];
  averageConfidence: number;
  bestConfidence: number;
}

interface GalleryProcessingResult {
  success: boolean;
  galleryId: string;
  totalImages: number;
  processedImages: number;
  skippedImages: number;
  performers: PerformerFrequency[];
  processingResults: ImageProcessingResult[];
  error?: string;
  totalProcessingTime?: number;
}

interface AIResultsOverlayGalleriesProps {
  jobData: any; // Job with tasks and results
  galleryData?: any; // Gallery information
  onClose: () => void;
  React: any;
}

const AIResultsOverlayGalleries: React.FC<AIResultsOverlayGalleriesProps> = ({
  jobData,
  galleryData,
  onClose,
  React
}) => {
  // =============================================================================
  // STATE MANAGEMENT
  // =============================================================================
  const [selectedPerformer, setSelectedPerformer] = React.useState(null);
  const [showRawData, setShowRawData] = React.useState(false);
  const [expandedView, setExpandedView] = React.useState(false);
  const [performerOperations, setPerformerOperations] = React.useState(new Map());

  // =============================================================================
  // PROCESS BATCH RESULTS
  // =============================================================================
  const processBatchResults = React.useMemo(() => {
    if (!jobData || !jobData.tasks) {
      return null;
    }

    console.log('Processing batch job results:', jobData);

    const results: ImageProcessingResult[] = [];
    const performerMap = new Map<string, PerformerFrequency>();
    let totalProcessingTime = 0;
    let processedCount = 0;
    let skippedCount = 0;

    jobData.tasks.forEach((task: any, index: number) => {
      if (!task.output_json || task.status !== 'finished') {
        skippedCount++;
        return;
      }

      processedCount++;
      if (task.processing_time_ms) {
        totalProcessingTime += task.processing_time_ms;
      }

      const imageId = task.input_data?.entity_id || `image_${index}`;
      const imageTitle = task.input_data?.image_title || `Image ${index + 1}`;
      
      // Get image URL from entity data if available, otherwise construct it
      let imageUrl = `/image/${imageId}/image`; // Default fallback
      if (task.input_data?.entity && task.input_data.entity.paths) {
        imageUrl = task.input_data.entity.paths.image || 
                   task.input_data.entity.paths.preview || 
                   task.input_data.entity.paths.thumbnail || 
                   imageUrl;
      }

      const performers: DetectedPerformer[] = [];

      try {
        // Parse Visage results - handle nested structure
        let visageData = task.output_json;
        if (visageData.data) {
          visageData = visageData.data;
        }

        // Handle array structure
        if (Array.isArray(visageData)) {
          visageData.forEach((detection: any) => {
            if (detection && detection.performers && Array.isArray(detection.performers)) {
              detection.performers.forEach((performer: any) => {
                if (performer && performer.name) {
                  performers.push({
                    id: performer.id || performer.name.replace(/\s+/g, '_'),
                    name: performer.name,
                    confidence: performer.confidence || 0,
                    distance: performer.distance || 0,
                    image: performer.image || '',
                    image_url: performer.image_url || performer.performer_image_url,
                    performer_url: performer.performer_url || '',
                    stash_url: performer.stash_url,
                    faceIndex: performers.length,
                    additional_info: performer
                  });
                }
              });
            }
          });
        }
      } catch (error) {
        console.error('Error parsing task results:', error, task.output_json);
      }

      results.push({
        imageId,
        imageUrl,
        success: performers.length > 0,
        performers,
        processingTime: task.processing_time_ms
      });

      // Build performer frequency map
      performers.forEach((performer) => {
        const key = performer.name;
        if (!performerMap.has(key)) {
          performerMap.set(key, {
            performer,
            frequency: 0,
            appearances: [],
            averageConfidence: 0,
            bestConfidence: 0
          });
        }

        const performerFreq = performerMap.get(key)!;
        performerFreq.frequency++;
        performerFreq.appearances.push({
          imageId,
          imageUrl,
          confidence: performer.confidence
        });

        // Update confidence metrics
        const allConfidences = performerFreq.appearances.map(app => app.confidence);
        performerFreq.averageConfidence = allConfidences.reduce((a, b) => a + b, 0) / allConfidences.length;
        performerFreq.bestConfidence = Math.max(...allConfidences);
      });
    });

    // Convert performer map to sorted array
    const performers = Array.from(performerMap.values()).sort((a, b) => b.frequency - a.frequency);

    const galleryResult: GalleryProcessingResult = {
      success: processedCount > 0,
      galleryId: galleryData?.id || 'unknown',
      totalImages: jobData.tasks.length,
      processedImages: processedCount,
      skippedImages: skippedCount,
      performers,
      processingResults: results,
      totalProcessingTime
    };

    console.log('Processed gallery results:', galleryResult);
    return galleryResult;
  }, [jobData]);

  // =============================================================================
  // PERFORMER ACTIONS
  // =============================================================================
  const handlePerformerAction = async (performerFreq: PerformerFrequency, action: string) => {
    const actionKey = `${action}_${performerFreq.performer.id}`;
    
    if (performerOperations.has(actionKey)) {
      return; // Operation already in progress
    }

    setPerformerOperations(prev => new Map(prev.set(actionKey, true)));

    try {
      const MutateGraphQL = (window as any).MutateGraphQL;
      if (!MutateGraphQL) {
        throw new Error('MutateGraphQL utility not available');
      }

      const mutateUtil = MutateGraphQL({ React });

      switch (action) {
        case 'tag_all_images':
          console.log(`Tagging ${performerFreq.appearances.length} images with ${performerFreq.performer.name}`);
          
          for (const appearance of performerFreq.appearances) {
            try {
              const result = await mutateUtil.associatePerformerWithEntity(
                performerFreq.performer.name,
                'image',
                appearance.imageId
              );
              
              if (!result.success) {
                console.error(`Failed to tag image ${appearance.imageId}:`, result.error);
              }
            } catch (error) {
              console.error(`Error tagging image ${appearance.imageId}:`, error);
            }
          }
          
          alert(`✅ Tagged ${performerFreq.appearances.length} images with "${performerFreq.performer.name}"`);
          break;

        case 'tag_gallery':
          if (galleryData?.id) {
            // This would need a gallery performer association method
            console.log(`Tagging gallery ${galleryData.id} with ${performerFreq.performer.name}`);
            alert(`🚧 Gallery tagging not yet implemented`);
          }
          break;

        case 'view_stashdb':
          if (performerFreq.performer.performer_url) {
            window.open(performerFreq.performer.performer_url, '_blank');
          }
          break;

        default:
          console.warn(`Unknown action: ${action}`);
      }
    } catch (error) {
      console.error(`Error performing action ${action}:`, error);
      alert(`❌ Error: ${error.message || 'Unknown error occurred'}`);
    } finally {
      setPerformerOperations(prev => {
        const newMap = new Map(prev);
        newMap.delete(actionKey);
        return newMap;
      });
    }
  };

  // =============================================================================
  // UTILITY FUNCTIONS
  // =============================================================================
  const getConfidenceColor = (confidence: number): string => {
    const conf = confidence > 1 ? confidence : confidence * 100;
    if (conf >= 80) return '#4ade80';
    if (conf >= 60) return '#fbbf24';
    return '#f87171';
  };

  const formatConfidence = (confidence: number): string => {
    const conf = confidence > 1 ? confidence : confidence * 100;
    return `${conf.toFixed(1)}%`;
  };

  const formatProcessingTime = (ms: number): string => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  // =============================================================================
  // RENDER COMPONENTS
  // =============================================================================
  const renderPerformerFrequencyCard = (performerFreq: PerformerFrequency, index: number) => {
    const { performer, frequency, appearances, averageConfidence, bestConfidence } = performerFreq;
    const isExpanded = selectedPerformer === `${performer.id}_${index}`;
    
    const tagAllInProgress = performerOperations.has(`tag_all_images_${performer.id}`);
    const tagGalleryInProgress = performerOperations.has(`tag_gallery_${performer.id}`);

    return React.createElement('div', {
      key: `performer-freq-${index}`,
      style: {
        marginBottom: '16px',
        padding: '16px',
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        borderRadius: '8px',
        border: '1px solid rgba(255, 255, 255, 0.1)'
      }
    }, [
      // Performer Header
      React.createElement('div', {
        key: 'header',
        style: {
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'start',
          marginBottom: '12px'
        }
      }, [
        React.createElement('div', { key: 'info' }, [
          React.createElement('div', {
            key: 'name-freq',
            style: { display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }
          }, [
            React.createElement('h6', {
              key: 'name',
              style: { margin: 0, color: 'white', fontSize: '1rem' }
            }, performer.name),
            React.createElement('span', {
              key: 'badge',
              style: {
                backgroundColor: '#4ade80',
                color: 'white',
                padding: '2px 8px',
                borderRadius: '12px',
                fontSize: '0.8rem',
                fontWeight: '500'
              }
            }, `${frequency} image${frequency > 1 ? 's' : ''}`)
          ]),
          React.createElement('div', {
            key: 'confidence',
            style: { fontSize: '0.85rem', color: 'rgba(255, 255, 255, 0.7)' }
          }, [
            'Best: ',
            React.createElement('span', {
              key: 'best',
              style: { color: getConfidenceColor(bestConfidence * 100) }
            }, formatConfidence(bestConfidence)),
            ' • Avg: ',
            React.createElement('span', {
              key: 'avg',
              style: { color: getConfidenceColor(averageConfidence * 100) }
            }, formatConfidence(averageConfidence))
          ])
        ]),
        performer.image || performer.image_url ? React.createElement('img', {
          key: 'thumbnail',
          src: performer.image_url || performer.image,
          alt: performer.name,
          style: {
            width: '60px',
            height: '60px',
            borderRadius: '6px',
            objectFit: 'cover',
            border: '1px solid rgba(255, 255, 255, 0.2)'
          },
          onError: (e: any) => {
            e.target.style.display = 'none';
          }
        }) : React.createElement('div', {
          key: 'thumbnail-placeholder',
          style: {
            width: '60px',
            height: '60px',
            borderRadius: '6px',
            backgroundColor: '#6c5ce7',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            fontWeight: 'bold',
            fontSize: '16px'
          }
        }, performer.name.split(' ').map((n: string) => n[0]).join('').toUpperCase().substring(0, 2))
      ]),

      // Action Buttons
      React.createElement('div', {
        key: 'actions',
        style: { display: 'flex', gap: '8px', marginBottom: '12px' }
      }, [
        React.createElement('button', {
          key: 'tag-images',
          onClick: () => handlePerformerAction(performerFreq, 'tag_all_images'),
          disabled: tagAllInProgress,
          style: {
            fontSize: '0.8rem',
            padding: '6px 12px',
            backgroundColor: tagAllInProgress ? '#6b7280' : '#4ade80',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: tagAllInProgress ? 'not-allowed' : 'pointer',
            fontWeight: '500'
          }
        }, tagAllInProgress ? '⏳ Tagging...' : `🏷️ Tag All ${frequency} Images`),

        React.createElement('button', {
          key: 'tag-gallery',
          onClick: () => handlePerformerAction(performerFreq, 'tag_gallery'),
          disabled: tagGalleryInProgress,
          style: {
            fontSize: '0.8rem',
            padding: '6px 12px',
            backgroundColor: tagGalleryInProgress ? '#6b7280' : '#60a5fa',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: tagGalleryInProgress ? 'not-allowed' : 'pointer',
            fontWeight: '500'
          }
        }, tagGalleryInProgress ? '⏳ Tagging...' : '🎯 Tag Gallery'),

        performer.performer_url ? React.createElement('button', {
          key: 'view-stashdb',
          onClick: () => handlePerformerAction(performerFreq, 'view_stashdb'),
          style: {
            fontSize: '0.8rem',
            padding: '6px 12px',
            backgroundColor: '#8b5cf6',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
            fontWeight: '500'
          }
        }, '🔗 StashDB') : null
      ]),

      // Toggle Appearances
      React.createElement('button', {
        key: 'toggle-appearances',
        onClick: () => setSelectedPerformer(isExpanded ? null : `${performer.id}_${index}`),
        style: {
          fontSize: '0.8rem',
          padding: '4px 8px',
          backgroundColor: 'transparent',
          color: '#60a5fa',
          border: '1px solid #60a5fa',
          borderRadius: '4px',
          cursor: 'pointer',
          marginBottom: isExpanded ? '12px' : '0'
        }
      }, `${isExpanded ? '🗜️ Hide' : '🔍 Show'} Appearances (${frequency})`),

      // Image Appearances
      isExpanded ? React.createElement('div', {
        key: 'appearances',
        style: {
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
          gap: '8px',
          marginTop: '12px'
        }
      }, appearances.map((appearance, appIndex) =>
        React.createElement('div', {
          key: `appearance-${appIndex}`,
          style: {
            position: 'relative',
            borderRadius: '6px',
            overflow: 'hidden',
            border: '1px solid rgba(255, 255, 255, 0.2)',
            cursor: 'pointer'
          }
        }, [
          React.createElement('img', {
            key: 'image',
            src: appearance.imageUrl,
            alt: `Appearance ${appIndex + 1}`,
            style: {
              width: '100%',
              height: '80px',
              objectFit: 'cover',
              display: 'block'
            },
            onError: (e: any) => {
              e.target.style.display = 'none';
              e.target.parentNode.style.backgroundColor = 'rgba(255, 255, 255, 0.1)';
              e.target.parentNode.style.display = 'flex';
              e.target.parentNode.style.alignItems = 'center';
              e.target.parentNode.style.justifyContent = 'center';
              e.target.parentNode.textContent = '🖼️';
            }
          }),
          React.createElement('div', {
            key: 'overlay',
            style: {
              position: 'absolute',
              top: '4px',
              right: '4px',
              backgroundColor: getConfidenceColor(appearance.confidence * 100),
              color: 'white',
              padding: '2px 6px',
              borderRadius: '4px',
              fontSize: '0.75rem',
              fontWeight: '500'
            }
          }, formatConfidence(appearance.confidence))
        ])
      )) : null
    ]);
  };

  const renderProcessingStats = () => {
    if (!processBatchResults) return null;

    const successRate = (processBatchResults.processedImages / processBatchResults.totalImages) * 100;

    return React.createElement('div', {
      key: 'processing-stats',
      style: {
        marginBottom: '20px',
        padding: '16px',
        backgroundColor: 'rgba(255, 255, 255, 0.05)',
        borderRadius: '8px',
        border: '1px solid rgba(255, 255, 255, 0.1)'
      }
    }, [
      React.createElement('h6', {
        key: 'title',
        style: { color: 'white', marginBottom: '12px' }
      }, '📊 Processing Statistics'),
      
      React.createElement('div', {
        key: 'stats-grid',
        style: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '0.9rem' }
      }, [
        React.createElement('div', { key: 'total' }, [
          React.createElement('span', {
            key: 'label',
            style: { color: 'rgba(255, 255, 255, 0.7)' }
          }, 'Total Images: '),
          React.createElement('span', {
            key: 'value',
            style: { color: 'white', fontWeight: '500' }
          }, processBatchResults.totalImages)
        ]),
        React.createElement('div', { key: 'processed' }, [
          React.createElement('span', {
            key: 'label',
            style: { color: 'rgba(255, 255, 255, 0.7)' }
          }, 'Processed: '),
          React.createElement('span', {
            key: 'value',
            style: { color: '#4ade80', fontWeight: '500' }
          }, `✅ ${processBatchResults.processedImages}`)
        ]),
        React.createElement('div', { key: 'success-rate' }, [
          React.createElement('span', {
            key: 'label',
            style: { color: 'rgba(255, 255, 255, 0.7)' }
          }, 'Success Rate: '),
          React.createElement('span', {
            key: 'value',
            style: { color: 'white', fontWeight: '500' }
          }, `${successRate.toFixed(1)}%`)
        ]),
        React.createElement('div', { key: 'performers' }, [
          React.createElement('span', {
            key: 'label',
            style: { color: 'rgba(255, 255, 255, 0.7)' }
          }, 'Performers: '),
          React.createElement('span', {
            key: 'value',
            style: { color: '#60a5fa', fontWeight: '500' }
          }, `👥 ${processBatchResults.performers.length}`)
        ])
      ])
    ]);
  };

  // =============================================================================
  // MAIN RENDER
  // =============================================================================
  if (!processBatchResults) {
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
        zIndex: 2147483647,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }
    }, [
      React.createElement('div', {
        key: 'error',
        style: {
          padding: '40px',
          backgroundColor: 'rgba(20, 20, 20, 0.95)',
          borderRadius: '16px',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          color: 'white',
          textAlign: 'center'
        }
      }, [
        React.createElement('h3', { key: 'title' }, '❌ No Results Available'),
        React.createElement('p', {
          key: 'message',
          style: { color: 'rgba(255, 255, 255, 0.7)', marginBottom: '20px' }
        }, 'Unable to process batch results data'),
        React.createElement('button', {
          key: 'close',
          onClick: onClose,
          style: {
            padding: '8px 16px',
            backgroundColor: '#4ade80',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer'
          }
        }, 'Close')
      ])
    ]);
  }

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
      zIndex: 2147483647,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '20px'
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
            style: { color: 'white', margin: '0 0 4px 0', fontSize: '1.5rem', fontWeight: '600' }
          }, '🖼️ Gallery Analysis Results'),
          React.createElement('p', {
            key: 'subtitle',
            style: { color: 'rgba(255, 255, 255, 0.6)', margin: 0, fontSize: '0.9rem' }
          }, `${processBatchResults.performers.length} performers found in ${processBatchResults.processedImages}/${processBatchResults.totalImages} images`)
        ]),
        React.createElement('div', {
          key: 'header-controls',
          style: { display: 'flex', gap: '8px', alignItems: 'center' }
        }, [
          React.createElement('button', {
            key: 'raw-data',
            onClick: () => setShowRawData(!showRawData),
            style: {
              background: 'transparent',
              border: '1px solid rgba(255, 255, 255, 0.3)',
              color: 'rgba(255, 255, 255, 0.8)',
              fontSize: '12px',
              padding: '6px 10px',
              borderRadius: '4px',
              cursor: 'pointer'
            }
          }, `${showRawData ? 'Hide' : 'Show'} Raw Data`),
          React.createElement('button', {
            key: 'close',
            onClick: onClose,
            style: {
              background: 'transparent',
              border: 'none',
              color: 'rgba(255, 255, 255, 0.6)',
              fontSize: '24px',
              cursor: 'pointer',
              padding: '8px'
            }
          }, '×')
        ])
      ]),

      // Content
      React.createElement('div', {
        key: 'content-area',
        style: {
          flex: 1,
          overflow: 'auto',
          padding: '20px'
        }
      }, [
        // Processing Stats
        renderProcessingStats(),

        // Performers Section
        processBatchResults.performers.length > 0 ? React.createElement('div', {
          key: 'performers-section',
          style: { marginBottom: '20px' }
        }, [
          React.createElement('h6', {
            key: 'performers-title',
            style: { color: 'white', marginBottom: '16px', fontSize: '1.1rem' }
          }, '👥 Detected Performers (by frequency)'),
          
          ...processBatchResults.performers.map((performerFreq, index) =>
            renderPerformerFrequencyCard(performerFreq, index)
          )
        ]) : React.createElement('div', {
          key: 'no-performers',
          style: {
            textAlign: 'center',
            padding: '40px',
            color: 'rgba(255, 255, 255, 0.6)'
          }
        }, [
          React.createElement('div', {
            key: 'icon',
            style: { fontSize: '3rem', marginBottom: '16px' }
          }, '👁️'),
          React.createElement('h6', {
            key: 'title',
            style: { color: 'white', marginBottom: '8px' }
          }, 'No Performers Detected'),
          React.createElement('p', {
            key: 'message',
            style: { margin: 0, fontSize: '0.9rem' }
          }, `Processed ${processBatchResults.processedImages} images but found no recognizable faces`)
        ]),

        // Raw Data Section
        showRawData ? React.createElement('div', {
          key: 'raw-data',
          style: {
            marginTop: '20px',
            padding: '16px',
            backgroundColor: 'rgba(255, 255, 255, 0.05)',
            borderRadius: '8px',
            border: '1px solid rgba(255, 255, 255, 0.1)'
          }
        }, [
          React.createElement('h6', {
            key: 'raw-title',
            style: { color: 'white', marginBottom: '12px' }
          }, 'Raw Job Data'),
          React.createElement('pre', {
            key: 'raw-content',
            style: {
              backgroundColor: '#1a1a1a',
              color: '#e2e8f0',
              padding: '12px',
              borderRadius: '6px',
              fontSize: '11px',
              maxHeight: '300px',
              overflow: 'auto',
              margin: 0
            }
          }, JSON.stringify(jobData, null, 2))
        ]) : null
      ])
    ])
  ]);
};

// Expose globally for plugin usage
(window as any).AIResultsOverlayGalleries = AIResultsOverlayGalleries;

export default AIResultsOverlayGalleries;