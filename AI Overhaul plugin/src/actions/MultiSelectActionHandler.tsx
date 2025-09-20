// =============================================================================
// Multi-Select Action Handler - Batch operations for selected items
// =============================================================================

import { ActionResult, AISettings } from './ImageActionHandler';
import { MultiSelectContext } from './MultiSelectDetection';

export class MultiSelectActionHandler {

  async execute(action: string, serviceName: string, multiSelectContext: MultiSelectContext, settings: AISettings): Promise<ActionResult> {
    if (action.includes('multi-select-analyze-faces') || action.includes('batch')) {
      return await this.handleMultiSelectFaceAnalysis(serviceName, multiSelectContext, settings);
    }

    return {
      success: false,
      message: `Multi-select action ${action} is not yet implemented`
    };
  }

  private async handleMultiSelectFaceAnalysis(serviceName: string, multiSelectContext: MultiSelectContext, settings: AISettings): Promise<ActionResult> {
    try {
      // Check if ImageHandler is available for batch processing
      const ImageHandler = (window as any).ImageHandler;
      if (!ImageHandler) {
        throw new Error('ImageHandler not available for batch processing');
      }

      const imageHandler = new ImageHandler();

      if (multiSelectContext.selectionType === 'images') {
        const options = {
          maxConcurrent: 2,
          skipErrors: true
        };

        const batchResults = await imageHandler.batchGetImagesWithBase64(
          multiSelectContext.selectedItems,
          options
        );
        
        if (batchResults.length === 0) {
          return {
            success: false,
            message: 'Failed to process any of the selected images'
          };
        }

        // Create batch job
        const jobData = await imageHandler.createBatchJobData(
          batchResults,
          'multi_select_analysis',
          {
            source: 'button_multi_select',
            selection_size: multiSelectContext.selectedItems.length,
            processed_count: batchResults.length
          }
        );

        const images = jobData.tasks.map((task: any) => task.input_data.image_data);
        const jobPayload = {
          images: images,
          visage_api_url: `http://${settings.stashAIServer}:9997/api/predict_1`,
          config: {
            threshold: settings.visageThreshold || 0.7,
            job_name: `Multi-Select Batch: ${multiSelectContext.selectedItems.length} images`,
            user_id: 'ai_overhaul_button',
            session_id: 'multi_select_batch_session',
            additional_params: {
              max_faces: 10,
              return_embeddings: false,
              source: 'ai_overhaul_button_multi_select',
              entity_type: 'image'
            }
          }
        };

        const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/visage/job`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(jobPayload)
        });

        if (!response.ok) {
          throw new Error(`Failed to create batch job: ${response.status} ${response.statusText}`);
        }

        const result = await response.json();

        return {
          success: true,
          message: `${serviceName} batch processing started! Processing ${jobData.tasks.length} selected images as single batch job.`,
          taskId: result.job_id || result.id,
          data: {
            jobId: result.job_id || result.id,
            processedImages: jobData.tasks.length,
            totalSelected: multiSelectContext.selectedItems.length,
            type: 'multi_select_batch'
          }
        };

      } else if (multiSelectContext.selectionType === 'scenes') {
        // Handle multi-select scenes - create individual tasks
        const taskIds: string[] = [];
        let successCount = 0;

        for (const sceneId of multiSelectContext.selectedItems) {
          try {
            const taskData = {
              scene_id: sceneId,
              threshold: settings.visageThreshold || 0.7,
              visage_api_url: `http://${settings.stashAIServer}:9997/api/predict_1`,
              additional_params: {
                max_faces: 10,
                return_embeddings: false,
                source: 'ai_overhaul_multi_select_scenes',
                entity_type: 'scene',
                entity_id: sceneId,
                batch_context: {
                  selection_type: 'multi_select_scenes',
                  batch_size: multiSelectContext.selectedItems.length
                }
              }
            };

            const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/visage/task`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(taskData)
            });

            if (response.ok) {
              const result = await response.json();
              if (result.task_id) {
                taskIds.push(result.task_id);
                successCount++;
              }
            }
          } catch (error) {
            console.error(`Failed to create task for scene ${sceneId}:`, error);
          }
        }

        if (successCount === 0) {
          return {
            success: false,
            message: `Failed to create any ${serviceName} tasks for selected scenes`
          };
        }

        return {
          success: true,
          message: `${serviceName} analysis started for ${successCount} of ${multiSelectContext.selectedItems.length} selected scenes.`,
          data: {
            taskIds,
            successCount,
            totalSelected: multiSelectContext.selectedItems.length,
            type: 'multi_select_scenes'
          }
        };
      }

      return {
        success: false,
        message: `Multi-select ${serviceName} is not yet implemented for ${multiSelectContext.selectionType}`
      };

    } catch (error: any) {
      console.error('Multi-select action failed:', error);
      return {
        success: false,
        message: `Multi-select ${serviceName} failed: ${error.message}`
      };
    }
  }
}