---
orchestrator_version: { { version } }
schema_version: { { version } }
last_updated: { { timestamp } }
---

# OSCAR Orchestrator v{{ version }}

## NODE 5 — Tool Selection

| Intent                        | Tool                          |
| ----------------------------- | ----------------------------- |
| {% for tool in tools          | sort(attribute='priority') %} |
| {{ tool.intent_description }} | {{ tool.name }}               |

{% endfor %}

## NODE 10 — Column Validation

[... base columns ...]

{% for tool in tools %}
{% if tool.new_columns %}
**NEW for {{ tool.name }}:**
{% for col in tool.new_columns %}

- {{ col.name }} — {{ col.description }}
  {% endfor %}
  {% endif %}
  {% endfor %}

[... rest of orchestrator stays the same ...]
