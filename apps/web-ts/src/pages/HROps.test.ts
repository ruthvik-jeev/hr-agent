import { describe, expect, it } from "vitest";

import type { BackendHRRequest } from "@/lib/backend";
import {
  isBlockedNeedsInfo,
  isDueSoon,
  matchesHROpsQueueFilters,
  sortHRQueue,
  toPanelRequestStatus,
} from "@/pages/HROps";

describe("toPanelRequestStatus", () => {
  it("maps assigned NEW/READY requests to assigned", () => {
    expect(toPanelRequestStatus("NEW", "jordan.lee@acme.com")).toBe("assigned");
    expect(toPanelRequestStatus("READY", "jordan.lee@acme.com")).toBe("assigned");
  });

  it("maps unresolved workflow states", () => {
    expect(toPanelRequestStatus("NEEDS_INFO", null)).toBe("in_review");
    expect(toPanelRequestStatus("IN_PROGRESS", null)).toBe("in_progress");
    expect(toPanelRequestStatus("ESCALATED", null)).toBe("in_progress");
  });

  it("maps terminal states to resolved", () => {
    expect(toPanelRequestStatus("RESOLVED", null)).toBe("resolved");
    expect(toPanelRequestStatus("CANCELLED", null)).toBe("resolved");
  });

  it("maps unassigned NEW/READY requests to pending", () => {
    expect(toPanelRequestStatus("NEW", null)).toBe("pending");
    expect(toPanelRequestStatus("READY", null)).toBe("pending");
  });
});

function makeRequest(overrides?: Partial<BackendHRRequest>): BackendHRRequest {
  return {
    request_id: 1,
    tenant_id: "default",
    requester_user_id: "alex.kim@acme.com",
    requester_role: "EMPLOYEE",
    subject_employee_id: null,
    requester_name: "Alex Kim",
    requester_department: "Engineering",
    requester_title: "Engineer",
    subject_employee_name: null,
    type: "ESCALATION",
    subtype: "PAYROLL",
    summary: "Need payroll correction",
    description: "March net pay mismatch",
    priority: "P1",
    risk_level: "MED",
    sla_due_at: null,
    status: "NEW",
    assignee_user_id: "jordan.lee@acme.com",
    assignee_name: "Jordan Lee",
    required_fields: [],
    captured_fields: {},
    missing_fields: [],
    created_at: "2026-03-13T10:00:00",
    updated_at: "2026-03-13T10:00:00",
    last_action_at: "2026-03-13T10:00:00",
    resolution_text: null,
    resolution_sources: [],
    escalation_ticket_id: null,
    last_message_to_requester: null,
    last_message_at: null,
    ...overrides,
  };
}

describe("matchesHROpsQueueFilters", () => {
  it("matches column filters across all supported fields", () => {
    const item = makeRequest({
      status: "IN_PROGRESS",
      priority: "P0",
      sla_due_at: new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString(),
    });
    expect(
      matchesHROpsQueueFilters(item, {
        priority: "P0",
        type: "ESCALATION / PAYROLL",
        status: "IN_PROGRESS",
        dueSoon: "due_soon",
      })
    ).toBe(true);
  });

  it("rejects on any non-matching filter", () => {
    const item = makeRequest();
    expect(
      matchesHROpsQueueFilters(item, {
        priority: "P2",
        type: "all",
        status: "all",
        dueSoon: "all",
      })
    ).toBe(false);
    expect(
      matchesHROpsQueueFilters(item, {
        priority: "all",
        type: "all",
        status: "RESOLVED",
        dueSoon: "all",
      })
    ).toBe(false);
    expect(
      matchesHROpsQueueFilters(
        makeRequest({ sla_due_at: "2026-03-15T10:00:00", status: "IN_PROGRESS" }),
        {
          priority: "all",
          type: "all",
          status: "all",
          dueSoon: "due_soon",
        }
      )
    ).toBe(false);
  });
});

describe("sortHRQueue", () => {
  it("applies priority, SLA, risk, status grouping, and created_at tie-break", () => {
    const input = [
      makeRequest({
        request_id: 1,
        priority: "P1",
        sla_due_at: "2026-03-14T09:00:00",
        risk_level: "MED",
        status: "READY",
        created_at: "2026-03-13T09:00:00",
      }),
      makeRequest({
        request_id: 2,
        priority: "P0",
        sla_due_at: "2026-03-14T10:00:00",
        risk_level: "HIGH",
        status: "READY",
        created_at: "2026-03-13T12:00:00",
      }),
      makeRequest({
        request_id: 3,
        priority: "P0",
        sla_due_at: "2026-03-14T10:00:00",
        risk_level: "LOW",
        status: "READY",
        created_at: "2026-03-13T11:00:00",
      }),
      makeRequest({
        request_id: 4,
        priority: "P0",
        sla_due_at: "2026-03-14T10:00:00",
        risk_level: "HIGH",
        status: "NEEDS_INFO",
        created_at: "2026-03-13T08:00:00",
      }),
    ];

    const sorted = sortHRQueue(input);
    expect(sorted.map((item) => item.request_id)).toEqual([2, 4, 3, 1]);
  });

  it("keeps NEEDS_INFO P0 ahead when SLA is sooner than READY/IN_PROGRESS", () => {
    const needsInfo = makeRequest({
      request_id: 10,
      priority: "P0",
      status: "NEEDS_INFO",
      sla_due_at: "2026-03-14T08:00:00",
      risk_level: "HIGH",
    });
    const ready = makeRequest({
      request_id: 11,
      priority: "P0",
      status: "READY",
      sla_due_at: "2026-03-14T09:00:00",
      risk_level: "HIGH",
    });

    const sorted = sortHRQueue([ready, needsInfo]);
    expect(sorted.map((item) => item.request_id)).toEqual([10, 11]);
  });
});

describe("bucket helpers", () => {
  it("marks blocked needs-info items by status or missing fields", () => {
    expect(isBlockedNeedsInfo(makeRequest({ status: "NEEDS_INFO", missing_fields: [] }))).toBe(
      true
    );
    expect(isBlockedNeedsInfo(makeRequest({ status: "READY", missing_fields: ["month"] }))).toBe(
      true
    );
    expect(isBlockedNeedsInfo(makeRequest({ status: "READY", missing_fields: [] }))).toBe(false);
  });

  it("marks due soon by SLA window and excludes closed items", () => {
    const now = new Date("2026-03-13T10:00:00");
    expect(
      isDueSoon(
        makeRequest({
          status: "IN_PROGRESS",
          sla_due_at: "2026-03-13T20:00:00",
        }),
        now,
        24
      )
    ).toBe(true);
    expect(
      isDueSoon(
        makeRequest({
          status: "RESOLVED",
          sla_due_at: "2026-03-13T20:00:00",
        }),
        now,
        24
      )
    ).toBe(false);
  });
});
