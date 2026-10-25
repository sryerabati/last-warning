# AWS access and spending

The project ceiling is **$30** from the user-reported **$100** Innovation Hub credit. The app and TRIBE Mini run locally; Amazon Bedrock supplies the default resident decisions. No permanent GPU instance or inference endpoint is needed.

The credit balance and AWS billing total have not been independently verified. Current application-accounted spending appears in **Advanced → Scenario settings** and **Model & methods**, or `GET /api/agents/status`. Do not substitute earlier smoke-test costs for the current ledger total.

## Bedrock limits

The provider uses the previously authenticated Ohio profile **`us.amazon.nova-micro-v1:0`** through **`us-east-2`**. It sends ordinary Converse text requests in batches of up to 10 resident contexts, with one in-flight request per service process, at most 3,000 output tokens per request and one retry. Client creation and network access share that serialized slot to avoid a native TLS concurrency failure observed on this Mac. TLS certificate verification remains enabled. The model returns a JSON decisions array; strict validation requires every requested resident ID exactly once and checks each action against that resident’s available actions. Invalid output or a transient connection failure can retry once; missing access or repeated failure stops the run. There is no automatic Rules fallback.

Legacy experiments use **`nova_resident_json_v4`**. New living-town experiments use **`nova_resident_json_life_v1`**, adding an individually validated `CONTINUE_ROUTINE` choice alongside the four emergency actions. Routine schedules and ambient playback run locally without cloud calls; Bedrock decides whether to continue or interrupt them during an emergency.

Requests use temperature zero, a five-second connection timeout and a sixty-second read timeout. If an otherwise valid response omits residents, validated model choices are held while the single retry requests only the missing residents. The model supplies those remaining decisions; the application does not invent them. Other validation errors retry with the precise error and allowed choices. A round is applied only after all requested residents have valid decisions; failed recovery discards the unapplied partial round. Both requests remain accounted. Isolated provider tests exercise these boundaries without paid inference.

Application-enforced limits:

- **$0.30 per run**.
- **$5 for this Bedrock phase**.
- **$30 for project requests**, including the earlier $0.00000441 Nova Micro smoke request.

Before a request, SQLite atomically reserves a conservative allowance for Nova Micro’s full 128K input context and the requested output limit. A successful response replaces that reservation with the estimate from actual token usage. Explicit unbilled rejections release the reservation; an interrupted or uncertain request retains its allowance. A crash or second server process cannot reuse already reserved funds.

The ledger is **`data/agents/bedrock/spend.sqlite3`** under the project, regardless of `LAST_WARNING_DATA_DIR`. Keep it when clearing verification data or moving the app. Each run records request IDs, context hashes, checkpoints, tokens and estimated/accounted costs. Validation failures retain their diagnostic detail and sanitized response excerpt in the ignored ledger. Replay reads saved frames and decisions without paid calls.

Rates checked for this implementation are **$0.035 per million input tokens** and **$0.14 per million output tokens**, from the [official Ohio Bedrock price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/us-east-2/index.csv). The [Nova Micro model card](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-micro.html) documents its context size. Cost estimates are not AWS billing records; these safeguards cover calls through this application rather than unrelated account activity.

## Credentials and startup

The AWS SDK is included in the normal application dependencies. Use an existing AWS profile or standard `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` and region environment variables. Credentials are not saved in the database, recordings or frontend bundle.

For an existing configured profile with valid login:

```bash
AWS_PROFILE=innovation-hub AWS_DEFAULT_REGION=us-east-2 bash scripts/start.sh
```

The profile must already exist; refresh its IAM Identity Center login when its session expires. Bedrock status checks inspect local credential configuration without calling inference or EC2/ECS metadata endpoints. “Configured” does not prove current model authorization; the first real request verifies that.

For a temporary session entered through hidden input:

```bash
uv run python backend/scripts/serve_with_aws.py --credential-parts 4
```

The four prompts accept **four consecutive substrings of one JSON object**, joined before parsing. Its exact keys are `aws_access_key_id`, `aws_secret_access_key` and `aws_session_token`, with string values. These are not four separate JSON documents or four independent credential fields. Keep each part comfortably below the terminal’s input-line limit. The launcher verifies STS, sets the session only in its process environment and starts the local server. No credential values should be placed in documentation, source, a startup command or committed files.

If credentials expire, restart with a refreshed session. A blocked request produces an explicit error; choosing **Advanced → Scenario settings → Rules baseline** is an intentional offline choice.

## TRIBE and previous GPU attempts

TRIBE v2 Mini runs on the local M4 Mac and adds **no AWS inference charges**. Bedrock runs the resident language model; it cannot import the arbitrary TRIBE brain encoder. These jobs have separate outputs and costs.

Earlier EC2 launches in Ohio and Northern Virginia failed on zero On-Demand/Spot GPU quotas. The organization policy denied the automatic quota-increase request. Temporary SSH keys and security groups were removed; checks found no leftover project instances or volumes. No paid GPU compute or storage started.

An optional full-model CUDA job would require the Innovation Hub administrator to enable **16 On-Demand G/VT vCPUs**, quota **L-DB2E81BA**, in `us-east-2`. The prepared bounded launcher and historical price checks remain in [TRIBE integration](tribe-integration.md). That route is unnecessary for local Mini, and live full-model inference remains unverified.
