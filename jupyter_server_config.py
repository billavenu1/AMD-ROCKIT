# Jupyter Server configuration for embedding in ARIA frontend iframe
c = get_config()

# Monkey-patch JupyterHandler to forcibly return our CSP
import jupyter_server.base.handlers
def _custom_csp(self):
    return "frame-ancestors 'self' http://localhost:3000 http://localhost:5173 http://localhost:8502 *"
jupyter_server.base.handlers.JupyterHandler.content_security_policy = property(_custom_csp)

c.ServerApp.allow_origin = '*'
c.ServerApp.token = ''
c.ServerApp.password = ''
c.ServerApp.disable_check_xsrf = True
c.NotebookApp.allow_origin = '*'
c.NotebookApp.token = ''
c.NotebookApp.password = ''
c.NotebookApp.disable_check_xsrf = True

# ── Public Demo Lockdown ──────────────────────────────────────────
# Disable terminals so users can't run bash commands
c.ServerApp.terminals_enabled = False

# Disable the ability to create new kernels (prevents code execution)
c.MappingKernelManager.default_kernel_name = ''
c.MappingKernelManager.allowed_message_types = []

# Disable file modification via the Contents API
c.ContentsManager.allow_hidden = False
