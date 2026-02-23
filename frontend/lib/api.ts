import {
  AlertEvent,
  Domain,
  ExecuteRunRequest,
  OpsStatus,
  RobotEnvVar,
  RobotEnvVarUpsertItem,
  RobotListResponse,
  RobotVersion,
  Run,
  RunListResponse,
  RunLog,
  Schedule,
  Service,
  ServiceRunRequest,
  SlaRule,
  Worker
} from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

function authHeaders(token?: string): HeadersInit {
  const resolved = token ?? process.env.NEXT_PUBLIC_API_TOKEN ?? "";
  return resolved ? { Authorization: `Bearer ${resolved}` } : {};
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(errorBody || "Request failed.");
  }
  return (await response.json()) as T;
}

export async function fetchRobots(token?: string): Promise<RobotListResponse> {
  const response = await fetch(`${API_BASE}/robots`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<RobotListResponse>(response);
}

export async function createRobot(payload: unknown, token?: string): Promise<unknown> {
  const response = await fetch(`${API_BASE}/robots`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    },
    body: JSON.stringify(payload)
  });
  return handleResponse<unknown>(response);
}

export async function fetchRobotVersions(robotId: string, token?: string): Promise<RobotVersion[]> {
  const response = await fetch(`${API_BASE}/robots/${robotId}/versions`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<RobotVersion[]>(response);
}

export async function fetchRobotEnvVars(
  robotId: string,
  envName: "PROD" | "HML" | "TEST",
  token?: string
): Promise<RobotEnvVar[]> {
  const response = await fetch(`${API_BASE}/robots/${robotId}/env?env=${envName}`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<RobotEnvVar[]>(response);
}

export async function upsertRobotEnvVars(
  robotId: string,
  envName: "PROD" | "HML" | "TEST",
  items: RobotEnvVarUpsertItem[],
  token?: string
): Promise<RobotEnvVar[]> {
  const response = await fetch(`${API_BASE}/robots/${robotId}/env?env=${envName}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    },
    body: JSON.stringify({ items })
  });
  return handleResponse<RobotEnvVar[]>(response);
}

export async function deleteRobotEnvVar(
  robotId: string,
  envName: "PROD" | "HML" | "TEST",
  key: string,
  token?: string
): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/robots/${robotId}/env/${encodeURIComponent(key)}?env=${envName}`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<{ message: string }>(response);
}

export async function publishRobotVersion(robotId: string, formData: FormData, token?: string): Promise<RobotVersion> {
  const response = await fetch(`${API_BASE}/robots/${robotId}/versions/publish`, {
    method: "POST",
    headers: {
      ...authHeaders(token)
    },
    body: formData
  });
  return handleResponse<RobotVersion>(response);
}

export async function activateRobotVersion(robotId: string, versionId: string, token?: string): Promise<RobotVersion> {
  const response = await fetch(`${API_BASE}/robots/${robotId}/versions/${versionId}/activate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<RobotVersion>(response);
}

export async function executeRun(robotId: string, payload: ExecuteRunRequest, token?: string): Promise<Run> {
  const response = await fetch(`${API_BASE}/runs/${robotId}/execute`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    },
    body: JSON.stringify(payload)
  });
  return handleResponse<Run>(response);
}

export async function fetchRuns(
  token?: string,
  query?: { robotId?: string; serviceId?: string; triggerType?: "MANUAL" | "SCHEDULED" | "RETRY"; status?: string }
): Promise<RunListResponse> {
  const params = new URLSearchParams();
  if (query?.robotId) params.set("robot_id", query.robotId);
  if (query?.serviceId) params.set("service_id", query.serviceId);
  if (query?.triggerType) params.set("trigger_type", query.triggerType);
  if (query?.status) params.set("status", query.status);

  const response = await fetch(`${API_BASE}/runs${params.size ? `?${params.toString()}` : ""}`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<RunListResponse>(response);
}

export async function fetchRun(runId: string, token?: string): Promise<Run> {
  const response = await fetch(`${API_BASE}/runs/${runId}`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<Run>(response);
}

export async function cancelRun(runId: string, token?: string): Promise<Run> {
  const response = await fetch(`${API_BASE}/runs/${runId}/cancel`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<Run>(response);
}

export async function fetchWorkers(token?: string): Promise<Worker[]> {
  const response = await fetch(`${API_BASE}/workers`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<Worker[]>(response);
}

export async function pauseWorker(workerId: string, token?: string): Promise<Worker> {
  const response = await fetch(`${API_BASE}/workers/${workerId}/pause`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<Worker>(response);
}

export async function resumeWorker(workerId: string, token?: string): Promise<Worker> {
  const response = await fetch(`${API_BASE}/workers/${workerId}/resume`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<Worker>(response);
}

export async function fetchOpsStatus(token?: string): Promise<OpsStatus> {
  const response = await fetch(`${API_BASE}/ops/status`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<OpsStatus>(response);
}

export async function createRobotSchedule(robotId: string, payload: unknown, token?: string): Promise<Schedule> {
  const response = await fetch(`${API_BASE}/robots/${robotId}/schedule`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    },
    body: JSON.stringify(payload)
  });
  return handleResponse<Schedule>(response);
}

export async function fetchRobotSchedule(robotId: string, token?: string): Promise<Schedule> {
  const response = await fetch(`${API_BASE}/robots/${robotId}/schedule`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<Schedule>(response);
}

export async function updateRobotSchedule(robotId: string, payload: unknown, token?: string): Promise<Schedule> {
  const response = await fetch(`${API_BASE}/robots/${robotId}/schedule`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    },
    body: JSON.stringify(payload)
  });
  return handleResponse<Schedule>(response);
}

export async function deleteRobotSchedule(robotId: string, token?: string): Promise<void> {
  const response = await fetch(`${API_BASE}/robots/${robotId}/schedule`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(errorBody || "Request failed.");
  }
}

export async function createRobotSla(robotId: string, payload: unknown, token?: string): Promise<SlaRule> {
  const response = await fetch(`${API_BASE}/robots/${robotId}/sla`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    },
    body: JSON.stringify(payload)
  });
  return handleResponse<SlaRule>(response);
}

export async function fetchRobotSla(robotId: string, token?: string): Promise<SlaRule> {
  const response = await fetch(`${API_BASE}/robots/${robotId}/sla`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<SlaRule>(response);
}

export async function updateRobotSla(robotId: string, payload: unknown, token?: string): Promise<SlaRule> {
  const response = await fetch(`${API_BASE}/robots/${robotId}/sla`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    },
    body: JSON.stringify(payload)
  });
  return handleResponse<SlaRule>(response);
}

export async function fetchAlerts(
  token?: string,
  query?: { status?: "open" | "resolved"; type?: AlertEvent["type"]; robotId?: string; limit?: number }
): Promise<AlertEvent[]> {
  const params = new URLSearchParams();
  if (query?.status) params.set("status", query.status);
  if (query?.type) params.set("type", query.type);
  if (query?.robotId) params.set("robot_id", query.robotId);
  if (query?.limit) params.set("limit", String(query.limit));
  const response = await fetch(`${API_BASE}/alerts${params.size ? `?${params.toString()}` : ""}`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<AlertEvent[]>(response);
}

export async function resolveAlert(alertId: string, token?: string): Promise<AlertEvent> {
  const response = await fetch(`${API_BASE}/alerts/${alertId}/resolve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<AlertEvent>(response);
}

export async function fetchDomains(token?: string): Promise<Domain[]> {
  const response = await fetch(`${API_BASE}/domains`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<Domain[]>(response);
}

export async function createDomain(payload: unknown, token?: string): Promise<Domain> {
  const response = await fetch(`${API_BASE}/domains`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    },
    body: JSON.stringify(payload)
  });
  return handleResponse<Domain>(response);
}

export async function updateDomain(domainId: string, payload: unknown, token?: string): Promise<Domain> {
  const response = await fetch(`${API_BASE}/domains/${domainId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    },
    body: JSON.stringify(payload)
  });
  return handleResponse<Domain>(response);
}

export async function deleteDomain(domainId: string, token?: string): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/domains/${domainId}`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<{ message: string }>(response);
}

export async function fetchServices(token?: string, query?: { domainId?: string; enabledOnly?: boolean }): Promise<Service[]> {
  const params = new URLSearchParams();
  if (query?.domainId) params.set("domain_id", query.domainId);
  if (query?.enabledOnly) params.set("enabled_only", "true");

  const response = await fetch(`${API_BASE}/services${params.size ? `?${params.toString()}` : ""}`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<Service[]>(response);
}

export async function fetchService(serviceId: string, token?: string): Promise<Service> {
  const response = await fetch(`${API_BASE}/services/${serviceId}`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<Service>(response);
}

export async function createService(payload: unknown, token?: string): Promise<Service> {
  const response = await fetch(`${API_BASE}/services`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    },
    body: JSON.stringify(payload)
  });
  return handleResponse<Service>(response);
}

export async function updateService(serviceId: string, payload: unknown, token?: string): Promise<Service> {
  const response = await fetch(`${API_BASE}/services/${serviceId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    },
    body: JSON.stringify(payload)
  });
  return handleResponse<Service>(response);
}

export async function deleteService(serviceId: string, token?: string): Promise<{ message: string }> {
  const response = await fetch(`${API_BASE}/services/${serviceId}`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<{ message: string }>(response);
}

export async function fetchDomainServices(slug: string, token?: string, includeDisabled = false): Promise<Service[]> {
  const response = await fetch(`${API_BASE}/domains/${slug}/services?include_disabled=${includeDisabled ? "true" : "false"}`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<Service[]>(response);
}

export async function runService(serviceId: string, payload: ServiceRunRequest, token?: string): Promise<Run> {
  const response = await fetch(`${API_BASE}/services/${serviceId}/run`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    },
    body: JSON.stringify(payload)
  });
  return handleResponse<Run>(response);
}

export async function fetchServiceRuns(serviceId: string, token?: string, limit = 20): Promise<Run[]> {
  const response = await fetch(`${API_BASE}/services/${serviceId}/runs?limit=${limit}`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<Run[]>(response);
}

export async function fetchRunLogs(runId: string, token?: string): Promise<RunLog[]> {
  const response = await fetch(`${API_BASE}/runs/${runId}/logs`, {
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(token)
    }
  });
  return handleResponse<RunLog[]>(response);
}

export function wsLogsUrl(runId: string, token?: string): string {
  const wsBase = process.env.NEXT_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000/api/v1/ws";
  const resolvedToken = token ?? process.env.NEXT_PUBLIC_API_TOKEN ?? "";
  return `${wsBase}/runs/${runId}/logs?token=${encodeURIComponent(resolvedToken)}`;
}
