# Use the official Python base image
FROM python:3.11-slim

# Install OpenVPN and required dependencies
RUN apt-get update && \
    apt-get install -y openvpn curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --trusted-host pypi.python.org -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Create a directory for VPN configs
RUN mkdir -p /app/vpn_configs

# Set the VPN config directory as a volume
VOLUME /app/vpn_configs

# Run the script when the container launches
CMD ["python", "mt_rose_lift_checker.py"]
