include("$(MPY_DIR)/ports/rp2/boards/manifest.py")
# Freeze all Python files in top-level project folder
freeze(".", ("main.py",))

# Freeze an entire folder of .py files
freeze("src")

# Freeze Microdot framework
freeze("microdot")

# Freeze utemplate (template engine)
freeze("utemplate")

# Freeze your templates (HTML files become frozen strings)
freeze("templates")

# Freeze static files (JS, CSS, etc.)
freeze("static")

