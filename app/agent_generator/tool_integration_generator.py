#!/usr/bin/env python3
"""
Tool Integration Generator for Decision Tree Orchestrator
Automatically generates all artifacts needed to add a new tool

Usage:
    python tool_integration_generator.py init
    python tool_integration_generator.py add <tool_spec.yaml>
    python tool_integration_generator.py validate
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
        with open(spec_path) as f:
            spec = yaml.safe_load(f)

        # Basic validation
        required_fields = ['name', 'description', 'version', 'parameters', 'query_context_template']
        tool_def = spec.get('tool_definition', {})

        for field in required_fields:
            if field not in tool_def:
                raise ValueError(f"Missing required field: {field}")

        return spec
