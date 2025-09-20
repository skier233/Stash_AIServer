// =============================================================================
// Multi-Select Action Handlers
// =============================================================================

// Inline interfaces to avoid import issues
interface PageContext {
  page: 'scenes' | 'galleries' | 'images' | 'groups' | 'performers' | 'home' | 'unknown';
  entityId: string | null;
  isDetailView: boolean;
}

interface AISettings {
  stashAIServer: string;
  port: string;
  visageThreshold?: number;
}

interface ActionResult {
  success: boolean;
  message: string;
  taskId?: string;
  data?: any;
}

interface ActionHandler {
  execute(
    action: string,
    serviceName: string,
    context: PageContext,
    settings: AISettings
  ): Promise<ActionResult>;
}

// Extended interface for multi-select context
export interface MultiSelectContext extends PageContext {
  selectedItems: string[];
  selectionType: 'images' | 'scenes' | 'performers' | 'galleries';
}

export class MultiSelectActionHandler implements ActionHandler {
  async execute(
    action: string,
    serviceName: string,
    context: PageContext,
    settings: AISettings
  ): Promise<ActionResult> {
    
    // Ensure we have multi-select context
    const multiContext = context as MultiSelectContext;
    if (!multiContext.selectedItems || multiContext.selectedItems.length === 0) {
      return {
        success: false,
        message: 'No items selected for batch processing'
      };
    }

    switch (action) {
      case 'batch-analyze-faces':
        return this.handleBatchFaceAnalysis(serviceName, multiContext, settings);
      
      case 'batch-analyze-content':
        return this.handleBatchContentAnalysis(serviceName, multiContext, settings);
      
      case 'batch-process-selected':
        return this.handleBatchProcessSelected(serviceName, multiContext, settings);
      
      default:
        return {
          success: false,
          message: `Unknown multi-select action: ${action}`
        };
    }
  }

  private async handleBatchFaceAnalysis(
    serviceName: string,
    context: MultiSelectContext,
    settings: AISettings
  ): Promise<ActionResult> {
    
    const { selectedItems, selectionType } = context;
    
    if (selectionType !== 'images' && selectionType !== 'scenes') {
      return {
        success: false,
        message: 'Face analysis is only available for images and scenes'
      };
    }

    try {
      console.log(`Starting batch face analysis for ${selectedItems.length} ${selectionType}`);

      const taskIds: string[] = [];
      let successCount = 0;
      let errorCount = 0;

      // Process each selected item
      for (const itemId of selectedItems) {
        try {
          let taskData = {};

          if (selectionType === 'images') {
            taskData = {
              image_id: itemId,
              threshold: settings.visageThreshold || 0.7,
              visage_api_url: `http://${settings.stashAIServer}:9997/api/predict_1`,
              additional_params: {
                max_faces: 10,
                return_embeddings: false,
                source: 'ai_overhaul_multi_select',
                entity_type: 'image',
                entity_id: itemId,
                batch_context: {
                  selection_size: selectedItems.length,
                  batch_type: 'multi_select_images'
                }
              }
            };
          } else if (selectionType === 'scenes') {
            taskData = {
              scene_id: itemId,
              threshold: settings.visageThreshold || 0.7,
              visage_api_url: `http://${settings.stashAIServer}:9997/api/predict_1`,
              additional_params: {
                max_faces: 10,
                return_embeddings: false,
                source: 'ai_overhaul_multi_select',
                entity_type: 'scene',
                entity_id: itemId,
                batch_context: {
                  selection_size: selectedItems.length,
                  batch_type: 'multi_select_scenes'
                }
              }
            };
          }

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
            console.error(`Failed to create task for ${itemId}: ${response.status}`);
            errorCount++;
          }
        } catch (error) {
          console.error(`Error creating task for ${itemId}:`, error);
          errorCount++;
        }
      }

      if (successCount === 0) {
        return {
          success: false,
          message: `Failed to start ${serviceName} analysis for any of the ${selectedItems.length} selected ${selectionType}`
        };
      }

      return {
        success: true,
        message: `${serviceName} batch analysis started! Processing ${successCount} of ${selectedItems.length} selected ${selectionType}.${errorCount > 0 ? ` ${errorCount} items failed to start.` : ''} ${taskIds.length} tasks created.`,
        taskId: taskIds.length > 0 ? taskIds[0] : undefined,
        data: {
          taskIds,
          successCount,
          errorCount,
          totalItems: selectedItems.length,
          selectionType,
          type: 'multi_select_batch'
        }
      };

    } catch (error: any) {
      console.error('Batch face analysis failed:', error);
      return {
        success: false,
        message: `${serviceName} batch analysis failed: ${error.message}`
      };
    }
  }

  private async handleBatchContentAnalysis(
    serviceName: string,
    context: MultiSelectContext,
    settings: AISettings
  ): Promise<ActionResult> {
    
    // Placeholder for content analysis implementation
    return {
      success: false,
      message: `${serviceName} batch content analysis is not yet implemented for ${context.selectionType}`
    };
  }

  private async handleBatchProcessSelected(
    serviceName: string,
    context: MultiSelectContext,
    settings: AISettings
  ): Promise<ActionResult> {
    
    const { selectedItems, selectionType } = context;

    // For images, use the ImageHandler batch processing
    if (selectionType === 'images') {
      return this.handleBatchImageProcessing(serviceName, context, settings);
    }

    return {
      success: false,
      message: `Batch processing is not yet implemented for ${selectionType}`
    };
  }

  private async handleBatchImageProcessing(
    serviceName: string,
    context: MultiSelectContext,
    settings: AISettings
  ): Promise<ActionResult> {
    
    const { selectedItems } = context;
    
    try {
      console.log(`Starting batch image processing for ${selectedItems.length} selected images`);

      // Get ImageHandler
      const ImageHandler = (window as any).ImageHandler;
      if (!ImageHandler) {
        throw new Error('ImageHandler not available');
      }

      const imageHandler = new ImageHandler();

      // Set up progress tracking
      let processedCount = 0;
      const options = {
        maxConcurrent: 2,
        skipErrors: true,
        onProgress: (processed: number, total: number, current?: any) => {
          processedCount = processed;
          console.log(`Multi-select processing progress: ${processed}/${total}${current ? ` - ${current.title || current.id}` : ''}`);
        },
        onError: (error: Error, imageData: any) => {
          console.error(`Error processing selected image ${imageData.id}:`, error);
        }
      };

      // Process selected images with batch handler
      const batchResults = await imageHandler.batchGetImagesWithBase64(selectedItems, options);
      
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
          selection_size: selectedItems.length,
          processed_count: batchResults.length
        }
      );

      // Submit as batch job or individual tasks
      const taskIds: string[] = [];
      
      for (const task of jobData.tasks) {
        const taskData = {
          image_id: task.input_data.entity_id,
          threshold: settings.visageThreshold || 0.7,
          visage_api_url: `http://${settings.stashAIServer}:9997/api/predict_1`,
          additional_params: {
            ...task.metadata,
            max_faces: 10,
            source: 'ai_overhaul_multi_select_batch',
            entity_type: 'image',
            entity_id: task.input_data.entity_id,
            batch_context: {
              selection_type: 'multi_select',
              batch_size: jobData.tasks.length,
              original_selection_size: selectedItems.length
            }
          }
        };

        try {
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
          }
        } catch (error) {
          console.error(`Failed to create task for image ${task.input_data.entity_id}:`, error);
        }
      }

      return {
        success: true,
        message: `${serviceName} batch processing started! Processing ${batchResults.length} of ${selectedItems.length} selected images. ${taskIds.length} tasks created.`,
        taskId: taskIds.length > 0 ? taskIds[0] : undefined,
        data: {
          taskIds,
          processedImages: batchResults.length,
          totalSelected: selectedItems.length,
          skippedImages: selectedItems.length - batchResults.length,
          type: 'multi_select_batch'
        }
      };

    } catch (error: any) {
      console.error('Batch image processing failed:', error);
      return {
        success: false,
        message: `${serviceName} batch processing failed: ${error.message}`
      };
    }
  }

  // Get available actions for multi-select context
  getAvailableActions(context: MultiSelectContext): string[] {
    const actions: string[] = [];

    if (context.selectedItems && context.selectedItems.length > 1) {
      switch (context.selectionType) {
        case 'images':
          actions.push('batch-analyze-faces', 'batch-process-selected');
          break;
        case 'scenes':
          actions.push('batch-analyze-faces');
          break;
        case 'performers':
          // Future: batch performer analysis
          break;
        case 'galleries':
          // Future: batch gallery processing
          break;
      }
    }

    return actions;
  }

  // Helper method to detect multi-select context
  static detectMultiSelectContext(): MultiSelectContext | null {
    try {
      // Determine current page context first
      const pathname = window.location.pathname;
      let page: PageContext['page'] = 'unknown';
      let selectionType: 'images' | 'scenes' | 'performers' | 'galleries' = 'images';
      
      if (pathname.includes('/images')) {
        page = 'images';
        selectionType = 'images';
      } else if (pathname.includes('/scenes')) {
        page = 'scenes';
        selectionType = 'scenes';
      } else if (pathname.includes('/galleries')) {
        page = 'galleries';
        selectionType = 'galleries';
      } else if (pathname.includes('/performers')) {
        page = 'performers';
        selectionType = 'performers';
      }

      // Look for selected elements using Stash's actual selection classes
      const selectedElements = document.querySelectorAll(
        '.grid-card.selected, .card.selected, .grid-item.selected, [data-selected="true"]'
      );
      
      if (selectedElements.length <= 1) {
        return null; // Need multiple selections
      }

      const selectedItems: string[] = [];

      // Extract IDs from Stash's card structure
      for (let i = 0; i < selectedElements.length; i++) {
        const element = selectedElements[i];
        let id = null;
        
        // Try to extract ID from data attributes first (most reliable)
        id = element.getAttribute('data-id') || 
             element.getAttribute('data-image-id') ||
             element.getAttribute('data-scene-id') ||
             element.getAttribute('data-performer-id') ||
             element.getAttribute('data-gallery-id');

        // If no data attribute, try to extract from href attributes
        if (!id) {
          const link = element.querySelector('a[href]');
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
          const allLinks = element.querySelectorAll('a[href]');
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
        console.log('MultiSelectActions: Found', selectedElements.length, 'selected elements but extracted', selectedItems.length, 'IDs');
        return null;
      }

      console.log('MultiSelectActions detected:', {
        selectedItems: selectedItems.length,
        selectionType,
        page,
        pathname
      });

      return {
        page,
        entityId: null, // Not applicable for multi-select
        isDetailView: false, // Multi-select is typically in list views
        selectedItems,
        selectionType
      };

    } catch (error) {
      console.error('Error detecting multi-select context:', error);
      return null;
    }
  }
}

export default MultiSelectActionHandler;