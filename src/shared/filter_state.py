"""Estado compartido para filtros comunes entre páginas."""

from collections.abc import Iterable

import streamlit as st


FILTER_CAREERS_KEY = "selected_careers"
FILTER_FACULTIES_KEY = "selected_faculties"
FILTER_CAREER_TYPES_KEY = "selected_career_types"

FILTER_CAREERS_WIDGET_KEY = "_filter_selected_careers"
FILTER_FACULTIES_WIDGET_KEY = "_filter_selected_faculties"
FILTER_CAREER_TYPES_WIDGET_KEY = "_filter_selected_career_types"


def render_shared_multiselect(
    label: str,
    options: Iterable,
    state_key: str,
    widget_key: str,
    default: Iterable | None = None,
) -> list:
    """Renderiza un multiselect que sincroniza contra estado persistente."""
    option_list = list(options)
    _prepare_filter_widget_state(
        state_key=state_key,
        widget_key=widget_key,
        options=option_list,
        default=default,
    )
    selected = st.multiselect(
        label,
        options=option_list,
        key=widget_key,
        on_change=_commit_filter_widget_state,
        args=(widget_key, state_key, option_list),
    )
    st.session_state[state_key] = _filter_valid_values(selected, option_list)
    return st.session_state[state_key]


def render_shared_segmented_control(
    label: str,
    options: Iterable,
    state_key: str,
    widget_key: str,
    default: Iterable | None = None,
) -> list:
    """Renderiza un segmented_control multi que sincroniza estado persistente."""
    option_list = list(options)
    _prepare_filter_widget_state(
        state_key=state_key,
        widget_key=widget_key,
        options=option_list,
        default=default,
    )
    selected = st.segmented_control(
        label,
        options=option_list,
        selection_mode="multi",
        key=widget_key,
        on_change=_commit_filter_widget_state,
        args=(widget_key, state_key, option_list),
    )
    st.session_state[state_key] = _filter_valid_values(selected or [], option_list)
    return st.session_state[state_key]


def sync_filter_state(state_key: str, options: Iterable, default: Iterable | None = None) -> list:
    """Normaliza un filtro persistente sin renderizar widget."""
    option_list = list(options)
    selected = _normalize_filter_values(st.session_state.get(state_key), option_list, default)
    st.session_state[state_key] = selected
    return selected


def _prepare_filter_widget_state(
    state_key: str,
    widget_key: str,
    options: list,
    default: Iterable | None = None,
) -> None:
    selected = sync_filter_state(state_key, options, default)
    st.session_state[widget_key] = selected


def _commit_filter_widget_state(widget_key: str, state_key: str, options: list) -> None:
    selected = st.session_state.get(widget_key, [])
    st.session_state[state_key] = _filter_valid_values(selected or [], options)


def _normalize_filter_values(value, options: list, default: Iterable | None = None) -> list:
    if value is None:
        value = [] if default is None else list(default)
    return _filter_valid_values(_coerce_to_list(value), options)


def _filter_valid_values(values: Iterable, options: list) -> list:
    valid_values = []
    for value in values:
        for option in options:
            if value == option:
                valid_values.append(option)
                break
    return valid_values


def _coerce_to_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]
