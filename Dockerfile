
# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for OpenCV and EasyOCR
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# We use --no-cache-dir to keep the image small, but for offline builds
# you might want to bundle the wheels if building completely offline is required.
# As per instructions, we assume this build process happens WITH internet, 
# resulting in an image that runs WITHOUT internet.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# IMPORTANT: The model MUST be downloaded during the build process
# so it is baked into the image.
RUN python setup_model.py

# Define environment variable
ENV PYTHONUNBUFFERED=1

# Run main.py when the container launches
# Default command processes the train directory (mounted as volume recommended)
ENTRYPOINT ["python", "main.py"]
CMD ["--input", "/data", "--output", "/data/results.json"]
