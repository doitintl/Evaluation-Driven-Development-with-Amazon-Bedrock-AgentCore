# Evaluation-Driven Development for AI Agents on Amazon Bedrock AgentCore

**▶ Take the workshop:** [Evaluation-Driven Development for AI Agents on Amazon Bedrock AgentCore](https://catalog.us-east-1.prod.workshops.aws/workshops/cfc69d6e-22d8-4613-b122-3d155c248f71/en-US) (AWS Workshop Studio)

This repository holds the source for that workshop: the Workshop Studio content, the infrastructure templates, and the example agents attendees work on.

---

## Why this workshop

If you have shipped an LLM-powered agent, you have probably been asked questions like these:

- *"Should we move to a different model?"* You answered with a guess.
- *"I changed the prompt to fix one bug. Did it break anything else?"* Another guess.
- *"A customer says the agent ignored a constraint."* You can't reproduce it.

These aren't problems with the LLM. They're evaluation problems. Teams can see that an agent answered, but not **what it did, whether that was good, or what specifically broke** when quality drops.

Agents make this harder than ordinary software. An agent decides for itself which tools to call and in what order. That sequence is its **trajectory**, and nobody writes it, so nobody can fully predict it. **A wrong path can still produce a right-looking answer.** An agent that skips the opening-hours lookup can still write a confident itinerary that sends someone to a museum on the day it's closed. If you only check the final text, a customer finds the problem before you do.

## What problem it solves

**Evaluation-Driven Development (EDD)** treats agent quality the way TDD treats code correctness. Every change is measured against a fixed definition of "good", and that definition exists *before* the change. The workshop builds the tooling so every production agent can answer four questions with a number:

| Question | How EDD answers it |
|---|---|
| *What happened?* | OpenTelemetry traces and structured logs in CloudWatch and X-Ray |
| *Was the agent good?* | AgentCore Online Evaluation (LLM-as-Judge) scoring every session |
| *What specifically broke?* | Trajectory evaluation that checks the agent's path as well as its answer |
| *What should "good" look like?* | Production sessions pulled back into the test suite as fresh ground truth |

The core idea is the **two-lens model**. A content lens (LLM-as-Judge) and a trajectory lens (tool-call matcher) catch different failures. A change can improve one while quietly regressing the other, so one green score is never enough.

## What's in the workshop

The running example is a **Coordinator agent for the fictional city of Luminara**. It orchestrates three specialist tools (`query_sites`, `plan_route`, `suggest_dining`). Real-world constraints, like the Grand Museum being closed on Mondays and the Harbor Cruise needing advance booking, make the trajectory matter, not just the answer.

| Module | What you do |
|---|---|
| **0. Setup** | Run the travel agent in a browser-based Code Editor and read its first trajectory |
| **1. Agentic Observability** | Wire traces and logs into AgentCore Observability. **Path A:** Strands on AgentCore Runtime (zero instrumentation code). **Path B:** any framework via an OpenInference adapter (pi-mono TypeScript) |
| **2. Continuous Monitoring** | Deploy an AgentCore Online Evaluator that automatically scores every session, with an optional custom rubric |
| **3. Trajectory Evaluation** | Run model-swap and prompt-change experiments, watch the two lenses disagree, and deploy your trajectory matcher as a custom AgentCore evaluator |
| **4. Production-to-Dev Ground Truth** | Use a coding agent and reusable "Powers" to turn low-scoring production sessions into test cases and close the loop |

Plan for about 3.5 to 4.5 hours. The workshop is intermediate level: you should be able to read TypeScript or Python and be comfortable with the AWS CLI. No prior AgentCore experience is needed.

## What you take away

- **Observability and evaluation as separate concerns.** Traces tell you what happened, and evaluation tells you whether it was good. You deploy and evolve each on its own.
- **Two lenses, not one.** Online Evaluation catches content regressions on real traffic. The framework eval catches trajectory regressions before you deploy. You ship when both agree.
- **A ground-truth loop.** Test cases written at launch drift away from what users actually do. Low-scoring production sessions are the test cases you haven't written yet.
- **Reusable assets for your own agents:** the observability and evaluation CloudFormation templates, the eval scaffold (`travel-agent/eval/`), and two coding-agent Powers (`kiro-powers/`) that automate the wire-up and case-first development.

---

## Repository layout

```
workshop-scaffold/
  workshop/            # Workshop Studio content (Hugo), contentspec.yaml, static assets, packaging scripts
  infrastructure/      # CloudFormation stacks and custom-resource Lambdas
  participant-scripts/ # Helper scripts attendees run during the workshop
  kiro-powers/         # Coding-agent Powers used in Module 4
travel-agent/          # pi-mono TypeScript Coordinator agent (Path B, Modules 3-4), incl. eval/ scaffold
travel-agent-strands/  # Strands Python Coordinator agent (Path A)
```

To build the Workshop Studio asset bundle (templates, Lambda zips, repo zip), run `bash workshop-scaffold/workshop/scripts/package_for_workshop.sh`.

## License

MIT-0. See `workshop-scaffold/LICENSE`.
