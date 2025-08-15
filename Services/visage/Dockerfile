 FROM python:3.10

  # Install minimal dependencies for OpenCV and CUDA support
  RUN apt-get update && apt-get install -y \
      libgl1-mesa-dri \
      libglib2.0-0 \
      libsm6 \
      libxext6 \
      libxrender-dev \
      libgomp1 \
      ffmpeg \
      curl \
      && rm -rf /var/lib/apt/lists/*

  # Create a non-root user
  RUN useradd -m -u 1000 user

  WORKDIR /code

  # Set environment variables
  ENV MPLCONFIGDIR=/code/matplotlib
  ENV DEEPFACE_HOME=/code/.deepface

  # Create necessary directories
  RUN mkdir -p /code/models /code/data /code/config /code/.deepface /code/matplotlib && \
      chown -R user:user /code

  # Switch to user
  USER user

  # Copy requirements and install dependencies
  COPY --chown=user:user ./requirements.txt /code/requirements.txt

  RUN pip install --no-cache-dir --upgrade pip && \
      pip install --no-cache-dir --upgrade -r /code/requirements.txt

  # Copy application files
  COPY --chown=user:user ./app.py /code/
  COPY --chown=user:user ./faces.json /code/
  COPY --chown=user:user ./persons.zip /code/
  COPY --chown=user:user ./models/ /code/models/

  # Expose ports for Gradio and FastAPI
  EXPOSE 7860 8000

  CMD ["python", "app.py"]