# Configuration file for jupyter-server.

c = get_config()  #noqa

# Security settings to allow iframe embedding
# Setting frame-ancestors to 'self' and * allows embedding in any site (including localhost:5173)
c.ServerApp.tornado_settings = {
    'headers': {
        'Content-Security-Policy': "frame-ancestors 'self' *;",
        'Access-Control-Allow-Origin': '*',
        'X-Frame-Options': 'ALLOWALL' # Attempt to override default SAMEORIGIN if present
    }
}

# Network and Server settings
c.ServerApp.ip = '0.0.0.0'
c.ServerApp.port = 8888
c.ServerApp.open_browser = False

# Authentication and Access
c.ServerApp.token = 'inzyts-token'
c.ServerApp.allow_origin = '*'  # Allow requests from any origin
c.ServerApp.disable_check_xsrf = True  # Disable XSRF check for easier embedding development
