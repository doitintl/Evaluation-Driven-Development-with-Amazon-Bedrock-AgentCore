# Architecture: Pi-Mono Travel Agent

## System Diagram

```
┌─────────────────────────────────────────────────┐
│                  User / CLI                       │
└─────────────────────┬───────────────────────────┘
                      │ prompt
                      ▼
┌─────────────────────────────────────────────────┐
│              Coordinator Agent                    │
│   (Orchestrates specialists, maintains context)  │
└──────┬──────────────┬──────────────────┬────────┘
       │              │                  │
       ▼              ▼                  ▼
┌─────────────┐ ┌───────────────┐ ┌────────────────┐
│ Sites Agent │ │  Route Agent  │ │  Dining Agent  │
│  (query_    │ │ (plan_route)  │ │ (suggest_      │
│   sites)    │ │               │ │   dining)      │
└──────┬──────┘ └───┬───────┬──┘ └──┬──────┬──────┘
       │            │       │       │      │
       ▼            ▼       ▼       ▼      ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│attractions.ts│ │distances.ts │ │restaurants.ts│
└─────────────┘ └─────────────┘ └─────────────┘
```

The Coordinator Agent is a pi-mono `Agent` instance with three specialist tools registered. When it receives a user message, the LLM decides which tools to invoke based on the request. Each specialist operates on deterministic mock data and returns structured results that the Coordinator synthesizes into a user-facing itinerary.

## Multi-Agent Collaboration Patterns

There are four recognized patterns for multi-agent collaboration (ref: [AWS blog on multi-agent collaboration patterns with Strands Agents](https://aws.amazon.com/blogs/machine-learning/multi-agent-collaboration-patterns-using-strands-agents-sdk/)):

| Pattern | Summary |
|---------|---------|
| **Agents as Tools** | Specialized agents are wrapped as callable tools invoked by a primary orchestrator agent that acts as a manager delegating specific queries to expert sub-agents. |
| **Swarms** | Decentralized peer agents collaborate without a fixed hierarchy, dynamically selecting which agent handles each subtask through negotiation. |
| **Agent Graphs** | Agents are organized in a structured directed network where messages flow along predefined edges between nodes. |
| **Workflows** | Agents execute in predefined sequential or parallel pipelines with fixed execution order and explicit handoff points. |

## Why Agents as Tools Was Chosen

The Agents-as-Tools pattern is a natural fit for travel itinerary planning:

1. **Clear subtask decomposition** — Travel planning naturally decomposes into distinct subtasks (attraction lookup, route optimization, dining suggestions) requiring different expertise and data access.

2. **Hierarchical decision-making** — The Coordinator decides when and which specialist to consult based on the user's request, mirroring how a human travel planner would delegate to experts.

3. **Separation of concerns** — Each specialist is independently testable with its own input schema, logic, and mock data. This makes constraint validation straightforward.

4. **Suitability for EDD** — Inter-agent coordination failures are observable at each tool-call handoff point. Evaluators can detect misrouting, context loss, and synthesis errors at well-defined boundaries.

5. **Modularity** — Specialists can be replaced, enhanced, or instrumented independently without touching the Coordinator's core logic.

## Why Not Other Patterns

### Swarms

Inappropriate because travel planning has clear task decomposition — it is not a peer brainstorming problem. The domain requires ordered execution (sites → route → dining), not emergent consensus among equal agents. A swarm would introduce non-deterministic delegation that makes EDD evaluation harder without adding value.

### Agent Graphs

Add unnecessary complexity for three specialists. Directed graph routing (edges, conditions, message passing) is suited to larger systems with many agents and complex routing logic. With only three specialist nodes, the overhead of defining graph topology outweighs any benefit.

### Workflows

Too rigid for multi-turn conversational refinement. The orchestrator must dynamically decide which specialists to re-invoke based on conversation context — a user might ask a follow-up about dining without needing route re-planning. A fixed pipeline cannot adapt to follow-up questions or partial re-planning requests.

## Data Flow

```
User Message
  → [ EDD: Request Analysis] main.ts (mode detection)
  → [ EDD: Orchestration Decision] Coordinator Agent
  → [ EDD: Tool Selection] LLM decides which tools to call
  → Tool Execution:
      [ EDD: Data Accuracy] Sites Agent → attraction info
      [ EDD: Constraint Satisfaction] Route Agent → optimized schedule
      [ EDD: Relevance] Dining Agent → restaurant suggestions
  → [ EDD: Synthesis Quality] Coordinator synthesizes responses
  → [ EDD: Format Compliance] Formatted itinerary → User
```

Each ` EDD` annotation marks a point where an evaluator can intercept and validate correctness:

| Annotation Point | What to Evaluate |
|-----------------|-----------------|
| Request Analysis | Did the system correctly identify the execution mode and parse the user intent? |
| Orchestration Decision | Did the Coordinator correctly identify which specialists are needed? |
| Tool Selection | Did the LLM invoke the right tools with appropriate parameters? |
| Data Accuracy | Did the Sites Agent return information matching the source mock data? |
| Constraint Satisfaction | Did the Route Agent respect all constraints (closures, hours, travel time, budget)? |
| Relevance | Did the Dining Agent return restaurants appropriate for the meal type and location? |
| Synthesis Quality | Did the Coordinator coherently combine specialist outputs without contradiction? |
| Format Compliance | Does the final output follow the structured itinerary format with day headers and time slots? |

## EDD-Relevant Failure Modes

The Agents-as-Tools pattern introduces specific failure modes that Evaluation-Driven Development is designed to detect:

### 1. Orchestrator Misrouting

The Coordinator invokes the wrong specialist for a given query. For example, asking the Route Agent about restaurant prices or the Dining Agent about opening hours. This occurs when the LLM misinterprets which domain a question belongs to.

**Detection**: Compare the tool invoked against the semantic category of the user's request.

### 2. Context Loss

A specialist receives a tool call missing key constraints that the user specified. For example, the Route Agent plans a schedule without knowing that the user mentioned they arrive on Monday — resulting in Monday-closed attractions being scheduled for Day 1.

**Detection**: Compare user-stated constraints against the parameters passed in each tool call.

### 3. Contradictory Outputs

Different specialists return conflicting information. For example, the Sites Agent reports the Grand Museum closes at 18:00, but the Route Agent schedules a visit starting at 17:30 with a 120-minute duration — implying departure at 19:30.

**Detection**: Cross-validate time windows, closure days, and factual claims across specialist responses.

### 4. Integration Errors

The Coordinator fails to coherently synthesize specialist responses. For example, the Dining Agent suggests restaurants near attractions that the Route Agent removed from the itinerary due to closure conflicts.

**Detection**: Verify that dining suggestions reference attractions actually present in the final route.

### 5. Conversation Drift

In multi-turn interactions, context degrades across turns. Later turns lose earlier preferences — the user said "budget-friendly" in turn 1, but by turn 4 the agent suggests upscale restaurants without acknowledging the constraint.

**Detection**: Track stated preferences across turns and verify they are respected in later responses.
