"""Fail-closed reservations shared by every role and persisted across invocations."""
import asyncio
import json
import math
import os
import time
from pathlib import Path

from app.evaluation.protocol import checked, digest, encoded
from app.services.provider_budget import ProviderBudgetExceeded


class Campaign:
    """One process owns a campaign at a time; a stale lock requires inspection."""
    def __init__(self, directory, protocol_digest, ceiling, input_rate, output_rate):
        values = (ceiling, input_rate, output_rate)
        if any(not math.isfinite(v) or v <= 0 for v in values):
            raise ValueError("Campaign ceiling and conservative token prices must be finite and positive")
        self.directory = Path(directory)
        self.identity = dict(protocol_digest=protocol_digest, ceiling=ceiling,
                             input_rate=input_rate, output_rate=output_rate)
        self.owned = False

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / "campaign.lock").open("x", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
        self.owned = True
        try:
            path = self.directory / "campaign.json"
            self.state = checked(path) if path.exists() else {**self.identity, "charged_usd": 0.0, "requests": []}
            if any(self.state[key] != value for key, value in self.identity.items()):
                raise ValueError("Existing campaign protocol/ceiling/prices cannot be changed")
            self.save()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *args):
        if self.owned:
            (self.directory / "campaign.lock").unlink()
            self.owned = False

    def save(self):
        temporary = self.directory / "campaign.tmp"
        with temporary.open("wb") as handle:
            handle.write(encoded({"sha256": digest(self.state), "payload": self.state}))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.directory / "campaign.json")

    def price(self, inputs, outputs):
        return (inputs * self.identity["input_rate"] + outputs * self.identity["output_rate"]) / 1_000_000

    def reserve(self, identity, amount):
        if self.state["charged_usd"] + amount > self.identity["ceiling"] + 1e-12:
            raise ProviderBudgetExceeded("Campaign cost ceiling reached")
        index = len(self.state["requests"])
        self.state["requests"].append({"run": identity, "reserved_usd": amount, "charged_usd": amount,
                                       "state": "RESERVED_OR_INTERRUPTED"})
        self.state["charged_usd"] += amount
        self.save()  # Persist BEFORE the request; a crash never refunds unknown charges.
        return index

    def settle(self, index, amount, status):
        request = self.state["requests"][index]
        self.state["charged_usd"] += amount - request["charged_usd"]
        request.update(charged_usd=amount, state=status)
        self.save()


class Meter:
    def __init__(self, controls, campaign, identity, trace):
        self.controls, self.campaign, self.identity, self.trace = controls, campaign, identity, trace
        self.calls = self.inputs = self.outputs = 0
        self.cost = 0.0
        self.started = time.monotonic()
        self.lock = asyncio.Lock()
        self.step = "INITIALIZE"
        self.revisions = set()
        self.overrun = False

    def progress(self, step, iteration=None):
        self.step = step
        self.trace.append({"event": "role", "role": step, "iteration": iteration})

    async def invoke(self, bound, messages, *, output_tokens=4096):
        schema = bound.schema.model_json_schema() if bound.schema else None
        # Conservative byte count for byte-tokenized chat input, plus framing and
        # schema overhead. This is a reservation, NOT a claim of measured usage.
        prompt = json.dumps([{"role": getattr(m, "type", "human"), "content": m.content} for m in messages], ensure_ascii=False)
        inputs = len(prompt.encode()) + len(json.dumps(schema, ensure_ascii=False).encode()) + 1024
        outputs = min(output_tokens, 8192)
        reserve = self.campaign.price(inputs, outputs)
        async with self.lock:
            c = self.controls
            if self.overrun or self.calls >= c["max_llm_calls"] or self.inputs + inputs > c["max_input_tokens"] or self.outputs + outputs > c["max_output_tokens"] or self.cost + reserve > c["max_cost_usd"] + 1e-12:
                raise ProviderBudgetExceeded("Evaluation run reservation exceeds its call/token/cost cap")
            remaining = c["timeout_seconds"] - (time.monotonic() - self.started)
            if remaining <= 0:
                raise TimeoutError("Evaluation run deadline reached")
            index = self.campaign.reserve(self.identity, reserve)
            self.calls += 1
            self.inputs += inputs
            self.outputs += outputs
            self.cost += reserve
            event = {"event": "provider_attempt", "role": self.step, "call": self.calls,
                     "schema": bound.schema.__name__ if bound.schema else None,
                     "reserved_input_tokens": inputs, "reserved_output_tokens": outputs,
                     "model": c["model"], "temperature": c["temperature"], "state": "STARTED"}
            event.update(provider=c.get("provider", "openai"), sampling_mode=c.get("sampling_mode", "temperature"))
            event["transport_settings"] = getattr(getattr(bound, "client", None), "runtime_settings", {})
            self.trace.append(event)
        try:
            async with asyncio.timeout(remaining):
                raw, parsed = await bound.request(messages, outputs)
            usage = getattr(raw, "usage_metadata", None)
            metadata = getattr(raw, "response_metadata", {}) or {}
            revision = metadata.get("model_name") or metadata.get("model_version") or "unavailable"
            self.revisions.add(str(revision))
            measured = (isinstance(usage, dict) and type(usage.get("input_tokens")) is int
                        and type(usage.get("output_tokens")) is int and usage["input_tokens"] > 0
                        and usage["output_tokens"] >= 0)
            used_in, used_out = (usage["input_tokens"], usage["output_tokens"]) if measured else (inputs, outputs)
            charged = self.campaign.price(used_in, used_out)
            async with self.lock:
                self.inputs += used_in - inputs
                self.outputs += used_out - outputs
                self.cost += charged - reserve
                self.overrun |= used_in > inputs or used_out > outputs
                self.campaign.settle(index, charged, "MEASURED" if measured else "CONSERVATIVE_ESTIMATE")
            event.update(state="RETURNED", model_revision=revision, input_tokens=used_in, output_tokens=used_out,
                         estimated_cost_usd=charged, usage_measured=measured,
                         finish_reason=metadata.get("finish_reason"), reservation_overrun=self.overrun)
            if parsed is None:
                raise ValueError("Provider returned an unparseable structured response")
            return parsed
        except BaseException as exc:
            event.update(state="FAILED", error_type=type(exc).__name__)
            if "estimated_cost_usd" not in event:
                event.update(estimated_cost_usd=reserve, input_tokens=inputs,
                             output_tokens=outputs, usage_measured=False)
            # Unknown usage retains its complete reservation, also after timeout.
            raise


class PinnedLLM:
    def __init__(self, client, meter, schema=None):
        self.client, self.meter, self.schema = client, meter, schema

    def with_structured_output(self, schema):
        return PinnedLLM(self.client, self.meter, schema)

    async def request(self, messages, outputs):
        return await self.client.request(messages, self.schema, outputs)

    async def ainvoke(self, messages):
        return await self.meter.invoke(self, messages)
