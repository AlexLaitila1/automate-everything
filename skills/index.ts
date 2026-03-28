import type { AgentSkill } from "./types";
import { pingSkill } from "./pingSkill";

// Add new skills here as you build them during the hackathon.
export const allSkills: AgentSkill[] = [
  pingSkill,
];
