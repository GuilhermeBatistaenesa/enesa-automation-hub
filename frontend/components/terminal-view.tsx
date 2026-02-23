"use client";

import { useEffect, useRef } from "react";

import { RunLog } from "@/lib/types";

export function TerminalView({ logs }: { logs: RunLog[] }) {
  const terminalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="terminal" ref={terminalRef}>
      {logs.length === 0 ? <p className="terminal-empty">Nenhum log recebido ainda.</p> : null}
      {logs.map((entry) => (
        <p key={`${entry.timestamp}-${entry.id}`} className={`terminal-line level-${entry.level.toLowerCase()}`}>
          <span className="terminal-ts">{new Date(entry.timestamp).toLocaleTimeString()}</span>
          <span>[{entry.level}]</span>
          <span>{entry.message}</span>
        </p>
      ))}
    </div>
  );
}
