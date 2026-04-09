import { useState, useEffect, useCallback } from 'react';

export interface AgentMapCommand {
  type: 'MAP_HIGHLIGHT' | 'MAP_SHOW_COMPETITORS' | 'MAP_CLEAR' | 'MAP_TRIGGER_STRATEGY' | 'MAP_PULSE_NODE' | 'MAP_TRIGGER_SIMULATION';
  route_id?: string;
  node_id?: string;
  rationale?: string;
  intent?: string;
  efficiency?: number;
  competitors?: any[];
  strategy?: any;
  event_type?: string;
  markers?: { coord: number[], label: string, color: string }[];
  procurement_path?: number[][];
}

export function useAgentMapInteraction() {
  const [activeCommand, setActiveCommand] = useState<AgentMapCommand | null>(null);

  useEffect(() => {
    const handler = (e: any) => {
      if (e.detail) {
        setActiveCommand(e.detail);
      }
    };
    window.addEventListener('AGENT_MAP_COMMAND', handler);
    return () => window.removeEventListener('AGENT_MAP_COMMAND', handler);
  }, []);

  const clearCommand = useCallback(() => {
    setActiveCommand(null);
  }, []);

  return { activeCommand, clearCommand };
}

export function dispatchAgentMapCommand(command: AgentMapCommand) {
  window.dispatchEvent(new CustomEvent('AGENT_MAP_COMMAND', { detail: command }));
}
