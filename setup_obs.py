import os
import glob

def patch_main_py(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if "setup_logging" in content:
        print(f"Already patched: {filepath}")
        return

    # Find the service name
    service_name = "unknown"
    for line in content.split('\n'):
        if "create_service_app(service_name=" in line:
            import re
            m = re.search(r'service_name=["\'](.*?)["\']', line)
            if m:
                service_name = m.group(1)
                break
                
    # Insert imports
    import_statement = "\nfrom observability import setup_logging, setup_tracing, setup_metrics\n"
    
    # We want to insert the setup calls right after app = create_service_app(...)
    setup_calls = f"""

# Observability setup
setup_logging(service_name="{service_name}")
setup_tracing(service_name="{service_name}", app=app)
setup_metrics(app)
"""

    if "from contracts.service_factory import create_service_app" in content:
        content = content.replace(
            "from contracts.service_factory import create_service_app",
            "from contracts.service_factory import create_service_app" + import_statement
        )
    else:
        # Just prepend if not found
        content = import_statement + content
        
    # Replace the app creation line
    target_line = f'app = create_service_app(service_name="{service_name}")'
    if target_line in content:
        content = content.replace(target_line, target_line + setup_calls)
    else:
        target_line2 = f"app = create_service_app(service_name='{service_name}')"
        if target_line2 in content:
            content = content.replace(target_line2, target_line2 + setup_calls)
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Patched {filepath}")

if __name__ == "__main__":
    for filepath in glob.glob("backend/services/*/app/main.py"):
        patch_main_py(filepath)
