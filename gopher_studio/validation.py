"""Strict input validation shared by HTTP and the prompt composer."""

import math
import re

MAX_TEXT = 4000


class InputError(ValueError):
    def __init__(self, field, message):
        self.field = field
        super().__init__(message)


def obj(value, field, allowed):
    if not isinstance(value, dict):
        raise InputError(field, "Expected a JSON object / esperado objeto JSON.")
    extra = set(value) - set(allowed)
    if extra:
        raise InputError(field, "Unknown fields / campos desconhecidos: " + ", ".join(sorted(extra)))
    return value


def text(value, field, required=False):
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT or "\x00" in value:
        raise InputError(field, "Expected nonempty text of at most 4000 characters / texto não vazio, máximo 4000 caracteres.")
    return value.strip()


def strings(value, field):
    if not isinstance(value, list) or len(value) > 20:
        raise InputError(field, "Expected a list of up to 20 strings / lista de até 20 textos.")
    return [text(v, f"{field}[{i}]", True) for i, v in enumerate(value)]


def validate(data):
    obj(data, "body", ("goal", "language", "prompt_language", "context", "feedback"))
    result = {"goal": text(data.get("goal"), "goal", True)}
    for key in ("language", "prompt_language"):
        if key in data:
            if data[key] not in ("pt", "pt-BR", "en"):
                raise InputError(key, "Supported languages / idiomas suportados: pt, pt-BR, en.")
            result[key] = "pt" if data[key].startswith("pt") else "en"
    context = obj(data.get("context", {}), "context", (
        "fl_studio_version", "project_state", "current_task", "reference",
        "preferences", "constraints", "action", "observations", "proposals", "unknowns"))
    ctx = {}
    for key in ("fl_studio_version", "project_state", "current_task", "reference"):
        if key in context:
            ctx[key] = text(context[key], "context." + key, True)
    for key in ("preferences", "constraints", "observations", "proposals", "unknowns"):
        ctx[key] = strings(context.get(key, []), "context." + key)
    if "action" in context:
        action = obj(context["action"], "context.action", ("type", "target", "value"))
        kind = action.get("type")
        if kind not in ("set_tempo", "add_instrument", "rename_channel", "set_mixer_volume"):
            raise InputError("context.action.type", "Use set_tempo, add_instrument, rename_channel or set_mixer_volume.")
        act = {"type": kind}
        for key in ("target", "value"):
            if key not in action:
                continue
            value = action[key]
            if kind == "set_tempo" and key == "value":
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 10 <= value <= 522:
                    raise InputError("context.action.value", "BPM must be between 10 and 522 / BPM entre 10 e 522.")
                act[key] = value
            else:
                act[key] = text(value, "context.action." + key, True)
        if kind == "set_mixer_volume" and "value" in act and not re.fullmatch(r"[+-]?\d+(?:\.\d+)?\s*(?:dB|%)", act["value"], re.I):
            raise InputError("context.action.value", "Specify a number and unit, e.g. -6 dB or 50% / informe valor e unidade.")
        ctx["action"] = act
    result["context"] = ctx
    if "feedback" in data:
        feedback = obj(data["feedback"], "feedback", ("previous_prompt", "gopher_response", "observed_result"))
        if not any(feedback.get(k) for k in ("gopher_response", "observed_result")):
            raise InputError("feedback", "Provide gopher_response or observed_result / informe a resposta ou resultado observado.")
        result["feedback"] = {k: text(v, "feedback." + k, True) for k, v in feedback.items()}
    return result
