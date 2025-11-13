include("$(MPY_DIR)/ports/rp2/boards/manifest.py")

# Python modules
freeze(".", ("main.py",))

# Static JSON
freeze_file("config.json")

# Your Python packages
freeze("src")
freeze("microdot")

# Template engine runtime only
freeze("utemplate", ("template.py", "utemplate.py", "helpers.py"))

# Freeze assets only
freeze_dir("templates")
freeze_dir("static")
