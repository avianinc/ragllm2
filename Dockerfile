# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first to leverage Docker cache
COPY . /app

# Install any needed packages specified in requirements.txt
# Make sure jupyterlab is listed in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install supervisord
RUN apt-get update && apt-get install -y supervisor

# Make port 5000 available for Flask and port 8888 for Jupyter Lab
EXPOSE 5000 8888

# Define environment variable for Flask
ENV FLASK_APP=app.py

# Supervisor configuration file
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Run supervisord when the container launches
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
