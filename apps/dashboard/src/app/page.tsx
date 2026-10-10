import type { Metadata } from "next";
import AgentWorkspace from "@/components/agent/AgentWorkspace";
export const metadata: Metadata = {
  title: "Pramāna Quant Terminal",
  description: "A local agent workspace for live economic signals, PRISM filtering, and evidence replay.",
};
export default function Page() { return <AgentWorkspace />; }
