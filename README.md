# Voice-to-Notes

A beginner-friendly web app that records your voice, transcribes it with
Azure AI Speech, and lets you save/view/edit/delete notes. Demonstrates a
full DevOps pipeline: Git/GitHub -> Docker -> Jenkins -> Kubernetes -> Azure.

## Quick Start (Local)

    python -m venv venv
    source venv/Scripts/activate      # Linux/Mac: venv/bin/activate
    pip install -r requirements.txt -r requirements-dev.txt
    cp .env.example .env
    pytest
    python app.py

Open http://localhost:5000

## Docker

    docker build -t voice-to-notes:local .
    docker run -d --name voice-to-notes -p 5000:5000 \
      -e AZURE_SPEECH_KEY="your_key" -e AZURE_SPEECH_REGION="your_region" \
      voice-to-notes:local

## Jenkins

Run Jenkins in Docker, install suggested plugins + Docker Pipeline,
create credentials: acr-credentials, aks-kubeconfig, azure-speech-key,
azure-speech-region. Create a Pipeline job pointing at this repo's
Jenkinsfile.

## Kubernetes / Azure

Create Azure resources (Resource Group, ACR, AKS), connect kubectl,
then apply manifests in the k8s/ folder:

    kubectl apply -f k8s/configmap.yaml
    kubectl apply -f k8s/pvc.yaml
    kubectl apply -f k8s/secret.yaml   (copy from secret.example.yaml first)
    kubectl apply -f k8s/deployment.yaml
    kubectl apply -f k8s/service.yaml

IMPORTANT: Azure AI Speech, ACR, and AKS incur costs. Delete resources
after testing with: az group delete --name <resource-group> --yes --no-wait

## Testing

    pytest

All Azure Speech calls are mocked in tests - no credentials or cost needed
to run the automated test suite.

## Known Limitations

- SQLite + 1 replica only (not for horizontal scaling).
- No authentication (do not store sensitive data).
- Kubernetes Secrets are base64-encoded, not encrypted by default.
