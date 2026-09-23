# Pi-Mono Travel Agent

A multi-agent travel itinerary planner for the fictional city of **Luminara**, built with TypeScript and [pi-agent-core](https://www.npmjs.com/package/pi-agent-core) (the `pi-mono` agent runtime, distributed as the `pi-agent-core` npm package). Uses the **Agents-as-Tools** pattern — a Coordinator Agent orchestrates three Specialist Agent tools to plan constraint-aware travel itineraries.

This is the starter project for the **EDD Workshop**, designed with realistic failure modes for Evaluation-Driven Development.

## Architecture Overview

The system implements the **Agents-as-Tools** multi-agent pattern (one of four recognized patterns: Agents as Tools, Swarms, Agent Graphs, and Workflows).

```
User Message
  → main.ts (mode detection: single-shot or interactive REPL)
  → Coordinator Agent (orchestrator)
      ├── tool: query_sites   → Sites Agent   (attraction lookup)
      ├── tool: plan_route    → Route Agent   (constraint-aware scheduling)
      └── tool: suggest_dining → Dining Agent  (restaurant recommendations)
  → Coordinator synthesizes specialist outputs
  → Formatted itinerary returned to user
```

**Why Agents-as-Tools?** Travel planning naturally decomposes into distinct subtasks requiring different expertise (site lookup, route optimization, dining suggestions). The orchestrator provides hierarchical decision-making about which specialist to consult, and the pattern enables clear separation of concerns, modularity of specialists, and suitability for EDD evaluation of inter-agent coordination.

## Prerequisites

- **Node.js** >= 20
- **AWS account** with Amazon Bedrock access
- **Claude model access** (Claude Sonnet 4.6 or configured alternative)

## Setup

1. Navigate to the travel-agent directory and install dependencies:

```bash
cd travel-agent
npm install
```

2. Copy the environment template and fill in your values:

```bash
cp .env.example .env
```

3. Configure environment variables in `.env`:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AWS_REGION` | Yes | — | AWS region with Bedrock access (e.g., `us-east-1`) |
| `MODEL_ID` | No | `us.anthropic.claude-sonnet-4-6` | Bedrock model identifier (cross-region inference profile) |
| `AWS_PROFILE` | No | default profile | AWS credentials profile name |

4. Verify setup (runs unit tests, no AWS credentials needed):

```bash
npm run verify
```

## Running

### Single-Shot Mode

Pass your prompt as a command-line argument:

```bash
npx tsx src/main.ts "Plan a 2-day trip focusing on history and food, arriving Monday"
```

### Interactive Mode

Start a multi-turn REPL session (no arguments):

```bash
npx tsx src/main.ts
```

Type `exit` or `quit` to end the session.

### Verification Commands

```bash
npm run verify       # Unit tests (no AWS credentials required)
npm run verify:e2e   # End-to-end test (requires AWS credentials + Bedrock access)
npm test             # Run all tests
```

## Example Conversations

### Example 1: Full itinerary planning

```
You> Plan a 2-day trip focusing on history and food, arriving Monday

Agent> === Day 1: Monday ===
09:00 - 11:00  Ancient Temple Ruins (visit, 45 min)
11:20 - 13:20  Old Quarter Walking Tour (visit, 150 min)
13:30 - 14:30  The Luminara Bistro (meal, lunch)
15:00 - 16:30  Royal Palace (visit, 90 min)

=== Day 2: Tuesday ===
09:00 - 11:00  Grand Museum of Luminara (visit, 120 min)
11:15 - 12:15  Café Celestial (meal, lunch)
13:00 - 14:30  Botanical Gardens (visit, 90 min)

Summary: 5 attractions, 2 days, estimated total cost: $85
Note: Grand Museum moved to Tuesday (closed Mondays)
```

### Example 2: Quick factual lookup

```
You> What time does the museum open?

Agent> The Grand Museum of Luminara is open from 09:00 to 18:00 daily, except
Mondays (closed). Typical visit duration is about 2 hours. No advance booking
required. Ticket price: $15.
```

### Example 3: Itinerary modification

```
You> Remove the art gallery and add the harbor cruise instead

Agent> Updated your itinerary! I've replaced the Luminara Art Gallery with the
Harbor Cruise on Day 1.

Note: The Harbor Cruise requires advance booking — make sure to reserve your spot
ahead of time. Departure times are 10:00–15:00.

=== Day 1 (revised): Monday ===
09:00 - 10:00  Skyline Tower (visit, 60 min)
10:20 - 11:20  Harbor Cruise (visit, 60 min) ⚠️ Advance booking required
...
```

## Project Structure

```
├── src/
│   ├── main.ts                 # Entry point: mode detection, REPL loop
│   ├── coordinator.ts          # Coordinator Agent setup & configuration
│   ├── agents/
│   │   ├── sites-agent.ts      # Sites specialist tool (attraction lookup)
│   │   ├── route-agent.ts      # Route specialist tool (constraint solver)
│   │   └── dining-agent.ts     # Dining specialist tool (restaurant suggestions)
│   ├── data/
│   │   ├── types.ts            # TypeScript interfaces
│   │   ├── attractions.ts      # Mock attraction data (10 sites)
│   │   ├── restaurants.ts      # Mock restaurant data (6 options)
│   │   └── distances.ts        # Travel time matrix between attractions
│   └── utils/
│       ├── config.ts           # Environment variable loading & retry logic
│       ├── constraints.ts      # Constraint checking (closures, time budgets)
│       └── formatter.ts        # Itinerary output formatting
├── test/
│   ├── unit/                   # Unit + property-based tests (no AWS needed)
│   └── e2e/                    # End-to-end integration tests (requires AWS)
├── package.json
├── tsconfig.json
├── vitest.config.ts
├── .env.example
└── README.md
```

## Testing

Run the unit test suite (no AWS credentials required):

```bash
npm test
```

Run end-to-end tests (requires AWS credentials and Bedrock access):

```bash
npm run verify:e2e
```

Skip E2E tests via environment variable:

```bash
SKIP_E2E=true npm test
```

Tests use [Vitest](https://vitest.dev/) with [fast-check](https://github.com/dubzzz/fast-check) for property-based testing.

## EDD Workshop Context

This project is the **starter project for the EDD Workshop** — it demonstrates the kind of complex agentic system where Evaluation-Driven Development provides the most value. The multi-agent architecture introduces realistic failure modes:

- **Orchestrator misrouting**: Coordinator invokes wrong specialist
- **Context loss**: Specialist misses key constraints from conversation history
- **Contradictory outputs**: Route agent contradicts sites agent on hours
- **Integration errors**: Coordinator fails to synthesize specialist responses coherently

These subtle failures are difficult to catch with traditional testing but detectable through EDD evaluation pipelines.
