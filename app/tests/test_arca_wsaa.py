from app.integrations.arca.wsaa_client import ArcaWSAAClient

def main():
    client = ArcaWSAAClient()
    auth = client.get_auth()

    print("✅ Autenticado correctamente contra ARCA/AFIP")
    print("CUIT:      ", auth.cuit)
    print("Token (ini):", auth.token[:80], "...")
    print("Sign  (ini):", auth.sign[:80], "...")
    print("Vence:     ", auth.expires_at)

if __name__ == "__main__":
    main()
