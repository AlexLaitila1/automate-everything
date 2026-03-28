import type { AgentSkill } from "./types";

export const pingSkill: AgentSkill = {
  name: "ping",
  description: "A simple test skill. Returns 'Pong: <message>'.",
  parameters: {
    type: "object",
    properties: {
      message: {
        type: "string",
        description: "The message to echo back.",
      },
    },
    required: ["message"],
  },
  async execute(args) {
    const message = args.message as string;
    return JSON.stringify({ result: `Pong: ${message}` });
  },
};
