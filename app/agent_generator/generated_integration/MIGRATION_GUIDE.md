# Migration Guide: Adding generic_search

**Orchestrator Version:** 1.0.0 → 1.1.0
**Schema Version:** 1.0.0 → 1.1.0
**Date:** 2026-01-23 00:17:11

---

## Summary

This guide covers integration of `generic_search` into the decision tree orchestrator.

**Description:** Retrieve variant rows with filters and pagination
**Change Type:** Minor (backward compatible)
**Estimated Time:** 30-45 minutes
**Breaking Changes:** None

---

## Step 1: Deploy Orchestrator (2 min)

```bash
# Copy generated orchestrator to production
cp generated_integration/orchestrator_dt_v1.1.0.md \
   prompts/versions/

# Update symlink to latest
ln -sf versions/orchestrator_dt_v1.1.0.md \
   prompts/orchestrator_dt.md
```

**Files Changed:**
- `prompts/orchestrator_dt.md` → v1.1.0

---

## Step 2: Deploy Schema (2 min)

```bash
# Copy generated schema to production
cp generated_integration/simple_plan_v1.1.0.json \
   schemas/versions/

# Update symlink
ln -sf versions/simple_plan_v1.1.0.json \
   schemas/simple_plan.json
```

**Files Changed:**
- `schemas/simple_plan.json` → v1.1.0

---

## Step 3: Deploy Pydantic Models (2 min)

```bash
cp generated_integration/generic_search_models.py schemas/
```

**Files Changed:**
- `schemas/generic_search_models.py` (new)

---

## Step 4: Deploy Agent Prompt (5 min)

```bash
cp generated_integration/generic_search_agent.md agents/
```

**Files Changed:**
- `agents/generic_search_agent.md` (new)

---

## Step 5: Add Tests (10 min)

```bash
cp generated_integration/test_generic_search.py tests/
pytest tests/test_generic_search.py -v
```

**Expected:** All tests should pass

---

## Step 6: Integration Testing (15 min)

Test with example queries:

- "Show me TP53 mutations"
- "Find BRCA1 missense variants"
- "Search for frameshift mutations in PIK3CA"

**Validation:**
1. Orchestrator routes to generic_search
2. Agent generates valid parameters
3. Tool executes successfully

---

## Rollback Procedure

If issues detected:

```bash
# Revert orchestrator
ln -sf versions/orchestrator_dt_v1.0.0.md \
   prompts/orchestrator_dt.md

# Revert schema
ln -sf versions/simple_plan_v1.0.0.json \
   schemas/simple_plan.json

# Remove new files
rm agents/generic_search_agent.md
rm schemas/generic_search_models.py
```

---

## Verification Checklist

- [ ] Orchestrator prompt deployed (v1.1.0)
- [ ] Schema deployed (v1.1.0)
- [ ] Pydantic models deployed
- [ ] Agent prompt deployed
- [ ] Tests passing
- [ ] Example queries tested manually
- [ ] Metrics dashboard updated
- [ ] Team notified

---

**Total Time:** ~40 minutes
**Risk:** Low (minor version, backward compatible)
**Confidence:** 0.92