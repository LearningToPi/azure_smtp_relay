# Azure SMTP Relay Docker Image

The Docker image is based on the official Python3.11 docker image.  The image is available on Docker Hub.  The Dockerfile in GitHub can also be used to build your own docker image.

The image on Docker Hub is built with the following options:

- TCP port 10025
- Running as username "python"
- "python" uid / gid set to 40000
- All required dependencies installed from requirements.txt file

## Running the Docker Image

The docker image accepts either command line parameters or a config.toml file. All parameters passed to the container will be applied to the azure_smtp_relay module. This means that all parameters from the README.md file are available for use.  However, the recommended setup is to use a config.toml file mapped to the container.  The config file should be mapped to "/app/config.toml"

Running with host port 25 redirected to the container, a TOML config file as well as command line parameters:

    docker run -d --name azure-smtp-relay -p 25:10025 -v [full local path]/config.toml:/app/config.toml learningtopi/azure_smtp_relay:latest --log-level DEBUG --max-queue-length 200

## Building the Image

If you would like to run the container with a different username or uid, download the Dockerfile and provide alternate username or uid as a argument to the build process. This allows for quick modification of the credentials to match your system if needed.

    docker build --build-arg USERNAME=smtp --build-arg UID=40001 -t azure_smtp_relay_local:1.0.3 .