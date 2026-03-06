import sys
import os
import subprocess
import importlib.util

# 1. Create mock gint module
with open("web-tools/gint.py", "w") as f:
    f.write("""
class Font:
    def __init__(self, *args):
        self.args = args
    def __repr__(self):
        return f"Font({self.args})"

def font(*args):
    return Font(*args)

def image(*args):
    pass
""")

# 2. Paths
repo_root = os.getcwd()
fxconv_py = os.path.join(repo_root, "tools", "fxconv-main.py")
fxconv_js = os.path.join(repo_root, "web-tools", "fxconv_cli.js")
font_img = os.path.join(repo_root, "PythonExtra", "ports", "sh", "examples", "fonts", "font_shmup.png")
ref_out = os.path.join(repo_root, "web-tools", "reference_shmup.py")
test_out = os.path.join(repo_root, "web-tools", "test_shmup.py")

# 3. Run Reference Tool
print("Running reference tool...")
env = os.environ.copy()
env["PYTHONPATH"] = env.get("PYTHONPATH", "") + ":" + os.path.join(repo_root, "tools")
cmd_ref = [
    sys.executable, fxconv_py,
    "--font", font_img,
    "-o", ref_out,
    "--py",
    "name:font_shmup",
    "charset:print",
    "grid.size:10x13",
    "grid.padding:0",
    "grid.border:0",
    "proportional:true"
]
ret = subprocess.run(cmd_ref, env=env, capture_output=True, text=True)
if ret.returncode != 0:
    print("Reference tool failed:")
    print(ret.stderr)
    sys.exit(1)

# 4. Run Test Tool
print("Running test tool...")
cmd_test = [
    "node", fxconv_js,
    font_img,
    "-o", test_out,
    "name:font_shmup",
    "charset:print",
    "grid.size:10x13",
    "grid.padding:0",
    "grid.border:0",
    "proportional:true"
]
ret = subprocess.run(cmd_test, capture_output=True, text=True)
if ret.returncode != 0:
    print("Test tool failed:")
    print(ret.stderr)
    sys.exit(1)

# 5. Compare
print("Comparing results...")
sys.path.append(os.path.join(repo_root, "web-tools"))

try:
    import reference_shmup
    import test_shmup
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

ref_font = reference_shmup.font_shmup
test_font = test_shmup.font_shmup

# Compare args
if len(ref_font.args) != len(test_font.args):
    print(f"Argument count mismatch! Ref: {len(ref_font.args)}, Test: {len(test_font.args)}")
    sys.exit(1)

# Check widths first (Arg 13, index 12)
if len(ref_font.args) > 12:
    widths_ref = ref_font.args[12]
    widths_test = test_font.args[12]
    if widths_ref != widths_test:
        print("Widths mismatch (Arg 12)!")
        print(f"Ref len: {len(widths_ref)}, Test len: {len(widths_test)}")
        for j in range(min(len(widths_ref), len(widths_test))):
            if widths_ref[j] != widths_test[j]:
                print(f"Width mismatch at glyph {j}: Ref {widths_ref[j]} vs Test {widths_test[j]}")
        sys.exit(1)

for i, (arg_ref, arg_test) in enumerate(zip(ref_font.args, test_font.args)):
    if arg_ref != arg_test:
        print(f"Mismatch at argument {i}:")
        # Truncate long output
        r_repr = repr(arg_ref)
        t_repr = repr(arg_test)
        if len(r_repr) > 100: r_repr = r_repr[:100] + "..."
        if len(t_repr) > 100: t_repr = t_repr[:100] + "..."

        print(f"Ref:  {r_repr}")
        print(f"Test: {t_repr}")

        # If it's bytes, maybe diff them
        if isinstance(arg_ref, bytes):
            print("Bytes mismatch details:")
            if len(arg_ref) != len(arg_test):
                 print(f"Length mismatch: {len(arg_ref)} vs {len(arg_test)}")
            else:
                 for j in range(len(arg_ref)):
                     if arg_ref[j] != arg_test[j]:
                         print(f"Byte {j}: {arg_ref[j]} vs {arg_test[j]}")
                         break
        sys.exit(1)

print("SUCCESS: Generated font matches reference exactly.")
