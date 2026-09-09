# Hackathon Eligibility Clarifications

## Organizer Clarification Message

The following inquiry is prepared for the hackathon organizers:

> "For the ClickHouse track, may we use Google ADK with Gemini Developer API through a Google AI Studio free-tier key, Firestore on Spark, and the official mcp-clickhouse server, without Vertex AI billing? Also, does the restriction on other AI tools prohibit external AI assistance during planning/development, or only AI tooling in the submitted application?"

## Key Constraints Addressed
1. **Google ADK & Gemini Developer API**: Utilizes official `google-genai` and `google-adk` SDKs using a Google AI Studio API key to remain completely free of mandatory Vertex AI credit card/billing requirements.
2. **Official mcp-clickhouse**: Employs the open-source ClickHouse MCP server (`mcp-clickhouse` on PyPI) directly connecting to the user's ClickHouse Cloud service.
3. **Firestore on Spark Free Tier**: Retains session state without paid Firebase extensions or Cloud Storage.
4. **Zero Alternate AI Providers**: No OpenAI, Anthropic, or external proprietary AI runtime dependencies within the submitted application architecture.
