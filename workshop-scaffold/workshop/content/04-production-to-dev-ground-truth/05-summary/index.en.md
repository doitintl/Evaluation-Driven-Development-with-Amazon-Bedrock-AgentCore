---
title: "4.5 Summary"
weight: 50
---

## The loop is closed

![The full EDD loop: cases written in Module 3 gate the deploy, Module 2 scores real sessions in production, and this module extracts the low-scoring ones back into cases.](/static/images/diagrams/module4-ground-truth-loop.png)

Every low-scoring production session becomes a future test case. Every test case prevents a future regression. The loop tightens with each iteration.

## What you learned

**Wire-up is mechanical, so a coding agent does it.** Connecting a tool to OTEL, querying log groups, filtering results, generating case code: all repeatable. You judge what the correct trajectory *should* be; the agent does the rest.

**Ground truth decays unless refreshed.** User behaviour shifts, features launch, edge cases emerge. Pulling low-scoring sessions into the suite keeps it aligned with reality instead of launch-day assumptions.

**The discipline is codifiable.** Cases first, both lenses, no shipping without green deltas, all encodable in a coding-agent skill:

1. **Before any model/prompt change**: run `npm run eval` (trajectory + content lens)
2. **After deploy**: monitor Online Eval scores for regressions
3. **Weekly**: pull low-scoring production sessions into the test suite
4. **Before shipping**: both lenses must show a positive delta

:::alert{type="success" header="This is what makes agents engineerable at scale"}
Without EDD, every agent is a snowflake: deployed with crossed fingers, monitored with hope, improved by guesswork. With it, Module 1 shows what the agent does, Module 2 scores every session, Module 3 catches reasoning-path regressions before deploy, Module 4 keeps the suite honest.

The result: agents you can reason about, measure, and improve with the rigour of any other software system. No heroic developers required, just a process a coding agent enforces.
:::

## Workshop complete

The full EDD toolkit:

| Module | Lens | Timing | What it catches |
|--------|------|--------|-----------------|
| 1 | Observability | Always-on | "What happened?": traces, logs, sessions |
| 2 | Online Eval | Post-deploy | "Was the answer good?": content regressions on real traffic |
| 3 | Framework Eval | Pre-deploy | "Did it take the right path?": trajectory regressions |
| 4 | Ground Truth Loop | Ongoing | "Are our tests still relevant?": test suite drift |

Ship with confidence. Both lenses green, ground truth fresh, loop closed.

## Clean up your resources

**In an AWS-hosted event: nothing to do.** Workshop Studio recycles the entire account when the
event ends, so no resources persist and nothing keeps billing.

**In your own account: deleting the root stack is not sufficient.** You deployed
`edd-observability` and `edd-eval-and-obs` yourself as sibling stacks, `agentcore deploy`
created its own `AgentCore-*` stack, and page 3.4 created a Lambda, an IAM role and an
evaluator with no stack at all. Most importantly, your Online Evaluation Config stays **ACTIVE**
and keeps invoking a judge model on any new traffic until you remove it.

The **[workshop summary](../../summary/)** has the ordered teardown, including why the
evaluation stack has to go first and the two commands that confirm you are actually clean.
Follow it there rather than improvising here.
