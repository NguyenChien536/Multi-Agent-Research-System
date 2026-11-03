"""Pinned provider transports; all calls must pass through the evaluation Meter."""
class OpenAITransport:
    """Pinned OpenAI chat client, no cache, retries, fallback or remote retrieval."""
    def __init__(self, controls):
        from app.core.config import settings
        from langchain_openai import ChatOpenAI
        if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("your_"):
            raise ValueError("An OpenAI key is required for this explicit transport")
        self.client = ChatOpenAI(
            model=controls["model"],
            temperature=controls["temperature"],
            api_key=settings.OPENAI_API_KEY,
            max_retries=0,
            cache=False,
            timeout=controls["timeout_seconds"],
        )

    async def request(self, messages, schema, outputs):
        client = self.client.model_copy(update={"max_tokens": outputs})
        if schema:
            result = await client.with_structured_output(
                schema, method="function_calling", include_raw=True
            ).ainvoke(messages)
            return result["raw"], result.get("parsed")
        raw = await client.ainvoke(messages)
        return raw, raw


class GeminiTransport:
    """Pinned Gemini chat client, no cache, retries, fallback or remote retrieval."""
    _FIXED_SAMPLING_MODELS = {
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.6-flash",
        "gemini-3.8-flash",
    }

    def __init__(self, controls):
        from app.core.config import settings
        from langchain_google_genai import ChatGoogleGenerativeAI

        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key or api_key.startswith("your_"):
            raise ValueError("A valid GEMINI_API_KEY is required for this explicit transport")

        model = controls["model"]
        if not model.startswith("gemini-") or "embedding" in model or "live" in model:
            raise ValueError(f"Invalid Gemini model specified: {model}")

        temp = controls.get("temperature")
        if model in self._FIXED_SAMPLING_MODELS:
            if controls.get("sampling_mode") != "provider_default" or temp is not None:
                raise ValueError(
                    f"Model {model} requires sampling_mode='provider_default' and temperature=None"
                )

        options = dict(
            model=model,
            google_api_key=api_key,
            vertexai=False,
            temperature=temp,
            max_retries=0,
            cache=False,
            timeout=controls["timeout_seconds"],
        )
        if model.startswith(("gemini-3.", "gemini-4.")):
            options["thinking_level"] = "low"
        self.runtime_settings = {"thinking_level": options.get("thinking_level", "provider_default"),
                                 "sampling_mode": controls.get("sampling_mode", "temperature")}
        self.client = ChatGoogleGenerativeAI(**options)

    async def request(self, messages, schema, outputs):
        from app.services.structured_output import _gemini_wire_schema

        client = self.client.model_copy(update={"max_output_tokens": outputs})
        if schema:
            wire = _gemini_wire_schema(schema.model_json_schema())
            result = await client.with_structured_output(wire, include_raw=True).ainvoke(messages)
            raw = result["raw"]
            parsed_data = result.get("parsed")
            parsed = schema.model_validate(parsed_data) if isinstance(parsed_data, dict) else None
            return raw, parsed
        raw = await client.ainvoke(messages)
        return raw, raw


def build_transport(controls):
    validate_transport_profile(controls)
    provider = controls.get("provider", "openai")
    if provider == "openai":
        return OpenAITransport(controls)
    elif provider == "gemini":
        return GeminiTransport(controls)
    raise ValueError(f"Unsupported transport provider: {provider}")


def validate_transport_profile(controls):
    """Pure preflight, also used by dry plans without constructing an API client."""
    provider, model = controls.get("provider", "openai"), controls["model"]
    if provider == "gemini":
        if not model.startswith("gemini-") or "embedding" in model or "live" in model:
            raise ValueError("Gemini evaluation requires an explicit Gemini chat model")
        if model in GeminiTransport._FIXED_SAMPLING_MODELS and (
            controls.get("sampling_mode") != "provider_default" or controls.get("temperature") is not None
        ):
            raise ValueError("This model requires provider_default sampling and null temperature")
    elif provider != "openai" or model.startswith("gemini-"):
        raise ValueError("Evaluation provider/model selection is inconsistent")
