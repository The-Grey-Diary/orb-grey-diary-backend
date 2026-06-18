import os, sys
def main():
    port = int(os.environ.get("PORT", 8080))
    print(f"[Grey Diary] Starting on 0.0.0.0:{port}", flush=True)
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, workers=1, log_level="info")
if __name__ == "__main__":
    main()
