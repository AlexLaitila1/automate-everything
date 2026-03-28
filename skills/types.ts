export interface JsonSchema {
  type: "object";
  properties: Record<string, {
    type: string;
    description: string;
    enum?: string[];
  }>;
  required?: string[];
}

export interface AgentSkill {
  name: string;
  description: string;
  parameters: JsonSchema;
  execute: (args: Record<string, unknown>) => Promise<string>;
}
