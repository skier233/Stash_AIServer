// =============================================================================
// Action Manager - Clean coordinator for all AI actions
// =============================================================================

import { ActionResult, PageContext, AISettings, ImageActionHandler } from './ImageActionHandler';
import { GalleryActionHandler } from './GalleryActionHandler';
import { MultiSelectActionHandler } from './MultiSelectActionHandler';
import { detectMultiSelectContext } from './MultiSelectDetection';

export class ActionManager {
  private imageHandler: ImageActionHandler;
  private galleryHandler: GalleryActionHandler;
  private multiSelectHandler: MultiSelectActionHandler;

  constructor() {
    this.imageHandler = new ImageActionHandler();
    this.galleryHandler = new GalleryActionHandler();
    this.multiSelectHandler = new MultiSelectActionHandler();
  }

  async executeAction(
    action: string,
    serviceName: string,
    context: PageContext,
    settings: AISettings
  ): Promise<ActionResult> {
    
    // Validate settings
    if (!settings) {
      return {
        success: false,
        message: 'AI Overhaul settings not found. Please configure in Settings > Tools > AI Overhaul Settings.'
      };
    }

    // Check for multi-select actions first
    if (action.startsWith('multi-select-') || action.includes('batch')) {
      const multiSelectContext = detectMultiSelectContext();
      if (multiSelectContext) {
        return await this.multiSelectHandler.execute(action, serviceName, multiSelectContext, settings);
      } else {
        return {
          success: false,
          message: 'Multi-select action requires multiple items to be selected'
        };
      }
    }

    // Route to appropriate handler based on context page
    try {
      switch (context.page) {
        case 'images':
        case 'scenes':
          return await this.imageHandler.execute(action, serviceName, context, settings);
        
        case 'galleries':
          return await this.galleryHandler.execute(action, serviceName, context, settings);
        
        case 'performers':
        case 'groups':
          return {
            success: false,
            message: `${serviceName} analysis is not yet implemented for ${context.page} pages`
          };
        
        default:
          return {
            success: false,
            message: `${serviceName} analysis is not available for this page type (${context.page})`
          };
      }
    } catch (error: any) {
      console.error('Action execution failed:', error);
      return {
        success: false,
        message: `Action failed: ${error.message}`
      };
    }
  }
}