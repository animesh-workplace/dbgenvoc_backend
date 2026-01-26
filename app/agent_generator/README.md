# Tool Integration System

Automated tool integration for decision tree orchestrators.

## Quick Start

### 1. Install Dependencies

```bash
pip install pyyaml jinja2
```

### 2. Copy Files

Copy these files to your project:
- `tool_integration_generator.py` → project root
- `tool_registry.json` → project root
- `generic_*.yaml` → reference examples

### 3. Create Base Template

Create `templates/orchestrator_dt_base_template.md` by converting your current orchestrator:

```markdown
---
orchestrator_version: {{ version }}
schema_version: {{ version }}
last_updated: {{ timestamp }}
---

# OSCAR Orchestrator v{{ version }}

## NODE 5 — Tool Selection

| Intent                    | Tool                           |
| ------------------------- | ------------------------------ |
{% for tool in tools|sort(attribute='priority') %}
| {{ tool.intent_description }} | {{ tool.name }} |
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
```

### 4. Initialize

```bash
python tool_integration_generator.py init
```

### 5. Add New Tools

```bash
python tool_integration_generator.py add path/to/new_tool.yaml
```

## Commands

- `init` - Generate initial orchestrator from registry
- `add <spec.yaml>` - Add new tool
- `validate` - Validate registry

## Tool Spec Format

See `generic_search.yaml`, `generic_aggregate.yaml` examples.

## Time Savings: 48 min → 1 min per tool

✓ Automatic orchestrator generation  
✓ Complete agent prompts with examples  
✓ Pydantic models  
✓ Test scaffolds  
✓ Migration guides  
