import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  Filter,
  Mail,
  MessageSquare,
  ShieldAlert,
  UserMinus,
  UserPlus,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import HRConversationSidebar from "@/components/HRConversationSidebar";
import MyRequestsPanel, { type EscalatedRequest } from "@/components/MyRequestsPanel";
import type { Conversation } from "@/components/ConversationSidebar";
import { useAuth } from "@/contexts/AuthContext";
import {
  assignHRRequest,
  changeHRRequestPriority,
  escalateHRRequest,
  fetchHRRequestDetail,
  fetchHRRequests,
  fetchSessions,
  messageHRRequestRequester,
  transitionHRRequestStatus,
  type BackendHRRequest,
  type BackendHRRequestDetail,
} from "@/lib/backend";

type Priority = "P0" | "P1" | "P2";
type Status =
  | "NEW"
  | "NEEDS_INFO"
  | "READY"
  | "IN_PROGRESS"
  | "RESOLVED"
  | "ESCALATED"
  | "CANCELLED";

export type HROpsQueueFilters = {
  priority: "all" | Priority;
  requester: string;
  summary: string;
  type: "all" | string;
  status: "all" | Status;
  assignee: string;
};

const DEFAULT_QUEUE_FILTERS: HROpsQueueFilters = {
  priority: "all",
  requester: "",
  summary: "",
  type: "all",
  status: "all",
  assignee: "",
};

function countActiveQueueFilters(filters: HROpsQueueFilters): number {
  let count = 0;
  if (filters.priority !== "all") count += 1;
  if (filters.requester.trim()) count += 1;
  if (filters.summary.trim()) count += 1;
  if (filters.type !== "all") count += 1;
  if (filters.status !== "all") count += 1;
  if (filters.assignee.trim()) count += 1;
  return count;
}

const priorityConfig: Record<Priority, { label: string; className: string }> = {
  P0: {
    label: "P0",
    className: "bg-destructive/10 text-destructive border-destructive/20",
  },
  P1: {
    label: "P1",
    className: "bg-warning/10 text-warning border-warning/20",
  },
  P2: {
    label: "P2",
    className: "bg-muted text-muted-foreground border-border",
  },
};

const statusConfig: Record<Status, { label: string; icon: typeof Clock; color: string }> = {
  NEW: { label: "New", icon: AlertTriangle, color: "text-warning" },
  NEEDS_INFO: { label: "Needs Info", icon: MessageSquare, color: "text-amber-500" },
  READY: { label: "Ready", icon: Clock, color: "text-info" },
  IN_PROGRESS: { label: "In Progress", icon: Clock, color: "text-info" },
  ESCALATED: { label: "Escalated", icon: ShieldAlert, color: "text-destructive" },
  RESOLVED: { label: "Resolved", icon: CheckCircle2, color: "text-emerald-500" },
  CANCELLED: { label: "Cancelled", icon: XCircle, color: "text-muted-foreground" },
};

const DUE_SOON_HOURS = 24;

const priorityOrder: Record<Priority, number> = {
  P0: 0,
  P1: 1,
  P2: 2,
};

const riskOrder: Record<BackendHRRequest["risk_level"], number> = {
  HIGH: 0,
  MED: 1,
  LOW: 2,
};

function mapPriority(p: string | null | undefined): Priority {
  if (p === "P0" || p === "P1" || p === "P2") return p;
  return "P2";
}

function toTypeLabel(item: BackendHRRequest): string {
  return `${item.type || "General"} / ${item.subtype || "General"}`;
}

function toTimestamp(iso?: string | null): number | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.getTime();
}

function isReadyLikeStatus(status: Status): boolean {
  return status === "READY" || status === "IN_PROGRESS";
}

function shouldKeepNeedsInfoAhead(
  needsInfoItem: BackendHRRequest,
  otherItem: BackendHRRequest
): boolean {
  if (mapPriority(needsInfoItem.priority) !== "P0") return false;
  const needsInfoSla = toTimestamp(needsInfoItem.sla_due_at);
  if (needsInfoSla === null) return false;
  const otherSla = toTimestamp(otherItem.sla_due_at);
  if (otherSla === null) return true;
  return needsInfoSla < otherSla;
}

export function compareHRQueueOrder(
  a: BackendHRRequest,
  b: BackendHRRequest
): number {
  const priorityDiff = priorityOrder[mapPriority(a.priority)] - priorityOrder[mapPriority(b.priority)];
  if (priorityDiff !== 0) return priorityDiff;

  const aSla = toTimestamp(a.sla_due_at) ?? Number.POSITIVE_INFINITY;
  const bSla = toTimestamp(b.sla_due_at) ?? Number.POSITIVE_INFINITY;
  if (aSla !== bSla) return aSla - bSla;

  const aRisk = riskOrder[a.risk_level] ?? riskOrder.LOW;
  const bRisk = riskOrder[b.risk_level] ?? riskOrder.LOW;
  if (aRisk !== bRisk) return aRisk - bRisk;

  const aIsNeedsInfo = a.status === "NEEDS_INFO";
  const bIsNeedsInfo = b.status === "NEEDS_INFO";
  const aIsReadyLike = isReadyLikeStatus(a.status);
  const bIsReadyLike = isReadyLikeStatus(b.status);

  if (aIsNeedsInfo && bIsReadyLike) {
    if (!shouldKeepNeedsInfoAhead(a, b)) return 1;
  } else if (bIsNeedsInfo && aIsReadyLike) {
    if (!shouldKeepNeedsInfoAhead(b, a)) return -1;
  }

  const aGroup = aIsReadyLike ? 0 : aIsNeedsInfo ? 1 : 2;
  const bGroup = bIsReadyLike ? 0 : bIsNeedsInfo ? 1 : 2;
  if (aGroup !== bGroup) return aGroup - bGroup;

  const aCreated = toTimestamp(a.created_at) ?? Number.POSITIVE_INFINITY;
  const bCreated = toTimestamp(b.created_at) ?? Number.POSITIVE_INFINITY;
  if (aCreated !== bCreated) return aCreated - bCreated;

  return a.request_id - b.request_id;
}

export function sortHRQueue(items: BackendHRRequest[]): BackendHRRequest[] {
  return [...items].sort(compareHRQueueOrder);
}

export function isBlockedNeedsInfo(item: BackendHRRequest): boolean {
  return item.status === "NEEDS_INFO" || (item.missing_fields?.length ?? 0) > 0;
}

export function isDueSoon(
  item: BackendHRRequest,
  now: Date = new Date(),
  windowHours: number = DUE_SOON_HOURS
): boolean {
  if (item.status === "RESOLVED" || item.status === "CANCELLED") return false;
  const dueAt = toTimestamp(item.sla_due_at);
  if (dueAt === null) return false;
  const nowTs = now.getTime();
  const maxTs = nowTs + windowHours * 60 * 60 * 1000;
  return dueAt >= nowTs && dueAt <= maxTs;
}

function toSessionPreview(session: {
  title?: string | null;
  turn_count: number;
  created_at: string;
}): string {
  if (session.title && session.title.trim()) return session.title;
  if (session.turn_count > 0) {
    return `Conversation ${new Date(session.created_at).toLocaleDateString()}`;
  }
  return "New conversation";
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleString();
}

export function toPanelRequestStatus(
  status: BackendHRRequest["status"],
  assigneeUserId?: string | null
): EscalatedRequest["status"] {
  if (status === "RESOLVED" || status === "CANCELLED") return "resolved";
  if (status === "NEEDS_INFO") return "in_review";
  if (status === "IN_PROGRESS" || status === "ESCALATED") return "in_progress";
  if (assigneeUserId) return "assigned";
  return "pending";
}

export function matchesHROpsQueueFilters(
  item: BackendHRRequest,
  filters: HROpsQueueFilters
): boolean {
  const priority = mapPriority(item.priority);
  if (filters.priority !== "all" && priority !== filters.priority) return false;

  if (filters.requester.trim()) {
    const requesterNeedle = filters.requester.trim().toLowerCase();
    const requesterHaystack = `${item.requester_name || ""} ${item.requester_user_id || ""}`.toLowerCase();
    if (!requesterHaystack.includes(requesterNeedle)) return false;
  }

  if (filters.summary.trim()) {
    const summaryNeedle = filters.summary.trim().toLowerCase();
    if (!item.summary.toLowerCase().includes(summaryNeedle)) return false;
  }

  if (filters.type !== "all" && toTypeLabel(item) !== filters.type) return false;

  if (filters.status !== "all" && item.status !== filters.status) return false;

  if (filters.assignee.trim()) {
    const assigneeNeedle = filters.assignee.trim().toLowerCase();
    const assigneeHaystack = (
      item.assignee_name ||
      item.assignee_user_id ||
      "Unassigned"
    ).toLowerCase();
    if (!assigneeHaystack.includes(assigneeNeedle)) return false;
  }

  return true;
}

function toMyRequest(
  item: BackendHRRequest,
  detail: BackendHRRequestDetail | null
): EscalatedRequest {
  const status = toPanelRequestStatus(item.status, item.assignee_user_id);

  const panelPriority =
    item.priority === "P0" ? "critical" : item.priority === "P1" ? "high" : "medium";

  return {
    id: String(item.request_id),
    summary: item.summary.length > 60 ? `${item.summary.slice(0, 60)}...` : item.summary,
    fullSummary: `${item.requester_name || item.requester_user_id}: ${item.description}`,
    aiResponse:
      item.last_message_to_requester ||
      item.resolution_text ||
      "No latest update has been recorded yet.",
    status,
    priority: panelPriority,
    category: `${item.type} / ${item.subtype}`,
    timestamp: new Date(item.created_at),
    auditLog:
      detail?.timeline?.map((event) => ({
        label: event.event_note || event.event_type.replace(/_/g, " "),
        timestamp: new Date(event.created_at),
      })) || [
        { label: "Request created", timestamp: new Date(item.created_at) },
        { label: "Last update", timestamp: new Date(item.updated_at) },
      ],
  };
}

export default function HROps() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [requestsOpen, setRequestsOpen] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [queueFilters, setQueueFilters] = useState<HROpsQueueFilters>(DEFAULT_QUEUE_FILTERS);
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState<BackendHRRequest[]>([]);
  const [detailById, setDetailById] = useState<Record<number, BackendHRRequestDetail>>({});
  const [messageDraft, setMessageDraft] = useState<Record<number, string>>({});
  const [resolutionNotes, setResolutionNotes] = useState<Record<number, string>>({});

  const currentUserEmail = user?.email?.toLowerCase() || "";

  const loadRequests = useCallback(async () => {
    if (!user?.email) return;
    const rows = await fetchHRRequests(user.email);
    setItems(rows);
  }, [user?.email]);

  const loadDetail = useCallback(
    async (requestId: number) => {
      if (!user?.email) return;
      const detail = await fetchHRRequestDetail(user.email, requestId);
      setDetailById((prev) => ({ ...prev, [requestId]: detail }));
    },
    [user?.email]
  );

  const syncRequest = useCallback(
    async (requestId: number) => {
      if (!user?.email) return;
      const detail = await fetchHRRequestDetail(user.email, requestId);
      setDetailById((prev) => ({ ...prev, [requestId]: detail }));
      setItems((prev) =>
        prev.map((item) => (item.request_id === requestId ? detail.request : item))
      );
    },
    [user?.email]
  );

  useEffect(() => {
    if (!user?.email) return;
    let cancelled = false;
    const bootstrap = async () => {
      setLoading(true);
      try {
        const rows = await fetchHRRequests(user.email);
        if (!cancelled) setItems(rows);
      } catch (error: any) {
        toast.error(error?.message || "Failed to load HR queue");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [user?.email]);

  useEffect(() => {
    if (!user?.email) return;
    let cancelled = false;

    const loadSessions = async () => {
      try {
        const sessions = await fetchSessions(user.email);
        if (cancelled) return;
        setConversations(
          sessions
            .map((session) => ({
              id: session.session_id,
              preview: toSessionPreview(session),
              timestamp: new Date(session.created_at),
            }))
            .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
        );
      } catch {
        // Keep dashboard usable if chat sessions fail to load.
      }
    };

    void loadSessions();
    return () => {
      cancelled = true;
    };
  }, [user?.email]);

  const handleExpand = async (requestId: number) => {
    const isExpanded = expandedId === requestId;
    setExpandedId(isExpanded ? null : requestId);
    if (isExpanded || detailById[requestId]) return;
    try {
      await loadDetail(requestId);
    } catch (error: any) {
      toast.error(error?.message || "Failed to load request detail");
    }
  };

  const runAction = async (
    requestId: number,
    action: () => Promise<unknown>,
    successMessage: string
  ) => {
    try {
      await action();
      toast.success(successMessage);
      try {
        await syncRequest(requestId);
      } catch {
        await loadRequests();
      }
    } catch (error: any) {
      toast.error(error?.message || "Action failed");
    }
  };

  const typeOptions = useMemo(
    () =>
      Array.from(new Set(items.map((item) => toTypeLabel(item)))).sort((a, b) =>
        a.localeCompare(b)
      ),
    [items]
  );

  const filtered = useMemo(
    () => items.filter((item) => matchesHROpsQueueFilters(item, queueFilters)),
    [items, queueFilters]
  );
  const activeFilterCount = useMemo(
    () => countActiveQueueFilters(queueFilters),
    [queueFilters]
  );

  const assignedToMeAll = filtered.filter(
    (item) => (item.assignee_user_id || "").toLowerCase() === currentUserEmail
  );
  const unresolved = filtered.filter(
    (item) => item.status !== "RESOLVED" && item.status !== "CANCELLED"
  );
  const closed = filtered.filter(
    (item) => item.status === "RESOLVED" || item.status === "CANCELLED"
  );
  const needsInfo = unresolved.filter((item) => isBlockedNeedsInfo(item));
  const escalated = unresolved.filter((item) => item.status === "ESCALATED");
  const dueSoon = unresolved.filter((item) => isDueSoon(item));
  const unassigned = unresolved.filter((item) => !item.assignee_user_id);
  const assignedToMe = unresolved.filter(
    (item) => (item.assignee_user_id || "").toLowerCase() === currentUserEmail
  );
  const assignedToOthers = unresolved.filter(
    (item) =>
      !!item.assignee_user_id &&
      (item.assignee_user_id || "").toLowerCase() !== currentUserEmail
  );

  const assignedRequests = sortHRQueue(assignedToMeAll).map((item) =>
    toMyRequest(item, detailById[item.request_id] || null)
  );

  return (
    <div className="min-h-screen flex w-full">
      <HRConversationSidebar
        activeConversationId={activeConversation}
        conversations={conversations}
        onSelectConversation={(id) => {
          setActiveConversation(id);
          navigate("/hr-chat");
        }}
        onNewConversation={() => navigate("/hr-chat")}
        onDeleteConversation={(id) => {
          setConversations((prev) => prev.filter((c) => c.id !== id));
          if (activeConversation === id) setActiveConversation(null);
        }}
        onClearAll={() => {
          setConversations([]);
          setActiveConversation(null);
        }}
        assignedCount={assignedToMeAll.length}
      />

      <main className="flex-1 flex flex-col min-w-0 h-screen overflow-auto">
        <header className="flex items-center justify-between px-6 py-3 border-b bg-card">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-base text-primary">PingHR</span>
            <span className="text-muted-foreground text-sm">/ HR Ops Dashboard</span>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="gap-2 text-primary border-primary/30 hover:bg-primary/5"
            onClick={() => setRequestsOpen(true)}
          >
            <Mail className="h-4 w-4" />
            My Requests
            {assignedToMeAll.length > 0 && (
              <span className="ml-1 h-5 min-w-5 px-1 rounded-full bg-destructive text-destructive-foreground text-[10px] font-bold flex items-center justify-center">
                {assignedToMeAll.length}
              </span>
            )}
          </Button>
        </header>

        <div className="p-6 max-w-7xl mx-auto w-full">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-2xl font-bold mb-1">HR Request Queue</h1>
              <p className="text-muted-foreground text-sm">
                {filtered.length} shown ({items.length} total) · {unresolved.length} active ·{" "}
                {closed.length} closed
              </p>
            </div>
          </div>

          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div className="text-xs text-muted-foreground">
              {activeFilterCount > 0
                ? `${activeFilterCount} active filter${activeFilterCount === 1 ? "" : "s"}`
                : "No active filters"}
            </div>
            <div className="flex items-center gap-2">
              {activeFilterCount > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setQueueFilters(DEFAULT_QUEUE_FILTERS)}
                >
                  Reset
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                onClick={() => setShowFilters((prev) => !prev)}
              >
                <Filter className="h-3.5 w-3.5" />
                {showFilters ? "Hide Filters" : "Show Filters"}
              </Button>
            </div>
          </div>

          {showFilters && (
            <div className="mb-6 rounded-xl border bg-card p-3">
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
                <Select
                  value={queueFilters.priority}
                  onValueChange={(value) =>
                    setQueueFilters((prev) => ({
                      ...prev,
                      priority: value as HROpsQueueFilters["priority"],
                    }))
                  }
                >
                  <SelectTrigger className="h-9 text-sm" aria-label="Filter by priority">
                    <SelectValue placeholder="Priority" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All priorities</SelectItem>
                    <SelectItem value="P0">P0</SelectItem>
                    <SelectItem value="P1">P1</SelectItem>
                    <SelectItem value="P2">P2</SelectItem>
                  </SelectContent>
                </Select>

                <Input
                  value={queueFilters.requester}
                  onChange={(e) =>
                    setQueueFilters((prev) => ({ ...prev, requester: e.target.value }))
                  }
                  placeholder="Requester"
                  className="h-9 text-sm"
                  aria-label="Filter by requester"
                />

                <Input
                  value={queueFilters.summary}
                  onChange={(e) =>
                    setQueueFilters((prev) => ({ ...prev, summary: e.target.value }))
                  }
                  placeholder="Summary"
                  className="h-9 text-sm"
                  aria-label="Filter by summary"
                />

                <Select
                  value={queueFilters.type}
                  onValueChange={(value) =>
                    setQueueFilters((prev) => ({ ...prev, type: value }))
                  }
                >
                  <SelectTrigger className="h-9 text-sm" aria-label="Filter by type">
                    <SelectValue placeholder="Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All types</SelectItem>
                    {typeOptions.map((type) => (
                      <SelectItem key={type} value={type}>
                        {type}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Select
                  value={queueFilters.status}
                  onValueChange={(value) =>
                    setQueueFilters((prev) => ({
                      ...prev,
                      status: value as HROpsQueueFilters["status"],
                    }))
                  }
                >
                  <SelectTrigger className="h-9 text-sm" aria-label="Filter by status">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All statuses</SelectItem>
                    <SelectItem value="NEW">New</SelectItem>
                    <SelectItem value="NEEDS_INFO">Needs Info</SelectItem>
                    <SelectItem value="READY">Ready</SelectItem>
                    <SelectItem value="IN_PROGRESS">In Progress</SelectItem>
                    <SelectItem value="ESCALATED">Escalated</SelectItem>
                    <SelectItem value="RESOLVED">Resolved</SelectItem>
                    <SelectItem value="CANCELLED">Cancelled</SelectItem>
                  </SelectContent>
                </Select>

                <Input
                  value={queueFilters.assignee}
                  onChange={(e) =>
                    setQueueFilters((prev) => ({ ...prev, assignee: e.target.value }))
                  }
                  placeholder='Assignee / "unassigned"'
                  className="h-9 text-sm"
                  aria-label="Filter by assignee"
                />
              </div>
            </div>
          )}

          {loading ? (
            <div className="text-sm text-muted-foreground">Loading queue...</div>
          ) : (
            <div className="space-y-5">
              {[
                { label: "Needs Info", rows: sortHRQueue(needsInfo) },
                { label: `Due Soon (${DUE_SOON_HOURS}h)`, rows: sortHRQueue(dueSoon) },
                { label: "Escalated", rows: sortHRQueue(escalated) },
                { label: "Unassigned", rows: sortHRQueue(unassigned) },
                { label: "Assigned to Me", rows: sortHRQueue(assignedToMe) },
                { label: "Assigned to Others", rows: sortHRQueue(assignedToOthers) },
                { label: "Closed", rows: sortHRQueue(closed) },
              ].map((section) => (
                <div key={section.label} className="bg-card border rounded-xl shadow-soft overflow-hidden">
                  <div className="px-4 py-3 border-b bg-muted/20 text-sm font-semibold">
                    {section.label} ({section.rows.length})
                  </div>
                  <Table>
                    <TableHeader>
                      <TableRow className="bg-muted/30">
                        <TableHead className="w-[110px]">Priority</TableHead>
                        <TableHead>Requester</TableHead>
                        <TableHead className="max-w-[320px]">Summary</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead className="min-w-[170px]">Due</TableHead>
                        <TableHead>Assignee</TableHead>
                        <TableHead className="w-[60px]" />
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {section.rows.map((item) => {
                        const requestId = item.request_id;
                        const isExpanded = expandedId === requestId;
                        const priority = mapPriority(item.priority);
                        const pConfig = priorityConfig[priority];
                        const status = item.status as Status;
                        const sConfig = statusConfig[status];
                        const dueSoonFlag = isDueSoon(item);
                        const dueAtTs = toTimestamp(item.sla_due_at);
                        const remainingHours =
                          dueAtTs === null
                            ? null
                            : Math.ceil((dueAtTs - Date.now()) / (1000 * 60 * 60));
                        const isOverdue = remainingHours !== null && remainingHours < 0;
                        const detail = detailById[requestId];
                        const isMine =
                          (item.assignee_user_id || "").toLowerCase() === currentUserEmail;
                        const missingFields = detail?.missing_fields || [];
                        const agentSuggestionRaw =
                          detail?.request?.captured_fields?.["agent_suggestion"] ??
                          item.captured_fields?.["agent_suggestion"];
                        const agentSuggestion =
                          typeof agentSuggestionRaw === "string" && agentSuggestionRaw.trim()
                            ? agentSuggestionRaw
                            : null;

                        return (
                          <Fragment key={requestId}>
                            <TableRow
                              className={`cursor-pointer hover:bg-muted/30 ${isMine ? "bg-primary/5" : ""}`}
                              onClick={() => void handleExpand(requestId)}
                            >
                              <TableCell>
                                <Badge variant="outline" className={`text-xs ${pConfig.className}`}>
                                  {pConfig.label}
                                </Badge>
                              </TableCell>
                              <TableCell className="font-medium text-sm">
                                {item.requester_name || item.requester_user_id}
                              </TableCell>
                              <TableCell className="text-sm text-muted-foreground max-w-[320px] truncate">
                                {item.summary}
                              </TableCell>
                              <TableCell>
                                <Badge variant="outline" className="text-xs">
                                  {item.type} / {item.subtype}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                <div className="flex flex-wrap items-center gap-1.5">
                                  <Badge variant="secondary" className="text-xs gap-1">
                                    <sConfig.icon className={`h-3 w-3 ${sConfig.color}`} />
                                    {sConfig.label}
                                  </Badge>
                                  {dueSoonFlag && (
                                    <Badge
                                      variant="outline"
                                      className="text-[10px] border-amber-300 text-amber-700 bg-amber-50"
                                    >
                                      Due Soon
                                    </Badge>
                                  )}
                                </div>
                              </TableCell>
                              <TableCell className="text-xs">
                                <div className="flex flex-col">
                                  <span
                                    className={
                                      isOverdue
                                        ? "font-medium text-destructive"
                                        : dueSoonFlag
                                        ? "font-medium text-amber-700"
                                        : "text-muted-foreground"
                                    }
                                  >
                                    {remainingHours === null
                                      ? "No SLA"
                                      : isOverdue
                                      ? `${Math.abs(remainingHours)}h overdue`
                                      : `${remainingHours}h left`}
                                  </span>
                                  {item.sla_due_at && (
                                    <span className="text-[10px] text-muted-foreground">
                                      Due {formatDateTime(item.sla_due_at)}
                                    </span>
                                  )}
                                  {dueSoonFlag && !isOverdue && (
                                    <span className="text-[10px] text-amber-700">
                                      Within 24h
                                    </span>
                                  )}
                                </div>
                              </TableCell>
                              <TableCell className="text-xs text-muted-foreground">
                                {item.assignee_name || item.assignee_user_id || "Unassigned"}
                              </TableCell>
                              <TableCell>
                                {isExpanded ? (
                                  <ChevronUp className="h-4 w-4 text-muted-foreground" />
                                ) : (
                                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                                )}
                              </TableCell>
                            </TableRow>

                            {isExpanded && (
                              <TableRow>
                                <TableCell colSpan={8} className="bg-muted/10 p-0">
                                  <motion.div
                                    initial={{ opacity: 0 }}
                                    animate={{ opacity: 1 }}
                                    className="px-6 py-4 space-y-4"
                                  >
                                    <div className="grid md:grid-cols-2 gap-4">
                                      <div className="space-y-4">
                                        <div>
                                          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                            Request Detail
                                          </h4>
                                          <p className="text-sm bg-card rounded-lg p-3 border whitespace-pre-wrap">
                                            {item.description}
                                          </p>
                                        </div>
                                        <div>
                                          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                            Resolution / Latest Context
                                          </h4>
                                          <div className="text-sm bg-accent/30 rounded-lg p-3 whitespace-pre-wrap border border-primary/10">
                                            {item.resolution_text || item.last_message_to_requester || "No resolution context yet."}
                                          </div>
                                        </div>
                                        <div>
                                          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                            Agent Suggestion
                                          </h4>
                                          <div className="text-sm bg-card rounded-lg p-3 border whitespace-pre-wrap">
                                            {agentSuggestion || "No agent suggestion captured."}
                                          </div>
                                        </div>
                                        <div>
                                          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                            Completeness
                                          </h4>
                                          <div className="rounded-lg border bg-card p-3 space-y-1">
                                            <div className="text-sm">
                                              {detail ? `${detail.completeness_percent}% complete` : "Loading..."}
                                            </div>
                                            <div className="text-xs text-muted-foreground">
                                              Missing: {missingFields.length > 0 ? missingFields.join(", ") : "None"}
                                            </div>
                                          </div>
                                        </div>
                                      </div>

                                      <div className="space-y-4">
                                        <div>
                                          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                            Timeline
                                          </h4>
                                          <div className="rounded-lg border bg-card p-3 max-h-[280px] overflow-auto space-y-2">
                                            {(detail?.timeline || []).length === 0 && (
                                              <div className="text-xs text-muted-foreground">No timeline events yet.</div>
                                            )}
                                            {(detail?.timeline || []).map((event) => (
                                              <div key={event.event_id} className="text-xs">
                                                <div className="font-medium">
                                                  {event.event_type.replace(/_/g, " ")}
                                                </div>
                                                <div className="text-muted-foreground">
                                                  {event.event_note || "No note"} · {formatDateTime(event.created_at)}
                                                </div>
                                              </div>
                                            ))}
                                          </div>
                                        </div>

                                        <div>
                                          <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                                            Message Requester
                                          </h4>
                                          <Textarea
                                            placeholder="Write a message to requester..."
                                            value={messageDraft[requestId] || ""}
                                            onChange={(e) =>
                                              setMessageDraft((prev) => ({
                                                ...prev,
                                                [requestId]: e.target.value,
                                              }))
                                            }
                                            className="text-sm min-h-[80px]"
                                          />
                                        </div>
                                      </div>
                                    </div>

                                    <div className="grid md:grid-cols-2 gap-3">
                                      <Select
                                        value={priority}
                                        onValueChange={(value) => {
                                          const next = value as Priority;
                                          void runAction(
                                            requestId,
                                            () => changeHRRequestPriority(user!.email, requestId, next),
                                            "Priority updated"
                                          );
                                        }}
                                      >
                                        <SelectTrigger className="h-9 text-sm">
                                          <SelectValue placeholder="Change priority" />
                                        </SelectTrigger>
                                        <SelectContent>
                                          <SelectItem value="P0">P0</SelectItem>
                                          <SelectItem value="P1">P1</SelectItem>
                                          <SelectItem value="P2">P2</SelectItem>
                                        </SelectContent>
                                      </Select>

                                      <Textarea
                                        placeholder="Resolution note (used for resolve/escalate)"
                                        value={resolutionNotes[requestId] || ""}
                                        onChange={(e) =>
                                          setResolutionNotes((prev) => ({
                                            ...prev,
                                            [requestId]: e.target.value,
                                          }))
                                        }
                                        className="text-sm min-h-[56px]"
                                      />
                                    </div>

                                    <div className="flex flex-wrap gap-2">
                                      {!isMine ? (
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            void runAction(
                                              requestId,
                                              () => assignHRRequest(user!.email, requestId, user!.email),
                                              "Assigned to you"
                                            );
                                          }}
                                        >
                                          <UserPlus className="h-3.5 w-3.5 mr-1.5" />
                                          Assign to me
                                        </Button>
                                      ) : (
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            void runAction(
                                              requestId,
                                              () => assignHRRequest(user!.email, requestId, null),
                                              "Unassigned"
                                            );
                                          }}
                                        >
                                          <UserMinus className="h-3.5 w-3.5 mr-1.5" />
                                          Unassign
                                        </Button>
                                      )}

                                      <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          const note = messageDraft[requestId]?.trim();
                                          if (!note) {
                                            toast.error("Please enter a message first.");
                                            return;
                                          }
                                          void runAction(
                                            requestId,
                                            () => messageHRRequestRequester(user!.email, requestId, note),
                                            "Requester message logged"
                                          );
                                        }}
                                      >
                                        <MessageSquare className="h-3.5 w-3.5 mr-1.5" />
                                        Message requester
                                      </Button>

                                      {(item.status === "NEW" || item.status === "READY" || item.status === "NEEDS_INFO") && (
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            void runAction(
                                              requestId,
                                              () => transitionHRRequestStatus(user!.email, requestId, "IN_PROGRESS"),
                                              "Moved to In Progress"
                                            );
                                          }}
                                        >
                                          <Clock className="h-3.5 w-3.5 mr-1.5" />
                                          Move to In Progress
                                        </Button>
                                      )}

                                      {(item.status === "IN_PROGRESS" || item.status === "ESCALATED") && (
                                        <Button
                                          size="sm"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            void runAction(
                                              requestId,
                                              () =>
                                                transitionHRRequestStatus(
                                                  user!.email,
                                                  requestId,
                                                  "RESOLVED",
                                                  resolutionNotes[requestId]?.trim() || undefined
                                                ),
                                              "Marked resolved"
                                            );
                                          }}
                                        >
                                          <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" />
                                          Mark resolved
                                        </Button>
                                      )}

                                      {item.status !== "RESOLVED" && item.status !== "CANCELLED" && item.status !== "ESCALATED" && (
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            void runAction(
                                              requestId,
                                              () =>
                                                escalateHRRequest(
                                                  user!.email,
                                                  requestId,
                                                  resolutionNotes[requestId]?.trim() || undefined
                                                ),
                                              "Escalated request"
                                            );
                                          }}
                                        >
                                          <ShieldAlert className="h-3.5 w-3.5 mr-1.5" />
                                          Escalate
                                        </Button>
                                      )}

                                      {(item.status === "RESOLVED" || item.status === "CANCELLED") && (
                                        <span className="text-xs text-emerald-600 font-medium flex items-center gap-1">
                                          <CheckCircle2 className="h-3.5 w-3.5" />
                                          Closed
                                        </span>
                                      )}
                                    </div>

                                    <div className="text-xs text-muted-foreground">
                                      <FileText className="h-3.5 w-3.5 inline mr-1" />
                                      Last update: {formatDateTime(item.updated_at)}
                                    </div>
                                  </motion.div>
                                </TableCell>
                              </TableRow>
                            )}
                          </Fragment>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      <MyRequestsPanel
        isOpen={requestsOpen}
        onClose={() => setRequestsOpen(false)}
        requests={assignedRequests}
      />
    </div>
  );
}
