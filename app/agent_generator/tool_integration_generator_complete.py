#!/usr/bin/env python3
"""
Tool Integration Generator for Decision Tree Orchestrator
Automatically generates all artifacts needed to add a new tool

Usage:
    python tool_integration_generator.py init
    python tool_integration_generator.py add <tool_spec.yaml>
    python tool_integration_generator.py validate

Author: Generated for dbGENVOC project
Date: 2026-01-23
"""

import sys
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

try:
    from jinja2 import Template, Environment, FileSystemLoader
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False
    print("Warning: jinja2 not installed. Install with: pip install jinja2")


class ToolRegistry:
    """Manages the registry of all tools"""

    def __init__(self, registry_path: str = "tool_registry.json"):
        self.registry_path = Path(registry_path)
        self.data = self._load()

    def _load(self) -> Dict:
        if self.registry_path.exists():
            with open(self.registry_path) as f:
                return json.load(f)
        return {
            "version": "1.0.0",
            "last_updated": datetime.now().isoformat(),
            "tools": []
        }

    def save(self):
        with open(self.registry_path, 'w') as f:
            json.dump(self.data, f, indent=2)
        print(f"✓ Updated: {self.registry_path}")

    def add_tool(self, tool_spec: Dict) -> None:
        tool_def = tool_spec['tool_definition']

        tool_entry = {
            "name": tool_def['name'],
            "version": tool_def['version'],
            "priority": tool_def.get('placement', {}).get('node_priority', 999),
            "intent_description": tool_def.get('placement', {}).get('node5_intent_description', tool_def['description']),
            "added_in_version": self.data['version'],
            "new_columns": tool_def.get('new_columns', [])
        }

        # Remove if exists (update case)
        self.data['tools'] = [t for t in self.data['tools'] if t['name'] != tool_def['name']]

        # Add new tool
        self.data['tools'].append(tool_entry)

        # Sort by priority
        self.data['tools'] = sorted(self.data['tools'], key=lambda x: x['priority'])

        self.data['last_updated'] = datetime.now().isoformat()

    def remove_tool(self, tool_name: str) -> bool:
        original_count = len(self.data['tools'])
        self.data['tools'] = [t for t in self.data['tools'] if t['name'] != tool_name]

        if len(self.data['tools']) < original_count:
            self.data['last_updated'] = datetime.now().isoformat()
            return True
        return False

    def get_tools(self) -> List[Dict]:
        return self.data['tools']

    def bump_version(self, bump_type: str = 'minor') -> str:
        """Bump version number"""
        major, minor, patch = map(int, self.data['version'].split('.'))

        if bump_type == 'major':
            major += 1
            minor = 0
            patch = 0
        elif bump_type == 'minor':
            minor += 1
            patch = 0
        else:
            patch += 1

        new_version = f"{major}.{minor}.{patch}"
        self.data['version'] = new_version
        return new_version


class ToolIntegrationGenerator:
    """Main generator class"""

    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.output_dir = self.base_dir / "generated_integration"
        self.output_dir.mkdir(exist_ok=True)

        self.registry = ToolRegistry(self.base_dir / "tool_registry.json")

        # Setup Jinja2 environment
        if HAS_JINJA2:
            template_dir = self.base_dir / "templates"
            if template_dir.exists():
                self.jinja_env = Environment(loader=FileSystemLoader(str(template_dir)))
            else:
                self.jinja_env = None
        else:
            self.jinja_env = None

    def load_tool_spec(self, spec_path: str) -> Dict:
        """Load and validate tool specification"""
        spec_file = Path(spec_path)
        if not spec_file.exists():
            raise FileNotFoundError(f"Tool spec not found: {spec_path}")

        with open(spec_file) as f:
            spec = yaml.safe_load(f)

        # Basic validation
        required_fields = ['name', 'description', 'version', 'parameters', 'query_context_template']
        tool_def = spec.get('tool_definition', {})

        missing_fields = [f for f in required_fields if f not in tool_def]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        return spec

    def generate_orchestrator_complete(self) -> str:
        """Generate complete orchestrator prompt"""

        if self.jinja_env is None:
            print("⚠️  Cannot generate orchestrator:")
            if not HAS_JINJA2:
                print("   - Install jinja2: pip install jinja2")
            template_dir = self.base_dir / "templates"
            if not template_dir.exists():
                print(f"   - Create directory: {template_dir}/")
                print("   - Add: orchestrator_dt_base_template.md")
            return None

        try:
            template = self.jinja_env.get_template('orchestrator_dt_base_template.md')
        except Exception as e:
            print(f"⚠️  Template not found: {e}")
            print("   Create: templates/orchestrator_dt_base_template.md")
            return None

        version = self.registry.data['version']
        tools = self.registry.get_tools()

        content = template.render(
            version=version,
            timestamp=datetime.now().isoformat(),
            tools=tools
        )

        output_path = self.output_dir / f"orchestrator_dt_v{version}.md"
        with open(output_path, 'w') as f:
            f.write(content)

        print(f"✓ Generated: {output_path}")
        return str(output_path)

    def generate_schema(self) -> str:
        """Generate complete JSON schema"""
        version = self.registry.data['version']
        tools = self.registry.get_tools()

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "SimplePlan",
            "version": version,
            "type": "object",
            "required": ["plan"],
            "properties": {
                "plan": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["step_id", "tool_name", "query_context", "deps"],
                        "properties": {
                            "step_id": {"type": "string"},
                            "tool_name": {
                                "type": "string",
                                "enum": [tool['name'] for tool in tools]
                            },
                            "query_context": {"type": "string"},
                            "deps": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        }
                    }
                }
            }
        }

        output_path = self.output_dir / f"simple_plan_v{version}.json"
        with open(output_path, 'w') as f:
            json.dump(schema, f, indent=2)

        print(f"✓ Generated: {output_path}")
        return str(output_path)

    def generate_pydantic_model(self, tool_spec: Dict) -> str:
        """Generate Pydantic model for tool parameters"""
        tool_def = tool_spec['tool_definition']
        tool_name = tool_def['name']

        # Convert to PascalCase
        class_name = ''.join(word.capitalize() for word in tool_name.split('_')) + 'Request'

        code_lines = [
            '"""',
            f'Pydantic models for {tool_name}',
            'Generated by tool_integration_generator.py',
            '"""',
            '',
            'from pydantic import BaseModel, Field',
            'from typing import List, Optional, Literal',
            '',
            ''
        ]

        # Generate main model
        code_lines.append(f'class {class_name}(BaseModel):')
        code_lines.append('    """')
        code_lines.append(f'    Request model for {tool_name}')
        code_lines.append(f'    {tool_def["description"]}')
        code_lines.append('    """')
        code_lines.append('')

        # Required fields
        for param in tool_def['parameters'].get('required', []):
            field_type = param['type']
            field_desc = param.get('description', '')

            if 'enum' in param:
                enum_values = ', '.join([f'"{v}"' for v in param['enum']])
                field_type = f'Literal[{enum_values}]'

            code_lines.append(f'    {param["name"]}: {field_type} = Field(')
            code_lines.append('        ...,')
            code_lines.append(f'        description="{field_desc}"')
            code_lines.append('    )')

        # Optional fields
        for param in tool_def['parameters'].get('optional', []):
            field_type = param['type']
            default = param.get('default', 'None')
            field_desc = param.get('description', '')

            if 'enum' in param:
                enum_values = ', '.join([f'"{v}"' for v in param['enum']])
                field_type = f'Optional[Literal[{enum_values}]]'
            else:
                field_type = f'Optional[{field_type}]'

            if isinstance(default, str) and default != 'None':
                default = f'"{default}"'

            code_lines.append(f'    {param["name"]}: {field_type} = Field(')
            code_lines.append(f'        default={default},')
            code_lines.append(f'        description="{field_desc}"')
            code_lines.append('    )')

        output_path = self.output_dir / f"{tool_name}_models.py"
        with open(output_path, 'w') as f:
            f.write('\n'.join(code_lines))

        print(f"✓ Generated: {output_path}")
        return str(output_path)

    def generate_agent_prompt(self, tool_spec: Dict) -> str:
        """Generate downstream agent prompt with examples and validation"""
        tool_def = tool_spec['tool_definition']
        tool_name = tool_def['name']
        class_name = ''.join(word.capitalize() for word in tool_name.split('_')) + 'Request'

        lines = [
            f'# {tool_name.replace("_", " ").title()} Parameter Generator Agent',
            '',
            '## Role',
            f'You are a specialized parameter generator for the `{tool_name}` tool in the dbGENVOC genomics platform.',
            '',
            f'Your job is to parse the orchestrator\'s `query_context` string and generate a valid JSON object that matches the `{class_name}` Pydantic model.',
            '',
            '---',
            '',
            '## Input Format',
            '',
            'You receive a SimplePlan step from the orchestrator:',
            '',
            '```json',
            '{',
            f'  "step_id": "step_1",',
            f'  "tool_name": "{tool_name}",',
            f'  "query_context": "{tool_def["query_context_template"]}",',
            '  "deps": []',
            '}',
            '```',
            '',
            '---',
            '',
            '## Your Task',
            '',
            f'Parse the `query_context` field and extract key-value pairs (pipe-separated format) to generate valid parameters for the {tool_name} tool.',
            '',
            '---',
            '',
            '## Pydantic Model Schema',
            '',
            'The output MUST match this structure:',
            '',
            '```python',
            f'class {class_name}(BaseModel):',
        ]

        # Add required fields to schema
        for param in tool_def['parameters'].get('required', []):
            field_type = param['type']
            if 'enum' in param:
                enum_str = str(param['enum']).replace("'", '"')
                field_type = f'Literal{enum_str}'
            lines.append(f'    {param["name"]}: {field_type}  # Required')

        # Add optional fields to schema
        for param in tool_def['parameters'].get('optional', []):
            field_type = param['type']
            default = param.get('default', 'None')
            if 'enum' in param:
                enum_str = str(param['enum']).replace("'", '"')
                field_type = f'Optional[Literal{enum_str}]'
            else:
                field_type = f'Optional[{field_type}]'
            lines.append(f'    {param["name"]}: {field_type} = {default}  # Optional')

        lines.extend([
            '```',
            '',
            '---',
            '',
            '## Parsing Rules',
            '',
            '### Required Fields',
            ''
        ])

        # Document required parameters
        for param in tool_def['parameters'].get('required', []):
            lines.append(f'**{param["name"]}:**')
            lines.append(f'- {param.get("description", "No description")}')
            lines.append(f'- Extract from: `{param["name"]}: <value>`')
            if 'enum' in param:
                lines.append(f'- Must be one of: {", ".join(param["enum"])}')
            lines.append('')

        lines.extend([
            '### Optional Fields',
            ''
        ])

        # Document optional parameters
        for param in tool_def['parameters'].get('optional', []):
            lines.append(f'**{param["name"]}:**')
            lines.append(f'- {param.get("description", "No description")}')
            lines.append(f'- Extract from: `{param["name"]}: <value>`')
            lines.append(f'- Default: {param.get("default", "None")}')
            if 'enum' in param:
                lines.append(f'- Must be one of: {", ".join(param["enum"])}')
            lines.append('')

        lines.extend([
            '---',
            '',
            '## Validation Gates',
            ''
        ])

        # Add validation gates
        for i, gate in enumerate(tool_def.get('validation_gates', []), 1):
            lines.append(f'### Gate {i}: {gate["condition"]}')
            lines.append('')
            lines.append(f'IF {gate["condition"]}:')
            lines.append(f'- **ERROR**: "{gate["error"]}"')
            lines.append(f'- **ACTION**: {gate["action"]}')
            lines.append('')

        lines.extend([
            '---',
            '',
            '## Output Format',
            '',
            'Return ONLY valid JSON matching the schema. No explanations, no markdown.',
            '',
            '```json',
            '{'
        ])

        # Add example output
        all_params = tool_def['parameters'].get('required', []) + tool_def['parameters'].get('optional', [])
        for i, param in enumerate(all_params):
            comma = ',' if i < len(all_params) - 1 else ''
            if param['type'] == 'str':
                if 'enum' in param:
                    lines.append(f'  "{param["name"]}": "{param["enum"][0]}"{comma}')
                else:
                    lines.append(f'  "{param["name"]}": "example_value"{comma}')
            elif 'List' in param['type']:
                if 'enum' in param:
                    lines.append(f'  "{param["name"]}": ["{param["enum"][0]}"]{ comma}')
                else:
                    lines.append(f'  "{param["name"]}": ["value1"]{comma}')
            elif param['type'] == 'int':
                lines.append(f'  "{param["name"]}": 10{comma}')
            elif param['type'] == 'bool':
                lines.append(f'  "{param["name"]}": true{comma}')
            else:
                lines.append(f'  "{param["name"]}": null{comma}')

        lines.extend([
            '}',
            '```',
            '',
            '---',
            '',
            '## Example Queries',
            ''
        ])

        # Add example queries
        for i, query in enumerate(tool_def.get('example_queries', [])[:3], 1):
            lines.append(f'### Example {i}')
            lines.append('')
            lines.append(f'**User Query:** "{query}"')
            lines.append('')
            lines.append('**Expected Parameters:**')
            lines.append('```json')
            lines.append('{')
            lines.append('  "table_name": "nibmg_exome_somatic_variants",')
            lines.append('  ...')
            lines.append('}')
            lines.append('```')
            lines.append('')

        lines.extend([
            '---',
            '',
            '## Summary',
            '',
            '**INPUT:** Orchestrator\'s pipe-separated query_context string',
            '**OUTPUT:** Valid JSON matching the Pydantic model',
            '**VALIDATION:** Check all required fields and validation gates',
            '**ERROR HANDLING:** Return descriptive JSON errors for invalid requests',
            '',
            'Always return JSON only. No prose. No markdown formatting.',
        ])

        output_path = self.output_dir / f"{tool_name}_agent.md"
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

        print(f"✓ Generated: {output_path}")
        return str(output_path)

    def generate_tests(self, tool_spec: Dict) -> str:
        """Generate pytest test scaffold"""
        tool_def = tool_spec['tool_definition']
        tool_name = tool_def['name']
        class_name = ''.join(word.capitalize() for word in tool_name.split('_')) + 'Request'

        lines = [
            '"""',
            f'Tests for {tool_name}',
            'Generated by tool_integration_generator.py',
            '"""',
            '',
            'import pytest',
            f'from {tool_name}_models import {class_name}',
            '',
            '',
            f'def test_valid_{tool_name}_request():',
            '    """Test that valid parameters pass validation"""',
            f'    request = {class_name}(',
        ]

        # Add required params with example values
        for param in tool_def['parameters'].get('required', []):
            if param['type'] == 'str':
                if 'enum' in param:
                    lines.append(f'        {param["name"]}="{param["enum"][0]}",')
                else:
                    lines.append(f'        {param["name"]}="test_value",')
            elif 'List' in param['type']:
                if 'enum' in param:
                    lines.append(f'        {param["name"]}=["{param["enum"][0]}"],')
                else:
                    lines.append(f'        {param["name"]}=["value1"],')
            else:
                lines.append(f'        {param["name"]}=None,')

        lines.extend([
            '    )',
            '    assert request is not None',
            '',
            '',
            'def test_missing_required_field():',
            '    """Test that missing required field raises ValidationError"""',
            '    with pytest.raises(Exception):',
            f'        request = {class_name}(',
            '            # Missing required field intentionally',
            '        )',
            '',
            '',
            'def test_query_context_parsing():',
            '    """Test parsing query_context from orchestrator"""',
            f'    query_context = "{tool_def["query_context_template"]}"',
            '    ',
            '    # TODO: Implement query_context parsing logic',
            '    # parsed = parse_query_context(query_context)',
            f'    # request = {class_name}(**parsed)',
            '    # assert request is not None',
            '    pass',
        ])

        output_path = self.output_dir / f"test_{tool_name}.py"
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

        print(f"✓ Generated: {output_path}")
        return str(output_path)

    def generate_migration_guide(self, tool_spec: Dict, old_version: str) -> str:
        """Generate migration guide for deployment"""
        tool_def = tool_spec['tool_definition']
        tool_name = tool_def['name']
        new_version = self.registry.data['version']

        lines = [
            f'# Migration Guide: Adding {tool_name}',
            '',
            f'**Orchestrator Version:** {old_version} → {new_version}',
            f'**Schema Version:** {old_version} → {new_version}',
            f'**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            '',
            '---',
            '',
            '## Summary',
            '',
            f'This guide covers integration of `{tool_name}` into the decision tree orchestrator.',
            '',
            f'**Description:** {tool_def["description"]}',
            '**Change Type:** Minor (backward compatible)',
            '**Estimated Time:** 30-45 minutes',
            '**Breaking Changes:** None',
            '',
            '---',
            '',
            '## Step 1: Deploy Orchestrator (2 min)',
            '',
            '```bash',
            '# Copy generated orchestrator to production',
            f'cp generated_integration/orchestrator_dt_v{new_version}.md \\',
            '   prompts/versions/',
            '',
            '# Update symlink to latest',
            f'ln -sf versions/orchestrator_dt_v{new_version}.md \\',
            '   prompts/orchestrator_dt.md',
            '```',
            '',
            '**Files Changed:**',
            f'- `prompts/orchestrator_dt.md` → v{new_version}',
            '',
            '---',
            '',
            '## Step 2: Deploy Schema (2 min)',
            '',
            '```bash',
            '# Copy generated schema to production',
            f'cp generated_integration/simple_plan_v{new_version}.json \\',
            '   schemas/versions/',
            '',
            '# Update symlink',
            f'ln -sf versions/simple_plan_v{new_version}.json \\',
            '   schemas/simple_plan.json',
            '```',
            '',
            '**Files Changed:**',
            f'- `schemas/simple_plan.json` → v{new_version}',
            '',
            '---',
            '',
            '## Step 3: Deploy Pydantic Models (2 min)',
            '',
            '```bash',
            f'cp generated_integration/{tool_name}_models.py schemas/',
            '```',
            '',
            '**Files Changed:**',
            f'- `schemas/{tool_name}_models.py` (new)',
            '',
            '---',
            '',
            '## Step 4: Deploy Agent Prompt (5 min)',
            '',
            '```bash',
            f'cp generated_integration/{tool_name}_agent.md agents/',
            '```',
            '',
            '**Files Changed:**',
            f'- `agents/{tool_name}_agent.md` (new)',
            '',
            '---',
            '',
            '## Step 5: Add Tests (10 min)',
            '',
            '```bash',
            f'cp generated_integration/test_{tool_name}.py tests/',
            f'pytest tests/test_{tool_name}.py -v',
            '```',
            '',
            '**Expected:** All tests should pass',
            '',
            '---',
            '',
            '## Step 6: Integration Testing (15 min)',
            '',
            'Test with example queries:',
            ''
        ]

        # Add example queries
        for query in tool_def.get('example_queries', [])[:3]:
            lines.append(f'- "{query}"')

        lines.extend([
            '',
            '**Validation:**',
            f'1. Orchestrator routes to {tool_name}',
            '2. Agent generates valid parameters',
            '3. Tool executes successfully',
            '',
            '---',
            '',
            '## Rollback Procedure',
            '',
            'If issues detected:',
            '',
            '```bash',
            '# Revert orchestrator',
            f'ln -sf versions/orchestrator_dt_v{old_version}.md \\',
            '   prompts/orchestrator_dt.md',
            '',
            '# Revert schema',
            f'ln -sf versions/simple_plan_v{old_version}.json \\',
            '   schemas/simple_plan.json',
            '',
            '# Remove new files',
            f'rm agents/{tool_name}_agent.md',
            f'rm schemas/{tool_name}_models.py',
            '```',
            '',
            '---',
            '',
            '## Verification Checklist',
            '',
            f'- [ ] Orchestrator prompt deployed (v{new_version})',
            f'- [ ] Schema deployed (v{new_version})',
            '- [ ] Pydantic models deployed',
            '- [ ] Agent prompt deployed',
            '- [ ] Tests passing',
            '- [ ] Example queries tested manually',
            '- [ ] Metrics dashboard updated',
            '- [ ] Team notified',
            '',
            '---',
            '',
            '**Total Time:** ~40 minutes',
            '**Risk:** Low (minor version, backward compatible)',
            '**Confidence:** 0.92',
        ])

        output_path = self.output_dir / "MIGRATION_GUIDE.md"
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

        print(f"✓ Generated: {output_path}")
        return str(output_path)

    def add_tool(self, spec_path: str):
        """Add a new tool"""
        print(f"\nAdding tool from: {spec_path}")
        print("="*70)

        # Load spec
        tool_spec = self.load_tool_spec(spec_path)
        tool_name = tool_spec['tool_definition']['name']

        # Store old version
        old_version = self.registry.data['version']

        # Add to registry and bump version
        self.registry.add_tool(tool_spec)
        self.registry.bump_version('minor')
        self.registry.save()

        # Generate all artifacts
        print(f"\nGenerating artifacts for: {tool_name}")
        print("-"*70)

        self.generate_orchestrator_complete()
        self.generate_schema()
        self.generate_pydantic_model(tool_spec)
        self.generate_agent_prompt(tool_spec)
        self.generate_tests(tool_spec)
        self.generate_migration_guide(tool_spec, old_version)

        print("\n" + "="*70)
        print("✓ INTEGRATION COMPLETE")
        print("="*70)
        print(f"\nNew version: {self.registry.data['version']}")
        print(f"Tool added: {tool_name}")
        print(f"\nGenerated artifacts in: {self.output_dir}")
        print("\nNext steps:")
        print("  1. Review generated files")
        print("  2. Follow MIGRATION_GUIDE.md")
        print("  3. Test with example queries")
        print("  4. Deploy and monitor")

    def init(self):
        """Initialize with existing tools"""
        print("\nInitializing orchestrator with existing tools...")
        print("="*70)

        self.generate_orchestrator_complete()
        self.generate_schema()

        print("\n" + "="*70)
        print("✓ INITIALIZATION COMPLETE")
        print("="*70)
        print(f"\nVersion: {self.registry.data['version']}")
        print(f"Tools: {len(self.registry.get_tools())}")
        print(f"\nGenerated:")
        print(f"  - orchestrator_dt_v{self.registry.data['version']}.md")
        print(f"  - simple_plan_v{self.registry.data['version']}.json")

    def validate(self):
        """Validate current registry"""
        print("\nValidating tool registry...")
        print("="*70)

        tools = self.registry.get_tools()
        errors = []

        # Check for duplicate priorities
        priorities = [t['priority'] for t in tools]
        if len(priorities) != len(set(priorities)):
            errors.append("Duplicate priorities detected")

        # Check for duplicate names
        names = [t['name'] for t in tools]
        if len(names) != len(set(names)):
            errors.append("Duplicate tool names detected")

        # Check required fields
        for tool in tools:
            required_keys = ['name', 'version', 'priority', 'intent_description']
            if not all(k in tool for k in required_keys):
                errors.append(f"Tool {tool.get('name', 'UNKNOWN')} missing required fields")

        if errors:
            print("\n❌ VALIDATION FAILED")
            for err in errors:
                print(f"  - {err}")
            return False
        else:
            print("\n✓ Tool registry is valid")
            print(f"\nSummary:")
            print(f"  Version: {self.registry.data['version']}")
            print(f"  Tools: {len(tools)}")
            for tool in tools:
                print(f"    - {tool['name']} (priority {tool['priority']})")
            return True


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python tool_integration_generator.py init")
        print("  python tool_integration_generator.py add <tool_spec.yaml>")
        print("  python tool_integration_generator.py validate")
        sys.exit(1)

    command = sys.argv[1]
    generator = ToolIntegrationGenerator()

    try:
        if command == "init":
            generator.init()

        elif command == "add":
            if len(sys.argv) < 3:
                print("Error: Please provide tool spec file")
                print("Usage: python tool_integration_generator.py add <tool_spec.yaml>")
                sys.exit(1)
            generator.add_tool(sys.argv[2])

        elif command == "validate":
            generator.validate()

        else:
            print(f"Unknown command: {command}")
            print("\nAvailable commands:")
            print("  init     - Generate orchestrator from existing tools")
            print("  add      - Add a new tool")
            print("  validate - Validate tool registry")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
