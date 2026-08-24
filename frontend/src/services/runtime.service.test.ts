import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./auth", () => ({ getAccessToken: vi.fn().mockResolvedValue("token") }));

import { RuntimeEventCursor, subscribeRuntime } from "./runtime.service";

const event = (sequence: number) => ({
  type: "step",
  execution_id: "runtime-1",
  workflow_id: "workflow-1",
  sequence,
});

describe("RuntimeEventCursor", () => {
  it("tracks the greatest accepted sequence", () => {
    const cursor = new RuntimeEventCursor();
    expect(cursor.accept(event(1))).toBe(true);
    expect(cursor.accept(event(3))).toBe(true);
    expect(cursor.lastSequence).toBe(3);
  });

  it("drops duplicate and out-of-order network events", () => {
    const cursor = new RuntimeEventCursor();
    expect(cursor.accept(event(3))).toBe(true);
    expect(cursor.accept(event(3))).toBe(false);
    expect(cursor.accept(event(2))).toBe(false);
    expect(cursor.accept(event(4))).toBe(true);
  });

  it("allows transport events without a durable sequence", () => {
    const cursor = new RuntimeEventCursor();
    expect(cursor.accept({...event(0), type:"heartbeat"})).toBe(true);
    expect(cursor.lastSequence).toBe(0);
  });
});

describe("subscribeRuntime reconnect", () => {
  const encoder = new TextEncoder();
  const streamResponse = (frames:string) => new Response(new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(frames));
      controller.close();
    },
  }), {status:200, headers:{"Content-Type":"text/event-stream"}});

  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("reconnects with its cursor, drops duplicates, and stops on terminal", async () => {
    const streamRequests: Array<{url:string;headers:Headers}> = [];
    let streamCount = 0;
    vi.stubGlobal("fetch", vi.fn(async (input:RequestInfo | URL, init?:RequestInit) => {
      const url=String(input);
      if (!url.includes("/events/")) {
        return new Response(JSON.stringify({status:"RUNNING",workflow_id:"workflow-1"}), {status:200});
      }
      streamRequests.push({url,headers:new Headers(init?.headers)});
      streamCount += 1;
      return streamCount === 1
        ? streamResponse('id: 1\nevent: runtime_event\ndata: {"type":"runtime.started","execution_id":"runtime-1","workflow_id":"workflow-1","sequence":1,"final":false}\n\n')
        : streamResponse('id: 1\nevent: runtime_event\ndata: {"type":"runtime.started","execution_id":"runtime-1","workflow_id":"workflow-1","sequence":1,"final":false}\n\nid: 2\nevent: runtime_event\ndata: {"type":"runtime.completed","execution_id":"runtime-1","workflow_id":"workflow-1","sequence":2,"aggregate_status":"COMPLETED","status":"completed","final":true}\n\n');
    }));
    const received:number[]=[];
    subscribeRuntime("runtime-1", event => received.push(event.sequence || 0));

    await vi.waitFor(() => expect(received).toEqual([1]));
    await vi.advanceTimersByTimeAsync(1000);
    await vi.waitFor(() => expect(received).toEqual([1,2]));

    expect(streamRequests).toHaveLength(2);
    expect(streamRequests[1].url).toContain("after_sequence=1");
    expect(streamRequests[1].headers.get("Last-Event-ID")).toBe("1");
    await vi.advanceTimersByTimeAsync(8000);
    expect(streamRequests).toHaveLength(2);
  });

  it("aborting prevents a pending reconnect", async () => {
    let streamRequests=0;
    vi.stubGlobal("fetch", vi.fn(async (input:RequestInfo | URL) => {
      if (!String(input).includes("/events/")) {
        return new Response(JSON.stringify({status:"RUNNING",workflow_id:"workflow-1"}), {status:200});
      }
      streamRequests += 1;
      return streamResponse('id: 1\ndata: {"type":"step","execution_id":"runtime-1","workflow_id":"workflow-1","sequence":1,"final":false}\n\n');
    }));
    const unsubscribe=subscribeRuntime("runtime-1", () => undefined);
    await vi.waitFor(() => expect(streamRequests).toBe(1));
    unsubscribe();
    await vi.advanceTimersByTimeAsync(8000);
    expect(streamRequests).toBe(1);
  });
});
