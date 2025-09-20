// =============================================================================
// AI Action Manager - Coordinates all AI actions
// =============================================================================

import { ActionHandler, ActionResult, PageContext, AISettings } from './ActionTypes';
import ImageActionHandler from './ImageActions';
import GalleryActionHandler from './GalleryActions';
import MultiSelectActionHandler, { MultiSelectContext } from './MultiSelectActions';

export class ActionManager {
  private imageHandler: ActionHandler;
  private galleryHandler: ActionHandler;
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
    if (action.startsWith('batch-') || action.includes('multi-select')) {
      const multiSelectContext = MultiSelectActionHandler.detectMultiSelectContext();
      if (multiSelectContext) {
        return await this.multiSelectHandler.execute(action, serviceName, multiSelectContext, settings);
      } else {
        return {
          success: false,
          message: 'Multi-select action requires multiple items to be selected'
        };
      }
    }

    // Route action to appropriate handler based on context or action type
    try {
      switch (context.page) {
        case 'images':
        case 'scenes':
          return await this.imageHandler.execute(action, serviceName, context, settings);
        
        case 'galleries':
          return await this.galleryHandler.execute(action, serviceName, context, settings);
        
        case 'performers':
          // TODO: Add performer-specific actions
          return {
            success: false,
            message: `${serviceName} analysis is not yet implemented for performer pages`
          };
        
        default:
          return {
            success: false,
            message: `${serviceName} analysis is not available for this page type`
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

  // Get available actions for a specific context
  getAvailableActions(context: PageContext): string[] {
    const actions: string[] = [];

    // Check for multi-select actions first
    const multiSelectContext = MultiSelectActionHandler.detectMultiSelectContext();
    if (multiSelectContext) {
      actions.push(...this.multiSelectHandler.getAvailableActions(multiSelectContext));
    }

    // Add context-specific actions
    switch (context.page) {
      case 'images':
      case 'scenes':
        if (context.isDetailView) {
          actions.push('analyze-faces', 'analyze-content');
        }
        break;
      
      case 'galleries':
        if (context.isDetailView && this.galleryHandler instanceof GalleryActionHandler) {
          actions.push(...this.galleryHandler.getAvailableActions(context));
        }
        break;
      
      case 'performers':
        if (context.isDetailView) {
          actions.push('analyze-performer');
        }
        break;
    }

    return actions;
  }

  // Check if multi-select actions are available
  hasMultiSelectActions(): boolean {
    const multiSelectContext = MultiSelectActionHandler.detectMultiSelectContext();
    return multiSelectContext !== null && multiSelectContext.selectedItems.length > 1;
  }

  // Get multi-select context if available
  getMultiSelectContext(): MultiSelectContext | null {
    return MultiSelectActionHandler.detectMultiSelectContext();
  }
}

export default ActionManager;