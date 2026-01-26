"""
Additional generator methods - include these in main file
"""

def generate_orchestrator_complete(self) -> str:
    """Generate complete orchestrator prompt"""

    if self.jinja_env is None:
        print("⚠️  No Jinja2 or template found. Skipping orchestrator generation.")
        print("   Install jinja2: pip install jinja2")
        print("   Create templates/orchestrator_dt_base_template.md")
        return None

    try:
        template = self.jinja_env.get_template('orchestrator_dt_base_template.md')
    except:
        print("⚠️  orchestrator_dt_base_template.md not found. Skipping.")
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
