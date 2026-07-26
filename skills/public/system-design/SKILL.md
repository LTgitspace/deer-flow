---
name: system-design
description: Design scalable, maintainable systems end-to-end. Use when the user asks for "design this", "architecture", "system design", "how to build", "technical design", or "architecture review". Covers requirements, architecture decisions, component design, data modeling, API surface, deployment topology, and tradeoff documentation.
---

# System Design Skill

## Purpose

Produce a complete system design document that covers functional and non-functional requirements, architecture decisions, component breakdown, data flow, API surface, deployment topology, and tradeoff analysis.

---

## Phase 1: Requirements Gathering

**Gate: Must complete before architecture decisions.**

### What to Establish

| Field | Description | Example |
|---|---|---|
| **System goal** | One-line purpose | "A real-time chat application supporting 10M DAU" |
| **Functional requirements** | What the system must do | Send/receive messages, presence indicators, file sharing |
| **Non-functional requirements** | Performance, scale, reliability | 99.99% uptime, <100ms p99 latency, 10M concurrent users |
| **Constraints** | Budget, time, team size, tech stack | 3 engineers, 2 months, AWS only, React + Go |

### Required Output

```
## Scope
- **Goal**: {goal}
- **Users**: {estimated count and growth}

## Functional Requirements
1. {requirement}
2. {requirement}
3. {requirement}

## Non-Functional Requirements
- **Latency**: {target}
- **Availability**: {target}
- **Durability**: {target}
- **Scale**: {current and projected}

## Constraints
- **Team**: {size and skills}
- **Timeline**: {timeline}
- **Budget**: {budget}
- **Tech limitations**: {limitations}
```

---

## Phase 2: High-Level Architecture

**Gate: Requirements must be listed before architecture.**

### Deliverables

1. **System context diagram** — external actors and boundaries
2. **Architecture style** — monolithic / microservices / event-driven / serverless / CQRS / event sourcing
3. **Major components** — list of services, their responsibilities, and communication patterns
4. **Data flow diagrams** — for the core write path, read path, and async flows

### Output Template

```
## Architecture Overview

### Style
{style} — rationale: {why this style fits}

### Component Diagram (text)
```
[Client] ←→ [API Gateway] ←→ [Service A] ←→ [Database]
                              ↕
                          [Service B] ←→ [Queue]
```

### Component Responsibilities

| Component | Responsibility | Protocol | Scaling Strategy |
|---|---|---|---|
| API Gateway | Auth, rate limit, routing | HTTP/gRPC | Horizontal (ELB) |
| Service A | Core business logic | gRPC | Horizontal (+shard) |
| Service B | Async processing | Pub/sub | Partitioned |
| Database | Persistent storage | SQL/NoSQL | Read replicas + sharding |
```

---

## Phase 3: Detailed Component Design

**Gate: High-level architecture approved.**

### For Each Component

| Aspect | What to Define |
|---|---|
| **API surface** | Endpoints, request/response schemas, pagination, error codes |
| **State management** | What state lives where, consistency model, caching strategy |
| **Concurrency model** | Threading, async, worker pools, backpressure |
| **Failure modes** | Degraded behavior, retry strategies, circuit breakers |
| **Observability** | Logging, metrics, tracing, alerting thresholds |

### Data Model Design

```
### Core Entities

**User**
- id: UUID (PK)
- email: string (unique indexed)
- password_hash: string
- created_at: timestamp

**Message**
- id: UUID (PK)
- sender_id: UUID (FK → User)
- conversation_id: UUID (FK, indexed)
- content: text
- created_at: timestamp (clustered index)
```

### Storage Decisions

| Data Type | Storage Technology | Rationale |
|---|---|---|
| User profiles | PostgreSQL | Relational, ACID, joins |
| Messages | Cassandra / ScyllaDB | High write throughput, time-series |
| Session cache | Redis | Low-latency reads, TTL-based expiry |
| File attachments | S3 / GCS | Blob storage, CDN-fronted |
| Search index | Elasticsearch | Full-text search, aggregation |
| Async queue | Kafka / Redis streams | Ordered, replayable, partitioned |

---

## Phase 4: API Design

**Gate: Component design must define the API surface.**

### Requirements

- RESTful or gRPC endpoints for all CRUD operations
- Standard error format across all services
- Pagination, filtering, sorting
- Versioning strategy
- Authentication and authorization model

### Template

```
### Message API

`POST /api/v1/conversations/{id}/messages`
- **Auth**: Bearer token
- **Body**: `{ content: string, message_type: "text"|"image" }`
- **Response 201**: `{ id: UUID, created_at: timestamp }`
- **Errors**: 400 (validation), 401 (unauth), 404 (conv not found), 429 (rate limit)

### Pagination
- Cursor-based: `GET /api/v1/messages?cursor={id}&limit=50`
- Response includes `next_cursor` and `has_more`
```

---

## Phase 5: Data Flow & Consistency

**Gate: Components and API designed.**

### Trace the Critical Paths

| Path | What Happens | Consistency Needed |
|---|---|---|
| **Write** | User sends message → API Gateway → Service A → DB write → queue → notify receiver | Strong (sender must see it immediately) |
| **Read** | User opens app → load recent messages from DB → subscribe to new via WebSocket | Eventually consistent (stale reads OK) |
| **Async** | Queue consumer processes message → update search index → push notification | At-least-once, idempotent |

### Consistency Decisions

| Decision | Rationale |
|---|---|
| **Read-after-write consistency** for own messages | Cache invalidation on write, read-through cache |
| **Eventual consistency** for other users' messages | Acceptable staleness: 500ms |
| **Strong consistency** for payments/transactions | Write to single leader, read from leader |

---

## Phase 6: Deployment & Operations

**Gate: Design complete.**

| Aspect | Decision |
|---|---|
| **Infrastructure** | Kubernetes / Serverless / VMs / Physical |
| **CI/CD** | Build → test → containerize → staging → canary → production |
| **Scaling** | Horizontal pod autoscaling (CPU, memory, custom metrics) |
| **Backup & DR** | Daily snapshots, cross-region replication, RTO/RPO targets |
| **Monitoring** | SLIs, SLOs, dashboards, alerting (PagerDuty/Pager) |
| **Cost estimate** | Monthly infrastructure cost projection |

---

## Phase 7: Tradeoffs & Alternatives

**Gate: Deliver the complete design document.**

### Documentation Template

```
## Tradeoff Analysis

| Decision | Rationale | Alternative Considered | Why Not |
|---|---|---|---|
| {decision} | {reason} | {alternative} | {drawback} |
| PostgreSQL | ACID, team familiarity | CockroachDB | Overkill for current scale |

## Future Considerations
- {item to revisit at 10× scale}
- {item to revisit at 100× scale}

## Risks & Mitigations
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Database write throughput | Medium | High | Plan for sharding in year 2 |
| Single region failure | Low | Critical | Multi-region DR plan |
```

### Final Synthesis

Present a complete design document at `present_file`:

```
# System Design: {System Name}

## 1. Requirements
{Phase 1 output}

## 2. High-Level Architecture
{Phase 2 output}

## 3. Component Design
{Phase 3 output}

## 4. API Design
{Phase 4 output}

## 5. Data Flow
{Phase 5 output}

## 6. Deployment
{Phase 6 output}

## 7. Tradeoffs
{Phase 7 output}
```

## Bare Minimum

Under tight constraints, at minimum deliver:

1. Functional + non-functional requirements listed
2. High-level architecture diagram (text)
3. 3 core entities in data model
4. 2 critical paths traced (write + read)
5. Key tradeoff documented
6. Deployment decisions
