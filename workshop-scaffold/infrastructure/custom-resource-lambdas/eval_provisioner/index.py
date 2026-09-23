# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""AgentCore Online-Eval provisioner — custom resource Lambda.

Creates one LLM-as-Judge evaluator and N Online Evaluation Configs (one per
service.name). Used by infrastructure/stacks/agentcore-eval-and-obs.yaml.

The rubric, judge model id, and sampling percentage are passed in as
ResourceProperties — they're TODOs the workshop participant fills in
when deploying the eval+obs CFN.

Bundled with a recent boto3 (the Lambda runtime's stock boto3 lacks the
`bedrock-agentcore-control` evaluator + online-eval APIs).
"""

from __future__ import annotations

import json
import re
import time
import urllib.request

import boto3
from botocore.exceptions import ClientError


def _send(event, context, status, data=None, reason='OK'):
    # PhysicalResourceId MUST be stable across invocations. It used to be
    # context.log_stream_name, which changes every run: CloudFormation then treated
    # every property change as a REPLACEMENT, created the new config, and
    # immediately sent Delete for the old physical id. The Delete branch below
    # removes any config matching ConfigPrefix, so it wiped the config that had
    # just been created, and the stack still reported success. Net effect: changing
    # any property (for example EvaluatorMode Builtin -> Custom in Module 2.6)
    # silently left the account with ZERO online evaluation configs.
    # Echoing the incoming id makes Update an in-place update instead.
    physical_id = event.get('PhysicalResourceId') or \
        f"eval-provisioner-{event['LogicalResourceId']}"
    body = json.dumps({
        'Status': status, 'Reason': reason,
        'PhysicalResourceId': physical_id,
        'StackId': event['StackId'], 'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': data or {},
    })
    # ResponseURL is the pre-signed HTTPS S3 URL that CloudFormation itself
    # injects into the custom-resource event — it is always https and is not
    # user-controlled input, so the Bandit B310 "audit url open for permitted
    # schemes" concern (file:/custom schemes) does not apply. This is the
    # canonical cfnresponse callback pattern.
    urllib.request.urlopen(urllib.request.Request(  # nosec B310 - CFN-provided pre-signed https ResponseURL
        event['ResponseURL'], data=body.encode(),
        headers={'Content-Type': ''}, method='PUT',
    ))


def _warm_up_marketplace_subscription(model_id):
    """Trigger AWS Marketplace auto-subscription for the judge model.

    Fresh AWS sandbox accounts may not be subscribed to a Bedrock model
    yet. The first InvokeModel call from a native principal triggers
    the auto-subscription. AgentCore's CreateEvaluator pre-flight uses
    the eval-EXECUTION role (a service role) to test access — and that
    PATH does NOT trigger auto-subscription, leaving CreateEvaluator
    to fail with the misleading 'Role does not have access for model'.

    The fix: have the Lambda's own role (a native principal) invoke
    the model first, which triggers the subscription account-wide.
    Then CreateEvaluator's pre-flight succeeds.

    Strip the inference-profile prefix because InvokeModel only accepts
    a foundation-model id at this stage.
    """
    import time
    bedrock_runtime = boto3.client('bedrock-runtime')
    # Try with the global. or us. id first; fall back to the bare id.
    candidate_ids = [model_id]
    for prefix in ('global.', 'us.'):
        if model_id.startswith(prefix):
            candidate_ids.append(model_id[len(prefix):])
            break
    body = json.dumps({
        'anthropic_version': 'bedrock-2023-05-31',
        'max_tokens': 16,
        'messages': [{'role': 'user', 'content': 'warmup'}],
    })
    for cid in candidate_ids:
        for attempt in range(3):
            try:
                bedrock_runtime.invoke_model(
                    modelId=cid,
                    contentType='application/json',
                    body=body,
                )
                print(f'Marketplace warm-up succeeded for {cid}')
                # First successful InvokeModel triggers the subscription;
                # give it 60s to propagate before AgentCore pre-flight checks.
                time.sleep(60)
                return
            except ClientError as e:
                msg = str(e)
                if 'aws-marketplace:Subscribe' in msg or 'aws-marketplace:ViewSubscriptions' in msg:
                    # Subscription kick-off succeeded but the actual subscribe
                    # hasn't propagated yet. Wait and retry.
                    print(f'Marketplace subscribe in flight ({cid}, attempt {attempt+1}); sleep 60s')
                    time.sleep(60)
                    continue
                # Wrong model id format — try the next candidate.
                if 'ValidationException' in msg or 'AccessDenied' in msg:
                    print(f'Warm-up failed for {cid}: {msg[:120]}')
                    break
                raise
    print('Warm-up exhausted; CreateEvaluator may still succeed if cache is warm.')


def _make_evaluator(cp, name, model_id, rubric):
    """Create the LLM-as-Judge evaluator.

    Schema (verified from boto3 1.43.10 model):
      evaluatorConfig.llmAsAJudge: {
        instructions, ratingScale,
        modelConfig: { bedrockEvaluatorModelConfig: {modelId, inferenceConfig} }
      }
      ratingScale.numerical[].{value, label, definition}
    """
    # Trigger Marketplace auto-subscription if needed (fresh accounts).
    _warm_up_marketplace_subscription(model_id)

    # The CreateEvaluator API does a pre-flight check on the eval-execution
    # role's Bedrock access. Fresh CFN-created roles can fail that check
    # for ~30-90s due to IAM propagation. Retry on the specific error.
    import time
    last_err = None
    for attempt in range(8):
        try:
            return _try_create(cp, name, model_id, rubric)
        except ClientError as e:
            msg = str(e)
            last_err = e
            if 'Role does not have access' in msg:
                wait = 15 * (attempt + 1)
                print(f'IAM propagation wait #{attempt+1}: sleeping {wait}s')
                time.sleep(wait)
                continue
            raise
    raise last_err


def _try_create(cp, name, model_id, rubric):
    eval_args = dict(
        evaluatorName=name,
        level='TRACE',
        evaluatorConfig={
            'llmAsAJudge': {
                'instructions': rubric,
                'modelConfig': {
                    'bedrockEvaluatorModelConfig': {
                        'modelId': model_id,
                        'inferenceConfig': {'maxTokens': 500, 'temperature': 0.0},
                    },
                },
                'ratingScale': {
                    'numerical': [
                        {'value': 1, 'label': 'Poor', 'definition': 'Fails to meet expectations'},
                        {'value': 2, 'label': 'Fair', 'definition': 'Partially meets expectations'},
                        {'value': 3, 'label': 'Good', 'definition': 'Meets expectations'},
                        {'value': 4, 'label': 'Very Good', 'definition': 'Exceeds expectations'},
                        {'value': 5, 'label': 'Excellent', 'definition': 'Far exceeds expectations'},
                    ],
                },
            },
        },
    )
    try:
        return cp.create_evaluator(**eval_args)['evaluatorId']
    except ClientError as e:
        if e.response['Error']['Code'] not in ('ConflictException', 'ValidationException'):
            raise
        # An evaluator with this name already exists, but its config (judge
        # model, rubric, rating scale) might be stale. AgentCore evaluators
        # are immutable (lockedForModification=true), so the only way to roll
        # forward is delete + recreate. We must also delete any
        # OnlineEvaluationConfigs that reference it, since AgentCore won't
        # let an evaluator be deleted while a config points at it.
        for ev in cp.list_evaluators().get('evaluators', []):
            if ev.get('evaluatorName') != name:
                continue
            stale_id = ev['evaluatorId']
            print(f'  found stale evaluator {stale_id}; recreating with current config')
            try:
                for cfg in cp.list_online_evaluation_configs().get('onlineEvaluationConfigs', []) or []:
                    referenced = any(
                        e.get('evaluatorId') == stale_id
                        for e in (cfg.get('evaluators') or [])
                    )
                    if referenced:
                        cp.delete_online_evaluation_config(
                            onlineEvaluationConfigId=cfg['onlineEvaluationConfigId'],
                        )
                        print(f"  deleted dependent config {cfg.get('onlineEvaluationConfigName')}")
            except Exception as cleanup_err:
                print(f'  config cleanup warning: {cleanup_err}')
            # AgentCore locks an evaluator for as long as ANY active online
            # evaluation config references it, and it releases that lock
            # asynchronously after the config is deleted. Deleting immediately
            # therefore raises
            #   ValidationException: Cannot delete a locked evaluator.
            # which used to fail the custom resource. CloudFormation then
            # retried the identical call during rollback and failed again,
            # leaving the stack in UPDATE_ROLLBACK_FAILED, a state no further
            # `aws cloudformation deploy` can recover from.
            #
            # So: retry while the lock drains, and if it never drains, reuse
            # the existing evaluator rather than failing. A slightly stale
            # rubric is a far better outcome than a wedged stack.
            for attempt in range(6):
                try:
                    cp.delete_evaluator(evaluatorId=stale_id)
                    print(f'  deleted {stale_id}; creating fresh evaluator')
                    return cp.create_evaluator(**eval_args)['evaluatorId']
                except ClientError as del_err:
                    msg = str(del_err)
                    locked = 'locked' in msg.lower()
                    if not locked:
                        print(f'  delete_evaluator failed ({msg}); reusing {stale_id}')
                        return stale_id
                    print(f'  evaluator still locked (attempt {attempt + 1}/6); waiting 10s')
                    time.sleep(10)
            print(f'  lock never released; reusing existing evaluator {stale_id}')
            return stale_id
        raise


def handler(event, context):
    print(f'boto3 version: {boto3.__version__}')
    cp = boto3.client('bedrock-agentcore-control')
    p = event['ResourceProperties']

    if event['RequestType'] == 'Delete':
        try:
            for cfg in cp.list_online_evaluation_configs().get('onlineEvaluationConfigs', []):
                if cfg['onlineEvaluationConfigName'].startswith(p['ConfigPrefix']):
                    cp.delete_online_evaluation_config(
                        onlineEvaluationConfigId=cfg['onlineEvaluationConfigId'],
                    )
        except Exception as e:
            print(f'cfg cleanup warn: {e}')
        # Only delete the custom evaluator (built-ins are AgentCore-managed)
        if p.get('EvaluatorMode', 'Custom') == 'Custom':
            try:
                target = p['EvaluatorName'].replace('-', '_')
                for ev in cp.list_evaluators().get('evaluators', []):
                    if ev.get('evaluatorName') == target:
                        cp.delete_evaluator(evaluatorId=ev['evaluatorId'])
            except Exception as e:
                print(f'eval cleanup warn: {e}')
        _send(event, context, 'SUCCESS')
        return

    try:
        evaluator_mode = p.get('EvaluatorMode', 'Custom')
        rubric = p.get('RubricInstructions') or 'Score the agent.'

        if evaluator_mode == 'Builtin':
            # Builtin path: skip CreateEvaluator entirely. Reference
            # AgentCore's built-in `Builtin.Helpfulness` directly in the
            # Online Eval Config. Zero rubric authoring, zero judge-model
            # config, zero pre-flight IAM races.
            evaluator_id = 'Builtin.Helpfulness'
            print(f'EvaluatorMode=Builtin: using {evaluator_id} (no CreateEvaluator call)')
        else:
            # Custom path: create our own LLM-as-Judge with the rubric.
            # Defence-in-depth: AgentCore evaluatorName regex is
            # ^[a-zA-Z0-9_]+$ (NO hyphens). Strip hyphens from the
            # incoming EvaluatorName so the API call doesn't fail when a
            # caller forgot to do it inline.
            evaluator_name = p['EvaluatorName'].replace('-', '_')
            evaluator_id = _make_evaluator(
                cp, evaluator_name, p['JudgeModelId'], rubric)
            print(f'EvaluatorMode=Custom: created {evaluator_id}')

        sampling_pct = float(p.get('SamplingPercentage', 100))
        configs = []
        # The log group is built from LogGroupServiceName (the log-group
        # suffix). The `serviceNames` FILTER uses ServiceNames (the OTEL
        # service.name the agent actually emits). On Path B they are the
        # same string; on AgentCore Runtime (Path A) they differ: the log
        # group keeps the runtime id (myAgent-ABC123-DEFAULT) while records
        # carry the dot-joined myAgent.DEFAULT. Falls back to the filter
        # value when not supplied, preserving old behaviour.
        log_group_svc = p.get('LogGroupServiceName') or p['ServiceNames'][0]
        for svc in p['ServiceNames']:
            # Online-eval-config name regex: ^[a-zA-Z][a-zA-Z0-9_]{0,47}$
            # Sanitize EVERY disallowed character, not just hyphens: Path A
            # service names contain a DOT (myAgent.DEFAULT), which produced
            # "Value at 'onlineEvaluationConfigName' failed to satisfy
            # constraint" when only hyphens were replaced (verified live
            # 2026-08-02).
            safe_prefix = re.sub(r'[^a-zA-Z0-9_]', '_', p['ConfigPrefix'])
            safe_svc = re.sub(r'[^a-zA-Z0-9_]', '_', svc)
            cfg_name = f"{safe_prefix}_{safe_svc}"[:48]
            log_group = f'/aws/bedrock-agentcore/runtimes/{log_group_svc}'
            # CreateOnlineEvaluationConfig pre-flight checks the
            # eval-execution role's `bedrock:*` access. Fresh CFN-
            # created roles can fail that check for ~30-90s due to IAM
            # propagation. Retry with backoff on the specific error.
            import time
            create_args = dict(
                onlineEvaluationConfigName=cfg_name,
                description=f'EDD workshop online eval for {svc}',
                rule={
                    'samplingConfig': {'samplingPercentage': sampling_pct},
                    'sessionConfig': {'sessionTimeoutMinutes': 5},
                },
                dataSourceConfig={
                    'cloudWatchLogs': {
                        'logGroupNames': [log_group],
                        'serviceNames': [svc],
                    },
                },
                evaluators=[{'evaluatorId': evaluator_id}],
                evaluationExecutionRoleArn=p['ExecutionRoleArn'],
                enableOnCreate=True,
            )
            last_err = None
            cfg_id = None
            for attempt in range(8):
                try:
                    resp = cp.create_online_evaluation_config(**create_args)
                    cfg_id = resp['onlineEvaluationConfigId']
                    break
                except ClientError as e:
                    code = e.response['Error']['Code']
                    msg = str(e)
                    last_err = e
                    print(f'CreateOnlineEvaluationConfig attempt #{attempt+1} failed: code={code} msg={msg[:200]}')
                    if code == 'ConflictException':
                        # Two reasons we can hit this:
                        #   1. A previous deploy already created the config and
                        #      we're updating with the same name + same evaluator
                        #      (idempotent — return the existing id).
                        #   2. A previous deploy is being torn down and a delete
                        #      is in flight; the name is reserved but list returns
                        #      empty. In that case, sleep and retry.
                        # Look up the existing config by name to distinguish.
                        existing = None
                        for cfg in cp.list_online_evaluation_configs().get('onlineEvaluationConfigs', []):
                            if cfg['onlineEvaluationConfigName'] == cfg_name:
                                existing = cfg
                                break
                        if existing:
                            # Idempotent reuse — but only if the evaluator matches
                            # what we wanted. If it doesn't (e.g. switched from
                            # Builtin → Custom), delete and retry on next loop.
                            existing_id = existing['onlineEvaluationConfigId']
                            try:
                                full = cp.get_online_evaluation_config(
                                    onlineEvaluationConfigId=existing_id)
                                existing_evaluators = [
                                    ev.get('evaluatorId')
                                    for ev in full.get('evaluators', [])]
                                wanted = [evaluator_id]
                                if existing_evaluators == wanted:
                                    print(f'  existing config matches wanted evaluator; reusing {existing_id}')
                                    cfg_id = existing_id
                                    break
                                print(f'  existing config has evaluators={existing_evaluators} but we want {wanted}; deleting and retrying')
                                cp.delete_online_evaluation_config(
                                    onlineEvaluationConfigId=existing_id)
                            except ClientError as ge:
                                print(f'  GetOnlineEvaluationConfig failed: {ge}; treating as in-flight delete')
                            time.sleep(15)
                            continue
                        # No config found in list but conflict reported — likely
                        # stale name reservation from an in-flight delete. Wait.
                        print(f'  Config {cfg_name} not in list but ConflictException; sleeping 15s')
                        time.sleep(15)
                        continue
                    if 'does not have permissions to invoke' in msg \
                            or 'Role does not have access' in msg \
                            or 'aws-marketplace:Subscribe' in msg:
                        # IAM propagation race or Marketplace auto-subscribe race
                        wait = 15 * (attempt + 1)
                        print(f'IAM/Marketplace propagation wait #{attempt+1}: sleeping {wait}s')
                        time.sleep(wait)
                        continue
                    raise
                except Exception as e:
                    last_err = e
                    print(f'CreateOnlineEvaluationConfig attempt #{attempt+1} non-ClientError: {type(e).__name__}: {e}')
                    raise
            if cfg_id is None:
                raise last_err or RuntimeError(
                    f'create_online_evaluation_config failed without exception after {attempt+1} attempts')
            configs.append({'svc': svc, 'id': cfg_id})

        _send(event, context, 'SUCCESS', {
            'EvaluatorId': evaluator_id,
            'Configs': json.dumps(configs),
        })
    except Exception as e:
        print(f'FAILED: {e}')
        _send(event, context, 'FAILED', reason=str(e)[:200])
