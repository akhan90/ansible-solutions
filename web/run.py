import os
import logging
from app import create_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8443))
    tls_crt = "/tls/tls.crt"
    tls_key = "/tls/tls.key"

    logging.info("🚀 Starting Mutating Webhook Server")
    logging.info(f"Listening on port {port}")

    if os.path.exists(tls_crt) and os.path.exists(tls_key):
        try:
            logging.info("✅ Found TLS certs, starting HTTPS server...")
            app.run(host="0.0.0.0", port=port, ssl_context=(tls_crt, tls_key))
        except Exception as e:
            logging.error(f"❌ Failed to start HTTPS: {e}")
            logging.warning("Starting HTTP for debug.")
            app.run(host="0.0.0.0", port=port)
    else:
        logging.warning("⚠️ No TLS certs found, running HTTP (dev mode)")
        app.run(host="0.0.0.0", port=port)
