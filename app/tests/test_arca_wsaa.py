from app.integrations.arca.wsaa_client import ArcaWSAAClient

def main():
    client = ArcaWSAAClient()
    auth = client.get_auth()

if __name__ == "__main__":
    main()
