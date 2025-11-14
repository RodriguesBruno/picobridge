# my_manifest.py
# Include default MicroPython RP2 manifest
include("$(BOARD_DIR)/manifest.py")

# Freeze main entry point
module("main.py", base_path="/home/maso/picobridge_build/picobridge")

# Freeze Python application code in src/
package("src", base_path="/home/maso/picobridge_build/picobridge")

# Freeze Microdot framework
package("microdot", base_path="/home/maso/picobridge_build/picobridge/lib")

# Freeze utemplate library
package("utemplate", base_path="/home/maso/picobridge_build/picobridge/lib")

# Freeze config file as raw data
freeze_file("/home/maso/picobridge_build/picobridge/config.json")
