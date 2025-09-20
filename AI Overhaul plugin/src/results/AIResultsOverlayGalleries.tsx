// Use the global PluginApi interface instead of redefining it

(function () {
  const PluginApi = (window as any).PluginApi;
  const React = PluginApi.React;
  const { Modal, Button, Card, Badge, Row, Col, Alert } = PluginApi.libraries.Bootstrap;

  // Types for gallery processing results
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
    jobData?: any; // NEW: Accept raw job data
    galleryData?: any;
    galleryResults?: GalleryProcessingResult; // LEGACY: Pre-processed results  
    rawResponse?: any;
    onClose: () => void;
    React?: any;
  }

  // Process job data into gallery results format
  const processJobDataToGalleryResults = (jobData: any): GalleryProcessingResult => {
    if (!jobData || !jobData.tasks) {
      return {
        success: false,
        galleryId: 'unknown',
        totalImages: 0,
        processedImages: 0,
        skippedImages: 0,
        performers: [],
        processingResults: [],
        error: 'No job data provided'
      };
    }

    console.log('🔄 Processing job data to gallery results:', jobData);

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

      // Extract entity ID and handle different batch job structures
      let imageId = null;
      let imageUrl = null;
      let imageTitle = `Image ${index + 1}`;
      
      // Check if this is a batch job with base64 image data
      if (task.input_data?.image && typeof task.input_data.image === 'string' && 
          task.input_data.image.startsWith('/9j/')) {
        // This is base64 image data - create data URL
        imageId = `batch_${task.input_data.batch_index || index}`;
        imageUrl = `data:image/jpeg;base64,${task.input_data.image}`;
        imageTitle = `Batch Image ${(task.input_data.batch_index || index) + 1}`;
        
        console.log(`✅ Task ${index}: Batch job with base64 data, imageId=${imageId}`);
      } else {
        // Try different locations for entity ID (entity-based jobs)
        if (task.input_data?.entity_id) {
          imageId = task.input_data.entity_id;
        } else if (task.input_data?.image_id) {
          imageId = task.input_data.image_id;
        } else if (task.input_data?.entity?.id) {
          imageId = task.input_data.entity.id;
        } else if (task.input_data?.data?.entity_id) {
          imageId = task.input_data.data.entity_id;
        } else {
          // Fallback
          imageId = `image_${index}`;
          console.warn(`No entity ID found for task ${index}, using fallback`);
        }
        
        // Construct proper Stash image URL for entity-based images
        imageUrl = `/image/${imageId}/image`;
      }

      const performers: DetectedPerformer[] = [];

      try {
        // Parse Visage results - handle nested structure
        let visageData = task.output_json;
        if (visageData.data) {
          visageData = visageData.data;
        }

        // Handle array structure
        let faces = [];
        if (Array.isArray(visageData)) {
          faces = visageData;
        } else if (visageData.faces && Array.isArray(visageData.faces)) {
          faces = visageData.faces;
        } else if (visageData.predictions && Array.isArray(visageData.predictions)) {
          faces = visageData.predictions;
        }

        console.log(`Task ${index}: Found ${faces.length} faces`);
        if (faces.length > 0) {
          console.log(`🔍 First face data structure:`, faces[0]);
        }

        faces.forEach((faceDetectionItem: any, detectionIndex: number) => {
          console.log(`🎭 Processing face detection ${detectionIndex}:`, faceDetectionItem);
          
          // Check if this is an array of face detections or a single detection
          let faceDetections = [];
          if (Array.isArray(faceDetectionItem)) {
            faceDetections = faceDetectionItem;
            console.log(`📋 Face detection ${detectionIndex} contains ${faceDetections.length} individual faces`);
          } else {
            faceDetections = [faceDetectionItem];
            console.log(`📋 Face detection ${detectionIndex} is a single face object`);
          }
          
          // Process each individual face detection
          faceDetections.forEach((singleFaceDetection: any, faceIndex: number) => {
            const detectionPerformers = singleFaceDetection.performers || [];
            console.log(`🔍 Face ${faceIndex} in detection ${detectionIndex}: Found ${detectionPerformers.length} performers`);
            
            if (detectionPerformers.length > 0) {
              console.log(`👥 First performer data for face ${faceIndex}:`, detectionPerformers[0]);
            }
          
            detectionPerformers.forEach((performer: any, performerIndex: number) => {
              // Helper function to extract performer name - copied from VisageImageResults
              const getPerformerName = (performer: any): string | null => {
                const possibleNameFields = [
                  'performer_name', 'label', 'title', 'display_name', 'full_name', 
                  'person_name', 'celebrity', 'actor', 'model', 'person'
                ];
                
                for (const field of possibleNameFields) {
                  if (performer[field] && typeof performer[field] === 'string' && 
                      !performer[field].includes('/9j/') && performer[field].length < 200) {
                    return performer[field];
                  }
                }
                
                if (performer.name && typeof performer.name === 'string' && 
                    !performer.name.includes('/9j/') && performer.name.length < 200) {
                  return performer.name;
                }
                
                return null;
              };
              
              const performerName = getPerformerName(performer);
              if (performerName) {
                const detectedPerformer: DetectedPerformer = {
                  id: performer.id || `unknown_${detectionIndex}_${faceIndex}_${performerIndex}`,
                  name: performerName,
                  confidence: performer.confidence || 0,
                  distance: performer.distance || 0,
                  image: performer.image || '',
                  image_url: performer.image_url || performer.image,
                  performer_url: performer.performer_url || '',
                  stash_url: performer.stash_url || '',
                  faceIndex: detectionIndex,
                  additional_info: performer
                };

                performers.push(detectedPerformer);

                // Track performer frequency
                const performerId = detectedPerformer.id;
                if (!performerMap.has(performerId)) {
                  performerMap.set(performerId, {
                    performer: detectedPerformer,
                    frequency: 0,
                    appearances: [],
                    averageConfidence: 0,
                    bestConfidence: 0
                  });
                }

                const performerFreq = performerMap.get(performerId)!;
                performerFreq.frequency++;
                performerFreq.appearances.push({
                  imageId,
                  imageUrl,
                  confidence: detectedPerformer.confidence
                });

                // Update confidence metrics
                const confidences = performerFreq.appearances.map(a => a.confidence);
                performerFreq.averageConfidence = confidences.reduce((sum, conf) => sum + conf, 0) / confidences.length;
                performerFreq.bestConfidence = Math.max(...confidences);
              }
            });
          });
        });

      } catch (error) {
        console.error(`Failed to parse task ${index} results:`, error);
      }

      results.push({
        imageId,
        imageUrl,
        success: true,
        performers,
        processingTime: task.processing_time_ms
      });
    });

    const galleryResults: GalleryProcessingResult = {
      success: true,
      galleryId: jobData.job_id || 'unknown',
      totalImages: jobData.tasks.length,
      processedImages: processedCount,
      skippedImages: skippedCount,
      performers: Array.from(performerMap.values()),
      processingResults: results,
      totalProcessingTime
    };

    console.log('✅ Processed gallery results:', galleryResults);
    return galleryResults;
  };

  // GraphQL mutation functions - using direct fetch to Stash GraphQL endpoint
  const makeGraphQLRequest = async (query: string, variables: any) => {
    try {
      const response = await fetch('/graphql', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query,
          variables
        })
      });

      if (!response.ok) {
        throw new Error(`GraphQL request failed: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      
      if (result.errors) {
        throw new Error(`GraphQL errors: ${result.errors.map((e: any) => e.message).join(', ')}`);
      }

      return result;
    } catch (error) {
      console.error('GraphQL request failed:', error);
      throw error;
    }
  };

  const galleryUpdateMutation = async (variables: any) => {
    const query = `
      mutation GalleryUpdate($input: GalleryUpdateInput!) {
        galleryUpdate(input: $input) {
          id
          title
          performers {
            id
            name
          }
        }
      }
    `;
    return makeGraphQLRequest(query, variables);
  };

  const bulkImageUpdateMutation = async (variables: any) => {
    const query = `
      mutation BulkImageUpdate($input: BulkImageUpdateInput!) {
        bulkImageUpdate(input: $input) {
          id
          performers {
            id
            name
          }
        }
      }
    `;
    return makeGraphQLRequest(query, variables);
  };

  // Toast notification function
  const showToast = (message: string, variant: 'success' | 'danger' | 'warning' | 'info' = 'info') => {
    try {
      // Try to use PluginApi toast if available
      if ((PluginApi as any).util && (PluginApi as any).util.showToast) {
        (PluginApi as any).util.showToast({ message, variant });
      } else {
        // Fallback to browser alert
        console.log(`Toast [${variant}]: ${message}`);
        // Try to show as a temporary overlay in the top right
        const toast = document.createElement('div');
        toast.style.cssText = `
          position: fixed;
          top: 20px;
          right: 20px;
          background: ${variant === 'success' ? '#28a745' : variant === 'danger' ? '#dc3545' : variant === 'warning' ? '#ffc107' : '#17a2b8'};
          color: white;
          padding: 12px 20px;
          border-radius: 4px;
          z-index: 9999;
          font-size: 14px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        `;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        // Remove after 5 seconds
        setTimeout(() => {
          if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
          }
        }, 5000);
      }
    } catch (error) {
      console.error('Failed to show toast:', error);
      alert(message); // Ultimate fallback
    }
  };

  // Utility functions
  const getConfidenceColor = (confidence: number): string => {
    // Convert percentage to decimal if needed (copied from VisageImageResults)
    const conf = confidence > 1 ? confidence / 100 : confidence;
    if (conf >= 0.8) return 'success';
    if (conf >= 0.6) return 'warning';
    return 'danger';
  };

  const formatConfidence = (confidence: number): string => {
    // Handle both decimal and percentage formats (copied from VisageImageResults)
    const conf = confidence > 1 ? confidence : confidence * 100;
    return `${conf.toFixed(1)}%`;
  };

  const formatProcessingTime = (ms: number): string => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60000).toFixed(1)}m`;
  };

  // Function to find real Stash image IDs for batch job appearances using GraphQL
  const findRealImageIdsForBatchJob = async (appearances: any[], galleryData: any): Promise<string[]> => {
    const foundIds: string[] = [];
    
    // Strategy 1: If we have a gallery, get all gallery images and match by batch index
    if (galleryData?.id) {
      console.log(`🔍 Querying gallery ${galleryData.id} images...`);
      
      try {
        const galleryQuery = `
          query FindGalleryImages($gallery_id: ID!) {
            findGallery(id: $gallery_id) {
              images {
                id
                path
                checksum
                width
                height
                size
              }
            }
          }
        `;
        
        const galleryResponse = await makeGraphQLRequest(galleryQuery, { gallery_id: galleryData.id });
        const galleryImages = galleryResponse?.data?.findGallery?.images || [];
        
        console.log(`📊 Found ${galleryImages.length} images in gallery ${galleryData.id}`);
        
        // Try to match batch appearances to gallery images
        for (const appearance of appearances) {
          if (appearance.imageId && appearance.imageId.toString().startsWith('batch_')) {
            // Extract batch index from batch_X format
            const batchIndexMatch = appearance.imageId.match(/batch_(\d+)/);
            if (batchIndexMatch) {
              const batchIndex = parseInt(batchIndexMatch[1]);
              
              // Use batch index to get corresponding gallery image (0-based indexing)
              if (batchIndex < galleryImages.length) {
                const matchedImage = galleryImages[batchIndex];
                if (matchedImage && matchedImage.id) {
                  foundIds.push(matchedImage.id);
                  console.log(`✅ Matched batch_${batchIndex} to gallery image ${matchedImage.id} (${matchedImage.path})`);
                } else {
                  console.log(`❌ No image found at gallery index ${batchIndex}`);
                }
              } else {
                console.log(`❌ Batch index ${batchIndex} exceeds gallery size ${galleryImages.length}`);
              }
            }
          }
        }
        
        if (foundIds.length > 0) {
          console.log(`🎯 Successfully matched ${foundIds.length} batch appearances to gallery images`);
          return foundIds;
        }
      } catch (error) {
        console.error('❌ Error querying gallery images:', error);
      }
    }
    
    // Strategy 2: If no gallery or gallery matching failed, try other approaches
    console.log('🔍 Attempting alternative matching strategies...');
    
    // TODO: Could add more strategies here like:
    // - Image similarity search
    // - Metadata matching (dimensions, file size)
    // - Path/filename matching
    
    return foundIds;
  };

  const AIResultsOverlayGalleries: React.FC<AIResultsOverlayGalleriesProps> = ({
    jobData,
    galleryData,
    galleryResults: providedGalleryResults,
    rawResponse,
    onClose
  }) => {
    // Extract gallery data from job data if not provided directly
    const effectiveGalleryData = React.useMemo(() => {
      if (galleryData) {
        console.log('🖼️ Using provided gallery data:', galleryData);
        return galleryData;
      }
      
      console.log('🖼️ Attempting to extract gallery data from job data:', jobData);
      
      // Try to extract gallery information from job data
      if (jobData?.tasks && jobData.tasks.length > 0) {
        console.log('🖼️ Checking tasks for gallery ID, first task:', jobData.tasks[0]);
        
        const firstTask = jobData.tasks[0];
        if (firstTask?.input_data) {
          console.log('🖼️ First task input_data:', firstTask.input_data);
          
          // Check various possible locations for gallery ID
          const galleryId = firstTask.input_data.gallery_id || 
                           firstTask.input_data.entity_id ||
                           firstTask.input_data.data?.gallery_id ||
                           firstTask.input_data.data?.entity_id;
          
          if (galleryId) {
            console.log('🖼️ Extracted gallery ID from task input_data:', galleryId);
            return { id: galleryId };
          } else {
            console.log('🖼️ No gallery ID found in task input_data fields');
          }
        }
      }
      
      // Check if job metadata contains gallery info
      if (jobData?.job_metadata?.gallery_id) {
        console.log('🖼️ Found gallery ID in job metadata:', jobData.job_metadata.gallery_id);
        return { id: jobData.job_metadata.gallery_id };
      }
      
      // Check if job contains gallery context for gallery-batch analysis
      if (jobData?.adapter_name === 'gallery-batch' || jobData?.job_name?.includes('Gallery')) {
        console.log('🖼️ Gallery batch job detected, checking for gallery context...');
        
        // For gallery batch jobs, check if any task has gallery context
        for (const task of jobData?.tasks || []) {
          const taskGalleryId = task?.context?.gallery_id || task?.gallery_id;
          if (taskGalleryId) {
            console.log('🖼️ Found gallery ID in task context:', taskGalleryId);
            return { id: taskGalleryId };
          }
        }
      }
      
      console.warn('⚠️ No gallery data available - gallery tagging will be disabled');
      console.warn('🖼️ Job data structure:', {
        jobId: jobData?.job_id,
        adapterName: jobData?.adapter_name,
        jobName: jobData?.job_name,
        taskCount: jobData?.tasks?.length,
        firstTaskKeys: jobData?.tasks?.[0] ? Object.keys(jobData.tasks[0]) : [],
        firstTaskInputKeys: jobData?.tasks?.[0]?.input_data ? Object.keys(jobData.tasks[0].input_data) : [],
        // Add detailed inspection of job data
        fullJobKeys: jobData ? Object.keys(jobData) : [],
        sampleTaskInputData: jobData?.tasks?.[0]?.input_data,
        jobMetadata: jobData?.job_metadata
      });
      
      // For debugging: log the full job data structure (only in console, not to user)
      if (jobData) {
        console.warn('🔍 Full job data for gallery ID debugging:', JSON.stringify(jobData, null, 2));
      }
      
      return null;
    }, [galleryData, jobData]);
    
    // Process job data if provided, otherwise use provided gallery results
    const galleryResults = React.useMemo(() => {
      if (providedGalleryResults) {
        return providedGalleryResults;
      }
      if (jobData) {
        return processJobDataToGalleryResults(jobData);
      }
      return null;
    }, [jobData, providedGalleryResults]);

    // Debug logging
    React.useEffect(() => {
      if (galleryResults) {
        console.log('🖼️ Gallery Results Data:', galleryResults);
        console.log('🎭 Performers:', galleryResults.performers);
        if (galleryResults.performers && galleryResults.performers.length > 0) {
          console.log('🎯 First Performer:', galleryResults.performers[0]);
          console.log('📊 First Performer Confidence:', galleryResults.performers[0].averageConfidence);
          console.log('🖼️ First Performer Appearances:', galleryResults.performers[0].appearances?.slice(0, 3));
        }
      }
    }, [galleryResults]);

    const [expandedImage, setExpandedImage] = React.useState(false);
    const [showRawData, setShowRawData] = React.useState(false);
    const [selectedPerformer, setSelectedPerformer] = React.useState(null);
    const [isTagging, setIsTagging] = React.useState({} as {[key: string]: boolean});
    const [selectedImageOverlay, setSelectedImageOverlay] = React.useState(null as { imageId: string, task: any, visageResults: any } | null);

    // Tagging functions
    const tagGalleryWithPerformer = async (performerFreq: PerformerFrequency) => {
      if (!effectiveGalleryData?.id) {
        console.error('Gallery ID not available for tagging');
        showToast('Gallery ID not available - cannot tag gallery', 'danger');
        return;
      }

      const actionKey = `tag_gallery_${performerFreq.performer.id}`;
      setIsTagging((prev: any) => ({ ...prev, [actionKey]: true }));

      try {
        console.log(`🏷️ Tagging gallery ${effectiveGalleryData.id} with performer ${performerFreq.performer.name}`);
        
        const response = await galleryUpdateMutation({
          input: {
            id: effectiveGalleryData.id,
            performer_ids: {
              ids: [performerFreq.performer.id],
              mode: 'ADD' // Add to existing performers
            }
          }
        });

        if (response?.data?.galleryUpdate) {
          console.log('✅ Gallery tagged successfully:', response.data.galleryUpdate);
          // Show success notification
          const message = `Gallery tagged with ${performerFreq.performer.name}`;
          showToast(message, 'success');
        }
      } catch (error: any) {
        console.error('❌ Failed to tag gallery:', error);
        const message = `Failed to tag gallery: ${error.message || 'Unknown error'}`;
        showToast(message, 'danger');
      } finally {
        setIsTagging((prev: any) => ({ ...prev, [actionKey]: false }));
      }
    };

    const tagImagesWithPerformer = async (performerFreq: PerformerFrequency) => {
      if (!performerFreq.appearances || performerFreq.appearances.length === 0) {
        console.error('No image appearances available for tagging');
        return;
      }

      const actionKey = `tag_images_${performerFreq.performer.id}`;
      setIsTagging((prev: any) => ({ ...prev, [actionKey]: true }));

      try {
        // Extract real Stash image IDs from appearances
        const validImageIds = [];
        const processedUrls = new Set(); // Prevent duplicates
        
        for (const appearance of performerFreq.appearances) {
          let imageId = appearance.imageId;
          
          // If it's a synthetic batch ID, try to extract from URL
          if (!/^\d+$/.test(imageId)) {
            console.log(`🔍 Found synthetic ID: ${imageId}, attempting to extract from URL: ${appearance.imageUrl}`);
            
            if (appearance.imageUrl) {
              // Try to extract image ID from various Stash URL patterns
              const urlPatterns = [
                /\/images\/(\d+)/, // /images/123
                /\/image\/(\d+)/, // /image/123  
                /image=(\d+)/, // ?image=123
                /imageId=(\d+)/, // ?imageId=123
                /id=(\d+)/, // ?id=123
                /\/(\d+)\.jpg/, // /123.jpg
                /\/(\d+)\.jpeg/, // /123.jpeg
                /\/(\d+)\.png/, // /123.png
                /\/(\d+)\.webp/, // /123.webp
                /\/(\d+)$/ // ends with /123
              ];
              
              let extractedId = null;
              for (const pattern of urlPatterns) {
                const match = appearance.imageUrl.match(pattern);
                if (match && match[1]) {
                  extractedId = match[1];
                  console.log(`✅ Extracted ID ${extractedId} from URL using pattern: ${pattern}`);
                  break;
                }
              }
              
              if (extractedId && !processedUrls.has(appearance.imageUrl)) {
                imageId = extractedId;
                processedUrls.add(appearance.imageUrl);
                console.log(`🎯 Using extracted ID: ${imageId} for tagging`);
              } else if (!extractedId) {
                console.log(`❌ Could not extract ID from URL: ${appearance.imageUrl}`);
              }
            }
          }
          
          // Only include numeric IDs (real Stash image IDs) and avoid duplicates
          if (/^\d+$/.test(imageId) && !validImageIds.includes(imageId)) {
            validImageIds.push(imageId);
          } else if (!/^\d+$/.test(imageId)) {
            console.log(`🚫 Skipping invalid ID: ${imageId} (not numeric)`);
          }
        }
        
        if (validImageIds.length === 0) {
          console.warn('⚠️ No valid image IDs found for tagging after URL extraction');
          console.warn('📊 Appearance data for debugging:', performerFreq.appearances.map(app => ({
            imageId: app.imageId,
            imageUrl: app.imageUrl,
            confidence: app.confidence
          })));
          
          // For batch jobs, try to find real image IDs using GraphQL queries
          const hasBatchIds = performerFreq.appearances.some(app => app.imageId && app.imageId.toString().startsWith('batch_'));
          if (hasBatchIds) {
            console.log('🔍 Batch job detected, attempting to find real image IDs via GraphQL...');
            try {
              const foundImageIds = await findRealImageIdsForBatchJob(performerFreq.appearances, effectiveGalleryData);
              if (foundImageIds.length > 0) {
                console.log(`✅ Found ${foundImageIds.length} real image IDs via GraphQL:`, foundImageIds);
                validImageIds.push(...foundImageIds);
              } else {
                console.log('❌ No matching images found via GraphQL queries');
                if (effectiveGalleryData?.id) {
                  showToast(`Batch job detected - use "Tag Gallery" to tag all gallery images with ${performerFreq.performer.name}`, 'info');
                } else {
                  showToast('Batch job detected but no gallery available for tagging. Individual image tagging not supported for batch processing.', 'warning');
                }
                return;
              }
            } catch (error) {
              console.error('❌ Error finding real image IDs via GraphQL:', error);
              if (effectiveGalleryData?.id) {
                showToast(`Batch job detected - use "Tag Gallery" to tag all gallery images with ${performerFreq.performer.name}`, 'info');
              } else {
                showToast('Batch job detected but no gallery available for tagging. Individual image tagging not supported for batch processing.', 'warning');
              }
              return;
            }
          } else {
            showToast('No real Stash image IDs found - could not extract from URLs', 'warning');
            return;
          }
        }
        
        console.log(`🏷️ Tagging ${validImageIds.length} real images with performer ${performerFreq.performer.name} (from ${performerFreq.appearances.length} appearances)`);
        console.log('📋 Valid image IDs for tagging:', validImageIds);
        
        const response = await bulkImageUpdateMutation({
          input: {
            ids: validImageIds,
            performer_ids: {
              ids: [performerFreq.performer.id],
              mode: 'ADD' // Add to existing performers
            }
          }
        });

        if (response?.data) {
          console.log('✅ Images tagged successfully:', response.data);
          // Show success notification
          const message = `${validImageIds.length} images tagged with ${performerFreq.performer.name}`;
          showToast(message, 'success');
        }
      } catch (error: any) {
        console.error('❌ Failed to tag images:', error);
        const message = `Failed to tag images: ${error.message || 'Unknown error'}`;
        showToast(message, 'danger');
      } finally {
        setIsTagging((prev: any) => ({ ...prev, [actionKey]: false }));
      }
    };

    const handlePerformerAction = async (performer: PerformerFrequency, action: string) => {
      console.log(`🎯 Performer action: ${action} for ${performer.performer.name}`);
      
      switch (action) {
        case 'tag_gallery':
          await tagGalleryWithPerformer(performer);
          break;
        case 'tag_all_images':
          await tagImagesWithPerformer(performer);
          break;
        case 'view':
          // Open performer details in a new tab
          if (performer.performer.stash_url || performer.performer.performer_url) {
            window.open(performer.performer.stash_url || performer.performer.performer_url, '_blank');
          }
          break;
      }
    };

    // Function to open individual image in VisageImageResults overlay
    const openIndividualImage = (imageId: string) => {
      console.log('🖼️ Opening individual image:', imageId);
      
      // Find the corresponding task from the job data
      if (!jobData?.tasks) {
        console.error('No job data available to open individual image');
        return;
      }

      // Find the task that corresponds to this image
      const task = jobData.tasks.find((task: any, index: number) => {
        // Check if this is a batch job with base64 image data
        if (task.input_data?.image && typeof task.input_data.image === 'string' && 
            task.input_data.image.startsWith('/9j/')) {
          const taskImageId = `batch_${task.input_data.batch_index || index}`;
          return taskImageId === imageId;
        } else {
          // Try different locations for entity ID (entity-based jobs)
          const taskImageId = task.input_data?.entity_id || task.input_data?.image_id || 
                             task.input_data?.entity?.id || task.input_data?.data?.entity_id || 
                             `image_${index}`;
          return taskImageId === imageId;
        }
      });

      if (!task) {
        console.error('Could not find task for image:', imageId);
        return;
      }

      console.log('🎯 Found task for image:', task);

      // Prepare the task data for VisageImageResults
      let taskForOverlay;
      
      if (task.input_data?.image && typeof task.input_data.image === 'string' && 
          task.input_data.image.startsWith('/9j/')) {
        // For batch jobs with base64 data, create a structure that VisageImageResults can handle
        // We'll create a mock entity structure that includes the direct image URL
        taskForOverlay = {
          ...task,
          input_data: {
            // Try to make it look like a regular Stash entity
            entity_id: imageId.replace('batch_', ''), // Remove batch prefix for ID
            entity_type: 'image',
            // Provide multiple ways for VisageImageResults to find the image
            image_id: imageId.replace('batch_', ''),
            id: imageId.replace('batch_', ''),
            // Also keep the batch-specific data
            batch_index: task.input_data.batch_index,
            is_batch_image: true,
            batch_image_data: task.input_data.image
          }
        };
        
        console.log('🎯 Prepared batch task for VisageImageResults:', taskForOverlay);
      } else {
        // For entity-based jobs, keep the original structure
        taskForOverlay = task;
        console.log('🎯 Prepared entity task for VisageImageResults:', taskForOverlay);
      }

      // Set the selected image overlay data
      setSelectedImageOverlay({
        imageId,
        task: taskForOverlay,
        visageResults: task.output_json
      });
    };

    const renderPerformerFrequencyCardDark = (performerFreq: PerformerFrequency, index: number) => {
      const { performer, frequency, appearances, averageConfidence, bestConfidence } = performerFreq;
      const isExpanded = selectedPerformer === `${performer.id}_${index}`;

      return React.createElement('div', {
        key: `performer-freq-${index}`,
        style: { 
          marginBottom: '16px'
        }
      }, [
        // Performer header (like VisageImageResults detection header)
        React.createElement('div', {
          key: 'performer-header',
          style: {
            padding: '12px',
            backgroundColor: isExpanded ? 'rgba(74, 144, 226, 0.1)' : 'rgba(255, 255, 255, 0.05)',
            borderRadius: '8px',
            border: `1px solid ${isExpanded ? 'rgba(74, 144, 226, 0.3)' : 'rgba(255, 255, 255, 0.1)'}`,
            cursor: 'pointer',
            marginBottom: '8px'
          },
          onClick: () => setSelectedPerformer(isExpanded ? null : `${performer.id}_${index}`)
        }, [
          React.createElement('div', {
            key: 'performer-info',
            style: {
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }
          }, [
            React.createElement('div', { key: 'left-info' }, [
              React.createElement('div', {
                key: 'name-and-frequency',
                style: { 
                  color: 'white',
                  fontWeight: '600',
                  marginBottom: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }
              }, [
                performer.name,
                React.createElement('span', {
                  key: 'frequency-badge',
                  style: {
                    backgroundColor: 'rgba(74, 144, 226, 0.2)',
                    color: '#60a5fa',
                    padding: '2px 6px',
                    borderRadius: '12px',
                    fontSize: '0.75rem',
                    fontWeight: '500'
                  }
                }, `${frequency} image${frequency > 1 ? 's' : ''}`)
              ]),
              React.createElement('div', {
                key: 'confidence-metrics',
                style: { 
                  color: 'rgba(255, 255, 255, 0.7)',
                  fontSize: '0.85rem'
                }
              }, `Best: ${formatConfidence(bestConfidence)} • Avg: ${formatConfidence(averageConfidence)}`)
            ]),
            
            // Performer thumbnail
            React.createElement('div', {
              key: 'performer-thumbnail',
              style: {
                width: '40px',
                height: '40px',
                borderRadius: '4px',
                overflow: 'hidden',
                border: '1px solid rgba(255, 255, 255, 0.2)',
                backgroundColor: 'rgba(255, 255, 255, 0.05)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }
            }, (performer.image || performer.image_url) ? React.createElement('img', {
              src: performer.image_url || performer.image,
              alt: performer.name,
              style: {
                width: '100%',
                height: '100%',
                objectFit: 'cover'
              },
              onError: (e: any) => {
                console.warn(`Failed to load performer image: ${performer.image_url || performer.image}`);
                e.target.style.display = 'none';
                const placeholder = document.createElement('div');
                placeholder.style.cssText = 'width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; background: #6c5ce7; color: white; font-weight: bold; font-size: 12px;';
                placeholder.textContent = performer.name.split(' ').map((n: string) => n[0]).join('').toUpperCase().substring(0, 2);
                e.target.parentNode.appendChild(placeholder);
              }
            }) : React.createElement('div', {
              style: {
                width: '100%',
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: '#6c5ce7',
                color: 'white',
                fontWeight: 'bold',
                fontSize: '12px'
              }
            }, performer.name.split(' ').map((n: string) => n[0]).join('').toUpperCase().substring(0, 2)))
          ])
        ]),
        
        // Action buttons (always visible for batch operations)
        React.createElement('div', {
          key: 'performer-actions',
          style: {
            marginBottom: '8px',
            display: 'flex',
            gap: '6px',
            justifyContent: 'flex-end'
          }
        }, [
          React.createElement('button', {
            key: 'tag-images-btn',
            onClick: (e: any) => {
              e.stopPropagation();
              handlePerformerAction(performerFreq, 'tag_all_images');
            },
            disabled: isTagging[`tag_images_${performerFreq.performer.id}`],
            style: {
              fontSize: '0.7rem',
              padding: '4px 8px',
              backgroundColor: isTagging[`tag_images_${performerFreq.performer.id}`] ? '#666' : '#4ade80',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: '500'
            }
          }, isTagging[`tag_images_${performerFreq.performer.id}`] ? 'Tagging...' : `Tag ${frequency} Images`),
          
          React.createElement('button', {
            key: 'tag-gallery-btn',
            onClick: (e: any) => {
              e.stopPropagation();
              handlePerformerAction(performerFreq, 'tag_gallery');
            },
            disabled: isTagging[`tag_gallery_${performerFreq.performer.id}`],
            style: {
              fontSize: '0.7rem',
              padding: '4px 8px',
              backgroundColor: isTagging[`tag_gallery_${performerFreq.performer.id}`] ? '#666' : '#60a5fa',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: '500'
            }
          }, isTagging[`tag_gallery_${performerFreq.performer.id}`] ? 'Tagging...' : 'Tag Gallery')
        ]),

        // Image appearances (expandable like VisageImageResults)
        isExpanded && React.createElement('div', {
          key: 'appearances',
          style: {
            padding: '10px',
            backgroundColor: 'rgba(255, 255, 255, 0.03)',
            borderRadius: '6px',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            marginLeft: '12px'
          }
        }, [
          React.createElement('div', {
            key: 'appearances-title',
            style: {
              color: 'rgba(255, 255, 255, 0.8)',
              fontSize: '0.85rem',
              marginBottom: '8px',
              fontWeight: '500'
            }
          }, `Image Appearances (${appearances.length})`),
          
          React.createElement('div', {
            key: 'appearances-grid',
            style: {
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(60px, 1fr))',
              gap: '6px'
            }
          }, appearances.map((appearance, appIndex) =>
            React.createElement('div', {
              key: `appearance-${appIndex}`,
              style: { 
                position: 'relative',
                borderRadius: '4px',
                overflow: 'hidden',
                border: '1px solid rgba(255, 255, 255, 0.2)',
                transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                cursor: 'pointer'
              },
              onMouseEnter: (e: any) => {
                e.currentTarget.style.transform = 'scale(1.05)';
                e.currentTarget.style.boxShadow = '0 2px 8px rgba(74, 144, 226, 0.3)';
              },
              onMouseLeave: (e: any) => {
                e.currentTarget.style.transform = 'scale(1)';
                e.currentTarget.style.boxShadow = 'none';
              },
              onClick: () => {
                openIndividualImage(appearance.imageId);
              }
            }, [
              React.createElement('img', {
                key: 'appearance-img',
                src: appearance.imageUrl,
                alt: `Appearance ${appIndex + 1}`,
                style: {
                  width: '60px',
                  height: '60px',
                  objectFit: 'cover',
                  display: 'block'
                },
                onError: (e: any) => {
                  console.warn(`Failed to load image: ${appearance.imageUrl}`);
                  e.target.style.display = 'none';
                  const placeholder = document.createElement('div');
                  placeholder.style.cssText = 'width: 60px; height: 60px; background: #333; display: flex; align-items: center; justify-content: center; color: #666; font-size: 10px;';
                  placeholder.textContent = '🖼️';
                  e.target.parentNode.appendChild(placeholder);
                }
              }),
              React.createElement('div', {
                key: 'confidence-overlay',
                style: {
                  position: 'absolute',
                  top: '2px',
                  right: '2px',
                  backgroundColor: getConfidenceColor(appearance.confidence) === 'success' ? '#4ade80' : getConfidenceColor(appearance.confidence) === 'warning' ? '#fbbf24' : '#f87171',
                  color: 'white',
                  fontSize: '8px',
                  padding: '1px 3px',
                  borderRadius: '2px',
                  fontWeight: 'bold'
                }
              }, formatConfidence(appearance.confidence))
            ])
          ))
        ])
      ]);
    };

    const renderPerformerFrequencyCard = (performerFreq: PerformerFrequency, index: number) => {
      const { performer, frequency, appearances, averageConfidence, bestConfidence } = performerFreq;
      const isExpanded = selectedPerformer === `${performer.id}_${index}`;

      return React.createElement(Card, {
        key: `performer-freq-${index}`,
        style: { 
          marginBottom: '15px',
          border: '1px solid #dee2e6',
          borderRadius: '8px',
          transition: 'box-shadow 0.2s ease',
          cursor: 'pointer'
        },
        className: 'ai-performer-frequency-card',
        onMouseEnter: (e: any) => {
          e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
        },
        onMouseLeave: (e: any) => {
          e.currentTarget.style.boxShadow = 'none';
        }
      },
        React.createElement('div', { style: { padding: '15px' } },
          React.createElement('div', {
            style: {
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'start',
              marginBottom: '15px'
            }
          },
            React.createElement('div', { className: 'performer-info' },
              React.createElement('div', {
                style: { display: 'flex', alignItems: 'center', marginBottom: '8px' }
              },
                React.createElement('h5', { style: { margin: 0 } }, performer.name),
                React.createElement(Badge, {
                  variant: 'primary',
                  style: { marginLeft: '8px' }
                }, `${frequency} image${frequency > 1 ? 's' : ''}`)
              ),
              React.createElement('div', { className: 'confidence-metrics' },
                React.createElement('small', { style: { color: '#6c757d' } },
                  'Best: ',
                  React.createElement(Badge, {
                    variant: getConfidenceColor(bestConfidence)
                  }, formatConfidence(bestConfidence)),
                  ' Avg: ',
                  React.createElement(Badge, {
                    variant: getConfidenceColor(averageConfidence)
                  }, formatConfidence(averageConfidence))
                )
              ),
              // StashDB link if available (similar to VisageImageResults)
              performer.performer_url ? React.createElement('div', {
                style: { marginTop: '6px' }
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
            ),
            React.createElement('div', { 
              className: 'performer-thumbnail',
              style: {
                width: '60px',
                height: '60px',
                borderRadius: '4px',
                overflow: 'hidden',
                border: '1px solid #dee2e6',
                backgroundColor: '#f8f9fa',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }
            },
              (performer.image || performer.image_url) ? React.createElement('img', {
                src: performer.image_url || performer.image,
                alt: performer.name,
                style: {
                  width: '100%',
                  height: '100%',
                  objectFit: 'cover'
                },
                onError: (e: any) => {
                  console.warn(`Failed to load performer image: ${performer.image_url || performer.image}`);
                  e.target.style.display = 'none';
                  // Show performer initials instead
                  const placeholder = document.createElement('div');
                  placeholder.style.cssText = 'width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; background: #6c5ce7; color: white; font-weight: bold; font-size: 16px;';
                  placeholder.textContent = performer.name.split(' ').map((n: string) => n[0]).join('').toUpperCase().substring(0, 2);
                  e.target.parentNode.appendChild(placeholder);
                }
              }) : React.createElement('div', {
                style: {
                  width: '100%',
                  height: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: '#6c5ce7',
                  color: 'white',
                  fontWeight: 'bold',
                  fontSize: '16px'
                }
              }, performer.name.split(' ').map((n: string) => n[0]).join('').toUpperCase().substring(0, 2))
            )
          ),

          // Gallery-specific actions
          React.createElement('div', {
            className: 'gallery-performer-actions',
            style: { marginBottom: '15px' }
          },
            React.createElement(Button, {
              size: 'sm',
              variant: 'primary',
              style: { marginRight: '8px' },
              disabled: isTagging[`tag_images_${performerFreq.performer.id}`],
              onClick: () => handlePerformerAction(performerFreq, 'tag_all_images')
            }, 
              isTagging[`tag_images_${performerFreq.performer.id}`] ? 
                React.createElement('span', null, '⏳ Tagging...') : 
                `🏷️ Tag All ${frequency} Images`
            ),
            effectiveGalleryData?.id && React.createElement(Button, {
              size: 'sm',
              variant: 'outline-success',
              style: { marginRight: '8px' },
              disabled: isTagging[`tag_gallery_${performerFreq.performer.id}`],
              onClick: () => handlePerformerAction(performerFreq, 'tag_gallery')
            }, 
              isTagging[`tag_gallery_${performerFreq.performer.id}`] ? 
                React.createElement('span', null, '⏳ Tagging...') : 
                '🎯 Tag Gallery'
            ),
            React.createElement(Button, {
              size: 'sm',
              variant: 'outline-secondary',
              onClick: () => handlePerformerAction(performerFreq, 'view')
            }, '👁️ View Details')
          ),

          // Image appearances
          React.createElement('div', { className: 'image-appearances' },
            React.createElement(Button, {
              variant: 'link',
              size: 'sm',
              onClick: () => setSelectedPerformer(isExpanded ? null : `${performer.id}_${index}`),
              style: { padding: 0, marginBottom: '8px' }
            },
              isExpanded ? '🗜️' : '🔍',
              ` ${isExpanded ? 'Hide' : 'Show'} Image Appearances (${frequency})`
            ),

            isExpanded && React.createElement('div', { className: 'appearances-grid' },
              React.createElement(Row, null,
                appearances.map((appearance, appIndex) =>
                  React.createElement(Col, {
                    key: appIndex,
                    xs: 6,
                    md: 4,
                    lg: 3,
                    style: { marginBottom: '8px' }
                  },
                    React.createElement('div', {
                      className: 'appearance-thumbnail',
                      style: { 
                        position: 'relative',
                        borderRadius: '4px',
                        overflow: 'hidden',
                        border: '1px solid #dee2e6',
                        transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                        cursor: 'pointer'
                      },
                      onMouseEnter: (e: any) => {
                        e.currentTarget.style.transform = 'scale(1.02)';
                        e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.15)';
                      },
                      onMouseLeave: (e: any) => {
                        e.currentTarget.style.transform = 'scale(1)';
                        e.currentTarget.style.boxShadow = 'none';
                      },
                      onClick: () => {
                        // Could add click functionality to view full image
                        console.log(`Clicked on appearance image: ${appearance.imageUrl}`);
                      }
                    },
                      React.createElement('img', {
                        src: appearance.imageUrl,
                        alt: `Appearance ${appIndex + 1}`,
                        style: {
                          maxHeight: '80px',
                          objectFit: 'cover',
                          width: '100%',
                          display: 'block'
                        },
                        onError: (e: any) => {
                          // Try fallback URL or show placeholder
                          console.warn(`Failed to load image: ${appearance.imageUrl}`);
                          e.target.style.display = 'none';
                          // Add a placeholder div
                          const placeholder = document.createElement('div');
                          placeholder.style.cssText = 'width: 100%; height: 80px; background: #f8f9fa; display: flex; align-items: center; justify-content: center; color: #6c757d; font-size: 12px;';
                          placeholder.textContent = '🖼️ Image unavailable';
                          e.target.parentNode.appendChild(placeholder);
                        }
                      }),
                      React.createElement('div', {
                        className: 'appearance-overlay',
                        style: {
                          position: 'absolute',
                          top: '4px',
                          right: '4px',
                          zIndex: 10
                        }
                      },
                        React.createElement(Badge, {
                          variant: getConfidenceColor(appearance.confidence),
                          style: {
                            fontSize: '10px',
                            fontWeight: 'bold',
                            padding: '2px 6px'
                          }
                        }, formatConfidence(appearance.confidence))
                      ),
                      // Add image info overlay at bottom
                      React.createElement('div', {
                        style: {
                          position: 'absolute',
                          bottom: '0',
                          left: '0',
                          right: '0',
                          background: 'linear-gradient(transparent, rgba(0,0,0,0.7))',
                          color: 'white',
                          fontSize: '10px',
                          padding: '8px 4px 4px',
                          textAlign: 'center'
                        }
                      }, `Image ${appIndex + 1}`)
                    )
                  )
                )
              )
            )
          )
        )
      );
    };

    const renderProcessingStats = () => {
      if (!galleryResults) return null;

      const successRate = (galleryResults.processedImages / galleryResults.totalImages) * 100;

      return React.createElement('div', {
        key: 'processing-stats',
        style: { 
          marginBottom: '16px',
          padding: '12px',
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          borderRadius: '8px',
          border: '1px solid rgba(255, 255, 255, 0.1)'
        }
      },
        React.createElement('div', {
          style: {
            color: 'white',
            fontSize: '0.9rem'
          }
        }, [
          React.createElement('div', {
            key: 'stats-title',
            style: { 
              marginBottom: '8px',
              fontWeight: '600',
              color: 'rgba(255, 255, 255, 0.9)'
            }
          }, '📊 Processing Statistics'),
          
          React.createElement('div', {
            key: 'stats-content',
            style: {
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '0.8rem',
              color: 'rgba(255, 255, 255, 0.7)'
            }
          }, [
            React.createElement('span', { key: 'total' }, `Total: ${galleryResults.totalImages}`),
            React.createElement('span', { key: 'processed', style: { color: '#4ade80' } }, `✅ ${galleryResults.processedImages}`),
            React.createElement('span', { key: 'success-rate' }, `${successRate.toFixed(1)}% success`),
            galleryResults.performers?.length ? React.createElement('span', { key: 'performers', style: { color: '#60a5fa' } }, `👥 ${galleryResults.performers.length} performers`) : null
          ].filter(Boolean))
        ])
      );
    };

    const renderGalleryResults = () => {
      if (!galleryResults) {
        return React.createElement('div', {
          style: {
            padding: '20px',
            textAlign: 'center',
            color: 'rgba(255, 255, 255, 0.6)'
          }
        }, '🧠 No gallery results to display');
      }

      if (!galleryResults.success) {
        return React.createElement('div', {
          style: {
            padding: '20px',
            textAlign: 'center',
            color: '#f87171'
          }
        }, `❌ Error: ${galleryResults.error || 'Gallery processing failed'}`);
      }

      if (galleryResults.performers.length === 0) {
        return React.createElement('div', {
          style: {
            padding: '20px',
            textAlign: 'center',
            color: '#fbbf24'
          }
        }, `👁️ No performers detected across ${galleryResults.processedImages} processed images`);
      }

      return React.createElement('div', { className: 'gallery-results' }, [
        // Processing Statistics (smaller, condensed version)
        renderProcessingStats(),

        // Performer Frequencies with new dark styling
        ...galleryResults.performers.map((performerFreq, index) =>
          renderPerformerFrequencyCardDark(performerFreq, index)
        )
      ]);
    };

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
            }, '🖼️ ' + (jobData?.job_name || effectiveGalleryData?.title || 'Batch Analysis Results')),
            React.createElement('p', {
              key: 'subtitle',
              style: {
                color: 'rgba(255, 255, 255, 0.6)',
                margin: 0,
                fontSize: '0.9rem'
              }
            }, `Found ${galleryResults?.performers?.length || 0} performer${(galleryResults?.performers?.length || 0) !== 1 ? 's' : ''} across ${galleryResults?.processedImages || 0} processed images`)
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

        // Content Area - Two Panel Layout like VisageImageResults
        React.createElement('div', {
          key: 'content-area',
          style: {
            display: 'flex',
            flex: 1,
            overflow: 'hidden'
          }
        }, [
          // Left Panel - Batch Images Section
          React.createElement('div', {
            key: 'batch-images-section',
            style: {
              flex: 1,
              position: 'relative',
              display: 'flex',
              flexDirection: 'column',
              padding: '20px'
            }
          }, [
            React.createElement('h3', {
              key: 'batch-title',
              style: {
                color: 'white',
                margin: '0 0 16px 0',
                fontSize: '1.1rem',
                fontWeight: '600'
              }
            }, 'Batch Images'),

            // Batch images grid
            React.createElement('div', {
              key: 'batch-images-grid',
              style: {
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))',
                gap: '12px',
                overflowY: 'auto',
                maxHeight: '400px'
              }
            }, galleryResults?.processingResults?.map((result, index) =>
              React.createElement('div', {
                key: `batch-image-${index}`,
                style: {
                  position: 'relative',
                  borderRadius: '8px',
                  overflow: 'hidden',
                  border: '2px solid rgba(255, 255, 255, 0.2)',
                  cursor: 'pointer',
                  transition: 'transform 0.2s ease, border-color 0.2s ease'
                },
                onMouseEnter: (e: any) => {
                  e.currentTarget.style.transform = 'scale(1.05)';
                  e.currentTarget.style.borderColor = 'rgba(74, 144, 226, 0.5)';
                },
                onMouseLeave: (e: any) => {
                  e.currentTarget.style.transform = 'scale(1)';
                  e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.2)';
                },
                onClick: () => {
                  openIndividualImage(result.imageId);
                }
              }, [
                React.createElement('img', {
                  key: 'batch-image',
                  src: result.imageUrl,
                  style: {
                    width: '100%',
                    height: '120px',
                    objectFit: 'cover',
                    display: 'block'
                  },
                  alt: `Batch image ${index + 1}`,
                  onError: (e: any) => {
                    console.warn(`Failed to load batch image: ${result.imageUrl}`);
                    e.target.style.display = 'none';
                    const placeholder = document.createElement('div');
                    placeholder.style.cssText = 'width: 100%; height: 120px; background: #333; display: flex; align-items: center; justify-content: center; color: #666; font-size: 12px;';
                    placeholder.textContent = '🖼️ Image unavailable';
                    e.target.parentNode.appendChild(placeholder);
                  }
                }),
                React.createElement('div', {
                  key: 'batch-image-overlay',
                  style: {
                    position: 'absolute',
                    bottom: '0',
                    left: '0',
                    right: '0',
                    background: 'linear-gradient(transparent, rgba(0,0,0,0.8))',
                    color: 'white',
                    fontSize: '10px',
                    padding: '8px 4px 4px',
                    textAlign: 'center'
                  }
                }, `${result.performers?.length || 0} face${(result.performers?.length || 0) !== 1 ? 's' : ''}`)
              ])
            ) || []),

            // Job Info Section
            React.createElement('div', {
              key: 'job-info',
              style: {
                marginTop: '20px',
                padding: '15px',
                backgroundColor: 'rgba(255, 255, 255, 0.05)',
                borderRadius: '8px',
                border: '1px solid rgba(255, 255, 255, 0.1)'
              }
            }, [
              React.createElement('h6', {
                key: 'job-title',
                style: { color: 'white', marginBottom: '8px' }
              }, 'Job Information'),
              React.createElement('div', {
                key: 'job-details',
                style: { fontSize: '0.85rem', color: 'rgba(255, 255, 255, 0.7)' }
              }, [
                React.createElement('div', { key: 'job-name' }, `Job: ${jobData?.job_name || 'Unknown'}`),
                React.createElement('div', { key: 'job-status' }, `Status: ${jobData?.status || 'Unknown'}`),
                React.createElement('div', { key: 'job-images' }, `Images: ${galleryResults?.totalImages || 0} total, ${galleryResults?.processedImages || 0} processed`),
                React.createElement('div', { key: 'job-id' }, `ID: ${jobData?.job_id || 'Unknown'}`)
              ])
            ])
          ]),

          // Right Panel - Performers Details (like VisageImageResults details panel)
          React.createElement('div', {
            key: 'performers-panel',
            style: {
              width: '400px',
              borderLeft: '1px solid rgba(255, 255, 255, 0.1)',
              padding: '20px',
              overflowY: 'auto'
            }
          }, [
            React.createElement('h3', {
              key: 'performers-title',
              style: {
                color: 'white',
                margin: '0 0 16px 0',
                fontSize: '1.1rem',
                fontWeight: '600'
              }
            }, 'Detected Performers'),

            // Render performers using existing function but with new styling
            renderGalleryResults()
          ])
        ]),

      ]),

      // Individual Image Overlay (VisageImageResults)
      selectedImageOverlay && (window as any).VisageImageResults && (() => {
        // For batch images, we need to provide the image URL directly
        const isBatchImage = selectedImageOverlay.task.input_data?.is_batch_image;
        const imageUrl = isBatchImage 
          ? `data:image/jpeg;base64,${selectedImageOverlay.task.input_data.batch_image_data}`
          : null;
          
        console.log('🖼️ Opening VisageImageResults:', {
          isBatchImage,
          imageUrl: imageUrl ? `${imageUrl.substring(0, 50)}...` : 'none',
          task: selectedImageOverlay.task
        });

        // Create a custom VisageImageResults component that handles batch images
        return React.createElement((window as any).VisageImageResults, {
          key: 'individual-image-overlay',
          task: selectedImageOverlay.task,
          visageResults: selectedImageOverlay.visageResults,
          onClose: () => setSelectedImageOverlay(null),
          React: React,
          // Pass the direct image URL for batch images
          directImageUrl: imageUrl
        });
      })()
    ]);
  };

  // Make the component available globally
  (window as any).AIResultsOverlayGalleries = AIResultsOverlayGalleries;

})();