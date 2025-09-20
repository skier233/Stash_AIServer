// =============================================================================
// Actions - Consolidated for Browser Loading
// =============================================================================

// Import all the modular components
import { detectMultiSelectContext, MultiSelectContext } from './actions/MultiSelectDetection';
import { ActionResult, PageContext, AISettings, ImageActionHandler } from './actions/ImageActionHandler';
import { GalleryActionHandler } from './actions/GalleryActionHandler';
import { MultiSelectActionHandler } from './actions/MultiSelectActionHandler';
import { ActionManager } from './actions/ActionManager';

// Make ActionManager available globally
(window as any).ActionManager = ActionManager;

console.log('🚀 Action Manager loaded with clean modular architecture');