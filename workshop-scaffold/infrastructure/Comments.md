
General comment for running in your own account: 
    Existing Agents
    Transaction Search might be enabled already


General comment: why not rename these folders as "tools" instead of "agents"?
/workshop/edd-workshop/travel-agent/src/agents
/workshop/edd-workshop/travel-agent-strands/src/agents



In step https://catalog.us-east-1.prod.workshops.aws/workshops/cfc69d6e-22d8-4613-b122-3d155c248f71/en-US/01-agentic-observability/path-a-strands/02-deploy-agent#capture-the-auto-generated-names

    Because I had an existing agent, I got this:


    [participant@ip-10-91-1-198 travel-agent-strands]$ cd /workshop/edd-workshop
    ./scripts/capture-runtime-names.sh
    source config.env

    ERROR: found 2 runtime log groups. Not guessing which is yours.
    /aws/bedrock-agentcore/runtimes/advisor_advisor-DXRuHKD4BN-DEFAULT
    /aws/bedrock-agentcore/runtimes/travelAgentStrands_travelAgent-suWic32Iqg-DEFAULT

    Re-run with the one you just deployed, for example:
    ./scripts/capture-runtime-names.sh advisor_advisor-DXRuHKD4BN-DEFAULT
    [participant@ip-10-91-1-198 edd-workshop]$ ./scripts/capture-runtime-names.sh  travelAgentStrands_travelAgent-suWic32Iqg-DEFAULT

    Captured and saved to /workshop/edd-workshop/config.env:

    RUNTIME_LOG_SUFFIX   = travelAgentStrands_travelAgent-suWic32Iqg-DEFAULT
        -> log group /aws/bedrock-agentcore/runtimes/travelAgentStrands_travelAgent-suWic32Iqg-DEFAULT
        -> pass this to Path A.3 as the CFN ServiceName parameter

    RUNTIME_SERVICE_NAME = travelAgentStrands_travelAgent.DEFAULT
        -> read from a real log record, not guessed
        -> Module 2's evaluator filters on this

    Every new terminal now picks both up, because config.env is sourced on login.
    In THIS shell, run:  source /workshop/edd-workshop/config.env
    [participant@ip-10-91-1-198 edd-workshop]$ 


In step https://catalog.us-east-1.prod.workshops.aws/workshops/cfc69d6e-22d8-4613-b122-3d155c248f71/en-US/02-continuous-monitoring/02-deploy-eval-cfn#deploy-the-stack

    I didn't read the instructions carefully and deployed the Path B CF stack. A HIGHLIGHTED WARNING should help avoid this human error.



In step https://catalog.us-east-1.prod.workshops.aws/workshops/cfc69d6e-22d8-4613-b122-3d155c248f71/en-US/02-continuous-monitoring/03-invoke-and-verify-scores#troubleshooting

    I think the first check is only valide for Path B (It returns nothing when using Path A)

Why not create a copy-pasteable script for Path B that is easy to use in step https://catalog.us-east-1.prod.workshops.aws/workshops/cfc69d6e-22d8-4613-b122-3d155c248f71/en-US/02-continuous-monitoring/06-optional-custom-evaluator#generate-new-traffic

THIS IS NOT CLEAR TO ME (do we need to remove the "ABSOLUTE RULE, NO EXCEPTIONS:" block in the Strands coordinator code?):
Step https://catalog.us-east-1.prod.workshops.aws/workshops/cfc69d6e-22d8-4613-b122-3d155c248f71/en-US/03-trajectory-evaluation/03-prompt-change instructions not as clear as all previous ones. This step in particular, in a bit confusing: https://catalog.us-east-1.prod.workshops.aws/workshops/cfc69d6e-22d8-4613-b122-3d155c248f71/en-US/03-trajectory-evaluation/03-prompt-change#step-6:-generate-live-traffic-(post-deploy-smoke-detector)


In step https://catalog.us-east-1.prod.workshops.aws/workshops/cfc69d6e-22d8-4613-b122-3d155c248f71/en-US/03-trajectory-evaluation/04-online-trajectory-eval if you implement 2.6 (Optional) Custom evaluator, the current Evaluation is not "Builtin.Helpfulness", but "edd_workshop_travel_quality". Later, on the same page, this situation is addressed, but not at the start of the page.

In step https://catalog.us-east-1.prod.workshops.aws/workshops/cfc69d6e-22d8-4613-b122-3d155c248f71/en-US/04-production-to-dev-ground-truth/03-apply-wireup-power#step-1:-read-the-power I can't find the Kiro POWER file

In step https://catalog.us-east-1.prod.workshops.aws/workshops/cfc69d6e-22d8-4613-b122-3d155c248f71/en-US/04-production-to-dev-ground-truth/03-apply-wireup-power#step-5:-verify-the-wire-up

    This doesn't show the date:
        grep -m1 -A1 'date:' src/data/events.ts
    But:
        date: string; // YYYY-MM-DD
        time: string; // HH:MM
    Either change the grep or open the file with the editor

    I took Path A and this is not working:

    cd /workshop/edd-workshop/solutions/module-1/openinference-aws-adapter
    npm install                       # about 10 seconds, one time
    source /workshop/edd-workshop/config.env
    USER_QUERY="Are there any events in Luminara on <a date from src/data/events.ts>?" npm start

I think I can't continue from this point on if I haven't followed Path B. Or can I?




