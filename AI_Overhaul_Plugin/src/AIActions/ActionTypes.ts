// =============================================================================
// AI Action Types and Interfaces
// =============================================================================

export interface PageContext {
  page: 'scenes' | 'galleries' | 'images' | 'groups' | 'performers' | 'home' | 'unknown';
  entityId: string | null;
  isDetailView: boolean;
}

export interface AISettings {
  stashAIServer: string;
  port: string;
  visageThreshold?: number;
}

export interface ActionResult {
  success: boolean;
  message: string;
  taskId?: string;
  data?: any;
}

export interface ActionHandler {
  execute(
    action: string,
    serviceName: string,
    context: PageContext,
    settings: AISettings
  ): Promise<ActionResult>;
}