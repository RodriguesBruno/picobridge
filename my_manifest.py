include("$(MPY_DIR)/ports/rp2/boards/manifest.py")

# Freeze an entire folder of .py files
freeze("src", opt=3)

# Freeze Microdot framework
freeze("microdot", opt=3)

# Freeze utemplate (template engine)
freeze("utemplate", opt=3)

# Freeze your templates (HTML files become frozen strings)
freeze("templates")

# Freeze static files (JS, CSS, etc.)
freeze("static")

# Freeze all Python files in top-level project folder
freeze(".", ("main.py", "config.json"))

