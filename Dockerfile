FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 \
    HOME=/app \
    MODEL_DIR=/app/models \
    JOBS_DIR=/data/jobs \
    DB_PATH=/data/jobs.db \
    HRTF_ZIP=/app/8d-render/hrtf/full.zip \
    RENDER_SCRIPT=/app/8d-render/8d_render.py

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install audio-separator onnxruntime==1.27.0 fastapi "uvicorn[standard]" python-multipart

WORKDIR /app
COPY 8d-studio /app/8d-studio
COPY 8d_songs/8d_render.py /app/8d-render/8d_render.py
COPY 8d_songs/hrtf/full.zip /app/8d-render/hrtf/full.zip

RUN audio-separator -m htdemucs_6s.yaml --model_file_dir /app/models --download_model_only \
    && audio-separator -m htdemucs_ft.yaml --model_file_dir /app/models --download_model_only \
    && audio-separator -m MDX23C-8KFFT-InstVoc_HQ.ckpt --model_file_dir /app/models --download_model_only

VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app/8d-studio"]
