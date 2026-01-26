# Quick Start Guide

## Problem You Had

When you ran:
```bash
python tool_integration_generator.py add generic_search.yaml
```

Nothing happened because the original file was incomplete (only had class definitions, no main() function).

## Solution

Use the **COMPLETE** version:

```bash
# Use the complete generator
mv tool_integration_generator_complete.py tool_integration_generator.py
chmod +x tool_integration_generator.py
```

## Test It Now

```bash
# 1. Validate registry
python tool_integration_generator.py validate

# Expected output:
# ✓ Tool registry is valid
# Version: 1.0.0
# Tools: 3
#   - generic_search (priority 1)
#   - generic_aggregate (priority 2)
#   - generic_concatenated_aggregate (priority 3)

# 2. Initialize (generate v1.0.0 files)
python tool_integration_generator.py init

# Expected output:
# ⚠️  Cannot generate orchestrator:
#    - Create directory: templates/
#    - Add: orchestrator_dt_base_template.md
# ✓ Generated: generated_integration/simple_plan_v1.0.0.json
# ✓ INITIALIZATION COMPLETE

# 3. Add a new tool
python tool_integration_generator.py add generic_search.yaml

# Expected output:
# Adding tool from: generic_search.yaml
# ======================================================================
# Generating artifacts for: generic_search
# ----------------------------------------------------------------------
# ✓ Updated: tool_registry.json
# ⚠️  Cannot generate orchestrator: [template needed]
# ✓ Generated: generated_integration/simple_plan_v1.1.0.json
# ✓ Generated: generated_integration/generic_search_models.py
# ✓ Generated: generated_integration/generic_search_agent.md
# ✓ Generated: generated_integration/test_generic_search.py
# ✓ Generated: generated_integration/MIGRATION_GUIDE.md
# ✓ INTEGRATION COMPLETE
```

## What You Get

After running `add`:

1. **generic_search_models.py** - Pydantic models (~80 lines)
2. **generic_search_agent.md** - Complete agent prompt (~200 lines)
3. **test_generic_search.py** - Test scaffold
4. **simple_plan_v1.1.0.json** - Updated schema
5. **MIGRATION_GUIDE.md** - Deployment instructions

## Next: Create Base Template (Optional)

The orchestrator generation needs `templates/orchestrator_dt_base_template.md`.

Create it from your existing `orchestrator_dt.md`:

```markdown
---
orchestrator_version: {{ version }}
---

# OSCAR Orchestrator v{{ version }}

## NODE 5 — Tool Selection

{% for tool in tools|sort(attribute='priority') %}
| {{ tool.intent_description }} | {{ tool.name }} |
{% endfor %}

[... rest of orchestrator ...]
```

Then run `init` again to generate the complete orchestrator!

## Files in This Directory

- `tool_integration_generator_complete.py` ← **USE THIS ONE** (complete, 750 lines)
- `tool_integration_generator.py` ← Original incomplete version
- `generic_search.yaml` ← Example tool spec
- `generic_aggregate.yaml` ← Example tool spec
- `generic_concatenated_aggregate.yaml` ← Example tool spec
- `tool_registry.json` ← Tool registry (3 tools)
- `README.md` ← Full documentation
- `QUICKSTART.md` ← This file

## Troubleshooting

**"No module named 'yaml'"**
```bash
pip install pyyaml
```

**"No module named 'jinja2'"**
```bash
pip install jinja2
```

**"Tool spec not found"**
- Make sure the YAML file exists
- Use the correct path: `python tool_integration_generator.py add path/to/file.yaml`

**"Nothing happens"**
- Make sure you're using `tool_integration_generator_complete.py` (not the incomplete one)
- Check that you have a command: `init`, `add`, or `validate`

## Time to First Result

- Install dependencies: 30 seconds
- Run validate: 1 second
- Run add tool: 5 seconds
- **Total: 36 seconds to working system!**
