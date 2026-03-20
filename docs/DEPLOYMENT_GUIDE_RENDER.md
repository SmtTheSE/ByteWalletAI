# 🚀 ByteWallet AI: Render Deployment Guide

This guide provides step-by-step instructions to deploy ByteWallet AI as a "One-Click" service on [Render](https://render.com).

## 1. Prerequisites
- A **GitHub** account containing your ByteWallet AI repository.
- A **Render** account (Free tier is sufficient).
- **Ngrok** (Optional: Only if you want to connect the cloud API to your local Ollama LLM).

---

## 2. One-Click Deployment Flow

### Step A: Connect to Render
1.  Log in to the [Render Dashboard](https://dashboard.render.com).
2.  Click **"New +"** and select **"Blueprint"**.
3.  Connect your GitHub repository `SmtTheSE/ByteWalletAI`.
4.  Render will automatically detect the `render.yaml` file.

### Step B: Configure Environment Variables
During the blueprint setup, Render will ask for values. You can keep the defaults, but for production AI voice:
-   `OLLAMA_BASE_URL`: If you want to use your local Mac's Ollama, set this to your **Ngrok URL** (e.g., `https://random-id.ngrok-free.app`).
-   `OLLAMA_MODEL`: Default is `qwen2.5:latest`.

---

## 3. Connecting to Local Ollama (The "Hybrid" Secret)
Since LLMs are heavy, running them on a free cloud tier is slow. We recommended running Ollama on your local Mac and tunneling it to Render:

1.  **Start Ollama locally**: `ollama serve`
2.  **Start Ngrok tunnel**: 
    ```bash
    ngrok http 11434 --host-header="localhost:11434"
    ```
3.  **Update Render**: In your Render Dashboard settings, update `OLLAMA_BASE_URL` with the Ngrok address.

---

## 4. Verification
Once deployed, your API will be live at `https://bytewallet-ai.onrender.com`.
Test it with a simple health check:
```bash
curl https://bytewallet-ai.onrender.com/
```

**ByteWallet AI is now live in the cloud!** 🌍🛰️
