# AI Overhaul Plugin

Advanced AI integration plugin for Stash that provides face recognition, content analysis, and batch processing capabilities.

## 🏗️ Architecture Overview

The AI Overhaul plugin uses a clean, modular architecture designed for maintainability and easy expansion:

```
src/
├── actions/                    # Modular action handlers
│   ├── MultiSelectDetection.tsx    # Multi-select context detection
│   ├── ImageActionHandler.tsx      # Image & scene face analysis
│   ├── GalleryActionHandler.tsx    # Gallery batch processing  
│   ├── MultiSelectActionHandler.tsx # Multi-select batch operations
│   ├── ActionManager.tsx           # Main coordinator
│   └── index.ts                   # Clean exports
├── utils/                     # Shared utilities
│   ├── UniversalGraphQL.tsx        # GraphQL queries
│   ├── MutateGraphQL.tsx          # GraphQL mutations
│   └── SVGIcons.ts               # Icon utilities
├── css/                      # Styling
│   ├── AIOverhaul.css           # Main styles
│   └── AIButton.css            # Button-specific styles
├── AIButton.tsx              # Main AI button component
└── AIButtonIntegration.tsx   # Stash integration
```

## 🚀 Core Components

### ActionManager
The central coordinator that routes actions to appropriate handlers based on context:
- **Image/Scene actions** → `ImageActionHandler`
- **Gallery actions** → `GalleryActionHandler` 
- **Multi-select actions** → `MultiSelectActionHandler`

### AI Button
Responsive button that:
- Auto-detects page context (images, scenes, galleries, etc.)
- Shows contextual AI services based on current page
- Handles multi-select operations automatically
- Integrates with StashAI Server for real AI processing

### Service Discovery
Dynamically discovers available AI services by:
- Reading settings from localStorage
- Health-checking StashAI Server
- Filtering services based on page context
- Supporting multi-select batch operations

## 📋 Current Services

| Service | Description | Supported Pages | Multi-Select |
|---------|-------------|----------------|--------------|
| **Visage** | Face Recognition | Images, Scenes | ✅ |
| **Content Analysis** | Content Classification | Images, Scenes | ✅ |
| **Scene Analysis** | Scene Detection | Scenes | ❌ |
| **Gallery Batch** | Analyze all gallery images | Galleries | ❌ |

## ➕ Adding a New Service

### Step 1: Define the Service

Add your new service to the service discovery in `AIButton.tsx`:

```typescript
const services = [
  // Existing services...
  {
    name: 'Video Analysis',           // Display name
    description: 'Analyze video content',  // Description shown in dropdown
    action: 'analyze-video',          // Action identifier
    icon: '🎥',                      // Emoji or icon
    supportedTypes: ['scene']         // Pages where service appears
  }
];
```

### Step 2: Add Action Handler

Choose the appropriate handler based on your service type:

#### For Single Item Actions (Images/Scenes)
Add to `ImageActionHandler.tsx`:

```typescript
async execute(action: string, serviceName: string, context: PageContext, settings: AISettings): Promise<ActionResult> {
  switch (action) {
    // Existing cases...
    case 'analyze-video':
      return await this.handleVideoAnalysis(serviceName, context, settings);
  }
}

private async handleVideoAnalysis(serviceName: string, context: PageContext, settings: AISettings): Promise<ActionResult> {
  try {
    const taskData = {
      service_type: "video_analysis",
      scene_id: context.entityId,
      config: {
        // Your service-specific config
        api_endpoint: `http://${settings.stashAIServer}:9999/api/analyze_video`,
        source: 'ai_overhaul_button'
      }
    };

    const response = await fetch(`http://${settings.stashAIServer}:${settings.port}/api/video/task`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(taskData)
    });

    if (!response.ok) {
      throw new Error(`Failed to create task: ${response.status} ${response.statusText}`);
    }

    const result = await response.json();

    return {
      success: true,
      message: `${serviceName} task created successfully!`,
      taskId: result.task_id || result.id,
      data: result
    };

  } catch (error: any) {
    return {
      success: false,
      message: `Failed to start ${serviceName}: ${error.message}`
    };
  }
}
```

#### For New Content Types (Performers, Tags, etc.)
Create a new handler file `src/actions/PerformerActionHandler.tsx`:

```typescript
export class PerformerActionHandler {
  async execute(action: string, serviceName: string, context: PageContext, settings: AISettings): Promise<ActionResult> {
    switch (action) {
      case 'analyze-performer':
        return await this.handlePerformerAnalysis(serviceName, context, settings);
      
      default:
        return {
          success: false,
          message: `Unknown performer action: ${action}`
        };
    }
  }

  private async handlePerformerAnalysis(serviceName: string, context: PageContext, settings: AISettings): Promise<ActionResult> {
    // Implementation specific to performer analysis
  }
}
```

Then add it to `ActionManager.tsx`:

```typescript
import { PerformerActionHandler } from './PerformerActionHandler';

export class ActionManager {
  private performerHandler: PerformerActionHandler;

  constructor() {
    // Existing handlers...
    this.performerHandler = new PerformerActionHandler();
  }

  async executeAction(action: string, serviceName: string, context: PageContext, settings: AISettings): Promise<ActionResult> {
    switch (context.page) {
      // Existing cases...
      case 'performers':
        return await this.performerHandler.execute(action, serviceName, context, settings);
    }
  }
}
```

#### For Batch/Multi-Select Support
Add to `MultiSelectActionHandler.tsx`:

```typescript
async execute(action: string, serviceName: string, multiSelectContext: MultiSelectContext, settings: AISettings): Promise<ActionResult> {
  if (action.includes('multi-select-analyze-video')) {
    return await this.handleMultiSelectVideoAnalysis(serviceName, multiSelectContext, settings);
  }
  // Existing logic...
}

private async handleMultiSelectVideoAnalysis(serviceName: string, multiSelectContext: MultiSelectContext, settings: AISettings): Promise<ActionResult> {
  // Implementation for batch video analysis
}
```

### Step 3: Update Service Discovery

Ensure your new service appears in the right contexts by updating the `supportedTypes` array and adding any new page context detection in `AIButton.tsx`.

### Step 4: Recompile and Test

1. **Recompile the modular components:**
```bash
# Update the consolidated ActionManagerModular.js with your new handlers
```

2. **Test your service:**
   - Navigate to the appropriate page type
   - Click the AI button
   - Verify your service appears in the dropdown
   - Test the action execution

## 🔧 Development Tips

### Service Configuration
Services can be configured via the AI Overhaul settings:
- **Server address** and **port** are configurable
- **Service-specific settings** (like thresholds) can be added to settings
- **API endpoints** should be parameterized through settings

### Error Handling
Always provide meaningful error messages:
```typescript
return {
  success: false,
  message: 'Specific error that helps users understand what went wrong'
};
```

### Context Detection
The button automatically detects:
- **Page type** (`images`, `scenes`, `galleries`, etc.)
- **Detail view** (specific item page vs list page)  
- **Entity ID** (the specific item being viewed)
- **Multi-select context** (when multiple items are selected)

### Multi-Select Support
To support multi-select operations:
1. Add your action to `getMultiSelectActions()` in `AIButton.tsx`
2. Implement the batch handler in `MultiSelectActionHandler.tsx`
3. Use `ImageHandler` for batch processing when available

## 🧪 Testing

### Manual Testing
1. **Single item actions**: Navigate to specific image/scene/gallery page and test
2. **Multi-select actions**: Select multiple items and test batch operations
3. **Error cases**: Test with StashAI Server down, invalid settings, etc.
4. **Context switching**: Test service availability across different page types

### Console Debugging
The plugin provides debug logging:
- Service discovery: `🚀 AI Button: Discovering services...`
- Context detection: `🎯 Multi-select detected: X items selected`
- Action execution: Check browser console for API calls and responses

## 🔗 StashAI Server Integration

The plugin integrates with StashAI Server endpoints:
- **Health check**: `GET http://{server}:{port}/health`
- **Individual tasks**: `POST http://{server}:{port}/api/{service}/task`  
- **Batch jobs**: `POST http://{server}:{port}/api/{service}/job`
- **Task cancellation**: `POST http://{server}:{port}/api/queue/cancel/{task_id}`
- **Job details**: `GET http://{server}:{port}/api/queue/job/{job_id}`

### Task Cancellation
The WebSocket manager supports task and job cancellation:
```javascript
// Cancel a single task
const wsManager = new window.AIOverhaulWebSocketManager('http://server:9998');
const result = await wsManager.cancelTask('task-id');

// Cancel all tasks in a job
const jobResult = await wsManager.cancelJob('job-id');
console.log(`Cancelled ${jobResult.cancelledTasks.length} tasks`);
```

Ensure your StashAI Server supports the required endpoints for new services.

## 📝 Configuration

Settings are stored in `localStorage` as `ai_overhaul_settings`:
```json
{
  "stashAIServer": "10.0.0.154",
  "port": "9998", 
  "visageThreshold": 0.7,
  "customServiceSetting": "value"
}
```

## 🤝 Contributing

When adding new services:
1. Follow the modular architecture patterns
2. Add comprehensive error handling  
3. Update this README with your service
4. Test across different contexts (single item, multi-select, error cases)
5. Keep the ActionManager coordinator lightweight - business logic goes in handlers

## 📚 Architecture Benefits

This modular design provides:
- **🔧 Maintainability**: Each handler focuses on one responsibility
- **🚀 Scalability**: Easy to add new services and content types
- **🧪 Testability**: Handlers can be tested independently  
- **📖 Readability**: Clear separation of concerns
- **🔄 Reusability**: GraphQL utilities and patterns can be shared

The plugin is designed to grow with your AI processing needs while maintaining clean, understandable code.