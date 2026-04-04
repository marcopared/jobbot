from __future__ import annotations

import json
from typing import Any, Mapping

from bs4 import BeautifulSoup

from core.ingestion.sources.public_boards.common import clean_text


def parse_next_data_payload(html: str | None) -> Mapping[str, Any] | None:
    if html is None:
        return None
    if not str(html).strip():
        return None

    document = BeautifulSoup(str(html), "html.parser")
    script = document.find("script", attrs={"id": "__NEXT_DATA__"})
    if script is None:
        return None

    raw = script.string or script.get_text()
    if not raw:
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, Mapping):
        return None
    return payload


def extract_initial_state(html: str | None) -> Mapping[str, Any]:
    payload = parse_next_data_payload(html)
    if not payload:
        return {}
    props = payload.get("props")
    if not isinstance(props, Mapping):
        return {}
    page_props = props.get("pageProps")
    if not isinstance(page_props, Mapping):
        return {}
    initial_state = page_props.get("initialState")
    if not isinstance(initial_state, Mapping):
        return {}
    return initial_state


def getro_primary_location(value: Any) -> str | None:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                location = clean_text(item)
                if location:
                    return location
            if isinstance(item, Mapping):
                location = clean_text(item.get("name") or item.get("description"))
                if location:
                    return location
    return clean_text(value)


def getro_employment_type(value: Any) -> str | None:
    if isinstance(value, list):
        labels: list[str] = []
        for item in value:
            if isinstance(item, Mapping):
                label = clean_text(item.get("label") or item.get("value"))
            else:
                label = clean_text(item)
            if label:
                labels.append(label)
        if labels:
            return ", ".join(labels)
        return None
    return clean_text(value)


def load_json_object(text: str | None) -> Mapping[str, Any]:
    payload = clean_text(text)
    if not payload:
        return {}
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, Mapping):
        return {}
    return data
